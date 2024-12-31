import google.generativeai as genai
import os, discord, logging, aiohttp, datetime, asyncio, time, tempfile
from engine.db import fetch_recent_message, supabase
from dotenv import load_dotenv
from google.generativeai import caching
from typing import Optional
import subprocess
            
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

GOOGLE_API_KEY = os.getenv('GEMINI_PRO_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)

async def get_media_duration(file_path: str, content_type: str) -> float:
    """Get media duration using ffprobe with fallback"""
    if not os.path.exists(file_path):
        logging.error(f"File not found: {file_path}")
        return 5.0

    try:
        # Use ffprobe to get duration
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            file_path
        ]
        
        for attempt in range(3):  # Try 3 times
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.stdout.strip():
                    duration = float(result.stdout.strip())
                    logging.info(f"Media duration from ffprobe: {duration:.1f}s")
                    return duration
                await asyncio.sleep(1)  # Wait before retry
            except ValueError:
                if attempt == 2:  # Last attempt
                    logging.warning("Could not parse duration, using fallback")
                    return 5.0
                continue
                
        logging.warning("Could not get duration from ffprobe, using fallback")
        return 5.0

    except Exception as e:
        logging.error(f"Error getting media duration: {str(e)}")
        return 5.0
    
# Modify prep_file to handle videos differently
def prep_file(file_path, display_name, is_av=False):
    sample_file = genai.upload_file(path=file_path, display_name=display_name)
    logging.info(f"Uploaded file '{sample_file.display_name}' as: {sample_file.uri}")
    return sample_file

PRIMARY_MODEL = "models/gemini-2.0-flash-exp"
FALLBACK_MODEL = "models/gemini-1.5-flash"

# Quota tracking
last_quota_failure = None
quota_reset_hour = 0  # Midnight UTC

async def get_active_model():
    global last_quota_failure
    
    # Check if we should reset quota failure status
    if last_quota_failure:
        now = datetime.datetime.now(datetime.timezone.utc)
        if now.day != last_quota_failure.day:
            last_quota_failure = None
            logging.info("Quota status reset for new day")
    
    # Use fallback if quota was exhausted today
    if last_quota_failure:
        logging.info(f"Using fallback model {FALLBACK_MODEL} due to quota exhaustion")
        return FALLBACK_MODEL
    return PRIMARY_MODEL

async def extract_content_from_file(sample_file, prompt, is_av=False, duration=0):
    """Extract content with improved media handling and caching"""
    global last_quota_failure
    
    try:
        active_model = await get_active_model()
        logging.info(f"Using model: {active_model}")
        
        # Handle AV specific processing
        if is_av:
            max_wait = 300  # 5 minutes timeout
            start_time = time.time()
            
            while sample_file.state.name == 'PROCESSING':
                logging.info('Waiting for media file to be processed...')
                await asyncio.sleep(2)
                sample_file = genai.get_file(sample_file.name)
                
                if time.time() - start_time > max_wait:
                    logging.error("Media processing timeout")
                    return None
                    
            logging.info(f'Media processing complete: {sample_file.uri}')
        
        # Only use caching for 1.5 model
        for attempt in range(3):
            try:
                if active_model == FALLBACK_MODEL:
                    cache = caching.CachedContent.create(
                        model=active_model,
                        display_name=getattr(sample_file, 'name', 'content'),
                        system_instruction='You are a content analyzer, analyze the provided content.',
                        contents=[sample_file],
                        ttl=datetime.timedelta(minutes=5 if is_av else 2),
                    )
                    model = genai.GenerativeModel.from_cached_content(cached_content=cache)
                else:
                    model = genai.GenerativeModel(active_model)
                
                response = model.generate_content([sample_file, prompt])
                
                if response and response.candidates:
                    # Check finish reason and handle response
                    if response.candidates[0].finish_reason == 8:  # SAFETY
                        logging.error("Response blocked by safety filters")
                        continue
                        
                    # Try to get text from response parts
                    if response.candidates[0].content and response.candidates[0].content.parts:
                        for part in response.candidates[0].content.parts:
                            if hasattr(part, 'text') and part.text:
                                logging.info(f"Token usage: {response.usage_metadata}")
                                return part.text
                                
                    logging.error(f"Invalid response format: {response}")
                    
            except Exception as e:
                logging.error(f"Attempt {attempt + 1} failed: {str(e)}")
                if "quota" in str(e).lower():
                    last_quota_failure = datetime.datetime.now(datetime.timezone.utc)
                    logging.warning(f"Quota exhausted for {active_model}, switching to fallback")
                    if active_model == PRIMARY_MODEL:
                        active_model = FALLBACK_MODEL
                        continue
                if attempt < 2:
                    await asyncio.sleep(3)
        return None
                
    except Exception as e:
        logging.error(f"Error extracting content: {str(e)}")
        return None

# Download and process an attachment from a URL
async def handle_attachment(bot, message, attachment):
    file_path = None
    try:
        # File size limit - 20MB for videos, 10MB for others
        size_limit = 20 * 1024 * 1024 if attachment.content_type.startswith('video/') else 10 * 1024 * 1024
        if attachment.size > size_limit:
            await message.reply(f"File too large. Maximum size is {size_limit//1024//1024}MB.")
            return
        # Determine the content type of the file
        content_type = attachment.content_type
        logging.info(f"Content Type: {content_type}")

        # Define supported content types
        supported_types = ['image/', 'application/', 'text/', 'video/', 'audio/']
        is_supported = any(content_type.startswith(supported) for supported in supported_types)

        if not is_supported:
            await message.reply("Unsupported file type. Please upload an image, PDF, video, audio, text/code or text/plain file.")
            return

        # Set the local file path
        _, file_extension = os.path.splitext(attachment.filename)
        file_path = f"downloaded_file{file_extension}"

        # Download the file
        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.url) as resp:
                if resp.status == 200:
                    with open(file_path, "wb") as f:
                        f.write(await resp.read())
                    logging.info("Downloaded file successfully.")
                else:
                    await message.reply("Failed to download the file.")
                    return

        # Check if file is video
        is_av = attachment.content_type.startswith(('video/', 'audio/'))
        
        # Get media duration if video/audio
        duration = 0
        if is_av:
            duration = await get_media_duration(file_path, attachment.content_type)
            if duration > 300:  # 5 minute limit
                await message.reply("Media file too long. Maximum duration is 5 minutes.")
                return
            await message.reply(f"Processing {duration:.1f} second media file, please wait...")

        # Upload file with video flag
        sample_file = prep_file(file_path, attachment.filename, is_av=is_av)
        
        # Retrieve the last relevant message, prioritizing the user’s recent message
        last_message = fetch_recent_message(supabase, guild_id=str(message.guild.id), user_id=str(message.author.id))

        if last_message:
            context_message = f"Last relevant message in the guild: {last_message['content']}\n"
            context_message += f"Bot response to that message: {last_message['response']}\n"
        else:
            context_message = ""
        # Determine the prompt
        prompt = message.content.strip().replace(f"<@{bot.user.id}>", "").replace("seeyuh", "").strip()
        if not prompt:
            if content_type.startswith('image/'):
                prompt = "Explain the content of the image."
            elif content_type.startswith ('application/'):
                prompt = "Provide a summary of the document."
            elif content_type.startswith('text/'):
                prompt = "Provide an analysis of the text file."
            elif content_type.startswith('video/'):
                prompt = "Provide a summary of the video."
            elif content_type.startswith('audio/'):
                prompt = "Provide an analysis of the audio."    
            else:
                prompt = "Analyze the content of the file."
        prompt = f"You are a chill discord bot with multimodal AI features. Your responses are genz style.\n{context_message} \nCurrent query: {prompt}"
        extracted_content = await extract_content_from_file(
            sample_file, 
            prompt, 
            is_av=is_av,
            duration=duration
        )

        if extracted_content:
            with tempfile.TemporaryDirectory() as temp_dir:
                message_components = []  # List of (content_type, content) tuples
                text = extracted_content
                text_only_content = ""  # For database storage
                
                # Process content sequentially
                while '```' in text:
                    # Get text before code block
                    pre_code = text[:text.find('```')].strip()
                    if pre_code:
                        message_components.append(('text', pre_code))
                        text_only_content += pre_code + "\n"
                    
                    # Extract code block
                    lang_start = text.find('```') + 3
                    lang_end = text.find('\n', lang_start)
                    file_ext = '.' + text[lang_start:lang_end].strip().lower()
                    code_start = text.find('\n', lang_end) + 1
                    code_end = text.find('```', code_start)
                    code = text[code_start:code_end]
                    
                    # Get remaining text
                    text = text[text.find('```', code_end) + 3:].strip()
                    
                    if code.strip():
                        if file_ext.lower() == '.csv':
                            # Handle CSV in chunks
                            csv_lines = code.strip().split('\n')
                            chunk_size = 1000
                            chunks = [csv_lines[i:i + chunk_size] for i in range(0, len(csv_lines), chunk_size)]
                            
                            for i, chunk in enumerate(chunks):
                                code_path = os.path.join(temp_dir, f'data_part_{i+1}{file_ext}')
                                with open(code_path, 'w', encoding='utf-8') as f:
                                    f.write('\n'.join(chunk))
                                message_components.append(('file', discord.File(code_path)))
                        else:
                            code_path = os.path.join(temp_dir, f'code_{len([c for c in message_components if c[0] == "file"])}{file_ext}')
                            with open(code_path, 'w', encoding='utf-8') as f:
                                f.write(code)
                            message_components.append(('file', discord.File(code_path)))
                
                # Add remaining text
                if text:
                    message_components.append(('text', text))
                    text_only_content += text + "\n"
                
                # Send messages respecting Discord's limits
                current_files = []
                current_text = []
                
                for comp_type, content in message_components:
                    if comp_type == 'text':
                        current_text.append(content)
                        if current_files:  # Send accumulated files
                            await message.reply(
                                content="\n".join(current_text)[:2000] if current_text else "Here's your code:",
                                files=current_files
                            )
                            current_files = []
                            current_text = []
                    else:  # File
                        current_files.append(content)
                        if len(current_files) >= 10:
                            await message.reply(
                                content="\n".join(current_text)[:2000] if current_text else "Here's your code:",
                                files=current_files
                            )
                            current_files = []
                            current_text = []
                
                # Send any remaining content
                if current_files or current_text:
                    await message.reply(
                        content="\n".join(current_text)[:2000] if current_text else None,
                        files=current_files if current_files else None
                    )
                
                return text_only_content.strip() or "Generated files have been sent."
        
        else:
            await message.reply("Failed to extract content from the file.")
            return "Failed to extract content from the file."

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        await message.reply("An error occurred while processing the file.")
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logging.info("Deleted temporary file.")

async def handle_interaction(
    interaction: discord.Interaction,
    file: discord.Attachment,
    prompt: Optional[str] = None
):
    # Initialize file_path as None at the start
    file_path = None
    
    try:
        # File size limit - 20MB for videos, 10MB for others
        size_limit = 20 * 1024 * 1024 if file.content_type.startswith('video/') else 10 * 1024 * 1024
        if file.size > size_limit:
            await interaction.followup.send(f"File too large. Maximum size is {size_limit//1024//1024}MB.")
            return
        
        # Determine the content type of the file
        content_type = file.content_type
        logging.info(f"Content Type: {content_type}")
        
        # Set the local file path before first use
        _, file_extension = os.path.splitext(file.filename)
        file_path = f"downloaded_file{file_extension}"
        
        # Define supported content types
        supported_types = ['image/', 'application/', 'text/', 'video/', 'audio/']
        is_supported = any(content_type.startswith(supported) for supported in supported_types)

        if not is_supported:
            await interaction.followup.send("Unsupported file type. Please upload an image, PDF, video, audio, text/code or text/plain file.")
            return

        # Download the file
        async with aiohttp.ClientSession() as session:
            async with session.get(file.url) as resp:
                if resp.status == 200:
                    with open(file_path, "wb") as f:
                        f.write(await resp.read())
                    logging.info("Downloaded file successfully.")
                else:
                    await interaction.followup.send("Failed to download the file.")
                    return

        # Upload the downloaded file and prepare it for analysis
        is_av = file.content_type.startswith(('video/', 'audio/'))
        
        # Get media duration if video/audio
        duration = 0
        if is_av:
            duration = await get_media_duration(file_path, file.content_type)
            if duration > 300:  # 5 minute limit
                await interaction.followup.send("Media file too long. Maximum duration is 5 minutes.")
                return
            await interaction.followup.send(f"Processing {duration:.1f} second media file, please wait...")

        sample_file = prep_file(file_path, file.filename, is_av=is_av)

        # Determine the prompt
        if not prompt:
            if content_type.startswith('image/'):
                prompt = "Explain the content of the image."
            elif content_type.startswith('application/'):
                prompt = "Provide a summary of the document."
            elif content_type.startswith('text/'):
                prompt = "Provide an analysis of the text file."
            elif content_type.startswith('video/'):
                prompt = "Provide a summary of the video."  
            elif content_type.startswith('audio/'):
                prompt = "Provide an analysis of the audio."  
            else:
                prompt = "Analyze the content of the file."
        prompt = f"Generate a response to the following prompt under 4096 characters: {prompt}"
        extracted_content = await extract_content_from_file(
            sample_file, 
            prompt, 
            is_av=is_av,
            duration=duration
        )

        # Reply with extracted content
        if extracted_content:
            # Split the content into chunks if it exceeds the embed size limit
            max_embed_size = 6000
            content_chunks = [extracted_content[i:i + max_embed_size] for i in range(0, len(extracted_content), max_embed_size)]

            for chunk in content_chunks:
                embed = discord.Embed(
                    title="Image Analysis" if content_type.startswith('image/') else "Video Analysis" if content_type.startswith('video/') else "File Analysis",
                    description=chunk,
                    color=0x00ff00
                )
                icon_url = (
                str(interaction.client.user.avatar.url)
                if interaction.client.user.avatar
                else str(interaction.client.user.default_avatar.url)
                )
                if content_type.startswith('image/'):
                    embed.set_image(url=file.url)
                    embed.set_thumbnail(url=file.url)
                embed.set_footer(
                    text=interaction.client.user.name,
                    icon_url=icon_url
                )
                if not content_type.startswith('image/'):
                    await interaction.followup.send(embed=embed, file=discord.File(file_path))
                else:
                    await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("Failed to extract content from the file.")

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        await interaction.followup.send("An error occurred while processing the file.")
    finally:
        # Clean up by deleting the downloaded file if it exists
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logging.info("Deleted temporary file.")
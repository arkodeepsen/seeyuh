import google.generativeai as genai
import os, discord, logging, aiohttp, datetime, asyncio, time, tempfile, io
from engine.db import fetch_recent_message, supabase
from dotenv import load_dotenv
from google.generativeai import caching
from typing import Optional
import subprocess
import re
from google.genai import types
            
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
from engine.ai.gemini import genai_client

# YouTube URL pattern
YOUTUBE_PATTERN = re.compile(
    r'(?:https?://)?(?:www\.)?' 
    r'(?:youtube\.com/watch\?v=|youtu\.be/)' 
    r'([a-zA-Z0-9_-]{11})'
)

# General URL pattern (excluding YouTube)
GENERAL_URL_PATTERN = re.compile(
    r'https?://(?!(?:www\.)?(?:youtube\.com|youtu\.be))[^\s]+',
    re.IGNORECASE
)

async def wait_for_file_active(file_obj, timeout_seconds: int = 300, poll_interval: float = 1.5):
    """Poll Gemini Files API until the uploaded file becomes ACTIVE.

    Returns the refreshed file object once ACTIVE. Raises on FAILED or timeout.
    """
    start_time = time.time()
    name = getattr(file_obj, 'name', file_obj)
    last_state = None
    while True:
        try:
            refreshed = await asyncio.to_thread(genai.get_file, name)
            state = getattr(getattr(refreshed, 'state', None), 'name', None) or getattr(refreshed, 'state', None)
            if state != last_state:
                logging.info(f"File {name} state: {state}")
                last_state = state
            if state == 'ACTIVE':
                return refreshed
            if state == 'FAILED':
                raise RuntimeError(f"File {name} processing failed")
        except Exception as e:
            logging.debug(f"wait_for_file_active polling error: {e}")

        if time.time() - start_time > timeout_seconds:
            raise TimeoutError(f"File {name} did not become ACTIVE within {timeout_seconds}s")
        await asyncio.sleep(poll_interval)

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

PRIMARY_MODEL = "models/gemini-2.5-flash"
FALLBACK_MODEL = "models/gemini-2.0-flash"

# Image editing models
PRIMARY_IMAGE_MODEL = "gemini-2.5-flash-image-preview"
FALLBACK_IMAGE_MODEL = "gemini-2.0-flash-preview-image-generation"

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

async def get_active_image_model():
    global last_quota_failure
    
    # Check if we should reset quota failure status
    if last_quota_failure:
        now = datetime.datetime.now(datetime.timezone.utc)
        if now.day != last_quota_failure.day:
            last_quota_failure = None
            logging.info("Image model quota status reset for new day")
    
    # Use fallback if quota was exhausted today
    if last_quota_failure:
        logging.info(f"Using fallback image model {FALLBACK_IMAGE_MODEL} due to quota exhaustion")
        return FALLBACK_IMAGE_MODEL
    return PRIMARY_IMAGE_MODEL

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
async def handle_url_context(bot, message, urls: list):
    """Handle general URLs using URL context tool"""
    try:
        text_input = message.content.strip().replace(f"<@{bot.user.id}>", "").replace("seeyuh", "").strip()
        # Remove URLs from the prompt
        for url in urls:
            text_input = text_input.replace(url, '').strip()
        
        if not text_input:
            text_input = f"Analyze and summarize the content from the following URL{'s' if len(urls) > 1 else ''}: {', '.join(urls)}"
        else:
            # Include URLs in the prompt for context
            text_input = f"{text_input}\n\nRelevant URLs: {', '.join(urls)}"
        
        logging.info(f"Processing {len(urls)} URL(s) with URL context tool")
        async with message.channel.typing():
            active_model = await get_active_model()
            logging.info(f"Using model: {active_model}")
            
            # Configure URL context tool
            tools = [{"url_context": {}}]
            
            for attempt in range(2):
                try:
                    response = await asyncio.to_thread(
                        genai_client.models.generate_content,
                        model=active_model,
                        contents=text_input,
                        config=types.GenerateContentConfig(tools=tools)
                    )
                    
                    if response and response.candidates and response.candidates[0].content.parts:
                        full_text = []
                        for part in response.candidates[0].content.parts:
                            if hasattr(part, 'text') and part.text:
                                full_text.append(part.text)
                        
                        text = '\n'.join(full_text).strip()
                        if text:
                            # Log URL context metadata if available
                            if hasattr(response.candidates[0], 'url_context_metadata'):
                                logging.info(f"URL context metadata: {response.candidates[0].url_context_metadata}")
                            
                            # Chunk response if too long
                            if len(text) <= 2000:
                                await message.reply(text)
                            else:
                                # Send in meaningful chunks
                                remaining = text
                                while len(remaining) > 2000:
                                    slice_ = remaining[:2000]
                                    cut = max(slice_.rfind('\n\n'), slice_.rfind('\n'), slice_.rfind('. '))
                                    if cut < 1000:
                                        cut = 2000
                                    await message.reply(remaining[:cut].strip())
                                    remaining = remaining[cut:].lstrip()
                                if remaining:
                                    await message.reply(remaining)
                            return text
                    break
                except Exception as e:
                    logging.error(f"URL context processing attempt {attempt + 1} failed: {str(e)}")
                    if "quota" in str(e).lower():
                        last_quota_failure = datetime.datetime.now(datetime.timezone.utc)
                        if active_model == PRIMARY_MODEL:
                            active_model = FALLBACK_MODEL
                            continue
                    if attempt < 1:
                        await asyncio.sleep(2)
                    else:
                        await message.reply(f"❌ Failed to process URL(s): {str(e)}")
                        return None
    except Exception as e:
        logging.error(f"URL context handling error: {e}")
        await message.reply(f"❌ Error processing URL(s): {str(e)}")
        return None

async def handle_youtube_url(bot, message, youtube_url: str):
    """Handle YouTube URL directly via Gemini API"""
    try:
        text_input = message.content.strip().replace(f"<@{bot.user.id}>", "").replace("seeyuh", "").strip()
        # Remove the URL from the prompt
        text_input = re.sub(YOUTUBE_PATTERN, '', text_input).strip()
        if not text_input:
            text_input = "Please summarize this video in detail."
        
        logging.info(f"Processing YouTube URL: {youtube_url}")
        async with message.channel.typing():
            active_model = await get_active_model()
            logging.info(f"Using model: {active_model}")
            
            # Create content with YouTube URL
            content = types.Content(
                parts=[
                    types.Part(file_data=types.FileData(file_uri=youtube_url)),
                    types.Part(text=f"You are a chill discord bot with multimodal AI features. Your responses are genz style.\nCurrent query: {text_input}")
                ]
            )
            
            for attempt in range(2):
                try:
                    response = await asyncio.to_thread(
                        genai_client.models.generate_content,
                        model=active_model,
                        contents=content
                    )
                    if response and response.text:
                        # Chunk response if too long
                        text = response.text
                        if len(text) <= 2000:
                            await message.reply(text)
                        else:
                            # Send in chunks
                            chunks = [text[i:i+2000] for i in range(0, len(text), 2000)]
                            for chunk in chunks:
                                await message.reply(chunk)
                        return text
                    break
                except Exception as e:
                    logging.error(f"YouTube processing attempt {attempt + 1} failed: {str(e)}")
                    if "quota" in str(e).lower():
                        last_quota_failure = datetime.datetime.now(datetime.timezone.utc)
                        if active_model == PRIMARY_MODEL:
                            active_model = FALLBACK_MODEL
                            continue
                    if attempt < 1:
                        await asyncio.sleep(2)
                    else:
                        await message.reply(f"❌ Failed to process YouTube video: {str(e)}")
                        return None
    except Exception as e:
        logging.error(f"YouTube URL handling error: {e}")
        await message.reply(f"❌ Error processing YouTube URL: {str(e)}")
        return None

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

        # If the file is an image, check for editing keywords
        if content_type.startswith('image/'):
            from PIL import Image
            import io
            from engine.ai.gemini import genai_client
            
            # Get the user's prompt
            text_input = message.content.strip().replace(f"<@{bot.user.id}>", "").replace("seeyuh", "").strip()
            if not text_input:
                text_input = "Explain the content of the image."
            
            # Define editing keywords
            editing_keywords = ['edit', 'generate', 'make', 'change', 'add', 'replace', 'remove', 'create', 
                              'modify', 'transform', 'alter', 'adjust', 'draw', 'paint', 'apply', 'insert']
            
            # Check if prompt contains editing keywords
            should_edit = any(keyword in text_input.lower() for keyword in editing_keywords)
            
            try:
                pil_image = Image.open(file_path).convert("RGB")
                
                if should_edit:
                    # Use image editing model
                    logging.info("Editing keywords detected, using image editing model")
                    active_image_model = await get_active_image_model()
                    logging.info(f"Using image model: {active_image_model}")
                    
                    async with message.channel.typing():
                        for attempt in range(2):  # Try primary then fallback
                            try:
                                response = await asyncio.to_thread(
                                    genai_client.models.generate_content,
                                    model=active_image_model,
                                    contents=[text_input, pil_image],
                                    config={'response_modalities': ['TEXT', 'IMAGE']}
                                )
                                break  # Success, exit retry loop
                            except Exception as e:
                                logging.error(f"Image model {active_image_model} failed: {e}")
                                if "quota" in str(e).lower():
                                    last_quota_failure = datetime.datetime.now(datetime.timezone.utc)
                                    logging.warning(f"Quota exhausted for {active_image_model}")
                                
                                if attempt == 0 and active_image_model == PRIMARY_IMAGE_MODEL:
                                    active_image_model = FALLBACK_IMAGE_MODEL
                                    logging.info(f"Switching to fallback image model: {active_image_model}")
                                    continue
                                else:
                                    raise e
                        
                        # Collect image + text to send together
                        out_text = None
                        out_img_bytes = None
                        for part in response.candidates[0].content.parts:
                            if hasattr(part, 'text') and part.text and not out_text:
                                out_text = part.text
                            elif hasattr(part, 'inline_data') and part.inline_data is not None and out_img_bytes is None:
                                out_img_bytes = part.inline_data.data
                        if out_img_bytes:
                            with io.BytesIO(out_img_bytes) as output:
                                output.seek(0)
                                file = discord.File(fp=output, filename="edited_image.png")
                                await message.reply(content=(out_text or None), file=file)
                                return "Image edited and sent."
                        if out_text:
                            await message.reply(out_text)
                            return "Image edited."
                else:
                    # Use normal Gemini model for image analysis
                    logging.info("No editing keywords detected, using normal Gemini model")
                    active_model = await get_active_model()
                    logging.info(f"Using model: {active_model}")
                    
                    async with message.channel.typing():
                        model = genai.GenerativeModel(active_model)
                        prompt = f"You are a chill discord bot with multimodal AI features. Your responses are genz style.\nCurrent query: {text_input}"
                        
                        for attempt in range(2):
                            try:
                                response = await asyncio.to_thread(model.generate_content, [pil_image, prompt])
                                if response and response.text:
                                    await message.reply(response.text[:2000])
                                    return response.text
                                break
                            except Exception as e:
                                logging.error(f"Attempt {attempt + 1} failed: {str(e)}")
                                if "quota" in str(e).lower():
                                    last_quota_failure = datetime.datetime.now(datetime.timezone.utc)
                                    logging.warning(f"Quota exhausted for {active_model}, switching to fallback")
                                    if active_model == PRIMARY_MODEL:
                                        active_model = FALLBACK_MODEL
                                        model = genai.GenerativeModel(active_model)
                                        continue
                                if attempt < 1:
                                    await asyncio.sleep(2)
                                else:
                                    await message.reply("Failed to analyze the image.")
                                    return "Failed to analyze the image."
                        
            except Exception as e:
                logging.error(f"Gemini image processing error: {e}")
                await message.reply(f"❌ Error processing image: {str(e)}")
                return f"Error processing image: {str(e)}"

        # Check if file is video
        is_av = attachment.content_type.startswith(('video/', 'audio/'))
        
        # Get media duration if video/audio
        duration = 0
        if is_av:
            duration = await get_media_duration(file_path, attachment.content_type)
            if duration > 300:  # 5 minute limit
                await message.reply("Media file too long. Maximum duration is 5 minutes.")
                return
            processing_msg = await message.reply(f"Processing {duration:.1f} second media file, please wait...")

        # Upload file with video flag and wait ACTIVE
        sample_file = prep_file(file_path, attachment.filename, is_av=is_av)
        try:
            sample_file = await wait_for_file_active(sample_file)
        except Exception as e:
            logging.error(f"File did not become ACTIVE: {e}")
            await message.reply("❌ File upload failed to process. Please try again.")
            return

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
            # Delete processing message if it exists
            if is_av:
                await processing_msg.delete()
                
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
                    lang = text[lang_start:lang_end].strip().lower()
                    code_start = text.find('\n', lang_end) + 1
                    code_end = text.find('```', code_start)
                    code = text[code_start:code_end]
                    
                    # Get remaining text
                    text = text[text.find('```', code_end) + 3:].strip()
                    
                    # Only create file if language exists and code is not empty
                    if lang and code.strip():
                        file_ext = '.' + lang
                        
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
                    else:
                        # If no language specified, keep code block in markdown
                        message_components.append(('text', f'```\n{code}\n```'))
                        text_only_content += f'```\n{code}\n```\n'
                
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
            # Delete processing message if it exists
            if is_av:
                await processing_msg.delete()

            await message.reply("Failed to extract content from the file.")
            return "Failed to extract content from the file."

    except Exception as e:
        # Delete processing message if it exists
        if is_av:
            await processing_msg.delete()
        logging.error(f"An error occurred: {e}")
        await message.reply("An error occurred while processing the file.")
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logging.info("Deleted temporary file.")

async def handle_message_files(bot, message):
    """Collect multiple attachments and URLs from the message/thread, send to Gemini in one call."""
    try:
        # Check for YouTube URLs first
        youtube_urls = YOUTUBE_PATTERN.findall(message.content or "")
        if youtube_urls:
            # Process first YouTube URL found
            yt_url = f"https://www.youtube.com/watch?v={youtube_urls[0]}"
            return await handle_youtube_url(bot, message, yt_url)
        
        # Check referenced message for YouTube URLs
        if message.reference:
            try:
                ref = await message.channel.fetch_message(message.reference.message_id)
                youtube_urls = YOUTUBE_PATTERN.findall(ref.content or "")
                if youtube_urls:
                    yt_url = f"https://www.youtube.com/watch?v={youtube_urls[0]}"
                    return await handle_youtube_url(bot, message, yt_url)
            except Exception:
                pass
        
        # Check for general URLs (non-YouTube, non-image attachments)
        general_urls = GENERAL_URL_PATTERN.findall(message.content or "")
        if message.reference:
            try:
                ref = await message.channel.fetch_message(message.reference.message_id)
                general_urls.extend(GENERAL_URL_PATTERN.findall(ref.content or ""))
            except Exception:
                pass
        
        # Filter out image URLs that will be handled separately
        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg'}
        non_image_urls = [
            url for url in general_urls 
            if not any(url.lower().endswith(ext) for ext in image_extensions)
        ]
        
        # If we have general URLs and no attachments, use URL context tool
        if non_image_urls and not message.attachments:
            return await handle_url_context(bot, message, non_image_urls[:10])  # Limit to 10 URLs
        
        # Collect file sources: attachments + URLs in message and referenced message
        urls = []
        url_pattern = re.compile(r"https?://[^\s]+", re.IGNORECASE)
        urls.extend(url_pattern.findall(message.content or ""))
        if message.reference:
            try:
                ref = await message.channel.fetch_message(message.reference.message_id)
                urls.extend(url_pattern.findall(ref.content or ""))
            except Exception:
                pass

        # Download attachments and URLs
        temp_paths = []
        async with aiohttp.ClientSession() as session:
            # Handle attachments
            for att in (message.attachments or []):
                # Skip overly large files (>20MB videos, >10MB others)
                limit = 20 * 1024 * 1024 if att.content_type and att.content_type.startswith('video/') else 10 * 1024 * 1024
                if att.size and att.size > limit:
                    continue
                _, ext = os.path.splitext(att.filename)
                local_path = f"downloaded_file_{att.id}{ext}"
                async with session.get(att.url) as resp:
                    if resp.status == 200:
                        with open(local_path, 'wb') as f:
                            f.write(await resp.read())
                        temp_paths.append(local_path)

            # Handle URLs
            for u in urls[:10]:
                try:
                    async with session.get(u) as resp:
                        if resp.status != 200:
                            continue
                        # Best-effort filename
                        ct = resp.headers.get('Content-Type', '')
                        ext = '.bin'
                        if 'pdf' in ct:
                            ext = '.pdf'
                        elif 'image/' in ct:
                            subtype = ct.split('/')[-1].split(';')[0]
                            ext = f'.{subtype}' if subtype else '.img'
                        elif 'video/' in ct:
                            subtype = ct.split('/')[-1].split(';')[0]
                            ext = f'.{subtype}' if subtype else '.mp4'
                        elif 'audio/' in ct:
                            subtype = ct.split('/')[-1].split(';')[0]
                            ext = f'.{subtype}' if subtype else '.mp3'
                        elif 'text/' in ct:
                            ext = '.txt'
                        local_path = f"downloaded_link_{abs(hash(u))}{ext}"
                        with open(local_path, 'wb') as f:
                            f.write(await resp.read())
                        temp_paths.append(local_path)
                except Exception:
                    continue

        if not temp_paths:
            return None

        # Compute total size and decide inline vs upload
        total_bytes = 0
        for p in temp_paths:
            try:
                total_bytes += os.path.getsize(p)
            except Exception:
                pass
        use_uploads = total_bytes > 20 * 1024 * 1024

        # Decide intent and build contents
        prompt_text = message.content.strip().replace(f"<@{bot.user.id}>", "").replace("seeyuh", "").strip()
        if not prompt_text:
            prompt_text = "Analyze all provided files together and answer succinctly."

        image_exts = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp'}
        image_paths = [p for p in temp_paths if os.path.splitext(p)[1].lower() in image_exts]
        total_files = max(1, len(temp_paths))
        image_ratio = len(image_paths) / total_files
        # If >= 90% of provided files are images, route to image generation model (it can also return text)
        want_image_output = image_ratio >= 0.5 and len(image_paths) >= 1

        if want_image_output:
            # Use image generation model; pass prompt + all images
            from PIL import Image
            # Use same working invocation style as gemini.py via genai_client
            contents = [prompt_text]
            if use_uploads:
                # Upload images via Files API concurrently
                tasks = [asyncio.to_thread(genai.upload_file, path=p, display_name=os.path.basename(p)) for p in image_paths[:10]]
                uploaded_imgs = []
                for res in await asyncio.gather(*tasks, return_exceptions=True):
                    if isinstance(res, Exception):
                        continue
                    uploaded_imgs.append(res)
                # Ensure all uploaded files are ACTIVE before usage
                active_imgs = await asyncio.gather(
                    *[wait_for_file_active(f) for f in uploaded_imgs], return_exceptions=True
                )
                contents.extend([f for f in active_imgs if not isinstance(f, Exception)])
            else:
                # Inline small images
                for p in image_paths[:10]:
                    try:
                        contents.append(Image.open(p).convert('RGB'))
                    except Exception:
                        continue
            
            # Get active image model with fallback support
            active_image_model = await get_active_image_model()
            logging.info(f"Using image model for multi-file: {active_image_model}")
            
            for attempt in range(2):  # Try primary then fallback
                try:
                    response = genai_client.models.generate_content(
                        model=active_image_model,
                        contents=contents,
                        config={'response_modalities': ['TEXT', 'IMAGE']}
                    )
                    break  # Success, exit retry loop
                except Exception as e:
                    logging.error(f"Multi-file image model {active_image_model} failed: {e}")
                    if "quota" in str(e).lower():
                        last_quota_failure = datetime.datetime.now(datetime.timezone.utc)
                        logging.warning(f"Quota exhausted for {active_image_model}")
                    
                    if attempt == 0 and active_image_model == PRIMARY_IMAGE_MODEL:
                        active_image_model = FALLBACK_IMAGE_MODEL
                        logging.info(f"Switching to fallback image model: {active_image_model}")
                        continue
                    else:
                        raise e
                        
            try:
                preview_text = ""
                if response and getattr(response, 'text', None):
                    preview_text = response.text[:300].replace("\n", " ")
                logging.info(f"Multimodal image-gen response preview: {preview_text}")
            except Exception:
                pass
            out_text = None
            out_img = None
            if response and response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'text') and part.text and not out_text:
                        out_text = part.text
                    elif hasattr(part, 'inline_data') and part.inline_data is not None and out_img is None:
                        out_img = part.inline_data.data
            if out_img:
                with io.BytesIO(out_img) as buf:
                    buf.seek(0)
                    file = discord.File(fp=buf, filename="generated_image.png")
                    await message.reply(content=(out_text or None), file=file)
                    return "Generated image from multiple files."
            if out_text:
                await message.reply(out_text[:2000])
                return "Generated description from multiple files."
            await message.reply("No output from the image model.")
            return None
        else:
            # Upload all files and do multimodal analysis
            uploaded = []
            # Upload concurrently to avoid long blocking
            tasks = [asyncio.to_thread(genai.upload_file, path=p, display_name=os.path.basename(p)) for p in temp_paths]
            for res in await asyncio.gather(*tasks, return_exceptions=True):
                if isinstance(res, Exception):
                    continue
                uploaded.append(res)
            # Wait for ACTIVE state on all files before generation
            if uploaded:
                uploaded = [f for f in await asyncio.gather(
                    *[wait_for_file_active(f) for f in uploaded], return_exceptions=False
                )]
            if not uploaded:
                return None
            model = genai.GenerativeModel(PRIMARY_MODEL)
            response = model.generate_content([*uploaded, prompt_text])
            try:
                preview_text = ""
                if response and getattr(response, 'text', None):
                    preview_text = response.text[:300].replace("\n", " ")
                logging.info(f"Multimodal analysis response preview: {preview_text}")
            except Exception:
                pass
            if response and response.candidates and response.candidates[0].content.parts:
                full_text = []
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'text') and part.text:
                        full_text.append(part.text)
                text_out = "\n".join(t for t in full_text if t).strip()
                if text_out:
                    # Chunk into <=2000 with meaningful boundaries
                    remaining = text_out
                    while len(remaining) > 2000:
                        slice_ = remaining[:2000]
                        cut = max(slice_.rfind('\n\n'), slice_.rfind('\n'), slice_.rfind('. '))
                        if cut < 1000:
                            cut = 2000
                        await message.reply(remaining[:cut].strip())
                        remaining = remaining[cut:].lstrip()
                    if remaining:
                        await message.reply(remaining)
            return "Processed files with Gemini."
    except Exception as e:
        logging.error(f"handle_message_files error: {e}")
        await message.reply("❌ Error processing your files/links.")
        return None
    finally:
        # Clean up temp files
        for p in list(locals().get('temp_paths', [])):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass

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
        try:
            sample_file = await wait_for_file_active(sample_file)
        except Exception as e:
            logging.error(f"File did not become ACTIVE: {e}")
            await interaction.followup.send("❌ File upload failed to process. Please try again.")
            return

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
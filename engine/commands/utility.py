import discord, asyncio, aiohttp, random, httpx, re, json, io, base64, requests, os, logging, tempfile, aiofiles, time
try:
    from ddgs import DDGS
except Exception:
    from duckduckgo_search import DDGS
from google import genai
from engine.ai.gemini import genai_client
from discord import app_commands, File
from pathlib import Path
from typing import Optional
from pytube import Search
from urllib.parse import urlparse, parse_qs, quote
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from contextlib import contextmanager
from filelock import FileLock
from engine.utils import load_env, get_reddit_access_token, unsplash_env, hf_env, pexels_env, qwen_env, infinitetalk_env
from engine.db import get_welcome_settings, set_welcome_settings

# S3/Network Volume Configuration for InfiniteTalk (from environment)
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "https://s3api-eu-cz-1.runpod.io")
S3_REGION = os.getenv("S3_REGION", "eu-cz-1")
S3_BUCKET = os.getenv("S3_BUCKET", "efrqbt1i4d")

# Bot domain configuration (required for download URLs)
BOT_DOMAIN = os.getenv("BOT_DOMAIN", "https://your-bot-domain.com")

# S3 Uploader for InfiniteTalk
class S3Uploader:
    """Handle automatic uploads to RunPod Network Volume."""

    def __init__(self, access_key: str, secret_key: str):
        import boto3
        from botocore.exceptions import ClientError
        self.s3_client = boto3.client(
            's3',
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=S3_REGION
        )

    def upload_file(self, file_bytes: bytes, filename: str, folder: str = "") -> str:
        """
        Upload file to network volume.

        Returns: Path for RunPod API (e.g., /runpod-volume/images/file.jpg)
        """
        # Generate unique filename to avoid conflicts
        import uuid
        unique_id = uuid.uuid4().hex[:8]
        name, ext = os.path.splitext(filename)
        s3_key = f"{folder}{name}_{unique_id}{ext}" if folder else f"{name}_{unique_id}{ext}"

        # Remove leading slash
        s3_key = s3_key.lstrip('/')

        try:
            self.s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=s3_key,
                Body=file_bytes
            )

            # Return path for RunPod API
            return f"/runpod-volume/{s3_key}"

        except Exception as e:
            raise Exception(f"S3 upload failed: {e}")
from engine.ai.gemini_multimodal import handle_interaction
from engine.ai.gemini import code_ai_response, explain_ai_response, ask_ai_response, translate, prompt_ai_response, get_tts_text
from engine.ai.gemini_models import (
    pro10creative,
    pro15creative,
    pro15normal,
    flash15normal,
    flash15creative,
    flash158bn,
    flash158bc,
    flash2
)
# Load environment variables
DISCORD_TOKEN, OWNER, url, key = load_env()

# Configure logging for Unicode
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

TEMP_DIR = Path('/tmp/discord_tts')
os.makedirs(TEMP_DIR, mode=0o777, exist_ok=True)

# DuckAI config
ALLOWED_DUCKAI_MODELS = {
    "gpt-4o-mini",
    "llama-3.3-70b",
    "claude-3-haiku",
    "o3-mini",
    "mistral-small-3",
}
_last_duckai_chat_ts: float | None = None

@contextmanager
def safe_tempfile(guild_id: int):
    """Safely handle temp file creation and cleanup with verification"""
    temp_path = TEMP_DIR / f'temp_{guild_id}.mp3'
    lock_path = temp_path.with_suffix('.lock')
    
    try:
        with FileLock(lock_path):
            # Ensure clean state
            if temp_path.exists():
                temp_path.unlink()
            yield temp_path
    finally:
        # Don't delete immediately - let FFmpeg finish
        pass
            
# Define the say command
@app_commands.command(name='say', description='Make the bot say something.')
async def say_command(interaction: discord.Interaction, content: str):
    await interaction.response.send_message(content)

@app_commands.command(name='code', description='Get AI generated code for your given prompt.')
async def code_command(interaction: discord.Interaction, prompt: str, language: str = None, framework: str = None):
    await interaction.response.defer()
    
    # Try primary model first
    response = await code_ai_response(prompt, language=language, framework=framework, model="pro15normal")
    parts = response.candidates[0].content.parts
    
    # Check if response is empty
    if not any(hasattr(part, 'text') and part.text.strip() for part in parts):
        logging.info("Empty response from pro15normal, trying flash2...")
        response = await code_ai_response(prompt, language=language, framework=framework, model="flash2")
        parts = response.candidates[0].content.parts
        
        if not any(hasattr(part, 'text') and part.text.strip() for part in parts):
            await interaction.followup.send("Sorry, I couldn't generate any code. Please try rephrasing your prompt.")
            return
        
    # Debug logging
    logging.info(f"Full response object: {response}")
    
    # Check if response has executable code (Python)
    has_executable = any(hasattr(part, 'executable_code') and part.executable_code.code.strip() for part in parts)
    logging.info(f"Has executable code: {has_executable}")
    logging.info(f"Parts structure: {[type(getattr(p, 'executable_code', None)) for p in parts]}")
    
    if has_executable:
        with tempfile.TemporaryDirectory() as temp_dir:
            initial_text = next((part.text for part in parts if hasattr(part, 'text') and part.text.strip()), "")
            code_file = None
            output_file = None
            remaining_text = []
            seen_text = set()
            
            for part in parts:
                if hasattr(part, 'executable_code') and part.executable_code.code.strip():
                    code_path = os.path.join(temp_dir, 'code.py')
                    with open(code_path, 'w', encoding='utf-8') as f:
                        f.write(part.executable_code.code)
                    code_file = discord.File(code_path)
                
                elif hasattr(part, 'code_execution_result') and part.code_execution_result.output.strip():
                    output_path = os.path.join(temp_dir, 'output.txt')
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(part.code_execution_result.output)
                    output_file = discord.File(output_path)
                
                elif hasattr(part, 'text') and part.text.strip():
                    text = part.text
                    if '```' not in text and text not in seen_text:
                        seen_text.add(text)
                        if text != initial_text:
                            remaining_text.append(text)
            
            files = []
            if code_file:
                files.append(code_file)
            if output_file:
                files.append(output_file)
                
            await interaction.followup.send(content=initial_text[:2000], files=files)
            
            for text in remaining_text:
                if text.strip():
                    await interaction.followup.send(text[:2000])
    else:
        with tempfile.TemporaryDirectory() as temp_dir:
            initial_text = ""
            remaining_text = []
            code_files = []
            
            for i, part in enumerate(parts):
                if hasattr(part, 'text') and part.text.strip():
                    text = part.text
                    # Extract all code blocks
                    while '```' in text:
                        pre_code = text[:text.find('```')].strip()
                        lang_start = text.find('```') + 3
                        lang_end = text.find('\n', lang_start)
                        file_ext = '.' + text[lang_start:lang_end].strip().lower()
                        code_start = text.find('\n', lang_end) + 1
                        code_end = text.find('```', code_start)
                        code = text[code_start:code_end]
                        
                        # Get remaining text after this code block
                        text = text[text.find('```', code_end) + 3:].strip()
                        
                        if code.strip():
                            code_path = os.path.join(temp_dir, f'code_{len(code_files)}{file_ext}')
                            with open(code_path, 'w', encoding='utf-8') as f:
                                f.write(code)
                            code_files.append(discord.File(code_path))
                        
                        # Handle initial and remaining text
                        if not initial_text:
                            initial_text = pre_code[:2000] if pre_code else "Here's your code:"
                        elif pre_code:
                            remaining_text.append(pre_code)
                    
                    # Add any remaining text after last code block
                    if text and not initial_text:
                        initial_text = text[:2000]
                    elif text:
                        remaining_text.append(text)
            
            await interaction.followup.send(content=initial_text[:2000], files=code_files)
            
            for text in remaining_text:
                if text.strip():
                    await interaction.followup.send(text[:2000])
            
@app_commands.command(name='explain', description='Ask the bot to explain a concept or a topic in details.')
async def explain_command(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    # Get AI-generated response
    response = await explain_ai_response(prompt)
    
    # Split the response into multiple messages if it exceeds 2000 characters
    max_length = 2000
    response_parts = []
    current_part = ""
    
    for sentence in response.split('. '):
        if len(current_part) + len(sentence) + 1 <= max_length:  # +1 for the '.'
            if current_part:
                current_part += ' ' + sentence
            else:
                current_part = sentence
        else:
            response_parts.append(current_part.strip())
            current_part = sentence
    
    if current_part:
        response_parts.append(current_part.strip())
    
    for part in response_parts:
        await interaction.followup.send(part)

@app_commands.command(name='ask', description='Get a short, straightforward and concise single-line response to your question.')
async def ask_command(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    # Get AI-generated response
    response = await ask_ai_response(prompt)

    # Function to intelligently split the response
    def split_response(response, max_length=2000):
        response_parts = []
        current_part = ""
    
        # Split the response into sentences
        sentences = re.split(r'(?<=[.!?]) +', response)
    
        for sentence in sentences:
            if len(current_part) + len(sentence) + 1 <= max_length:  # +1 for the space
                if current_part:
                    current_part += ' ' + sentence
                else:
                    current_part = sentence
            else:
                response_parts.append(current_part.strip())
                current_part = sentence
    
        if current_part:
            response_parts.append(current_part.strip())
    
        return response_parts
    
    response_parts = split_response(response)
    
    for part in response_parts:
        await interaction.followup.send(part)
# Define the emoji command
@app_commands.command(name='emoji', description='Get seeyuh avatar as a custom emoji.')
async def emoji_command(interaction: discord.Interaction):
    await interaction.response.send_message("<:seeyuh:1302628356147122207>")

@app_commands.command(name='avatar', description='Get the avatar of a user.')
async def avatar_command(interaction: discord.Interaction, user: discord.User = None):
    if user is None:
        user = interaction.user
    await interaction.response.send_message(user.display_avatar.url)
    
@app_commands.command(name='banner', description='Get the banner of a user.')
async def banner_command(interaction: discord.Interaction, user: discord.User = None):
    if user is None:
        user = interaction.user
    if user.banner:
        await interaction.response.send_message(user.banner.url)
    else:
        await interaction.response.send_message("This user does not have a banner.")

@app_commands.command(
    name='analyze',
    description='Analyze the content of an image, video, PDF, text/code or text/plain.'
)
async def analyze_command(
    interaction: discord.Interaction,
    file: discord.Attachment,
    prompt: Optional[str] = None
):
    await interaction.response.defer()

    # Check if the file size exceeds 10 MB
    if file.size > 10 * 1024 * 1024:  # 10 MB limit
        await interaction.followup.send(
            "Attachment size exceeds 10 MB limit. Please upload a smaller file."
        )
        return  # Stop further processing

    # Check if the file is an image, PDF, or text file
    if file.content_type and (
        file.content_type.startswith("image/") or
        file.content_type.startswith("video/") or
        file.content_type == "application/pdf" or
        file.content_type.startswith("application/java") or
        file.content_type.startswith("text/") or
        file.content_type.startswith("audio/")
    ):
        if file.content_type == "image/bmp" or file.content_type == "text/csv":
            await interaction.followup.send(
                f"Unsupported file type. {file.content_type} files are not supported. Please try different file types."
            )
            return  # Stop further processing
        else:
            # Use the handle_attachment function
            await handle_interaction(interaction, file, prompt)
    else:
        await interaction.followup.send(
            f"Unsupported file type {file.content_type}. Please upload an image, video, PDF, plain text, or text-based code file."
        )

@app_commands.command(name='poll', description='Usage: /poll "Question" "Option 1, Option 2, Option 3" [duration in minutes]')
async def poll_command(interaction: discord.Interaction, question: str, options: str, duration: int = 60):
    # Check permissions
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("You do not have permission to create a poll.", ephemeral=True)
        return

    # Split options by commas
    options_list = [option.strip() for option in options.split(",")]

    # Validate number of options
    if len(options_list) < 2:
        await interaction.response.send_message("You need to provide at least 2 options for the poll.", ephemeral=True)
        return
    if len(options_list) > 10:
        await interaction.response.send_message("You can only provide up to 10 options for the poll.", ephemeral=True)
        return

    # Create the embed for the poll
    embed = discord.Embed(title=question, color=discord.Color.blurple())
    for i, option in enumerate(options_list):
        embed.add_field(name=f"Option {i + 1}", value=option, inline=False)

    # Send poll message
    await interaction.response.send_message(embed=embed)
    message = await interaction.original_response()

    # Add reactions for options (up to 10)
    for i in range(len(options_list)):
        await message.add_reaction(f"{i + 1}\u20e3")

    # Function to end the poll
    async def end_poll(message):
        await asyncio.sleep(duration * 60)  # Convert minutes to seconds
        message = await interaction.channel.fetch_message(message.id)
        reactions = message.reactions

        # Calculate the total number of votes
        total_votes = sum(reaction.count - 1 for reaction in reactions)  # Subtract 1 to exclude the bot's reaction

        # Update the embed with final results
        for i, option in enumerate(options_list):
            reaction = reactions[i]
            votes = reaction.count - 1  # Subtract 1 to exclude the bot's reaction
            percentage = (votes / total_votes) * 100 if total_votes > 0 else 0
            embed.set_field_at(i, name=f"Option {i + 1}", value=f"{option} - {votes} votes ({percentage:.2f}%)", inline=False)

        embed.set_footer(text="Poll closed")
        await message.edit(embed=embed)

    # Start the background task to end the poll
    interaction.client.loop.create_task(end_poll(message))

# Define the choices for languages
language_choices = [
    app_commands.Choice(name="English", value="English"),
    app_commands.Choice(name="Spanish", value="Spanish"),
    app_commands.Choice(name="French", value="French"),
    app_commands.Choice(name="German", value="German"),
    app_commands.Choice(name="Chinese (Simplified)", value="Chinese (Simplified)"),
    app_commands.Choice(name="Chinese (Traditional)", value="Chinese (Traditional)"),
    app_commands.Choice(name="Japanese", value="Japanese"),
    app_commands.Choice(name="Korean", value="Korean"),
    app_commands.Choice(name="Russian", value="Russian"),
    app_commands.Choice(name="Portuguese", value="Portuguese"),
    app_commands.Choice(name="Italian", value="Italian"),
    app_commands.Choice(name="Arabic", value="Arabic"),
    app_commands.Choice(name="Hindi", value="Hindi"),
    app_commands.Choice(name="Vietnamese", value="Vietnamese"),
    app_commands.Choice(name="Turkish", value="Turkish"),
    app_commands.Choice(name="Polish", value="Polish"),
    app_commands.Choice(name="Dutch", value="Dutch"),
    app_commands.Choice(name="Thai", value="Thai"),
    app_commands.Choice(name="Indonesian", value="Indonesian"),
    app_commands.Choice(name="Persian", value="Persian"),
    app_commands.Choice(name="Swedish", value="Swedish"),
    app_commands.Choice(name="Ukrainian", value="Ukrainian"),
    app_commands.Choice(name="Czech", value="Czech"),
    app_commands.Choice(name="Romanian", value="Romanian"),
    app_commands.Choice(name="Greek", value="Greek")
]

@app_commands.command(name='translate', description='Translate text to a specified language.')
@app_commands.choices(source_language=language_choices, target_language=language_choices)
async def translate_command(interaction: discord.Interaction, text: str, target_language: app_commands.Choice[str], source_language: app_commands.Choice[str] = None):
    await interaction.response.defer()
    prompt = f"Translate '{text}' from {source_language.name} to {target_language.name}" if source_language != None else f"Translate '{text}' to {target_language.name}"
    # Get translated text
    translated_text = await translate(prompt)
    await interaction.followup.send(translated_text)

# Define the choices for AI models
model_choices = [
    app_commands.Choice(name="gemini-pro (default)", value="pro10creative"),
    app_commands.Choice(name="gemini-1.5-pro-exp", value="pro15creative"),
    app_commands.Choice(name="gemini-1.5-pro", value="pro15normal"),
    app_commands.Choice(name="gemini-1.5-flash", value="flash15normal"),
    app_commands.Choice(name="gemini-1.5-flash-exp", value="flash15creative"),
    app_commands.Choice(name="gemini-1.5-flash8b", value="flash158bn"),
    app_commands.Choice(name="gemini-1.5-flash8b-exp", value="flash158bc"),
    app_commands.Choice(name="gemini-2.0-flash-exp (advanced)", value="flash2")
]

# Map model values to actual model objects
model_map = {
    "pro10creative": pro10creative,
    "pro15creative": pro15creative,
    "pro15normal": pro15normal,
    "flash15normal": flash15normal,
    "flash15creative": flash15creative,
    "flash158bn": flash158bn,
    "flash158bc": flash158bc,
    "flash2": flash2
}

@app_commands.command(name='chat', description='Chat with an AI model')
@app_commands.describe(
    prompt="Your message to the AI",
    model="Select AI model to chat with"
)
@app_commands.choices(
    model=[
        app_commands.Choice(name="Claude-3 Haiku", value="claude-3-haiku"),
        app_commands.Choice(name="GPT-4o Mini", value="gpt-4o-mini"),
        app_commands.Choice(name="Llama 3.1", value="llama-3.1-70b"), 
        app_commands.Choice(name="Mixtral 8x7B", value="mixtral-8x7b"),
        app_commands.Choice(name="Gemini-1.5-Flash", value="flash15normal"),
        app_commands.Choice(name="Gemini-2.0-Flash", value="flash2")
    ]
)
async def chat_command(
    interaction: discord.Interaction,
    prompt: str,
    model: app_commands.Choice[str]
):
    await interaction.response.defer()
    
    try:
        if model.value in ["flash15normal", "flash2"]:
            response = await prompt_ai_response(prompt, model_map[model.value])
        else:
            results = await search_ddg(
                prompt,
                num_results=1,
                search_type='chat',
                model=model.value
            )
            if results:
                _, response, _, _ = results[0]
            else:
                await interaction.followup.send("Failed to get AI response.")
                return

        # Split response into chunks of 4000 chars (leaving room for formatting)
        response_chunks = [response[i:i+4000] for i in range(0, len(response), 4000)]
        
        for i, chunk in enumerate(response_chunks):
            embed = discord.Embed(
                title="AI Chat Response" if i == 0 else f"AI Chat Response (Part {i+1})",
                description=chunk,
                color=discord.Color.blue()
            )
            
            if i == 0:  # Only add author and footer to first embed
                embed.set_author(
                    name=f"Chat with {model.name}",
                    icon_url=interaction.client.user.display_avatar.url
                )
                embed.set_footer(
                    text=f"Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}",
                    icon_url=interaction.client.user.display_avatar.url
                )
            
            await interaction.followup.send(embed=embed)
        
    except Exception as e:
        logging.error(f"Chat error: {e}")
        await interaction.followup.send("An error occurred during chat.")

@app_commands.command(name='prompt', description='Prompt for a specific AI model to generate a response.')
@app_commands.choices(model=model_choices)
async def prompt_command(interaction: discord.Interaction, prompt: str, model: app_commands.Choice[str] = None):
    await interaction.response.defer()
    selected_model = model_map[model.value] if model else pro10creative

    # Retry logic with timeout
    retries = 3
    for attempt in range(retries):
        try:
            response = await asyncio.wait_for(prompt_ai_response(prompt, selected_model), timeout=30)  # Await the coroutine with a timeout
            break
        except asyncio.TimeoutError:
            if attempt < retries - 1:
                await interaction.followup.send(f"Attempt {attempt + 1} failed. Retrying...")
            else:
                await interaction.followup.send("The request timed out. Please try again later.")
                return

    # Function to intelligently split the response
    def split_response(response, max_length=2000):
        response_parts = []
        current_part = ""
    
        # Split the response into sentences
        sentences = re.split(r'(?<=[.!?]) +', response)
    
        for sentence in sentences:
            if len(current_part) + len(sentence) + 1 <= max_length:  # +1 for the space
                if current_part:
                    current_part += ' ' + sentence
                else:
                    current_part = sentence
            else:
                response_parts.append(current_part.strip())
                current_part = sentence
    
        if current_part:
            response_parts.append(current_part.strip())
    
        return response_parts
    

    response_parts = split_response(response)
    
    for part in response_parts:
        await interaction.followup.send(part)

@app_commands.command(name='weather', description='Get the weather information for a specific location.')
async def weather_command(interaction: discord.Interaction, location: str):
    await interaction.response.defer()

    # Fetch weather information from wttr.in
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://wttr.in/{location}?format=j1") as resp:
            if resp.status == 200:
                data = await resp.json()
                current_condition = data['current_condition'][0]
                nearest_area = data['nearest_area'][0]

                # Extract weather information
                weather_description = current_condition['weatherDesc'][0]['value']
                temperature_c = current_condition['temp_C']
                feels_like_c = current_condition['FeelsLikeC']
                humidity = current_condition['humidity']
                wind_speed_kmph = current_condition['windspeedKmph']
                city = nearest_area['areaName'][0]['value']
                country = nearest_area['country'][0]['value']
                
                # Map condition to icons based on description (simple mapping)
                weather_icons = {
                    "Sunny": "☀️", "Clear": "🌕", "Cloudy": "☁️",
                    "Partly Cloudy": "⛅", "Overcast": "🌥️", "Rain": "🌧️",
                    "Thunderstorm": "⛈️", "Snow": "❄️", "Fog": "🌫️"
                }
                weather_icon = weather_icons.get(weather_description, "🌍")

                # Simulate terminal style with green text and icon
                embed = discord.Embed(
                    title=f"🌎 Weather in **{city}, {country}**",
                    description=f"{weather_icon} **{weather_description}**",
                    color=0x00FF00
                )
                
                # Set fields with emojis to replicate a weather terminal display
                embed.add_field(name="🌡️ Temperature", value=f"`{temperature_c}°C`", inline=True)
                embed.add_field(name="🌡️ Feels Like", value=f"`{feels_like_c}°C`", inline=True)
                embed.add_field(name="💧 Humidity", value=f"`{humidity}%`", inline=True)
                embed.add_field(name="🌬️ Wind Speed", value=f"`{wind_speed_kmph} km/h`", inline=True)

                # Moon phase and date/time fields for more realism
                embed.add_field(name="🌙 Moon Phase", value="`Waxing Crescent`", inline=True)  # example phase
                embed.set_thumbnail(url=f"https://wttr.in/static/weather_icons/113.png")  # Placeholder icon

                # Dark style footer for terminal look
                embed.set_footer(text=f"{interaction.client.user.name}", icon_url=interaction.client.user.display_avatar.url)

                # Send embed
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(f"Could not fetch weather information for {location}. Please try again later.")
                
# Define the choices for sort options
sort_choices = [
    app_commands.Choice(name="Hot", value="hot"),
    app_commands.Choice(name="Top", value="top"),
    app_commands.Choice(name="New", value="new"),
    app_commands.Choice(name="Rising", value="rising")
]

@app_commands.command(name="reddit", description="Get a random post from a subreddit of your choice.")
@app_commands.choices(sort=sort_choices)
async def reddit_command(interaction: discord.Interaction, subreddit: str, sort: app_commands.Choice[str] = None, nsfw: bool = False):
    await interaction.response.defer()

    # Enforce NSFW block if the channel is not NSFW
    if not interaction.channel.is_nsfw() and nsfw:
        nsfw = False
        await interaction.followup.send("🔒 NSFW content is blocked in this channel as it does not allow NSFW content.")
        
    if sort is None:
        sort = app_commands.Choice(name="Hot", value="hot")

    access_token = await get_reddit_access_token()
    url = f"https://oauth.reddit.com/r/{subreddit}/{sort.value}.json?limit=50"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "User-Agent": "seeyuh/0.1.0 (by u/drgamerarko)"
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

        # Extract posts from the response
        posts = data["data"]["children"]
        # Filter out NSFW posts if NSFW is set to False
        if not nsfw:
            posts = [post for post in posts if not post["data"]["over_18"]]

        if not posts:
            await interaction.followup.send("No posts found or all posts are NSFW. Try a different subreddit or allow NSFW.")
            return

        # Choose a random post from the filtered list
        random_post = random.choice(posts)["data"]

        # Create and send the embed with the post
        embed = discord.Embed(title=random_post["title"], color=discord.Color.random())
        if "url" in random_post and random_post["url"].endswith((".jpg", ".jpeg", ".png", ".gif")):
            embed.set_image(url=random_post["url"])
        else:
            embed.description = random_post.get("selftext", "No description available.")
        embed.set_footer(text=f"👍 {random_post['score']} | 💬 {random_post['num_comments']} comments", icon_url=interaction.client.user.avatar.url)

        await interaction.followup.send(embed=embed)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            await interaction.followup.send(f"The subreddit '{subreddit}' does not exist. Please try a different subreddit.")
        else:
            await interaction.followup.send("There was an error fetching posts from Reddit. Please try again later.")
        logging.error(f"HTTP error: {e}")
    except Exception as e:
        await interaction.followup.send("An unexpected error occurred. Please try again later.")
        logging.error(f"Unexpected error: {e}")

async def search_ddg(query: str, num_results: int = 3, search_type: str = 'text', model: str = None) -> list:
    try:
        with DDGS() as ddgs:
            results = []
            if search_type == 'video':
                video_results = list(ddgs.videos(
                    query,
                    region='wt-wt',
                    safesearch='moderate',
                    resolution='high',
                    max_results=num_results
                ))
                
                for r in video_results:
                    title = r.get('title', 'No title')
                    description = r.get('description', 'No description')
                    link = r.get('content', '#') 
                    duration = r.get('duration', 'Unknown duration')
                    publisher = r.get('publisher', 'Unknown source')
                    published = r.get('published', 'Unknown date')
                    views = r.get('statistics', {}).get('viewCount', '0')
                    thumbnail = r.get('images', {}).get('large', 'No image')
                    
                    source = f"Source: {publisher} | Duration: {duration} | Views: {views:,} | Date: {published}"
                    results.append((title, description, source, thumbnail))
                    
            elif search_type == 'text':
                try:
                    search_results = list(ddgs.text(
                        query, region='wt-wt',
                        safesearch='moderate', 
                        max_results=num_results
                    ))
                except Exception as e:
                    logging.warning(f"DDGS text failed: {e}")
                    search_results = []
                
                for r in search_results:
                    title = r.get('title', 'No title')
                    description = r.get('body', 'No description')
                    link = r.get('href', '#')
                    domain = urlparse(link).netloc.replace("www.", "") if link != '#' else 'Unknown'
                    source = f"Source: [{domain}]({link})"
                    results.append((title, description, source, "No image"))
                    
            elif search_type == 'image':
                image_results = list(ddgs.images(
                    query, region='wt-wt',
                    safesearch='moderate',
                    max_results=num_results
                ))
                
                for r in image_results:
                    if not r.get('image'):
                        continue
                    title = r.get('title', 'No title')
                    image_url = r.get('image')
                    source_url = r.get('url', '#')
                    domain = urlparse(source_url).netloc.replace("www.", "")
                    source = f"Source: [{domain}]({source_url})"
                    dimensions = f"{r.get('width','?')}x{r.get('height','?')}"
                    description = f"Size: {dimensions}"
                    results.append((title, description, source, image_url))
                    
            elif search_type == 'news':
                news_results = list(ddgs.news(
                    query,
                    region='wt-wt',
                    safesearch='moderate',
                    timelimit='m',  # Last month
                    max_results=num_results
                ))
                
                for r in news_results:
                    title = r.get('title', 'No title')
                    description = r.get('body', 'No description')
                    link = r.get('url', '#')
                    date = r.get('date', 'No date')
                    image = r.get('image', 'No image')
                    domain = urlparse(link).netloc.replace("www.", "")
                    source = f"Source: [{domain}]({link}) | Date: {date}"
                    results.append((title, description, source, image))
                    
            elif search_type == 'chat':
                # DuckAI chat with model validation and rate limiting per docs:
                # Ratelimit ~1 request per 15 seconds. Models: gpt-4o-mini, llama-3.3-70b, claude-3-haiku, o3-mini, mistral-small-3
                try:
                    from duckai import DuckAI
                    try:
                        from duckai.exceptions import (
                            RatelimitException,
                            TimeoutException,
                            ConversationLimitException,
                            DuckAIException,
                        )
                    except Exception:
                        # Older versions may not expose exceptions; treat all as generic
                        RatelimitException = TimeoutException = ConversationLimitException = DuckAIException = Exception
                    global _last_duckai_chat_ts
                    now_ts = time.time()
                    if _last_duckai_chat_ts and (now_ts - _last_duckai_chat_ts) < 15:
                        raise Exception("DuckAI ratelimit: wait 15s between requests")
                    dm = (model or "gpt-4o-mini").strip()
                    if dm not in ALLOWED_DUCKAI_MODELS:
                        dm = "gpt-4o-mini"
                    proxy = os.getenv("DUCKAI_PROXY") or None
                    try:
                        chat_response = DuckAI(proxy=proxy, timeout=30).chat(query, model=dm, timeout=30)
                    except (RatelimitException, ConversationLimitException) as _e:
                        _last_duckai_chat_ts = now_ts
                        raise _e
                    except (TimeoutException, DuckAIException) as _e:
                        raise _e
                    _last_duckai_chat_ts = now_ts
                    if chat_response:
                        results.append((
                            "AI Response",
                            chat_response,
                            "Source: DuckAI",
                            "No image"
                        ))
                except Exception as _e:
                    logging.warning(f"DuckAI chat failed: {_e}")
                    # Fallback to Gemini text models
                    try:
                        g_resp = genai_client.models.generate_content(
                            model="models/gemini-1.5-flash",
                            contents=query
                        )
                        g_text = getattr(g_resp, 'text', None)
                        if g_text:
                            results.append((
                                "AI Response",
                                g_text,
                                "Source: Seeyuh News AI powered by DuckDuckGo",
                                "No image"
                            ))
                        else:
                            raise Exception("Empty Gemini 1.5 Flash response")
                    except Exception as _g1:
                        logging.warning(f"Gemini 1.5 Flash fallback failed: {_g1}")
                        try:
                            g_resp2 = genai_client.models.generate_content(
                                model="models/gemini-1.5-flash-8b",
                                contents=query
                            )
                            g_text2 = getattr(g_resp2, 'text', None)
                            if g_text2:
                                results.append((
                                    "AI Response",
                                    g_text2,
                                    "Source: Seeyuh News AI powered by DuckDuckGo",
                                    "No image"
                                ))
                        except Exception as _g2:
                            logging.warning(f"Gemini 1.5 Flash 8B fallback failed: {_g2}")
                    
            return results
            
    except Exception as e:
        logging.error(f"DuckDuckGo search error: {e}")
        return []
            
# Define the choices for search engines
search_engine_choices = [
    app_commands.Choice(name="Bing", value="bing"),
    app_commands.Choice(name="Yahoo", value="yahoo"),
    app_commands.Choice(name="DuckDuckGo", value="duckduckgo"),
    app_commands.Choice(name="Google (DEPRECATED)", value="google"),
    app_commands.Choice(name="Ask.com (DEPRECATED)", value="ask")
]

# Define the icons for each search engine
search_engine_icons = {
    "google": "https://media.discordapp.net/attachments/533926025747234838/1303799821592694916/google.gif",
    "bing": "https://media.discordapp.net/attachments/533926025747234838/1303799821043503185/bing.gif",
    "duckduckgo": "https://duckduckgo.com/assets/icons/meta/DDG-icon_256x256.png",
    "yahoo": "https://media.discordapp.net/attachments/533926025747234838/1303799820292460554/yahoo.gif",
    "ask": "https://media.discordapp.net/attachments/533926025747234838/1303799822431817800/Ask.com.png"
}
# Map of search engine icons (high resolution, official logos)
SEARCH_ENGINE_AUTHOR_ICONS = {
    "google": "https://media.discordapp.net/attachments/533926025747234838/1316108610111279195/google.png",  # Google 'G' logo
    "bing": "https://media.discordapp.net/attachments/533926025747234838/1316108609305968791/bing.png",    # Bing 'b' logo
    "duckduckgo": "https://media.discordapp.net/attachments/533926025747234838/1316108610329120838/ddg.png", # DuckDuckGo duck logo
    "yahoo": "https://media.discordapp.net/attachments/533926025747234838/1316108609586724864/yahoo.png",   # Yahoo '!' logo
    "ask": "https://media.discordapp.net/attachments/533926025747234838/1316108609863553085/ask.png"      # Ask.com logo
}

@app_commands.command(name="news", description="Get the latest news articles with AI summary")
@app_commands.describe(
    query="Topic to search news for",
    summarize="Select AI model for summary"
)
@app_commands.choices(
    summarize=[
        app_commands.Choice(name="Claude-3 Haiku", value="claude-3-haiku"),
        app_commands.Choice(name="GPT-4o Mini", value="gpt-4o-mini"),
        app_commands.Choice(name="Llama 3.1", value="llama-3.1-70b"),
        app_commands.Choice(name="Mixtral 8x7B", value="mixtral-8x7b")
    ]
)
async def news_command(
    interaction: discord.Interaction, 
    query: str,
    summarize: app_commands.Choice[str] = None
):
    await interaction.response.defer()
    
    try:
        results = await search_ddg(query, num_results=5, search_type='news')
        
        if not results:
            await interaction.followup.send("No news found for that topic.")
            return
            
        # Create first embed with title and author
        main_embed = discord.Embed(
            title=f"Latest news for '{query}'",
            color=discord.Color.blue()
        )
        
        encoded_query = quote(query)
        main_embed.set_author(
            name="DuckDuckGo News",
            icon_url=SEARCH_ENGINE_AUTHOR_ICONS["duckduckgo"],
            url=f"https://duckduckgo.com/?q={encoded_query}&ia=news"
        )

        all_articles = []
        current_length = 0
        current_embed = main_embed
        embeds = [main_embed]
        
        # Process articles
        for title, description, source, image in results:
            field_content = f"{description}\n*{source}*"
            field_length = len(title) + len(field_content)
            
            # If adding this field would exceed limit, create new embed
            if current_length + field_length > 4000:
                current_embed = discord.Embed(
                    title=f"Latest news for '{query}' (continued)",
                    color=discord.Color.blue()
                )
                embeds.append(current_embed)
                current_length = 0
            
            current_embed.add_field(name=title, value=field_content, inline=False)
            current_length += field_length
            all_articles.append(f"Title: {title}\n{description}")
            
            # Set image in first embed that has space
            if image != "No image" and is_valid_url(image) and not any(e.image for e in embeds):
                current_embed.set_image(url=image)
                
        # Get AI summary if model selected
        if summarize:
            summary_query = f"Summarize these news articles:\n\n" + "\n\n".join(all_articles)
            summary_results = await search_ddg(
                summary_query,
                num_results=1,
                search_type='chat',
                model=summarize.value
            )
            
            if summary_results:
                _, summary, _, _ = summary_results[0]
                # Split summary if too long
                summary_chunks = [summary[i:i+4000] for i in range(0, len(summary), 4000)]
                
                for i, chunk in enumerate(summary_chunks):
                    if i == 0:
                        main_embed.description = f"**AI Summary ({summarize.name}):**\n{chunk}"
                    else:
                        summary_embed = discord.Embed(
                            title=f"AI Summary (Part {i+1})",
                            description=chunk,
                            color=discord.Color.blue()
                        )
                        embeds.append(summary_embed)

        # Add footer to last embed
        embeds[-1].set_footer(
            text=interaction.client.user.name,
            icon_url=interaction.client.user.display_avatar.url
        )
        
        # Send all embeds
        for embed in embeds:
            await interaction.followup.send(embed=embed)
        
    except Exception as e:
        logging.error(f"News search error: {e}")
        await interaction.followup.send("An error occurred while fetching news.")

@app_commands.command(name="aisearch", description="Search using AI and get summarized results")
@app_commands.describe(
    query="Your search query",
    model="AI model to use for summarization"
)
@app_commands.choices(
    model=[
        app_commands.Choice(name="Claude-3 Haiku", value="claude-3-haiku"),
        app_commands.Choice(name="GPT-4o Mini", value="gpt-4o-mini"), 
        app_commands.Choice(name="Llama 3.1", value="llama-3.1-70b"),
        app_commands.Choice(name="Mixtral 8x7B", value="mixtral-8x7b")
    ]
)
async def aisearch_command(
    interaction: discord.Interaction,
    query: str,
    model: app_commands.Choice[str]
):
    await interaction.response.defer()
    
    try:
        # Get search results
        search_results = await search_ddg(query, num_results=5, search_type='text')
        
        if not search_results:
            await interaction.followup.send("No results found.")
            return
            
        # Format sources and text
        sources = []
        search_text = []
        for title, desc, source, _ in search_results:
            url = source.split('](')[1].rstrip(')')
            sources.append(f"[{title}]({url})")
            search_text.append(f"Title: {title}\n{desc}")
            
        # Get AI summary
        summary_query = f"Query: {query}\nAnswer the query using these search results:\n\n" + "\n\n".join(search_text)
        ai_results = await search_ddg(
            summary_query,
            num_results=1,
            search_type='chat',
            model=model.value
        )
        
        if not ai_results:
            await interaction.followup.send("Failed to get AI summary.")
            return
            
        _, summary, _, _ = ai_results[0]
        summary_chunks = [summary[i:i+4000] for i in range(0, len(summary), 4000)]
        
        embeds = []
        
        # Create main embed
        main_embed = discord.Embed(
            title=f"AI Search: {query}",
            description=summary_chunks[0],
            color=discord.Color.blue()
        )
        
        main_embed.set_author(
            name=f"DuckDuckGo + {model.name}",
            icon_url=SEARCH_ENGINE_AUTHOR_ICONS["duckduckgo"]
        )
        
        main_embed.add_field(
            name="Sources",
            value="\n".join(sources),
            inline=False
        )
        
        embeds.append(main_embed)
        
        # Create additional embeds for long summaries
        for i, chunk in enumerate(summary_chunks[1:], 1):
            embed = discord.Embed(
                title=f"AI Search: {query} (Part {i+1})",
                description=chunk,
                color=discord.Color.blue()
            )
            embeds.append(embed)
            
        # Add footer to last embed
        embeds[-1].set_footer(
            text=interaction.client.user.name,
            icon_url=interaction.client.user.display_avatar.url
        )
        
        # Send all embeds
        for embed in embeds:
            await interaction.followup.send(embed=embed)
        
    except Exception as e:
        logging.error(f"News search error: {e}")
        await interaction.followup.send("An error occurred while fetching news.")

@app_commands.command(name="search", description="Search for a query on the web.")
@app_commands.choices(engine=search_engine_choices)
async def search_command(
    interaction: discord.Interaction, 
    query: str, 
    engine: app_commands.Choice[str] = None, 
    safesearch: bool = True, 
    image_search: bool = False,
    video_search: bool = False
):
    await interaction.response.defer()

    # Force SafeSearch if not NSFW channel
    if not interaction.channel.is_nsfw() and not safesearch:
        safesearch = True
        await interaction.followup.send("🔒 SafeSearch is enabled because this channel doesn't allow NSFW content.")

    if engine is None:
        engine = app_commands.Choice(name="DuckDuckGo", value="duckduckgo")

    # Handle video search
    if video_search:
        if engine.value != "duckduckgo":
            await interaction.followup.send(f"❌ Video search is not supported for {engine.name}. Try using DuckDuckGo instead.")
            return
            
        try:
            results = await search_ddg(query, num_results=5, search_type='video')
            
            if not results:
                await interaction.followup.send("No videos found.")
                return
                
            embed = discord.Embed(
                title=f"Video results for '{query}'",
                color=discord.Color.blue()
            )
            
            embed.set_author(
                name="DuckDuckGo Video Search",
                icon_url=SEARCH_ENGINE_AUTHOR_ICONS["duckduckgo"]
            )
            
            for title, description, source, thumbnail in results:
                embed.add_field(
                    name=title,
                    value=f"{description[:200]}...\n*{source}*",
                    inline=False
                )
                if thumbnail != "No image":
                    embed.set_thumbnail(url=thumbnail)
                    
            embed.set_footer(
                text=interaction.client.user.name,
                icon_url=interaction.client.user.display_avatar.url
            )
            
            await interaction.followup.send(embed=embed)
            return

        except Exception as e:
            logging.error(f"Video search error: {e}")
            await interaction.followup.send("❌ Error processing video search.")
            return

    # Map engine names to URLs with image search options
    search_urls = {
        "google": {
            "web": f"https://www.google.com/search?q={query.replace(' ', '+')}" + ("&safe=active" if safesearch else ""),
            "image": f"https://www.google.com/search?q={query.replace(' ', '+')}&tbm=isch" + ("&safe=active" if safesearch else "")
        },
        "bing": {
            "web": f"https://www.bing.com/search?q={query.replace(' ', '+')}" + ("&adlt=strict" if safesearch else ""),
            "image": f"https://www.bing.com/images/search?q={query.replace(' ', '+')}" + ("&adlt=strict" if safesearch else "")
        },
        "duckduckgo": {
            "web": f"https://duckduckgo.com/?q={query.replace(' ', '+')}" + ("&kp=1" if safesearch else ""),
            "image": f"https://duckduckgo.com/?q={query.replace(' ', '+')}&ia=images&iax=images" + ("&kp=1" if safesearch else "")
        },
        "yahoo": {
            "web": f"https://search.yahoo.com/search?p={query.replace(' ', '+')}",
            "image": f"https://images.search.yahoo.com/search/images?p={query.replace(' ', '+')}"
        },
        "ask": {
            "web": f"https://www.ask.com/web?q={query.replace(' ', '+')}",
            "image": f"https://www.ask.com/images?q={query.replace(' ', '+')}"
        }
    }
    search_url = search_urls.get(engine.value)["image" if image_search else "web"]
    
    # Custom headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(search_url, headers=headers) as resp:
            if resp.status != 200:
                await interaction.followup.send("❌ Could not fetch search results. Please try again later.")
                return

            html = await resp.text()
            soup = BeautifulSoup(html, 'html.parser')

            if image_search:
                # Image search mode
                results = []
                try:
                    if engine.value == "google":
                        # Find image results container
                        results_container = soup.find('div', class_='islrc')
                        if results_container:
                            for img_div in results_container.find_all('div', class_='isv-r'):
                                try:
                                    # Get actual image element
                                    image = img_div.find('img', class_='rg_i')
                                    if not image:
                                        continue
                    
                                    # Try multiple sources for image URL
                                    image_url = None
                                    for attr in ['src', 'data-src', 'data-iurl']:
                                        url = image.get(attr)
                                        if url and not url.startswith('data:') and len(url) > 200:
                                            image_url = url
                                            break
                    
                                    # Try metadata from parent container
                                    if not image_url:
                                        metadata = img_div.get('data-tbnid')
                                        if metadata:
                                            logging.info(f"Found metadata: {metadata}")
                                            parent_a = img_div.find_parent('a')
                                            if parent_a and parent_a.get('href'):
                                                image_url = parent_a['href']
                    
                                    if image_url:
                                        logging.info(f"Found Google image: {image_url}")
                                        embed = discord.Embed(title=f"Image search: {query}", color=discord.Color.blue())
                                        embed.set_image(url=image_url)
                                        
                                        # Try to get source URL
                                        source_div = img_div.find('div', class_='VFACy')
                                        if source_div and source_div.find('a'):
                                            source_url = source_div.find('a')['href']
                                            embed.add_field(name="Source", value=source_url, inline=False)
                                        
                                        embed.set_author(
                                            name=f"{engine.name} Image Search",
                                            icon_url=SEARCH_ENGINE_AUTHOR_ICONS[engine.value],
                                            url=search_url
                                        )
                                        await interaction.followup.send(embed=embed)
                                        return
                    
                                except Exception as e:
                                    logging.error(f"Error parsing Google image: {str(e)}")
                                    continue
                                
                    elif engine.value == "yahoo":
                        for img in soup.find_all(['li', 'div'], class_=['ld', 'img']):
                            try:
                                image = img.find('img')
                                image_url = image.get('data-src') or image.get('src')
                                if image_url and not image_url.startswith('data:'):
                                    embed = discord.Embed(title=f"Image search: {query}", color=discord.Color.blue())
                                    embed.set_image(url=image_url)
                                    embed.set_author(
                                        name=f"{engine.name} Image Search",
                                        icon_url=SEARCH_ENGINE_AUTHOR_ICONS[engine.value],
                                        url=search_url
                                    )
                                    await interaction.followup.send(embed=embed)
                                    return
                            except Exception as e:
                                logging.error(f"Error parsing Yahoo image: {e}")
                                continue
                                
                    elif engine.value == "bing":
                        for img in soup.find_all('div', class_='imgpt'):
                            try:
                                image = img.find('img')
                                if image and 'src' in image.attrs:
                                    image_url = image['src']
                                    embed = discord.Embed(title=f"Image search: {query}", color=discord.Color.blue())
                                    embed.set_image(url=image_url)
                                    embed.set_author(
                                        name=f"{engine.name} Image Search",
                                        icon_url=SEARCH_ENGINE_AUTHOR_ICONS[engine.value],
                                        url=search_url
                                    )
                                    await interaction.followup.send(embed=embed)
                                    return
                            except Exception as e:
                                logging.error(f"Error parsing Bing image: {e}")
                                continue
                
                    elif engine.value == "duckduckgo":
                        results = await search_ddg(query, num_results=5, search_type='image')
                        for result in results:
                            try:
                                title, description, source, image = result
                                if image != "No image":
                                    embed = discord.Embed(title=f"Image search: {query}", color=discord.Color.blue())
                                    embed.set_image(url=image)
                                    embed.add_field(name=title, value=f"{description}\n{source}", inline=False)
                                    embed.set_author(
                                        name=f"{engine.name} Image Search",
                                        icon_url=SEARCH_ENGINE_AUTHOR_ICONS[engine.value],
                                        url=search_url
                                    )
                                    await interaction.followup.send(embed=embed)
                                    return
                            except Exception as e:
                                logging.error(f"Error parsing DuckDuckGo image: {e}")
                                continue
                                
                    else:
                        await interaction.followup.send("❌ Image search is not supported for this search engine.")
                        return
                                 
                    await interaction.followup.send("❌ No image results found.")
                    return
                    
                except Exception as e:
                    logging.error(f"Image search error: {e}")
                    await interaction.followup.send("❌ Error processing image search.")
                    return

            else:
                # Normal web search
                results = await extract_search_results(soup, engine.value, query)
    

            # Build and send the embed
            embed = discord.Embed(title=f"Search results for '{query}'", color=discord.Color.blue())

            # Add author with search engine icon
            search_urls_base = {
                "google": "https://www.google.com",
                "bing": "https://www.bing.com",
                "duckduckgo": "https://duckduckgo.com",
                "yahoo": "https://search.yahoo.com",
                "ask": "https://www.ask.com"
            }
            embed.set_author(
                name=f"{engine.name} Search", 
                icon_url=SEARCH_ENGINE_AUTHOR_ICONS[engine.value],
                url=search_urls_base[engine.value]
            )
            embed.set_thumbnail(url=search_engine_icons[engine.value])
            if results:
                for title, description, source, image in results[:5]:  # Limit to top 5 results
                    embed.add_field(name=title or "No title", value=f"{description or 'No description'}\n*{source}*", inline=False)
                    if image != "No image" and is_valid_url(image):
                        embed.set_image(url=image)
            else:
                embed.description = "No results found."

            embed.set_footer(text=interaction.client.user.name, icon_url=interaction.client.user.display_avatar.url)
            await interaction.followup.send(embed=embed)
    
async def extract_search_results(soup, engine, query):
    results = []

    def get_meta_image(soup):
        """Extract image from meta tags with proper error handling"""
        try:
            meta_img = (
                soup.find('meta', attrs={'property': 'og:image'}) or 
                soup.find('meta', attrs={'property': 'twitter:image'}) or
                soup.find('meta', attrs={'name': 'thumbnail'})
            )
            return meta_img['content'] if meta_img and 'content' in meta_img.attrs else "No image"
        except Exception:
            return "No image"

    if engine == "google":
        for g in soup.find_all(['div', 'g'], class_=['tF2Cxc', 'g']):
            try:
                title = g.find('h3').text if g.find('h3') else "No title"
                link = g.find('a')['href'] if g.find('a') else "No link"
                description = g.find('div', class_='VwiC3b').text if g.find('div', class_='VwiC3b') else "No description"
                
                # Enhanced image extraction for Google
                image = (
                    g.find('img', class_=['rISBZc', 'XNo5Ab'])['src'] if g.find('img', class_=['rISBZc', 'XNo5Ab']) else
                    g.find('g-img')['src'] if g.find('g-img') and 'src' in g.find('g-img').attrs else
                    g.find('img')['src'] if g.find('img') and 'src' in g.find('img').attrs else
                    "No image"
                )
                
                domain = urlparse(link).netloc.replace("www.", "")
                source = f"Source: [{domain}]({link})"
                results.append((title, description, source, image))
            except Exception as e:
                logging.error(f"Error parsing Google result: {e}")
                continue

    elif engine == "bing":
        for b in soup.find_all('li', class_='b_algo'):
            try:
                title = b.find('h2').text if b.find('h2') else "No title"
                link = b.find('a')['href'] if b.find('a') else "No link"
                description = b.find('p').text if b.find('p') else "No description"
                
                # Enhanced image extraction for Bing
                image = (
                    b.find('img', class_=['cico', 'rms_img'])['src'] if b.find('img', class_=['cico', 'rms_img']) else
                    b.find('img')['src'] if b.find('img') and 'src' in b.find('img').attrs else
                    "No image"
                )
                
                domain = urlparse(link).netloc.replace("www.", "")
                source = f"Source: [{domain}]({link})"
                results.append((title, description, source, image))
            except Exception as e:
                logging.error(f"Error parsing Bing result: {e}")
                continue
            
    elif engine == "yahoo":
        for y in soup.find_all('div', class_='algo'):  # Changed from algo-sr
            try:
                # Get title and clean it
                title = y.find('h3').get_text(strip=True) if y.find('h3') else "No title"
                
                # Get real link instead of redirect
                link_elem = y.find('a')
                if link_elem:
                    link = link_elem['href']
                    # Remove Yahoo redirect
                    if 'r.search.yahoo.com' in link:
                        parsed = urlparse(link)
                        query_params = parse_qs(parsed.query)
                        link = query_params.get('p', [link])[0]
                else:
                    link = "No link"
                    
                # Get and clean description
                description = y.find('div', class_='compText').get_text(strip=True) if y.find('div', class_='compText') else "No description"
                description = description[:300] + '...' if len(description) > 300 else description
                
                # Get image if available
                image = y.find('img')['src'] if y.find('img') else "No image"
                
                # Format domain and source
                domain = urlparse(link).netloc.replace("www.", "")
                source = f"Source: [{domain}]({link})"
                
                results.append((title, description, source, image))
                
            except Exception as e:
                logging.error(f"Error parsing Yahoo result: {e}")
                continue
            
    elif engine == "duckduckgo":
        results = await search_ddg(
            query, 
            num_results=5,
            search_type='text'
        )

    elif engine == "ask":
        for a in soup.find_all('div', class_='PartialSearchResults-body'):
            title = a.find('div', class_='PartialSearchResults-title').text if a.find('div', class_='PartialSearchResults-title') else "No title"
            link = a.find('a', class_='PartialSearchResults-link')['href'] if a.find('a', class_='PartialSearchResults-link') else "No link"
            description = a.find('p', class_='PartialSearchResults-item-abstract').text if a.find('p', class_='PartialSearchResults-item-abstract') else "No description"
            image = a.find('img', class_='PartialSearchResults-image')['src'] if a.find('img', class_='PartialSearchResults-image') else "No image"
            
            domain = urlparse(link).netloc.replace("www.", "")
            source = f"Source: [{domain}]({link})"
            results.append((title, description, source, image))
            
    return results

def is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

@app_commands.command(name='meaning', description='Get the meaning of a word.')
async def meaning_command(interaction: discord.Interaction, word: str):
    await interaction.response.defer()
    
    # Validate the input word
    if not word.isalnum():
        await interaction.followup.send("Invalid word. Please enter a valid word.")
        return

    url = f"https://urbandictionary.com/define.php?term={word}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    meaning, example = parse_meaning(html)
                    if meaning and example:
                        embed = create_embed(interaction, word, meaning, example)
                        await interaction.followup.send(embed=embed)
                    else:
                        await interaction.followup.send("Could not find the meaning of the word.")
                else:
                    await interaction.followup.send("Could not fetch the meaning of the word. Please try again later.")
    except aiohttp.ClientError as e:
        await interaction.followup.send(f"An error occurred: {str(e)}")

def parse_meaning(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, 'html.parser')
    meaning = soup.find('div', class_='meaning')
    example = soup.find('div', class_='example')
    return (meaning.text.strip() if meaning else None, example.text.strip() if example else None)

def create_embed(interaction: discord.Interaction, word: str, meaning: str, example: str) -> discord.Embed:
    embed = discord.Embed(title=f"Meaning of '{word}'", description=meaning, color=discord.Color.green())
    embed.add_field(name="Example", value=example, inline=False)
    embed.set_thumbnail(url="https://media.discordapp.net/attachments/533926025747234838/1303814912858128518/Urban_Dictionary_logo.svg.png")
    embed.set_footer(text=interaction.client.user.name, icon_url=interaction.client.user.display_avatar.url)
    return embed

UNSPLASH_ACCESS_KEY = unsplash_env()
async def unsplash_image_search(query: str, orientation: str = 'landscape'):

    url = 'https://api.unsplash.com/photos/random'
    params = {
        'query': query,
        'client_id': UNSPLASH_ACCESS_KEY,
        'orientation': orientation  # Optional: 'landscape', 'portrait', 'squarish'
    }

    headers = {
        'Accept-Version': 'v1'
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    image_url = data['urls']['regular']
                    photographer = data['user']['name']
                    photo_link = data['links']['html']
                    return image_url, photographer, photo_link
                elif resp.status == 404:
                    logging.info(f"No images found for query: {query}")
                    return None, None, None
                elif resp.status == 403:
                    logging.info("Access Forbidden: Check your Unsplash Access Key and permissions.")
                    return None, None, None
                elif resp.status == 429:
                    logging.info("Rate limit exceeded: Too many requests to Unsplash API.")
                    return None, None, None
                else:
                    logging.error(f"Error fetching image: {resp.status}")
                    return None, None, None
        except asyncio.TimeoutError:
            logging.error("Request timed out while contacting Unsplash API.")
            return None, None, None
        except Exception as e:
            logging.error(f"Exception during Unsplash image search: {e}")
            return None, None, None

async def web_image_search(query: str, engine: str) -> str:
    async with aiohttp.ClientSession() as session:
        search_url = f"https://images.search.yahoo.com/search/images?p={query}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        
        try:
            async with session.get(search_url, headers=headers) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    if engine == "yahoo":
                        for img in soup.find_all(['li', 'div'], class_=['ld', 'img']):
                            image = img.find('img')
                            if not image:
                                continue
                            image_url = image.get('data-src') or image.get('src')
                            if image_url and not image_url.startswith('data:'):
                                return image_url
                                
                    elif engine == "bing":
                        for img in soup.find_all('div', class_='imgpt'):
                            image = img.find('img')
                            if image and 'src' in image.attrs:
                                return image['src']
                                
        except Exception as e:
            logging.error(f"Error in {engine} image search: {e}")
    return None

@app_commands.command(name="image", description="Search for an image")
@app_commands.choices(
    engine=[
        app_commands.Choice(name="Unsplash", value="unsplash"),
        app_commands.Choice(name="DuckDuckGo", value="duckduckgo"),
        app_commands.Choice(name="Bing", value="bing"),
        app_commands.Choice(name="Yahoo", value="yahoo")
    ],
    orientation=[
        app_commands.Choice(name="Landscape", value="landscape"),
        app_commands.Choice(name="Portrait", value="portrait"), 
        app_commands.Choice(name="Squarish", value="squarish")
    ]
)
async def image_command(
    interaction: discord.Interaction,
    query: str,
    engine: app_commands.Choice[str],
    orientation: app_commands.Choice[str] = None
):
    await interaction.response.defer()
    
    try:
        if engine.value == "unsplash":
            orient = orientation.value if orientation else "landscape"
            image_url, photographer, photo_link = await unsplash_image_search(query, orient)
            if image_url:
                embed = discord.Embed(
                    title=f"Image result for '{query}'",
                    description=f"Photo by [{photographer}]({photo_link}) on [Unsplash](https://unsplash.com/)",
                    color=discord.Color.blue()
                )
                embed.set_image(url=image_url)
                
        elif engine.value == "duckduckgo":
            results = await search_ddg(query, num_results=1, search_type='image')
            if results:
                title, description, source, image_url = results[0]
                embed = discord.Embed(title=f"Image search: {query}", color=discord.Color.blue())
                embed.set_image(url=image_url)
                embed.add_field(name=title, value=f"{description}\n{source}", inline=False)
                encoded_query = quote(query)
                embed.set_author(
                    name="DuckDuckGo Image Search",
                    icon_url=SEARCH_ENGINE_AUTHOR_ICONS["duckduckgo"],
                    url=f"https://duckduckgo.com/?q={encoded_query}&ia=images"
                )
                
        elif engine.value in ["bing", "yahoo"]:
            image_url = await web_image_search(query, engine.value)
            if image_url:
                embed = discord.Embed(title=f"Image search: {query}", color=discord.Color.blue())
                embed.set_image(url=image_url)
                embed.set_author(
                    name=f"{engine.value.capitalize()} Image Search",
                    icon_url=SEARCH_ENGINE_AUTHOR_ICONS[engine.value],
                    url=f"https://{engine.value}.com/images/search?q={query}"
                )
        
        if image_url:
            embed.set_footer(text=interaction.client.user.name, icon_url=interaction.client.user.display_avatar.url)
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"No images found for that query on {engine.value.capitalize()}.")
            
    except Exception as e:
        logging.error(f"Image search error: {e}")
        await interaction.followup.send("An error occurred while searching for images.")

API_KEY = pexels_env()
BASE_URL = 'https://api.pexels.com/videos/search'

def search_videos(query, per_page=10):
    headers = {
        'Authorization': API_KEY
    }
    params = {
        'query': query,
        'per_page': per_page,
        'page': random.randint(1, 50)  # Randomize page number
    }
    try:
        response = requests.get(BASE_URL, headers=headers, params=params)
        response.raise_for_status()
        return response.json().get('videos', [])
    except Exception as err:
        logging.error(f"Error occurred: {err}")
    return []

def get_popular_videos():
    headers = {
        'Authorization': API_KEY
    }
    params = {
        'per_page': 10,
        'page': random.randint(1, 50)
    }
    try:
        response = requests.get('https://api.pexels.com/videos/popular', headers=headers, params=params)
        response.raise_for_status()
        return response.json().get('videos', [])
    except Exception as e:
        logging.error(f"Error fetching popular videos: {e}")
    return []

@app_commands.command(name='video', description='Search for a video using Pexels.')
async def video(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    videos = search_videos(query)
    if not videos:
        await interaction.followup.send(
            f"No videos found for your query. Trying popular videos instead.")
        videos = get_popular_videos()
        if not videos:
            await interaction.followup.send("No videos found.")
            return

    success = await send_video(interaction, videos)
    if not success:
        await interaction.followup.send("Could not find a suitable video to send.")

async def send_video(interaction, videos):
    tried_videos = set()
    max_retries = 15

    for _ in range(max_retries):
        if not videos:
            return False
        video = random.choice(videos)
        video_url = video['video_files'][0]['link']
        video_id = video['id']

        if video_id in tried_videos:
            continue  # Skip if already tried
        tried_videos.add(video_id)

        # Download the video file
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(video_url) as resp:
                    if resp.status == 200:
                        video_data = await resp.read()
                        video_size = len(video_data)
                        if video_size > 50 * 1024 * 1024:  # Discord limit is 50 MB
                            continue  # Try another video
                        video_filename = f"video_{video_id}.mp4"
                        with open(video_filename, "wb") as f:
                            f.write(video_data)
                        try:
                            await interaction.followup.send(file=discord.File(video_filename))
                        finally:
                            os.remove(video_filename)
                        return True  # Video sent successfully
            except Exception as e:
                logging.error(f"Error downloading video: {e}")
                continue  # Try next video
    return False  # Failed to send a video after retries
                
# Hugging Face API Key
HF_API_KEY = hf_env()
if not HF_API_KEY:
    logging.error("Hugging Face API Key not found. Please set HF_API_KEY in your environment variables.")

# Qwen Image API URL
RUNPOD_ENDPOINT_ID, RUNPOD_API_KEY = qwen_env()
if not RUNPOD_ENDPOINT_ID or not RUNPOD_API_KEY:
    logging.error("RunPod credentials not found. Please set RUNPOD_ENDPOINT_ID and RUNPOD_API_KEY in your environment variables.")

# Aspect ratio presets for Qwen Image (1K quality)
ASPECT_RATIOS = {
    "1:1 Square": {"width": 1024, "height": 1024},
    "16:9 Landscape": {"width": 1920, "height": 1080},
    "9:16 Portrait": {"width": 1080, "height": 1920},
    "4:3 Standard": {"width": 1280, "height": 960},
    "3:4 Portrait": {"width": 960, "height": 1280},
    "21:9 Ultrawide": {"width": 2048, "height": 878},
    "3:2 Photo": {"width": 1536, "height": 1024},
    "2:3 Photo Portrait": {"width": 1024, "height": 1536},
}

# Loading GIFs for image generation (local files)
LOADING_GIFS = [
    "assets/loading_bars.gif",
    "assets/loading_circle.gif",
    "assets/loading_spinner.gif",
    "assets/loading_computer.gif"
]

# Explicit content keywords for basic filtering
EXPLICIT_KEYWORDS = [
    "nude", "naked", "nsfw", "porn", "sex", "sexual", "xxx", "adult", "erotic",
    "boobs", "breast", "tits", "ass", "pussy", "dick", "cock", "penis", "vagina",
    "hentai", "ecchi", "lewd", "fetish", "bdsm", "kinky", "explicit"
]

def check_explicit_content(prompt: str) -> bool:
    """Simple check for explicit content in prompt"""
    prompt_lower = prompt.lower()
    return any(keyword in prompt_lower for keyword in EXPLICIT_KEYWORDS)

async def _fallback_to_gemini(prompt: str) -> io.BytesIO | None:
    """
    Fallback to Gemini image generation when RunPod fails.
    
    Args:
        prompt: Text description of what to generate
    
    Returns:
        io.BytesIO containing the generated PNG image, or None on failure
    """
    try:
        logging.info(f"Using Gemini fallback for image generation: {prompt[:50]}...")
        client = genai.Client()
        response = client.models.generate_content(
            model="gemini-2.0-flash-preview-image-generation",
            contents=[prompt],
            config=genai.types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"]
            )
        )
        
        # Extract image from response
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'inline_data') and part.inline_data is not None:
                image_bytes = part.inline_data.data
                logging.info("Image generated successfully via Gemini fallback")
                return io.BytesIO(image_bytes)
        
        logging.error("No image data in Gemini response")
        return None
    except Exception as e:
        logging.error(f"Gemini fallback also failed: {e}")
        return None

async def generate_image_qwen(
    prompt,
    negative_prompt=" ",  # Space character enables CFG
    width=1024,
    height=1024,
    steps=50,
    cfg_scale=4.0,
    seed=None,
    retries=3,
    backoff_factor=2,
    status_callback=None  # Callback for status updates
):
    """
    Generate an image using the RunPod Serverless Qwen Image API.
    Falls back to Gemini if RunPod fails.
    
    Args:
        prompt: Text description of what to generate
        negative_prompt: What to avoid in the image (default: space for CFG)
        width: Image width in pixels (default: 1024)
        height: Image height in pixels (default: 1024)
        steps: Number of inference steps (default: 50)
        cfg_scale: Classifier-Free Guidance scale (default: 4.0)
        seed: Random seed for reproducibility (default: None/random)
        retries: Number of retry attempts (default: 3)
        backoff_factor: Backoff factor for retries (default: 2)
        status_callback: Optional async callback function for status updates
    
    Returns:
        io.BytesIO containing the generated PNG image, or None on failure
    """
    if not RUNPOD_ENDPOINT_ID or not RUNPOD_API_KEY:
        logging.error("RunPod credentials not configured, falling back to Gemini")
        return await _fallback_to_gemini(prompt)
    
    # Prepare request payload for RunPod serverless
    payload = {
        "input": {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "num_inference_steps": steps,
            "true_cfg_scale": cfg_scale
        }
    }
    
    if seed is not None:
        payload["input"]["seed"] = seed
    
    try:
        logging.info(f"Using RunPod serverless for Qwen image generation: {prompt[:50]}...")
        
        # RunPod serverless headers
        headers = {
            'Authorization': f'Bearer {RUNPOD_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        runpod_url = f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}/run"
        
        # Step 1: Submit job to RunPod serverless
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(
                runpod_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logging.error(f"Failed to submit RunPod job: {response.status}, {error_text}")
                    logging.info("Falling back to Gemini...")
                    return await _fallback_to_gemini(prompt)
                
                result = await response.json()
                job_id = result.get("id")
                
                if not job_id:
                    logging.error("No job_id returned from RunPod")
                    return await _fallback_to_gemini(prompt)
                
                logging.info(f"RunPod job submitted: {job_id}")
            
            # Step 2: Poll for completion
            status_url = f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}/status/{job_id}"
            max_attempts = 200  # 200 attempts * 3 seconds = 10 minutes
            poll_interval = 3
            
            for attempt in range(max_attempts):
                await asyncio.sleep(poll_interval)
                
                try:
                    async with session.get(
                        status_url,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as status_response:
                        if status_response.status != 200:
                            logging.warning(f"Failed to check status: {status_response.status}")
                            continue
                        
                        status_data = await status_response.json()
                        status = status_data.get("status")
                        
                        # Update status callback if provided
                        if status_callback:
                            try:
                                elapsed = (attempt + 1) * poll_interval
                                await status_callback(status, elapsed, max_attempts * poll_interval)
                            except Exception as e:
                                logging.error(f"Status callback error: {e}")
                        
                        if status == "COMPLETED":
                            output = status_data.get("output")
                            if not output:
                                logging.error("No output in RunPod response")
                                return await _fallback_to_gemini(prompt)
                            
                            image_b64 = output.get("image")
                            result_seed = output.get("seed")
                            
                            if not image_b64:
                                logging.error("No image data in RunPod result")
                                return await _fallback_to_gemini(prompt)
                            
                            # Decode base64 image
                            image_bytes = base64.b64decode(image_b64)
                            logging.info(f"Qwen image generated successfully via RunPod. Seed: {result_seed}")
                            return io.BytesIO(image_bytes)
                            
                        elif status == "FAILED":
                            error_msg = status_data.get("error", "Unknown error")
                            logging.error(f"RunPod job failed: {error_msg}")
                            return await _fallback_to_gemini(prompt)
                        
                        elif status in ["IN_QUEUE", "IN_PROGRESS"]:
                            # Still processing, continue polling
                            if attempt % 5 == 0:  # Log every 15 seconds
                                logging.info(f"RunPod job {job_id} status: {status} (attempt {attempt + 1}/{max_attempts})")
                            continue
                        else:
                            logging.warning(f"Unknown RunPod status: {status}")
                            continue
                
                except asyncio.TimeoutError:
                    logging.warning(f"Timeout checking status (attempt {attempt + 1})")
                    continue
                except Exception as e:
                    logging.warning(f"Error checking status: {e}")
                    continue
            
            # If we get here, we timed out
            logging.error(f"RunPod job timed out after {max_attempts * poll_interval} seconds")
            return await _fallback_to_gemini(prompt)
        
    except asyncio.TimeoutError:
        logging.error("RunPod image generation timed out, falling back to Gemini")
        return await _fallback_to_gemini(prompt)
    except aiohttp.ClientError as e:
        logging.error(f"RunPod API client error: {e}, falling back to Gemini")
        return await _fallback_to_gemini(prompt)
    except Exception as e:
        logging.error(f"Unexpected error in RunPod image generation: {e}, falling back to Gemini")
        return await _fallback_to_gemini(prompt)
    
async def generate_image(
    prompt,
    negative_prompt="(deformed iris, deformed pupils, semi-realistic, cgi, 3d, render, sketch, cartoon, drawing, anime:1.4), text, close up, cropped, out of frame, worst quality, low quality, jpeg artifacts, ugly, duplicate, morbid, mutilated, extra fingers, mutated hands, poorly drawn hands, poorly drawn face, mutation, deformed, blurry, dehydrated, bad anatomy, bad proportions, extra limbs, cloned face, disfigured, gross proportions, malformed limbs, missing arms, missing legs, extra arms, extra legs, fused fingers, too many fingers, long neck",
    width=None,
    height=None,
    steps=None,
    model="Qwen-Image",  # Changed default to Qwen-Image
    seed=None,
    retries=10,
    backoff_factor=2
):
    # Route to Qwen Image API if Qwen-Image model is selected (always uses async endpoint)
    if model == "Qwen-Image":
        return await generate_image_qwen(
            prompt=prompt,
            negative_prompt=negative_prompt if negative_prompt else " ",
            width=width if width else 1024,
            height=height if height else 1024,
            steps=steps if steps else 50,
            cfg_scale=4.0,
            seed=seed,
            retries=retries,
            backoff_factor=backoff_factor
        )
    
    # Retrieve the model information for HuggingFace models
    model_info = AVAILABLE_MODELS.get(model)
    if not model_info:
        logging.error(f"Model '{model}' not found. Using default Qwen-Image.")
        # Fallback to Qwen-Image if model not found
        return await generate_image_qwen(
            prompt=prompt,
            negative_prompt=negative_prompt if negative_prompt else " ",
            width=width if width else 1024,
            height=height if height else 1024,
            steps=steps if steps else 50,
            cfg_scale=4.0,
            seed=seed
        )
    hf_model_id = model_info["model_id"]

    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "inputs": prompt,
        "options": {
            "wait_for_model": True
        }
    }

    # Include additional parameters if provided
    data["negative_prompt"] = negative_prompt if negative_prompt else "(deformed iris, deformed pupils, semi-realistic, cgi, 3d, render, sketch, cartoon, drawing, anime:1.4), text, close up, cropped, out of frame, worst quality, low quality, jpeg artifacts, ugly, duplicate, morbid, mutilated, extra fingers, mutated hands, poorly drawn hands, poorly drawn face, mutation, deformed, blurry, dehydrated, bad anatomy, bad proportions, extra limbs, cloned face, disfigured, gross proportions, malformed limbs, missing arms, missing legs, extra arms, extra legs, fused fingers, too many fingers, long neck"
    if width:
        data["width"] = width
    if height:
        data["height"] = height
    if steps:
        data["steps"] = steps
    data["seed"] = seed if seed else random.randint(0, 3999999999)

    data = json.dumps(data)

    # Rest of the function remains the same...

    for attempt in range(1, retries + 1):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"https://api-inference.huggingface.co/models/{hf_model_id}",
                    headers=headers,
                    data=data,
                    timeout=120
                ) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        logging.info(f"Image generated successfully for prompt: '{prompt}' using model: '{model}'")
                        return io.BytesIO(image_data)
                    else:
                        text = await response.text()
                        logging.error(f"Error: {response.status}, Response: {text}")
                        if response.status in [429, 500, 502, 503, 504]:
                            raise aiohttp.ClientError(f"Server error: {response.status}")
                        return None
        except (asyncio.TimeoutError, aiohttp.ClientError) as e:
            logging.error(f"Attempt {attempt} failed with error: {e}")
            if attempt == retries:
                logging.error("All retry attempts failed.")
                return None
            await asyncio.sleep(backoff_factor ** attempt)
        except Exception as e:
            logging.error(f"Unexpected exception during image generation: {e}")
            return None
        
# Generate both text and image using Gemini image generation model from text-only prompt
async def generate_image_and_text_gemini(prompt: str) -> tuple[str | None, io.BytesIO | None]:
    try:
        client = genai.Client()
        response = client.models.generate_content(
            model="gemini-2.0-flash-preview-image-generation",
            contents=[prompt]
        )
        out_text: str | None = None
        out_image: io.BytesIO | None = None
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'text') and part.text and not out_text:
                out_text = part.text
            elif hasattr(part, 'inline_data') and part.inline_data is not None and out_image is None:
                out_image = io.BytesIO(part.inline_data.data)
        return out_text, out_image
    except Exception as e:
        logging.error(f"Gemini image generation error: {e}")
        return None, None

# Define available models and their descriptions
AVAILABLE_MODELS = {
    "Qwen-Image": {
        "model_id": "qwen-image",  # Special identifier for Qwen API
        "description": "Image generated using seeyuh-image-high (unlimited) (Fast Generation)"
    },
    "FLUX.1-schnell": {
        "model_id": "black-forest-labs/FLUX.1-schnell",
        "description": "Image generated using FLUX.1 [schnell]"
    },
    "stable-diffusion-3.5-turbo": {
        "model_id": "stabilityai/stable-diffusion-3.5-large-turbo",
        "description": "Image generated using Stable Diffusion 3.5 Turbo."
    },
    "stable-diffusion-3.5-large": {
        "model_id": "stabilityai/stable-diffusion-3.5-large",
        "description": "Image generated using Stable Diffusion 3.5 Large."
    },
    "FLUX.1-dev": {
        "model_id": "black-forest-labs/FLUX.1-dev",
        "description": "Image generated using FLUX.1 [dev]"
    },
    "stable-diffusion-3.5-medium": {
        "model_id": "stabilityai/stable-diffusion-3.5-medium",
        "description": "Image generated using Stable Diffusion 3.5 Medium."
    },
    "dreamlike-photoreal-2.0": {
        "model_id": "dreamlike-art/dreamlike-photoreal-2.0",
        "description": "Image generated using Dreamlike Photoreal 2.0."
    },
    "flux-midjourney-anime": {
        "model_id": "brushpenbob/flux-midjourney-anime",
        "description": "Image generated using FLUX Midjourney Anime."
    },
    "flux-ghibsky-illustration": {
        "model_id": "aleksa-codes/flux-ghibsky-illustration",
        "description": "Image generated using FLUX Ghibsky Illustration."
    },
    "stable-diffusion-xl-base-1.0": {
        "model_id": "stabilityai/stable-diffusion-xl-base-1.0",
        "description": "Image generated using Stable Diffusion XL Base 1.0."
    },
    "RealVisXL_V4.0": {
        "model_id": "SG161222/RealVisXL_V4.0",
        "description": "Image generated using RealVisXL V4.0."
    },
    "epiCPhotoGasm": {
        "model_id": "Yntec/epiCPhotoGasm",
        "description": "Image generated using epiCPhotoGasm."
    },
    "HyperRemix": {
        "model_id": "Yntec/HyperRemix",
        "description": "Image generated using HyperRemix."
    },
    "AnalogMadness-realistic-model-v5": {
        "model_id": "digiplay/AnalogMadness-realistic-model-v5",
        "description": "Image generated using AnalogMadness-realistic-model-v5."
    },
    "ZHMix-Dramatic-v2.0": {
        "model_id": "digiplay/ZHMix-Dramatic-v2.0",
        "description": "Image generated using ZHMix-Dramatic-v2.0."
    },
    "MilkyWonderland_v1": {
        "model_id": "digiplay/MilkyWonderland_v1",
        "description": "Image generated using MilkyWonderland_v1."
    },
    "Hyperlink": {
        "model_id": "Yntec/Hyperlink",
        "description": "Image generated using Hyperlink."
    },
    "pixel-art-xl": {
        "model_id": "nerijs/pixel-art-xl",
        "description": "Image generated using pixel-art-xl."
    },
    "stable-diffusion-3-medium": {
        "model_id": "stabilityai/stable-diffusion-3-medium",
        "description": "Image generated using Stable Diffusion 3 Medium."
    },
    "openjourney": {
        "model_id": "prompthero/openjourney",
        "description": "Image generated using OpenJourney."
    },
    "stable-diffusion-2-1": {
        "model_id": "stabilityai/stable-diffusion-2-1",
        "description": "Image generated using Stable Diffusion 2.1."
    },
    "beLIEve": {
        "model_id": "Yntec/beLIEve",
        "description": "Image generated using beLIEve."
    },
    "fishmix_other_v1": {
        "model_id": "digiplay/fishmix_other_v1",
        "description": "Image generated using fishmix_other_v1."
    },
    "HyperPhotoGASM" : {
        "model_id": "Yntec/HyperPhotoGASM",
        "description": "Image generated using HyperPhotoGASM."
    },
    "Gap_2.6": {
        "model_id": "digiplay/Gap_2.6",
        "description": "Image generated using Gap_2.6."
    },
    "CrystalReality": {
        "model_id": "Yntec/CrystalReality",
        "description": "Image generated using CrystalReality."
    },
    "meinamix-meinav11-sd15": {
        "model_id": "John6666/meinamix-meinav11-sd15",
        "description": "Image generated using meinamix-meinav11-sd15."
    },
    "ya3p_VAE": {
        "model_id": "digiplay/ya3p_VAE",
        "description": "Image generated using ya3p_VAE."
    },
    "ZemiHR_v2_diffusers": {
        "model_id": "digiplay/ZemiHR_v2_diffusers",
        "description": "Image generated using ZemiHR_v2_diffusers."
    },
    "Chip_n_DallE": {
        "model_id": "Yntec/Chip_n_DallE",
        "description": "Image generated using Chip_n_DallE."
    },
    "ClayStyle": {
        "model_id": "Yntec/ClayStyle",
        "description": "Image generated using ClayStyle."
    },
    "Maji5PlusCCTV": {
        "model_id": "digiplay/Maji5PlusCCTV",
        "description": "Image generated using Maji5PlusCCTV."
    },
    "LusterMix_v1.5_safetensors": {
        "model_id": "digiplay/LusterMix_v1.5_safetensors",
        "description": "Image generated using LusterMix_v1.5_safetensors."
    },
    "Ponygraphy": {
        "model_id": "Yntec/Ponygraphy",
        "description": "Image generated using Ponygraphy."
    },
    "DucHaitenGODofSIMP": {
        "model_id": "Yntec/DucHaitenGODofSIMP",
        "description": "Image generated using DucHaitenGODofSIMP."
    },
    "DonutHoleMix_Beta": {
        "model_id": "digiplay/DonutHoleMix_Beta",
        "description": "Image generated using DonutHoleMix_Beta."
    },
    "Flux.1-dev-LoRA-r128-RedditReality": {
        "model_id": "RareConcepts/Flux.1-dev-LoRA-r128-RedditReality",
        "description": "Image generated using RedditReality"
    },
    "Reddit": {
        "model_id": "Yntec/Reddit",
        "description": "Image generated using Reddit"
    },
    "Flux-Super-Realism-LoRA": {
        "model_id": "strangerzonehf/Flux-Super-Realism-LoRA",
        "description": "Image generated using Flux-Super-Realism-LoRA"
    },
    "FLUX_master": {
        "model_id": "user3712931729/flux-nsfw-highres",
        "description": "Image generated using FLUX_master"
    },
    "DucHaiten-Real3D-V1": {
        "model_id": "digiplay/DucHaiten-Real3D-NSFW-V1",
        "description": "Image generated using DucHaiten-Real3D-V1"
    },

}

# Create mapping from internal model values to display names
MODEL_DISPLAY_NAMES = {
    "Qwen-Image": "seeyuh-image-high (unlimited)",
    "stable-diffusion-3.5-turbo": "Stable Diffusion 3.5 Turbo",
    "FLUX.1-schnell": "FLUX.1-schnell",
    "stable-diffusion-3.5-large": "Stable Diffusion 3.5 Large",
    "FLUX.1-dev": "FLUX.1-dev",
    "flux-ghibsky-illustration": "FLUX Ghibsky Illustration",
    "Flux-Super-Realism-LoRA": "FLUX Super Realism LoRA",
    "FLUX_master": "FLUX Master Highres",
    "stable-diffusion-xl-base-1.0": "Stable Diffusion XL Base 1.0",
    "RealVisXL_V4.0": "RealVisXL V4.0",
    "epiCPhotoGasm": "epiCPhotoGasm",
    "HyperRemix": "HyperRemix",
    "AnalogMadness-realistic-model-v5": "AnalogMadness-realistic-model-v5",
    "ZHMix-Dramatic-v2.0": "ZHMix-Dramatic-v2.0",
    "MilkyWonderland_v1": "MilkyWonderland_v1",
    "openjourney": "OpenJourney",
    "LusterMix_v1.5_safetensors": "LusterMix_v1.5_safetensors",
    "Chip_n_DallE": "Chip_n_DallE",
    "ZemiHR_v2_diffusers": "ZemiHR_v2_diffusers",
    "meinamix-meinav11-sd15": "meinamix-meinav11-sd15",
    "ya3p_VAE": "ya3p_VAE",
    "Maji5PlusCCTV": "maJi5PlusCCTV",
    "DonutHoleMix_Beta": "DonutHoleMix_Beta",
    "DucHaiten-Real3D-V1": "DucHaiten-Real3D-V1",
    "Gap_2.6": "Gap_2.6",
}

MODEL_CHOICES = [
    app_commands.Choice(name="seeyuh-image-high (Default - unlimited)", value="Qwen-Image"),
    app_commands.Choice(name="Stable Diffusion 3.5 Turbo", value="stable-diffusion-3.5-turbo"),
    app_commands.Choice(name="FLUX.1-schnell", value="FLUX.1-schnell"),
    app_commands.Choice(name="Stable Diffusion 3.5 Large", value="stable-diffusion-3.5-large"),
    app_commands.Choice(name="FLUX.1-dev", value="FLUX.1-dev"),
    app_commands.Choice(name="FLUX Ghibsky Illustration", value="flux-ghibsky-illustration"),
    app_commands.Choice(name="FLUX Super Realism LoRA", value="Flux-Super-Realism-LoRA"),
    app_commands.Choice(name="FLUX Master Highres", value="FLUX_master"),
    app_commands.Choice(name="Stable Diffusion XL Base 1.0", value="stable-diffusion-xl-base-1.0"),
    app_commands.Choice(name="RealVisXL V4.0", value="RealVisXL_V4.0"),
    app_commands.Choice(name="epiCPhotoGasm", value="epiCPhotoGasm"),
    app_commands.Choice(name="HyperRemix", value="HyperRemix"),
    app_commands.Choice(name="AnalogMadness-realistic-model-v5", value="AnalogMadness-realistic-model-v5"),
    app_commands.Choice(name="ZHMix-Dramatic-v2.0", value="ZHMix-Dramatic-v2.0"),
    app_commands.Choice(name="MilkyWonderland_v1", value="MilkyWonderland_v1"),
    app_commands.Choice(name="OpenJourney", value="openjourney"),
    app_commands.Choice(name="LusterMix_v1.5_safetensors", value="LusterMix_v1.5_safetensors"),
    app_commands.Choice(name="Chip_n_DallE", value="Chip_n_DallE"),
    app_commands.Choice(name="ZemiHR_v2_diffusers", value="ZemiHR_v2_diffusers"),
    app_commands.Choice(name="meinamix-meinav11-sd15", value="meinamix-meinav11-sd15"),
    app_commands.Choice(name="ya3p_VAE", value="ya3p_VAE"),
    app_commands.Choice(name="maJi5PlusCCTV", value="Maji5PlusCCTV"),
    app_commands.Choice(name="DonutHoleMix_Beta", value="DonutHoleMix_Beta"),
    app_commands.Choice(name="DucHaiten-Real3D-V1", value="DucHaiten-Real3D-V1"),
    app_commands.Choice(name="Gap_2.6", value="Gap_2.6")
]

ASPECT_RATIO_CHOICES = [
    app_commands.Choice(name="1:1 Square (1024x1024)", value="1:1 Square"),
    app_commands.Choice(name="16:9 Landscape (1920x1080)", value="16:9 Landscape"),
    app_commands.Choice(name="9:16 Portrait (1080x1920)", value="9:16 Portrait"),
    app_commands.Choice(name="4:3 Standard (1280x960)", value="4:3 Standard"),
    app_commands.Choice(name="3:4 Portrait (960x1280)", value="3:4 Portrait"),
    app_commands.Choice(name="21:9 Ultrawide (2048x878)", value="21:9 Ultrawide"),
    app_commands.Choice(name="3:2 Photo (1536x1024)", value="3:2 Photo"),
    app_commands.Choice(name="2:3 Photo Portrait (1024x1536)", value="2:3 Photo Portrait"),
]

@app_commands.command(name="imagine", description="Generate an image with AI")
@app_commands.describe(
    prompt="The text prompt for the image.",
    model="Choose AI model to use.",
    aspect_ratio="Choose aspect ratio preset (overrides custom width/height).",
    negative_prompt="Text to avoid in the image (optional).",
    width="Custom width in pixels (ignored if aspect_ratio is set).",
    height="Custom height in pixels (ignored if aspect_ratio is set).",
    steps="Number of inference steps (optional).",
    seed="Seed for the image generation (optional)."
)
@app_commands.choices(model=MODEL_CHOICES, aspect_ratio=ASPECT_RATIO_CHOICES)
async def imagine_command(
    interaction: discord.Interaction,
    prompt: str,
    model: str = "Qwen-Image",
    aspect_ratio: Optional[str] = None,
    negative_prompt: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    steps: Optional[int] = None,
    seed: Optional[int] = None
):
    await interaction.response.defer()
    
    # Check for explicit content in prompt
    if check_explicit_content(prompt):
        embed = discord.Embed(
            title="⚠️ Content Warning",
            description="Your prompt may contain explicit content that violates Discord's Terms of Service.\n\n"
                       "Discord automatically blocks NSFW images from being sent to certain channels and users.\n\n"
                       "Please modify your prompt to comply with Discord's content policy.",
            color=discord.Color.red()
        )
        embed.set_footer(text="Tip: Use appropriate channels and age-restricted servers for mature content")
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    # Get dimensions for display
    final_width = width
    final_height = height
    
    # Handle aspect ratio vs custom dimensions
    if aspect_ratio and aspect_ratio in ASPECT_RATIOS:
        dimensions = ASPECT_RATIOS[aspect_ratio]
        final_width = dimensions["width"]
        final_height = dimensions["height"]
        logging.info(f"Using aspect ratio '{aspect_ratio}': {final_width}x{final_height}")
    
    # For Qwen-Image, show loading animation with status updates
    if model == "Qwen-Image":
        # Pick a random loading gif
        loading_gif_path = random.choice(LOADING_GIFS)
        loading_gif_filename = os.path.basename(loading_gif_path)
        
        # Load the local GIF file
        loading_gif_file = discord.File(loading_gif_path, filename=loading_gif_filename)
        
        # Create initial loading embed
        embed = discord.Embed(
            title="🎨 Generating Image...",
            description=f"**Prompt:** {prompt[:100]}{'...' if len(prompt) > 100 else ''}\n**Status:** Starting generation...",
            color=discord.Color.blue()
        )
        embed.set_image(url=f"attachment://{loading_gif_filename}")
        embed.set_footer(text=f"Model: {MODEL_DISPLAY_NAMES.get(model, model)} | Resolution: {final_width or 1024}x{final_height or 1024}")
        
        # Send loading message with attached GIF
        loading_message = await interaction.followup.send(embed=embed, file=loading_gif_file, wait=True)
        
        # Status update callback
        last_update_time = [time.time()]  # Use list to allow modification in nested function
        
        async def update_status(status, elapsed, max_time, error_detail=None):
            # Update every 10 seconds to avoid rate limits
            if time.time() - last_update_time[0] < 10 and status not in ["done", "error"]:
                return
            
            last_update_time[0] = time.time()
            
            if status == "queued":
                status_text = "⏳ Queued - Waiting to start..."
            elif status == "running":
                progress = min(int((elapsed / max_time) * 100), 95)
                status_text = f"⚡ Generating... ({progress}% - {elapsed}s elapsed)"
            elif status == "error":
                status_text = f"❌ Error: {error_detail}"
            else:
                status_text = f"🔄 {status.capitalize()}..."
            
            embed.description = f"**Prompt:** {prompt[:100]}{'...' if len(prompt) > 100 else ''}\n**Status:** {status_text}"
            
            try:
                await loading_message.edit(embed=embed)
            except Exception as e:
                logging.error(f"Failed to update status message: {e}")
        
        # Prepare kwargs for generation
        kwargs = {
            "prompt": prompt,
            "negative_prompt": negative_prompt if negative_prompt else " ",
            "width": final_width if final_width else 1024,
            "height": final_height if final_height else 1024,
            "steps": steps if steps else 50,
            "cfg_scale": 4.0,
            "seed": seed,
            "status_callback": update_status
        }
        
        # Generate image with Qwen
        image_data = await generate_image_qwen(**kwargs)
        
        if image_data:
            try:
                image_data.seek(0)
                file = discord.File(fp=image_data, filename="image.png")
                
                # Edit loading message to show final image
                await loading_message.edit(content=None, embed=None, attachments=[file])
            except discord.HTTPException as e:
                # Check if it's the explicit content error
                if e.code == 20009:
                    logging.error(f"Discord blocked explicit content: {e}")
                    error_embed = discord.Embed(
                        title="🚫 Content Blocked by Discord",
                        description="Discord's safety systems detected that this image contains explicit or NSFW content.\n\n"
                                   "**Possible reasons:**\n"
                                   "• The generated image violates Discord's Terms of Service\n"
                                   "• This channel or recipient cannot receive NSFW content\n"
                                   "• The image was flagged by Discord's automated filters\n\n"
                                   "**What you can do:**\n"
                                   "• Use an age-restricted channel marked as NSFW\n"
                                   "• Modify your prompt to be more appropriate\n"
                                   "• Contact server administrators about NSFW channels",
                        color=discord.Color.red()
                    )
                    error_embed.set_footer(text="Discord enforces strict content policies to keep communities safe")
                    await loading_message.edit(content=None, embed=error_embed, attachments=[])
                else:
                    logging.error(f"Discord HTTP error sending image: {e}")
                    await loading_message.edit(
                        content=f"Failed to send the image: {str(e)}", 
                        embed=None, 
                        attachments=[]
                    )
            except Exception as e:
                logging.error(f"Error sending image to Discord: {e}")
                await loading_message.edit(content="Failed to send the generated image.", embed=None, attachments=[])
        else:
            await loading_message.edit(
                content="Sorry, I couldn't generate an image for that prompt. Please try again later.",
                embed=None,
                attachments=[]
            )
    else:
        # For non-Qwen models, use original flow without status updates
        kwargs = {
            "prompt": prompt,
            "model": model
        }
        
        if final_width is not None:
            kwargs["width"] = final_width
        if final_height is not None:
            kwargs["height"] = final_height
        if negative_prompt is not None:
            kwargs["negative_prompt"] = negative_prompt
        if steps is not None:
            kwargs["steps"] = steps
        if seed is not None:
            kwargs["seed"] = seed

        image_data = await generate_image(**kwargs)

        if image_data:
            try:
                image_data.seek(0)
                file = discord.File(fp=image_data, filename="image.png")
                await interaction.followup.send(file=file)
            except discord.HTTPException as e:
                # Check if it's the explicit content error
                if e.code == 20009:
                    logging.error(f"Discord blocked explicit content: {e}")
                    error_embed = discord.Embed(
                        title="🚫 Content Blocked by Discord",
                        description="Discord's safety systems detected that this image contains explicit or NSFW content.\n\n"
                                   "**Possible reasons:**\n"
                                   "• The generated image violates Discord's Terms of Service\n"
                                   "• This channel or recipient cannot receive NSFW content\n"
                                   "• The image was flagged by Discord's automated filters\n\n"
                                   "**What you can do:**\n"
                                   "• Use an age-restricted channel marked as NSFW\n"
                                   "• Modify your prompt to be more appropriate\n"
                                   "• Contact server administrators about NSFW channels",
                        color=discord.Color.red()
                    )
                    error_embed.set_footer(text="Discord enforces strict content policies to keep communities safe")
                    await interaction.followup.send(embed=error_embed)
                else:
                    logging.error(f"Discord HTTP error sending image: {e}")
                    await interaction.followup.send(f"Failed to send the image: {str(e)}")
            except Exception as e:
                logging.error(f"Error sending image to Discord: {e}")
                await interaction.followup.send("Failed to send the generated image.")
        else:
            await interaction.followup.send(
                "Sorry, I couldn't generate an image for that prompt. Please try again later."
            )
        
async def generate_caption(image_bytes):
    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json",
    }

    # Encode image to base64 string
    encoded_image = base64.b64encode(image_bytes).decode('utf-8')

    # Prepare the payload
    payload = {
        "inputs": {
            "image": encoded_image
        }
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-large",
            headers=headers,
            json=payload,
            timeout=120
        ) as response:
            if response.status == 200:
                result = await response.json()
                if isinstance(result, list) and len(result) > 0:
                    caption = result[0].get('generated_text', '')
                    return caption
                else:
                    logging.info("No caption generated.")
            else:
                text = await response.text()
                logging.error(f"Error: {response.status}, Response: {text}")
    return None

@app_commands.command(name="caption", description="Generate a caption for an image.")
@app_commands.describe(
    image="The image to caption."
)
async def caption_command(
    interaction: discord.Interaction,
    image: discord.Attachment
):
    await interaction.response.defer()
    try:
        image_bytes = await image.read()
        caption = await generate_caption(image_bytes)
        if caption:
            embed = discord.Embed(
                title="Image Caption",
                description=caption,
                color=discord.Color.blue()
            )
            embed.set_author(
                name=f"Requested by {interaction.user}",
                icon_url=interaction.user.display_avatar.url
            )
            file = discord.File(fp=io.BytesIO(image_bytes), filename="image.png")
            embed.set_image(url="attachment://image.png")
            embed.set_footer(
                text=interaction.client.user.name,
                icon_url=interaction.client.user.display_avatar.url
            )
            await interaction.followup.send(embed=embed, file=file)
        else:
            await interaction.followup.send(
                "Sorry, I couldn't generate a caption for the image. Please try again later."
            )
    except Exception as e:
        logging.error(f"Error: {e}")
        await interaction.followup.send("An error occurred while processing your request.")
        
async def generate_variations(image_bytes):
    headers = {
        "Authorization": f"Bearer {HF_API_KEY}"
        # Do not set 'Content-Type' header when sending raw binary data
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api-inference.huggingface.co/models/lambdalabs/sd-image-variations-diffusers",
            headers=headers,
            data=image_bytes,  # Send the raw image bytes directly
            timeout=360
        ) as response:
            if response.status == 200:
                # The API returns the generated image bytes directly
                generated_image = io.BytesIO(await response.read())
                return generated_image
            else:
                text = await response.text()
                logging.error(f"Error: {response.status}, Response: {text}")
    return None
@app_commands.command(name="variation", description="Generate a variation of an image using AI.")
@app_commands.describe(
    image="The image to generate a variation from."
)
async def variation_command(
    interaction: discord.Interaction,
    image: discord.Attachment
):
    await interaction.response.defer()
    try:
        # Read the image bytes from the attachment
        image_bytes = await image.read()

        # Generate the variation
        variation_image = await generate_variations(image_bytes)

        if variation_image:
            variation_file = discord.File(fp=variation_image, filename="variation.png")
            original_file = discord.File(fp=io.BytesIO(image_bytes), filename="image.png")
            embed = discord.Embed(
                title="Image Variation",
                color=discord.Color.blue()
            )
            embed.set_author(
                name=f"Requested by {interaction.user}",
                icon_url=interaction.user.display_avatar.url
            )
            embed.set_image(url="attachment://variation.png")
            embed.set_thumbnail(url="attachment://image.png")
            embed.set_footer(
                text=interaction.client.user.name,
                icon_url=interaction.client.user.display_avatar.url
            )
            await interaction.followup.send(embed=embed, files=[variation_file, original_file])
        else:
            await interaction.followup.send(
                "Sorry, I couldn't generate a variation of the image. Please try again later."
            )
    except Exception as e:
        logging.error(f"Error: {e}")
        await interaction.followup.send(
            "An error occurred while processing your request."
        )
        
async def refine_image(image_bytes, prompt):
    try:
        # Convert bytes to PIL Image
        image = Image.open(io.BytesIO(image_bytes))
        
        # Convert to PNG format
        png_buffer = io.BytesIO()
        image.save(png_buffer, format='PNG')
        png_buffer.seek(0)
        png_bytes = png_buffer.getvalue()
    except Exception as e:
        logging.error(f"Image validation error: {e}")
        return None

    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Prepare payload with both image and prompt
    payload = {
        "inputs": png_bytes,
        "prompt": prompt
    }

    # Send raw image bytes
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-refiner-1.0",
            headers=headers,
            data=png_bytes,  # Send raw bytes directly
            timeout=120
        ) as response:
            if response.status == 200:
                refined_image = io.BytesIO(await response.read())
                refined_image.seek(0)
                return refined_image
            else:
                text = await response.text()
                logging.error(f"Error: {response.status}, Response: {text}")
    return None

@app_commands.command(name="refine", description="Refine an image using AI.")
@app_commands.describe(
    image="The image to refine.",
    prompt="A text prompt to guide the refinement."
)
async def refine_command(
    interaction: discord.Interaction,
    image: discord.Attachment,
    prompt: str
):
    await interaction.response.defer()
    try:
        # Read the image bytes from the attachment
        image_bytes = await image.read()

        # Refine the image
        refined_image = await refine_image(image_bytes, prompt)

        if refined_image:
            refined_file = discord.File(fp=refined_image, filename="refined_image.png")
            original_file = discord.File(fp=io.BytesIO(image_bytes), filename="image.png")
            embed = discord.Embed(
                title="Refined Image",
                description=f"Prompt: {prompt}",
                color=discord.Color.blue()
            )
            embed.set_author(
                name=f"Requested by {interaction.user}",
                icon_url=interaction.user.display_avatar.url
            )
            embed.set_image(url="attachment://refined_image.png")
            embed.set_thumbnail(url="attachment://image.png")
            embed.set_footer(
                text=interaction.client.user.name,
                icon_url=interaction.client.user.display_avatar.url
            )
            await interaction.followup.send(embed=embed, files=[refined_file, original_file])
        else:
            await interaction.followup.send(
                "Sorry, I couldn't refine the image. Please try again later."
            )
    except Exception as e:
        logging.error(f"Error: {e}")
        await interaction.followup.send(
            "An error occurred while processing your request."
        )

async def modify_image(image_bytes, instruction):
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            pil_image = img.convert('RGB')
    except Exception as e:
        logging.error(f"Image validation error: {e}")
        return None

    try:
        client = genai.Client()
        response = client.models.generate_content(
            model="gemini-2.0-flash-preview-image-generation",
            contents=[instruction, pil_image],
            config=genai.types.GenerateContentConfig(
                response_modalities=["IMAGE"]
            )
        )
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'inline_data') and part.inline_data is not None:
                return io.BytesIO(part.inline_data.data)
        return None
    except Exception as e:
        logging.error(f"Gemini image modify error: {e}")
        return None

@app_commands.command(name="modify", description="Modify an image based on an instruction.")
@app_commands.describe(
    image="The image to modify.",
    instruction="A text instruction describing the modification."
)
async def modify_command(
    interaction: discord.Interaction,
    image: discord.Attachment,
    instruction: str
):
    await interaction.response.defer()
    try:
        # Read the image bytes from the attachment
        image_bytes = await image.read()

        # Modify the image
        modified_image = await modify_image(image_bytes, instruction)

        if modified_image:
            modified_file = discord.File(fp=modified_image, filename="modified_image.png")
            original_file = discord.File(fp=io.BytesIO(image_bytes), filename="image.png")
            embed = discord.Embed(
                title="Modified Image",
                description=f"Instruction: {instruction}",
                color=discord.Color.blue()
            )
            embed.set_author(
                name=f"Requested by {interaction.user}",
                icon_url=interaction.user.display_avatar.url
            )
            embed.set_image(url="attachment://modified_image.png")
            embed.set_thumbnail(url="attachment://image.png")
            embed.set_footer(
                text=interaction.client.user.name,
                icon_url=interaction.client.user.display_avatar.url
            )
            await interaction.followup.send(embed=embed, files=[modified_file, original_file])
        else:
            await interaction.followup.send(
                "Sorry, I couldn't modify the image. Please try again later."
            )
    except Exception as e:
        logging.error(f"Error: {e}")
        await interaction.followup.send(
            "An error occurred while processing your request."
        )

async def search_youtube(query):
    search = Search(query)
    results = []
    for video in search.results:
        results.append((video.title, video.description, video.watch_url, video.thumbnail_url))
    return results

@app_commands.command(name="youtube", description="Search for videos on YouTube.")
@app_commands.describe(
    query="The search query for YouTube."
)
async def youtube_command(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    try:
        results = await search_youtube(query)
        if results:
            embed = discord.Embed(
                title=f"Search Results for '{query}'",
                color=discord.Color.red()
            )
            embed.set_author(
                name=f"Requested by {interaction.user}",
                icon_url=interaction.user.display_avatar.url
            )
            embed.set_footer(
                text=interaction.client.user.name,
                icon_url=interaction.client.user.display_avatar.url
            )
            for title, description, source, thumbnail in results:
                # Handle None values and truncate long descriptions
                safe_title = title if title else "No title available"
                safe_description = description[:200] + "..." if description and len(description) > 200 else description if description else "No description available"
                safe_source = source if source else "#"
                
                embed.add_field(
                    name=safe_title[:256],  # Discord embed title limit
                    value=f"{safe_description}\n{safe_source}",
                    inline=False
                )
                embed.set_thumbnail(url=thumbnail)
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("No results found for the search query.")
    except Exception as e:
        logging.error(f"Error: {e}")
        await interaction.followup.send("An error occurred while processing your request.")

# Define the language choices for TTS
tts_language_choices = [
    app_commands.Choice(name="English (US)", value="en-US"),
    app_commands.Choice(name="English (UK)", value="en-GB"),
    app_commands.Choice(name="Spanish", value="es"),
    app_commands.Choice(name="French", value="fr"),
    app_commands.Choice(name="German", value="de"),
    app_commands.Choice(name="Italian", value="it"),
    app_commands.Choice(name="Portuguese", value="pt"),
    app_commands.Choice(name="Russian", value="ru"),
    app_commands.Choice(name="Japanese", value="ja"),
    app_commands.Choice(name="Korean", value="ko"),
    app_commands.Choice(name="Chinese (Mandarin)", value="zh"),
    app_commands.Choice(name="Hindi", value="hi"),
    app_commands.Choice(name="Arabic", value="ar"),
    app_commands.Choice(name="Dutch", value="nl"),
    app_commands.Choice(name="Polish", value="pl"),
    app_commands.Choice(name="Turkish", value="tr"),
    app_commands.Choice(name="Vietnamese", value="vi"),
    app_commands.Choice(name="Thai", value="th"),
    app_commands.Choice(name="Greek", value="el"),
    app_commands.Choice(name="Swedish", value="sv"),
    app_commands.Choice(name="Danish", value="da"),
    app_commands.Choice(name="Finnish", value="fi"),
    app_commands.Choice(name="Norwegian", value="no"),
    app_commands.Choice(name="Czech", value="cs"),
    app_commands.Choice(name="Bengali", value="bn")
]
PREFERRED_REGIONS = [
    'us-east', 
    'us-central',
    'us-west',
    'us-south'
]
@app_commands.command(name="tts", description="Convert text or AI response to speech.")
@app_commands.describe(
    text="Direct text to convert to speech",
    prompt="Get AI response for this prompt and convert to speech",
    language="The language to use for text-to-speech."
)
@app_commands.choices(language=tts_language_choices)
async def text_to_speech(
    interaction: discord.Interaction,
    text: str = None,
    prompt: str = None,
    language: app_commands.Choice[str] = None
):
    try:
        await interaction.response.defer(ephemeral=True)

        if not text and not prompt:
            raise ValueError("Please provide either text or prompt")

        if text and prompt:
            raise ValueError("Please provide either text or prompt, not both")

        if prompt:
            text = await get_tts_text(prompt, language.name if language else "English")

        if not interaction.user.voice:
            raise ValueError("You need to be in a voice channel to use this command!")

        if not interaction.guild.voice_client:
            voice_channel = interaction.user.voice.channel
        
            # Try preferred regions
            for region in PREFERRED_REGIONS:
                try:
                    #await voice_channel.edit(rtc_region=region)
                    await voice_channel.connect()
                    logging.info(f"Connected to {voice_channel} with region {region}")
                    break
                except discord.HTTPException:
                    continue
            else:
                # Fallback without region specification
                await voice_channel.connect()
                logging.info(f"Connected to {voice_channel} with default region")
            
        lang_code = language.value if language else "en-US"
        tts_url = f"https://translate.google.com/translate_tts?ie=UTF-8&tl={lang_code}&client=tw-ob&q={text}"

        temp_path = None
        with safe_tempfile(interaction.guild.id) as tmp:
            temp_path = tmp
            async with aiohttp.ClientSession() as session:
                async with session.get(tts_url) as response:
                    if response.status != 200:
                        raise Exception(f"TTS service returned status code {response.status}")
                        
                    # Write file
                    async with aiofiles.open(temp_path, 'wb') as f:
                        await f.write(await response.read())
                    
                    # Verify file
                    if not temp_path.exists():
                        raise FileNotFoundError(f"File not found: {temp_path}")
                    
                    if temp_path.stat().st_size == 0:
                        raise ValueError("Empty audio file created")
                        
                    logging.info(f"Created temp file: {temp_path} Size: {temp_path.stat().st_size}")
                    
                    # Small delay to ensure file is fully written
                    await asyncio.sleep(0.5)
                    
                    # Create audio source
                    try:
                        source = await discord.FFmpegOpusAudio.from_probe(
                            str(temp_path),
                            options='-filter:a volume=2.0'
                        )
                    except Exception as e:
                        logging.error(f"FFmpeg error: {e}")
                        raise
                        
                    # Play audio
                    if interaction.guild.voice_client.is_playing():
                        interaction.guild.voice_client.stop()
                    
                    def after_playing(error):
                        if error:
                            logging.error(f"Playback error: {error}")
                        # Clean up file after playback
                        try:
                            if temp_path and temp_path.exists():
                                temp_path.unlink()
                        except Exception as e:
                            logging.error(f"Cleanup error: {e}")
                    
                    interaction.guild.voice_client.play(source, after=after_playing)
                    
                    # Send confirmation
                    embed = discord.Embed(
                        title="Text to Speech",
                        description=f"Now playing TTS message in {language.name if language else 'English (US)'}",
                        color=discord.Color.green()
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        logging.error(f"TTS error: {e}")
        embed = discord.Embed(
            title="Error", 
            description=f"An error occurred: {str(e)}", 
            color=discord.Color.red()
        )
        # Clean up on error
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except:
                pass
        await interaction.followup.send(embed=embed, ephemeral=True)
        
API_URL = "https://api-inference.huggingface.co/models/facebook/musicgen-small"

async def generate_music(prompt: str) -> bytes:
    """Generate music from text using HuggingFace API"""
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    payload = {"inputs": prompt}
    
    async with aiohttp.ClientSession() as session:
        async with session.post(API_URL, headers=headers, json=payload) as response:
            if response.status != 200:
                raise Exception(f"API request failed with status {response.status}")
            return await response.read()

def sync_cleanup(file_path: str):
    """Wait before cleanup to ensure playback completes"""
    time.sleep(2)  # Add delay
    try:
        if os.path.exists(file_path):
            os.unlink(file_path)
            logging.info(f"Cleaned up temp file: {file_path}")
    except Exception as e:
        logging.error(f"Cleanup error: {str(e)}")

@app_commands.command(name="musicgen", description="Generate music using AI.")
@app_commands.describe(prompt="Description of the music you want to generate")
async def musicgen(interaction: discord.Interaction, prompt: str):
    await interaction.response.send_message(
        "🎵 **Music Generation**\n\n"
        "This feature is currently only available to supporters and donors! "
        "Help keep the bot running and unlock exclusive AI music generation capabilities.\n\n"
        "💎 **Support us to access:**\n"
        "• AI Music Generation\n"
        "• Premium AI Models\n"
        "• Priority Support\n\n"
        "Contact the bot owner for donation/support options.",
        ephemeral=True
    )
        
genai_client = genai.Client(api_key=os.getenv('GEMINI_PRO_API_KEY'), http_options={'api_version':'v1alpha'})

@app_commands.command(
    name="reason",
    description="Get AI's reasoning with code execution capability"
)
@app_commands.describe(
    prompt="The topic or question to reason about"
)
async def reason_command(
    interaction: discord.Interaction, 
    prompt: str
):
    try:
        await interaction.response.defer()
        
        config = {
            'thinking_config': {'include_thoughts': True}
        }
        
        response = genai_client.models.generate_content(
            model='gemini-2.0-flash-thinking-exp-01-21',
            contents=prompt,
            config=config
        )

        def create_new_embed():
            return discord.Embed(color=discord.Color.blue())

        def chunk_text(text, limit=900):
            chunks = []
            while text:
                if len(text) <= limit:
                    chunks.append(text)
                    break
                
                split_index = text.rfind('\n', 0, limit)
                if split_index == -1:
                    split_index = limit
                
                chunks.append(text[:split_index])
                text = text[split_index:].lstrip()
            return chunks

        # Send initial embed with prompt
        initial_embed = discord.Embed(
            title="🤔 AI Reasoning",
            description=f"{prompt}",
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=initial_embed)

        # Process thoughts and response
        for part in response.candidates[0].content.parts:
            if part.thought:
                chunks = chunk_text(part.text)
                for i, chunk in enumerate(chunks):
                    embed = create_new_embed()
                    embed.add_field(
                        name=f"💭 Thought Process (Part {i+1})" if len(chunks) > 1 else "💭 Thought Process",
                        value=f"{chunk}",  # Added code block formatting
                        inline=False
                    )
                    await interaction.followup.send(embed=embed)
            else:
                chunks = chunk_text(part.text)
                for i, chunk in enumerate(chunks):
                    embed = create_new_embed()
                    embed.add_field(
                        name=f"🔍 Response (Part {i+1})" if len(chunks) > 1 else "🔍 Response",
                        value=chunk,
                        inline=False
                    )
                    await interaction.followup.send(embed=embed)

    except Exception as e:
        logging.error(f"Reason command error: {e}")
        await interaction.followup.send(
            f"❌ Error: {str(e)}",
            ephemeral=True
        )

@app_commands.command(name="edit-image", description="Edit an image using Seeyuh Native Image Editor. Upload an image and describe the edit you want.")
@app_commands.describe(
    image="The image to edit (attachment)",
    prompt="Describe the edit you want (e.g., 'add a llama next to me')"
)
async def edit_image_command(
    interaction: discord.Interaction,
    image: discord.Attachment,
    prompt: str
):
    await interaction.response.defer()

    # Check file type and size
    if not image.content_type or not image.content_type.startswith("image/"):
        await interaction.followup.send("Please upload a valid image file.")
        return
    if image.size > 10 * 1024 * 1024:
        await interaction.followup.send("Image size exceeds 10 MB limit. Please upload a smaller image.")
        return

    try:
        # Download the image
        async with aiohttp.ClientSession() as session:
            async with session.get(image.url) as resp:
                if resp.status != 200:
                    await interaction.followup.send("Failed to download the image.")
                    return
                img_bytes = await resp.read()

        pil_image = Image.open(io.BytesIO(img_bytes)).convert("RGB")

        # Send initial embed with original image as thumbnail
        embed = discord.Embed(
            title="Editing Image with Seeyuh Native Image Editor...",
            description=f"**Prompt:** {prompt}",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=image.url)
        embed.set_footer(text="Original image preview")
        await interaction.followup.send(embed=embed)

        # Prepare Gemini client and call
        client = genai.Client()
        text_input = prompt
        response = client.models.generate_content(
            model="gemini-2.0-flash-preview-image-generation",
            contents=[text_input, pil_image]
        )

        # Process response
        sent = False
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'text') and part.text:
                await interaction.followup.send(part.text)
                sent = True
            elif hasattr(part, 'inline_data') and part.inline_data is not None:
                img_result = Image.open(io.BytesIO(part.inline_data.data)).convert("RGBA")

                # Add watermark: 'AI' text and bot avatar at bottom right
                draw = ImageDraw.Draw(img_result)
                font_size = max(16, img_result.width // 32)
                try:
                    font = ImageFont.truetype("arial.ttf", font_size)
                except Exception:
                    font = ImageFont.load_default()
                text = "AI"
                # PIL >= 8.0.0: use font.getbbox, else fallback to font.getsize
                try:
                    bbox = font.getbbox(text)
                    text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
                except AttributeError:
                    text_width, text_height = font.getsize(text)
                margin = 8
                x = img_result.width - text_width - font_size - margin * 2
                y = img_result.height - text_height - margin
                # Draw text with shadow for visibility
                draw.text((x+1, y+1), text, font=font, fill=(0,0,0,180))
                draw.text((x, y), text, font=font, fill=(255,255,255,220))

                # Add bot avatar as small circle
                try:
                    avatar_bytes = None
                    if interaction.client.user.avatar:
                        avatar_url = interaction.client.user.avatar.url
                        async with aiohttp.ClientSession() as session:
                            async with session.get(avatar_url) as resp:
                                if resp.status == 200:
                                    avatar_bytes = await resp.read()
                    if avatar_bytes:
                        avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
                        avatar_size = font_size * 2
                        avatar_img = avatar_img.resize((avatar_size, avatar_size), Image.LANCZOS)
                        # Make avatar circular
                        mask = Image.new("L", (avatar_size, avatar_size), 0)
                        mask_draw = ImageDraw.Draw(mask)
                        mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
                        avatar_img.putalpha(mask)
                        avatar_x = img_result.width - avatar_size - margin
                        avatar_y = img_result.height - avatar_size - margin
                        img_result.alpha_composite(avatar_img, (avatar_x, avatar_y))
                except Exception as e:
                    logging.warning(f"Failed to add avatar watermark: {e}")

                with io.BytesIO() as output:
                    img_result.save(output, format="PNG")
                    output.seek(0)
                    file = discord.File(fp=output, filename="edited_image.png")
                    await interaction.followup.send(file=file)
                    sent = True
        if not sent:
            await interaction.followup.send("No result was returned by the AI.")
    except Exception as e:
        logging.error(f"edit-image error: {e}")
        await interaction.followup.send(f"❌ Error: {str(e)}")

# ---------------- Welcome configuration commands ----------------

def has_welcome_permissions(user_permissions) -> bool:
    """Check if user has permissions to manage welcome settings"""
    return (user_permissions.administrator or 
            user_permissions.manage_guild or 
            user_permissions.manage_channels)

@app_commands.command(name="welcome-enable", description="Enable welcome messages for this server")
async def welcome_enable(interaction: discord.Interaction):
    if not has_welcome_permissions(interaction.user.guild_permissions):
        await interaction.response.send_message("❌ You need **Administrator**, **Manage Server**, or **Manage Channels** permission to configure welcome messages.", ephemeral=True)
        return
    set_welcome_settings(str(interaction.guild.id), enabled=True)
    await interaction.response.send_message("✅ Welcome messages **enabled** for this server!")


@app_commands.command(name="welcome-disable", description="Disable welcome messages for this server")
async def welcome_disable(interaction: discord.Interaction):
    if not has_welcome_permissions(interaction.user.guild_permissions):
        await interaction.response.send_message("❌ You need **Administrator**, **Manage Server**, or **Manage Channels** permission to configure welcome messages.", ephemeral=True)
        return
    set_welcome_settings(str(interaction.guild.id), enabled=False)
    await interaction.response.send_message("🚫 Welcome messages **disabled** for this server.")


@app_commands.command(name="welcome-message", description="Set a custom welcome message")
@app_commands.describe(message="Use placeholders: {mention}, {user}, {guild}, {intro}, {roles}")
async def welcome_message(interaction: discord.Interaction, message: str):
    if not has_welcome_permissions(interaction.user.guild_permissions):
        await interaction.response.send_message("❌ You need **Administrator**, **Manage Server**, or **Manage Channels** permission to configure welcome messages.", ephemeral=True)
        return
    
    if len(message) > 1000:
        await interaction.response.send_message("❌ Welcome message must be 1000 characters or less.", ephemeral=True)
        return
        
    set_welcome_settings(str(interaction.guild.id), message=message)
    await interaction.response.send_message(f"✍️ Custom welcome message saved:\n> {message[:200]}{'...' if len(message) > 200 else ''}")


@app_commands.command(name="welcome-channel", description="Choose the channel for welcome messages")
@app_commands.describe(channel="Text channel to post welcome messages in")
async def welcome_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not has_welcome_permissions(interaction.user.guild_permissions):
        await interaction.response.send_message("❌ You need **Administrator**, **Manage Server**, or **Manage Channels** permission to configure welcome messages.", ephemeral=True)
        return
    if not channel.permissions_for(interaction.guild.me).send_messages:
        await interaction.response.send_message("❌ I don't have permission to send messages in that channel.", ephemeral=True)
        return
    set_welcome_settings(str(interaction.guild.id), channel_id=str(channel.id))
    await interaction.response.send_message(f"📢 Welcome channel set to {channel.mention}")


# Aspect ratio presets for InfiniteTalk (custom resolutions supported)
aspect_ratio_choices = [
    app_commands.Choice(name="16:9 - 854px (854x480)", value="854x480"),
    app_commands.Choice(name="9:16 - 854px Portrait (480x854)", value="480x854"),
    app_commands.Choice(name="1:1 - 512px (512x512)", value="512x512"),
    app_commands.Choice(name="16:9 - 512px (512x288)", value="512x288"),
    app_commands.Choice(name="16:9 - 768px (768x432)", value="768x432"),
    app_commands.Choice(name="9:16 - 512px (288x512)", value="288x512"),
    app_commands.Choice(name="9:16 - 768px Portrait (432x768)", value="432x768")
]

def get_dimensions_from_preset(preset: str) -> tuple:
    """Convert preset string to width and height"""
    try:
        width, height = preset.split('x')
        return (int(width), int(height))
    except:
        return (512, 512)  # Default

@app_commands.command(name="animate", description="Animate an image/video with audio using Seeyuh-Animate-S2V")
@app_commands.describe(
    media="Image or video to animate (PNG/JPG/MP4/MOV)",
    audio="Audio file (WAV/MP3) - optional if using text",
    audio2="Secondary audio file for multi-person mode (optional)",
    text="Text for TTS audio - optional if using audio file",
    prompt="Animation prompt/style - optional, AI will use default if empty",
    resolution="Output aspect ratio preset",
    person_count="Number of people in the animation",
    language="Language for text-to-speech (if using text)"
)
@app_commands.choices(
    resolution=aspect_ratio_choices,
    person_count=[
        app_commands.Choice(name="Single Person", value="single"),
        app_commands.Choice(name="Multi-Person", value="multi")
    ],
    language=tts_language_choices
)
async def animate_command(
    interaction: discord.Interaction,
    media: discord.Attachment,
    audio: discord.Attachment = None,
    audio2: discord.Attachment = None,
    text: str = None,
    prompt: str = None,
    resolution: app_commands.Choice[str] = None,
    person_count: app_commands.Choice[str] = None,
    language: app_commands.Choice[str] = None
):
    """Animate an image/video with audio using InfiniteTalk AI from RunPod"""
    
    # Load InfiniteTalk credentials
    INFINITETALK_ENDPOINT_ID, INFINITETALK_API_KEY = infinitetalk_env()

    if not INFINITETALK_ENDPOINT_ID or not INFINITETALK_API_KEY:
        await interaction.response.send_message(
            "❌ InfiniteTalk is not configured. Please set `INFINITETALK_ENDPOINT_ID` and `INFINITETALK_API_KEY` environment variables.",
            ephemeral=True
        )
        return

    # Get S3 credentials for network volume uploads
    s3_access_key = os.getenv("RUNPOD_VOLUME_ACCESS_KEY", "")
    s3_secret_key = os.getenv("RUNPOD_VOLUME_SECRET_KEY", "")

    if not s3_access_key or not s3_secret_key:
        await interaction.response.send_message(
            "❌ S3 credentials not configured. Please set `RUNPOD_VOLUME_ACCESS_KEY` and `RUNPOD_VOLUME_SECRET_KEY` environment variables.",
            ephemeral=True
        )
        return
    
    # Validate media format (image or video)
    is_video = media.content_type and media.content_type.startswith('video/')
    is_image = media.content_type and media.content_type.startswith('image/')
    
    if not is_image and not is_video:
        await interaction.response.send_message(
            "❌ Please provide a valid image (PNG/JPG) or video (MP4/MOV) file.",
            ephemeral=True
        )
        return
    
    # Validate audio/text input
    person_count_value = person_count.value if person_count else "single"
    if not audio and not text:
        await interaction.response.send_message(
            "❌ You must provide either:\n"
            "• An audio file, OR\n"
            "• Text for text-to-speech\n\n"
            "If you provide text without a language, AI will detect the best language automatically.",
            ephemeral=True
        )
        return

    # Validate second audio for multi-person mode
    if person_count_value == "multi" and audio and not audio2:
        await interaction.response.send_message(
            "❌ Multi-person mode requires two audio files. Please provide both primary and secondary audio files.",
            ephemeral=True
        )
        return
    
    # Validate audio format if provided
    if audio and audio.content_type and not audio.content_type.startswith('audio/'):
        await interaction.response.send_message(
            "❌ Please provide a valid audio file (WAV, MP3).",
            ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    try:
        # Initialize S3 uploader
        s3_uploader = S3Uploader(s3_access_key, s3_secret_key)

        # Upload media to S3
        media_bytes = await media.read()
        media_type = "video" if is_video else "image"
        media_path = s3_uploader.upload_file(media_bytes, media.filename, folder=media_type + "s")
        logging.info(f"Uploaded media to network volume: {media_path}")

        # Get dimensions from resolution preset
        width, height = get_dimensions_from_preset(resolution.value if resolution else "512x512")

        # Prepare base payload with network volume
        person_count_value = person_count.value if person_count else "single"
        payload = {
            "input": {
                "prompt": prompt if prompt else "Create a natural, expressive talking animation that matches the audio perfectly with realistic facial movements and lip sync",
                "input_type": media_type,  # "image" or "video"
                "person_count": person_count_value,
                "width": width,
                "height": height,
                "network_volume": True
            }
        }

        # Add media path based on input type
        if media_type == "image":
            payload["input"]["image_path"] = media_path
        else:
            payload["input"]["video_path"] = media_path
        
        # Handle audio source
        audio_source = None
        if audio:
            # User provided audio file - upload to S3
            audio_bytes = await audio.read()
            audio_path = s3_uploader.upload_file(audio_bytes, audio.filename, folder="audio")
            payload["input"]["wav_path"] = audio_path
            audio_source = f"audio file: {audio.filename}"
            logging.info(f"Uploaded primary audio to network volume: {audio_path}")

            # Handle second audio for multi-person mode
            if person_count_value == "multi" and audio2:
                audio2_bytes = await audio2.read()
                audio2_path = s3_uploader.upload_file(audio2_bytes, audio2.filename, folder="audio")
                payload["input"]["wav_path_2"] = audio2_path
                audio_source += f" + {audio2.filename}"
                logging.info(f"Uploaded secondary audio to network volume: {audio2_path}")
        
        elif text:
            # Use text-to-speech
            tts_text = text
            tts_language = language.value if language else None
            
            # If no language specified, use AI to detect language and generate appropriate text
            if not tts_language:
                logging.info(f"No language specified, using AI to detect and optimize text...")
                
                # Use AI to analyze text and determine best language
                ai_prompt = f"""Analyze this text and determine the most appropriate language code and potentially improve the text for natural speech.

Text: {text}

Return ONLY a JSON object with this exact format (no markdown, no code blocks):
{{"text": "optimized text for speech", "language": "language-code"}}

Language codes: en-US, en-GB, es, fr, de, it, pt, ru, ja, ko, zh, hi, ar, nl, pl, tr, vi, th, el, sv, da, fi, no, cs, bn

If text is already good, return it as-is. Only improve if needed for better speech synthesis."""
                
                try:
                    ai_response = await get_tts_text(ai_prompt, "en")
                    # Parse AI response
                    ai_response = ai_response.strip()
                    # Remove markdown code blocks if present
                    if ai_response.startswith('```'):
                        ai_response = ai_response.split('```')[1]
                        if ai_response.startswith('json'):
                            ai_response = ai_response[4:]
                    
                    ai_data = json.loads(ai_response)
                    tts_text = ai_data.get("text", text)
                    tts_language = ai_data.get("language", "en-US")
                    logging.info(f"AI detected language: {tts_language}, optimized text: {tts_text[:50]}...")
                except Exception as e:
                    logging.warning(f"AI language detection failed, using defaults: {e}")
                    tts_language = "en-US"
            
            # Generate TTS audio using edge-tts with gTTS fallback
            tts_temp_path = TEMP_DIR / f'tts_{interaction.user.id}_{int(time.time())}.mp3'
            
            try:
                import edge_tts
                
                # Map our language codes to edge-tts voices
                voice_map = {
                    "en-US": "en-US-AriaNeural",
                    "en-GB": "en-GB-SoniaNeural",
                    "es": "es-ES-ElviraNeural",
                    "fr": "fr-FR-DeniseNeural",
                    "de": "de-DE-KatjaNeural",
                    "it": "it-IT-ElsaNeural",
                    "pt": "pt-BR-FranciscaNeural",
                    "ru": "ru-RU-SvetlanaNeural",
                    "ja": "ja-JP-NanamiNeural",
                    "ko": "ko-KR-SunHiNeural",
                    "zh": "zh-CN-XiaoxiaoNeural",
                    "hi": "hi-IN-SwaraNeural",
                    "ar": "ar-SA-ZariyahNeural",
                    "nl": "nl-NL-ColetteNeural",
                    "pl": "pl-PL-ZofiaNeural",
                    "tr": "tr-TR-EmelNeural",
                    "vi": "vi-VN-HoaiMyNeural",
                    "th": "th-TH-PremwadeeNeural",
                    "el": "el-GR-AthinaNeural",
                    "sv": "sv-SE-SofieNeural",
                    "da": "da-DK-ChristelNeural",
                    "fi": "fi-FI-NooraNeural",
                    "no": "nb-NO-PernilleNeural",
                    "cs": "cs-CZ-VlastaNeural",
                    "bn": "bn-IN-TanishaaNeural"
                }
                
                voice = voice_map.get(tts_language, "en-US-AriaNeural")
                
                # Generate audio with edge-tts
                communicate = edge_tts.Communicate(tts_text, voice)
                await communicate.save(str(tts_temp_path))
                
                audio_source = f"TTS (edge-tts): '{tts_text[:30]}...' in {tts_language}"
                logging.info(f"Generated TTS audio with edge-tts: {tts_text[:50]} in {tts_language}")
                
            except (ImportError, Exception) as edge_error:
                logging.warning(f"edge-tts failed: {edge_error}, falling back to gTTS")
                
                try:
                    from gtts import gTTS
                    
                    # Map to gTTS language codes
                    gtts_lang_map = {
                        "en-US": "en", "en-GB": "en", "es": "es", "fr": "fr",
                        "de": "de", "it": "it", "pt": "pt", "ru": "ru",
                        "ja": "ja", "ko": "ko", "zh": "zh-CN", "hi": "hi",
                        "ar": "ar", "nl": "nl", "pl": "pl", "tr": "tr",
                        "vi": "vi", "th": "th", "el": "el", "sv": "sv",
                        "da": "da", "fi": "fi", "no": "no", "cs": "cs", "bn": "bn"
                    }
                    
                    gtts_lang = gtts_lang_map.get(tts_language, "en")
                    tts = gTTS(text=tts_text, lang=gtts_lang)
                    tts.save(str(tts_temp_path))
                    
                    audio_source = f"TTS (gTTS): '{tts_text[:30]}...' in {tts_language}"
                    logging.info(f"Generated TTS audio with gTTS fallback: {tts_text[:50]} in {gtts_lang}")
                    
                except Exception as gtts_error:
                    logging.error(f"Both edge-tts and gTTS failed: {gtts_error}")
                    await interaction.followup.send(f"❌ Failed to generate text-to-speech. Install edge-tts or gTTS: `pip install edge-tts gtts`")
                    return
            
            # Upload generated audio to S3
            try:
                async with aiofiles.open(tts_temp_path, 'rb') as f:
                    tts_audio_bytes = await f.read()

                # Upload TTS audio to S3
                tts_filename = f"tts_{interaction.user.id}_{int(time.time())}.mp3"
                audio_path = s3_uploader.upload_file(tts_audio_bytes, tts_filename, folder="tts")
                payload["input"]["wav_path"] = audio_path
                logging.info(f"Uploaded TTS audio to network volume: {audio_path}")

                # Cleanup temp file
                tts_temp_path.unlink()

            except Exception as e:
                logging.error(f"Failed to upload TTS audio: {e}")
                if tts_temp_path.exists():
                    tts_temp_path.unlink()
                await interaction.followup.send(f"❌ Failed to process TTS audio: {str(e)}")
                return
        
        # Handle prompt
        if prompt:
            payload["input"]["prompt"] = prompt
            logging.info(f"Using custom prompt: {prompt}")
        else:
            # Use default prompt
            payload["input"]["prompt"] = "Create a natural, expressive talking animation that matches the audio perfectly with realistic facial movements and lip sync"
            logging.info("Using default animation prompt")
        
        # Headers for RunPod API
        headers = {
            'Authorization': f'Bearer {INFINITETALK_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        # Submit job to InfiniteTalk RunPod endpoint
        runpod_url = f"https://api.runpod.ai/v2/{INFINITETALK_ENDPOINT_ID}/run"
        
        logging.info(f"Submitting InfiniteTalk job for {interaction.user.name}...")
        
        async with aiohttp.ClientSession() as session:
            # Submit job
            async with session.post(runpod_url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logging.error(f"InfiniteTalk submission failed: {response.status} - {error_text}")
                    await interaction.followup.send(f"❌ Failed to submit animation job: {response.status}")
                    return
                
                result = await response.json()
                job_id = result.get('id')
                
                if not job_id:
                    await interaction.followup.send("❌ Failed to get job ID from InfiniteTalk")
                    return
                
                logging.info(f"InfiniteTalk job submitted: {job_id}")
                
                # Pick a random loading GIF (same as /imagine)
                loading_gif_path = random.choice(LOADING_GIFS)
                loading_gif_filename = os.path.basename(loading_gif_path)
                
                # Load the local GIF file
                loading_gif_file = discord.File(loading_gif_path, filename=loading_gif_filename)
                
                # Create initial embed with loading GIF
                embed = discord.Embed(
                    title="🎬 Animation In Progress",
                    description=f"**Job ID:** `{job_id}`\n**Status:** Submitting to RunPod...",
                    color=discord.Color.blue()
                )
                embed.add_field(name="🖼️ Media", value=f"{media_type} ({media.filename})", inline=True)
                embed.add_field(name="🔊 Audio", value=audio_source[:100], inline=True)
                
                # Fix aspect ratio display
                resolution_name = resolution.name if resolution else "1:1 - 512px (512x512)"
                embed.add_field(name="📐 Resolution", value=f"{resolution_name}", inline=True)
                
                if prompt:
                    embed.add_field(name="💭 Prompt", value=prompt[:200] + ('...' if len(prompt) > 200 else ''), inline=False)
                
                embed.set_image(url=f"attachment://{loading_gif_filename}")
                embed.set_footer(text="This may take 20-30 minutes for complex animations")
                
                status_message = await interaction.followup.send(embed=embed, file=loading_gif_file)
            
            # Poll for completion (up to 40 minutes for long jobs)
            status_url = f"https://api.runpod.ai/v2/{INFINITETALK_ENDPOINT_ID}/status/{job_id}"
            max_attempts = 480  # 40 minutes max (5s intervals)
            attempt = 0
            last_status = None
            start_time = time.time()
            
            while attempt < max_attempts:
                await asyncio.sleep(5)  # Wait 5 seconds between polls
                attempt += 1
                elapsed = time.time() - start_time
                
                async with session.get(status_url, headers=headers) as status_response:
                    if status_response.status != 200:
                        logging.error(f"Failed to check job status: {status_response.status}")
                        continue
                    
                    status_data = await status_response.json()
                    job_status = status_data.get('status')
                    
                    logging.info(f"InfiniteTalk job {job_id} status: {job_status} (attempt {attempt}/{max_attempts}, {elapsed:.0f}s elapsed)")
                    
                    # Update embed every 30 seconds or when status changes
                    if job_status != last_status or attempt % 6 == 0:
                        embed.description = f"**Job ID:** `{job_id}`\n**Status:** {job_status}\n**Elapsed Time:** {elapsed/60:.1f} minutes"
                        embed.color = discord.Color.orange() if job_status == "IN_PROGRESS" else discord.Color.blue()
                        
                        try:
                            await status_message.edit(embed=embed)
                        except:
                            pass
                        
                        last_status = job_status
                    
                    if job_status == 'COMPLETED':
                        output = status_data.get('output')
                        
                        if not output:
                            embed.title = "❌ Animation Failed"
                            embed.description = "Animation completed but no output found."
                            embed.color = discord.Color.red()
                            await status_message.edit(embed=embed)
                            return
                        
                        # Handle different output formats
                        video_url = None
                        if isinstance(output, dict):
                            # Try different possible field names for the video
                            video_url = (output.get('video_url') or
                                       output.get('video_path') or
                                       output.get('output') or
                                       output.get('result') or
                                       output.get('video'))

                            # If video_path starts with /runpod-volume/, download directly from S3
                            if video_url and video_url.startswith('/runpod-volume/'):
                                filename = video_url.split('/')[-1]
                                logging.info(f"Downloading video directly from S3: {filename}")

                                # Download directly from S3 instead of using backend URL
                                try:
                                    # Initialize S3 client
                                    import boto3
                                    from botocore.exceptions import ClientError

                                    s3_client = boto3.client(
                                        's3',
                                        endpoint_url=S3_ENDPOINT,
                                        aws_access_key_id=s3_access_key,
                                        aws_secret_access_key=s3_secret_key,
                                        region_name=S3_REGION
                                    )

                                    # Get video from S3
                                    s3_response = s3_client.get_object(Bucket=S3_BUCKET, Key=filename)
                                    video_bytes = s3_response['Body'].read()

                                    logging.info(f"Successfully downloaded {len(video_bytes)} bytes from S3")

                                    # Send video directly without URL-based download
                                    temp_video = TEMP_DIR / f'animated_{interaction.user.id}_{job_id}.mp4'
                                    try:
                                        async with aiofiles.open(temp_video, 'wb') as f:
                                            await f.write(video_bytes)

                                        # Delete the status embed and send video
                                        try:
                                            await status_message.delete()
                                        except:
                                            pass

                                        # Send the animated video
                                        exec_time = status_data.get('executionTime', 0) / 1000
                                        await interaction.followup.send(
                                            f"✅ **Animation Complete!**\n"
                                            f"⏱️ Total Time: {elapsed/60:.1f} minutes (Execution: {exec_time:.1f}s)\n"
                                            f"🎬 Generated by InfiniteTalk AI\n"
                                            f"📐 {width}x{height}",
                                            file=discord.File(temp_video, filename=f"animated_{job_id}.mp4")
                                        )

                                        logging.info(f"Animation sent successfully for job {job_id}")
                                        return

                                    finally:
                                        # Cleanup
                                        if temp_video.exists():
                                            temp_video.unlink()

                                except Exception as s3_error:
                                    logging.error(f"Failed to download from S3: {s3_error}")
                                    # Fall back to trying the backend URL if S3 fails
                                    video_url = f"{BOT_DOMAIN}/infinittalk/download-public/{filename}"
                                    logging.info(f"Falling back to backend URL: {video_url}")
                                    # Continue with URL-based download
                        elif isinstance(output, str):
                            video_url = output
                        elif isinstance(output, list) and len(output) > 0:
                            video_url = output[0]
                        
                        if not video_url:
                            logging.error(f"Could not extract video URL from output: {output}")
                            embed.title = "❌ Animation Failed"
                            embed.description = "Animation completed but video URL not found in output."
                            embed.color = discord.Color.red()
                            await status_message.edit(embed=embed)
                            return
                        
                        logging.info(f"Animation completed! Video URL: {video_url}")
                        
                        # Update embed to show downloading
                        embed.title = "📥 Downloading Video"
                        embed.description = f"**Job ID:** `{job_id}`\n**Status:** Downloading completed video..."
                        embed.color = discord.Color.green()
                        try:
                            await status_message.edit(embed=embed)
                        except:
                            pass
                        
                        # Download the video
                        async with session.get(video_url, timeout=aiohttp.ClientTimeout(total=120)) as video_response:
                            if video_response.status != 200:
                                embed.title = "❌ Download Failed"
                                embed.description = f"Failed to download video: {video_response.status}"
                                embed.color = discord.Color.red()
                                await status_message.edit(embed=embed)
                                return
                            
                            video_bytes = await video_response.read()
                            
                            # Save to temp file
                            temp_video = TEMP_DIR / f'animated_{interaction.user.id}_{job_id}.mp4'
                            try:
                                async with aiofiles.open(temp_video, 'wb') as f:
                                    await f.write(video_bytes)
                                
                                # Delete the status embed and send video
                                try:
                                    await status_message.delete()
                                except:
                                    pass
                                
                                # Send the animated video
                                exec_time = status_data.get('executionTime', 0) / 1000
                                await interaction.followup.send(
                                    f"✅ **Animation Complete!**\\n"
                                    f"⏱️ Total Time: {elapsed/60:.1f} minutes (Execution: {exec_time:.1f}s)\\n"
                                    f"🎬 Generated by InfiniteTalk AI\\n"
                                    f"📐 {width}x{height} ({resolution.name if resolution else 'Square'})",
                                    file=discord.File(temp_video, filename=f"animated_{job_id}.mp4")
                                )
                                
                                logging.info(f"Animation sent successfully for job {job_id}")
                                return
                                
                            finally:
                                # Cleanup
                                if temp_video.exists():
                                    temp_video.unlink()
                    
                    elif job_status == 'FAILED':
                        error_msg = status_data.get('error', 'Unknown error')
                        logging.error(f"InfiniteTalk job failed: {error_msg}")
                        
                        embed.title = "❌ Animation Failed"
                        embed.description = f"**Job ID:** `{job_id}`\n**Error:** {error_msg}"
                        embed.color = discord.Color.red()
                        await status_message.edit(embed=embed)
                        return
                    
                    elif job_status in ['IN_QUEUE', 'IN_PROGRESS']:
                        # Still processing, continue polling
                        continue
                    
                    else:
                        logging.warning(f"Unknown job status: {job_status}")
            
            # Timeout
            embed.title = "⏱️ Animation Timed Out"
            embed.description = f"**Job ID:** `{job_id}`\n**Status:** Timeout after {max_attempts * 5 / 60:.0f} minutes\nThe job may still be processing on RunPod."
            embed.color = discord.Color.red()
            await status_message.edit(embed=embed)
    
    except asyncio.TimeoutError:
        await interaction.followup.send("❌ Request timed out. Please try again.")
    except Exception as e:
        logging.error(f"InfiniteTalk animation error: {e}", exc_info=True)
        await interaction.followup.send(f"❌ An error occurred: {str(e)}")


@app_commands.command(name="welcome-show", description="Show current welcome configuration")
async def welcome_show(interaction: discord.Interaction):
    settings = get_welcome_settings(str(interaction.guild.id))
    ch = interaction.guild.get_channel(int(settings['channel_id'])) if settings.get('channel_id') else None
    
    embed = discord.Embed(
        title="🎉 Welcome Configuration",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="Status", 
        value="✅ Enabled" if settings.get('enabled', True) else "🚫 Disabled",
        inline=True
    )
    
    embed.add_field(
        name="Channel", 
        value=ch.mention if ch else "🔍 Auto-detect",
        inline=True
    )
    
    custom_msg = settings.get('message')
    if custom_msg:
        embed.add_field(
            name="Custom Message", 
            value=f"```{custom_msg[:100]}{'...' if len(custom_msg) > 100 else ''}```",
            inline=False
        )
    else:
        embed.add_field(
            name="Message", 
            value="📝 Default: `Welcome {mention} to {guild}.`",
            inline=False
        )
    
    embed.add_field(
        name="Available Placeholders",
        value="`{mention}` - User mention\n`{user}` - Display name\n`{guild}` - Server name\n`{intro}` - Welcome intro\n`{roles}` - Role count",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


@app_commands.command(name="welcome-reset", description="Reset welcome settings to default")
async def welcome_reset(interaction: discord.Interaction):
    if not has_welcome_permissions(interaction.user.guild_permissions):
        await interaction.response.send_message("❌ You need **Administrator**, **Manage Server**, or **Manage Channels** permission to configure welcome messages.", ephemeral=True)
        return
    
    set_welcome_settings(str(interaction.guild.id), enabled=True, channel_id=None, message=None)
    await interaction.response.send_message("🔄 Welcome settings **reset** to default:\n✅ Enabled\n📢 Auto-detect channel\n📝 Default message")
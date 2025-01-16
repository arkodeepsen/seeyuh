import discord, asyncio, aiohttp, random, httpx, re, json, io, base64, requests, os, logging, tempfile, aiofiles, time
from duckduckgo_search import DDGS
from discord import app_commands, File
from pathlib import Path
from typing import Optional
from pytube import Search
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup
from PIL import Image
from contextlib import contextmanager
from filelock import FileLock
from engine.utils import load_env, get_reddit_access_token, unsplash_env, hf_env, pexels_env
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
                search_results = list(ddgs.text(
                    query, region='wt-wt',
                    safesearch='moderate', 
                    max_results=num_results,
                    backend='html'
                ))
                
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
                chat_response = ddgs.chat(
                    query,
                    model=model if model else "claude-3-haiku",
                    timeout=30
                )
                if chat_response:
                    results.append((
                        "AI Response",
                        chat_response,
                        "Source: DuckDuckGo AI",
                        "No image"
                    ))
                    
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
        
        main_embed.set_author(
            name="DuckDuckGo News",
            icon_url=SEARCH_ENGINE_AUTHOR_ICONS["duckduckgo"],
            url=f"https://duckduckgo.com/?q={query}&ia=news"
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
                embed.set_author(
                    name="DuckDuckGo Image Search",
                    icon_url=SEARCH_ENGINE_AUTHOR_ICONS["duckduckgo"],
                    url=f"https://duckduckgo.com/?q={query}&ia=images"
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
    
async def generate_image(
    prompt,
    negative_prompt="(deformed iris, deformed pupils, semi-realistic, cgi, 3d, render, sketch, cartoon, drawing, anime:1.4), text, close up, cropped, out of frame, worst quality, low quality, jpeg artifacts, ugly, duplicate, morbid, mutilated, extra fingers, mutated hands, poorly drawn hands, poorly drawn face, mutation, deformed, blurry, dehydrated, bad anatomy, bad proportions, extra limbs, cloned face, disfigured, gross proportions, malformed limbs, missing arms, missing legs, extra arms, extra legs, fused fingers, too many fingers, long neck",
    width=None,
    height=None,
    steps=None,
    model="stable-diffusion-3.5-turbo",
    seed=random.randint(0, 3999999999),
    retries=10,
    backoff_factor=2
):
    # Retrieve the model information
    model_info = AVAILABLE_MODELS.get(model)
    if not model_info:
        logging.error(f"Model '{model}' not found. Using default model.")
        model_info = AVAILABLE_MODELS["stable-diffusion-3.5-turbo"]
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
        
# Define available models and their descriptions
AVAILABLE_MODELS = {
    "stable-diffusion-3.5-turbo": {
        "model_id": "stabilityai/stable-diffusion-3.5-large-turbo",
        "description": "Image generated using Stable Diffusion 3.5 Turbo."
    },
    "FLUX.1-schnell": {
        "model_id": "black-forest-labs/FLUX.1-schnell",
        "description": "Image generated using FLUX.1 [schnell]"
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

MODEL_CHOICES = [
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
    app_commands.Choice(name="Gap_2.6", value="Gap_2.6"),
    app_commands.Choice(name="Reddit", value="Reddit")
]

@app_commands.command(name="imagine", description="Generate an image with AI")
@app_commands.describe(
    prompt="The text prompt for the image.",
    model="Choose AI model to use.",
    negative_prompt="Text to avoid in the image (optional).",
    width="Width of the image in pixels (optional).",
    height="Height of the image in pixels (optional).",
    steps="Number of inference steps (optional).",
    seed="Seed for the image generation (optional)."
)
@app_commands.choices(model=MODEL_CHOICES)
async def imagine_command(
    interaction: discord.Interaction,
    prompt: str,
    model: str = "stable-diffusion-3.5-turbo",
    negative_prompt: Optional[str] = None,  # Changed to Optional
    width: Optional[int] = None,
    height: Optional[int] = None,
    steps: Optional[int] = None,
    seed: Optional[int] = None  # Changed to Optional
):
    await interaction.response.defer()

    # Only pass non-None values
    kwargs = {
        "prompt": prompt,
        "model": model
    }
    
    # Add optional parameters only if they're provided
    if negative_prompt is not None:
        kwargs["negative_prompt"] = negative_prompt
    if width is not None:
        kwargs["width"] = width
    if height is not None:
        kwargs["height"] = height
    if steps is not None:
        kwargs["steps"] = steps
    if seed is not None:
        kwargs["seed"] = seed

    image_data = await generate_image(**kwargs)

    if image_data:
        try:
            image_data.seek(0)
            file = discord.File(fp=image_data, filename="image.png")
            model_description = AVAILABLE_MODELS[model]["description"]
            embed = discord.Embed(
                title=f"Generated Image for: '{prompt}'",
                color=discord.Color.blue(),
                description=model_description
            )
            embed.set_author(
                name=f"Requested by {interaction.user}",
                icon_url=interaction.user.display_avatar.url
            )
            embed.set_footer(
                text=interaction.client.user.name,
                icon_url=interaction.client.user.display_avatar.url
            )
            embed.set_image(url="attachment://image.png")
            await interaction.followup.send(embed=embed, file=file)
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
        # Convert bytes to PIL Image and validate
        with Image.open(io.BytesIO(image_bytes)) as img:
            # Convert to RGB if needed
            if img.mode in ('RGBA', 'LA'):
                img = img.convert('RGB')
            
            # Save as PNG
            png_buffer = io.BytesIO()
            img.save(png_buffer, format='PNG')
            png_bytes = png_buffer.getvalue()
    except Exception as e:
        logging.error(f"Image validation error: {e}")
        return None

    headers = {
        "Authorization": f"Bearer {HF_API_KEY}"
        # Remove Content-Type header to let aiohttp handle it
    }

    # Create form data
    form = aiohttp.FormData()
    form.add_field('image', 
                  png_bytes,
                  filename='image.png',
                  content_type='image/png')
    form.add_field('text', instruction)

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api-inference.huggingface.co/models/timbrooks/instruct-pix2pix",
            headers=headers,
            data=form,
            timeout=120
        ) as response:
            if response.status == 200:
                return io.BytesIO(await response.read())
            else:
                text = await response.text()
                logging.error(f"Error {response.status}: {text}")
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
    try:
        await interaction.response.defer()
        
        if not HF_API_KEY:
            await interaction.followup.send("❌ HuggingFace API key not configured!")
            return
            
        # Generate music
        audio_data = await generate_music(prompt)
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix='.flac', delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name
            
        # Verify file
        if not os.path.exists(tmp_path):
            raise FileNotFoundError(f"File not found: {tmp_path}")
        
        if os.path.getsize(tmp_path) == 0:
            raise ValueError("Empty audio file created")
        
        # Send file in chat
        await interaction.followup.send(
            f"🎵 Generated music for: **{prompt}**",
            file=File(tmp_path, f'{prompt[:200]}.flac')  # Limit filename to 200 chars
        )
        
        # Join voice channel if user is in one
        if interaction.user.voice:
            channel = interaction.user.voice.channel
            
            # Connect to voice
            voice_client = None
            for region in PREFERRED_REGIONS:
                try:
                    await channel.edit(rtc_region=region)
                    if not interaction.guild.voice_client:
                        voice_client = await channel.connect()
                    else:
                        voice_client = interaction.guild.voice_client
                        if voice_client.channel != channel:
                            await voice_client.move_to(channel)
                    await asyncio.sleep(1)
                    break
                except Exception as e:
                    logging.error(f"Voice connection error: {e}")
                    continue

            # Create audio source like TTS
            try:
                source = await discord.FFmpegOpusAudio.from_probe(
                    tmp_path,
                    options='-filter:a volume=2.0'
                )
                
                def after_playing(error):
                    if error:
                        logging.error(f"Playback error: {error}")
                    try:
                        if os.path.exists(tmp_path):
                            os.unlink(tmp_path)
                            logging.info(f"Cleaned up temp file: {tmp_path}")
                    except Exception as e:
                        logging.error(f"Cleanup error: {e}")

                voice_client.play(source, after=after_playing)
                
            except Exception as e:
                logging.error(f"FFmpeg error: {e}")
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                await interaction.followup.send("❌ Failed to play audio", ephemeral=True)
                
    except Exception as e:
        logging.error(f"MusicGen error: {e}")
        await interaction.followup.send(f"❌ Error: {str(e)}")
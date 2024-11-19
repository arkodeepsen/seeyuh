import discord, asyncio, aiohttp, random, httpx, re, json, io, base64
from discord import app_commands
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from PIL import Image
from engine.utils import load_env, get_reddit_access_token, unsplash_env, hf_env
from engine.ai.gemini import code_ai_response, explain_ai_response, ask_ai_response, translate, prompt_ai_response
from engine.ai.gemini_models import (
    pro10creative,
    pro15creative,
    pro15normal,
    flash15normal,
    flash15creative,
    flash158bn,
    flash158bc
)
# Load environment variables
DISCORD_TOKEN, OWNER, url, key = load_env()

# Define the say command
@app_commands.command(name='say', description='Make the bot say something.')
async def say_command(interaction: discord.Interaction, content: str):
    await interaction.response.send_message(content)

@app_commands.command(name='code', description='Get AI generated code for your given prompt.')
async def code_command(interaction: discord.Interaction, prompt: str, language: str = None, framework: str = None):
    await interaction.response.defer()
    # Get AI-generated response
    response = await code_ai_response(prompt, language=language, framework=framework)
    
    # Split the response into multiple messages if it exceeds 2000 characters
    max_length = 2000 - 6  # Deduct 6 characters for the code block delimiters (``` at the end and ``` at the beginning)
    response_parts = [response[i:i + max_length] for i in range(0, len(response), max_length)]

    for i, part in enumerate(response_parts):
        if i == 0:
            await interaction.followup.send(f"{part}```")
        elif i == len(response_parts) - 1:
            await interaction.followup.send(f"```{part}")
        else:
            await interaction.followup.send(f"```{part}```")
            
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
                current_part += '. ' + sentence
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

@app_commands.command(name='poll', description='[MOD ONLY] Usage: /poll "Question" "Option 1, Option 2, Option 3" [duration in minutes]')
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
    app_commands.Choice(name="gemini-1.5-flash8b-exp", value="flash158bc")
]

# Map model values to actual model objects
model_map = {
    "pro10creative": pro10creative,
    "pro15creative": pro15creative,
    "pro15normal": pro15normal,
    "flash15normal": flash15normal,
    "flash15creative": flash15creative,
    "flash158bn": flash158bn,
    "flash158bc": flash158bc
}

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
        print(f"HTTP error: {e}")
    except Exception as e:
        await interaction.followup.send("An unexpected error occurred. Please try again later.")
        print(f"Unexpected error: {e}")
        
# Define the choices for search engines
search_engine_choices = [
    app_commands.Choice(name="Google", value="google"),
    app_commands.Choice(name="Bing", value="bing"),
    app_commands.Choice(name="DuckDuckGo (DEPRECATED)", value="duckduckgo"),
    app_commands.Choice(name="Yahoo (DEPRECATED)", value="yahoo"),
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

@app_commands.command(name="search", description="Search for a query on the web.")
@app_commands.choices(engine=search_engine_choices)
async def search_command(interaction: discord.Interaction, query: str, engine: app_commands.Choice[str] = None, safesearch: bool = True):
    await interaction.response.defer()

    # Force SafeSearch if the channel is not NSFW
    if not interaction.channel.is_nsfw() and not safesearch:
        safesearch = True
        await interaction.followup.send("🔒 SafeSearch is enabled because this channel doesn’t allow NSFW content.")
        
    if engine is None:
        engine = app_commands.Choice(name="Google", value="google")

    # Map engine names to URLs and SafeSearch options
    search_urls = {
        "google": f"https://www.google.com/search?q={query.replace(' ', '+')}" + ("&safe=active" if safesearch else ""),
        "bing": f"https://www.bing.com/search?q={query.replace(' ', '+')}" + ("&adlt=strict" if safesearch else ""),
        "duckduckgo": f"https://duckduckgo.com/?q={query.replace(' ', '+')}" + ("&kp=1" if safesearch else ""),
        "yahoo": f"https://search.yahoo.com/search?p={query.replace(' ', '+')}",
        "ask": f"https://www.ask.com/web?q={query.replace(' ', '+')}"
    }
    search_url = search_urls.get(engine.value)
    
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

            # Parse search results based on the selected engine
            results = extract_search_results(soup, engine.value)

            # Build and send the embed
            embed = discord.Embed(title=f"Search results for '{query}'", color=discord.Color.blue())
            embed.set_thumbnail(url=search_engine_icons[engine.value])
            if results:
                for title, description, source, image in results[:5]:  # Limit to top 5 results
                    embed.add_field(name=title or "No title", value=f"{description or 'No description'}\n*{source}*", inline=False)
                    if image != "No image" and is_valid_url(image):
                        embed.set_image(url=image)
            else:
                embed.description = "No results found."

            embed.set_footer(text=interaction.client.user.name, icon_url=interaction.client.user.avatar.url)
            await interaction.followup.send(embed=embed)

def extract_search_results(soup, engine):
    results = []

    if engine == "google":
        for g in soup.find_all('div', class_='tF2Cxc'):
            title = g.find('h3').text if g.find('h3') else "No title"
            link = g.find('a')['href'] if g.find('a') else "No link"
            description = g.find('div', class_='VwiC3b').text if g.find('div', class_='VwiC3b') else "No description"
            image = g.find('img')['src'] if g.find('img') else "No image"
            
            # Get the source domain name
            domain = urlparse(link).netloc.replace("www.", "")
            source = f"Source: [{domain}]({link})"
            
            results.append((title, description, source, image))

    elif engine == "bing":
        for b in soup.find_all('li', class_='b_algo'):
            title = b.find('h2').text if b.find('h2') else "No title"
            link = b.find('a')['href'] if b.find('a') else "No link"
            description = b.find('p').text if b.find('p') else "No description"
            image = b.find('img')['src'] if b.find('img') else "No image"
            
            domain = urlparse(link).netloc.replace("www.", "")
            source = f"Source: [{domain}]({link})"
            
            results.append((title, description, source, image))

    elif engine == "duckduckgo":
        for d in soup.find_all('div', class_='result'):
            title = d.find('a', class_='result__a').text if d.find('a', class_='result__a') else "No title"
            link = d.find('a', class_='result__a')['href'] if d.find('a', class_='result__a') else "No link"
            description = d.find('div', class_='result__snippet').text if d.find('div', class_='result__snippet') else "No description"
            image = d.find('img')['src'] if d.find('img') else "No image"
            
            domain = urlparse(link).netloc.replace("www.", "")
            source = f"Source: [{domain}]({link})"
            
            results.append((title, description, source, image))

    elif engine == "yahoo":
        for y in soup.find_all('div', class_='dd algo'):
            title = y.find('h3').text if y.find('h3') else "No title"
            link = y.find('a')['href'] if y.find('a') else "No link"
            description = y.find('p').text if y.find('p') else "No description"
            image = y.find('img')['src'] if y.find('img') else "No image"
            
            domain = urlparse(link).netloc.replace("www.", "")
            source = f"Source: [{domain}]({link})"
            
            results.append((title, description, source, image))

    elif engine == "ask":
        for a in soup.find_all('div', class_='PartialSearchResults-item'):
            title = a.find('h2').text if a.find('h2') else "No title"
            link = a.find('a')['href'] if a.find('a') else "No link"
            description = a.find('p').text if a.find('p') else "No description"
            image = a.find('img')['src'] if a.find('img') else "No image"
            
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
                    print(f"No images found for query: {query}")
                    return None, None, None
                elif resp.status == 403:
                    print("Access Forbidden: Check your Unsplash Access Key and permissions.")
                    return None, None, None
                elif resp.status == 429:
                    print("Rate limit exceeded: Too many requests to Unsplash API.")
                    return None, None, None
                else:
                    print(f"Error fetching image: {resp.status}")
                    return None, None, None
        except asyncio.TimeoutError:
            print("Request timed out while contacting Unsplash API.")
            return None, None, None
        except Exception as e:
            print(f"Exception during Unsplash image search: {e}")
            return None, None, None

@app_commands.command(name="image", description="Search for an image using Unsplash")
@app_commands.choices(orientation=[
    app_commands.Choice(name="Landscape", value="landscape"),
    app_commands.Choice(name="Portrait", value="portrait"),
    app_commands.Choice(name="Squarish", value="squarish")
])
async def image_command(interaction: discord.Interaction, query: str, orientation: app_commands.Choice[str]):

    await interaction.response.defer()  # Defer response to show the bot is working

    image_url, photographer, photo_link = await unsplash_image_search(query, orientation.value)

    if image_url:
        embed = discord.Embed(
            title=f"Image result for '{query}'",
            description=f"Photo by [{photographer}]({photo_link}) on [Unsplash](https://unsplash.com/)",
            color=discord.Color.blue()
        )
        embed.set_image(url=image_url)
        embed.set_footer(
            text=interaction.client.user.name,
            icon_url=interaction.client.user.display_avatar.url
        )
        await interaction.followup.send(embed=embed)
    else:
        await interaction.followup.send("Sorry, I couldn't find any images for that query.")
                
# Hugging Face API Key
HF_API_KEY = hf_env()
if not HF_API_KEY:
    print("Hugging Face API Key not found. Please set HF_API_KEY in your environment variables.")
    
async def generate_image(
    prompt,
    negative_prompt="(deformed iris, deformed pupils, semi-realistic, cgi, 3d, render, sketch, cartoon, drawing, anime:1.4), text, close up, cropped, out of frame, worst quality, low quality, jpeg artifacts, ugly, duplicate, morbid, mutilated, extra fingers, mutated hands, poorly drawn hands, poorly drawn face, mutation, deformed, blurry, dehydrated, bad anatomy, bad proportions, extra limbs, cloned face, disfigured, gross proportions, malformed limbs, missing arms, missing legs, extra arms, extra legs, fused fingers, too many fingers, long neck",
    width=None,
    height=None,
    steps=None,
    model="stable-diffusion-3.5-turbo",
    seed=random.randint(0, 3999999999),
    retries=3,
    backoff_factor=2
):
    # Retrieve the model information
    model_info = AVAILABLE_MODELS.get(model)
    if not model_info:
        print(f"Model '{model}' not found. Using default model.")
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
                        print(f"Image generated successfully for prompt: '{prompt}' using model: '{model}'")
                        return io.BytesIO(image_data)
                    else:
                        text = await response.text()
                        print(f"Error: {response.status}, Response: {text}")
                        if response.status in [429, 500, 502, 503, 504]:
                            raise aiohttp.ClientError(f"Server error: {response.status}")
                        return None
        except (asyncio.TimeoutError, aiohttp.ClientError) as e:
            print(f"Attempt {attempt} failed with error: {e}")
            if attempt == retries:
                print("All retry attempts failed.")
                return None
            await asyncio.sleep(backoff_factor ** attempt)
        except Exception as e:
            print(f"Unexpected exception during image generation: {e}")
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
        "model_id": "pimpilikipilapi1/NSFW_master",
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
    app_commands.Choice(name="FLUX Master", value="FLUX_master"),
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
    negative_prompt: str = "(deformed iris, deformed pupils, semi-realistic, cgi, 3d, render, sketch, cartoon, drawing, anime:1.4), text, close up, cropped, out of frame, worst quality, low quality, jpeg artifacts, ugly, duplicate, morbid, mutilated, extra fingers, mutated hands, poorly drawn hands, poorly drawn face, mutation, deformed, blurry, dehydrated, bad anatomy, bad proportions, extra limbs, cloned face, disfigured, gross proportions, malformed limbs, missing arms, missing legs, extra arms, extra legs, fused fingers, too many fingers, long neck",
    width: int = None,
    height: int = None,
    steps: int = None,
    seed: int = random.randint(0, 3999999999)
):
    await interaction.response.defer()  # Show processing indicator

    image_data = await generate_image(
        prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        steps=steps,
        model=model,
        seed=seed
    )

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
            print(f"Error sending image to Discord: {e}")
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
            "https://api-inference.huggingface.co/models/nlpconnect/vit-gpt2-image-captioning",
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
                    print("No caption generated.")
            else:
                text = await response.text()
                print(f"Error: {response.status}, Response: {text}")
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
        print(f"Error: {e}")
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
                print(f"Error: {response.status}, Response: {text}")
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
        print(f"Error: {e}")
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
        print(f"Image validation error: {e}")
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
                print(f"Error: {response.status}, Response: {text}")
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
        print(f"Error: {e}")
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
        print(f"Image validation error: {e}")
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
                print(f"Error {response.status}: {text}")
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
        print(f"Error: {e}")
        await interaction.followup.send(
            "An error occurred while processing your request."
        )
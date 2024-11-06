import discord, asyncio, aiohttp, random, httpx
from discord import app_commands
from bs4 import BeautifulSoup
from engine.utils import load_env, get_reddit_access_token
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
        if len(current_part) + len(sentence) + 2 <= max_length:  # +2 for the '. ' or '\n'
            current_part += sentence + '. '
        else:
            response_parts.append(current_part.strip())
            current_part = sentence + '. '

    if current_part:
        response_parts.append(current_part.strip())

    for part in response_parts:
        await interaction.followup.send(part)

@app_commands.command(name='ask', description='Get a short, straightforward and concise single-line response to your question.')
async def ask_command(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    # Get AI-generated response
    response = await ask_ai_response(prompt)
    
    # Split the response into multiple messages if it exceeds 2000 characters
    max_length = 2000
    response_parts = []
    current_part = ""

    for sentence in response.split('. '):
        if len(current_part) + len(sentence) + 2 <= max_length:  # +2 for the '. ' or '\n'
            current_part += sentence + '. '
        else:
            response_parts.append(current_part.strip())
            current_part = sentence + '. '

    if current_part:
        response_parts.append(current_part.strip())

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

    # Split the response into multiple messages if it exceeds 2000 characters
    max_length = 2000
    response_parts = []
    current_part = ""

    for sentence in response.split('. '):
        if len(current_part) + len(sentence) + 2 <= max_length:  # +2 for the '. ' or '\n'
            current_part += sentence + '. '
        else:
            response_parts.append(current_part.strip())
            current_part = sentence + '. '

    if current_part:
        response_parts.append(current_part.strip())

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
async def reddit_command(interaction: discord.Interaction, subreddit: str, sort: app_commands.Choice[str] = "hot", nsfw: bool = False):
    await interaction.response.defer()

    # Enforce NSFW block if the channel is not NSFW
    if not interaction.channel.is_nsfw() and nsfw:
        nsfw = False
        await interaction.followup.send("🔒 NSFW content is blocked in this channel as it does not allow NSFW content.")

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

        # Create and send the embed with the meme
        embed = discord.Embed(title=random_post["title"], color=discord.Color.random())
        embed.set_image(url=random_post["url"])
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
    app_commands.Choice(name="DuckDuckGo", value="duckduckgo"),
    app_commands.Choice(name="Yahoo", value="yahoo"),
    app_commands.Choice(name="Ask.com", value="ask")
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
async def search_command(interaction: discord.Interaction, query: str, engine: app_commands.Choice[str], safesearch: bool = True):
    await interaction.response.defer()

    # Force SafeSearch if the channel is not NSFW
    if not interaction.channel.is_nsfw() and not safesearch:
        safesearch = True
        await interaction.followup.send("🔒 SafeSearch is enabled because this channel doesn’t allow NSFW content.")

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
                for title, link, description in results[:5]:  # Limit to top 5 results
                    embed.add_field(name=title or "No title", value=f"{description or 'No description'}\n[Link]({link})", inline=False)
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
            description = g.find('span', class_='aCOpRe').text if g.find('span', class_='aCOpRe') else "No description"
            results.append((title, link, description))
    elif engine == "bing":
        for b in soup.find_all('li', class_='b_algo'):
            title = b.find('h2').text if b.find('h2') else "No title"
            link = b.find('a')['href'] if b.find('a') else "No link"
            description = b.find('p').text if b.find('p') else "No description"
            results.append((title, link, description))
    elif engine == "duckduckgo":
        for d in soup.find_all('div', class_='result__body'):
            title = d.find('h2').text if d.find('h2') else "No title"
            link = d.find('a')['href'] if d.find('a') else "No link"
            description = d.find('a', class_='result__snippet').text if d.find('a', class_='result__snippet') else "No description"
            results.append((title, link, description))
    elif engine == "yahoo":
        for y in soup.find_all('div', class_='dd algo algo-sr Sr'):
            title = y.find('h3').text if y.find('h3') else "No title"
            link = y.find('a')['href'] if y.find('a') else "No link"
            description = y.find('p').text if y.find('p') else "No description"
            results.append((title, link, description))
    elif engine == "ask":
        for a in soup.find_all('div', class_='PartialSearchResults-item'):
            title = a.find('h2').text if a.find('h2') else "No title"
            link = a.find('a')['href'] if a.find('a') else "No link"
            description = a.find('p').text if a.find('p') else "No description"
            results.append((title, link, description))

    return results

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
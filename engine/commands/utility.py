import discord, asyncio, aiohttp, random, httpx
from discord import app_commands
from typing import List
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
        if len(current_part) + len(sentence) + 1 <= max_length:
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
    response_parts = [response[i:i + max_length] for i in range(0, len(response), max_length)]

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

@app_commands.command(name='translate', description='Translate text to a specified language.')
async def translate_command(interaction: discord.Interaction, text: str, source_language: str, target_language: str):
    await interaction.response.defer()
    prompt = f"Translate '{text}' from {source_language} to {target_language}"
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
async def prompt_command(interaction: discord.Interaction, model: app_commands.Choice[str], prompt: str):
    await interaction.response.defer()
    selected_model = model_map[model.value]
    response = await prompt_ai_response(prompt, selected_model)  # Await the coroutine
    await interaction.followup.send(response)

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

@app_commands.command(name="reddit", description="Get a random post from subreddit of your choice.")
@app_commands.choices(sort=sort_choices)
async def reddit_command(interaction: discord.Interaction, subreddit: str, sort: app_commands.Choice[str] = "hot"):
    await interaction.response.defer()

    access_token = await get_reddit_access_token()
    url = f"https://oauth.reddit.com/r/{subreddit}/{sort.value}.json?limit=50"  # Note the OAuth URL
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
        random_post = random.choice(posts)["data"]

        # Create and send the embed with the meme
        embed = discord.Embed(title=random_post["title"], color=discord.Color.random())
        embed.set_image(url=random_post["url"])
        embed.set_footer(text=f"👍 {random_post['score']} | 💬 {random_post['num_comments']} comments", icon_url=interaction.client.user.avatar.url)

        await interaction.followup.send(embed=embed)

    except httpx.HTTPStatusError as e:
        await interaction.followup.send("There was an error fetching posts from Reddit. Please try again later.")
        print(f"HTTP error: {e}")
    except Exception as e:
        await interaction.followup.send("An unexpected error occurred. Please try again later.")
        print(f"Unexpected error: {e}")

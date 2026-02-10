import discord, requests, asyncio, os, re, aiohttp, random
from discord import app_commands
from typing import Optional
from bs4 import BeautifulSoup
from supabase import Client, create_client
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Initialize Supabase client (ensure this matches your bot.py initialization)
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Get the Steam API key from environment variables
STEAM_API_KEY = os.getenv('STEAM_API_KEY')

# Define the 'steam' command as a regular command
@app_commands.command(name='steam', description='Lookup your or others Steam profiles.')
@app_commands.describe(
    user='Mention a user to lookup their Steam profile.',
    steam_input='Provide your Steam ID or profile URL to lookup.'
)
async def steam(interaction: discord.Interaction, user: discord.User = None, steam_input: str = None):
    await interaction.response.defer(ephemeral=False)

    if steam_input:
        # Case 1: Steam ID or URL provided to lookup
        steam_id = extract_steam_id(steam_input)
        if not steam_id:
            await interaction.followup.send("❌ Invalid Steam ID or profile URL provided.", ephemeral=True)
            return

        steam_data = get_steam_data(steam_id)
        if steam_data:
            embed = create_steam_embed(steam_data)
            await interaction.followup.send(embed=embed, ephemeral=False)
        else:
            await interaction.followup.send(
                "⚠️ Could not retrieve Steam details. Ensure the Steam ID is correct and the profile is public.",
                ephemeral=True
            )
        return

    if user:
        # Case 2: Lookup another user's Steam profile
        cached = supabase.table('steam_cache').select('*').eq('user_id', str(user.id)).execute()
        if cached.data:
            steam_data = cached.data[0]['steam_data']
            embed = create_steam_embed(steam_data)
            await interaction.followup.send(
                f"🕹️ **Steam Profile for {user.name}**", embed=embed, ephemeral=False
            )
        else:
            await interaction.followup.send(
                f"⚠️ {user.mention} has not linked their Steam account.", ephemeral=False
            )
        return

    # Case 3: Lookup own Steam profile
    user_id_str = str(interaction.user.id)
    cached = supabase.table('steam_cache').select('*').eq('user_id', user_id_str).execute()
    if cached.data:
        steam_data = cached.data[0]['steam_data']
        embed = create_steam_embed(steam_data)
        await interaction.followup.send("🕹️ **Your Steam Profile**", embed=embed, ephemeral=False)
    else:
        # Prompt user to link their Steam account
        await interaction.followup.send(
            f"{interaction.user.mention}, you have not linked your Steam account. Use `/steamlink` to link your Steam account.",
            ephemeral=True
        )

@app_commands.command(name='steamunlink', description='Unlink your Steam account from your Discord account.')
async def steamunlink(interaction: discord.Interaction):
    user = interaction.user
    await interaction.response.defer(ephemeral=True)

    try:
        # Check if the user has linked their Steam account
        cached = supabase.table('steam_cache').select('*').eq('user_id', str(user.id)).execute()
        if not cached.data:
            await interaction.followup.send("❌ You have not linked your Steam account.", ephemeral=True)
            return

        # Unlink the Steam account
        supabase.table('steam_cache').delete().eq('user_id', str(user.id)).execute()
        await interaction.followup.send("✅ Steam account unlinked successfully.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)

# Define the 'steamlink' command
@app_commands.command(name='steamlink', description='Link your Steam account to your Discord account.')
async def steamlink(interaction: discord.Interaction):
    user = interaction.user
    await interaction.response.defer(ephemeral=True)

    # Check if the user has already linked their Steam account
    cached = supabase.table('steam_cache').select('*').eq('user_id', str(user.id)).execute()
    if cached.data:
        await interaction.followup.send("✅ You have already linked your Steam account.", ephemeral=True)
        return

    # Prompt user for Steam ID or Vanity URL
    await interaction.followup.send(f"{user.mention}, please provide your Steam ID or profile URL.", ephemeral=True)

    def check(m):
        return m.author == user and m.channel == interaction.channel

    try:
        msg = await interaction.client.wait_for('message', check=check, timeout=60)
        await msg.delete()  # Delete the user's message after reading
        steam_input = msg.content
        steam_id = extract_steam_id(steam_input)
        if not steam_id:
            await interaction.followup.send("❌ Invalid Steam ID or profile URL provided.", ephemeral=True)
            return

        steam_data = get_steam_data(steam_id)
        if steam_data:
            # Cache the result in Supabase
            supabase.table('steam_cache').upsert({
                'user_id': str(user.id),
                'steam_id': steam_id,
                'steam_data': steam_data
            }).execute()
            embed = create_steam_embed(steam_data)
            await interaction.followup.send("✅ Steam account linked successfully!", embed=embed, ephemeral=True)
        else:
            await interaction.followup.send("⚠️ Could not retrieve Steam details. Ensure your profile is public and the Steam ID is correct.", ephemeral=True)
    except asyncio.TimeoutError:
        await interaction.followup.send("⏰ You took too long to respond. Please try the command again.", ephemeral=True)
    except requests.exceptions.RequestException:
        await interaction.followup.send("⚠️ An error occurred while connecting to the Steam API.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"⚠️ An unexpected error occurred: {e}", ephemeral=True)

# Helper functions (extract_steam_id, resolve_vanity_url, get_steam_data, create_steam_embed, get_persona_state)
def extract_steam_id(input_str):
    """Extract Steam ID from input string using regex."""
    input_str = input_str.strip()
    patterns = [
        r'https?://steamcommunity\.com/id/([a-zA-Z0-9_-]+)',
        r'https?://steamcommunity\.com/profiles/(\d+)',
        r'^([a-zA-Z0-9_-]+)$',  # Vanity ID
        r'^(\d+)$'               # Steam64 ID
    ]
    for pattern in patterns:
        match = re.match(pattern, input_str)
        if match:
            return match.group(1)
    return None

def resolve_vanity_url(vanity_url):
    """Resolve a vanity URL to a Steam ID."""
    api_url = "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/"
    params = {
        'key': STEAM_API_KEY,
        'vanityurl': vanity_url
    }
    response = requests.get(api_url, params=params)
    data = response.json()
    if data.get('response', {}).get('success') == 1:
        return data['response']['steamid']
    return None

def get_steam_data(steam_id):
    """Retrieve Steam user data."""
    if not steam_id.isdigit():
        steam_id = resolve_vanity_url(steam_id)
        if not steam_id:
            return None

    api_url = "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/"
    params = {
        'key': STEAM_API_KEY,
        'steamids': steam_id
    }
    response = requests.get(api_url, params=params)
    data = response.json()
    if data.get('response', {}).get('players'):
        return data['response']['players'][0]
    return None

def create_steam_embed(steam_data):
    """Create a Discord embed with Steam user data."""
    embed = discord.Embed(
        title=steam_data.get('personaname', 'Unknown'),
        url=steam_data.get('profileurl'),
        description="🕹️ **Steam Profile Information**",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=steam_data.get('avatarfull'))
    embed.add_field(name="🏷️ Real Name", value=steam_data.get('realname', 'N/A'), inline=True)
    embed.add_field(name="🔄 Status", value=get_persona_state(steam_data.get('personastate')), inline=True)
    embed.add_field(name="🌍 Country", value=steam_data.get('loccountrycode', 'N/A'), inline=True)
    embed.set_footer(text="Steam API • Powered by discord.py", icon_url="https://media.discordapp.net/attachments/533926025747234838/1309933897315913830/steam.png")
    return embed

def get_persona_state(state_code):
    """Convert persona state code to string."""
    states = {
        0: "🛑 Offline",
        1: "🟢 Online",
        2: "🔴 Busy",
        3: "🟡 Away",
        4: "🟣 Snooze",
        5: "⚙️ Looking to Trade",
        6: "🎮 Looking to Play"
    }
    return states.get(state_code, "❓ Unknown")

@app_commands.command(name='steamgame', description='Lookup a game on Steam.')
@app_commands.describe(game='The name of the game to lookup.')
async def steamgame(interaction: discord.Interaction, game: str):
    """Lookup a game on Steam."""
    game = game.lower()
    await interaction.response.defer(ephemeral=False)
    
    api_url = "https://api.steampowered.com/ISteamApps/GetAppList/v2/"
    response = requests.get(api_url)
    data = response.json()
    apps = data['applist']['apps']
    
    app_id = None
    for app in apps:
        if game in app['name'].lower():
            app_id = app['appid']
            break
    
    if app_id is None:
        await interaction.followup.send("❌ Game not found.", ephemeral=True)
        return
    
    api_url = f"https://store.steampowered.com/api/appdetails?appids={app_id}"
    response = requests.get(api_url)
    data = response.json()
    
    if not data[str(app_id)]['success']:
        await interaction.followup.send("❌ Failed to retrieve game details.", ephemeral=True)
        return
    
    app_data = data[str(app_id)]['data']
    # Clean the detailed description using BeautifulSoup
    raw_description = app_data.get('detailed_description', 'No description available.')
    soup = BeautifulSoup(raw_description, 'html.parser')
    clean_description = soup.get_text(separator='\n')

    # Truncate the description if it's too long
    if len(clean_description) > 2048:
        clean_description = clean_description[:2045] + '...'

    embed = discord.Embed(
        title=app_data['name'],
        description=clean_description,
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=app_data.get('header_image', ''))
    embed.add_field(name="📊 Price", value=app_data.get('price_overview', {}).get('final_formatted', 'Free'), inline=True)
    embed.add_field(name="📊 Release Date", value=app_data.get('release_date', {}).get('date', 'Unknown'), inline=True)
    embed.add_field(name="📊 Developer", value=', '.join(app_data.get('developers', ['Unknown'])), inline=True)
    embed.add_field(name="📊 Publisher", value=', '.join(app_data.get('publishers', ['Unknown'])), inline=True)
    embed.add_field(
        name="📊 Genre",
        value=', '.join(genre['description'] for genre in app_data.get('genres', [{'description': 'Unknown'}])),
        inline=True
    )
    tags = app_data.get('tags', [])
    if tags:
        embed.add_field(
            name="📊 Tags",
            value=', '.join(tags),
            inline=True
        )
    embed.set_footer(text="Steam API • Powered by discord.py", icon_url="https://media.discordapp.net/attachments/533926025747234838/1309933897315913830/steam.png")
    
    await interaction.followup.send(embed=embed)
    
@app_commands.command(name='steamnews', description='Get the latest news for a game on Steam.')
@app_commands.describe(game='The name of the game to get news for.')
async def steamnews(interaction: discord.Interaction, game: str):
    """Get the latest news for a game on Steam."""
    game = game.lower()
    await interaction.response.defer(ephemeral=False)
    
    # Get the app list from Steam
    api_url = "https://api.steampowered.com/ISteamApps/GetAppList/v2/"
    response = requests.get(api_url)
    if response.status_code != 200:
        await interaction.followup.send("❌ Failed to retrieve app list from Steam.", ephemeral=True)
        return
    data = response.json()
    apps = data['applist']['apps']
    
    # Find the app ID and name
    app_id = None
    app_name = None
    for app in apps:
        if game in app['name'].lower():
            app_id = app['appid']
            app_name = app['name']
            break
    
    if app_id is None:
        await interaction.followup.send("❌ Game not found.", ephemeral=True)
        return
    
    # Get the news for the app
    api_url = f"https://api.steampowered.com/ISteamNews/GetNewsForApp/v0002/?appid={app_id}&count=5&maxlength=300&format=json"
    response = requests.get(api_url)
    if response.status_code != 200:
        await interaction.followup.send("❌ Failed to retrieve news from Steam.", ephemeral=True)
        return
    data = response.json()
    
    # Check if 'appnews' and 'newsitems' exist in the response
    if 'appnews' not in data or not data['appnews'].get('newsitems'):
        await interaction.followup.send("❌ No news available for this game.", ephemeral=True)
        return
    
    news_items = data['appnews']['newsitems']
    if not news_items:
        await interaction.followup.send("❌ No news available for this game.", ephemeral=True)
        return

    # Create the embed
    embed = discord.Embed(title=f"📰 Latest News for {app_name}", color=discord.Color.blue())
    for news in news_items:
        # Clean the contents
        raw_contents = news.get('contents', '')
        soup = BeautifulSoup(raw_contents, 'html.parser')
        clean_contents = soup.get_text(separator='\n')
        # Truncate if necessary
        if len(clean_contents) > 1024:
            clean_contents = clean_contents[:1021] + '...'
        embed.add_field(name=news['title'], value=f"{clean_contents}\n[Read more]({news['url']})", inline=False)
    
    embed.set_footer(text="Steam API • Powered by discord.py", icon_url="https://media.discordapp.net/attachments/533926025747234838/1309933897315913830/steam.png")
    await interaction.followup.send(embed=embed)

@app_commands.command(name='leaderboard', description='Get the top seeyuh users.')
@app_commands.describe(scope='Choose the leaderboard scope.')
@app_commands.choices(scope=[
    app_commands.Choice(name='Global', value='global'),
    app_commands.Choice(name='Server', value='server')
])
async def leaderboard(interaction: discord.Interaction, scope: str):
    # Automatically set scope to 'global' if used in DM
    if interaction.guild is None:
        scope = 'global'
    
    await interaction.response.defer(ephemeral=False)

    # Prepare parameters for the RPC call
    if scope == 'global':
        params = {'in_scope': 'global'}
        title = "🌐 Global Leaderboard"
    else:
        guild_id = str(interaction.guild.id)
        params = {'in_scope': 'server', 'in_guild_id': guild_id}
        title = f"📊 Server Leaderboard for {interaction.guild.name}"

    # Call the 'get_leaderboard' function
    response = supabase.rpc('get_leaderboard', params).execute()

    leaderboard_data = response.data

    if not leaderboard_data:
        await interaction.followup.send("⚠️ No data available for the selected scope.", ephemeral=False)
        return

    # Fetch Discord user objects concurrently
    async def fetch_user(user_id):
        try:
            user = await interaction.client.fetch_user(int(user_id))
            return user
        except (discord.NotFound, discord.HTTPException):
            return None

    users = await asyncio.gather(*[fetch_user(entry['user_id']) for entry in leaderboard_data])

    # Build leaderboard entries
    leaderboard_entries = []
    for idx, (entry, user) in enumerate(zip(leaderboard_data, users), start=1):
        username = user.name if user else f"User ID {entry['user_id']}"
        message_count = entry['message_count']
        leaderboard_entries.append(f"**{idx}. {username}** - {message_count} messages")

    # Create embed
    embed = discord.Embed(
        title=title,
        description="\n".join(leaderboard_entries),
        color=discord.Color.green()
    )
    if users and users[0]:
        embed.set_thumbnail(url=interaction.guild.icon.url if scope == 'server' else users[0].display_avatar.url)
    embed.set_footer(text="Leaderboard • Powered by Supabase", icon_url=interaction.client.user.display_avatar.url)

    await interaction.followup.send(embed=embed, ephemeral=False)

@app_commands.command(name='rank', description="Get your rank or someone else's rank.")
@app_commands.describe(user="The user to check the rank for (optional).")
async def rank(interaction: discord.Interaction, user: Optional[discord.Member] = None):
    await interaction.response.defer(ephemeral=False)
    
    # Use the provided user or default to the command invoker
    target_user = user or interaction.user
    user_id = str(target_user.id)
    guild_id = str(interaction.guild.id) if interaction.guild else None

    # Prepare parameters for the RPC call
    params = {'p_user_id': user_id}
    if guild_id:
        params['p_guild_id'] = guild_id

    # Call the 'get_rank' function
    try:
        response = supabase.rpc('get_rank', params).execute()
    except Exception as e:
        await interaction.followup.send(f"⚠️ An error occurred while fetching the rank: {e}", ephemeral=True)
        return

    rank_data = response.data

    if not rank_data:
        await interaction.followup.send("⚠️ No rank data available.", ephemeral=False)
        return

    rank_info = rank_data[0]  # Assuming the function returns a single row

    global_message_count = rank_info.get('global_message_count', 0)
    global_rank = rank_info.get('global_rank', 0)
    server_message_count = rank_info.get('server_message_count', 0) if guild_id else 0
    server_rank = rank_info.get('server_rank', 0) if guild_id else 0

    # Fetch user avatar
    avatar_url = target_user.display_avatar.replace(size=256).url

    async with aiohttp.ClientSession() as session:
        async with session.get(avatar_url) as resp:
            if resp.status != 200:
                await interaction.followup.send("⚠️ Failed to fetch the avatar.", ephemeral=True)
                return
            avatar_bytes = await resp.read()

    # Open avatar image
    avatar = Image.open(BytesIO(avatar_bytes)).convert("RGBA")
    avatar = avatar.resize((180, 180))

    # Create base image
    base_width, base_height = 800, 300
    img = Image.new('RGBA', (base_width, base_height), color=(255, 255, 255, 0))

    # Create background with random colors and glass effect
    background_color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255), 200)
    background = Image.new('RGBA', img.size, color=background_color)
    background = background.filter(ImageFilter.GaussianBlur(radius=10))
    img.paste(background, (0, 0))

    # Add random gradient overlay
    gradient = Image.new('L', (1, base_height), color=0xFF)
    for y in range(base_height):
        gradient.putpixel((0, y), int(255 * (1 - y / base_height)))
    gradient = gradient.resize(img.size)
    img.putalpha(gradient)

    # Add random decorative elements
    draw = ImageDraw.Draw(img)
    for _ in range(5):
        shape = random.choice(['circle', 'square'])
        size = random.randint(20, 50)
        position = (random.randint(0, base_width - size), random.randint(0, base_height - size))
        color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255), 128)
        if shape == 'circle':
            draw.ellipse([position, (position[0] + size, position[1] + size)], fill=color)
        else:
            draw.rectangle([position, (position[0] + size, position[1] + size)], fill=color)

    # Create rounded corners
    radius = 25
    mask = Image.new('L', img.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([(0, 0), img.size], radius=radius, fill=255)
    img.putalpha(mask)

    # Paste avatar with circular mask
    avatar_mask = Image.new('L', avatar.size, 0)
    avatar_draw = ImageDraw.Draw(avatar_mask)
    avatar_draw.ellipse([(0, 0), avatar.size], fill=255)
    avatar.putalpha(avatar_mask)
    img.paste(avatar, (50, 60), avatar)

    # Load and paste badge icon if available
    if global_rank <= 10:
        badge_mapping = {
            1: 'assets/badges/gold_badge.png',
            2: 'assets/badges/silver_badge.png',
            3: 'assets/badges/bronze_badge.png',
        }
        badge_path = badge_mapping.get(global_rank, 'assets/badges/top10_badge.png')
        try:
            badge = Image.open(badge_path).convert("RGBA")
            badge = badge.resize((80, 80))
            img.paste(badge, (700, 20), badge)
        except Exception as e:
            print(f"Error loading badge: {e}")

    # Load fonts
    try:
        font_large = ImageFont.truetype("assets/fonts/arial.ttf", 40)  
        font_medium = ImageFont.truetype("assets/fonts/arial.ttf", 20)
    except:
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()

    # Function to draw text with shadow
    def draw_text_with_shadow(draw, position, text, font, text_color, shadow_color):
        x, y = position
        # Draw shadow with larger offset
        draw.text((x + 4, y + 4), text, font=font, fill=shadow_color)  # Increased from 2 to 4
        # Draw main text
        draw.text((x, y), text, font=font, fill=text_color)

    draw = ImageDraw.Draw(img)

    # Text colors
    text_color = (255, 255, 255)
    shadow_color = (0, 0, 0, 128)

    # Update the user_name variable
    user_name = f"{target_user.name}#{target_user.discriminator}"
    draw_text_with_shadow(draw, (260, 50), user_name, font_large, text_color, shadow_color)

    # Global Rank and Messages
    draw_text_with_shadow(draw, (260, 120), f"Global Rank: {global_rank}", font_medium, text_color, shadow_color)
    draw_text_with_shadow(draw, (260, 160), f"Global Messages: {global_message_count}", font_medium, text_color, shadow_color)

    # Server Rank and Messages
    if guild_id:
        draw_text_with_shadow(draw, (260, 200), f"Server Rank: {server_rank}", font_medium, text_color, shadow_color)
        draw_text_with_shadow(draw, (260, 240), f"Server Messages: {server_message_count}", font_medium, text_color, shadow_color)
    else:
        draw_text_with_shadow(draw, (260, 200), "Server Rank: N/A", font_medium, text_color, shadow_color)

    # Save image to BytesIO and send
    with BytesIO() as image_binary:
        img.save(image_binary, 'PNG')
        image_binary.seek(0)
        file = discord.File(fp=image_binary, filename='rank.png')
        await interaction.followup.send(file=file)
        
@app_commands.command(name='itunes', description="Search the iTunes Store's catalog of music, movies, TV shows, podcasts, and audiobooks.")
@app_commands.describe(
    term='The search term or keyword(s) you want to search for.',
    media='The type of media you want to search for (e.g. music, movie, tvShow, podcast, audiobook).',
    entity='The type of entity you want to search for (e.g. album, song, movie, tvSeason, podcast, audiobook).',
    attribute='The attribute you want to search for (e.g. actorTerm, genreIndex, languageTerm).',
    limit='The maximum number of results to return.'
)
@app_commands.choices(
    media=[
        app_commands.Choice(name='Music', value='music'),
        app_commands.Choice(name='Movie', value='movie'),
        app_commands.Choice(name='TV Show', value='tvShow'),
        app_commands.Choice(name='Podcast', value='podcast'),
        app_commands.Choice(name='Audiobook', value='audiobook')
    ],
    entity=[
        app_commands.Choice(name='Album', value='album'),
        app_commands.Choice(name='Song', value='song'),
        app_commands.Choice(name='Movie', value='movie'),
        app_commands.Choice(name='TV Season', value='tvSeason'),
        app_commands.Choice(name='Podcast', value='podcast'),
        app_commands.Choice(name='Audiobook', value='audiobook')
    ]
)
async def itunes(interaction: discord.Interaction, term: str, media: str, entity: str, attribute: str = None, limit: int = 5):
    """Search the iTunes Store's catalog."""
    await interaction.response.defer(ephemeral=False)

    params = {
        'term': term,
        'limit': limit,
        'media': media,
        'entity': entity,
        'attribute': attribute
    }

    api_url = "https://itunes.apple.com/search"
    async with aiohttp.ClientSession() as session:
        async with session.get(api_url, params=params) as response:
            if response.status != 200:
                await interaction.followup.send("❌ Failed to retrieve data from iTunes.", ephemeral=True)
                return
            data = await response.json()
    results = data.get('results', [])
    if not results:
        await interaction.followup.send("❌ No results found.", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"iTunes Search Results for '{term}'",
        color=discord.Color.blue()
    )

    for result in results:
        name = result.get('trackName') or result.get('collectionName') or result.get('artistName')
        kind = result.get('kind') or result.get('collectionType') or result.get('wrapperType')
        url = result.get('trackViewUrl') or result.get('collectionViewUrl') or result.get('artistViewUrl')
        embed.add_field(name=f"{name} ({kind})", value=f"[View on iTunes]({url})", inline=False)

    await interaction.followup.send(embed=embed)
    
@app_commands.command(name='cat', description='Get a random cat image.')
async def cat(interaction: discord.Interaction):
    """Get a random cat image."""
    await interaction.response.defer(ephemeral=False)
    async with aiohttp.ClientSession() as session:
        async with session.get('https://cataas.com/cat') as resp:
            if resp.status != 200:
                await interaction.followup.send("❌ Failed to fetch cat image.", ephemeral=True)
                return
            image_data = await resp.read()
            file = discord.File(BytesIO(image_data), filename="cat.png")
            await interaction.followup.send(file=file)

@app_commands.command(name='dog', description='Get a random dog image.')
@app_commands.describe(breed='Optional breed of the dog.')
async def dog(interaction: discord.Interaction, breed: str = None):
    """Get a random dog image."""
    await interaction.response.defer(ephemeral=False)
    url = f'https://dog.ceo/api/breed/{breed}/images/random' if breed else 'https://dog.ceo/api/breeds/image/random'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                await interaction.followup.send("❌ Failed to fetch dog image.", ephemeral=True)
                return
            data = await resp.json()
            if data['status'] == 'success':
                await interaction.followup.send(data['message'])
            else:
                await interaction.followup.send("❌ Failed to fetch dog image.", ephemeral=True)
            
@app_commands.command(name='dogfact', description='Get a random dog fact.')
async def dogfact(interaction: discord.Interaction):
    """Get a random dog fact."""
    await interaction.response.defer(ephemeral=False)
    async with aiohttp.ClientSession() as session:
        async with session.get('https://dog-api.kinduff.com/api/facts') as resp:
            if resp.status != 200:
                await interaction.followup.send("❌ Failed to fetch dog fact.", ephemeral=True)
                return
            data = await resp.json()
            if data['success']:
                await interaction.followup.send(data['facts'][0])
            else:
                await interaction.followup.send("❌ Failed to fetch dog fact.", ephemeral=True)

@app_commands.command(name='donate', description='Get the donation link for the bot.')
async def donate(interaction: discord.Interaction):
    """Get the donation link for the bot."""
    await interaction.response.defer(ephemeral=False)
    await interaction.followup.send("🎉 **Support the bot development by donating here:** https://paypal.me/arkodeepsen") 
               
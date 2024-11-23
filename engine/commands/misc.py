import discord, requests, asyncio, os, re
from discord import app_commands
from discord.ext import commands
from supabase import Client, create_client

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

    # Determine query based on scope
    if scope == 'global':
        query = supabase.table('messages') \
            .select('user_id') \
            .count('user_id', alias='message_count') \
            .group('user_id') \
            .order('message_count', desc=True) \
            .limit(10) \
            .execute()
        title = "🌐 Global Leaderboard"
    else:
        guild_id = str(interaction.guild.id)
        query = supabase.table('messages') \
            .select('user_id') \
            .count('user_id', alias='message_count') \
            .eq('guild_id', guild_id) \
            .group('user_id') \
            .order('message_count', desc=True) \
            .limit(10) \
            .execute()
        title = f"📊 Server Leaderboard for {interaction.guild.name}"

    if not query.data:
        await interaction.followup.send("⚠️ No data available for the selected scope.", ephemeral=False)
        return

    leaderboard_data = query.data

    # Fetch Discord user objects concurrently
    async def fetch_user(user_id):
        try:
            user = await interaction.client.fetch_user(int(user_id))
            return user
        except discord.NotFound:
            return None

    users = await asyncio.gather(*[fetch_user(entry['user_id']) for entry in leaderboard_data])

    # Build leaderboard entries
    leaderboard_entries = []
    for idx, (entry, user) in enumerate(zip(leaderboard_data, users), start=1):
        username = user.name if user else f"User ID {entry['user_id']}"
        leaderboard_entries.append(f"**{idx}. {username}** - {entry['message_count']} messages")

    # Create embed
    embed = discord.Embed(
        title=title,
        description="\n".join(leaderboard_entries),
        color=discord.Color.green()
    )
    embed.set_footer(text="Leaderboard • Powered by Supabase", icon_url=interaction.client.user.display_avatar.url)

    await interaction.followup.send(embed=embed, ephemeral=False)
    
@app_commands.command(name='rank', description='Get your seeyuh rank.')
async def rank(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    
    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id) if interaction.guild else None
    
    # Fetch global message count
    global_count_response = supabase.table('messages') \
        .select('user_id') \
        .eq('user_id', user_id) \
        .count() \
        .execute()
    global_message_count = global_count_response.count if global_count_response.status_code == 200 else 0
    
    # Fetch server message count
    if guild_id:
        server_count_response = supabase.table('messages') \
            .select('user_id') \
            .eq('guild_id', guild_id) \
            .eq('user_id', user_id) \
            .count() \
            .execute()
        server_message_count = server_count_response.count if server_count_response.status_code == 200 else 0
    else:
        server_message_count = 0
    
    # Calculate global rank
    global_rank_response = supabase.table('messages') \
        .select('user_id, count') \
        .group('user_id') \
        .execute()
    
    if global_rank_response.status_code == 200:
        sorted_global = sorted(
            [item for item in global_rank_response.data],
            key=lambda x: x['count'],
            reverse=True
        )
        global_rank = next((index + 1 for index, item in enumerate(sorted_global) if item['user_id'] == user_id), None)
    else:
        global_rank = None
    
    # Calculate server rank
    if guild_id:
        server_rank_response = supabase.table('messages') \
            .select('user_id, count') \
            .eq('guild_id', guild_id) \
            .group('user_id') \
            .execute()
        
        if server_rank_response.status_code == 200:
            sorted_server = sorted(
                [item for item in server_rank_response.data],
                key=lambda x: x['count'],
                reverse=True
            )
            server_rank = next((index + 1 for index, item in enumerate(sorted_server) if item['user_id'] == user_id), None)
        else:
            server_rank = None
    else:
        server_rank = 'N/A'
    
    # Create rank image
    from PIL import Image, ImageDraw, ImageFont
    import aiohttp
    from io import BytesIO

    # Fetch user avatar
    avatar_url = interaction.user.display_avatar.url
    
    async with aiohttp.ClientSession() as session:
        async with session.get(avatar_url) as resp:
            avatar_bytes = await resp.read()
    avatar = Image.open(BytesIO(avatar_bytes)).convert("RGBA")
    avatar = avatar.resize((100, 100))
    
    # Create base image
    img = Image.new('RGB', (400, 200), color=(54,57,63))
    draw = ImageDraw.Draw(img)
    
    # Load font
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()
    
    # Paste avatar
    img.paste(avatar, (20, 50), avatar)
    
    # Write text
    draw.text((140, 50), f"Username: {interaction.user.name}", font=font, fill=(255,255,255))
    draw.text((140, 80), f"Global Rank: {global_rank if global_rank else 'N/A'}", font=font, fill=(255,255,255))
    draw.text((140, 110), f"Global Messages: {global_message_count}", font=font, fill=(255,255,255))
    if guild_id:
        draw.text((140, 140), f"Server Rank: {server_rank if server_rank else 'N/A'}", font=font, fill=(255,255,255))
        draw.text((140, 170), f"Server Messages: {server_message_count}", font=font, fill=(255,255,255))
    else:
        draw.text((140, 140), f"Server Rank: N/A", font=font, fill=(255,255,255))
    
    # Save image to BytesIO
    with BytesIO() as image_binary:
        img.save(image_binary, 'PNG')
        image_binary.seek(0)
        file = discord.File(fp=image_binary, filename='rank.png')
        await interaction.followup.send(file=file)
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

# Define the 'steam' slash command
@app_commands.command(name='steam', description='Get Steam details of yourself or another user.')
@app_commands.describe(member='Select a member or leave blank to select yourself')
async def steam(interaction: discord.Interaction, member: discord.Member = None, bot: commands.Bot = None):
    user = member or interaction.user
    await interaction.response.defer(ephemeral=False)

    # Check cache in Supabase
    cached = supabase.table('steam_cache').select('*').eq('discord_id', str(user.id)).execute()
    if cached.data:
        steam_data = cached.data[0]['steam_data']
    else:
        # Prompt user for Steam ID or Vanity URL
        await interaction.followup.send(f"{user.mention}, please provide your Steam ID or profile URL.")

        def check(m):
            return m.author == user and m.channel == interaction.channel

        try:
            msg = await interaction.client.wait_for('message', check=check, timeout=60)
            steam_id = extract_steam_id(msg.content)
            if not steam_id:
                await interaction.followup.send("❌ Invalid Steam ID or profile URL provided.", ephemeral=True)
                return

            steam_data = get_steam_data(steam_id)
            if steam_data:
                # Cache the result in Supabase
                supabase.table('steam_cache').upsert({
                    'discord_id': str(user.id),
                    'steam_id': steam_id,
                    'steam_data': steam_data
                }).execute()
            else:
                await interaction.followup.send("⚠️ Could not retrieve Steam details. Ensure your profile is public and the Steam ID is correct.", ephemeral=True)
                return
        except asyncio.TimeoutError:
            await interaction.followup.send("⏰ You took too long to respond. Please try the command again.", ephemeral=True)
            return
        except requests.exceptions.RequestException:
            await interaction.followup.send("⚠️ An error occurred while connecting to the Steam API.", ephemeral=True)
            return
        except Exception:
            await interaction.followup.send("⚠️ An unexpected error occurred. Please try again.", ephemeral=True)
            return

    embed = create_steam_embed(steam_data)
    await interaction.followup.send(embed=embed, ephemeral=False)

def extract_steam_id(input_str):
    """Extract Steam ID from input string using regex."""
    input_str = input_str.strip()
    # Regex patterns
    patterns = [
        r'https?://steamcommunity\.com/id/([a-zA-Z0-9_-]+)',
        r'https?://steamcommunity\.com/profiles/(\d+)',
        r'^([a-zA-Z0-9_-]+)$',
        r'^(\d+)$'
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
    embed.set_footer(text="Steam API • Powered by discord.py", icon_url="https://steamstore-a.akamaihd.net/public/shared/images/header/logo_steam.svg")
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
    embed.set_footer(text="Leaderboard • Powered by Supabase")

    await interaction.followup.send(embed=embed, ephemeral=False)
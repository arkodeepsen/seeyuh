import discord, requests, asyncio, os
from discord import app_commands

# Get the Steam API key from environment variables
STEAM_API_KEY = os.getenv('STEAM_API_KEY')

# Define the 'steam' slash command
@app_commands.command(name='steam', description='Get Steam details of yourself or another user.')
@app_commands.describe(member='Select a member or leave blank to select yourself')
async def steam(interaction: discord.Interaction, member: discord.Member = None):
    user = member or interaction.user

    # Attempt to retrieve Steam ID from Discord connections
    steam_id = None
    if member:
        # If a member is mentioned, attempt to fetch their Steam connection
        try:
            connections = await member.fetch_connections()
            for connection in connections:
                if connection.type == 'steam':
                    steam_id = connection.id  # Steam64 ID
                    break
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to access this user's connections. Please provide a Steam ID or profile URL instead.",
                ephemeral=True
            )
            return
    else:
        # If no member is mentioned, attempt to fetch the invoking user's Steam connection
        try:
            connections = await interaction.user.fetch_connections()
            for connection in connections:
                if connection.type == 'steam':
                    steam_id = connection.id  # Steam64 ID
                    break
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to access your connections. Please provide your Steam ID or profile URL.",
                ephemeral=True
            )
            return

    if steam_id:
        # Steam ID found via connections
        steam_data = get_steam_data(steam_id)
        if steam_data:
            embed = create_steam_embed(steam_data)
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        else:
            await interaction.response.send_message(
                "Could not retrieve Steam details. Please ensure your profile is public and the Steam ID is correct.",
                ephemeral=True
            )
            return

    # If Steam ID not found via connections, prompt for Steam ID or profile URL
    await interaction.response.send_message(
        f"{user.mention}, please provide your Steam ID or profile URL.",
        ephemeral=True
    )

    # Wait for the user's response
    def check(m):
        return m.author == user and m.channel == interaction.channel

    try:
        # Wait for a message from the user
        msg = await interaction.client.wait_for('message', check=check, timeout=60)
        steam_id = extract_steam_id(msg.content)
        if not steam_id:
            await interaction.followup.send("Invalid Steam ID or profile URL provided.", ephemeral=True)
            return

        steam_data = get_steam_data(steam_id)
        if steam_data:
            embed = create_steam_embed(steam_data)
            await interaction.followup.send(embed=embed, ephemeral=False)
        else:
            await interaction.followup.send(
                "Could not retrieve Steam details. Please ensure your profile is public and the Steam ID is correct.",
                ephemeral=True
            )
    except asyncio.TimeoutError:
        await interaction.followup.send(
            "You took too long to respond. Please try the command again.",
            ephemeral=True
        )
    except requests.exceptions.RequestException:
        await interaction.followup.send(
            "An error occurred while connecting to the Steam API.",
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(
            "An error occurred. Please try again.",
            ephemeral=True
        )

def extract_steam_id(input_str):
    """Extract Steam ID from input string."""
    input_str = input_str.strip()
    if input_str.isdigit():
        return input_str  # Steam64 ID

    # Check for profile URL
    if 'steamcommunity.com/id/' in input_str:
        try:
            vanity_url = input_str.split('steamcommunity.com/id/')[1].split('/')[0]
            return resolve_vanity_url(vanity_url)
        except IndexError:
            return None
    elif 'steamcommunity.com/profiles/' in input_str:
        try:
            return input_str.split('steamcommunity.com/profiles/')[1].split('/')[0]
        except IndexError:
            return None

    return None

def resolve_vanity_url(vanity_url):
    """Resolve a custom URL to a Steam ID."""
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
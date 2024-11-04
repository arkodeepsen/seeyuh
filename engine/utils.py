import os
from dotenv import load_dotenv
import discord
import time
import asyncio

def load_env():
    load_dotenv()  # Load environment variables from a .env file
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
    OWNER = os.getenv('OWNER_ID')
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    return DISCORD_TOKEN, OWNER, url, key

def reddit_env():
    load_dotenv()  # Load environment variables from a .env file
    client_id = os.getenv('REDDIT_CLIENT_ID')
    client_secret = os.getenv('REDDIT_CLIENT_SECRET')
    user_agent = os.getenv('REDDIT_USER_AGENT')
    return client_id, client_secret, user_agent

def giphy_env():
    load_dotenv()  # Load environment variables from a .env file
    GIPHY_API_KEY = os.getenv('GIPHY_API_KEY')
    return GIPHY_API_KEY

def intents():
    # Define the bot with intents
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True                # Receive guild-related events
    intents.members = True                # Receive member-related events
    intents.bans = True                   # Receive ban-related events
    intents.emojis = True                 # Receive emoji-related events
    intents.integrations = True           # Receive integration-related events
    intents.webhooks = True               # Receive webhook-related events
    intents.voice_states = True           # Receive voice state updates
    intents.presences = True              # Receive presence updates (online, offline, etc.)
    intents.messages = True                # Receive message-related events
    intents.guild_messages = True         # Receive guild message events
    intents.dm_messages = True             # Receive direct message events
    intents.reactions = True               # Receive reaction events
    intents.guild_reactions = True        # Receive guild reaction events
    return intents

async def update_presence(bot):
    custom_emoji = discord.PartialEmoji(name="seeyuh", id=1302628356147122207)  # Define the PartialEmoji with the emoji ID
    while True:
        unique_users = len(bot.users)  # Get the current number of unique users and guilds
        guild_count = len(bot.guilds)
        status = discord.CustomActivity(name="/help")  # Define the CustomActivity with the updated user count
        # Set the bot's activity with updated user count
        activity = discord.Activity(
            type=discord.ActivityType.listening,
            name=f"{unique_users} users across {guild_count} servers! 😉"  # Updated text
        )
        await bot.change_presence(
            status=discord.Status.idle,
            activity=activity
        )

        # Wait a few minutes before updating again (e.g., 5 minutes)
        await asyncio.sleep(300)
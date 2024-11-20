'''
import discord
from discord import app_commands
import aiohttp
import os
from supabase import create_client, Client

# Initialize Supabase client
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

PERSPECTIVE_API_KEY = os.getenv('PERSPECTIVE_API_KEY')

# Moderation commands

# Toggle Perspective API automoderation
@app_commands.command(name="toggle_perspective", description="Toggle Perspective API automoderation.")
@app_commands.checks.has_permissions(administrator=True)
async def toggle_perspective(interaction: discord.Interaction):
    guild_id = interaction.guild_id
    # Fetch current settings
    response = supabase.table('server_settings').select('*').eq('guild_id', guild_id).execute()
    data = response.data
    if data:
        settings = data[0]
        new_status = not settings['perspective_enabled']
        # Update settings
        supabase.table('server_settings').update({'perspective_enabled': new_status}).eq('guild_id', guild_id).execute()
    else:
        new_status = True
        # Insert new settings
        supabase.table('server_settings').insert({'guild_id': guild_id, 'perspective_enabled': new_status, 'blocked_words': []}).execute()
    status_text = "enabled" if new_status else "disabled"
    await interaction.response.send_message(f"Perspective API automoderation is now {status_text}.", ephemeral=True)

# Add blocked word
@app_commands.command(name="add_blocked_word", description="Add a word to block.")
@app_commands.describe(
    word="The word to block."
)
@app_commands.checks.has_permissions(administrator=True)
async def add_blocked_word(interaction: discord.Interaction, word: str):
    guild_id = interaction.guild_id
    response = supabase.table('server_settings').select('*').eq('guild_id', guild_id).execute()
    data = response.data
    if data:
        settings = data[0]
        blocked_words = settings.get('blocked_words', [])
        if word.lower() not in blocked_words:
            blocked_words.append(word.lower())
            # Update settings
            supabase.table('server_settings').update({'blocked_words': blocked_words}).eq('guild_id', guild_id).execute()
            await interaction.response.send_message(f"Added '{word}' to the list of blocked words.", ephemeral=True)
        else:
            await interaction.response.send_message(f"'{word}' is already in the list of blocked words.", ephemeral=True)
    else:
        # Insert new settings
        supabase.table('server_settings').insert({'guild_id': guild_id, 'perspective_enabled': False, 'blocked_words': [word.lower()]}).execute()
        await interaction.response.send_message(f"Added '{word}' to the list of blocked words.", ephemeral=True)

# Remove blocked word
@app_commands.command(name="remove_blocked_word", description="Remove a blocked word.")
@app_commands.describe(
    word="The word to remove."
)
@app_commands.checks.has_permissions(administrator=True)
async def remove_blocked_word(interaction: discord.Interaction, word: str):
    guild_id = interaction.guild_id
    response = supabase.table('server_settings').select('*').eq('guild_id', guild_id).execute()
    data = response.data
    if data:
        settings = data[0]
        blocked_words = settings.get('blocked_words', [])
        if word.lower() in blocked_words:
            blocked_words.remove(word.lower())
            # Update settings
            supabase.table('server_settings').update({'blocked_words': blocked_words}).eq('guild_id', guild_id).execute()
            await interaction.response.send_message(f"Removed '{word}' from the list of blocked words.", ephemeral=True)
        else:
            await interaction.response.send_message(f"'{word}' is not in the list of blocked words.", ephemeral=True)
    else:
        await interaction.response.send_message(f"No blocked words are set for this server.", ephemeral=True)

# List blocked words
@app_commands.command(name="list_blocked_words", description="List the blocked words.")
@app_commands.checks.has_permissions(administrator=True)
async def list_blocked_words(interaction: discord.Interaction):
    guild_id = interaction.guild_id
    response = supabase.table('server_settings').select('blocked_words').eq('guild_id', guild_id).execute()
    data = response.data
    if data:
        blocked_words = data[0].get('blocked_words', [])
        if blocked_words:
            words = ', '.join(blocked_words)
            await interaction.response.send_message(f"Blocked words: {words}", ephemeral=True)
        else:
            await interaction.response.send_message("There are no blocked words set.", ephemeral=True)
    else:
        await interaction.response.send_message("There are no blocked words set.", ephemeral=True)

# Moderation actions and message handling

# Event listener for automoderation
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    guild_id = message.guild.id
    response = supabase.table('server_settings').select('*').eq('guild_id', guild_id).execute()
    data = response.data
    blocked = False

    if data:
        settings = data[0]
        # Check for custom blocked words
        for word in settings.get('blocked_words', []):
            if word in message.content.lower():
                blocked = True
                reason = "Used a blocked word."
                break
        # Check with Perspective API if enabled and not already blocked
        if not blocked and settings.get('perspective_enabled', False):
            flagged = await check_message_content(message.content)
            if flagged:
                blocked = True
                reason = "Inappropriate content detected."

    if blocked:
        try:
            await message.delete()
            await message.channel.send(
                f"{message.author.mention}, your message was removed: {reason}",
                delete_after=5
            )
        except discord.Forbidden:
            pass
    else:
        await bot.process_commands(message)

async def check_message_content(content):
    try:
        url = f"https://commentanalyzer.googleapis.com/v1alpha1/comments:analyze?key={PERSPECTIVE_API_KEY}"
        payload = {
            "comment": {"text": content},
            "languages": ["en"],
            "requestedAttributes": {
                "TOXICITY": {},
                "SEVERE_TOXICITY": {},
                "IDENTITY_ATTACK": {},
                "INSULT": {},
                "PROFANITY": {},
                "THREAT": {},
            },
            "doNotStore": True,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    thresholds = {
                        "TOXICITY": 0.7,
                        "SEVERE_TOXICITY": 0.7,
                        "IDENTITY_ATTACK": 0.7,
                        "INSULT": 0.7,
                        "PROFANITY": 0.7,
                        "THREAT": 0.7,
                    }
                    for attr, threshold in thresholds.items():
                        score = result["attributeScores"][attr]["summaryScore"]["value"]
                        if score >= threshold:
                            return True
                else:
                    print(f"Perspective API error: {response.status}, {await response.text()}")
    except Exception as e:
        print(f"Error checking content moderation: {e}")
    return False
'''
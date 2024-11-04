import discord
from discord import app_commands
import time
from engine.utils import load_env
# Load environment variables
DISCORD_TOKEN, OWNER, url, key = load_env()

# Define the say command
@app_commands.command(name='say', description='Make the bot say something.')
async def say_command(interaction: discord.Interaction, content: str):
    await interaction.response.send_message(content)

# Define the emoji command
@app_commands.command(name='emoji', description='Get a random emoji from seeyuh custom emojis.')
async def emoji_command(interaction: discord.Interaction):
    await interaction.response.send_message("<:seeyuh:1302628356147122207>")
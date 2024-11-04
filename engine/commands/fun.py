import discord
from discord import app_commands
import time
from engine.ai.gemini import slash_ai_response
from engine.utils import load_env
# Load environment variables
DISCORD_TOKEN, OWNER, url, key = load_env()

# Define the roast command
@app_commands.command(name="roast", description="Roast a user in a light-hearted way!")
async def roast_command(interaction: discord.Interaction, user: discord.User):
    # Check if the bot is mentioned
    if user == interaction.client.user:
        await interaction.response.send_message("I can't roast myself! Try roasting someone else. 😅")
        return

    # Acknowledge the interaction immediately to prevent timeouts
    await interaction.response.defer()

    # Create a roast prompt specifically targeting the user
    roast_prompt = f"Roast {user.name} in a funny, light-hearted, and slang style. Make it playful and not too harsh."

    # Get the AI response for the roast
    response = await slash_ai_response(roast_prompt)
    
    # Send the roast as a reply after deferring
    await interaction.followup.send(f"{response}")
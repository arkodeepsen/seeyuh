import discord
from discord import app_commands
from typing import List
from engine.utils import load_env
from engine.ai.gemini import code_ai_response, explain_ai_response, ask_ai_response
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
    response_parts = [response[i:i + max_length] for i in range(0, len(response), max_length)]

    for part in response_parts:
        await interaction.followup.send(part)

@app_commands.command(name='ask', description='Get a short, straightforward and concise response to your question.')
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
@app_commands.command(name='emoji', description='Get a random emoji from seeyuh custom emojis.')
async def emoji_command(interaction: discord.Interaction):
    await interaction.response.send_message("<:seeyuh:1302628356147122207>")

@app_commands.command(name='avatar', description='Get the avatar of a user.')
async def avatar_command(interaction: discord.Interaction, user: discord.User = None):
    if user is None:
        user = interaction.user
    await interaction.response.send_message(user.display_avatar.url)

@app_commands.command(name='poll', description='[MOD ONLY] Create a poll. Usage: /poll "Question" "Option 1, Option 2, Option 3"')
async def poll_command(interaction: discord.Interaction, question: str, options: str):
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

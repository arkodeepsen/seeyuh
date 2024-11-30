import discord
from discord import app_commands
from discord.ext import commands
import aiohttp

# Kick command
@app_commands.command(name="kick", description="Kick a member from the server.")
@app_commands.describe(
    member="The member to kick.",
    reason="Reason for kicking the member."
)
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    await member.kick(reason=reason)
    await interaction.response.send_message(f"{member} has been kicked.", ephemeral=True)

# Ban command
@app_commands.command(name="ban", description="Ban a member from the server.")
@app_commands.describe(
    member="The member to ban.",
    reason="Reason for banning the member."
)
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    await member.ban(reason=reason)
    await interaction.response.send_message(f"{member} has been banned.", ephemeral=True)

# Mute command
@app_commands.command(name="mute", description="Mute a member.")
@app_commands.describe(
    member="The member to mute.",
    reason="Reason for muting the member."
)
@app_commands.checks.has_permissions(moderate_members=True)
async def mute(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    mute_role = discord.utils.get(interaction.guild.roles, name="Muted")
    if not mute_role:
        mute_role = await interaction.guild.create_role(name="Muted")
        for channel in interaction.guild.channels:
            await channel.set_permissions(mute_role, send_messages=False, speak=False)
    await member.add_roles(mute_role, reason=reason)
    await interaction.response.send_message(f"{member} has been muted.", ephemeral=True)

# Unmute command
@app_commands.command(name="unmute", description="Unmute a member.")
@app_commands.describe(
    member="The member to unmute."
)
@app_commands.checks.has_permissions(moderate_members=True)
async def unmute(interaction: discord.Interaction, member: discord.Member):
    mute_role = discord.utils.get(interaction.guild.roles, name="Muted")
    await member.remove_roles(mute_role)
    await interaction.response.send_message(f"{member} has been unmuted.", ephemeral=True)

# Warn command
@app_commands.command(name="warn", description="Warn a member.")
@app_commands.describe(
    member="The member to warn.",
    reason="Reason for warning the member."
)
@app_commands.checks.has_permissions(moderate_members=True)
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    # Implement your warning system (e.g., log to a database)
    await interaction.response.send_message(f"{member} has been warned.", ephemeral=True)

# Purge command
@app_commands.command(name="purge", description="Delete multiple messages.")
@app_commands.describe(
    amount="Number of messages to delete."
)
@app_commands.checks.has_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, amount: int):
    await interaction.response.defer(ephemeral=True)  # Defer the response
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"Deleted {len(deleted)} messages.", ephemeral=True)

# Timeout command
@app_commands.command(name="timeout", description="Timeout a member.")
@app_commands.describe(
    member="The member to timeout.",
    minutes="Duration in minutes.",
    reason="Reason for timeout."
)
@app_commands.checks.has_permissions(moderate_members=True)
async def timeout(interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = None):
    duration = discord.utils.utcnow() + discord.timedelta(minutes=minutes)
    await member.timeout(duration, reason=reason)
    await interaction.response.send_message(f"{member} has been timed out for {minutes} minutes.", ephemeral=True)

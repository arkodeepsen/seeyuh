import discord
from discord import app_commands
import time
from engine.utils import load_env
# Load environment variables
DISCORD_TOKEN, OWNER, url, key = load_env()

# Define the help command
@app_commands.command(name='help', description='List of available commands.')
async def help_command(interaction: discord.Interaction):
    description = "\n".join([f"`/{command.name}` - {command.description}" for command in interaction.client.tree.get_commands()])
    embed = discord.Embed(
        title="Help Command",
        description=description,
        color=discord.Color.blue()
    )
    embed.set_footer(text=f"{interaction.client.user.name}", icon_url=interaction.client.user.avatar.url)
    await interaction.response.send_message(embed=embed)

# Define the ping command
@app_commands.command(name='ping', description='Check if the bot is responsive.')
async def ping_command(interaction: discord.Interaction):
    start_time = time.time()

    # Send the initial response and capture the message
    embed = discord.Embed(
        title="Ping Command",
        description="Pong! Calculating ping...",
        color=discord.Color.orange()
    )
    embed.set_footer(text=f"{interaction.client.user.name}", icon_url=interaction.client.user.avatar.url)
    await interaction.response.send_message(embed=embed)

    # Calculate the ping
    latency = round(interaction.client.latency * 1000)  # Convert to milliseconds
    end_time = time.time()
    ping = round((end_time - start_time) * 1000)  # Convert to milliseconds

    embed = discord.Embed(
        title="Ping Command",
        description=f"Pong! Bot ping is {ping} ms. Discord API latency is {latency} ms.",
        color=discord.Color.green()
    )
    embed.set_footer(text=f"{interaction.client.user.name}", icon_url=interaction.client.user.avatar.url)

    # Instead of trying to edit, use followup to send the updated message
    message = await interaction.original_response()
    await message.edit(embed=embed)

# Define the info command
@app_commands.command(name='info', description='Get information about the bot or a user.')
async def info_command(interaction: discord.Interaction, user: discord.User = None):
    embed = discord.Embed(color=discord.Color.blue())
    
    if user is None:
        owner = await interaction.client.fetch_user(OWNER)  # Fetch the bot owner
        embed.title = f"Bot {interaction.client.user.name}#{interaction.client.user.discriminator} Information"
        embed.description = (
            f"**Version:** 1.0\n"
            f"**Description:** A Discord bot for moderation, entertainment, music, games, and AI responses.\n"
            f"**Prefix:** `/`\n"
            f"**Up since:** {time.ctime(interaction.client.uptime)}\n"
            f"**Commands:** {' '.join([f'`/{command.name}` ' for command in interaction.client.tree.get_commands()])}\n"
            f"**Owner:** [{owner.name}](https://discord.com/users/{owner.id})\n"
            f"**Currently serving:** {len(interaction.client.guilds)} servers\n"
            f"**Invite:** [Click here](https://discord.com/oauth2/authorize?client_id={interaction.client.user.id}&permissions=8&scope=bot%20applications.commands)\n"
            f"**Support:** [GitHub](https://github.com/arkodeepsen)\n"
            f"For more information, use `/info @user` to get user details."
        )
        embed.set_thumbnail(url=interaction.client.user.avatar.url)
        embed.set_footer(text=f"Bot {interaction.client.user.name} developed by {owner.name}", icon_url=owner.avatar.url)
    else:
        # Fetch the member object for the user in the guild
        member = interaction.guild.get_member(user.id)
        
        # If member is None, attempt to fetch it
        if member is None:
            try:
                member = await interaction.guild.fetch_member(user.id)
            except discord.NotFound:
                member = None  # If still None, handle gracefully

        embed.title = f"User Information for {user.name}"
        embed.set_thumbnail(url=user.avatar.url)
        
        # Check if member is None and provide appropriate details
        if member:
            # Check for activity
            if member.activity:  # Check if there is any activity
                if isinstance(member.activity, discord.Game):
                    activity_status = f"Playing {member.activity.name}"
                elif isinstance(member.activity, discord.Streaming):
                    activity_status = f"Streaming {member.activity.name}"
                elif isinstance(member.activity, discord.Activity):
                    activity_status = f"{member.activity.name}"  # General case
                else:
                    activity_status = 'Unknown Activity'
            else:
                activity_status = 'None'

            # Check for presence status
            if member.status == discord.Status.online:
                presence_status = 'Online'
            elif member.status == discord.Status.idle:
                presence_status = 'Idle'
            elif member.status == discord.Status.dnd:
                presence_status = 'Do Not Disturb'
            elif member.status == discord.Status.offline:
                presence_status = 'Offline'
            elif member.status == discord.Status.streaming:
                presence_status = 'Streaming'
            elif member.status == discord.Status.mobile:
                presence_status = 'Mobile'
            else:
                presence_status = 'Unknown Status'
            joined_date = member.joined_at.strftime('%Y-%m-%d %H:%M:%S') if member.joined_at else 'N/A'
            roles = ', '.join([role.name for role in member.roles]) if member.roles else 'None'
            top_role = member.top_role.name if member.top_role else 'None'
        else:
            activity_status = 'N/A'
            joined_date = 'N/A'
            roles = 'N/A'
            top_role = 'N/A'
        
        embed.description = (
            f"**User:** {user.name}#{user.discriminator}\n"
            f"**Display Name:** {user.display_name}\n"
            f"**Activity Status:** {activity_status}\n"
            f"**Presence Status:** {presence_status}\n"
            f"**ID:** {user.id}\n"
            f"**Joined:** {joined_date}\n"
            f"**Roles:** {roles}\n"
            f"**Top Role:** {top_role}\n"
            f"**Created:** {user.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"**Bot:** {'Yes' if user.bot else 'No'}\n"
        )
        embed.set_footer(text=f"{interaction.client.user.name}", icon_url=interaction.client.user.avatar.url)
    await interaction.response.send_message(embed=embed)

# Define the serverinfo command
@app_commands.command(name='serverinfo', description='Get information about the server.')
async def serverinfo_command(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=f"Server Information for {guild.name}", color=discord.Color.green())
    embed.add_field(name="Server ID", value=guild.id, inline=True)
    embed.add_field(name="Total Members", value=guild.member_count, inline=True)
    embed.add_field(name="Created On", value=guild.created_at.strftime('%Y-%m-%d %H:%M:%S'), inline=True)
    embed.set_thumbnail(url=guild.icon.url)
    embed.set_footer(text=f"{interaction.client.user.name}", icon_url=interaction.client.user.avatar.url)
    await interaction.response.send_message(embed=embed)
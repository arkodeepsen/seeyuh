import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import time
from ai import get_ai_response

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
OWNER = os.getenv('OWNER_ID')

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

# Create the bot instance with the specified intents
bot = commands.Bot(command_prefix='/', intents=intents)

# Load slash commands
@bot.event
async def on_ready():
    bot.uptime = time.time()
    print(f'Logged in as {bot.user}')
    # Sync commands with Discord
    await bot.tree.sync()

# Slash commands
@bot.tree.command(name='help', description='List of available commands.')
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Help Command",
        description="Available commands: `/help`, `/ping`, `/info`, `/serverinfo`",
        color=discord.Color.blue()
    )
    embed.set_footer(text=f"{bot.user.name}", icon_url=bot.user.avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='ping', description='Check if the bot is responsive.')
async def ping_command(interaction: discord.Interaction):
    start_time = time.time()
    await interaction.response.send_message("Pong! Calculating ping...")
    end_time = time.time()
    ping = round((end_time - start_time) * 1000)  # Convert to milliseconds
    embed = discord.Embed(
        title="Ping Command",
        description=f"Pong! Bot ping is {ping} ms.",
        color=discord.Color.green()
    )
    embed.set_footer(text=f"{bot.user.name}", icon_url=bot.user.avatar.url)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name='info', description='Get information about the bot or a user.')
async def info_command(interaction: discord.Interaction, user: discord.User = None):
    embed = discord.Embed(color=discord.Color.blue())
    
    if user is None:
        owner = await bot.fetch_user(OWNER)  # Fetch the bot owner
        embed.title = f"Bot {bot.user.name}#{bot.user.discriminator} Information"
        embed.description = (
            f"**Version:** 1.0\n"
            f"**Description:** A Discord bot for moderation, entertainment, music, games, and AI responses.\n"
            f"**Prefix:** `/`\n"
            f"**Up since:** {time.ctime(bot.uptime)}\n"
            f"**Commands:** `/help`, `/ping`, `/info`\n"
            f"**Owner:** [{owner.name}](https://discord.com/users/{owner.id})\n"
            f"**Currently serving:** {len(bot.guilds)} servers\n"
            f"**Invite:** [Click here](https://discord.com/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands)\n"
            f"**Support:** [GitHub](https://github.com/arkodeepsen)\n"
            f"For more information, use `/info @user` to get user details."
        )
        embed.set_thumbnail(url=bot.user.avatar.url)
        embed.set_footer(text=f"Bot {bot.user.name} developed by {owner.name}", icon_url=owner.avatar.url)
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
        embed.set_footer(text=f"{bot.user.name}", icon_url=bot.user.avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='serverinfo', description='Get information about the server.')
async def serverinfo_command(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=f"Server Information for {guild.name}", color=discord.Color.green())
    embed.add_field(name="Server ID", value=guild.id, inline=True)
    embed.add_field(name="Total Members", value=guild.member_count, inline=True)
    embed.add_field(name="Created On", value=guild.created_at.strftime('%Y-%m-%d %H:%M:%S'), inline=True)
    embed.set_thumbnail(url=guild.icon.url)
    embed.set_footer(text=f"{bot.user.name}", icon_url=bot.user.avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if bot.user.mentioned_in(message):
        content = message.content.strip()
        command_content = content.replace(f"<@!{bot.user.id}>", "").strip()
        words = command_content.split()

        # Check if there are more than two words
        if len(words) > 2:
            # Treat the message as an AI query
            response = await get_ai_response(command_content)
            await message.channel.send(response)
        else:
            command_found = False
            for word in words:
                # Check if the command exists
                command = bot.tree.get_command(word)
                if command:
                    command_found = True
                    
                    # Create a mock interaction object
                    class MockInteraction:
                        def __init__(self, channel):
                            self.channel = channel

                        async def response(self):
                            pass  # Not used for this context

                        async def send_message(self, content):
                            await self.channel.send(content)

                        async def followup(self, content):
                            await self.channel.send(content)

                        # Simulating the `interaction.response` object
                        class Response:
                            def __init__(self, channel):
                                self.channel = channel

                            async def send_message(self, embed=None, content=None):
                                if embed:
                                    await self.channel.send(embed=embed)
                                else:
                                    await self.channel.send(content)

                        @property
                        def response(self):
                            return self.Response(self.channel)

                    mock_interaction = MockInteraction(message.channel)

                    # Call the command callback with the mock interaction
                    await command.callback(mock_interaction)
                    break
            
            if not command_found:
                # If no command was found, treat it as an AI query
                response = await get_ai_response(command_content)
                await message.channel.send(response)

    await bot.process_commands(message)

# Run the bot
bot.run(DISCORD_TOKEN)

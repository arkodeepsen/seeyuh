import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import time
from ai import get_ai_response, slash_ai_response
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base

# Set up the database
Base = declarative_base()

class Guild(Base):
    __tablename__ = 'guilds'

    id = Column(Integer, primary_key=True)
    guild_id = Column(String, unique=True)
    guild_name = Column(String)

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    user_id = Column(String, unique=True)
    username = Column(String)
    discriminator = Column(String)
    guild_id = Column(String, ForeignKey('guilds.guild_id'))

class Message(Base):
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True)
    content = Column(String)
    user_id = Column(String, ForeignKey('users.user_id'))
    guild_id = Column(String, ForeignKey('guilds.guild_id'))
    response = Column(String)

# Create the SQLite database
DATABASE_URL = "sqlite:///bot_messages.db"
engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)

# Create a session
Session = sessionmaker(bind=engine)
session = Session()

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
            f"**Support:** [GitHub](https://github.com/arkodeepsen/seeyuh.git)\n"
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

@bot.tree.command(name="roast", description="Roast a user in a light-hearted way!")
async def roast_command(interaction: discord.Interaction, user: discord.User):
    # Acknowledge the interaction immediately to prevent timeouts
    await interaction.response.defer()

    # Create a roast prompt specifically targeting the user
    roast_prompt = f"Roast {user.display_name} in a funny, light-hearted, and slang style. Make it playful and not too harsh."

    # Get the AI response for the roast
    response = await slash_ai_response(roast_prompt)
    
    # Send the roast as a reply after deferring
    await interaction.followup.send(
        f"{response}"
    )

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if any(phrase in message.content.lower() for phrase in ["ded", "dead chat", "deadchat"]):
        await message.channel.send("Ded chat? I'm here to revive it! 😎")
        return
    if any(phrase in message.content.lower() for phrase in ["yamete", "kudasai", "moan", "horny"]):
        await message.channel.send("⣿⣿⣷⡁⢆⠈⠕⢕⢂⢕⢂⢕⢂⢔⢂⢕⢄⠂⣂⠂⠆⢂⢕⢂⢕⢂⢕⢂⢕⢂\n"
                                "⣿⣿⣿⡷⠊⡢⡹⣦⡑⢂⢕⢂⢕⢂⢕⢂⠕⠔⠌⠝⠛⠶⠶⢶⣦⣄⢂⢕⢂⢕\n"
                                "⣿⣿⠏⣠⣾⣦⡐⢌⢿⣷⣦⣅⡑⠕⠡⠐⢿⠿⣛⠟⠛⠛⠛⠛⠡⢷⡈⢂⢕⢂\n"
                                "⠟⣡⣾⣿⣿⣿⣿⣦⣑⠝⢿⣿⣿⣿⣿⣿⡵⢁⣤⣶⣶⣿⢿⢿⢿⡟⢻⣤⢑⢂\n"
                                "⣾⣿⣿⡿⢟⣛⣻⣿⣿⣿⣦⣬⣙⣻⣿⣿⣷⣿⣿⢟⢝⢕⢕⢕⢕⢽⣿⣿⣷⣔\n"
                                "⣿⣿⠵⠚⠉⢀⣀⣀⣈⣿⣿⣿⣿⣿⣿⣿⣿⣿⣗⢕⢕⢕⢕⢕⢕⣽⣿⣿⣿⣿\n"
                                "⢷⣂⣠⣴⣾⡿⡿⡻⡻⣿⣿⣴⣿⣿⣿⣿⣿⣿⣷⣵⣵⣵⣷⣿⣿⣿⣿⣿⣿⡿\n"
                                "⢌⠻⣿⡿⡫⡪⡪⡪⡪⣺⣿⣿⣿⣿⣿⠿⠿⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠃\n"
                                "⠣⡁⠹⡪⡪⡪⡪⣪⣾⣿⣿⣿⣿⠋⠐⢉⢍⢄⢌⠻⣿⣿⣿⣿⣿⣿⣿⣿⠏⠈\n"
                                "⡣⡘⢄⠙⣾⣾⣾⣿⣿⣿⣿⣿⣿⡀⢐⢕⢕⢕⢕⢕⡘⣿⣿⣿⣿⣿⣿⠏⠠⠈\n"
                                "⠌⢊⢂⢣⠹⣿⣿⣿⣿⣿⣿⣿⣿⣧⢐⢕⢕⢕⢕⢕⢅⣿⣿⣿⣿⡿⢋⢜⠠⠈\n"
                                "⠄⠁⠕⢝⡢⠈⠻⣿⣿⣿⣿⣿⣿⣿⣷⣕⣑⣑⣑⣵⣿⣿⣿⡿⢋⢔⢕⣿⠠⠈\n"
                                "⠨⡂⡀⢑⢕⡅⠂⠄⠉⠛⠻⠿⢿⣿⣿⣿⣿⣿⣿⣿⣿⡿⢋⢔⢕⢕⣿⣿⠠⠈\n"
                                "⠄⠪⣂⠁⢕⠆⠄⠂⠄⠁⡀⠂⡀⠄⢈⠉⢍⢛⢛⢛⢋⢔⢕⢕⢕⣽⣿⣿⠠⠈")
        return
    if any(phrase in message.content.lower() for phrase in ["motivation", "motivate"]):
        await message.channel.send("Did someone say....\n"
                           "⠀⠀⢐⢸⢸⢭⢗⢯⡺⡵⣝⢮⡳⣝⢮⢳⢕⢽⢸⡪⡪⡊⢆⢑⢐⠀⠀⠀⠀⠀\n"
                           "⠀⢀⢢⢣⢏⢯⣓⢧⢳⡳⣕⢷⣝⡮⣗⡽⡹⣜⢕⢧⢳⢩⠢⡡⢂⠈⠀⠀⠀⠀\n"
                           "⠀⢂⢕⢕⢕⢗⢎⡮⣳⢽⢺⡳⣳⢽⡳⣝⢽⢸⢸⢣⢣⢣⠱⡨⢂⠂⡀⠀⠀⠀\n"
                           "⠀⡰⡑⡕⡕⡕⡧⡯⢮⡳⡕⠕⠌⢂⠡⢑⢕⢧⢑⠑⠁⠠⢁⢂⢂⠂⠀⠀⠀⠀\n"
                           "⠀⠔⢈⢎⢮⢪⡳⣝⣕⢖⢜⠬⢌⢂⢌⢮⢽⢕⠅⠀⠀⠢⡂⡄⠄⠀⠀⠀⠀⠀\n"
                           "⠀⠐⢐⢕⢇⡗⣝⣞⢮⣻⣪⢯⢮⢮⢺⣪⢯⣫⢊⠀⠀⢁⠢⡂⡂⢄⢁⠀⠀⠀\n"
                           "⠀⠀⡂⢳⣈⢯⡪⡺⣝⣞⢾⢝⣮⡳⡽⣺⢝⣞⢆⠠⠀⠐⠠⡃⢕⠡⠀⠀⠀⠀\n"
                           "⠀⠀⠀⠨⢺⢜⢜⡝⡮⣺⢽⢝⡮⣫⢯⠞⡟⡎⡇⠀⠀⠀⠐⠈⠔⡈⠀⠀⠀⠀\n"
                           "⠀⠀⠀⠌⠢⡑⢕⢭⡫⣞⢽⢕⡯⣗⢷⢕⡮⡢⡂⠄⢁⠠⢈⠄⠡⠀⠀⠀⠀⢀\n"
                           "⠀⠀⠀⠠⠑⢜⠸⡜⡞⣎⢗⡽⡺⣵⡫⡯⡺⡪⠣⡁⡂⠌⠠⠐⠀⠀⠀⠀⠀⢀\n"
                           "⠀⠀⠀⠀⠅⠁⠈⡎⡯⣪⡳⡕⡝⡔⡅⣖⢔⢜⢄⢂⠠⠈⠄⡀⠀⠀⠀⠀⠀⠀\n"
                           "⠀⠀⠀⢐⠀⠀⠀⡇⡏⡮⣪⢳⡹⣪⢣⢣⢡⢱⢨⠠⡂⠌⡐⠀⠀⠀⠀⠀⠀⠀\n"
                           "⠀⠀⠀⠈⠀⠀⢀⠘⢎⢎⢎⢧⡫⣎⣗⣝⢮⢪⣊⠪⡐⢐⠀⠀⠀⠀⠀⠀⠀⠀\n"
                           "⠀⠀⡀⠌⠀⠀⠀⠀⠌⠘⠜⡜⡜⡮⢮⢺⢸⢪⢒⠕⡈⠀⠀⠀⠀⠀⠀⠀⠀⠄\n"
                           "⢀⢀⠂⢅⠂⠀⠀⠀⠀⠐⠀⡈⠢⢣⢃⡃⡁⠊⠐⠀⠀⠀⢀⠀⠀⠀⠀⠀⢐⠀\n"
                           "\n"
                           "...M O T I V A T I O N?")
        return
    if bot.user.mentioned_in(message) or "seeyuh" in message.content.lower():
        content = message.content.strip()
        command_content = content.replace(f"<@!{bot.user.id}>", "").strip()
        command_content = command_content.replace("seeyuh", "").strip()
        words = command_content.split()
    
        # Check for mentioned users
        mentioned_users = [user for user in message.mentions if user != bot.user]

        # Get or create the guild entry
        guild_entry = session.query(Guild).filter_by(guild_id=message.guild.id).first()
        if not guild_entry:
            guild_entry = Guild(guild_id=message.guild.id, guild_name=message.guild.name)
            session.add(guild_entry)
            session.commit()
        
        # If there are more than three words, treat as an AI query
        if len(words) > 3:
            ai_prompt = command_content
            if mentioned_users:
                user_name = mentioned_users[0].display_name
                ai_prompt = f"{message.author} queries about {user_name}: {command_content}"
            
            response = await get_ai_response(ai_prompt)
            await message.channel.send(response)
            # Save the user message and bot response
            save_message_to_db(guild_entry.guild_id, message.author, ai_prompt, response)
            return  # Exit early to avoid command processing

        # Proceed with command processing if message has three or fewer words
        command_found = False
        for word in words:
            # Check if the command exists
            command = bot.tree.get_command(word)
            if command:
                command_found = True
                command_name = word
                
                # Define the MockInteraction class within the on_message function
                class MockInteraction:
                    def __init__(self, message, mentioned_user=None):
                        self.channel = message.channel
                        self.guild = message.guild
                        self.user = message.author
                        self.id = message.id
                        self.mentioned_user = mentioned_user  # Set the mentioned user

                    async def send_message(self, content):
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

                        async def defer(self):
                            # Placeholder defer to mimic interaction.defer()
                            pass

                    # Adding a mock `followup` class to simulate followup messages
                    class Followup:
                        def __init__(self, channel):
                            self.channel = channel

                        async def send(self, content):
                            await self.channel.send(content)

                    @property
                    def response(self):
                        return self.Response(self.channel)

                    @property
                    def followup(self):
                        return self.Followup(self.channel)

                # If a specific user was mentioned, pass them into the command
                target_user = mentioned_users[0] if mentioned_users else None
                mock_interaction = MockInteraction(message, target_user)

                # Call the command callback with the mock interaction
                if target_user:
                    response =await command.callback(mock_interaction, target_user)  # Include the user argument
                else:
                    response = await command.callback(mock_interaction)
                # After the command execution, capture the response
                if isinstance(response, str):
                    # If the command returns a string directly
                    bot_response = response
                else:
                    # If the command sends a message via interaction, you may need to handle it differently
                    # Mock a function to capture the sent message (you can customize this based on your commands)
                    bot_response = f"response generated by bot for /{command_name}"  # You may change this according to how your command sends messages
                save_message_to_db(guild_entry.guild_id, message.author, command_content, bot_response)
                break

        if not command_found:
            # Treat as an AI query, include any mentioned user's name
            ai_prompt = command_content
            if mentioned_users:
                user_name = mentioned_users[0].display_name
                ai_prompt = f"{message.author} queries about {user_name}: {command_content}"
            
            response = await get_ai_response(ai_prompt)
            await message.channel.send(response)

            # Save the user message and bot response
            save_message_to_db(guild_entry.guild_id, message.author, ai_prompt, response)

    await bot.process_commands(message)
    
def save_message_to_db(guild_id, author, user_message, bot_response):
    # Get or create the user entry
    user_entry = session.query(User).filter_by(user_id=author.id).first()
    if not user_entry:
        user_entry = User(user_id=author.id, username=author.name, discriminator=author.discriminator, guild_id=guild_id)
        session.add(user_entry)
        session.commit()

    new_message = Message(
        content=user_message,
        user_id=user_entry.user_id,
        guild_id=guild_id,
        response=bot_response
    )
    session.add(new_message)
    session.commit()

# Run the bot
bot.run(DISCORD_TOKEN)

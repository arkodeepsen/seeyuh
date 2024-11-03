import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import time
from ai import get_ai_response, slash_ai_response
from supabase import create_client, Client
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import sessionmaker
import asyncio
import random

# Load environment variables
from dotenv import load_dotenv
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
OWNER = os.getenv('OWNER_ID')

# Supabase setup
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# SQLAlchemy base
Base = declarative_base()

# Define the Guild model
class Guild(Base):
    __tablename__ = 'guilds'

    id = Column(Integer, primary_key=True)
    guild_id = Column(String, unique=True)
    guild_name = Column(String)

# Define the User model
class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    user_id = Column(String, unique=True)
    username = Column(String)
    discriminator = Column(String)
    guild_id = Column(String, ForeignKey('guilds.guild_id'))

# Define the Message model
class Message(Base):
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True)
    content = Column(String)
    user_id = Column(String, ForeignKey('users.user_id'))
    guild_id = Column(String, ForeignKey('guilds.guild_id'))
    response = Column(String)

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
    description = "\n".join([f"`/{command.name}` - {command.description}" for command in bot.tree.get_commands()])
    embed = discord.Embed(
        title="Help Command",
        description=description,
        color=discord.Color.blue()
    )
    embed.set_footer(text=f"{bot.user.name}", icon_url=bot.user.avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='ping', description='Check if the bot is responsive.')
async def ping_command(interaction: discord.Interaction):
    start_time = time.time()

    # Send the initial response and capture the message
    await interaction.response.send_message(embed=discord.Embed(
        title="Ping Command",
        description="Pong! Calculating ping...",
        color=discord.Color.green()
    ))

    # Calculate the ping
    latency = round(bot.latency * 1000)  # Convert to milliseconds
    end_time = time.time()
    ping = round((end_time - start_time) * 1000)  # Convert to milliseconds

    embed = discord.Embed(
        title="Ping Command",
        description=f"Pong! Bot ping is {ping} ms. Discord API latency is {latency} ms.",
        color=discord.Color.green()
    )
    embed.set_footer(text=f"{bot.user.name}", icon_url=bot.user.avatar.url)

    # Instead of trying to edit, use followup to send the updated message
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
            f"**Commands:** {' '.join([f'`/{command.name}` ' for command in bot.tree.get_commands()])}\n"
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
    
    # List of Social Media and Internet Personalities
    social_media_terms = [
        "skibidi",
        "gyatt",
        "rizz",
        "duke dennis",
        "livvy dunne",
        "kai cenat",
        "aiden ross",
        "adin ross",
        "ishowspeed",
        "fanum",
        "john pork",
        "colleen ballinger"
    ]

    # List of Popular Phrases and Expressions
    popular_phrases = [
        "only in ohio",
        "did you pray today",
        "rizzing up",
        "no edging in class",
        "1 2 buckle my shoe",
        "bro really thinks he's carti",
        "literally hitting the griddy",
        "sin city monday left me broken",
        "quirked up white boy busting it down sexual style",
        "the ocky way",
        "PLUH"
    ]

    # List of Gaming and Meme References
    gaming_meme_references = [
        "freddy fazbear",
        "huggy wuggy",
        "gaten of banban",
        "grimace shake",
        "kiki do you love me",
        "pizza tower",
        "ugandan knuckles",
        "fortnite battle pass",
        "the biggest bird",
        "whopper whopper whopper whopper"
    ]

    # List of Cultural References and Random Concepts
    cultural_references = [
        "sigma",
        "alpha male",
        "omega male",
        "grindset",
        "goon cave",
        "smurf cat vs strawberry elephant",
        "shmlawg",
        "kumalala",
        "savesta",
        "thug shaker",
        "morbin time",
        "dj khaled",
        "sisyphus",
        "shadow wizard money gang",
        "bing chilling"
    ]

    # List of Absurd and Whimsical Terms
    absurd_terms = [
        "a whole bunch of turbulence",
        "bussing",
        "axel in harlem",
        "lightskin stare",
        "omar the referee",
        "chungus",
        "keanu reeves",
        "delulu",
        "opium bird",
        "cg5",
        "meowing",
        "all my fellas",
        "foot fetish",
        "social credit"
    ]

    # List of Reactions and Responses
    reactions = [
        "F in the chat",
        "i love lean",
        "redpilled",
        "cringe",
        "kino",
        "gigachad",
        "gooning",
        "we go gym",
        "kevin james",
        "josh hutcherson",
        "better caul saul",
        "i am a surgeon",
        "hit or miss, i guess they never miss huh",
        "i like ya cut g"
    ]

    # List of Miscellaneous Terms
    miscellaneous_terms = [
        "quandale dingle",
        "glizzy",
        "rose toy",
        "ankha zone",
        "metal pipe falling",
        "nickeh30",
        "xbox live",
        "kid named finger",
        "the coffin of andy and leyley"
    ]

    brain_rot_terms = social_media_terms + popular_phrases + gaming_meme_references + cultural_references + absurd_terms + reactions + miscellaneous_terms
    # Check for brain rot terms
    if any(term in message.content.lower() for term in brain_rot_terms):
        # Reply to the original message without directly mentioning the user
        responses = [
            "Bro, that's so brainrot! 🧠💀", 
            "What are you even saying? 🧠💀",
            "Brainrot alert! 🧠💀",
            "What kind of brainrot is this? 🧠💀",
            "That's some serious brainrot! 🧠💀",
            "Brainrot detected! 🧠💀",
            "You need to chill with the brainrot! 🧠💀",
            "Brainrot overload! 🧠💀",
            "This is peak brainrot content! 🧠💀",
            "Brainrot vibes only! 🧠💀",
            "Certified brainrot moment! 🧠💀",
            "Brainrot central! 🧠💀",
            "Brainrot level: 1000! 🧠💀",
            "Brainrot king/queen! 🧠💀",
            "Brainrot champion! 🧠💀",
            "Brainrot madness! 🧠💀",
            "Ultimate brainrot! 🧠💀",
            "Brainrot extravaganza! 🧠💀",
            "Brainrot fiesta! 🧠💀",
            "Brainrot overload detected! 🧠💀",
            "Brainrot vibes detected! 🧠💀",
            "Brainrot intensity: MAX! 🧠💀",
            "Brainrot phenomenon! 🧠💀",
            "Brainrot sensation! 🧠💀",
            "Brainrot mania! 🧠💀",
            "Brainrot frenzy! 🧠💀",
            "Brainrot explosion! 🧠💀",
            "Brainrot epidemic! 🧠💀",
            "Brainrot outbreak! 🧠💀",
            "Brainrot invasion! 🧠💀"
        ]
        await message.reply(random.choice(responses))
        return
    if any(phrase in message.content.lower() for phrase in ["gta 6", "gta vi"]):
        responses = [
            "GTA 6? That's never dropping lil bro. 😂",
            "GTA 6? Keep dreaming, lil bro! 😅",
            "GTA 6? Maybe in another lifetime, lil bro. 😆",
            "GTA 6? We'll be old by then, lil bro. 😂",
            "GTA 6? Not in this decade, lil bro! 😜"
        ]
        await message.channel.send(random.choice(responses))
        return
    if any(phrase in message.content.lower() for phrase in ["lil uzi", "uzi vert"]):
        await message.channel.send("Lil Uzi Vert? That's the vibes! 🚀 Eternal Atake and LUV vs. The World 2 are classics. 🌌")
        return
    if any(phrase in message.content.lower() for phrase in ["travis scott", "cactus jack"]):
        await message.channel.send("Travis Scott? Astroworld is a masterpiece. 🎢🎡🎠")
        return
    if any(phrase in message.content.lower() for phrase in ["playboi carti", "carti", "slatt", "vamp", "whole lotta red", "wlr", "homixide", "0pium"]):
        await message.channel.send("Playboi Carti? Whole Lotta Red is a vibe. 🩸🔴")
        return
    if any(phrase in message.content.lower() for phrase in ["kanye west", "yeezy"]):
        await message.channel.send("Kanye West? Yeezus is a classic. 🐻🔥")
        return
    if any(phrase in message.content.lower() for phrase in ["drake", "champagne papi"]):
        await message.channel.send("Drake? Certified Lover Boy? Certified Pedophile! 😂")
        return
    if any(phrase in message.content.lower() for phrase in ["the weeknd", "abel tesfaye"]):
        await message.channel.send("The Weeknd? Blinding Lights is iconic. 🌟🎤")
        return
    if any(phrase in message.content.lower() for phrase in ["eminem", "slim shady"]):
        await message.channel.send("Eminem? Rap God! 🎤🔥")
        return
    if any(phrase in message.content.lower() for phrase in ["mr beast", "mrbeast", "chris ", "kris ", "tyson", "jimmy"]):
        await message.channel.send("I just helped 1000 blind people see for the first time... 😳 1001th person ☠💀")
        return
    if any(phrase in message.content.lower() for phrase in ["pewdiepie", "felix"]):
        await message.channel.send("PewDiePie? Brofist! 👊👊")
        return
    if any(phrase in message.content.lower() for phrase in ["dream ", "george ", "sapnap ", "karl ", "quackity "]):
        await message.channel.send("Dream SMP? Dream Team? Dream is sus! 😳")
        return
    if any(phrase in message.content.lower() for phrase in ["ratio", "rati0"]):
        reply_message = await message.reply("Ratioed! 😂")
        await reply_message.add_reaction("⬆")
        return
    if any(phrase in message.content.lower() for phrase in ["simp", "simping"]):
        await message.channel.send("Simping is a way of life. 🥺")
        return
    if any(phrase in message.content.lower() for phrase in ["sus", "amogus", "among us", "impostor", "crewmate", "vent", "amongus"]):

        await message.channel.send("Amogus! 😳")
        return
    if any(phrase in message.content.lower() for phrase in ["bruh", "bruh moment"]) and random.random() < 0.2:
        await message.channel.send("Bruh moment! 😂")
        return
    if any(phrase in message.content.lower() for phrase in ["lmao", "lmfao", "lol", "rofl"]) and random.random() < 0.1:
        await message.channel.send("😆")
        return
    if any(phrase in message.content.lower() for phrase in ["rip", "rest in peace", "rip in peace"]) and random.random() < 0.5:
        await message.channel.send("Rest in peace! 😢")
        return
    if any(phrase in message.content.lower() for phrase in ["f in the chat", "press f", "fs in the chat"]):
        await message.channel.send("F")
        return
    if any(phrase in message.content.lower() for phrase in ["elon musk", "tesla", "spacex", "dogecoin"]):
        await message.channel.send("https://tenor.com/view/this-is-elon-musk-gif-24487310")
        return
    if any(phrase in message.content.lower() for phrase in ["good bot", "great bot", "best bot"]):
        await message.channel.send("Thank you! I'm here to help. 😄")
        return
    
    # 10% chance to respond to the message
    if random.random() < 0.1:
        command_content = message.content.strip()
        ai_prompt = f"{message.author} says: {command_content}. Query: make fun of the user in a playful but interesting manner."
        mentioned_users = message.mentions
        if mentioned_users:
            user_name = mentioned_users[0].display_name
            ai_prompt = f"{message.author} says about {user_name}: {command_content}. Query: make fun of both users in a playful but interesting manner."
        
        response = await get_ai_response(ai_prompt)
        await message.reply(response)

    # Process other commands or logic if needed
    await bot.process_commands(message)

    if any(phrase in message.content.lower() for phrase in ["bad bot", "worst bot", "terrible bot"]):
        await message.channel.send("I'm sorry to hear that. I'll try to do better. 😢")
        return
    # If the message does not contain any brain rot terms, proceed with the rest of the code
    if any(phrase in message.content.lower() for phrase in ["ded chat", "dead chat", "deadchat", "dedchat"]):
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

        # Check if the guild entry exists
        guild_entry = supabase.table('guilds').select('*').eq('guild_id', str(message.guild.id)).execute()

        # Insert or update the guild entry based on existence
        if not guild_entry.data:  # If no existing entry, insert
            try:
                supabase.table('guilds').insert({
                    'guild_id': str(message.guild.id),
                    'guild_name': message.guild.name
                }).execute()
            except Exception as e:
                print(f"Error inserting guild: {e}")
        else:  # If entry exists, update
            try:
                supabase.table('guilds').update({
                    'guild_name': message.guild.name
                }).eq('guild_id', str(message.guild.id)).execute()
            except Exception as e:
                print(f"Error updating guild: {e}")
    
        # If there are more than three words, treat as an AI query
        if len(words) > 3:
            ai_prompt = command_content
            if mentioned_users:
                user_name = mentioned_users[0].display_name
                ai_prompt = f"{message.author} queries about {user_name}: {command_content}"
    
            response = await get_ai_response(ai_prompt)
            await message.channel.send(response)
            # Save the user message and bot response
            save_message_to_db(str(message.guild.id), message.author, ai_prompt, response)
            return  # Exit early to avoid command processing
    
        # Proceed with command processing if message has three or fewer words
        command_found = False
        for word in words:
            # Check if the command exists
            command = bot.tree.get_command(word)
            if command:
                command_found = True
                command_name = word
    
                class MockInteraction:
                    def __init__(self, message, mentioned_user=None):
                        self.channel = message.channel
                        self.guild = message.guild
                        self.user = message.author
                        self.id = message.id
                        self.mentioned_user = mentioned_user
                        self._original_response = None  # Store original response if needed

                    async def send_message(self, content=None, embed=None):
                        # Send the message and store it as the original response
                        if embed:
                            self._original_response = await self.channel.send(embed=embed)  # Store the sent message
                        else:
                            self._original_response = await self.channel.send(content)  # Store the sent message
                        return self._original_response  # Return the message

                    async def original_response(self):
                        # Return the original response if it exists
                        return self._original_response

                    async def defer(self):
                        pass  # Placeholder for deferring a response if needed

                    class Response:
                        def __init__(self, channel):
                            self.channel = channel

                        async def send_message(self, content=None, embed=None):
                            if embed:
                                return await self.channel.send(embed=embed)  # Return the message
                            else:
                                return await self.channel.send(content)  # Return the message

                        async def defer(self):
                            pass  # Placeholder defer

                    class Followup:
                        def __init__(self, channel):
                            self.channel = channel

                        async def send(self, content=None, embed=None):
                            if embed:
                                await self.channel.send(embed=embed)
                            else:
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
    
                # Inside the command execution section
                if target_user:
                    response = await command.callback(mock_interaction, target_user)  # Include the user argument
                else:
                    try:
                        response = await command.callback(mock_interaction)
                    except TypeError as e:
                        if "missing 1 required positional argument: 'user'" in str(e):
                            response = "Please mention a user."
                            await message.channel.send(response)  # Send the error message to the channel
                        else:
                            raise e

                # After the command execution, capture the response
                if isinstance(response, str):
                    bot_response = response  # If the command returns a string directly
                else:
                    # Ensure response is handled appropriately
                    bot_response = f"Response generated by bot for /{command_name}"  # Adjust as necessary

                # Save the user message and bot response
                save_message_to_db(str(message.guild.id), message.author, command_content, bot_response)
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
            save_message_to_db(str(message.guild.id), message.author, ai_prompt, response)

    await bot.process_commands(message)
    
def save_message_to_db(guild_id, author, user_message, bot_response):
    # Upsert user entry
    user_entry_response = supabase.table('users').select('*').eq('user_id', str(author.id)).execute()

    if not user_entry_response.data:
        try:
            supabase.table('users').insert({
                'user_id': str(author.id),
                'username': author.name,
                'discriminator': author.discriminator,
                'guild_id': guild_id
            }).execute()
        except Exception as e:
            print(f"Error inserting user: {e}")

    # Insert new message without specifying the id
    try:
        supabase.table('messages').insert({
            'content': user_message,
            'user_id': str(author.id),
            'guild_id': guild_id,
            'response': bot_response
        }).execute()
    except Exception as e:
        print(f"Error inserting message: {e}")

# Run the bot
bot.run(DISCORD_TOKEN)

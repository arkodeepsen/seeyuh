import time, httpx, random, engine.commands.general as general, engine.commands.utility as utility, engine.commands.fun as fun
from discord.ext import commands
from engine.utils import load_env, intents, update_presence
from engine.db import fetch_recent_message, save_message_to_db
from engine.ai.gemini import get_ai_response
from supabase import create_client, Client
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, ForeignKey

# Load environment variables
DISCORD_TOKEN, OWNER, url, key = load_env()
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

# Create the bot instance with the specified intents
bot = commands.Bot(command_prefix='/', intents=intents())

# Load slash commands
@bot.event
async def on_ready():
    bot.uptime = time.time()
    print(f'Logged in as {bot.user}')
    bot.loop.create_task(update_presence(bot)) # Start the presence update loop
    await bot.tree.sync() # Sync commands with Discord

# Register the commands from general.py
bot.tree.add_command(general.help_command)
bot.tree.add_command(general.ping_command)
bot.tree.add_command(general.info_command)
bot.tree.add_command(general.serverinfo_command)

# Register the commands from utility.py
bot.tree.add_command(utility.say_command)
bot.tree.add_command(utility.emoji_command)

# Register the commands from fun.py
bot.tree.add_command(fun.roast_command)
  
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if bot.user.mentioned_in(message) or "seeyuh" in message.content.lower():
        content = message.content.strip()
        command_content = content.replace(f"<@{bot.user.id}>", "").strip()
        command_content = command_content.replace("seeyuh", "").strip()
        words = command_content.split()

        # Retrieve the last relevant message, prioritizing the user’s recent message
        last_message = fetch_recent_message(supabase, guild_id=str(message.guild.id), user_id=str(message.author.id))

        if last_message:
            context_message = f"Last relevant message in the guild: {last_message['content']}\n"
            context_message += f"Bot response to that message: {last_message['response']}\n"
        else:
            context_message = ""

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
            author_name = message.author.name
            current_query = f"from user {author_name} : {command_content}."
            ai_prompt = context_message + "Current query: " + current_query
            if mentioned_users:
                user_name = mentioned_users[0].name
                current_query = f"from user {author_name} about user {user_name} : {command_content}."
                ai_prompt = context_message + "Current query: " + current_query
    
            response = await get_ai_response(ai_prompt)
            # Split the response into multiple messages if it exceeds 2000 characters
            max_length = 2000
            response_parts = [response[i:i + max_length] for i in range(0, len(response), max_length)]

            for part in response_parts:
                await message.reply(part)
                
            # Save the user message and bot response
            save_message_to_db(str(message.guild.id), message.author, current_query, response)
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
                    def __init__(self, message, bot, mentioned_user=None, content=None, embed=None):
                        self.channel = message.channel
                        self.guild = message.guild
                        self.user = message.author
                        self.id = message.id
                        self.mentioned_user = mentioned_user
                        self._original_response = None  # Store original response if needed
                        self.content = content
                        self.embed = embed
                        self.client = bot  # Add the client attribute
                
                    async def send_message(self, content=None, embed=None):
                        # Send the message and store it as the original response
                        if embed:
                            self._original_response = await self.channel.send(embed=embed)
                        else:
                            self._original_response = await self.channel.send(content)
                        return self._original_response
                
                    async def original_response(self):
                        # Return the original response if it exists
                        return self._original_response
                
                    async def defer(self):
                        pass  # Placeholder for deferring a response if needed
                
                    class Response:
                        def __init__(self, channel):
                            self.channel = channel
                
                        async def send_message(self, content=None, embed=None):
                            # Ensure we send either content or embed properly
                            if embed:
                                return await self.channel.send(embed=embed)
                            else:
                                return await self.channel.send(content)
                
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
                mock_interaction = MockInteraction(message, bot, target_user)
                
                # Inside the command execution section
                if target_user:
                    response = await command.callback(mock_interaction, target_user)  # Include the user argument
                else:
                    try:
                        response = await command.callback(mock_interaction)
                    except TypeError as e:
                        if "missing 1 required positional argument: 'user'" in str(e):
                            response = f"User not mentioned, unreadable or you mentioned me. Please mention a user or try `/{word}` if issue persists."
                            await message.reply(response)  # Send the error message to the channel
                        elif "missing 1 required positional argument: 'content' in str(e)":
                            response = f"Use `/{word} content` `/help` to know more."
                            await message.reply(response)  # Send the error message to the channel
                        elif "missing 2 required positional arguments: 'content' and 'embed'" in str(e):
                            response = f"Content or embed not provided. Please use `/{word}` if issue persists."
                            await message.reply(response)  # Send the error message to the channel
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
            author_name = message.author.name
            current_query = f"from user {author_name} : {command_content}."
            ai_prompt = context_message + "Current query: " + current_query
            if mentioned_users:
                user_name = mentioned_users[0].name
                current_query = f"from user {author_name} about user {user_name} : {command_content}."
                ai_prompt = context_message + "Current query:" + current_query
            
            response = await get_ai_response(ai_prompt)
            # Split the response into multiple messages if it exceeds 2000 characters
            max_length = 2000
            response_parts = [response[i:i + max_length] for i in range(0, len(response), max_length)]

            for part in response_parts:
                await message.reply(part)
                
            # Save the user message and bot response
            save_message_to_db(str(message.guild.id), message.author, current_query, response)
            return  # Exit early to avoid command processing
    
    command_content = message.content.strip()
    words = command_content.split()
    if 0 < len(words) <= 2 and not bot.user.mentioned_in(message) and "seeyuh" not in message.content.lower():
        # Check for mentioned users
        mentioned_users = [user for user in message.mentions if user != bot.user]
        # Proceed with command processing if message has three or fewer words
        command_found = False
        for word in words:
            # Check if the command exists
            command = bot.tree.get_command(word)
            if command:
                command_found = True
                command_name = word

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
                
                class MockInteraction:
                    def __init__(self, message, bot, mentioned_user=None, content=None, embed=None):
                        self.channel = message.channel
                        self.guild = message.guild
                        self.user = message.author
                        self.id = message.id
                        self.mentioned_user = mentioned_user
                        self._original_response = None  # Store original response if needed
                        self.content = content
                        self.embed = embed
                        self.client = bot  # Add the client attribute
                
                    async def send_message(self, content=None, embed=None):
                        # Send the message and store it as the original response
                        if embed:
                            self._original_response = await self.channel.send(embed=embed)
                        else:
                            self._original_response = await self.channel.send(content)
                        return self._original_response
                
                    async def original_response(self):
                        # Return the original response if it exists
                        return self._original_response
                
                    async def defer(self):
                        pass  # Placeholder for deferring a response if needed
                
                    class Response:
                        def __init__(self, channel):
                            self.channel = channel
                
                        async def send_message(self, content=None, embed=None):
                            # Ensure we send either content or embed properly
                            if embed:
                                return await self.channel.send(embed=embed)
                            else:
                                return await self.channel.send(content)
                
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
                mock_interaction = MockInteraction(message, bot, target_user)
                
                # Inside the command execution section
                if target_user:
                    response = await command.callback(mock_interaction, target_user)  # Include the user argument
                else:
                    try:
                        response = await command.callback(mock_interaction)
                    except TypeError as e:
                        if "missing 1 required positional argument: 'user'" in str(e):
                            response = f"User not mentioned, unreadable or you mentioned me. Please mention a user or try `/{word}` if issue persists."
                            await message.reply(response)  # Send the error message to the channel
                        elif "missing 1 required positional argument: 'content' in str(e)":
                            response = f"Use `/{word} content` `/help` to know more."
                            await message.reply(response)  # Send the error message to the channel
                        elif "missing 2 required positional arguments: 'content' and 'embed'" in str(e):
                            response = f"Content or embed not provided. Please use `/{word}` if issue persists."
                            await message.reply(response)  # Send the error message to the channel
                        else:
                            raise e

                # After the command execution, capture the response
                if isinstance(response, str):
                    bot_response = response  # If the command returns a string directly
                     # Save the user message and bot response
                    save_message_to_db(str(message.guild.id), message.author, command_content, bot_response)
                else:
                    # Ensure response is handled appropriately
                    bot_response = f"Response generated by bot for /{command_name}"  # Adjust as necessary

                break
    
        # 10% chance to respond to the message
    if random.random() < 0.01:
        command_content = message.content.strip()
        author_name = message.author.name
        ai_prompt = f"{author_name} says: {command_content}. Query: make a funny but interesting response to the user's message or drop a serious response according to the topic."
        mentioned_users = [user for user in message.mentions if user != bot.user]
        if mentioned_users:
            user_name = mentioned_users[0].name
            ai_prompt = f"{author_name} says about {user_name}: {command_content}. Query: make fun of both users in a playful but interesting manner or drop some information related to the topic."
        
        response = await get_ai_response(ai_prompt)
        await message.reply(response)
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
                
    await bot.process_commands(message)

# Run the bot
bot.run(DISCORD_TOKEN)

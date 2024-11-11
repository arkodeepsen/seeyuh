import discord, time, uvicorn, asyncio, logging, random, engine.commands.general as general, engine.commands.utility as utility, engine.commands.fun as fun, engine.commands.music as music, engine.eventloop as eventloop
from discord.ext import commands, tasks
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Template
from engine.utils import load_env, intents, update_presence
from engine.db import fetch_recent_message, save_message_to_db, retry_check_and_update_guild_entry
from engine.ai.gemini import get_ai_response, code_ai_response
from engine.ai.gemini_multimodal import handle_attachment
from supabase import create_client, Client
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, ForeignKey

# Load environment variables
DISCORD_TOKEN, OWNER, url, key = load_env()
supabase: Client = create_client(url, key)

app = FastAPI()
# Mount the static files directory
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

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
    created_at = Column(String)  # Assuming you want to save the timestamp as a string

# Create the bot instance with the specified intents
bot = commands.Bot(command_prefix='/', intents=intents())

# Task to leave the voice channel after 10 minutes of inactivity
@tasks.loop(minutes=10)
async def check_inactivity():
    for vc in bot.voice_clients:
        if not vc.is_playing() and not vc.is_paused():
            await vc.disconnect()
            channel = vc.channel
            embed = discord.Embed(title="Voice Channel", description="Left the voice channel due to inactivity.", color=discord.Color.orange())
            await channel.send(embed=embed)
            
@app.get("/status")
def health_check():
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
def health_check():
    with open("templates/index.ejs") as file:
        template = Template(file.read())
    bot_uptime = time.strftime("%H:%M:%S", time.gmtime(time.time() - bot.uptime))
    html_content = template.render(status="ok", bot_name=bot.user.name, bot_uptime=bot_uptime, unique_users = len(bot.users), guild_count = len(bot.guilds))
    return HTMLResponse(content=html_content)

@app.get("/policy", response_class=HTMLResponse)
@app.get("/privacy-policy", response_class=HTMLResponse)
def privacy_policy():
    with open("templates/privacy-policy.ejs") as file:
        template = Template(file.read())
    html_content = template.render(bot_name=bot.user.name, contact_email="contact@arkodeep.me")
    return HTMLResponse(content=html_content)

@app.get("/terms", response_class=HTMLResponse)
@app.get("/tos", response_class=HTMLResponse)
@app.get("/terms-of-service", response_class=HTMLResponse)
def terms_of_service():
    with open("templates/tos.ejs") as file:
        template = Template(file.read())
    html_content = template.render(bot_name=bot.user.name, contact_email="contact@arkodeep.me")
    return HTMLResponse(content=html_content)

def run_http_server():
    uvicorn.run(app, host="0.0.0.0", port=8080)

# Load slash commands
@bot.event
async def on_ready():
    bot.uptime = time.time()
    bot.loop.create_task(update_presence(bot)) # Start the presence update loop
    await bot.tree.sync() # Sync commands with Discord   
    # Start the inactivity check task
    check_inactivity.start()
    eventloop.event_loop = asyncio.get_running_loop()
    print(f'Logged in as {bot.user}')

# Define the main function to run both the bot and HTTP server concurrently
async def main():
    # Run the HTTP server in the background
    asyncio.get_running_loop().run_in_executor(None, run_http_server)
    
    # Run the Discord bot
    await bot.start(DISCORD_TOKEN)
            
# Register the commands from general.py
general.help_command.category = "General"
general.ping_command.category = "General"
general.info_command.category = "General"
general.serverinfo_command.category = "General"
bot.tree.add_command(general.help_command)
bot.tree.add_command(general.ping_command)
bot.tree.add_command(general.info_command)
bot.tree.add_command(general.serverinfo_command)

# Register the commands from utility.py
utility.say_command.category = "Utility"
utility.emoji_command.category = "Utility"
utility.avatar_command.category = "Utility"
utility.code_command.category = "Utility"
utility.explain_command.category = "Utility"
utility.ask_command.category = "Utility"
utility.poll_command.category = "Utility"
utility.translate_command.category = "Utility"
utility.prompt_command.category = "Utility"
utility.reddit_command.category = "Utility"
utility.weather_command.category = "Utility"
utility.search_command.category = "Utility"
utility.meaning_command.category = "Utility"
bot.tree.add_command(utility.say_command)
bot.tree.add_command(utility.emoji_command)
bot.tree.add_command(utility.avatar_command)
bot.tree.add_command(utility.code_command)
bot.tree.add_command(utility.explain_command)
bot.tree.add_command(utility.ask_command)
bot.tree.add_command(utility.poll_command)
bot.tree.add_command(utility.translate_command)
bot.tree.add_command(utility.prompt_command)
bot.tree.add_command(utility.reddit_command)
bot.tree.add_command(utility.weather_command)
bot.tree.add_command(utility.search_command)
bot.tree.add_command(utility.meaning_command)

# Register the commands from fun.py
fun.roast_command.category = "Fun"
fun.compliment_command.category = "Fun"
fun.joke_command.category = "Fun"
fun.fact_command.category = "Fun"
fun.advice_command.category = "Fun"
fun.quote_command.category = "Fun"
fun.riddle_command.category = "Fun"
fun.meme_command.category = "Fun"
fun.gif_command.category = "Fun"
fun.rps_command.category = "Fun"
fun.tictactoe_command.category = "Fun"
fun.coinflip_command.category = "Fun"
fun.horoscope_command.category = "Fun"
fun.magic8ball_command.category = "Fun"
fun.dice_command.category = "Fun"
fun.choose_command.category = "Fun"
fun.wordle_command.category = "Fun"
fun.trivia_command.category = "Fun"
fun.rpsls_command.category = "Fun"
fun.mystery_command.category = "Fun"
bot.tree.add_command(fun.roast_command)
bot.tree.add_command(fun.compliment_command)
bot.tree.add_command(fun.joke_command)
bot.tree.add_command(fun.fact_command)
bot.tree.add_command(fun.advice_command)
bot.tree.add_command(fun.quote_command)
bot.tree.add_command(fun.riddle_command)
bot.tree.add_command(fun.meme_command)
bot.tree.add_command(fun.gif_command)
bot.tree.add_command(fun.rps_command)
bot.tree.add_command(fun.tictactoe_command)
bot.tree.add_command(fun.coinflip_command)
bot.tree.add_command(fun.horoscope_command)
bot.tree.add_command(fun.magic8ball_command)
bot.tree.add_command(fun.dice_command)
bot.tree.add_command(fun.choose_command)
bot.tree.add_command(fun.wordle_command)
bot.tree.add_command(fun.trivia_command)
bot.tree.add_command(fun.rpsls_command)
bot.tree.add_command(fun.mystery_command)

# Register the commands from music.py
music.join.category = "Music"
music.leave.category = "Music"
music.play.category = "Music"
music.pause.category = "Music"
music.resume.category = "Music"
music.stop.category = "Music"
music.now_playing.category = "Music"
music.queue.category = "Music"
music.filter_command.category = "Music"
music.list_filters.category = "Music"
music.clear_filters.category = "Music"
bot.tree.add_command(music.join)
bot.tree.add_command(music.leave)
bot.tree.add_command(music.play)
bot.tree.add_command(music.pause)
bot.tree.add_command(music.resume)
bot.tree.add_command(music.stop)
bot.tree.add_command(music.now_playing)
bot.tree.add_command(music.queue)
bot.tree.add_command(music.filter_command)
bot.tree.add_command(music.list_filters)
bot.tree.add_command(music.clear_filters)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Check if the message has attachments and bot is mentioned
    if (bot.user.mentioned_in(message) or "seeyuh" in message.content.lower()):
        if message.attachments:
            async with message.channel.typing():  # Show typing indicator
                for attachment in message.attachments:
                    if attachment.content_type and attachment.content_type.startswith("image/") or attachment.content_type == "application/pdf" or attachment.content_type.startswith("text/"):
                        await handle_attachment(bot, message, attachment)
                    else:
                        await message.reply("Unsupported file type. Please upload an image, pdf, text or code file.")
            return  # Stop further processing if this condition is met

        # Check if the message is a reply to another message that has attachments
        if message.reference:
            try:
                original_message = await message.channel.fetch_message(message.reference.message_id)
                if original_message.attachments:
                    async with message.channel.typing():  # Show typing indicator
                        for attachment in original_message.attachments:
                            if attachment.content_type and attachment.content_type.startswith("image/") or attachment.content_type == "application/pdf" or attachment.content_type.startswith("text/"):
                                await handle_attachment(bot, original_message, attachment)
                            elif attachment.content_type == "text/plain":
                                await handle_attachment(bot, message, attachment)
                            else:
                                await message.reply("Unsupported file type. Please upload an image, pdf, text or code file.")
                    return  # Stop further processing if this condition is met
            except discord.NotFound:
                await message.reply("The original message could not be found.")
                return  # Stop further processing if this condition is met

    if message.content.lower().startswith("say") or (("seeyuh" in message.content.lower() or bot.user.mentioned_in(message)) and "say" in message.content.lower()):
        content = message.content.strip()
        command_content = content.replace(f"<@{bot.user.id}>", "").strip()
        command_content = command_content.replace("seeyuh", "").strip()
        words = command_content.split()
        if words and words[0].lower() == "say":
            response_message = " ".join(words[1:])
            await message.reply(response_message)
            return  # Stop further processing if this condition is met
    
    if message.content.lower().startswith("code") or (("seeyuh" in message.content.lower() or bot.user.mentioned_in(message)) and "code" in message.content.lower()):
            content = message.content.strip()
            command_content = content.replace(f"<@{bot.user.id}>", "").strip()
            command_content = command_content.replace("seeyuh", "").strip()
            words = command_content.split()
            
            # Start the background task to retry the entry update
            bot.loop.create_task(retry_check_and_update_guild_entry(supabase, str(message.guild.id), message.guild.name))
            
            if words and words[0].lower() == "code":
                prompt = " ".join(words[1:])
                async with message.channel.typing():  # Show typing indicator
                    response_message = await code_ai_response(prompt)  # Await the coroutine directly
                # Split the response into multiple messages if it exceeds 2000 characters
                max_length = 2000 - 6  # Deduct 6 characters for the code block delimiters (``` at the end and ``` at the beginning)
                response_parts = [response_message[i:i + max_length] for i in range(0, len(response_message), max_length)]

                for i, part in enumerate(response_parts):
                    if i == 0:
                        await message.reply(f"```{part}")
                    elif i == len(response_parts) - 1:
                        await message.reply(f"{part}```")
                    else:
                        await message.reply(f"{part}```\n```")
            
                # Save the user message and bot response
                bot.loop.create_task(save_message_to_db(str(message.guild.id), message.author, prompt, response_message))
                return  # Stop further processing if this condition is met
    
    if bot.user.mentioned_in(message) or "seeyuh" in message.content.lower():
        content = message.content.strip()
        command_content = content.replace(f"<@{bot.user.id}>", "").strip()
        command_content = command_content.replace("seeyuh", "").strip()
        words = command_content.split()

        # Check if the message is a reply to another message
        if message.reference:
            try:
                original_message = await message.channel.fetch_message(message.reference.message_id)
                original_author = original_message.author.name
                original_content = original_message.content
                context_message = f"\nLast relevant message in the guild: {original_author} said: {original_content}"

            except discord.NotFound:
                print("Original message not found.")
                context_message = ""
        else:    
            # Retrieve the last relevant message, prioritizing the user’s recent message
            last_message = fetch_recent_message(supabase, guild_id=str(message.guild.id), user_id=str(message.author.id))

            if last_message:
                context_message = f"Last relevant message in the guild: {last_message['content']}\n"
                context_message += f"Bot response to that message: {last_message['response']}\n"
            else:
                context_message = ""

        # Check for mentioned users
        mentioned_users = [user for user in message.mentions if user != bot.user]

        # Start the background task to retry the entry update
        bot.loop.create_task(retry_check_and_update_guild_entry(supabase, str(message.guild.id), message.guild.name))
        
        # If there are more than three words, treat as an AI query
        if len(words) > 3:
            author_name = message.author.name
            current_query = f"from user {author_name} : {command_content}."
            ai_prompt = context_message + "Current query: " + current_query
        
            if mentioned_users:
                user_name = mentioned_users[0].name
                current_query = f"from user {author_name} about user {user_name} : {command_content}."
                ai_prompt = context_message + "\nCurrent query: " + current_query
        
            async with message.channel.typing():  # Show typing indicator
                response = await get_ai_response(ai_prompt)
            # Split the response into multiple messages if it exceeds 2000 characters
            max_length = 2000
            response_parts = [response[i:i + max_length] for i in range(0, len(response), max_length)]
        
            for part in response_parts:
                await message.reply(part)
                
            # Save the user message and bot response
            bot.loop.create_task(save_message_to_db(str(message.guild.id), message.author, current_query, response))
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
                        def __init__(self, interaction):
                            self.interaction = interaction
                
                        async def send_message(self, content=None, embed=None):
                            # Ensure we send either content or embed properly
                            if embed:
                                self.interaction._original_response = await self.interaction.channel.send(embed=embed)
                            else:
                                self.interaction._original_response = await self.interaction.channel.send(content)
                            return self.interaction._original_response
                
                        async def defer(self):
                            pass  # Placeholder defer
                
                    class Followup:
                        def __init__(self, interaction):
                            self.interaction = interaction
                
                        async def send(self, content=None, embed=None):
                            if embed:
                                await self.interaction.channel.send(embed=embed)
                            else:
                                await self.interaction.channel.send(content)
                
                    @property
                    def response(self):
                        return self.Response(self)
                
                    @property
                    def followup(self):
                        return self.Followup(self)
                
                # If a specific user was mentioned, pass them into the command
                target_user = mentioned_users[0] if mentioned_users else None
                mock_interaction = MockInteraction(message, bot, target_user)
                
                # Inside the command execution section
                if target_user:
                    async with message.channel.typing():  # Show typing indicator
                        response = await command.callback(mock_interaction, target_user)  # Include the user argument
                else:
                    try:
                        async with message.channel.typing():  # Show typing indicator
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
                elif isinstance(response, discord.Message):
                    bot_response = response.content  # Capture the content of the message
                elif isinstance(response, discord.Embed):
                    bot_response = response.description  # Capture the description of the embed
                else:
                    # Ensure response is handled appropriately
                    bot_response = f"Response generated by bot for /{command_name}"  # Adjust as necessary
                
                # Save the user message and bot response
                bot.loop.create_task(save_message_to_db(str(message.guild.id), message.author, command_content, bot_response))
                
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
            async with message.channel.typing():  # Show typing indicator
                response = await get_ai_response(ai_prompt)
            # Split the response into multiple messages if it exceeds 2000 characters
            max_length = 2000
            response_parts = [response[i:i + max_length] for i in range(0, len(response), max_length)]

            for part in response_parts:
                await message.reply(part)
                
            # Save the user message and bot response
            bot.loop.create_task(save_message_to_db(str(message.guild.id), message.author, current_query, response))
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

                # Start the background task to retry the entry update
                bot.loop.create_task(retry_check_and_update_guild_entry(supabase, str(message.guild.id), message.guild.name))
                
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
                        def __init__(self, interaction):
                            self.interaction = interaction
                
                        async def send_message(self, content=None, embed=None):
                            # Ensure we send either content or embed properly
                            if embed:
                                self.interaction._original_response = await self.interaction.channel.send(embed=embed)
                            else:
                                self.interaction._original_response = await self.interaction.channel.send(content)
                            return self.interaction._original_response
                
                        async def defer(self):
                            pass  # Placeholder defer
                
                    class Followup:
                        def __init__(self, interaction):
                            self.interaction = interaction
                
                        async def send(self, content=None, embed=None):
                            if embed:
                                await self.interaction.channel.send(embed=embed)
                            else:
                                await self.interaction.channel.send(content)
                
                    @property
                    def response(self):
                        return self.Response(self)
                
                    @property
                    def followup(self):
                        return self.Followup(self)
                
                # If a specific user was mentioned, pass them into the command
                target_user = mentioned_users[0] if mentioned_users else None
                mock_interaction = MockInteraction(message, bot, target_user)
                
                # Inside the command execution section
                if target_user:
                    async with message.channel.typing():  # Show typing indicator
                        response = await command.callback(mock_interaction, target_user)  # Include the user argument
                else:
                    try:
                        async with message.channel.typing():  # Show typing indicator
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
                elif isinstance(response, discord.Message):
                    bot_response = response.content  # Capture the content of the message
                elif isinstance(response, discord.Embed):
                    bot_response = response.description  # Capture the description of the embed
                else:
                    # Ensure response is handled appropriately
                    bot_response = f"Response generated by bot for /{command_name}"  # Adjust as necessary
                
                # Save the user message and bot response
                bot.loop.create_task(save_message_to_db(str(message.guild.id), message.author, command_content, bot_response))

                break
    
        # 10% chance to respond to the message
    if random.random() < 0.001:
        command_content = message.content.strip()
        author_name = message.author.name
        ai_prompt = f"Context: {author_name} says '{command_content}'. \nInstruction: Make a funny but interesting response related to the user, you can spin the user's message into a story or a joke."

                # Check if the message is a reply to another message
        if message.reference:
            try:
                original_message = await message.channel.fetch_message(message.reference.message_id)
                original_author = original_message.author.name
                original_content = original_message.content
                context_message = f"\nLast relevant message in the guild: {original_author} said: {original_content}"

            except discord.NotFound:
                print("Original message not found.")
                context_message = ""
                
        mentioned_users = [user for user in message.mentions if user != bot.user]
        if mentioned_users:
            user_name = mentioned_users[0].name
            ai_prompt = f"{context_message} \nCurrent Context: {author_name} says about {user_name} '{command_content}'. \nInstruction: make fun of both users in a playful but interesting manner, you can spin the user's message into a story or a joke."

        async with message.channel.typing():  # Show typing indicator
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
    if any(term in message.content.lower() for term in brain_rot_terms) and random.random() < 0.005:
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
    if any(phrase in message.content.lower() for phrase in ["gta 6", "gta vi ", "grand theft auto 6", "grand theft auto vi "]) and random.random() < 0.0125:
        responses = [
            "GTA 6? That's never dropping lil bro. 😂",
            "GTA 6? Keep dreaming, lil bro! 😅",
            "GTA 6? Maybe in another lifetime, lil bro. 😆",
            "GTA 6? We'll be old by then, lil bro. 😂",
            "GTA 6? Not in this decade, lil bro! 😜"
        ]
        await message.channel.send(random.choice(responses))
        return
    if any(phrase in message.content.lower() for phrase in ["fortnite", "fortnite battle royale"]) and random.random() < 0.0125:
        await message.channel.send("Fortnite? That's so 2018! 😂")
        return
    if any(phrase in message.content.lower() for phrase in ["minecraft", "creeper", "enderman", "steve", "herobrine"]) and random.random() < 0.0125:
        await message.channel.send("Minecraft? Classic! 🌲🔨")
        return
    if any(phrase in message.content.lower() for phrase in ["roblox", "robux", "bloxberg", "blox fruit"]) and random.random() < 0.0125:
        await message.channel.send("Roblox? Bloxberg? Blox Fruit? 🎮🔥")
        return
    if any(phrase in message.content.lower() for phrase in [" ligma", "sugma ", "sugondese", "sugoma"]) and random.random() < 0.0125:
        await message.reply("Balls! 😂")
        return
    if any(phrase in message.content.lower() for phrase in ["lil uzi", "uzi vert"]) and random.random() < 0.0125:
        await message.channel.send("Lil Uzi Vert? That's the vibes! 🚀 Eternal Atake and LUV vs. The World 2 are classics. 🌌")
        return
    if any(phrase in message.content.lower() for phrase in ["travis scott", "cactus jack"]) and random.random() < 0.0125:
        await message.channel.send("Travis Scott? Astroworld is a masterpiece. 🎢🎡🎠")
        return
    if any(phrase in message.content.lower() for phrase in ["playboi carti", "carti", "slatt", "vamp ", "whole lotta red", "wlr", "homixide", "0pium"]) and random.random() < 0.0125:
        await message.channel.send("Playboi Carti? Whole Lotta Red is a vibe. 🩸🔴")
        return
    if any(phrase in message.content.lower() for phrase in ["kanye west", "yeezy"]) and random.random() < 0.0125:
        await message.channel.send("Kanye West? Yeezus is a classic. 🐻🔥")
        return
    if any(phrase in message.content.lower() for phrase in ["drake ", "champagne papi", " ovo ", " drake"]) and random.random() < 0.0125:
        await message.channel.send("Drake? Certified Lover Boy? Certified Pedophile! 😂")
        return
    if any(phrase in message.content.lower() for phrase in ["the weeknd", "abel tesfaye"]) and random.random() < 0.0125:
        await message.channel.send("The Weeknd? Blinding Lights is iconic. 🌟🎤")
        return
    if any(phrase in message.content.lower() for phrase in ["eminem", "slim shady"]) and random.random() < 0.0125:
        await message.channel.send("Eminem? Rap God! 🎤🔥")
        return
    if any(phrase in message.content.lower() for phrase in ["mr beast", "mrbeast"]):
        await message.channel.send("I just helped 1000 blind people see for the first time... 😳 1001th person ☠💀")
        return
    if any(phrase in message.content.lower() for phrase in ["pewdiepie", "felix kjellberg"]) and random.random() < 0.0125:
        await message.channel.send("PewDiePie? Brofist! 👊👊")
        return
    if any(phrase in message.content.lower() for phrase in ["ratio ", "rati0", " ratio"]) and random.random() < 0.0125:
        reply_message = await message.reply("Ratioed! 😂")
        await reply_message.add_reaction("⬆")
        return
    if any(phrase in message.content.lower() for phrase in ["simp ", "simping"]) and random.random() < 0.05:
        await message.channel.send("Simping is a way of life. 🥺")
        return
    if any(phrase in message.content.lower() for phrase in [" sus", "sus ", "amogus", "among us", "impostor", "crewmate", " vent ", "amongus"]) and random.random() < 0.01:

        await message.channel.send("Amogus! 😳")
        return
    if any(phrase in message.content.lower() for phrase in ["bruh", "bruh moment"]) and random.random() < 0.001:
        await message.channel.send("Bruh moment! 😂")
        return
    if any(phrase in message.content.lower() for phrase in ["lmao", "lmfao", "lol", "rofl"]) and random.random() < 0.0005:
        await message.channel.send("😆")
        return
    if any(phrase in message.content.lower() for phrase in [" rip ", "rest in peace", "rip in peace"]) and random.random() < 0.5:
        await message.channel.send("Rest in peace! 😢")
        return
    if any(phrase in message.content.lower() for phrase in ["f in the chat", "press f", "fs in the chat"]) and random.random() < 0.5:
        await message.channel.send("F")
        return
    if any(phrase in message.content.lower() for phrase in ["elon musk", "tesla", "spacex", "dogecoin"]) and random.random() < 0.05:
        await message.channel.send("https://tenor.com/view/this-is-elon-musk-gif-24487310")
        return
    if any(phrase in message.content.lower() for phrase in ["good bot", "great bot", "best bot"]) and random.random() < 0.05:
        await message.channel.send("Thank you! I'm here to help. 😄")
        return

    if any(phrase in message.content.lower() for phrase in ["bad bot", "worst bot", "terrible bot"]) and random.random() < 0.05:
        await message.channel.send("I'm sorry to hear that. I'll try to do better. 😢")
        return
    # If the message does not contain any brain rot terms, proceed with the rest of the code
    if any(phrase in message.content.lower() for phrase in ["ded chat", "dead chat", "deadchat", "dedchat"]) and random.random() < 0.05:
        await message.channel.send("Ded chat? I'm here to revive it! 😎")
        return
    if any(phrase in message.content.lower() for phrase in ["yamete", "kudasai"]) and random.random() < 0.05:
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
    if any(phrase in message.content.lower() for phrase in ["motivation", "motivate"]) and random.random() < 0.05:
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

# Run main
asyncio.run(main())
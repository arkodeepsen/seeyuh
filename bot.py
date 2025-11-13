import discord, time, uvicorn, asyncio, logging, os, aiohttp, random, re, engine.commands.general as general, engine.commands.utility as utility, engine.commands.fun as fun, engine.commands.music as music, engine.commands.moderation as moderation, engine.commands.misc as misc, engine.commands.rpg as rpg, engine.eventloop as eventloop
from discord.ext import commands, tasks
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Template
from engine.utils import load_env, intents, update_presence
from engine.db import fetch_recent_message, save_message_to_db, retry_check_and_update_guild_entry, generate_and_cache_invites, sync_guilds_and_users, get_welcome_settings
from engine.ai.gemini import get_ai_response, code_ai_response
from engine.ai.gemini_multimodal import handle_attachment
from engine.commands.video import generate_meme_video, generate_meme_video_with_progress
from supabase import create_client, Client
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, ForeignKey

# Fix for Pillow compatibility with MoviePy
try:
    from PIL import Image
    if not hasattr(Image, 'ANTIALIAS'):
        Image.ANTIALIAS = Image.LANCZOS
except ImportError:
    pass

logging.basicConfig(level=logging.INFO)

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
            guild_id = vc.guild.id
            await vc.disconnect()
            # FIXED: Clean up music state when disconnecting due to inactivity
            try:
                from engine.commands.music import cleanup_guild_state
                cleanup_guild_state(guild_id)
            except Exception as e:
                logging.error(f"Failed to cleanup music state: {e}")
            channel = vc.channel
            embed = discord.Embed(title="Voice Channel", description="Left the voice channel due to inactivity.", color=discord.Color.orange())
            await channel.send(embed=embed)

# FIXED: New periodic memory cleanup task to prevent memory leaks
@tasks.loop(hours=1)  # Run every hour
async def periodic_memory_cleanup():
    """Periodic cleanup to prevent memory leaks - runs every hour"""
    import gc
    import psutil
    
    try:
        # Get memory usage before cleanup
        process = psutil.Process()
        memory_before = process.memory_info().rss / 1024 / 1024
        
        logging.info(f"[MEMORY] 🧹 Starting periodic cleanup (Memory: {memory_before:.1f}MB)")
        
        # Clean up music cache
        try:
            from engine.commands.music import clear_music_cache
            clear_music_cache()
        except Exception as e:
            logging.error(f"Failed to clear music cache: {e}")
        
        # Clean up video voice cache
        try:
            from engine.commands.video import cleanup_voice_cache
            cleanup_voice_cache()
        except Exception as e:
            logging.error(f"Failed to clear voice cache: {e}")
        
        # Force garbage collection
        gc.collect()
        
        # Get memory usage after cleanup
        memory_after = process.memory_info().rss / 1024 / 1024
        saved = memory_before - memory_after
        
        logging.info(f"[MEMORY] ✅ Cleanup complete (Memory: {memory_after:.1f}MB, Freed: {saved:.1f}MB)")
        
    except Exception as e:
        logging.error(f"[MEMORY] ❌ Periodic cleanup failed: {e}")

# FIXED: Keep Supabase project active (prevents auto-pause on free tier)
@tasks.loop(hours=6)  # Run every 6 hours
async def keep_supabase_alive():
    """Ping Supabase every 6 hours to prevent project from pausing"""
    try:
        logging.info("[SUPABASE] 🔄 Pinging Supabase to keep project active...")
        
        # Simple query to keep connection alive
        # Check if guilds table exists (lightweight query)
        response = supabase.table('guilds').select('guild_id').limit(1).execute()
        
        if response:
            logging.info("[SUPABASE] ✅ Ping successful - project stays active")
        else:
            logging.warning("[SUPABASE] ⚠️ Ping returned no data, but connection established")
            
    except Exception as e:
        logging.error(f"[SUPABASE] ❌ Ping failed: {e}")
        # Don't crash the bot if Supabase ping fails - just log it
            
@app.get("/status")
def health_check():
    return {"status": "ok"}

@app.head("/api/uptimerobot")
@app.get("/api/uptimerobot")
async def uptimerobot_check():
    return {}

@app.get("/api/endpoint")
def bot_details():
    return {"name": bot.user.name, "id": bot.user.id, "uptime": time.ctime(bot.uptime), "ping": round(bot.latency * 1000), "unique_users": len(bot.users), "guild_count": len(bot.guilds)}

@app.get("/", response_class=HTMLResponse)
def home():
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

@app.get("/donation", response_class=HTMLResponse)
@app.get("/donate", response_class=HTMLResponse)
def donation():
    with open("templates/donate.ejs") as file:
        template = Template(file.read())
    html_content = template.render(bot_name=bot.user.name, contact_email="contact@arkodeep.me")
    return HTMLResponse(content=html_content)

@app.get("/invite", response_class=HTMLResponse)
def invite():
    return HTMLResponse(content='<meta http-equiv="refresh" content="0; url=https://discord.com/oauth2/authorize?client_id=690530760540553276" />')

DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')

@app.post("/github-webhook")
async def github_webhook(request: Request):
    try:
        payload = await request.json()
        repo_name = payload.get('repository', {}).get('full_name', 'Unknown repo')
        event_type = request.headers.get('X-GitHub-Event', 'ping')

        # Create a custom message based on the event type
        if event_type == 'push':
            ref = payload.get('ref', 'Unknown ref')
            commits = payload.get('commits', [])
            pusher = payload.get('pusher', {}).get('name', 'Unknown pusher')
            pusher_avatar = payload.get('sender', {}).get('avatar_url', 'https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png')
            commit_messages = "\n".join([f"[`{commit['id'][:7]}`]({commit['url']}) - {commit['message']} by {commit['author']['name']}" for commit in commits])

            embed = discord.Embed(
            title="🚀 New Push Event",
            description=f"Repository: [{repo_name}]({payload.get('repository', {}).get('html_url', '#')})",
            color=discord.Color.green()
            )
            embed.add_field(name="Ref", value=ref, inline=False)
            embed.add_field(name="Pusher", value=pusher, inline=False)
            embed.add_field(name="Commits", value=commit_messages or "No commits", inline=False)
            embed.set_footer(text="GitHub Webhook • Push Event", icon_url="https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png")
            embed.set_thumbnail(url=pusher_avatar)

        elif event_type == 'pull_request':
            action = payload.get('action', 'Unknown action')
            pr = payload.get('pull_request', {})
            pr_title = pr.get('title', 'No title')
            pr_url = pr.get('html_url', '#')
            pr_user = pr.get('user', {}).get('login', 'Unknown user')
            pr_user_avatar = pr.get('user', {}).get('avatar_url', 'https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png')
            pr_body = pr.get('body', 'No description')

            embed = discord.Embed(
            title="📥 Pull Request Event",
            description=f"Repository: [{repo_name}]({payload.get('repository', {}).get('html_url', '#')})",
            color=discord.Color.blue()
            )
            embed.add_field(name="Action", value=action.capitalize(), inline=False)
            embed.add_field(name="Title", value=f"[{pr_title}]({pr_url})", inline=False)
            embed.add_field(name="Author", value=pr_user, inline=False)
            embed.add_field(name="Description", value=pr_body or "No description", inline=False)
            embed.set_footer(text="GitHub Webhook • Pull Request Event", icon_url="https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png")
            embed.set_thumbnail(url=pr_user_avatar)

        elif event_type == 'issues':
            action = payload.get('action', 'Unknown action')
            issue = payload.get('issue', {})
            issue_title = issue.get('title', 'No title')
            issue_url = issue.get('html_url', '#')
            issue_user = issue.get('user', {}).get('login', 'Unknown user')
            issue_user_avatar = issue.get('user', {}).get('avatar_url', 'https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png')
            issue_body = issue.get('body', 'No description')

            embed = discord.Embed(
            title="🐛 Issue Event",
            description=f"Repository: [{repo_name}]({payload.get('repository', {}).get('html_url', '#')})",
            color=discord.Color.orange()
            )
            embed.add_field(name="Action", value=action.capitalize(), inline=False)
            embed.add_field(name="Title", value=f"[{issue_title}]({issue_url})", inline=False)
            embed.add_field(name="Author", value=issue_user, inline=False)
            embed.add_field(name="Description", value=issue_body or "No description", inline=False)
            embed.set_footer(text="GitHub Webhook • Issue Event", icon_url="https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png")
            embed.set_thumbnail(url=issue_user_avatar)

        elif event_type == 'issue_comment':
            action = payload.get('action', 'Unknown action')
            comment = payload.get('comment', {})
            comment_body = comment.get('body', 'No content')
            commenter = comment.get('user', {}).get('login', 'Unknown user')
            commenter_avatar = comment.get('user', {}).get('avatar_url', 'https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png')
            issue = payload.get('issue', {})
            issue_title = issue.get('title', 'No title')
            issue_url = issue.get('html_url', '#')

            embed = discord.Embed(
            title="💬 Issue Comment Event",
            description=f"Repository: [{repo_name}]({payload.get('repository', {}).get('html_url', '#')})",
            color=discord.Color.purple()
            )
            embed.add_field(name="Action", value=action.capitalize(), inline=False)
            embed.add_field(name="Issue", value=f"[{issue_title}]({issue_url})", inline=False)
            embed.add_field(name="Commenter", value=commenter, inline=False)
            embed.add_field(name="Comment", value=comment_body or "No content", inline=False)
            embed.set_footer(text="GitHub Webhook • Issue Comment Event", icon_url="https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png")
            embed.set_thumbnail(url=commenter_avatar)

        else:
            # Detailed default case for other event types
            sender = payload.get('sender', {}).get('login', 'Unknown sender')
            sender_avatar = payload.get('sender', {}).get('avatar_url', 'https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png')
            event_description = f"A `{event_type}` event occurred in [{repo_name}]({payload.get('repository', {}).get('html_url', '#')}) initiated by **{sender}**."

            embed = discord.Embed(
            title="🔔 GitHub Event Notification",
            description=event_description,
            color=discord.Color.gold()
            )
            embed.add_field(name="Event Type", value=event_type, inline=False)
            embed.add_field(name="Sender", value=sender, inline=False)
            embed.add_field(name="Details", value="Check the repository for more information.", inline=False)
            embed.set_footer(text="GitHub Webhook • General Event", icon_url="https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png")
            embed.set_thumbnail(url=sender_avatar)

        discord_payload = {
            "embeds": [embed.to_dict()]
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(DISCORD_WEBHOOK_URL, json=discord_payload) as response:
                if response.status != 204:
                    return {"status": "error", "response": await response.text()}
        
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def run_http_server():
    try:
        port = int(os.getenv("PORT", "8080"))
    except Exception:
        port = 8080
    try:
        uvicorn.run(app, host="0.0.0.0", port=port)
    except OSError as e:
        logging.error(f"HTTP server bind failed on port {port}: {e}")
        return

# Load slash commands
@bot.event
async def on_ready():
    bot.uptime = time.time()
    bot.loop.create_task(update_presence(bot)) # Start the presence update loop
    await bot.tree.sync() # Sync commands with Discord   
    # Start the inactivity check task if not already running
    if not check_inactivity.is_running():
        check_inactivity.start()
    # FIXED: Start periodic memory cleanup task
    if not periodic_memory_cleanup.is_running():
        periodic_memory_cleanup.start()
        logging.info("[MEMORY] 🧹 Periodic memory cleanup task started (runs every hour)")
    # FIXED: Start Supabase keep-alive task
    if not keep_supabase_alive.is_running():
        keep_supabase_alive.start()
        logging.info("[SUPABASE] 🔄 Keep-alive task started (runs every 6 hours)")
    eventloop.event_loop = asyncio.get_running_loop()
    logging.info(f"Connected to Discord Gateway Region: {bot.latency:.2f} ms")
    logging.info(f'Logged in as {bot.user}')
    # Generate and cache invites without blocking the event loop
    asyncio.create_task(generate_and_cache_invites(bot))
    asyncio.create_task(sync_guilds_and_users(bot))

# FIXED: Clean up guild state when bot leaves a server
@bot.event
async def on_guild_remove(guild):
    """Clean up memory when bot is removed from a server"""
    try:
        from engine.commands.music import cleanup_guild_state
        cleanup_guild_state(guild.id)
        logging.info(f"[MEMORY] 🧹 Cleaned up state for guild {guild.name} (ID: {guild.id})")
    except Exception as e:
        logging.error(f"Failed to cleanup guild state on remove: {e}")

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

# Register the commands from moderation.py
moderation.kick.category = "Moderation"
moderation.ban.category = "Moderation"
moderation.purge.category = "Moderation"
moderation.mute.category = "Moderation"
moderation.unmute.category = "Moderation"
moderation.warn.category = "Moderation"
moderation.timeout.category = "Moderation"
bot.tree.add_command(moderation.kick)
bot.tree.add_command(moderation.ban)
bot.tree.add_command(moderation.purge)
bot.tree.add_command(moderation.mute)
bot.tree.add_command(moderation.unmute)
bot.tree.add_command(moderation.warn)
bot.tree.add_command(moderation.timeout)

# Register the commands from utility.py
utility.say_command.category = "Utility"
utility.emoji_command.category = "Utility"
utility.avatar_command.category = "Utility"
utility.banner_command.category = "Utility"
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
utility.image_command.category = "Utility"
utility.video.category = "Utility"
utility.imagine_command.category = "Utility"
utility.caption_command.category = "Utility"
utility.variation_command.category = "Utility"
utility.refine_command.category = "Utility"
utility.modify_command.category = "Utility"
utility.analyze_command.category = "Utility"
utility.youtube_command.category = "Utility"
utility.text_to_speech.category = "Utility"
utility.musicgen.category = "Utility"
utility.aisearch_command.category = "Utility"
utility.news_command.category = "Utility"
utility.chat_command.category = "Utility"
utility.reason_command.category = "Utility"
utility.edit_image_command.category = "Utility"
utility.welcome_enable.category = "Utility"
utility.welcome_disable.category = "Utility"
utility.welcome_message.category = "Utility"
utility.welcome_channel.category = "Utility"
utility.welcome_show.category = "Utility"
utility.welcome_reset.category = "Utility"
utility.animate_command.category = "Utility"
bot.tree.add_command(utility.say_command)
bot.tree.add_command(utility.emoji_command)
bot.tree.add_command(utility.avatar_command)
bot.tree.add_command(utility.banner_command)
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
bot.tree.add_command(utility.image_command)
bot.tree.add_command(utility.video)
bot.tree.add_command(utility.imagine_command)
bot.tree.add_command(utility.caption_command)
bot.tree.add_command(utility.variation_command)
bot.tree.add_command(utility.refine_command)
bot.tree.add_command(utility.modify_command)
bot.tree.add_command(utility.analyze_command)
bot.tree.add_command(utility.youtube_command)
bot.tree.add_command(utility.text_to_speech)
bot.tree.add_command(utility.musicgen)
bot.tree.add_command(utility.aisearch_command)
bot.tree.add_command(utility.news_command)
bot.tree.add_command(utility.chat_command)
bot.tree.add_command(utility.reason_command)
bot.tree.add_command(utility.edit_image_command)
bot.tree.add_command(utility.welcome_enable)
bot.tree.add_command(utility.welcome_disable)
bot.tree.add_command(utility.welcome_message)
bot.tree.add_command(utility.welcome_channel)
bot.tree.add_command(utility.welcome_show)
bot.tree.add_command(utility.welcome_reset)
bot.tree.add_command(utility.animate_command)

# Register the commands from fun.py
fun.roast_command.category = "Fun"
fun.compliment_command.category = "Fun"
fun.joke_command.category = "Fun"
fun.fact_command.category = "Fun"
fun.advice_command.category = "Fun"
fun.quote_command.category = "Fun"
fun.riddle_command.category = "Fun"
fun.meme_command.category = "Fun"
fun.dadjoke_command.category = "Fun"
fun.cowsay_command.category = "Fun"
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
fun.memegen_command.category = "Fun"
fun.soundboard_command.category = "Fun"
bot.tree.add_command(fun.roast_command)
bot.tree.add_command(fun.compliment_command)
bot.tree.add_command(fun.joke_command)
bot.tree.add_command(fun.fact_command)
bot.tree.add_command(fun.advice_command)
bot.tree.add_command(fun.quote_command)
bot.tree.add_command(fun.riddle_command)
bot.tree.add_command(fun.meme_command)
bot.tree.add_command(fun.dadjoke_command)
bot.tree.add_command(fun.cowsay_command)
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
bot.tree.add_command(fun.memegen_command)
bot.tree.add_command(fun.soundboard_command)

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
music.lyrics_command.category = "Music"
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
bot.tree.add_command(music.lyrics_command)

# Register the commands from misc.py
misc.steam.category = "Misc"
misc.steamlink.category = "Misc"
misc.steamunlink.category = "Misc"
misc.steamgame.category = "Misc"
misc.steamnews.category = "Misc"
misc.leaderboard.category = "Misc"
misc.rank.category = "Misc"
misc.itunes.category = "Misc"
misc.cat.category = "Misc"
misc.dog.category = "Misc"
misc.dogfact.category = "Misc"
bot.tree.add_command(misc.steam)
bot.tree.add_command(misc.steamlink)
bot.tree.add_command(misc.steamunlink)
bot.tree.add_command(misc.steamgame)
bot.tree.add_command(misc.steamnews)
bot.tree.add_command(misc.leaderboard)
bot.tree.add_command(misc.rank)
bot.tree.add_command(misc.itunes)
bot.tree.add_command(misc.cat)
bot.tree.add_command(misc.dog)
bot.tree.add_command(misc.dogfact)

"""
rpg.create_character.category = "RP/Economy"
rpg.stats.category = "RP/Economy"
rpg.inventory.category = "RP/Economy"
rpg.equip.category = "RP/Economy"
rpg.unequip.category = "RP/Economy"
rpg.use.category = "RP/Economy"
rpg.battle.category = "RP/Economy"
rpg.gift.category = "RP/Economy"
rpg.work.category = "RP/Economy"
bot.tree.add_command(rpg.create_character)
bot.tree.add_command(rpg.stats)
bot.tree.add_command(rpg.inventory)
bot.tree.add_command(rpg.equip)
bot.tree.add_command(rpg.unequip)
bot.tree.add_command(rpg.use)
bot.tree.add_command(rpg.battle)
bot.tree.add_command(rpg.gift)
bot.tree.add_command(rpg.work)
"""

@bot.event
async def on_guild_join(guild):
    """
    Event handler that triggers when the bot is added to a new guild (server).
    Sends the help embed to the 'general' channel or the first available text channel.
    """
    # Attempt to find a text channel that contains 'general' in its name
    general_channel = discord.utils.find(
        lambda c: 'general' in c.name.lower() and isinstance(c, discord.TextChannel), guild.channels
    )
    
    # If no 'general' channel is found, try all text channels until a suitable one is found
    if not general_channel:
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                general_channel = channel
                break
        else:
            general_channel = None
    
    # If a suitable channel is found, send the help embed
    if general_channel:
        embed = discord.Embed(title="Thanks for adding me!", description="I'm Seeyuh, a versatile Discord bot. Use `/help` to see all available commands.", color=discord.Color.green())
        try:
            await general_channel.send(embed=embed)
        except discord.Forbidden:
            print(f"Permission denied to send messages in {general_channel.name} of {guild.name}.")
        except Exception as e:
            print(f"Failed to send help message to {guild.name}: {e}")

# List of greeting emojis
greeting_emojis = ["👋", "😊", "😃", "🙌", "🤗"]

def _build_welcome_video_bytes(avatar_png_bytes: bytes, display_name: str, guild_name: str, guild_icon_bytes: bytes = None, bot_avatar_bytes: bytes = None) -> bytes:
    from io import BytesIO
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
    import numpy as np
    from moviepy.editor import ImageClip, AudioFileClip
    from moviepy.video.VideoClip import VideoClip
    from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
    from gtts import gTTS
    import edge_tts
    import asyncio
    import tempfile, os, random

    width, height = 1280, 720
    # Gradient background
    bg = Image.new('RGB', (width, height), '#0b1021')
    draw = ImageDraw.Draw(bg)
    for y in range(height):
        blend = y / height
        color = (
            int(11 + (25 - 11) * blend),
            int(16 + (55 - 16) * blend),
            int(33 + (105 - 33) * blend)
        )
        draw.line([(0, y), (width, y)], fill=color)

    # Soft vignette
    vignette = Image.new('L', (width, height), 0)
    vd = ImageDraw.Draw(vignette)
    vd.ellipse([(-int(width*0.2), -int(height*0.2)), (int(width*1.2), int(height*1.2))], fill=255)
    vignette = vignette.filter(ImageFilter.GaussianBlur(120))
    bg = Image.composite(bg, Image.new('RGB', (width, height), 'black'), ImageOps.invert(vignette).filter(ImageFilter.GaussianBlur(0)))

    # Enhanced decorative elements
    for cx, cy, r, color in [
        (width*0.15, height*0.25, 200, (52, 152, 219)),
        (width*0.85, height*0.75, 240, (155, 89, 182)),
        (width*0.75, height*0.2, 180, (46, 204, 113)),
        (width*0.3, height*0.8, 160, (241, 196, 15)),
    ]:
        # Multiple layered glows for depth
        for layer, (scale, alpha) in enumerate([(1.2, 120), (0.8, 160), (0.5, 200)]):
            blob = Image.new('RGBA', (int(r*2*scale), int(r*2*scale)), (0, 0, 0, 0))
            bd = ImageDraw.Draw(blob)
            bd.ellipse([(0, 0), (r*2*scale, r*2*scale)], fill=color + (alpha,))
            blob = blob.filter(ImageFilter.GaussianBlur(int(80*scale)))
            bg.paste(blob, (int(cx - r*scale), int(cy - r*scale)), blob)

    # Avatar circle with ring and shadow
    avatar = Image.open(BytesIO(avatar_png_bytes)).convert('RGBA')
    avatar = avatar.resize((360, 360), Image.LANCZOS)
    mask = Image.new('L', (360, 360), 0)
    ImageDraw.Draw(mask).ellipse([(0, 0), (360, 360)], fill=255)
    avatar = Image.composite(avatar, Image.new('RGBA', (360, 360), (0, 0, 0, 0)), mask)
    # Shadow
    shadow = Image.new('RGBA', (380, 380), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse([(0, 0), (380, 380)], fill=(0, 0, 0, 160))
    shadow = shadow.filter(ImageFilter.GaussianBlur(20))
    bg.paste(shadow, (int(width*0.08) - 10, int(height*0.45) - 10), shadow)
    bg.paste(avatar, (int(width*0.08), int(height*0.45)), avatar)
    # Ring
    ring = Image.new('RGBA', (380, 380), (0, 0, 0, 0))
    ring_d = ImageDraw.Draw(ring)
    ring_d.ellipse([(10, 10), (370, 370)], outline=(255, 255, 255, 220), width=6)
    ring = ring.filter(ImageFilter.GaussianBlur(1))
    bg.paste(ring, (int(width*0.08) - 10, int(height*0.45) - 10), ring)

    # Fonts
    def load_font(path_candidates, size):
        for p in path_candidates:
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except Exception:
                    pass
        return ImageFont.load_default()

    bold_font = load_font([
        "assets/fonts/arialbd.ttf",
        "assets/fonts/ARIALBD 1.TTF",
        "assets/fonts/ARIALNB.TTF",
    ], 78)
    regular_font = load_font([
        "assets/fonts/arial.ttf",
        "assets/fonts/ArialCE.ttf",
        "assets/fonts/ARIALN.TTF",
    ], 44)

    # Text with shadow
    def draw_text_with_shadow(img, xy, text, font, fill=(255, 255, 255), shadow=(0, 0, 0), offset=(2, 2)):
        d = ImageDraw.Draw(img)
        x, y = xy
        d.text((x + offset[0], y + offset[1]), text, font=font, fill=shadow)
        d.text((x, y), text, font=font, fill=fill)

    # Prepare server icon and bot avatar for animation
    guild_icon = None
    if guild_icon_bytes:
        try:
            guild_icon = Image.open(BytesIO(guild_icon_bytes)).convert('RGBA')
            guild_icon = guild_icon.resize((120, 120), Image.LANCZOS)
            # Circular mask for guild icon
            mask = Image.new('L', (120, 120), 0)
            ImageDraw.Draw(mask).ellipse([(0, 0), (120, 120)], fill=255)
            guild_icon = Image.composite(guild_icon, Image.new('RGBA', (120, 120), (0, 0, 0, 0)), mask)
        except Exception:
            guild_icon = None
    
    bot_avatar = None
    if bot_avatar_bytes:
        try:
            bot_avatar = Image.open(BytesIO(bot_avatar_bytes)).convert('RGBA')
            bot_avatar = bot_avatar.resize((100, 100), Image.LANCZOS)
            # Circular mask for bot avatar
            mask = Image.new('L', (100, 100), 0)
            ImageDraw.Draw(mask).ellipse([(0, 0), (100, 100)], fill=255)
            bot_avatar = Image.composite(bot_avatar, Image.new('RGBA', (100, 100), (0, 0, 0, 0)), mask)
        except Exception:
            bot_avatar = None

    title = f"Welcome, {display_name}!"
    subtitle = f"to {guild_name}"

    # Text positioning (more left, balanced to avoid avatar and cutoff)
    tx = int(width*0.15)
    ty = int(height*0.15)
    draw_text_with_shadow(bg, (tx, ty), title, bold_font)
    draw_text_with_shadow(bg, (tx, ty + 90), subtitle, regular_font, fill=(220, 240, 255))

    # Convert to frame with animated background
    video_duration = 6.0
    
    def make_animated_frame(t):
        """Create animated background with shifting colors"""
        # Create animated gradient background
        bg_animated = Image.new('RGB', (width, height), '#0b1021')
        draw_animated = ImageDraw.Draw(bg_animated)
        
        # Time-based color shift
        time_factor = t / video_duration
        
        for y in range(height):
            blend = y / height
            
            # Add subtle wave animation to the gradient
            wave_offset = 0.1 * np.sin(2 * np.pi * y / 200 + t * 2)
            blend = max(0, min(1, blend + wave_offset))
            
            # Animated color values that shift over time
            base_r = int(11 + (25 - 11) * blend + 10 * np.sin(t * 1.5))
            base_g = int(16 + (55 - 16) * blend + 15 * np.sin(t * 1.2 + 1))
            base_b = int(33 + (105 - 33) * blend + 20 * np.sin(t * 0.8 + 2))
            
            # Clamp values
            color = (
                max(0, min(255, base_r)),
                max(0, min(255, base_g)),
                max(0, min(255, base_b))
            )
            draw_animated.line([(0, y), (width, y)], fill=color)
        
        # Enhanced animated vignette
        vignette_animated = Image.new('L', (width, height), 0)
        vd_animated = ImageDraw.Draw(vignette_animated)
        
        # Pulsing vignette that breathes
        vignette_intensity = 0.7 + 0.3 * np.sin(t * 1.8)
        vd_animated.ellipse([
            (-int(width*0.2), -int(height*0.2)), 
            (int(width*1.2), int(height*1.2))
        ], fill=int(255 * vignette_intensity))
        vignette_animated = vignette_animated.filter(ImageFilter.GaussianBlur(120))
        bg_animated = Image.composite(bg_animated, Image.new('RGB', (width, height), 'black'), 
                                    ImageOps.invert(vignette_animated))
        
        # Enhanced animated decorative elements
        for i, (cx, cy, r, base_color) in enumerate([
            (width*0.15, height*0.25, 200, (52, 152, 219)),
            (width*0.85, height*0.75, 240, (155, 89, 182)),
            (width*0.75, height*0.2, 180, (46, 204, 113)),
            (width*0.3, height*0.8, 160, (241, 196, 15)),
        ]):
            # Animated position and intensity
            phase = i * 0.5
            animated_cx = cx + 30 * np.sin(t * 0.8 + phase)
            animated_cy = cy + 20 * np.cos(t * 1.2 + phase)
            animated_r = r + 30 * np.sin(t * 2 + phase)
            
            # Animated color with breathing effect
            color_mult = 0.8 + 0.4 * np.sin(t * 1.5 + phase)
            animated_color = (
                int(base_color[0] * color_mult),
                int(base_color[1] * color_mult),
                int(base_color[2] * color_mult)
            )
            
            # Multiple layered glows for depth
            for layer, (scale, alpha) in enumerate([(1.2, 120), (0.8, 160), (0.5, 200)]):
                blob = Image.new('RGBA', (int(animated_r*2*scale), int(animated_r*2*scale)), (0, 0, 0, 0))
                bd = ImageDraw.Draw(blob)
                final_alpha = int(alpha * (0.6 + 0.4 * np.sin(t * 2.5 + phase + layer)))
                bd.ellipse([(0, 0), (animated_r*2*scale, animated_r*2*scale)], 
                          fill=animated_color + (final_alpha,))
                blob = blob.filter(ImageFilter.GaussianBlur(int(80*scale)))
                
                # Ensure coordinates are within bounds
                paste_x = max(0, min(width - blob.width, int(animated_cx - animated_r*scale)))
                paste_y = max(0, min(height - blob.height, int(animated_cy - animated_r*scale)))
                bg_animated.paste(blob, (paste_x, paste_y), blob)
        
        # Copy static elements (avatar, icons, text) onto animated background
        bg_animated.paste(avatar, (int(width*0.08), int(height*0.45)), avatar)
        bg_animated.paste(ring, (int(width*0.08) - 10, int(height*0.45) - 10), ring)
        
        # Re-apply server icon and bot avatar if available
        if guild_icon is not None:
            try:
                bg_animated.paste(guild_icon, (width - 180, 40), guild_icon)
            except:
                pass
        
        if bot_avatar is not None:
            try:
                bg_animated.paste(bot_avatar, (width - 140, height - 140), bot_avatar)
            except:
                pass
        
        # Re-draw text with slight glow animation
        glow_intensity = 0.8 + 0.2 * np.sin(t * 3)
        text_glow = int(255 * glow_intensity)
        
        # Text with animated shadow
        draw_text_with_shadow(bg_animated, (tx, ty), title, bold_font, 
                            fill=(text_glow, text_glow, text_glow))
        draw_text_with_shadow(bg_animated, (tx, ty + 90), subtitle, regular_font, 
                            fill=(int(220*glow_intensity), int(240*glow_intensity), text_glow))
        
        return np.array(bg_animated)
    
    # Create video clip with animated background
    base_clip = VideoClip(make_animated_frame).set_duration(video_duration)

    # Random TTS selection
    spoken = f"Welcome {display_name} to {guild_name}."
    
    async def generate_audio(text, path):
        # Updated list with verified working voices from Edge TTS 7.2.0
        edge_voices = [
            "en-US-AriaNeural",         # Female
            "en-US-JennyNeural",        # Female  
            "en-US-GuyNeural",          # Male
            "en-US-ChristopherNeural",  # Male
            "en-US-AndrewNeural",       # Male
            "en-US-EmmaNeural",         # Female
            "en-US-BrianNeural",        # Male
            "en-US-AvaNeural",          # Female
            "en-US-EricNeural",         # Male
            "en-US-MichelleNeural",     # Female
            "en-US-RogerNeural",        # Male
            "en-US-SteffanNeural"       # Male
        ]
        
        use_edge = random.choice([True, True, True, True, True, True, True, True, True, True, True, True, False])  # 95% chance for Edge TTS
        
        if use_edge:
            # Try multiple voices if one fails
            tried_voices = set()
            max_attempts = min(3, len(edge_voices))
            
            for attempt in range(max_attempts):
                try:
                    remaining_voices = [v for v in edge_voices if v not in tried_voices]
                    if not remaining_voices:
                        remaining_voices = edge_voices  # Reset if all tried
                        
                    voice = random.choice(remaining_voices)
                    tried_voices.add(voice)
                    
                    print(f"[WELCOME] Attempt {attempt + 1}: Using Edge TTS voice: {voice}")
                    
                    # Clean up any existing file first
                    if os.path.exists(path):
                        try:
                            os.remove(path)
                        except:
                            pass
                    
                    communicate = edge_tts.Communicate(text, voice)
                    await communicate.save(path)
                    
                    # Verify the file was created and has content
                    if os.path.exists(path) and os.path.getsize(path) > 0:
                        size = os.path.getsize(path)
                        print(f"[WELCOME] ✅ Edge TTS succeeded with {voice} ({size} bytes)")
                        return
                    else:
                        print(f"[WELCOME] ⚠️ Edge TTS created empty/no file with {voice}")
                        
                except Exception as e:
                    print(f"[WELCOME] ❌ Edge TTS failed with {voice}: {e}")
                    continue
            
            print(f"[WELCOME] All Edge TTS attempts failed, falling back to gTTS")
        
        # gTTS fallback
        print(f"[WELCOME] Using gTTS {'(fallback)' if use_edge else '(by choice)'}")
        try:
            tts = gTTS(text=text, lang='en', tld='com', slow=False)
            tts.save(path)
            
            if os.path.exists(path) and os.path.getsize(path) > 0:
                size = os.path.getsize(path)
                print(f"[WELCOME] ✅ gTTS succeeded ({size} bytes)")
            else:
                print(f"[WELCOME] ❌ gTTS failed to create valid file")
        except Exception as e:
            print(f"[WELCOME] ❌ gTTS error: {e}")
            raise
    
    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, 'welcome.mp3')
        video_path = os.path.join(tmpdir, 'welcome.mp4')
        
        # Generate audio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(generate_audio(spoken, audio_path))
        finally:
            loop.close()
        audio_clip = None
        final = None
        glow_clip = None
        try:
            audio_clip = AudioFileClip(audio_path)
            # Align durations to avoid reading past audio end
            safe_duration = min(base_clip.duration or 0, audio_clip.duration or 0) or (audio_clip.duration or base_clip.duration)
            base_clip = base_clip.set_duration(safe_duration)
            audio_clip = audio_clip.subclip(0, safe_duration)
            # Multiple dynamic overlays
            width_i, height_i = width, height
            
            # Prismatic light sweep
            def prismatic_frame(t: float):
                overlay = Image.new('RGBA', (width_i, height_i), (0, 0, 0, 0))
                d = ImageDraw.Draw(overlay)
                progress = t / safe_duration
                
                # Multiple sweeping bands
                for band_idx, (speed, color, thickness) in enumerate([
                    (1.2, (52, 152, 219), 80),
                    (0.8, (155, 89, 182), 60),
                    (1.5, (46, 204, 113), 40),
                ]):
                    band_x = int((progress * speed) * (width_i + thickness*2)) - thickness
                    for i in range(-thickness, thickness, 2):
                        alpha = max(0, 200 - abs(i) * 3)
                        d.rectangle([(band_x + i, 0), (band_x + i + 1, height_i)], 
                                  fill=color + (alpha // 12,))
                return np.array(overlay.convert('RGB'))
            
            # Particle effects
            def particle_frame(t: float):
                overlay = Image.new('RGBA', (width_i, height_i), (0, 0, 0, 0))
                d = ImageDraw.Draw(overlay)
                rng = np.random.RandomState(int(t * 1000) % 1000)
                
                num_particles = 40
                for i in range(num_particles):
                    # Floating particles
                    x = (rng.random() * width_i + 50 * np.sin(t * 2 + i)) % width_i
                    y = (rng.random() * height_i + 30 * np.cos(t * 1.5 + i)) % height_i
                    size = 2 + int(3 * np.sin(t * 3 + i))
                    alpha = int(100 + 80 * np.sin(t * 4 + i * 0.5))
                    colors = [(52, 152, 219), (155, 89, 182), (46, 204, 113), (241, 196, 15)]
                    color = colors[i % len(colors)]
                    d.ellipse([(x-size, y-size), (x+size, y+size)], fill=color + (max(0, alpha),))
                
                return np.array(overlay.convert('RGB'))
            
            prismatic_clip = VideoClip(prismatic_frame).set_duration(safe_duration).set_fps(30).set_opacity(0.25)
            particle_clip = VideoClip(particle_frame).set_duration(safe_duration).set_fps(24).set_opacity(0.15)
            
            final = CompositeVideoClip([base_clip, prismatic_clip, particle_clip]).set_audio(audio_clip)
            final.write_videofile(
                video_path,
                fps=30,
                codec='libx264',
                audio_codec='aac',
                preset='medium',
                threads=2,
                verbose=False,
                logger=None
            )
        finally:
            if final is not None:
                try:
                    final.close()
                except Exception:
                    pass
            try:
                base_clip.close()
            except Exception:
                pass
            if audio_clip is not None:
                try:
                    audio_clip.close()
                except Exception:
                    pass
            for clip in [prismatic_clip, particle_clip]:
                try:
                    if clip is not None:
                        clip.close()
                except Exception:
                    pass
        with open(video_path, 'rb') as f:
            return f.read()


@bot.event
async def on_member_join(member):
    # Check welcome settings first
    try:
        from engine.db import get_welcome_settings
        settings = get_welcome_settings(str(member.guild.id))
        
        # If welcome is disabled, do nothing
        if not settings.get('enabled', True):
            print(f"[WELCOME] Welcome disabled for guild {member.guild.name}")
            return
            
        # Determine channel - use configured channel or fallback to default
        channel = None
        if settings.get('channel_id'):
            try:
                channel = member.guild.get_channel(int(settings['channel_id']))
                if not channel or not channel.permissions_for(member.guild.me).send_messages:
                    channel = None
            except (ValueError, AttributeError):
                channel = None
        
        # Fallback to default channel selection
        if not channel:
            preferred_names = ["welcome", "w3lcome", "welcome-channel"]
            for name in preferred_names:
                channel = discord.utils.get(member.guild.text_channels, name=name)
                if channel and channel.permissions_for(member.guild.me).send_messages:
                    break
            else:
                channel = member.guild.system_channel or next((c for c in member.guild.text_channels if c.permissions_for(member.guild.me).send_messages), None)

        if not channel:
            print(f"[WELCOME] No valid channel found for guild {member.guild.name}")
            return

        # Get custom message or use default
        custom_message = settings.get('message')
        if custom_message:
            # Replace placeholders in custom message
            welcome_text = custom_message.format(
                mention=member.mention,
                user=member.display_name,
                guild=member.guild.name,
                intro=f"Welcome {member.display_name}",
                roles=len(member.guild.roles)
            )
        else:
            # Default message
            welcome_text = f"Welcome {member.mention} to {member.guild.name}."

        avatar_url = member.display_avatar.replace(size=256, static_format='png').url
        async with aiohttp.ClientSession() as session:
            async with session.get(avatar_url) as resp:
                avatar_bytes = await resp.read() if resp.status == 200 else None
        
        if not avatar_bytes:
            await channel.send(welcome_text)
            return

        # Get guild icon and bot avatar
        guild_icon_bytes = None
        bot_avatar_bytes = None
        
        try:
            if member.guild.icon:
                icon_url = member.guild.icon.replace(size=256, static_format='png').url
                async with aiohttp.ClientSession() as session:
                    async with session.get(icon_url) as resp:
                        if resp.status == 200:
                            guild_icon_bytes = await resp.read()
        except Exception:
            pass
        
        try:
            if bot.user.avatar:
                bot_url = bot.user.avatar.replace(size=256, static_format='png').url
                async with aiohttp.ClientSession() as session:
                    async with session.get(bot_url) as resp:
                        if resp.status == 200:
                            bot_avatar_bytes = await resp.read()
        except Exception:
            pass

        # Offload heavy rendering
        loop = asyncio.get_running_loop()
        video_bytes = await loop.run_in_executor(None, _build_welcome_video_bytes, avatar_bytes, member.display_name, member.guild.name, guild_icon_bytes, bot_avatar_bytes)
        import io
        file = discord.File(fp=io.BytesIO(video_bytes), filename='welcome.mp4')
        await channel.send(content=welcome_text, file=file)
        
    except Exception as e:
        logging.exception(f"Failed to send welcome for {member}: {e}")
        # Fallback to simple message
        try:
            # Try to find any channel to send fallback message
            fallback_channel = member.guild.system_channel or next((c for c in member.guild.text_channels if c.permissions_for(member.guild.me).send_messages), None)
            if fallback_channel:
                await fallback_channel.send(f"Welcome {member.mention} to {member.guild.name}.")
        except Exception:
            pass  # If even fallback fails, just log and continue

@bot.event
async def on_message(message):
    import random  # Import random at the top to avoid UnboundLocalError
    
    # CRITICAL: Ignore bot messages FIRST to prevent infinite loops
    if message.author.bot:
        return
    
    # Also check for direct image URLs in replied-to messages
    if (bot.user.mentioned_in(message) or "seeyuh" in message.content.lower()) and message.reference:
        try:
            original_message = await message.channel.fetch_message(message.reference.message_id)
            import re, io
            from PIL import Image
            image_url_pattern = r'(https?://[^\s]+\.(?:png|jpg|jpeg|webp|gif|bmp|tiff|svg)(?:\?[^\s]*)?)'
            matches = re.findall(image_url_pattern, original_message.content, re.IGNORECASE)
            if matches:
                img_url = matches[0]
                async with message.channel.typing():
                    try:
                        import aiohttp
                        async with aiohttp.ClientSession() as session:
                            async with session.get(img_url) as resp:
                                if resp.status == 200:
                                    img_bytes = await resp.read()
                                    pil_image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                                else:
                                    await message.reply("Failed to download the image from the replied message's URL.")
                                    return
                        # Defer to unified multimodal handler for links as well
                        from engine.ai.gemini_multimodal import handle_message_files
                        handled = await handle_message_files(bot, message)
                        if handled is not None:
                            return
                    except Exception as e:
                        import logging
                        logging.error(f"Error processing replied image URL: {e}")
                        await message.reply(f"❌ Error processing replied image URL: {str(e)}")
                        return
        except discord.NotFound:
            await message.reply("The original message could not be found.")
            return
    # If the message includes attachments/links, always route to multimodal and stop further handling
    if bot.user.mentioned_in(message) or "seeyuh" in message.content.lower():
        import re
        if message.attachments or re.search(r"https?://[^\s]+", message.content or "", re.IGNORECASE):
            async with message.channel.typing():
                from engine.ai.gemini_multimodal import handle_message_files
                await handle_message_files(bot, message)
            return
    
    # Ignore messages that mention @everyone or @here
    if "@everyone" in message.content or "@here" in message.content:
        return
    
    # Check if the bot is mentioned or its name is used
    if bot.user.mentioned_in(message) or "seeyuh" in message.content.lower():
        # Check if there is no other content in the message
        if (message.content.strip() == f"<@{bot.user.id}>" or message.content.strip().lower() == "seeyuh") and not message.attachments and not message.reference:
            # React with a random greeting emoji
            await message.add_reaction(random.choice(greeting_emojis))
            return
        if random.random() < 0.001:  # 0.1% chance
            await message.channel.send(
                "If you enjoy using this bot, consider supporting its development with a small donation: https://paypal.me/arkodeepsen"
            )
            pass
        
    # Check if the message has attachments and bot is mentioned
    if (bot.user.mentioned_in(message) or "seeyuh" in message.content.lower()):
        if message.attachments:
            async with message.channel.typing():  # Show typing indicator
                responses = []
                for attachment in message.attachments:
                    if attachment.size > 10 * 1024 * 1024:  # Check if the attachment size exceeds 10 MB
                        error_message = "Attachment size exceeds 10 MB limit. Please upload a smaller file."
                        await message.reply(error_message)
                        responses.append(error_message)
                        continue  # Skip to the next attachment
                    if attachment.content_type and (
                        attachment.content_type.startswith("image/") or
                        attachment.content_type.startswith("video/") or
                        attachment.content_type.startswith("audio/") or
                        attachment.content_type == "application/pdf" or
                        attachment.content_type == "application/javascript" or
                        attachment.content_type == "application/java" or
                        attachment.content_type.startswith("text/")
                    ):
                        if attachment.content_type == "image/bmp" or attachment.content_type == "text/csv":
                            error_message = (
                                f"Unsupported file type '{attachment.content_type}'. "
                                "These files are not supported. Please try different file types."
                            )
                            await message.reply(error_message)
                            responses.append(error_message)
                        else:
                            resp = await handle_attachment(bot, message, attachment)
                            responses.append(resp)
                    else:
                        error_message = (
                            f"Unsupported file type '{attachment.content_type}'. "
                            "Please upload an image, video, audio, PDF, plain text, or text-based code file."
                        )
                        await message.reply(error_message)
                        responses.append(error_message)
    
            # Start the background task to retry the entry update
            bot.loop.create_task(retry_check_and_update_guild_entry(
                supabase,
                str(message.guild.id),
                message.guild.name
            ))
    
            # Save the user message and bot responses
            current_query = message.content.strip().replace(f"<@{bot.user.id}>", "").replace("seeyuh", "").strip()
            combined_response = '\n'.join(responses)
            bot.loop.create_task(save_message_to_db(
                str(message.guild.id),
                message.author,
                current_query,
                combined_response
            ))
            return  # Stop further processing
    
        # Check if the message is a reply to another message that has attachments
        if message.reference:
            try:
                original_message = await message.channel.fetch_message(message.reference.message_id)
                if original_message.attachments:
                    async with message.channel.typing():  # Show typing indicator
                        responses = []
                        for attachment in original_message.attachments:
                            if attachment.size > 10 * 1024 * 1024:  # Check if the attachment size exceeds 10 MB
                                error_message = "Attachment size exceeds 10 MB limit. Please upload a smaller file."
                                await message.reply(error_message)
                                responses.append(error_message)
                                continue  # Skip to the next attachment
                            if attachment.content_type and (
                                attachment.content_type.startswith("image/") or
                                attachment.content_type.startswith("video/") or
                                attachment.content_type.startswith("audio/") or
                                attachment.content_type == "application/pdf" or
                                attachment.content_type == "application/javascript" or
                                attachment.content_type == "application/java" or
                                attachment.content_type.startswith("text/")
                            ):
                                if attachment.content_type == "image/bmp" or attachment.content_type == "text/csv":
                                    error_message = (
                                        f"Unsupported file type '{attachment.content_type}'. "
                                        "These files are not supported. Please try different file types."
                                    )
                                    await message.reply(error_message)
                                    responses.append(error_message)
                                else:
                                    resp = await handle_attachment(bot, message, attachment)
                                    responses.append(resp)
                            else:
                                error_message = (
                                    f"Unsupported file type '{attachment.content_type}'. "
                                    "Please upload an image, video, audio, PDF, plain text, or text-based code file."
                                )
                                await message.reply(error_message)
                                responses.append(error_message)
    
                    # Start the background task to retry the entry update
                    bot.loop.create_task(retry_check_and_update_guild_entry(
                        supabase,
                        str(message.guild.id),
                        message.guild.name
                    ))
    
                    # Save the user message and bot responses
                    current_query = message.content.strip().replace(f"<@{bot.user.id}>", "").replace("seeyuh", "").strip()
                    combined_response = '\n'.join(responses)
                    bot.loop.create_task(save_message_to_db(
                        str(message.guild.id),
                        message.author,
                        current_query,
                        combined_response
                    ))
                    return  # Stop further processing
            except discord.NotFound:
                await message.reply("The original message could not be found.")
                return  # Stop further processing

    if message.content.lower().startswith("say") or (("seeyuh" in message.content.lower() or bot.user.mentioned_in(message)) and "say" in message.content.lower()):
        content = message.content.strip()
        command_content = content.replace(f"<@{bot.user.id}>", "").strip()
        command_content = command_content.replace("seeyuh", "").strip()
        words = command_content.split()
        if words and words[0].lower() == "say":
            response_message = " ".join(words[1:])
            await message.reply(response_message)
            return  # Stop further processing if this condition is met

    if (bot.user.mentioned_in(message) or "seeyuh" in message.content.lower()) and "chat meme" in message.content.lower():
                progress_msg = await message.channel.send("🎬 **Generating chat video...** \n⏳ **Progress:** 0% - Analyzing messages")
                try:
                    messages = []
                    processed_content = set()  # Track unique message content to avoid duplicates
                    trigger_id = message.id  # Store the ID of the trigger message
                    
                    # ENHANCED message collection with dynamic pool sizing
                    import datetime
                    
                    # Calculate dynamic pool based on channel activity
                    base_limit = 150  # Increased base limit
                    
                    # Check recent channel activity to adjust pool size
                    recent_msgs = 0
                    cutoff_time = message.created_at - datetime.timedelta(hours=2)
                    
                    async for quick_msg in message.channel.history(limit=50, before=message):
                        if quick_msg.created_at > cutoff_time:
                            recent_msgs += 1
                        else:
                            break
                    
                    # Dynamic pool: more active channels get larger pools
                    if recent_msgs > 30:
                        pool_limit = 300  # Very active channel
                    elif recent_msgs > 15:
                        pool_limit = 250  # Active channel  
                    elif recent_msgs > 5:
                        pool_limit = 200  # Moderate activity
                    else:
                        pool_limit = 150  # Low activity
                    
                    print(f"[MEME] Recent activity: {recent_msgs} messages, using pool size: {pool_limit}")
                    
                    # Update progress - message collection phase
                    await progress_msg.edit(content="🎬 **Generating chat video...** \n⏳ **Progress:** 10% - Collecting messages")
                    
                    async for msg in message.channel.history(limit=pool_limit):
                        # Skip trigger message and any message containing "chat meme"
                        if msg.id != trigger_id and not ("chat meme" in msg.content.lower() or "chat video" in msg.content.lower()):
                            
                            # Handle video/GIF attachments (prioritize these)
                            video_attachments = [att for att in msg.attachments if att.content_type and 
                                                (att.content_type.startswith("video/") or 
                                                 att.filename.lower().endswith(".gif"))]
                            
                            # Handle regular user messages with content
                            if not msg.content.startswith('/') and not msg.content.startswith('$'):
                                if msg.content.strip() and msg.content.strip() not in processed_content:
                                    # Strip out custom emoji format (<:name:id>) but keep regular text
                                    clean_content = re.sub(r'<a?:[a-zA-Z0-9_]+:[0-9]+>', '', msg.content)
                                    
                                    # Only proceed if there's meaningful text after cleaning
                                    if clean_content.strip():
                                        # Check for reply attachments
                                        reply_attachments = []
                                        if msg.reference:
                                            try:
                                                reply_msg = await message.channel.fetch_message(msg.reference.message_id)
                                                if reply_msg.attachments:
                                                    reply_attachments = [att.url for att in reply_msg.attachments if 
                                                                       att.content_type and (att.content_type.startswith("image/") or 
                                                                                            att.content_type.startswith("video/") or 
                                                                                            att.filename.lower().endswith((".gif", ".jpg", ".jpeg", ".png", ".webp")))]
                                                    print(f"[REPLY] Found {len(reply_attachments)} attachments in referenced message")
                                            except:
                                                pass  # Ignore errors fetching reply
                                        
                                        # Combine message attachments with reply attachments
                                        all_attachment_urls = [att.url for att in msg.attachments if att.content_type and 
                                                             (att.content_type.startswith("image/") or 
                                                              att.content_type.startswith("video/") or 
                                                              att.filename.lower().endswith(".gif"))] + reply_attachments
                                        
                                        messages.append({
                                            "name": msg.author.display_name,
                                            "message": clean_content,
                                            "avatar": str(msg.author.display_avatar.url),
                                            "user_id": str(msg.author.id),
                                            "has_image": bool(msg.attachments and any(att.content_type and 
                                                           (att.content_type.startswith("image/") or 
                                                            att.content_type.startswith("video/") or 
                                                            att.filename.lower().endswith(".gif")) 
                                                           for att in msg.attachments)) or bool(reply_attachments),
                                            "image_url": str(next((att.url for att in msg.attachments if 
                                                              att.content_type and (att.content_type.startswith("image/") or 
                                                                                  att.content_type.startswith("video/") or 
                                                                                  att.filename.lower().endswith(".gif"))), None)) or (reply_attachments[0] if reply_attachments else None),
                                            "attachment_urls": all_attachment_urls,
                                            "is_video": bool(video_attachments),
                                            "is_bot": msg.author.bot,
                                            "guild": message.guild  # Add guild reference for mention formatting
                                        })
                                        processed_content.add(msg.content.strip())
                                # Include messages with ANY media (images, videos, GIFs) even if they have no text
                                elif any(att.content_type and (att.content_type.startswith("image/") or 
                                                              att.content_type.startswith("video/") or 
                                                              att.filename.lower().endswith((".gif", ".jpg", ".jpeg", ".png", ".webp"))) 
                                       for att in msg.attachments):
                                    # Get all media attachments
                                    media_attachments = [att for att in msg.attachments if 
                                                       att.content_type and (att.content_type.startswith("image/") or 
                                                                           att.content_type.startswith("video/") or
                                                                           att.filename.lower().endswith((".gif", ".jpg", ".jpeg", ".png", ".webp")))]
                                    
                                    if media_attachments:
                                        first_attachment = media_attachments[0]
                                        is_video = (first_attachment.content_type.startswith("video/") or 
                                                  first_attachment.filename.lower().endswith(".gif"))
                                        is_image = first_attachment.content_type.startswith("image/")
                                        
                                        # Descriptive message based on attachment type
                                        if is_video:
                                            desc_message = "📹 *shared a video*" if first_attachment.content_type.startswith("video/") else "🎮 *shared a GIF*"
                                        else:
                                            desc_message = "🖼️ *shared an image*"
                                        
                                        # Check for reply attachments in media-only messages too
                                        reply_attachments = []
                                        if msg.reference:
                                            try:
                                                reply_msg = await message.channel.fetch_message(msg.reference.message_id)
                                                if reply_msg.attachments:
                                                    reply_attachments = [att.url for att in reply_msg.attachments if 
                                                                       att.content_type and (att.content_type.startswith("image/") or 
                                                                                            att.content_type.startswith("video/") or 
                                                                                            att.filename.lower().endswith((".gif", ".jpg", ".jpeg", ".png", ".webp")))]
                                            except:
                                                pass
                                        
                                        # Combine media attachments with reply attachments
                                        all_media_urls = [att.url for att in media_attachments] + reply_attachments
                                        
                                        messages.append({
                                            "name": msg.author.display_name,
                                            "message": desc_message,
                                            "avatar": str(msg.author.display_avatar.url),
                                            "user_id": str(msg.author.id),
                                            "has_image": True,
                                            "image_url": str(first_attachment.url) if not reply_attachments else reply_attachments[0],
                                            "attachment_urls": all_media_urls,
                                            "is_video": is_video,
                                            "is_bot": msg.author.bot,
                                            "guild": message.guild
                                        })
                            
                            # Include bot messages with videos/GIFs
                            elif msg.author.bot and msg.attachments:
                                media_attachments = [att for att in msg.attachments if 
                                                  att.content_type and (att.content_type.startswith("image/") or 
                                                                     att.content_type.startswith("video/") or
                                                                     att.filename.lower().endswith(".gif"))]
                                
                                if media_attachments:
                                    is_video = media_attachments[0].content_type.startswith("video/") or media_attachments[0].filename.lower().endswith(".gif")
                                    
                                    # Clean bot message content from emoji
                                    clean_content = re.sub(r'<a?:[a-zA-Z0-9_]+:[0-9]+>', '', msg.content) if msg.content else ""
                                    
                                    # Check for reply attachments in bot messages too
                                    reply_attachments = []
                                    if msg.reference:
                                        try:
                                            reply_msg = await message.channel.fetch_message(msg.reference.message_id)
                                            if reply_msg.attachments:
                                                reply_attachments = [att.url for att in reply_msg.attachments if 
                                                                   att.content_type and (att.content_type.startswith("image/") or 
                                                                                        att.content_type.startswith("video/") or 
                                                                                        att.filename.lower().endswith((".gif", ".jpg", ".jpeg", ".png", ".webp")))]
                                        except:
                                            pass
                                    
                                    # Combine bot attachments with reply attachments
                                    all_bot_urls = [att.url for att in media_attachments] + reply_attachments
                                    
                                    messages.append({
                                        "name": msg.author.display_name,
                                        "message": clean_content if clean_content.strip() else 
                                                  ("🎥 *shared a video*" if is_video else "🖼️ *shared an image*"),
                                        "avatar": str(msg.author.display_avatar.url),
                                        "user_id": str(msg.author.id),
                                        "has_image": True,
                                        "image_url": str(media_attachments[0].url) if not reply_attachments else reply_attachments[0],
                                        "attachment_urls": all_bot_urls,
                                        "is_video": is_video,
                                        "is_bot": msg.author.bot,
                                        "guild": message.guild
                                    })
                        
                        # Dynamic message limits based on server boost level
                        boost_level = message.guild.premium_tier if message.guild else 0
                        if boost_level >= 3:
                            message_limit = 200  # Level 3: 200 messages
                        elif boost_level >= 2:
                            message_limit = 100  # Level 2: 100 messages
                        else:
                            message_limit = 20   # Level 0/1: 20 messages
                        
                        if len(messages) >= message_limit:
                            break
                            
                    if len(messages) < 3:
                        await message.reply("Not enough valid messages to create a meme! Need at least 3 messages.")
                        return
                    
                    messages = messages[::-1]  # Reverse to get chronological order
                    
                    # Create a dynamic duration video with progress updates (duration calculated from audio)
                    video_bytes = await generate_meme_video_with_progress(messages, duration=None, progress_msg=progress_msg, guild=message.guild)
                    
                    file = discord.File(fp=video_bytes, filename="chat_meme_seeyuh.mp4")
                    await message.reply("Here's your next level chat meme! 😎🔥", file=file)
                    return
                except Exception as e:
                    await message.reply(f"Sorry, I couldn't create the meme: {str(e)}")
                    return
              
    if any(phrase in message.content.lower() for phrase in ["thick of it", "thickofit"]):
        link = "https://www.youtube.com/watch?v=At8v_Yc044Y"
        lyrics1 = """
        I'm in the thick of it, everybody knows
        They know me where it snows, I skied in and they froze
        I don't know no nothin' 'bout no ice, I'm just cold
        Forty somethin' milli' subs or so, I've been told
        I'm in my prime and this ain't even final form
        They knocked me down, but still, my feet, they find the floor
        I went from living rooms straight out to sold-out tours
        Life's a fight, but trust, I'm ready for the war
        """
        lyrics2 = """
        Woah-oh-oh
        This is how the story goes
        Woah-oh-oh
        I guess this is how the story goes
        """
        lyrics3 = """
        I'm in the thick of it, everybody knows
        They know me where it snows, I skied in and they froze
        I don't know no nothin' 'bout no ice, I'm just cold
        Forty somethin' milli' subs or so, I've been told
        From the screen to the ring, to the pen, to the king
        Where's my crown? That's my bling
        Always drama when I ring
        See, I believe that if I see it in my heart
        Smash through the ceiling 'cause I'm reachin' for the stars
        """
        lyrics4 = """
        Woah-oh-oh
        This is how the story goes
        Woah-oh-oh
        I guess this is how the story goes
        """
        lyrics5 = """
        I'm in the thick of it, everybody knows
        They know me where it snows, I skied in and they froze (woo)
        I don't know no nothin' 'bout no ice, I'm just cold
        Forty somethin' milli' subs or so, I've been told
        Highway to heaven, I'm just cruisin' by my lone'
        They cast me out, left me for dead, them people cold
        My faith in God, mind in the sun, I'm 'bout to sow (yeah)
        My life is hard, I took the wheel, I cracked the code (yeah-yeah, woah-oh-oh)
        Ain't nobody gon' save you, man, this life will break you (yeah, woah-oh-oh)
        In the thick of it, this is how the story goes
        """
        lyrics6 = """
        I'm in the thick of it, everybody knows
        They know me where it snows, I skied in and they froze
        I don't know no nothin' 'bout no ice, I'm just cold
        Forty somethin' milli' subs or so, I've been told
        I'm in the thick of it, everybody knows (everybody knows)
        They know me where it snows, I skied in and they froze (yeah)
        I don't know no nothin' 'bout no ice, I'm just cold
        Forty somethin' milli' subs or so, I've been told (ooh-ooh)
        """
        lyrics7 = """
        Woah-oh-oh (nah-nah-nah-nah, ayy, ayy)
        This is how the story goes (nah, nah)
        Woah-oh-oh
        I guess this is how the story goes
        """
        # Check if the bot is mentioned or the message contains "seeyuh"
        if bot.user.mentioned_in(message) or "seeyuh" in message.content.lower():
            response = random.choice([link, lyrics1, lyrics2, lyrics3, lyrics4, lyrics5, lyrics6, lyrics7])
            await message.channel.send(response)
            return
        # Otherwise, apply the random chance criteria
        elif random.random() < 0.05:
            response = random.choice([link, lyrics1, lyrics2, lyrics3, lyrics4, lyrics5, lyrics6, lyrics7])
            await message.channel.send(response)
            return
            
    if bot.user.mentioned_in(message) or "seeyuh" in message.content.lower():
        content = message.content.strip()
        command_content = content.replace(f"<@{bot.user.id}>", "seeyuh").strip()
        words = command_content.split()
    
        # Retrieve the last relevant message, prioritizing the user’s recent message
        last_message = fetch_recent_message(supabase, guild_id=str(message.guild.id), user_id=str(message.author.id))

        if last_message:
            context_message = f"Last relevant message in the guild: {last_message['content']}\n"
            context_message += f"Bot response to that message: {last_message['response']}\n"
        else:
            context_message = ""
            
        # Check if the message is a reply to another message
        if message.reference:
            try:
                original_message = await message.channel.fetch_message(message.reference.message_id)
                original_author = original_message.author.name
                original_content = original_message.content
                context_message += f"\n{message.author.name} replied to {original_author}'s message: {original_content}"

            except discord.NotFound:
                print("Original message not found.")

        # Check for mentioned users
        mentioned_users = [user for user in message.mentions if user != bot.user]

        # Start the background task to retry the entry update
        bot.loop.create_task(retry_check_and_update_guild_entry(supabase, str(message.guild.id), message.guild.name))
        
        # If there are more than three words, treat as an AI query
        if len(words) > 3:
            author_name = message.author.name
            current_query = f"{command_content}"
            ai_prompt = context_message + f"\nCurrent query from {author_name}: " + current_query
        
            if mentioned_users:
                mentioned_user_names = [user.name for user in mentioned_users]
                if message.reference and len(mentioned_users) > 1:
                    original_author_name = original_message.author.name
                    mentioned_user_names = [name for name in mentioned_user_names if name != original_author_name]
                user_names_str = ", ".join(mentioned_user_names)
                current_query = command_content
                for user in mentioned_users:
                    current_query = current_query.replace(f"<@{user.id}>", user.name)
                    current_query = current_query.replace(f"<@!{user.id}>", user.name)
                ai_prompt = context_message + f"\nCurrent query from {author_name}: " + current_query

            # Initialize image generation variables (handled downstream if needed)
            image_data = None
            image_text = None
            image_prompt = None
    
            # Always let the Gemini responder decide if this is an image request
            async with message.channel.typing():
                response, code_handled = await get_ai_response(ai_prompt, message)

            # Prepare file object if image data is available
            file = None
            if image_data:
                file = discord.File(fp=image_data, filename="image.png")

            # Only send text responses if code wasn't handled already
            if not code_handled:
                # Split response into parts at newlines while respecting 2000 char limit
                max_length = 2000
                response_parts = []
                current_part = ""
                
                for line in response.splitlines(keepends=True):
                    # If adding this line would exceed limit, start new part
                    if len(current_part) + len(line) > max_length:
                        if current_part:
                            response_parts.append(current_part)
                        current_part = line
                    else:
                        current_part += line
                        
                # Add final part if exists
                if current_part:
                    response_parts.append(current_part)

                # Send the first part
                await message.reply(response_parts[0])
                # Send the remaining parts if any
                for part in response_parts[1:]:
                    await message.channel.send(part)

            # Save the user message and bot response
            bot.loop.create_task(save_message_to_db(str(message.guild.id), message.author, current_query, response))
            return  # Exit early to avoid command processing
    
        # Proceed with command processing if message has three or fewer words
        command_found = False
        for word in words:
            # Check if the command exists
            command = bot.tree.get_command(word)
            if command and word != "seeyuh":
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
                            response = f"Use `/{word}` for the command.\n Use `/help` to know more."
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
            current_query = command_content
            ai_prompt = context_message + "\nCurrent query from " + author_name + ": " + current_query
            if mentioned_users:
                mentioned_user_names = [user.name for user in mentioned_users]
                if message.reference and len(mentioned_users) > 1:
                    original_author_name = original_message.author.name
                    mentioned_user_names = [name for name in mentioned_user_names if name != original_author_name]
                user_names_str = ", ".join(mentioned_user_names)
                current_query = command_content
                for user in mentioned_users:
                    current_query = current_query.replace(f"<@{user.id}>", user.name)
                    current_query = current_query.replace(f"<@!{user.id}>", user.name)
                ai_prompt = context_message + f"\nCurrent query from {author_name}: " + current_query
            
            # Always delegate to AI responder (handles image requests internally)
            async with message.channel.typing():
                response, code_handled = await get_ai_response(ai_prompt, message)

            # Only send text responses if code wasn't handled already
            if not code_handled:
                # Split response into parts at newlines while respecting 2000 char limit
                max_length = 2000
                response_parts = []
                current_part = ""
                
                for line in response.splitlines(keepends=True):
                    # If adding this line would exceed limit, start new part
                    if len(current_part) + len(line) > max_length:
                        if current_part:
                            response_parts.append(current_part)
                        current_part = line
                    else:
                        current_part += line
                        
                # Add final part if exists
                if current_part:
                    response_parts.append(current_part)

                # Send all response parts
                for i, part in enumerate(response_parts):
                    if i == 0:
                        await message.reply(part)
                    else:
                        await message.channel.send(part)

            # Save the user message and bot response
            bot.loop.create_task(save_message_to_db(str(message.guild.id), message.author, current_query, response))
            return  # Exit early to avoid command processing
    
    if message.content.startswith("$"):
        # Get the command content without the $ prefix
        command_content = message.content[1:].strip()
        words = command_content.split()
        if len(words) <= 2:
            # Check for mentioned users
            mentioned_users = [user for user in message.mentions if user != bot.user]
            # Proceed with command processing if message has three or fewer words
            command_found = False
            command_list = ["play", "pause", "resume", "stop", "skip", "queue", "np", "filters", "filters_clear", "join", "leave", "ask"]
            for word in words:
                # Check if the command exists
                command = bot.tree.get_command(word) if word not in command_list else None
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
                                response = f"Use `/{word}` for the command.\n Use `/help` to know more."
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
            mentioned_user_names = [user.name for user in mentioned_users]
            if message.reference and len(mentioned_users) > 1:
                original_author_name = original_message.author.name
                mentioned_user_names = [name for name in mentioned_user_names if name != original_author_name]
            user_names_str = ", ".join(mentioned_user_names)
            ai_prompt = f"{context_message} \nCurrent Context: {author_name} says about {user_names_str} '{command_content}'. \nInstruction: make fun of both users in a playful but interesting manner, you can spin the user's message into a story or a joke."

        async with message.channel.typing():  # Show typing indicator
            response, code_handled = await get_ai_response(ai_prompt, message)
            if not code_handled:
                # Split response into parts at newlines while respecting 2000 char limit
                max_length = 2000
                response_parts = []
                current_part = ""
                
                for line in response.splitlines(keepends=True):
                    # If adding this line would exceed limit, start new part
                    if len(current_part) + len(line) > max_length:
                        if current_part:
                            response_parts.append(current_part)
                        current_part = line
                    else:
                        current_part += line
                        
                # Add final part if exists
                if current_part:
                    response_parts.append(current_part)
                for part in response_parts:
                    await message.reply(part)
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
    if any(phrase in message.content.lower() for phrase in ["yamete", "yamate", "kudasai"]) and random.random() < 0.05:
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

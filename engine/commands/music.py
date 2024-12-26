import discord, yt_dlp as youtube_dl, asyncio, engine.eventloop as eventloop, re, os, lyricsgenius, logging, time, backoff
from youtube_transcript_api import YouTubeTranscriptApi
from requests.exceptions import HTTPError
from typing import Optional, Tuple, List
from discord import app_commands
from engine.utils import load_env

logging.basicConfig(level=logging.INFO)

# Initialize Genius with proper config and retries
genius = lyricsgenius.Genius(
    access_token=os.getenv('GENIUS_API_KEY'),
    timeout=10,
    retries=3
)

genius.verbose = False 
genius.remove_section_headers = True
genius.skip_non_songs = True
genius.excluded_terms = ["(Remix)", "(Live)", "(Official Audio)", "Official Video"]
genius._session.headers.update({
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
})

def clean_song_info(title: str, artist: str) -> Tuple[str, str]:
    """Clean song title and artist name"""
    # Remove common extras from title
    title = re.sub(r'\(.*?\)|\[.*?\]|Official.*?$|ft\..*?$|feat\..*?$', '', title)
    title = re.sub(r'\s+', ' ', title).strip()
    
    # Clean artist name
    artist = re.sub(r',.*$', '', artist)  # Remove featuring artists
    artist = re.sub(r'\s+', ' ', artist).strip()
    
    return title, artist

async def get_song_info(url: str) -> Optional[Tuple[str, str]]:
    """Extract song title and artist from YouTube URL"""
    ydl_opts = {
        'quiet': True,
        'extract_flat': True
    }
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', '')
            # Try to split title into song and artist
            if ' - ' in title:
                artist, song = title.split(' - ', 1)
            else:
                # Remove common YouTube title extras
                song = re.sub(r'\(.*?\)|\[.*?\]|Official.*?$', '', title).strip()
                artist = info.get('artist', info.get('uploader', ''))
            return song, artist
        except Exception as e:
            logging.error(f"Error extracting song info: {e}")
            return None

@backoff.on_exception(backoff.expo, Exception, max_tries=3)
async def get_genius_lyrics(song: str, artist: str) -> Optional[str]:
    """Get lyrics from Genius with retries"""
    try:
        if not os.getenv('GENIUS_API_KEY'):
            logging.error("Missing Genius API key")
            return None
            
        song, artist = clean_song_info(song, artist)
        logging.info(f"Searching Genius for: {song} by {artist}")

        for search_query in [
            (song, artist),
            (song, None),
            (f"{artist} {song}", None)
        ]:
            try:
                # Add delay between retries
                time.sleep(1)
                result = genius.search_song(*search_query)
                if result and result.lyrics:
                    lyrics = result.lyrics
                    lyrics = re.sub(r'\[[^\]]*\]', '', lyrics)
                    lyrics = re.sub(r'\d*Embed$', '', lyrics)
                    lyrics = re.sub(r'You might also like', '', lyrics)
                    lyrics = re.sub(r'\n\s*\n', '\n\n', lyrics)
                    lyrics = lyrics.replace('Lyrics', '').strip()
                    return lyrics
            except Exception as e:
                logging.error(f"Search attempt failed: {str(e)}")
                continue
        return None
    except Exception as e:
        logging.error(f"Genius API error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logging.error(f"Response status: {e.response.status_code}")
            logging.error(f"Response body: {e.response.text}")
        return None
    
# Load environment variables
DISCORD_TOKEN, OWNER, url, key = load_env()

# Define available audio effects
AUDIO_EFFECTS = {
    'bassboost': 'bass=g=10',
    'nightcore': 'asetrate=44100*1.25,aresample=44100,atempo=1.0',
    '8d': 'apulsator=hz=0.08',
    'vibrato': 'vibrato=f=5',
    'echo': 'aecho=0.8:0.88:60:0.4',
    'chipmunk': 'asetrate=44100*1.5,aresample=44100',
    'slowed': 'atempo=0.8',
    # Add more effects as desired
}

# Active filters per guild
active_filters = {}  # Key: guild.id, Value: set of active filters

# Setup for yt-dlp to extract audio
ytdl_options = {
    'format': 'bestaudio/best',
    'noplaylist': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    "cachedir": False,
    'options': '-vn -bufsize 64k',
    'extract_flat': False,
    'force_generic_extractor': False,
    # Add these options
    'cookiefile': os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'engine/youtube/cookies.txt'),
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'no_warnings': True,
    'cookiesfrombrowser': ('chrome',),  # Use cookies from Chrome
    # Add consent handling
    'extractor_args': {
        'youtube': {
            'player_client': ['android'],  # Use android client to avoid consent
            'player_skip': ['webpage'],    # Skip webpage download
            'consent': 'yes'               # Auto consent
        }
    }
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -bufsize 8192k -maxrate 2048k -user_agent "Mozilla/5.0"'
}

if not os.path.exists(ytdl_options['cookiefile']):
    logging.error(f"Cookie file not found at {ytdl_options['cookiefile']}")

ytdl = youtube_dl.YoutubeDL(ytdl_options)

# Queue to hold the songs
# Modify your song queue to include song info
song_queue = []  # Each item will be a tuple: (interaction, query, info)
current_song = None
loop_song = False
skip_votes = set()
previous_message = None
# Add at top with other globals
current_song_start = None

def is_valid_youtube_url(url: str) -> Optional[str]:
    """Validate YouTube URL and extract video ID"""
    patterns = [
        r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        r'youtube:([a-zA-Z0-9_-]{11})',  # For internal format
        r'([a-zA-Z0-9_-]{11})'  # Direct video ID
    ]
    
    for pattern in patterns:
        if match := re.search(pattern, url):
            return match.group(1)
    return None

# Now you can use 'bot' in this module
class MusicView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction):
        super().__init__(timeout=None)
        self.interaction = interaction
        self.youtube_url = None  # Store actual YouTube URL
        self.song_requester = interaction.user.id

    def set_url(self, url: str):
        """Set YouTube URL for currently playing song"""
        video_id = is_valid_youtube_url(url)
        if video_id:
            self.youtube_url = f"https://www.youtube.com/watch?v={video_id}"
        else:
            logging.error(f"Invalid YouTube URL format: {url}")

    @discord.ui.button(label="Pause", style=discord.ButtonStyle.primary, emoji="⏸️")
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.pause()
            embed = discord.Embed(title="Music", description="Paused the music.", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(title="Error", description="No music is currently playing.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="Resume", style=discord.ButtonStyle.primary, emoji="▶️")
    async def resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild.voice_client and interaction.guild.voice_client.is_paused():
            interaction.guild.voice_client.resume()
            embed = discord.Embed(title="Music", description="Resumed the music.", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(title="Error", description="The music is not paused.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.primary, emoji="⏭️")
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        global skip_votes
        if interaction.user.id not in skip_votes:
            skip_votes.add(interaction.user.id)
            listeners = len(interaction.guild.voice_client.channel.members) - 1  # Exclude the bot
            if len(skip_votes) / listeners > 0.5:
                interaction.guild.voice_client.stop()
                embed = discord.Embed(title="Music", description="Skipped the song.", color=discord.Color.green())
                await interaction.response.send_message(embed=embed)
                skip_votes.clear()
            else:
                embed = discord.Embed(title="Music", description=f"Skip vote added. {len(skip_votes)}/{listeners} votes.", color=discord.Color.green())
                await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(title="Error", description="You have already voted to skip.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="Loop", style=discord.ButtonStyle.primary, emoji="🔁")
    async def loop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        global loop_song
        loop_song = not loop_song
        status = "enabled" if loop_song else "disabled"
        await interaction.response.send_message(f"Looping is now {status}.", ephemeral=True)
        channel = interaction.channel
        await channel.send(f"Looping is now {status}.")
        
    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, emoji="⏹️")
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user is admin or song requester
        if (interaction.guild.voice_client and interaction.guild.voice_client.is_playing() and 
            (interaction.user.guild_permissions.administrator or interaction.user.id == self.song_requester)):
            interaction.guild.voice_client.stop()
            embed = discord.Embed(title="Music", description="Stopped the music.", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(title="Error", 
                                description="You don't have permission to stop the music. Only the song requester or server admin can stop.", 
                                color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Lyrics", style=discord.ButtonStyle.secondary, emoji="📝")
    async def lyrics_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.youtube_url:
            await interaction.response.send_message("No song is currently playing.", ephemeral=True)
            return

        await interaction.response.defer()
        logging.info(f"Processing YouTube URL: {self.youtube_url}")

        try:
            song_info = await get_song_info(self.youtube_url)
            if song_info:
                song, artist = song_info
                lyrics = await get_genius_lyrics(song, artist)
                
                if lyrics:
                    # Split lyrics into lines
                    lines = [line for line in lyrics.split('\n') if line.strip()]
                    
                    # Group into chunks
                    chunks = []
                    current_chunk = []
                    current_length = 0
                    
                    for line in lines:
                        if current_length + len(line) + 1 > 1900:
                            chunks.append('\n'.join(current_chunk))
                            current_chunk = [line]
                            current_length = len(line)
                        else:
                            current_chunk.append(line)
                            current_length += len(line) + 1
                    
                    if current_chunk:
                        chunks.append('\n'.join(current_chunk))
                    
                    # Send chunks
                    for i, chunk in enumerate(chunks):
                        if i == 0:
                            await interaction.followup.send(
                                f"📝 **Lyrics for {song} by {artist}**\n```\n{chunk}```"
                            )
                        else:
                            await interaction.followup.send(f"```\n{chunk}```")
                    return
                logging.info("No Genius lyrics found, trying YouTube captions")

            # Fallback to YouTube captions
            video_id = is_valid_youtube_url(self.youtube_url)
            
            try:
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                
                # Try different transcript types
                transcript = None
                for lang in ['en', 'en-US', 'en-GB']:
                    try:
                        transcript = transcript_list.find_transcript([lang])
                        break
                    except:
                        continue
                        
                if not transcript:
                    try:
                        transcript = transcript_list.find_manually_created_transcript()
                    except:
                        transcript = transcript_list.find_generated_transcript()
                        
                transcript_data = transcript.fetch()
                formatted_lyrics = []
                current_chunk = ""
                
                for entry in transcript_data:
                    minutes = int(entry['start']) // 60
                    seconds = int(entry['start']) % 60
                    timestamp = f"[{minutes:02d}:{seconds:02d}]"
                    line = f"{timestamp} {entry['text']}\n"
                    
                    if len(current_chunk) + len(line) > 1900:
                        formatted_lyrics.append(current_chunk)
                        current_chunk = line
                    else:
                        current_chunk += line
                
                if current_chunk:
                    formatted_lyrics.append(current_chunk)
                
                for i, chunk in enumerate(formatted_lyrics):
                    if i == 0:
                        await interaction.followup.send(
                            f"📝 **Video Transcript**\n```\n{chunk}```"
                        )
                    else:
                        await interaction.followup.send(f"```\n{chunk}```")
                        
            except Exception as e:
                logging.error(f"YouTube transcript error: {str(e)}")
                if "Subtitles are disabled" in str(e):
                    await interaction.followup.send("❌ This video does not have captions enabled.", ephemeral=True)
                else:
                    await interaction.followup.send("❌ Could not find lyrics or captions for this song.", ephemeral=True)
                
        except Exception as e:
            logging.error(f"Lyrics error: {e}")
            await interaction.followup.send("❌ Could not find lyrics for this song.", ephemeral=True)
            
# Join a voice channel
@app_commands.command(name="join", description="Join your voice channel.")
async def join(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        embed = discord.Embed(title="Error", description="I'm already in a voice channel!", color=discord.Color.red())
        await interaction.response.send_message(embed=embed)
        return

    if interaction.user.voice:
        channel = interaction.user.voice.channel
        await channel.connect()
        embed = discord.Embed(title="Voice Channel", description=f"Joined {channel}", color=discord.Color.green())
        await interaction.response.send_message(embed=embed)
    else:
        embed = discord.Embed(title="Error", description="You are not in a voice channel!", color=discord.Color.red())
        await interaction.response.send_message(embed=embed)

# Leave the voice channel
@app_commands.command(name="leave", description="Leave the voice channel.")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        embed = discord.Embed(title="Voice Channel", description="Disconnected from the voice channel.", color=discord.Color.green())
        await interaction.response.send_message(embed=embed)
    else:
        embed = discord.Embed(title="Error", description="I'm not in a voice channel!", color=discord.Color.red())
        await interaction.response.send_message(embed=embed)

# Play a YouTube URL or search query
# music.py (continued)

@app_commands.command(name="play", description="Play a song or playlist.")
@app_commands.describe(query="The song name or URL to play.")
async def play(interaction: discord.Interaction, query: str):
    try:
        await interaction.response.defer()

        if not interaction.guild.voice_client:
            if interaction.user.voice:
                channel = interaction.user.voice.channel
                await channel.connect()
            else:
                embed = discord.Embed(
                    title="Error",
                    description="You are not in a voice channel!",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed)
                return

        # Resolve the query to get song info
        info = ytdl.extract_info(query, download=False)
        if 'entries' in info:
            # If it's a playlist, take the first entry
            info = info['entries'][0]

        # Add the song to the queue
        song_queue.append((interaction, query, info))

        await interaction.followup.send(
            f"Added **{info['title']}** to the queue.",
            ephemeral=True
        )

        # If nothing is currently playing, start the next song
        voice_client = interaction.guild.voice_client
        if not voice_client.is_playing():
            await play_next_song()

    except Exception as e:
        embed = discord.Embed(
            title="Error",
            description=f"An error occurred: {e}",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed)
        
async def play_next_song():
    global current_song, previous_message, current_song_start
    
    if loop_song and current_song:
        interaction, query, info = current_song
    elif song_queue:
        interaction, query, info = song_queue.pop(0)
        current_song = (interaction, query, info)
    else:
        current_song = None
        return

    try:
        url2 = info['url']
        duration = info.get('duration', 0)
        current_song_start = time.time()

        # Create FFmpeg source with better buffering
        source = await discord.FFmpegOpusAudio.from_probe(
            url2,
            **ffmpeg_options
        )

        def after_playing(error):
            if error:
                logging.error(f"Playback error: {error}")
            
            # Schedule next song in event loop
            eventloop.event_loop.call_soon_threadsafe(
                lambda: asyncio.create_task(play_next_song())
            )

        # Play with increased buffer
        interaction.guild.voice_client.play(
            source,
            after=after_playing
        )

        # Add duration to embed if available
        embed = discord.Embed(
            title="Now Playing",
            description=f"[{info['title']}]({info['webpage_url']})",
            color=discord.Color.blue()
        )
        if duration:
            minutes = duration // 60
            seconds = duration % 60
            embed.add_field(name="Duration", value=f"{minutes:02d}:{seconds:02d}")
            
        embed.set_thumbnail(url=info['thumbnail'])
        embed.set_author(
            name=f"Requested by {interaction.user}",
            icon_url=interaction.user.display_avatar.url
        )
        embed.set_footer(
            text=f"{interaction.client.user.name}",
            icon_url=interaction.client.user.display_avatar.url
        )
        view = MusicView(interaction)
        view.set_url(info['webpage_url'])
        previous_message = await interaction.followup.send(embed=embed, view=view)

    except Exception as e:
        logging.error(f"Playback error: {e}")
        embed = discord.Embed(
            title="Error",
            description=f"An error occurred: {e}",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        
# Now Playing command
@app_commands.command(name="np", description="Show the currently playing song.")
async def now_playing(interaction: discord.Interaction):
    try:
        if current_song and current_song_start:
            _, _, info = current_song
            
            # Calculate progress
            duration = info.get('duration', 0)
            elapsed = int(time.time() - current_song_start)
            remaining = max(0, duration - elapsed)
            
            # Create progress bar (20 chars wide)
            progress = min(1.0, elapsed / duration if duration else 0)
            bar_length = 20
            filled = int(bar_length * progress)
            progress_bar = '▰' * filled + '▱' * (bar_length - filled)
            
            # Format timestamps
            elapsed_str = f"{elapsed//60:02d}:{elapsed%60:02d}"
            remaining_str = f"{remaining//60:02d}:{remaining%60:02d}/{duration//60:02d}:{duration%60:02d}"
            
            embed = discord.Embed(
                title="Now Playing",
                description=(
                    f"[{info['title']}]({info['webpage_url']})\n\n"
                    f"`{elapsed_str} {progress_bar} {remaining_str}`"
                ),
                color=discord.Color.blue()
            )
            
            embed.set_thumbnail(url=info['thumbnail'])
            embed.set_author(
                name=f"Requested by {interaction.user}",
                icon_url=interaction.user.display_avatar.url
            )
            embed.set_footer(
                text=f"{interaction.client.user.name}",
                icon_url=interaction.client.user.display_avatar.url
            )
            
            await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(
                title="Now Playing",
                description="No song is currently playing.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed)
            
    except Exception as e:
        embed = discord.Embed(
            title="Error",
            description=f"An error occurred: {e}",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

# Show the current queue
@app_commands.command(name="queue", description="Show the current queue.")
async def queue(interaction: discord.Interaction):
    await interaction.response.defer()  # Defer the response

    try:
        if song_queue:
            description = ""
            for i, (inter, query, info) in enumerate(song_queue):
                description += f"{i+1}. [{info['title']}]({info['webpage_url']})\n"
            embed = discord.Embed(
                title="Current Queue",
                description=description,
                color=discord.Color.blue()
            )
            embed.set_footer(
                text=f"{interaction.client.user.name}",
                icon_url=interaction.client.user.display_avatar.url
            )
            await interaction.followup.send(embed=embed)
        else:
            embed = discord.Embed(
                title="Queue",
                description="The queue is currently empty.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
    except Exception as e:
        # Handle any exceptions and ensure the interaction is responded to
        embed = discord.Embed(
            title="Error",
            description=f"An error occurred: {e}",
            color=discord.Color.red()
        )
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

# Stop the music
@app_commands.command(name="stop", description="Stop the music.")
async def stop(interaction: discord.Interaction):
    if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
        interaction.guild.voice_client.stop()
        embed = discord.Embed(title="Music", description="Stopped the music.", color=discord.Color.green())
        await interaction.response.send_message(embed=embed)
    else:
        embed = discord.Embed(title="Error", description="No music is currently playing.", color=discord.Color.red())
        await interaction.response.send_message(embed=embed)

# Pause the music
@app_commands.command(name="pause", description="Pause the music.")
async def pause(interaction: discord.Interaction):
    if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
        interaction.guild.voice_client.pause()
        embed = discord.Embed(title="Music", description="Paused the music.", color=discord.Color.green())
        await interaction.response.send_message(embed=embed)
    else:
        embed = discord.Embed(title="Error", description="No music is currently playing.", color=discord.Color.red())
        await interaction.response.send_message(embed=embed)

# Resume the music
@app_commands.command(name="resume", description="Resume the music.")
async def resume(interaction: discord.Interaction):
    if interaction.guild.voice_client and interaction.guild.voice_client.is_paused():
        interaction.guild.voice_client.resume()
        embed = discord.Embed(title="Music", description="Resumed the music.", color=discord.Color.green())
        await interaction.response.send_message(embed=embed)
    else:
        embed = discord.Embed(title="Error", description="The music is not paused.", color=discord.Color.red())
        await interaction.response.send_message(embed=embed)

@app_commands.command(name="filter", description="Toggle audio filters.")
@app_commands.describe(effect="The audio effect to toggle.")
@app_commands.choices(
    effect=[
        app_commands.Choice(name="Bass Boost", value="bassboost"),
        app_commands.Choice(name="Nightcore", value="nightcore"),
        app_commands.Choice(name="8D", value="8d"),
        app_commands.Choice(name="Vibrato", value="vibrato"),
        app_commands.Choice(name="Echo", value="echo"),
        app_commands.Choice(name="Chipmunk", value="chipmunk"),
        app_commands.Choice(name="Slowed", value="slowed"),
        # Add more choices as defined in AUDIO_EFFECTS
    ]
)
async def filter_command(interaction: discord.Interaction, effect: app_commands.Choice[str]):
    guild_id = interaction.guild.id

    # Initialize the set if not present
    if guild_id not in active_filters:
        active_filters[guild_id] = set()

    effect_name = effect.value

    if effect_name in active_filters[guild_id]:
        active_filters[guild_id].remove(effect_name)
        await interaction.response.send_message(f"**{effect.name}** has been disabled.", ephemeral=True)
    else:
        active_filters[guild_id].add(effect_name)
        await interaction.response.send_message(f"**{effect.name}** has been enabled.", ephemeral=True)
        
@app_commands.command(name="filters", description="List active audio filters.")
async def list_filters(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    filters = active_filters.get(guild_id, set())
    if filters:
        filter_names = [f.capitalize() for f in filters]
        filter_list = ', '.join(filter_names)
        await interaction.response.send_message(f"**Active Filters:** {filter_list}", ephemeral=True)
    else:
        await interaction.response.send_message("No active filters.", ephemeral=True)
        
@app_commands.command(name="filters_clear", description="Clear all active audio filters.")
async def clear_filters(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    if guild_id in active_filters and active_filters[guild_id]:
        active_filters[guild_id].clear()
        await interaction.response.send_message("All audio filters have been cleared.", ephemeral=True)
    else:
        await interaction.response.send_message("No active filters to clear.", ephemeral=True)

def extract_video_id(url):
    """Extract video ID from YouTube URL"""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:embed\/)([0-9A-Za-z_-]{11})',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

@app_commands.command(name='lyrics', description='Get lyrics/transcript from a YouTube video')
async def lyrics_command(interaction: discord.Interaction, url: str):
    await interaction.response.defer()
    logging.info(f"Processing URL for lyrics: {url}")
    
    try:
        # Extract video ID and validate URL
        video_id = extract_video_id(url)
        if not video_id:
            await interaction.followup.send("❌ Invalid YouTube URL")
            return
            
        youtube_url = f"https://www.youtube.com/watch?v={video_id}"
        
        # Try Genius lyrics first
        song_info = await get_song_info(youtube_url)
        if song_info:
            song, artist = song_info
            logging.info(f"Found song info: {song} by {artist}")
            lyrics = await get_genius_lyrics(song, artist)
            
            if lyrics:
                # Split lyrics into lines
                lines = [line for line in lyrics.split('\n') if line.strip()]
                
                # Group into chunks
                chunks = []
                current_chunk = []
                current_length = 0
                
                for line in lines:
                    if current_length + len(line) + 1 > 1900:
                        chunks.append('\n'.join(current_chunk))
                        current_chunk = [line]
                        current_length = len(line)
                    else:
                        current_chunk.append(line)
                        current_length += len(line) + 1
                
                if current_chunk:
                    chunks.append('\n'.join(current_chunk))
                
                # Send chunks
                for i, chunk in enumerate(chunks):
                    if i == 0:
                        await interaction.followup.send(
                            f"📝 **Lyrics for {song} by {artist}**\n```\n{chunk}```"
                        )
                    else:
                        await interaction.followup.send(f"```\n{chunk}```")
                return
                # If no Genius lyrics were found
                logging.info("No Genius lyrics found, trying YouTube captions")
                await interaction.followup.send("❌ Could not find lyrics for this song. Let me try getting the video captions...", ephemeral=True)

                
        # Fallback to YouTube captions
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # Try English transcripts first
            transcript = None
            for lang in ['en', 'en-US', 'en-GB']:
                try:
                    transcript = transcript_list.find_transcript([lang])
                    break
                except:
                    continue
                    
            if not transcript:
                try:
                    transcript = transcript_list.find_manually_created_transcript()
                except:
                    transcript = transcript_list.find_generated_transcript()
                    
            transcript_data = transcript.fetch()
            formatted_lyrics = []
            current_chunk = ""
            
            for entry in transcript_data:
                minutes = int(entry['start']) // 60
                seconds = int(entry['start']) % 60
                timestamp = f"[{minutes:02d}:{seconds:02d}]"
                line = f"{timestamp} {entry['text']}\n"
                
                if len(current_chunk) + len(line) > 1900:
                    formatted_lyrics.append(current_chunk)
                    current_chunk = line
                else:
                    current_chunk += line
            
            if current_chunk:
                formatted_lyrics.append(current_chunk)
            
            for i, chunk in enumerate(formatted_lyrics):
                if i == 0:
                    await interaction.followup.send(f"📝 **Video Transcript**\n```\n{chunk}```")
                else:
                    await interaction.followup.send(f"```\n{chunk}```")
                    
        except Exception as e:
            logging.error(f"YouTube transcript error: {str(e)}")
            if "Subtitles are disabled" in str(e):
                await interaction.followup.send("❌ This video does not have captions enabled.", ephemeral=True)
            else:
                raise
                
    except Exception as e:
        logging.error(f"Lyrics error: {str(e)}")
        await interaction.followup.send("❌ Could not find lyrics or captions for this video.", ephemeral=True)
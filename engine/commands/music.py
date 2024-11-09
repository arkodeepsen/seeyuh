import discord, re, aiohttp, yt_dlp as youtube_dl, asyncio, engine.eventloop as eventloop
from discord import app_commands
from discord.ext import commands
from engine.utils import load_env, intents

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
    'noplaylist': 'False',  # Allow playlists
    'quiet': True,  # Suppress output
    'no_warnings': True,  # Suppress warnings
    'default_search': 'auto',  # Automatically search for the query
    'source_address': '0.0.0.0',  # Bind to IPv4 address to avoid IPv6 issues
    "cachedir": False,
    'options': '-vn -bufsize 64k'
}

ffmpeg_options = {
    'options': '-vn'  # This removes the video
}

ytdl = youtube_dl.YoutubeDL(ytdl_options)

# Queue to hold the songs
# Modify your song queue to include song info
song_queue = []  # Each item will be a tuple: (interaction, query, info)
current_song = None
loop_song = False
skip_votes = set()
previous_message = None

# Now you can use 'bot' in this module
class MusicView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction):
        super().__init__(timeout=None)
        self.interaction = interaction

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

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, emoji="⏹️")
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.stop()
            embed = discord.Embed(title="Music", description="Stopped the music.", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(title="Error", description="No music is currently playing.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="Loop", style=discord.ButtonStyle.primary, emoji="🔁")
    async def loop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        global loop_song
        loop_song = not loop_song
        status = "enabled" if loop_song else "disabled"
        await interaction.response.send_message(f"Looping is now {status}.", ephemeral=True)

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
@app_commands.command(name="play", description="Play a song or playlist.")
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

        # Check if the query is a YouTube URL
        youtube_url_pattern = re.compile(
            r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/.+'
        )
        if not youtube_url_pattern.match(query):
            # If not a URL, search for the query on YouTube
            search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        video_id = re.search(r"watch\?v=(\S{11})", html)
                        if video_id:
                            query = f"https://www.youtube.com/watch?v={video_id.group(1)}"
                        else:
                            embed = discord.Embed(
                                title="Error",
                                description="No results found on YouTube.",
                                color=discord.Color.red()
                            )
                            await interaction.followup.send(embed=embed)
                            return

        # Fetch the song info once here
        info = ytdl.extract_info(query, download=False)

        # Add the song to the queue with its info
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
    global current_song, previous_message

    if loop_song and current_song:
        query = current_song['webpage_url']
        info = current_song
    elif song_queue:
        interaction, query, info = song_queue.pop(0)
        current_song = info  # Store the info of the current song
    else:
        current_song = None
        return

    try:
        # Get the direct URL to the audio
        url2 = info['url']
        source = await discord.FFmpegOpusAudio.from_probe(url2, **ffmpeg_options)

        # Play the audio and handle the after callback
        voice_client = interaction.guild.voice_client

        def after_playing(error):
            # Use the event loop from eventloop module
            coro = play_next_song()
            fut = asyncio.run_coroutine_threadsafe(coro, eventloop.event_loop)
            try:
                fut.result()
            except Exception as e:
                print(f"Error in after_playing: {e}")

        voice_client.play(source, after=after_playing)

        # Edit the previous message to indicate the song has been played
        if previous_message:
            await previous_message.edit(content="Played", embed=None, view=None)

        embed = discord.Embed(
            title="Now Playing",
            description=f"[{info['title']}]({info['webpage_url']})",
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
        view = MusicView(interaction)
        previous_message = await interaction.followup.send(embed=embed, view=view)

    except Exception as e:
        embed = discord.Embed(
            title="Error",
            description=f"An error occurred: {e}",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed)
        
# Now Playing command
@app_commands.command(name="np", description="Show the currently playing song.")
async def now_playing(interaction: discord.Interaction):
    try:
        if current_song:
            info = current_song  # Use the current_song info directly
            embed = discord.Embed(
                title="Now Playing",
                description=f"[{info['title']}]({info['webpage_url']})",
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
        # Handle any exceptions
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
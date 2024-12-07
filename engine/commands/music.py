import discord, yt_dlp as youtube_dl, asyncio, engine.eventloop as eventloop
from discord import app_commands
from engine.utils import load_env

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
    'noplaylist': False,  # Allow playlists
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
        channel = interaction.channel
        await channel.send(f"Looping is now {status}.")

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
    global current_song, previous_message

    if loop_song and current_song:
        interaction, query, info = current_song
    elif song_queue:
        interaction, query, info = song_queue.pop(0)
        current_song = (interaction, query, info)
    else:
        current_song = None
        return

    guild_id = interaction.guild.id
    filters = active_filters.get(guild_id, set())

    # Determine the FFmpeg options based on active filters
    if filters:
        # Combine all active filters with commas
        ffmpeg_filter = ','.join([AUDIO_EFFECTS[filter_name] for filter_name in filters])
        current_ffmpeg_options = {
            'options': f"-vn -af {ffmpeg_filter}"
        }
    else:
        # Use the default FFmpeg options
        current_ffmpeg_options = ffmpeg_options  # Refer to the global ffmpeg_options

    try:
        # Get the direct URL to the audio
        url2 = info['url']
        source = await discord.FFmpegOpusAudio.from_probe(url2, **current_ffmpeg_options)

        # Play the audio and handle the after callback
        voice_client = interaction.guild.voice_client

        def after_playing(error):
            if error:
                print(f"Error during playback: {error}")
            try:
                # Schedule the next song without blocking
                eventloop.event_loop.call_soon_threadsafe(
                    asyncio.create_task, play_next_song()
                )
            except Exception as e:
                print(f"Error scheduling next song: {e}")

        voice_client.play(source, after=after_playing)

        # Edit the previous message to indicate the song has been played
        if previous_message:
            async def edit_message():
                await previous_message.edit(content="Played", embed=None, view=None)
            eventloop.event_loop.call_soon_threadsafe(
                asyncio.create_task, edit_message()
            )

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
            _, _, info = current_song  # Unpack the tuple correctly
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
        
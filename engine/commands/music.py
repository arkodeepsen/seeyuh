import discord, re, aiohttp, yt_dlp as youtube_dl, asyncio
from discord import app_commands
from discord.ext import commands
from engine.utils import load_env, intents

# Load environment variables
DISCORD_TOKEN, OWNER, url, key = load_env()

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
song_queue = []
current_song = None
loop_song = False
skip_votes = set()

bot = commands.Bot(command_prefix="/", intents=intents())

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
                embed = discord.Embed(title="Error", description="You are not in a voice channel!", color=discord.Color.red())
                await interaction.followup.send(embed=embed)
                return

        # Check if the query is a YouTube URL
        youtube_url_pattern = re.compile(r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/.+')
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
                            embed = discord.Embed(title="Error", description="No results found on YouTube.", color=discord.Color.red())
                            await interaction.followup.send(embed=embed)
                            return

        # Add the song or playlist to the queue
        song_queue.append((interaction, query))
        if len(song_queue) > 1:
            await interaction.followup.send("Song queued.", ephemeral=True)
        if len(song_queue) == 1:
            await play_next_song()
    except discord.errors.NotFound:
        embed = discord.Embed(title="Error", description="Interaction not found or already acknowledged.", color=discord.Color.red())
        await interaction.followup.send(embed=embed)

async def play_next_song():
    global current_song
    if not song_queue:
        return

    interaction, query = song_queue.pop(0)
    current_song = query

    try:
        # Download or stream the audio from the URL
        info = ytdl.extract_info(query, download=False)
        if 'entries' in info:
            for entry in info['entries']:
                song_queue.append((interaction, entry['webpage_url']))
            await play_next_song()
            return

        url2 = info['url']
        source = await discord.FFmpegOpusAudio.from_probe(url2, **ffmpeg_options)
        interaction.guild.voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(play_next_song(), bot.loop))
        embed = discord.Embed(title="Now Playing", description=f"[{info['title']}]({query})", color=discord.Color.blue())
        embed.set_thumbnail(url=info['thumbnail'])
        embed.set_author(name=f"Requested by {interaction.user}", icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"{interaction.client.user.name}", icon_url=interaction.client.user.display_avatar.url)
        view = MusicView(interaction)
        await interaction.followup.send(embed=embed, view=view)
    except discord.errors.ClientException as e:
        embed = discord.Embed(title="Error", description=f"An error occurred: {e}", color=discord.Color.red())
        await interaction.followup.send(embed=embed)
    except Exception as e:
        embed = discord.Embed(title="Error", description=f"An unexpected error occurred: {e}", color=discord.Color.red())
        await interaction.followup.send(embed=embed)

# Now Playing command
@app_commands.command(name="np", description="Show the currently playing song.")
async def now_playing(interaction: discord.Interaction):
    try:
        await interaction.response.defer()
        if current_song:
            info = ytdl.extract_info(current_song, download=False)
            embed = discord.Embed(title="Now Playing", description=f"[{info['title']}]({current_song})", color=discord.Color.blue())
            embed.set_thumbnail(url=info['thumbnail'])
            embed.set_author(name=f"Requested by {interaction.user}", icon_url=interaction.user.display_avatar.url)
            embed.set_footer(text=f"{interaction.client.user.name}", icon_url=interaction.client.user.display_avatar.url)
            await interaction.followup.send(embed=embed)
        else:
            embed = discord.Embed(title="Now Playing", description="No song is currently playing.", color=discord.Color.red())
            await interaction.followup.send(embed=embed)
    except discord.errors.NotFound:
        embed = discord.Embed(title="Error", description="Interaction not found or already acknowledged.", color=discord.Color.red())
        await interaction.followup.send(embed=embed)

# Queue command
@app_commands.command(name="queue", description="Show the current queue.")
async def queue(interaction: discord.Interaction):
    if song_queue:
        description = "\n".join([f"{i+1}. [{ytdl.extract_info(query, download=False)['title']}]({query})" for i, (_, query) in enumerate(song_queue)])
        embed = discord.Embed(title="Current Queue", description=description, color=discord.Color.blue())
        embed.set_footer(text=f"{interaction.client.user.name}", icon_url=interaction.client.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)
    else:
        embed = discord.Embed(title="Queue", description="The queue is currently empty.", color=discord.Color.red())
        await interaction.response.send_message(embed=embed)

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

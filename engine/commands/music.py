import discord, yt_dlp as youtube_dl, asyncio, engine.eventloop as eventloop, re, os, lyricsgenius, logging, time, backoff, shlex, aiohttp, urllib.parse, requests
from youtube_transcript_api import YouTubeTranscriptApi
from requests.exceptions import HTTPError
from typing import Optional, Tuple, List
from discord import app_commands
from engine.utils import load_env

logging.basicConfig(level=logging.INFO)

PREFERRED_REGIONS = [
    'us-east', 
    'us-central',
    'us-west',
    'us-south'
]
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
                # Add delay between retries without blocking the event loop
                await asyncio.sleep(1)
                # Run blocking Genius API in a thread
                result = await asyncio.to_thread(genius.search_song, *search_query)
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

# SMART COOKIE STRATEGY FOR RAILWAY:
# 1. Default: No cookies (works locally)
# 2. Bot Detection: Auto-retry with cookies only when needed
# 3. Prevents: Format restrictions that cookies can cause
# 4. Environment: Set YT_COOKIES_FILE and YT_USER_AGENT for Railway

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

# Multiple configurations for different fallback strategies
ytdl_configs = {
    'ios_primary': {
        'format': 'bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch1',
        'extract_flat': False,
        'skip_unavailable_fragments': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['ios'],
                'player_skip': ['webpage'],
                'use_oauth': False,
            }
        },
        'http_headers': {
            'User-Agent': 'com.google.ios.youtube/19.29.1 (iPhone16,2; U; CPU iOS 17_5_1 like Mac OS X;)',
            'X-Youtube-Client-Name': '5',
            'X-Youtube-Client-Version': '19.29.1',
        },
        'sleep_interval_requests': 1,
        'max_sleep_interval_requests': 3,
    },
    'android_fallback': {
        'format': 'bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch1',
        'extract_flat': False,
        'skip_unavailable_fragments': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android'],
                'player_skip': ['webpage'],
                'use_oauth': False,
            }
        },
        'http_headers': {
            'User-Agent': 'com.google.android.youtube/19.29.37 (Linux; U; Android 13; SM-S901U Build/TP1A.220624.014) gzip',
            'X-Youtube-Client-Name': '3',
            'X-Youtube-Client-Version': '19.29.37',
        },
        'sleep_interval_requests': 1.5,
        'max_sleep_interval_requests': 4,
    },
    'web_fallback': {
        'format': 'bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch1',
        'extract_flat': False,
        'skip_unavailable_fragments': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['web'],
                'player_skip': ['webpage'],
                'use_oauth': False,
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        },
        'sleep_interval_requests': 2,
        'max_sleep_interval_requests': 5,
    }
}

# Enhanced primary config with anti-bot measures
ytdl_options = {
    'format': 'bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch1',
    'extract_flat': False,
    'skip_unavailable_fragments': True,
    'extractor_args': {
        'youtube': {
            'player_client': ['ios', 'android_embedded'],
            'player_skip': ['webpage', 'configs'],
            'use_oauth': False,
            'lang': ['en'],
            'region': 'US',
        }
    },
    'http_headers': {
        'User-Agent': 'com.google.ios.youtube/19.29.1 (iPhone16,2; U; CPU iOS 17_5_1 like Mac OS X;)',
        'X-Youtube-Client-Name': '5',
        'X-Youtube-Client-Version': '19.29.1',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
    },
    'sleep_interval_requests': 0.5,
    'max_sleep_interval_requests': 2,
    'extractor_retries': 2,
    'fragment_retries': 2,
    'retries': 3,
    'socket_timeout': 10,
    # Anti-bot measures
    'age_limit': None,
    'writesubtitles': False,
    'writeautomaticsub': False,
    'cachedir': False,
    'no_cache': True,
}

# Set up Railway-compatible User-Agent (no cookies by default - smart handling)
user_agent = os.getenv('YT_USER_AGENT')
if user_agent:
    ytdl_options['user_agent'] = user_agent
    logging.info("🌐 Using custom User-Agent for Railway")
else:
    ytdl_options['user_agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    logging.info("🌐 Using default User-Agent")

logging.info("🧠 SMART MODE: No cookies by default, will use cookies only for bot detection")


ffmpeg_options = {
    'before_options': (
        '-reconnect 1 '
        '-reconnect_streamed 1 '
        '-reconnect_delay_max 5 '
        '-reconnect_at_eof 1 '
        '-multiple_requests 1 '
        '-rw_timeout 15000000 '
        '-nostdin'
    ),
    'options': (
        '-vn '
        '-bufsize 64k '
        '-acodec libopus '
        '-ab 128k '
        '-loglevel error'
    )
}

# Replace create_audio_source function
@backoff.on_exception(backoff.expo, Exception, max_tries=3)
async def create_audio_source(url: str, headers: dict | None = None) -> discord.FFmpegOpusAudio:
    """Create audio source with robust header handling"""
    try:
        # Build base options
        opts = dict(ffmpeg_options)
        
        # Handle headers properly for Railway authentication
        if headers:
            # Add important headers individually to before_options for better compatibility
            bo = opts.get('before_options', '')
            
            # Add User-Agent if present (most important for auth)
            if 'User-Agent' in headers:
                ua = headers['User-Agent'].replace('"', '\\"')  # Escape quotes
                bo += f' -user_agent "{ua}"'
            
            # Add Referer if present (helps with auth)
            if 'Referer' in headers:
                ref = headers['Referer'].replace('"', '\\"')
                bo += f' -referer "{ref}"'

            # Add full header block using -headers for everything yt-dlp provided (Cookie, Accept, etc.)
            # Sanitize CRLF to prevent header injection issues
            try:
                hdr_lines = []
                for k, v in headers.items():
                    if v is None:
                        continue
                    key = str(k).replace('\r', ' ').replace('\n', ' ')
                    val = str(v).replace('\r', ' ').replace('\n', ' ')
                    hdr_lines.append(f"{key}: {val}")
                if hdr_lines:
                    header_block = "\\r\\n".join(hdr_lines) + "\\r\\n"
                    bo += f' -headers "{header_block}"'
            except Exception as _:
                pass

            opts['before_options'] = bo
            logging.debug(
                f"FFmpeg with auth headers: UA={headers.get('User-Agent', 'none')[:50]}..., Has-Cookie={'Cookie' in headers}"
            )
        
        # Validate URL before passing to FFmpeg
        if not url or not url.startswith(('http://', 'https://')):
            raise ValueError(f"Invalid URL for FFmpeg: {url}")
            
        logging.info(f"Creating FFmpeg source for: {url[:100]}...")
        
        # Use from_probe with fallback method for better compatibility
        return await discord.FFmpegOpusAudio.from_probe(
            url,
            method='fallback',
            **opts
        )
    except Exception as e:
        logging.error(f"FFmpeg probe failed: {e}")
        # Fallback: try basic creation without probe
        try:
            # Keep the same header options for fallback attempt as well
            logging.info("Retrying FFmpeg with basic options (preserving headers)")
            return await discord.FFmpegOpusAudio.create(url, **opts)
        except Exception as e2:
            logging.error(f"FFmpeg create also failed: {e2}")
            raise e2





ytdl = youtube_dl.YoutubeDL(ytdl_options)

# Simple cache for recent searches to avoid re-processing
_search_cache = {}
_cache_max_size = 50
_cache_last_cleanup = time.time()
_cache_cleanup_interval = 3600  # Clean up every hour

def clear_music_cache():
    """Clear the music search cache to free memory."""
    global _search_cache
    _search_cache.clear()
    logging.info("Music search cache cleared")

def auto_cleanup_cache():
    """Automatically clean up cache based on time and memory usage."""
    global _search_cache, _cache_last_cleanup
    
    current_time = time.time()
    
    # Clean up every hour or if cache is getting too large
    if (current_time - _cache_last_cleanup > _cache_cleanup_interval or
        len(_search_cache) > _cache_max_size * 0.8):
        
        # Remove oldest entries if cache is getting full
        if len(_search_cache) > _cache_max_size * 0.7:
            items_to_remove = len(_search_cache) - int(_cache_max_size * 0.5)
            for _ in range(items_to_remove):
                if _search_cache:
                    oldest_key = next(iter(_search_cache))
                    del _search_cache[oldest_key]
            logging.info(f"Auto-cleanup: Removed {items_to_remove} old cache entries")
        
        _cache_last_cleanup = current_time

def get_cache_stats():
    """Get cache statistics for debugging."""
    return {
        'size': len(_search_cache),
        'max_size': _cache_max_size,
        'keys': list(_search_cache.keys())[:10]  # First 10 keys for debugging
    }

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('webpage_url')
        self.duration = data.get('duration')
        self.artist = data.get('artist') or data.get('uploader') # Store artist info

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()

        # Auto-cleanup cache before processing
        auto_cleanup_cache()

        # Check cache first
        cache_key = f"{url}_{stream}"
        if cache_key in _search_cache:
            cached_data = _search_cache[cache_key]
            logging.debug(f"Using cached data for {url}")
            filename = cached_data['url'] if stream else ytdl.prepare_filename(cached_data)
            return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=cached_data)

        def extract_info():
            # Clean and validate the URL
            clean_url = url.strip()
            
            # Check for malformed URLs that might cause DNS issues
            if clean_url and not clean_url.startswith(('http://', 'https://', 'www.')):
                # It's a search query, ensure it's properly formatted
                clean_url = clean_url.replace('\n', ' ').replace('\r', ' ')
                # Remove any potentially problematic characters
                import re
                clean_url = re.sub(r'[^\w\s\-\.\(\)\[\]\'\"]+', ' ', clean_url)
                clean_url = ' '.join(clean_url.split())  # Normalize whitespace
            
            try:
                # If it's not a URL, try simple YouTube search first
                if not clean_url.startswith(('http://', 'https://', 'www.')):
                    # PRIORITY: Simple YouTube search with android_embedded (most reliable)
                    logging.info("🚀 Trying simple YouTube search first (priority method)...")
                    simple_url = simple_youtube_search(clean_url)
                    if simple_url:
                        try:
                            logging.info(f"🔄 Using android_embedded extraction (fastest & most reliable)...")
                            android_config = {
                                'format': 'bestaudio/best',
                                'quiet': True,
                                'no_warnings': True,
                                'ignoreerrors': True,
                                'extractor_args': {
                                    'youtube': {
                                        'player_client': ['android_embedded'],
                                        'player_skip': ['webpage', 'configs'],
                                    }
                                },
                                'http_headers': {
                                    'User-Agent': 'com.google.android.youtube/17.31.35 (Linux; U; Android 11) gzip',
                                    'X-Youtube-Client-Name': '55',
                                    'X-Youtube-Client-Version': '17.31.35',
                                }
                            }
                            android_ytdl = youtube_dl.YoutubeDL(android_config)
                            result = android_ytdl.extract_info(simple_url, download=not stream)
                            logging.info(f"✅ Simple search + android_embedded successful!")
                            return result
                        except Exception as android_e:
                            logging.debug(f"Simple search android_embedded failed: {android_e}")
                    
                    # FALLBACK: Only if simple search fails, try yt-dlp searches
                    logging.info("🔄 Simple search failed, falling back to yt-dlp searches...")
                    search_strategies = [
                        f"ytsearch1:{clean_url}",  # Original user query
                    ]
                    
                    for search_strategy in search_strategies:
                        try:
                            logging.info(f"🔍 Fallback yt-dlp search: {search_strategy}")
                            result = ytdl.extract_info(search_strategy, download=not stream)
                            if result and 'entries' in result and result['entries']:
                                logging.info(f"✅ Fallback search successful: {search_strategy}")
                                return result
                            elif result and 'entries' not in result:
                                logging.info(f"✅ Fallback direct match: {search_strategy}")
                                return result
                            else:
                                logging.debug(f"Fallback search {search_strategy} returned empty results")
                                continue
                        except Exception as search_e:
                            logging.debug(f"Fallback search strategy failed: {search_strategy} - {search_e}")
                            continue
                    
                    # If all fallbacks fail, try additional extraction strategies
                    extraction_strategies = [
                        {
                            'name': 'android_embedded',
                            'config': {
                                'format': 'bestaudio/best',
                                'quiet': True,
                                'no_warnings': True,
                                'ignoreerrors': True,
                                'extractor_args': {
                                    'youtube': {
                                        'player_client': ['android_embedded'],
                                        'player_skip': ['webpage', 'configs'],
                                    }
                                },
                                'http_headers': {
                                    'User-Agent': 'com.google.android.youtube/17.31.35 (Linux; U; Android 11) gzip',
                                    'X-Youtube-Client-Name': '55',
                                    'X-Youtube-Client-Version': '17.31.35',
                                }
                            }
                        },
                        {
                            'name': 'ios_music',
                            'config': {
                                'format': 'bestaudio/best',
                                'quiet': True,
                                'no_warnings': True,
                                'ignoreerrors': True,
                                'extractor_args': {
                                    'youtube': {
                                        'player_client': ['ios'],
                                        'player_skip': ['webpage'],
                                    }
                                },
                                'http_headers': {
                                    'User-Agent': 'com.google.ios.youtubemusic/5.21 (iPhone14,3; U; CPU iOS 15_6 like Mac OS X)',
                                    'X-Youtube-Client-Name': '26',
                                    'X-Youtube-Client-Version': '5.21',
                                }
                            }
                        },
                        {
                            'name': 'tv_embedded',
                            'config': {
                                'format': 'bestaudio/best',
                                'quiet': True,
                                'no_warnings': True,
                                'ignoreerrors': True,
                                'extractor_args': {
                                    'youtube': {
                                        'player_client': ['tv_embedded'],
                                        'player_skip': ['webpage'],
                                    }
                                }
                            }
                        },
                        {
                            'name': 'minimal',
                            'config': {
                                'format': 'worst',
                                'quiet': True,
                                'no_warnings': True,
                                'ignoreerrors': True,
                                'no_check_certificate': True,
                            }
                        }
                    ]
                    
                    if simple_url:
                        for strategy in extraction_strategies:
                            try:
                                logging.info(f"🔄 Trying {strategy['name']} extraction...")
                                strategy_ytdl = youtube_dl.YoutubeDL(strategy['config'])
                                result = strategy_ytdl.extract_info(simple_url, download=not stream)
                                logging.info(f"✅ {strategy['name']} extraction successful!")
                                return result
                            except Exception as strategy_e:
                                logging.debug(f"{strategy['name']} extraction failed: {strategy_e}")
                                continue
                        
                        logging.error("All extraction strategies failed for found video")
                    
                    # If all search strategies fail, try with format fallbacks
                    raise Exception("All search strategies failed")
                else:
                    # Direct URL extraction
                    return ytdl.extract_info(clean_url, download=not stream)
            except Exception as e:
                logging.error(f"Error extracting info from {url}: {e}")
                
                # Try with different client configurations first
                config_fallbacks = ['android_fallback', 'web_fallback']
                
                for config_name in config_fallbacks:
                    try:
                        logging.info(f"🔄 Trying {config_name} configuration...")
                        fallback_ytdl = youtube_dl.YoutubeDL(ytdl_configs[config_name])
                        
                        if not clean_url.startswith(('http://', 'https://', 'www.')):
                            return fallback_ytdl.extract_info(f"ytsearch1:{clean_url}", download=not stream)
                        else:
                            return fallback_ytdl.extract_info(clean_url, download=not stream)
                    except Exception as config_e:
                        logging.debug(f"{config_name} configuration failed: {config_e}")
                        continue
                
                # If client fallbacks fail, try format fallbacks with original config
                format_fallbacks = [
                    'bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best',
                    'bestaudio/best',
                    'worstaudio/worst',
                    'best[height<=720]/best',
                    'best'
                ]
                
                for format_option in format_fallbacks:
                    try:
                        logging.info(f"🔄 Trying format: {format_option}")
                        fallback_options = ytdl_options.copy()
                        fallback_options['format'] = format_option
                        fallback_ytdl = youtube_dl.YoutubeDL(fallback_options)
                        
                        if not url.startswith(('http://', 'https://', 'www.')):
                            return fallback_ytdl.extract_info(f"ytsearch1:{url}", download=not stream)
                        else:
                            return fallback_ytdl.extract_info(url, download=not stream)
                    except Exception as format_e:
                        logging.debug(f"Format {format_option} failed: {format_e}")
                        continue
                
                # Final fallback: try simple YouTube search
                if not clean_url.startswith(('http://', 'https://', 'www.')):
                    logging.info("🔄 Trying simple YouTube search as final fallback...")
                    simple_url = simple_youtube_search(clean_url)
                    if simple_url:
                        try:
                            # Try with the simplest possible config
                            simple_config = {
                                'format': 'bestaudio/best',
                                'quiet': True,
                                'no_warnings': True,
                                'ignoreerrors': False,
                            }
                            simple_ytdl = youtube_dl.YoutubeDL(simple_config)
                            return simple_ytdl.extract_info(simple_url, download=not stream)
                        except Exception as simple_e:
                            logging.error(f"Simple search fallback failed: {simple_e}")
                            
                            # Final attempt: Try with most basic configuration possible
                            logging.info("🔄 Final attempt with basic configuration...")
                            if simple_url:
                                try:
                                    basic_config = {
                                        'format': 'worst',  # Use worst quality to avoid restrictions
                                        'quiet': True,
                                        'no_warnings': True,
                                        'ignoreerrors': True,  # Ignore errors and try anyway
                                        'no_check_certificate': True,
                                        'prefer_insecure': True,
                                        'extractor_args': {
                                            'youtube': {
                                                'player_client': ['android_embedded'],
                                                'skip': ['dash', 'hls'],
                                            }
                                        }
                                    }
                                    basic_ytdl = youtube_dl.YoutubeDL(basic_config)
                                    return basic_ytdl.extract_info(simple_url, download=not stream)
                                except Exception as basic_e:
                                    logging.debug(f"Basic config failed: {basic_e}")
                
                raise e

        try:
            # Add timeout to prevent hanging
            data = await asyncio.wait_for(
                loop.run_in_executor(None, extract_info),
                timeout=40.0  # Increased timeout to allow for all fallback strategies
            )
            
            logging.debug(f"Raw data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")

            if 'entries' in data:
                logging.debug(f"Found {len(data['entries'])} entries")
                if not data['entries']:
                    raise Exception("No search results found")
                data = data['entries'][0]
                logging.debug(f"Selected entry keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            
            # Validate the data has required fields
            if not data or not isinstance(data, dict):
                raise Exception("Invalid data format returned")
            
            if 'url' not in data and 'webpage_url' not in data:
                raise Exception("No valid URL found in search results")

            # Cache the result
            if len(_search_cache) >= _cache_max_size:
                # Remove oldest entry
                oldest_key = next(iter(_search_cache))
                del _search_cache[oldest_key]
            _search_cache[cache_key] = data

            filename = data['url'] if stream else ytdl.prepare_filename(data)
            
            logging.debug(f"Creating FFmpeg audio source with filename: {filename}")
            logging.debug(f"FFmpeg options: {ffmpeg_options}")
            
            try:
                audio_source = discord.FFmpegPCMAudio(filename, **ffmpeg_options)
                logging.info(f"✅ FFmpeg audio source created successfully")
                return cls(audio_source, data=data)
            except Exception as ffmpeg_error:
                logging.error(f"❌ FFmpeg audio source creation failed: {ffmpeg_error}")
                raise Exception(f"Audio processing failed: {str(ffmpeg_error)}")
        except asyncio.TimeoutError:
            logging.error(f"Extraction timed out for '{url}' after 40 seconds")
            raise Exception(f"Search timed out. Please try again with a different search term.")
        except Exception as e:
            error_msg = str(e)
            if "list index out of range" in error_msg:
                logging.error(f"Search returned no results for '{url}': {e}")
                raise Exception(f"No search results found for '{url}'. Try a different search term.")
            elif "No search results found" in error_msg:
                logging.error(f"Empty search results for '{url}': {e}")
                raise Exception(f"No videos found for '{url}'. Try a more specific search term.")
            elif "Invalid data format" in error_msg:
                logging.error(f"Invalid response format for '{url}': {e}")
                raise Exception(f"YouTube returned invalid data for '{url}'. Please try again.")
            else:
                logging.error(f"Failed to create YTDLSource for '{url}': {e}")
                raise Exception(f"Failed to load '{url}': {error_msg}")

# Queue to hold the songs
# Modify your song queue to include song info
song_queue = []  # Each item will be a tuple: (interaction, query, info)
current_song = None
loop_song = False
skip_votes = set()
previous_message = None
# Add at top with other globals
current_song_start = None

def _choose_best_audio_format(formats: list) -> dict | None:
    """Pick an audio-capable format URL from yt-dlp formats list.

    Preference order:
    - Audio-only (vcodec == 'none')
    - Preferred itags: 251 (webm/opus), 140 (m4a/aac), 250/249
    - Highest abr
    Fallback: any entry with acodec present and url available
    """
    if not formats:
        return None
    preferred_itags = {'251': 3, '140': 2, '250': 2, '249': 1}
    candidates = []
    for f in formats:
        url = f.get('url')
        if not url:
            continue
        acodec = (f.get('acodec') or '').lower()
        vcodec = (f.get('vcodec') or '').lower()
        has_audio = acodec and acodec != 'none'
        audio_only = vcodec == 'none'
        if not has_audio and not audio_only:
            continue
        itag = str(f.get('format_id') or '')
        itag_score = preferred_itags.get(itag, 0)
        abr = f.get('abr') or 0
        candidates.append((audio_only, itag_score, abr, f))
    if not candidates:
        return None
    # Sort by: audio_only desc, itag_score desc, abr desc
    candidates.sort(key=lambda t: (t[0], t[1], t[2]), reverse=True)
    return candidates[0][3]

def simple_youtube_search(query):
    """Simple YouTube search fallback when yt-dlp fails"""
    try:
        # Clean the query for URL encoding
        clean_query = re.sub(r'[^\w\s\-]', ' ', query)
        clean_query = ' '.join(clean_query.split())
        
        # Try multiple search approaches
        search_urls = [
            f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(clean_query)}",
            f"https://m.youtube.com/results?search_query={urllib.parse.quote_plus(clean_query)}",  # Mobile version
        ]
        
        headers_list = [
            {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            },
            {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
            }
        ]
        
        for search_url in search_urls:
            for headers in headers_list:
                try:
                    response = requests.get(search_url, headers=headers, timeout=10)
                    if response.status_code == 200:
                        # Look for video IDs in the response
                        video_id_matches = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', response.text)
                        if video_id_matches:
                            video_id = video_id_matches[0]
                            return f"https://www.youtube.com/watch?v={video_id}"
                except Exception as req_e:
                    logging.debug(f"Search request failed: {req_e}")
                    continue
        
        return None
    except Exception as e:
        logging.debug(f"Simple YouTube search failed: {e}")
        return None

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

    @discord.ui.button(label="Lyrics (Powered by Genius.com)", style=discord.ButtonStyle.secondary, emoji="<:genius:1324379192032231424>")
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
                        if current_length + len(line) + 1 > 1500:
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
                                f"<:genius:1324379192032231424> **Lyrics for {song} by {artist}**\n```\n{chunk}```"
                            )
                        else:
                            await interaction.followup.send(f"```\n{chunk}```")
                    return
                logging.info("No Genius lyrics found, trying YouTube captions")

            # Fallback to YouTube captions
            video_id = is_valid_youtube_url(self.youtube_url)
            
            try:
                # Run blocking transcript fetch in a thread
                transcript_list = await asyncio.to_thread(YouTubeTranscriptApi.list_transcripts, video_id)
                
                # Try different transcript types
                transcript = None
                for lang in ['en', 'en-US', 'en-GB']:
                    try:
                        transcript = await asyncio.to_thread(transcript_list.find_transcript, [lang])
                        break
                    except:
                        continue
                        
                if not transcript:
                    try:
                        transcript = await asyncio.to_thread(transcript_list.find_manually_created_transcript)
                    except:
                        transcript = await asyncio.to_thread(transcript_list.find_generated_transcript)
                        
                transcript_data = await asyncio.to_thread(transcript.fetch)
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
        
        # Try to connect with preferred region
        for region in PREFERRED_REGIONS:
            try:
                #await channel.edit(rtc_region=region)
                await channel.connect()
                embed = discord.Embed(
                    title="Voice Channel", 
                    description=f"Joined {channel} (Region: {region})", 
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed)
                return
            except discord.HTTPException:
                continue
                
        # Fallback to default if no preferred region works
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
                for region in PREFERRED_REGIONS:
                    try:
                        #await channel.edit(rtc_region=region)
                        await channel.connect()
                        break
                    except discord.HTTPException:
                        continue
                else:
                    await channel.connect()  # Fallback
            else:
                embed = discord.Embed(
                    title="Error",
                    description="You are not in a voice channel!",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed)
                return

        # Extract music info with timeout using YTDLSource
        try:
            player = await asyncio.wait_for(
                YTDLSource.from_url(query, loop=asyncio.get_event_loop(), stream=True),
                timeout=45.0  # Increased timeout for complex extractions
            )
        except asyncio.TimeoutError:
            embed = discord.Embed(
                title="Error",
                description="Search timed out. Please try again with a different search term.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
            return
        except Exception as e:
            error_msg = str(e)
            if "403" in error_msg or "Forbidden" in error_msg:
                embed = discord.Embed(
                    title="Error",
                    description="YouTube is currently blocking requests. This is a temporary issue. Please try again in a few minutes or try a different song.",
                    color=discord.Color.red()
                )
            elif "Requested format is not available" in error_msg:
                embed = discord.Embed(
                    title="Error",
                    description="This video's format is not available. Please try a different song or search term.",
                    color=discord.Color.red()
                )
            elif "Search timed out" in error_msg:
                embed = discord.Embed(
                    title="Error",
                    description="Search timed out. Please try again with a different search term.",
                    color=discord.Color.red()
                )
            else:
                embed = discord.Embed(
                    title="Error",
                    description=f"Failed to find music: {error_msg}",
                    color=discord.Color.red()
                )
            await interaction.followup.send(embed=embed)
            return

        # Add the song to the queue  
        song_queue.append((interaction, query, player))

        await interaction.followup.send(
            f"Added **{player.title}** to the queue.",
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
    
    # Edit previous message if it exists
    if previous_message:
        try:
            # Get info from current song that just finished
            if not current_song:
                raise ValueError("No current_song to summarize")
            _, _, old_player = current_song
            played_embed = discord.Embed(
                title="Played",
                description=f"[{old_player.title}]({old_player.url})",
                color=discord.Color.green()
            )
            if duration := old_player.duration or 0:
                minutes = duration // 60
                seconds = duration % 60
                played_embed.add_field(name="Duration", value=f"{minutes:02d}:{seconds:02d}")
            
            if hasattr(old_player.data, 'get') and old_player.data.get('thumbnail'):
                played_embed.set_thumbnail(url=old_player.data['thumbnail'])
            await previous_message.edit(embed=played_embed, view=None)
        except Exception as e:
            logging.error(f"Failed to edit previous message: {e}")

    if loop_song and current_song:
        interaction, query, player = current_song
    elif song_queue:
        interaction, query, player = song_queue.pop(0)
        current_song = (interaction, query, player)
    else:
        current_song = None
        return

    try:
        # Player is already a YTDLSource object, ready to use
        duration = player.duration or 0
        current_song_start = time.time()

        # Use the player directly as the audio source
        source = player

        def after_playing(error):
            if error:
                # Log more details about FFmpeg errors to help diagnose Railway issues
                error_msg = str(error)
                if "return code" in error_msg.lower():
                    logging.error(f"🔥 FFmpeg process error: {error}")
                    logging.error(f"This may indicate invalid URL or auth headers on Railway")
                else:
                    logging.error(f"Playback error: {error}")
            eventloop.event_loop.call_soon_threadsafe(
                lambda: asyncio.create_task(play_next_song())
            )

        interaction.guild.voice_client.play(
            source,
            after=after_playing
        )

        # Create new message for current song
        embed = discord.Embed(
            title="Now Playing",
            description=f"[{player.title}]({player.url})",
            color=discord.Color.blue()
        )
        if duration:
            minutes = duration // 60
            seconds = duration % 60
            embed.add_field(name="Duration", value=f"{minutes:02d}:{seconds:02d}")
            
        # Set thumbnail if available
        if hasattr(player.data, 'get') and player.data.get('thumbnail'):
            embed.set_thumbnail(url=player.data['thumbnail'])
        embed.set_author(
            name=f"Requested by {interaction.user}",
            icon_url=interaction.user.display_avatar.url
        )
        embed.set_footer(
            text=f"{interaction.client.user.name}",
            icon_url=interaction.client.user.display_avatar.url
        )
        view = MusicView(interaction)
        view.set_url(player.url)
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
            for i, (inter, query, player) in enumerate(song_queue):
                description += f"{i+1}. [{player.title}]({player.url})\n"
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
                    if current_length + len(line) + 1 > 1500:
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
                            f"<:genius:1324379192032231424> **Lyrics for {song} by {artist}**\n```\n{chunk}```"
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
import discord, os, logging, sys, random, re, aiohttp, asyncio, tempfile, io, google.generativeai as genai
from google import genai as palm
try:
    from ddgs import DDGS  # New package name per upstream rename
except Exception:  # Fallback for older envs
    from duckduckgo_search import DDGS
from functools import partial
from datetime import datetime
from bs4 import BeautifulSoup
from functools import lru_cache
from typing import List, Any
from dotenv import load_dotenv
from urllib.parse import quote_plus, urlparse
from engine.utils import is_image_request, extract_image_prompt

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv('GEMINI_API')

# Configure the Google Generative AI SDK
genai.configure(api_key=GOOGLE_API_KEY)
genai_client = palm.Client(api_key=os.getenv('GEMINI_PRO_API_KEY'), http_options={'api_version':'v1alpha'})
# Configure logging for Unicode
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

from engine.ai.gemini_models import (
    pro10creative,
    pro15creative,
    pro15normal,
    flash15normal,
    flash15creative,
    flash158bn,
    flash158bc,
    flash2
)

# Model fallback chains
MODEL_CHAINS = {
    'pro15normal': ['pro15normal', 'flash2', 'flash15normal', 'flash158bn'],
    'flash2': ['flash2', 'flash15normal', 'flash158bn'],
    'pro15creative': ['pro15creative', 'flash15creative', 'flash158bc'],
    'flash15normal': ['flash15normal', 'flash158bn']
}

# Image editing models
PRIMARY_IMAGE_MODEL = "gemini-2.5-flash-image-preview"
FALLBACK_IMAGE_MODEL = "gemini-2.0-flash-preview-image-generation"

# Track quota failures
model_quota_failures = {}

async def try_model_chain(query, initial_model_name, tools=None):
    """Try models in sequence when quota exhausted"""
    global model_quota_failures
    
    # Get appropriate model chain
    chain = MODEL_CHAINS.get(initial_model_name, [initial_model_name])
    
    # Try each model in chain
    for model_name in chain:
        # Skip if quota exhausted today
        if model_name in model_quota_failures:
            last_failure = model_quota_failures[model_name]
            if datetime.now().date() == last_failure.date():
                logging.info(f"Skipping {model_name} - quota exhausted today")
                continue
            else:
                del model_quota_failures[model_name]
        
        try:
            model = globals()[model_name]
            logging.info(f"Trying model: {model_name}")
            if tools:
                response = model.generate_content(query, tools=tools)
            else:
                response = model.generate_content(query)
            return response
            
        except Exception as e:
            if "quota" in str(e).lower():
                model_quota_failures[model_name] = datetime.now()
                logging.warning(f"Quota exhausted for {model_name}, trying next model")
                continue
            raise
    
    logging.error("All models in chain exhausted")
    return None

async def get_active_image_model():
    """Get active image model with fallback support"""
    global model_quota_failures
    
    # Check if we should reset quota failure status for image models
    today = datetime.now().date()
    
    # Clean up old quota failures
    for model_name in list(model_quota_failures.keys()):
        if model_quota_failures[model_name].date() != today:
            del model_quota_failures[model_name]
            logging.info(f"Image model quota status reset for {model_name}")
    
    # Use fallback if primary quota was exhausted today
    primary_name = PRIMARY_IMAGE_MODEL.replace("-", "").replace(".", "")  # Convert to var name
    fallback_name = FALLBACK_IMAGE_MODEL.replace("-", "").replace(".", "")
    
    if PRIMARY_IMAGE_MODEL in str(model_quota_failures):
        logging.info(f"Using fallback image model {FALLBACK_IMAGE_MODEL} due to quota exhaustion")
        return FALLBACK_IMAGE_MODEL
    return PRIMARY_IMAGE_MODEL

def extract_current_query(prompt: str) -> str:
    """Extract clean search query from bot prompt format."""
    # Remove 'seeyuh' and clean prompt
    prompt = prompt.lower().replace('seeyuh', '').strip()
    
    # Extract query using regex pattern match
    query_pattern = re.compile(r"Current query from .*?:(.*)", re.IGNORECASE)
    match = query_pattern.search(prompt)
    
    if match:
        query = match.group(1).strip()
    else:
        query = prompt.strip()

    # Preserve URLs if present  
    urls = URL_PATTERN.findall(query)
    if urls:
        return urls[0]

    # Clean query
    query = query.rstrip('.!?')
    query = ' '.join(query.split()) # Normalize whitespace
    words = query.split()

    if not words:
        return ""

    # Try pattern matching first
    for pattern_type, patterns in PATTERNS.items():
        for pattern in patterns:
            match = pattern.search(query)
            if match:
                matched_query = match.group(0)
                # Get surrounding context 
                idx = query.find(matched_query)
                # Keep 3 words before match
                before = query[:idx].split()[-3:] if idx > 0 else []
                # Increase to 5 words after match for better context
                after = query[idx+len(matched_query):].split()[:10]
                context_query = ' '.join(filter(None, before + [matched_query] + after))
                
                # Only return pattern match if it captures most of original query
                if len(context_query.split()) >= len(words) * 0.7:
                    return context_query[:150]
                
    # Fall back to keyword scoring if no pattern match
    scores = {}
    for pos, word in enumerate(words):
        score = 0
        for category, weights in KEYWORDS.items():
            for weight, terms in weights.items():
                if any(term in ' '.join(words[max(0,pos-1):pos+2]) for term in terms):
                    score += {'high': 3, 'medium': 2, 'low': 1}[weight]
        scores[pos] = score

    # Only proceed with window scoring if we have enough words
    window = min(8, len(words))  # Adjust window size for short queries
    if window > 0:
        total_scores = []
        for i in range(len(words) - window + 1):
            total_scores.append((i, sum(scores[j] for j in range(i, i + window))))
            
        if total_scores:  # Check if we have any scores
            start = max(total_scores, key=lambda x: x[1])[0]
            end = min(start + window, len(words))
            return ' '.join(words[start:end])

    # Fallback to all words if query is short, otherwise first 15
    return ' '.join(words[:15])[:150]

# Pre-compile regex patterns
PATTERNS = {
    'position': [
        re.compile(r"(?:who|what).+?(?:is|are|was|were).+?(?:the|current|new|previous|former|next|upcoming|latest).+?(?:minister|president|ceo|leader|owner|creator|founder|developer|director|manager|head|chief|boss|executive)"),
        re.compile(r"who.+?(?:leads|runs|heads|owns|created|founded|developed|made|manages|directs|controls|operates).+?(?:now|currently|previously|formerly|recently|lately)")
    ],
    'media': [
        re.compile(r"(?:new|latest|trending|popular)?.+?(?:album|song|movie|show|video|film|series|episode|trailer)"),
        re.compile(r"(?:tracklist|tracks|songs|discography|playlist|soundtracks|ost)"),
        re.compile(r"(?:watch|stream|play|listen).+?(?:video|movie|show|song|music)"),
        re.compile(r"what.+?(?:trending|popular|viral|recommended|suggested)"),
        re.compile(r"(?:new|latest|trending|popular|viral|upcoming|recent|hot)?.+?(?:movie|show|video|film|series|episode|trailer|teaser|preview|clip|footage|stream|broadcast|live)"),
        re.compile(r"(?:watch|stream|play|view|see|check).+?(?:video|movie|show|film|clip|trailer|episode|series|channel|content)"),
        re.compile(r"(?:youtube|netflix|amazon|hulu|disney|twitch|tiktok|instagram).+?(?:video|stream|content|channel)")
    ],
    'visual': [
        re.compile(r"(?:show|display|see|look|send|search).+?(?:image|picture|photo|pic|thumbnail|screenshot)"),
        re.compile(r"(?:what|how).+?(?:looks|appears|displays|shown|visualized)"),
        re.compile(r"(?:new|latest|trending)?.+?(?:image|photo|picture|artwork|fanart|poster)"),
        re.compile(r"(?:show|display|see|look|view|check).+?(?:image|picture|photo|pic|photograph|snapshot|screenshot|thumbnail|preview|visual)"),
        re.compile(r"(?:what|how).+?(?:does|did|will).+?(?:look|appear|seem|show|display|present).+?(?:like|as|in)"),
        re.compile(r"(?:find|get|give|search).+?(?:image|picture|photo|pic|visual|screenshot).+?(?:of|about|for|showing|displaying)")
    ],
    'news': [
        re.compile(r"(?:latest|recent|breaking|current|today's|live).+?(?:news|update|development|story|report|coverage|situation|event)"),
        re.compile(r"(?:what).+?(?:happened|occurring|developing|trending|changing).+?(?:now|today|recently|lately|currently)"),
        re.compile(r"(?:tell|inform|update).+?(?:about|on|regarding).+?(?:latest|current|recent|new)")
    ],
    'status': [
        re.compile(r"(?:current|latest|new).+?(?:version|update|status|patch|release)"),
        re.compile(r"(?:weather|temperature|forecast|conditions).+?(?:in|at|for|now|today)"),
        re.compile(r"(?:price|cost|worth|value|stock|market).+?(?:of|for|now|current)"),
        re.compile(r"(?:current|latest|real-time|live).+?(?:status|condition|state|situation|position|standing)"),
        re.compile(r"(?:weather|temperature|forecast|price|stock|score|rating|rank).+?(?:now|today|current|latest|live)"),
        re.compile(r"(?:how|what).+?(?:is|are).+?(?:going|doing|performing|working|running).+?(?:now|currently|lately|recently)")
    ],
    'events': [
        re.compile(r"what.+?(?:happened|going|occurred|done|changed).+?(?:to|with|in)"),
        re.compile(r"(?:news|latest|update|story|coverage|report).+?(?:about|on|regarding|for)")
    ]
}

# Enhanced keywords with weights
KEYWORDS = {
    'media': {
        'very_high': set(['youtube', 'netflix', 'prime video', 'hulu', 'twitch', 'disney+', 'spotify', 'apple music', 'tiktok', 'instagram reels']),
        'high': set(['video', 'movie', 'show', 'trailer', 'episode', 'film', 'stream', 'watch', 'series', 'documentary', 'podcast', 'broadcast']),
        'medium': set(['tracklist', 'album', 'song', 'release', 'music', 'playlist', 'channel', 'content creator', 'vlog', 'gaming']),
        'low': set(['listen', 'hear', 'play', 'entertainment', 'audio', 'clip', 'preview'])
    },
    'visual': {
        'very_high': set(['show me', 'display image', 'find picture', 'search photo', 'get image of', 'look up picture']),
        'high': set(['picture of', 'image of', 'photo of', 'look like', 'appearance of', 'visual of', 'screenshot of']),
        'medium': set(['display', 'see', 'visual', 'artwork', 'screenshot', 'illustration', 'graphic', 'poster', 'thumbnail']),
        'low': set(['appear', 'looks', 'show', 'preview', 'view', 'visible', 'seen'])
    },
    'time': {
        'very_high': set(['right now', 'currently', 'real time', 'in progress', 'live update', 'as we speak', 'at this moment']),
        'high': set(['today', 'now', 'current', 'latest', 'live', 'breaking', 'instant', 'immediate']),
        'medium': set(['recent', 'upcoming', 'this', 'new', 'fresh', 'just in', 'trending']),
        'low': set(['soon', 'later', 'next', 'future', 'coming', 'expected', 'scheduled'])
    },
    'query': {
        'very_high': set(['what exactly is', 'how specifically', 'where exactly', 'when precisely', 'tell me specifically', 'explain in detail']),
        'high': set(['what is', 'how to', 'where can i', 'when will', 'why does', 'which one', 'who is', 'what are', 'how does']),
        'medium': set(['tell', 'show', 'give', 'find', 'search', 'explain', 'describe', 'inform', 'guide']),
        'low': set(['know', 'get', 'see', 'explain', 'what', 'who', 'where', 'when', 'how', 'why', 'which', 'check'])
    },
    'topic': {
        'very_high': set(['breaking news', 'live updates', 'emergency alert', 'critical update', 'urgent announcement', 'developing story']),
        'high': set(['weather', 'price', 'score', 'news', 'update', 'trending', 'viral', 'popular', 'latest development']),
        'medium': set(['president', 'minister', 'leader', 'celebrity', 'influencer', 'event', 'situation', 'incident', 'announcement']),
        'low': set(['about', 'info', 'details', 'facts', 'information', 'status', 'condition', 'state'])
    },
    'status': {
        'very_high': set(['current status', 'live status', 'real-time condition', 'active monitoring']),
        'high': set(['tracking', 'monitoring', 'status update', 'condition report', 'latest status']),
        'medium': set(['progress', 'development', 'situation', 'state', 'position']),
        'low': set(['update', 'check', 'verify', 'confirm', 'track'])
    }
}

# FIXED: Reduced cache size from 1000 to 200 to prevent memory bloat
@lru_cache(maxsize=200)
def needs_realtime_data(query: str) -> bool:
    query = ' '.join(query.lower().split())
        
    # Pattern matching with expanded patterns
    for patterns in PATTERNS.values():
        if any(pattern.search(query) for pattern in patterns):
            return True
            
    # Detect question patterns about recent events/news
    question_start = any(q in query for q in ['what', 'why', 'how', 'when', 'where', 'who'])
    tense = any(w in query for w in ['did', 'was', 'were', 'had', 'happened', 'occurred', 'changed', 'going', 'done', 'doing', 'will', 'is', 'are'])
    
    if question_start and tense:
        return True
    
    # Lower threshold for scoring
    score = 0
    words = set(query.split())
    
    for category in KEYWORDS.values():
        if words & category['very_high']:
            score += 0.5
        if words & category['high']:
            score += 0.3
        if words & category['medium']:
            score += 0.2
        if words & category['low']:
            score += 0.1
        if category in ['time', 'topic', 'status', 'query']:
            score *= 1.5
        
    return score >= 0.7

# Add link detection regex with enhanced pattern
URL_PATTERN = re.compile(
    r'(?:(?:https?:)?\/\/)?'  # Protocol (optional)
    r'(?:(?:[\w-]+\.)+[\w-]+)'  # Domain
    r'(?:\/[^\s]*)?'  # Path (optional)
    r'(?:\?[^\s]*)?'  # Query parameters (optional)
    r'(?:\#[^\s]*)?'  # Fragment (optional)
    r'(?:https?:)?\/\/(?:(?:www\.)?(?:youtube\.com|youtu\.be))\/[a-zA-Z0-9_-]+|'  # YouTube URLs
    r'(?:https?:)?\/\/(?:[\w-]+\.)+[\w-]+(?:\/[^\s]*)?'  # Other URLs
)

# NOTE: lru_cache doesn't work with async functions - this cache is ineffective
# FIXED: Reduced from 50 to 20 and added note for future async cache implementation
@lru_cache(maxsize=20)
async def scrape_url(url: str) -> str:
    """Scrape content from specific URL"""
    # Add protocol if missing
    if not url.startswith('http'):
        url = 'https:' + url if url.startswith('//') else 'https://' + url
        
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Remove scripts, styles
                    for script in soup(["script", "style"]):
                        script.decompose()
                        
                    text = soup.get_text()
                    lines = [line.strip() for line in text.splitlines() if line.strip()]
                    return "\n".join(lines)[:1000]
    except Exception as e:
        logging.error(f"Failed to scrape {url}: {e}")
        return None
    
# FIXED: Reduced cache size from 100 to 30 to save memory
@lru_cache(maxsize=30)
def get_search_type(query: str) -> str:
    # Expanded keyword categories
    keywords = {
        'image': {
            'direct': ['image', 'picture', 'photo', 'pic', 'img', 'photograph', 'snapshot', 'screencap', 'screenshot'],
            'actions': ['show', 'display', 'see', 'look', 'view', 'find', 'search'],
            'descriptive': ['visual', 'appearance', 'looks like', 'preview', 'thumbnail', 'avatar', 'icon', 'logo'],
            'formats': ['jpg', 'png', 'gif', 'jpeg', 'illustration', 'drawing', 'artwork', 'meme', 'infographic'],
            'requests': ['show me', 'what does it look like', 'how does it appear', 'can i see', 'got any pics']
        },
        'video': {
            'direct': ['video', 'movie', 'clip', 'footage', 'film', 'recording', 'reel', 'stream'],
            'actions': ['watch', 'play', 'stream', 'view', 'check out', 'see'],
            'platforms': ['youtube', 'vimeo', 'tiktok', 'twitch', 'instagram', 'facebook', 'netflix'],
            'descriptive': ['animation', 'trailer', 'episode', 'broadcast', 'live', 'series', 'show', 'vlog'],
            'formats': ['mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mkv'],
            'requests': ['watch this', 'how to video', 'tutorial on', 'streaming now']
        },
        'news': {
            'direct': ['news', 'article', 'story', 'report', 'coverage', 'press', 'media'],
            'time': ['latest', 'recent', 'today', 'breaking', 'current', 'update', 'live'],
            'topics': ['headlines', 'events', 'developments', 'analysis', 'editorial', 'opinion'],
            'sources': ['newspaper', 'magazine', 'journal', 'publication', 'agency', 'network'],
            'requests': ['what happened', 'tell me about', 'whats new with', 'latest on']
        }
    }

    # Skip AI generation requests
    skip_phrases = [
        'generate', 'create', 'make', 'draw', 'paint', 'design'
    ]
    query_lower = query.lower()
    
    if any(phrase in query_lower for phrase in skip_phrases):
        return 'text'

    # Score calculation function
    def calculate_score(category_dict: dict) -> float:
        score = 0
        weights = {
            'direct': 2.0,
            'actions': 1.5,
            'descriptive': 1.2,
            'formats': 1.8,
            'platforms': 1.6,
            'requests': 1.7,
            'time': 2.0,
            'topics': 1.8,
            'sources': 1.5
        }
        
        for category, weight in weights.items():
            if category in category_dict:
                matches = sum(1 for kw in category_dict[category] if kw in query_lower)
                score += matches * weight
                exact_matches = sum(1 for kw in category_dict[category] if f" {kw} " in f" {query_lower} ")
                score += exact_matches * 0.5
                
        return score

    # Calculate scores
    image_score = calculate_score(keywords['image'])
    video_score = calculate_score(keywords['video']) 
    news_score = calculate_score(keywords['news'])

    scores = {
        'image': image_score,
        'video': video_score,
        'news': news_score
    }

    # Threshold and comparison
    min_score = 1.0
    score_difference = 0.5

    max_score = max(scores.values())
    if max_score < min_score:
        return 'text'

    # Find type with highest score
    max_type = max(scores.items(), key=lambda x: x[1])[0]
    
    # Check if scores are too close
    for type_, score in scores.items():
        if type_ != max_type and abs(score - max_score) < score_difference:
            # Tiebreakers
            if 'news' in query_lower or any(w in query_lower for w in keywords['news']['time']):
                return 'news'
            if any(p in query_lower for p in keywords['video']['platforms']):
                return 'video'
            return 'text'
            
    return max_type

async def enhance_search_query(query: str, context: str) -> str:
    """Use Gemini to produce a concise search query when helpful; otherwise return input.
    Avoids external DDG chat dependency per upstream changes.
    """
    try:
        # Keep this tiny; models should not hallucinate beyond user prompt.
        systemInstruction = (
            "Given a user's question and minimal context, produce a concise web search query. "
            "Return only the query text without quotes."
        )
        prompt = f"Context: {context[:500]}\nQuestion: {query}\nQuery:"
        response = await try_model_chain((systemInstruction, prompt), 'flash2')
        if response and response.text:
            candidate = response.text.strip().splitlines()[0][:200]
            # fallback to original if too short
            return candidate if len(candidate) >= max(8, len(query)//2) else query
    except Exception as e:
        logging.warning(f"Gemini query enhancement fallback: {e}")
    return query

# NOTE: lru_cache doesn't work with async functions - this cache is ineffective
# FIXED: Reduced from 100 to 30 and added note for future async cache implementation
@lru_cache(maxsize=30)
async def get_search_results(query: str, prompt: str, num_results: int = 3) -> str:    
    search_type = get_search_type(query)
    enhanced_query = await enhance_search_query(query, prompt)
    try:
        backends = [b.strip() for b in os.getenv('DDG_TEXT_BACKENDS', 'google,brave,yahoo,auto').split(',') if b.strip()]
        results = None
        with DDGS() as ddgs:
            if search_type == 'text':
                # ddgs no longer supports 'html/lite/api' backends; let engine auto-select
                try:
                    results = ddgs.text(
                        enhanced_query,
                        region='wt-wt',
                        safesearch='moderate',
                        max_results=num_results
                    )
                except Exception as e:
                    logging.warning(f"DuckDuckGo text search failed: {e}")
            elif search_type == 'image':
                # Try up to 3 times with small backoff
                for attempt in range(3):
                    try:
                        results = ddgs.images(
                            enhanced_query,
                            region='wt-wt',
                            safesearch='moderate',
                            max_results=num_results
                        )
                        if results:
                            break
                    except Exception as e:
                        logging.warning(f"DuckDuckGo images failed (attempt {attempt+1}/3): {e}")
                    await asyncio.sleep(0.8 + 0.4 * attempt)
            elif search_type == 'news':
                try:
                    results = ddgs.news(
                        enhanced_query,
                        region='wt-wt',
                        safesearch='moderate',
                        timelimit='m',
                        max_results=num_results
                    )
                except Exception as e:
                    logging.warning(f"DuckDuckGo news failed: {e}")
            elif search_type == 'video':
                try:
                    results = ddgs.videos(
                        enhanced_query,
                        region='wt-wt',
                        safesearch='moderate',
                        max_results=num_results
                    )
                except Exception as e:
                    logging.warning(f"DuckDuckGo videos failed: {e}")

        if not results:
            return "No results found."

        formatted_results = []
        for r in results:
                if search_type == 'text':
                    entry = f"Title: {r.get('title', 'No Title')}\n"
                    entry += f"Description: {r.get('body', 'No Description')}\n"
                    if r.get('date'):
                        entry += f"Date: {r['date']}\n" 
                    url = r.get('href', '#')
                    domain = urlparse(url).netloc.replace("www.", "") if url != '#' else 'Unknown'
                    entry += f"Source: {domain}\n"
                    entry += f"URL: {url}\n"
                
                elif search_type == 'news':
                    title = r.get('title', 'No title')
                    desc = r.get('body', 'No description')
                    url = r.get('url', '#')
                    date = r.get('date', 'No date')
                    domain = urlparse(url).netloc.replace("www.", "") if url != '#' else 'Unknown source'
                    source = f"Source: [{domain}]({url})"
                    entry = f"Title: {title}\nDate: {date}\n{source}\n{desc}"
                    
                elif search_type == 'image':
                    title = r.get('title', 'No title')
                    image_url = r.get('image', '#')
                    source_url = r.get('url', '#')
                    domain = urlparse(source_url).netloc.replace("www.", "") if source_url != '#' else 'Unknown source'
                    source = f"Source: [{domain}]({source_url})"
                    dimensions = f"{r.get('width','?')}x{r.get('height','?')}"
                    entry = f"Title: {title}\n{source}\nSize: {dimensions}\nImage URL: {image_url}"
                    
                elif search_type == 'video':
                    title = r.get('title', 'No title')
                    link = r.get('content', '#')
                    domain = urlparse(link).netloc.replace("www.", "") if link != '#' else 'Unknown source'
                    duration = r.get('duration', 'Unknown duration')
                    publisher = r.get('publisher', domain)
                    published = r.get('published', 'Unknown date')
                    
                    # Safe handling of view count
                    try:
                        views = r.get('statistics', {}).get('viewCount', '0')
                        view_count = f"{int(views):,}" if views and views.isdigit() else '0'
                    except (ValueError, AttributeError):
                        view_count = '0'
                        
                    entry = f"Title: {title}\nSource: [{publisher}]({link})\nDuration: {duration} | Views: {view_count} | Date: {published}"
                else:
                    entry = f"Title: {r.get('title', 'No Title')}\n"
                    entry += f"Description: {r.get('body', 'No Description')}\n"
                    if r.get('date'):
                        entry += f"Date: {r['date']}\n" 
                    url = r.get('href', '#')
                    domain = urlparse(url).netloc.replace("www.", "") if url != '#' else 'Unknown'
                    entry += f"Source: {domain}\n"
                    entry += f"URL: {url}\n"
                
                formatted_results.append(entry)
            
        if search_type == 'video':
            instruction = (
                "NOTE - Instruction to AI: Provide only valid video links to user in [Title](Link) format. "
                "Always send single best matching video result, only send more than one results if needed according to the context."
            )
        elif search_type == 'image':
            instruction = (
                "NOTE - Instruction to AI: Provide only valid image links to user in [Title](Link) format. "
                "Always send single best matching image result, only send more than one results if needed according to the context."
            )
        else:
            instruction = ""

        formatted_results.insert(0, instruction)
        return "\n\n".join(formatted_results)
            
    except Exception as e:
        logging.error(f"DuckDuckGo search error: {e}")
        return f"Search failed: {str(e)}"
    
# NOTE: lru_cache doesn't work with async functions - this cache is ineffective
# FIXED: Reduced from 100 to 30 and added note for future async cache implementation
@lru_cache(maxsize=30) 
async def get_ai_response(prompt, message):
    current_query = extract_current_query(prompt)
    logging.info(f"Extracted query: {current_query}")
    
    # (Removed duplicate early image branch; handled below via model switch)
    
    # Check if query needs thinking model
    use_thinking = any(word in current_query.lower() for word in ['think', 'reason', 'reasoning'])
    # Image requests take precedence over thinking
    is_image = is_image_request(current_query)
    
    # Configure model settings
    config = {
        'thinking_config': {'include_thoughts': True} if (use_thinking and not is_image) else None
    }
    
    # Set model based on query type
    if is_image:
        active_image_model = await get_active_image_model()
        model_name = active_image_model
    else:
        model_name = 'gemini-2.0-flash-thinking-exp-01-21' if use_thinking else 'flash2'
    
    # Handle web enrichment for both text and image requests
    if not is_image:
        # Check for URLs first and skip image-like URLs
        urls = URL_PATTERN.findall(current_query)
        def _looks_like_image(u: str) -> bool:
            u = u.lower()
            return any(u.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.tiff', '.svg']) or 'format=webp' in u
        if urls and not any(_looks_like_image(u) for u in urls):
            content = await scrape_url(urls[0])
            if content:
                domain = urlparse(urls[0]).netloc.replace("www.", "")
                prompt = (
                    f"Content from {domain}:\n{content[:20000]}...\n\n"
                    f"{prompt}"
                )
        # Only check realtime data if no URLs found
        elif needs_realtime_data(current_query):
            logging.info(f"Real-time data needed (query: {current_query})")
            search_results = await get_search_results(current_query, prompt)
            if search_results:
                prompt = (
                    f"Based on current data for '{current_query}':\n\n"
                    f"{search_results}\n\n"
                    f"{prompt}"
                )
    else:
        # For image requests that ask for information + image (like "who is X show me image")
        # Extract the information query part and search for it
        info_query = current_query.lower()
        for keyword in ["show me image", "show me picture", "show image", "show picture", "find image", "find picture", "get image", "get picture"]:
            if keyword in info_query:
                info_query = info_query.replace(keyword, "").strip()
                break
        
        if info_query and len(info_query) > 3:  # Only search if there's substantial content
            logging.info(f"Image request with info query: {info_query}")
            search_results = await get_search_results(info_query, prompt)
            if search_results:
                prompt = (
                    f"Based on information about '{info_query}':\n\n"
                    f"{search_results}\n\n"
                    f"{prompt}\n\nGenerate both informative text and a relevant image."
                )
        
    systemInstruction = f"You are a discord bot named seeyuh. arkodeep is your developer, your responses are chill asf and very informal gen-z style. You are an automoderation, entertainment, music and games bot but also designed to help users with their queries. You will generate responses using AI and try using same languge as the query. You can provide information about the bot, list available commands, respond to user queries and access latest data from internet. You can use the `/help` command to see available commands."
    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    query = f"\n{systemInstruction} Today's date and time is {current_datetime}", f"\n{prompt}"
    logging.info(f"Query to AI: {query}")
    try:
        if is_image:
            # For image generation, pass prompt twice as provided by user
            for attempt in range(2):  # Try primary then fallback
                try:
                    logging.info(f"Using image model: {model_name}")
                    img_response = genai_client.models.generate_content(
                        model=model_name,
                        contents=(f"You are a discord bot named seeyuh.", f"\n{prompt}") if isinstance(prompt, str) else prompt,
                        config={
                            'response_modalities': ['TEXT', 'IMAGE']
                        }
                    )
                    break  # Success, exit retry loop
                except Exception as e:
                    logging.error(f"Image model {model_name} failed: {e}")
                    if "quota" in str(e).lower():
                        model_quota_failures[model_name] = datetime.now()
                        logging.warning(f"Quota exhausted for {model_name}")
                    
                    if attempt == 0 and model_name == PRIMARY_IMAGE_MODEL:
                        model_name = FALLBACK_IMAGE_MODEL
                        logging.info(f"Switching to fallback image model: {model_name}")
                        continue
                    else:
                        raise e
                        
            # Gather first image and any accompanying text
            out_text = None
            out_image_bytes = None
            
            # Check if response has candidates and content
            if (img_response and 
                hasattr(img_response, 'candidates') and 
                img_response.candidates and 
                len(img_response.candidates) > 0 and
                hasattr(img_response.candidates[0], 'content') and
                img_response.candidates[0].content and
                hasattr(img_response.candidates[0].content, 'parts') and
                img_response.candidates[0].content.parts):
                
                for part in img_response.candidates[0].content.parts:
                    if hasattr(part, 'inline_data') and part.inline_data is not None and out_image_bytes is None:
                        out_image_bytes = part.inline_data.data
                    elif hasattr(part, 'text') and part.text and not out_text:
                        out_text = part.text
            else:
                logging.error("Invalid Gemini image response structure")
                out_text = "Sorry, I couldn't generate an image right now. Please try again later."
            # Send both together in a single message if possible
            if out_image_bytes is not None:
                try:
                    await message.reply(content=(out_text or None), file=discord.File(fp=io.BytesIO(out_image_bytes), filename="image.png"))
                except Exception as e:
                    logging.error(f"Failed sending image+text: {e}")
                    # Fallback to image only
                    try:
                        await message.reply(file=discord.File(fp=io.BytesIO(out_image_bytes), filename="image.png"))
                    except Exception:
                        pass
            elif out_text:
                await message.reply(out_text)
            return ("", True)
        elif use_thinking:
            query = f"You are a discord bot named seeyuh.\n Today's date and time is {current_datetime}", f"\n{prompt}"
            response = genai_client.models.generate_content(
                model=model_name,
                contents=query,
                config=config
            )
            logging.info(f"Using thinking model.")

            for part in response.candidates[0].content.parts:
                if part.thought:
                    thought_lines = part.text.split('\n')
                    chunks = []
                    current_chunk = []
                    current_length = 0
                    
                    for line in thought_lines:
                        line_length = len(line) + 2  # +2 for "> " prefix
                        if current_length + line_length > 1900:  # Safe limit for Discord
                            chunks.append(current_chunk)
                            current_chunk = []
                            current_length = 0
                        current_chunk.append(line)
                        current_length += line_length
                    
                    if current_chunk:
                        chunks.append(current_chunk)
                    
                    # Send each chunk as a separate message
                    for i, chunk in enumerate(chunks):
                        formatted_thought = "> 💭 **Reasoning" + (f" (Part {i+1}/{len(chunks)})" if len(chunks) > 1 else "") + ":**\n" + "\n".join(f"> {line}" for line in chunk)
                        await message.reply(formatted_thought[:2000])  # Discord message limit
        else:
            response = await try_model_chain(query, model_name)
        
        if response.text:
            try:
                logging.info(f"AI response: {response.text}")
               
                if '```' in response.text:
                    with tempfile.TemporaryDirectory() as temp_dir:
                        message_components = []  # List of (type, content) tuples
                        text = response.text
                        text_only = ""  # For database storage
                        
                        # First pass: Process all content into components
                        while '```' in text:
                            # Handle text before code block
                            pre_code = text[:text.find('```')].strip()
                            if pre_code:
                                message_components.append(('text', pre_code))
                                text_only += pre_code + "\n"
                            
                            # Process code block
                            lang_start = text.find('```') + 3
                            lang_end = text.find('\n', lang_start)
                            lang = text[lang_start:lang_end].strip().lower()
                            code_start = text.find('\n', lang_end) + 1
                            code_end = text.find('```', code_start)
                            code = text[code_start:code_end]
                            
                            # Get remaining text
                            text = text[text.find('```', code_end) + 3:].strip()
                            
                            # Only create file if language extension exists
                            if lang and code.strip():
                                file_ext = '.' + lang
                                
                                if file_ext.lower() == '.csv':
                                    csv_lines = code.strip().split('\n')
                                    chunk_size = 1000
                                    chunks = [csv_lines[i:i + chunk_size] for i in range(0, len(csv_lines), chunk_size)]
                                    
                                    for i, chunk in enumerate(chunks):
                                        code_path = os.path.join(temp_dir, f'data_part_{i+1}{file_ext}')
                                        with open(code_path, 'w', encoding='utf-8') as f:
                                            f.write('\n'.join(chunk))
                                        message_components.append(('file', discord.File(code_path)))
                                else:
                                    code_path = os.path.join(temp_dir, f'code_{len([c for c in message_components if c[0] == "file"])}{file_ext}')
                                    with open(code_path, 'w', encoding='utf-8') as f:
                                        f.write(code)
                                    message_components.append(('file', discord.File(code_path)))
                            else:
                                # If no language specified, keep code block in markdown
                                message_components.append(('text', f'```\n{code}\n```'))
                                text_only += f'```\n{code}\n```\n'
                        
                        # Add any remaining text
                        if text:
                            message_components.append(('text', text))
                            text_only += text + "\n"
                        
                        # Second pass: Send all components in order
                        for comp_type, content in message_components:
                            if comp_type == 'text':
                                await message.reply(content[:2000])
                            else:  # file
                                await message.reply(files=[content])
                        
                        return (text_only.strip() or "Generated files have been sent.", True)
                    
                # Chunk long responses into <=2000 chars at meaningful boundaries
                text = response.text.strip()
                if len(text) <= 2000:
                    return (text, False)
                chunks = []
                remaining = text
                while len(remaining) > 2000:
                    slice_ = remaining[:2000]
                    # Prefer to break at paragraph / section / newline boundaries
                    cut = max(slice_.rfind('\n\n'), slice_.rfind('\n'), slice_.rfind('  '))
                    if cut < 1000:  # fallback if no good boundary near the end
                        cut = slice_.rfind('. ')
                    if cut < 0:
                        cut = 2000
                    chunks.append(remaining[:cut].strip())
                    remaining = remaining[cut:].lstrip()
                if remaining:
                    chunks.append(remaining)
                # Send chunks sequentially
                for i, chunk in enumerate(chunks):
                    await message.reply(chunk[:2000])
                return ("", True)
                
            except Exception as e:
                logging.error(f"Error in code block handling: {str(e)}")
                return (response.text, False)
    
        return ("I'm not sure how to respond to that.", False)
        
    except Exception as e:
        logging.error(f"Error generating response: {str(e)}")
        return ("Sorry, I could not process that.", False)

# Function to get AI response
async def slash_ai_response(prompt):
    systemInstruction = f"You are a discord bot named seeyuh. Your responses are chill asf and very informal gen-z style. You will do exactly what the user asks you to do."
    query = f"\n{systemInstruction}", f"\n{prompt}"
    try:
        response = await try_model_chain(query, 'flash15creative')
        return response.text or "I'm not sure how to respond to that."
    except Exception as e:
        print(f"Error generating response: {e}")
        return "Sorry, I could not process that."
    
async def slash_ai8b_response(prompt):
    systemInstruction = f"You are a discord bot named seeyuh. Your responses are chill asf and very informal gen-z style. You will do exactly what the user asks you to do."
    query = f"\n{systemInstruction}", f"\n{prompt}"
    model = flash158bc
    try:
        response = model.generate_content(query)
        return response.text or "I'm not sure how to respond to that."
    except Exception as e:
        print(f"Error generating response: {e}")
        return "Sorry, I could not process that."
    
async def code_ai_response(prompt: str, language: str = None, framework: str = None, model: str = "pro15normal") -> Any:
    systemInstruction = f"You are a discord bot named seeyuh. Your responses are chill asf and very informal gen-z style. You will strictly only generate code and answer programming related questions along with code snippets."
    language_info = f" in {language}" if language else ""
    framework_info = f" using {framework}" if framework else ""
    query = f"\n{systemInstruction}", f"User is asking for AI generated code{language_info}{framework_info} for prompt: {prompt}"
    
    try:
        if language and language.upper() == 'PYTHON' or 'python' in prompt.lower():
            response = await try_model_chain(query, model, tools='code_execution')
        else:
            response = await try_model_chain(query, model)
            
        if not response or not any(hasattr(part, 'text') and part.text.strip() 
                                 for part in response.candidates[0].content.parts):
            if model != "flash2":
                logging.info(f"Empty response from {model}, trying flash2...")
                return await code_ai_response(prompt, language, framework, "flash2")
            
        return response
        
    except Exception as e:
        logging.error(f"Error generating response with {model}: {e}")
        if model != "flash2":
            logging.info("Retrying with flash2 model...")
            return await code_ai_response(prompt, language, framework, "flash2")
        return None
    
async def explain_ai_response(prompt):
    systemInstruction = f"You are a discord bot named seeyuh. You will roleplay as professor seeyuh. You will strictly only explain serious concepts or topics in details covering the most important key information. Your message should be well structured to be displayed in discord and should not be too long. Don't be overly concise or too detailed unless specified by user."
    query = f"\n{systemInstruction}", f"\n User is asking a detailed explaination for: {prompt}"
    try:
        response = await try_model_chain(query, 'pro15normal')
        return response.text or "I'm not sure how to respond to that."
    except Exception as e:
        print(f"Error generating response: {e}")
        return "Sorry, I could not process that."
    
async def ask_ai_response(prompt):
    systemInstruction = f"You are a discord bot named seeyuh. Your responses are brief and concise. You will strictly only answer questions in a straightforward and simple manner keeping responses as short as possible."
    query = f"\n{systemInstruction}", f"\n User is asking: {prompt}"
    model = flash158bn
    try:
        response = model.generate_content(query)
        return response.text or "I'm not sure how to respond to that."
    except Exception as e:
        print(f"Error generating response: {e}")
        return "Sorry, I could not process that."
    
async def mystery(prompt):
    systemInstruction = f"You are a discord bot named seeyuh. Your responses are chill asf and very informal gen-z style. You are getting a brainfart."
    query = f"\n{systemInstruction}", f"\n{prompt}"
    model = flash158bc
    try:
        response = model.generate_content(query)
        return response.text or "Nmm sure AI'm nothow spond ato ethat.to respon"
    except Exception as e:
        print(f"Error generating response: {e}")
        return "Sorry."
    
async def translate(prompt):
    systemInstruction = f"You are a discord bot named seeyuh. Your will assume the role of a professional translator. You will strictly only translate text from one language to another."
    query = f"\n{systemInstruction}", f"\n{prompt}"
    try:
        response = await try_model_chain(query, 'pro15normal')
        return response.text or "I'm not sure how to respond to that."
    except Exception as e:
        print(f"Error generating response: {e}")
        return "Sorry, I could not process that."
    
async def prompt_ai_response(prompt, model):
    systemInstruction = f"You are a discord bot named seeyuh. Prompt:"
    query = f"\n{systemInstruction}", f"\n{prompt}"
    try:
        response = model.generate_content(query)
        return response.text or "I'm not sure how to respond to that."
    except Exception as e:
        print(f"Error generating response: {e}")
        return "Sorry, I could not process that."
    
async def get_tts_text(prompt: str, language: str) -> str:
    """Generate AI response for TTS in specified language"""
    system_instruction = (
        f"You are a discord bot named seeyuh. Your responses should be casual and "
        f"gen-z style. Generate a SHORT response (max 100 characters) in {language} "
        f"language that would sound natural when spoken."
    )
    query = f"\n{system_instruction}", f"\n{prompt}"
    
    try:
        response = flash158bn.generate_content(query)
        text = response.text or "I'm not sure how to respond to that."
        return text[:100]  # Limit length for TTS
    except Exception as e:
        logging.error(f"Error generating TTS response: {e}")
        return "Sorry, I could not process that."
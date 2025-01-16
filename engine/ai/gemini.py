import discord, os, logging, sys, random, re, aiohttp, asyncio, tempfile, google.generativeai as genai
from duckduckgo_search import DDGS
from functools import partial
from datetime import datetime
from bs4 import BeautifulSoup
from functools import lru_cache
from typing import List, Any
from dotenv import load_dotenv
from urllib.parse import quote_plus, urlparse

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv('GEMINI_API')

# Configure the Google Generative AI SDK
genai.configure(api_key=GOOGLE_API_KEY)

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

def extract_current_query(prompt: str) -> str:
    """Extract clean search query from bot prompt format."""
    if "Current query: from user" in prompt:
        # Get text after pattern
        query = prompt.split("Current query: from user", 1)[1]
        query = query.split(":")[-1].strip()
        
        # Check for URLs before cleaning
        urls = URL_PATTERN.findall(query)
        
        # Clean and limit query length, preserving URLs
        if not urls:
            query = query.rstrip('.!?')
            query = ' '.join(query.split())
            words = query.split()
            if len(words) > 15:
                query = ' '.join(words[:15])
            return query[:150]
        
        # Return query with URL intact
        return urls[0] if urls else query[:150]
        
    return prompt.strip()[:150]

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
        re.compile(r"(?:show|display|see|look).+?(?:image|picture|photo|pic|thumbnail|screenshot)"),
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
        'high': set(['video', 'movie', 'show', 'trailer', 'episode', 'film', 'stream', 'watch']),
        'medium': set(['tracklist', 'album', 'song', 'release', 'music', 'playlist']),
        'low': set(['listen', 'hear', 'play', 'entertainment'])
    },
    'visual': {
        'high': set(['show me', 'picture of', 'image of', 'photo of', 'look like']),
        'medium': set(['display', 'see', 'visual', 'artwork', 'screenshot']),
        'low': set(['appear', 'looks', 'shown', 'preview'])
    },
    'time': {
        'high': set(['today', 'now', 'current', 'latest', 'live']),
        'medium': set(['recent', 'upcoming', 'this', 'new']),
        'low': set(['soon', 'later', 'next', 'future'])
    },
    'query': {
        'high': set(['what', 'who', 'where', 'when', 'how', 'why', 'which']),
        'medium': set(['tell', 'show', 'give', 'find', 'search']),
        'low': set(['know', 'get', 'see', 'explain'])
    },
    'topic': {
        'high': set(['weather', 'price', 'score', 'news', 'update', 'trending']),
        'medium': set(['president', 'minister', 'leader', 'celebrity', 'influencer']),
        'low': set(['about', 'info', 'details', 'facts'])
    }
}

@lru_cache(maxsize=1000)
def needs_realtime_data(query: str) -> bool:
    query = ' '.join(query.lower().split())
    
    # Quick checks for common real-time queries
    if any(word in query for word in ('happened', 'owner', 'news', 'who', 'what')):
        return True
        
    # Pattern matching with expanded patterns
    for patterns in PATTERNS.values():
        if any(pattern.search(query) for pattern in patterns):
            return True
            
    # Lower threshold for scoring
    score = 0
    words = set(query.split())
    
    for category in KEYWORDS.values():
        if words & category['high']:
            score += 5
        if words & category['medium']:
            score += 3
        if words & category['low']:
            score += 1
            
    if 'today' in query or 'now' in query:
        score += 3
    if any(term in query for term in ('latest', 'current', 'new')):
        score += 2
        
    return score >= 4  # Lowered threshold from 6 to 4

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

@lru_cache(maxsize=50)
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
    
@lru_cache(maxsize=100)
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

async def get_search_results(query: str, num_results: int = 3) -> str:    
    search_type = get_search_type(query)
    try:
        loop = asyncio.get_event_loop()
        with DDGS() as ddgs:
            if search_type == 'text':
                search_func = partial(ddgs.text,
                    query, region='wt-wt', 
                    safesearch='moderate',
                    max_results=num_results,
                    backend='html'
                )
            elif search_type == 'image':
                search_func = partial(ddgs.images,
                    query, region='wt-wt',
                    safesearch='moderate',
                    max_results=num_results
                )
            elif search_type == 'news':
                search_func = partial(ddgs.news,
                    query,
                    region='wt-wt',
                    safesearch='moderate',
                    timelimit='m',  # Last month
                    max_results=num_results
                )
            else: # video
                search_func = partial(ddgs.videos,
                    query, region='wt-wt',
                    safesearch='moderate',
                    max_results=num_results
                )
                
            results = await loop.run_in_executor(None, search_func)
            
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
                    entry += f"NOTE - Instruction to AI: Provide information based on search results appropriately according to the context. Provide urls only if asked by the user in [Title](url) format."
                
                if search_type == 'news':
                    title = r.get('title', 'No title')
                    desc = r.get('body', 'No description')
                    url = r.get('url', '#')
                    date = r.get('date', 'No date')
                    source = r.get('source', 'Unknown source')
                    entry = f"Title: {title}\nDate: {date}\nSource: {source}\n{desc}\nURL: {url}"
                    entry += f"NOTE - Instruction to AI: Provide news information based on search results appropriately according to the context. Provide urls only if appropriate according to context, in [Title](url) format."
                    
                elif search_type == 'image':
                    entry = f"Title: {r.get('title', 'No Title')}\n"
                    entry += f"Source: {r.get('source', 'Unknown')}\n"
                    entry += f"Image URL: {r.get('image', '#')}\n"
                    entry += f"NOTE - Instruction to AI: Provide image link urls directly to user in [title](url) format. Send single best matching image result and more than one or all results only if needed according to the context."
                    
                else: # video
                    entry = f"Title: {r.get('title', 'No Title')}\n"
                    if r.get('duration'):
                        entry += f"Duration: {r.get('duration')}\n"
                    entry += f"Source: {r.get('publisher', 'Unknown')}\n"
                    entry += f"URL: {r.get('content', '#')}\n"
                    entry += f"NOTE - Instruction to AI: Provide video link urls to user in **[Title](url)** format. Send single best matching video result and more than one or all results only if needed according to the context."
                
                formatted_results.append(entry)
                
            return "\n\n".join(formatted_results)
            
    except Exception as e:
        logging.error(f"DuckDuckGo search error: {e}")
        return f"Search failed: {str(e)}"
    
@lru_cache(maxsize=100) 
async def get_ai_response(prompt, message):
    current_query = extract_current_query(prompt)
    logging.info(f"Extracted query: {current_query}")
    
    # Check for URLs first
    urls = URL_PATTERN.findall(current_query)
    if urls:
        content = await scrape_url(urls[0])
        if content:
            domain = urlparse(urls[0]).netloc.replace("www.", "")
            prompt = (
                f"Content from {domain}:\n{content[:20000]}...\n\n"
                f"{prompt}"
            )
    # Only check realtime data if no URLs found
    elif needs_realtime_data(current_query) and not "NOTE - Image automatically generated by stable diffusion for:" in prompt:
        logging.info(f"Real-time data needed (query: {current_query})")
        search_results = await get_search_results(current_query)
        if search_results:
            prompt = (
                f"Based on current data for '{current_query}':\n\n"
                f"{search_results}\n\n"
                f"{prompt}"
            )
        
    if "NOTE - Image automatically generated by stable diffusion for:" in prompt:
        systemInstruction = f"You are a discord bot named seeyuh. arkodeep is your developer, your responses are chill asf and very informal gen-z style. You are an automoderation, entertainment, music and games bot but also designed to help users with their queries. You will generate responses using AI and remember images will be generated using stable diffusion automatically when user prompts it, so you need not worry. You can provide information about the bot, list available commands, respond to user queries and access latest data from internet. You can use the `/help` command to see available commands."
    else:
        systemInstruction = f"You are a discord bot named seeyuh. arkodeep is your developer, your responses are chill asf and very informal gen-z style. You are an automoderation, entertainment, music and games bot but also designed to help users with their queries. You will generate responses using AI and try using same languge as the query. You can provide information about the bot, list available commands, respond to user queries and access latest data from internet. You can use the `/help` command to see available commands."
    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    query = f"\n{systemInstruction} Today's date and time is {current_datetime}", f"\n{prompt}"
    logging.info(f"Query to AI: {query}")
    try:
        response = await try_model_chain(query, 'flash2')
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
                    
                return (response.text, False)
                
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
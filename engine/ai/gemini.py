import os, logging, sys, random, re, aiohttp, asyncio, google.generativeai as genai
from datetime import datetime
from bs4 import BeautifulSoup
from functools import lru_cache
from typing import List
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
        re.compile(r"(?:who|what).+?(?:is|are).+?(?:the|current|new).+?(?:minister|president|ceo|leader|owner)"),
        re.compile(r"who.+?(?:leads|runs|heads|owns).+?(?:now|currently)")
    ],
    'media': [
        re.compile(r"(?:new|latest)?.+?(?:album|song|movie|show|release)"),
        re.compile(r"(?:tracklist|tracks|songs|discography)"),
        re.compile(r"what.+?(?:trending|popular|viral)")
    ],
    'status': [
        re.compile(r"(?:current|latest).+?(?:version|update|status)"),
        re.compile(r"(?:weather|temperature|forecast).+?(?:in|at|for)"),
        re.compile(r"(?:price|cost|worth|value).+?(?:of|for|now)")
    ],
    'events': [
        re.compile(r"what.+?(?:happened|going|occurred|done).+?(?:to|with)"),
        re.compile(r"(?:news|latest|update|story).+?(?:about|on|regarding)")
    ]
}

# Enhanced keywords with weights
KEYWORDS = {
    'media': {
        'high': set(['tracklist', 'album', 'song', 'release']),  # Added media-specific high priority
        'medium': set(['track', 'music', 'artist']),
        'low': set(['listen', 'hear', 'play'])
    },
    'time': {
        'high': set(['today', 'now', 'current', 'latest']),
        'medium': set(['recent', 'upcoming', 'this']),
        'low': set(['soon', 'later', 'next'])
    },
    'query': {
        'high': set(['what', 'who', 'where', 'when', 'how', 'tell', 'about']),
        'medium': set(['tell', 'show', 'give', 'find']),
        'low': set(['know', 'get', 'see'])
    },
    'topic': {
        'high': set(['weather', 'price', 'score', 'news', 'happened', 'owner', 'update']),
        'medium': set(['president', 'minister', 'leader']),
        'low': set(['about', 'info', 'details'])
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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
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
    
async def get_search_results(query: str, num_results: int = 3) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    search_url = f"https://www.google.com/search?q={quote_plus(query)}&safe=active"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(search_url, headers=headers) as resp:
            if resp.status == 200:
                html = await resp.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                results = []
                for g in soup.find_all('div', class_='tF2Cxc')[:num_results]:
                    title = g.find('h3').text if g.find('h3') else "No title"
                    link = g.find('a')['href'] if g.find('a') else "No link"
                    description = g.find('div', class_='VwiC3b').text if g.find('div', class_='VwiC3b') else "No description"
                    
                    if title and description:
                        domain = urlparse(link).netloc.replace("www.", "")
                        results.append(f"{title}\n{description[:300]}...\nSource: {domain}\n")
                
                if results:
                    return "\n".join(results)
                    
    return "No results found."

@lru_cache(maxsize=100) 
async def get_ai_response(prompt):
    current_query = extract_current_query(prompt)
    logging.info(f"Extracted query: {current_query}")
    
    # Check for URLs first
    urls = URL_PATTERN.findall(current_query)
    if urls:
        content = await scrape_url(urls[0])
        if content:
            domain = urlparse(urls[0]).netloc.replace("www.", "")
            prompt = (
                f"Content from {domain}:\n{content[:1000]}...\n\n"
                f"{prompt}"
            )
    # Only check realtime data if no URLs found
    elif needs_realtime_data(current_query):
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
    model = flash2
    try:
        response = model.generate_content(query)
        # Safely log response
        if response.text:
            try:
                logging.info(f"AI response: {response.text}")
            except UnicodeEncodeError:
                # Fallback to ASCII if Unicode fails
                logging.info(f"AI response: {response.text.encode('ascii', 'ignore').decode()}")
                
        return response.text or "I'm not sure how to respond to that."
        
    except Exception as e:
        logging.error(f"Error generating response: {str(e)}")
        return "Sorry, I could not process that."

# Function to get AI response
async def slash_ai_response(prompt):
    systemInstruction = f"You are a discord bot named seeyuh. Your responses are chill asf and very informal gen-z style. You will do exactly what the user asks you to do."
    query = f"\n{systemInstruction}", f"\n{prompt}"
    model = flash15creative
    try:
        response = model.generate_content(query)
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
    
async def code_ai_response(prompt, language=None, framework=None):
    systemInstruction = f"You are a discord bot named seeyuh. Your responses are chill asf and very informal gen-z style. You will strictly only generate code and answer programming related questions along with code snippets."
    language_info = f" in {language}" if language else ""
    framework_info = f" using {framework}" if framework else ""
    query = f"\n{systemInstruction}", f"User is asking for AI generated code{language_info}{framework_info} for prompt: {prompt}"
    model = pro15normal
    try:
        response = model.generate_content((query), tools='code_execution')
        return response.text or "I'm not sure how to respond to that."
    except Exception as e:
        print(f"Error generating response: {e}")
        return "Sorry, I could not process that."
    
async def explain_ai_response(prompt):
    systemInstruction = f"You are a discord bot named seeyuh. You will roleplay as professor seeyuh. You will strictly only explain serious concepts or topics in details covering the most important key information. Your message should be well structured to be displayed in discord and should not be too long. Don't be overly concise or too detailed unless specified by user."
    query = f"\n{systemInstruction}", f"\n User is asking a detailed explaination for: {prompt}"
    model = pro15normal
    try:
        response = model.generate_content(query)
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
    model = pro15normal
    try:
        response = model.generate_content(query)
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
        response = flash158bc.generate_content(query)
        text = response.text or "I'm not sure how to respond to that."
        return text[:100]  # Limit length for TTS
    except Exception as e:
        logging.error(f"Error generating TTS response: {e}")
        return "Sorry, I could not process that."
import os, base64, httpx, discord, asyncio
from dotenv import load_dotenv

def load_env():
    load_dotenv()  # Load environment variables from a .env file
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
    OWNER = os.getenv('OWNER_ID')
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    return DISCORD_TOKEN, OWNER, url, key

def unsplash_env():
    load_dotenv()  # Load environment variables from a .env file
    UNSPLASH_ACCESS_KEY = os.getenv('UNSPLASH_ACCESS_KEY')
    return UNSPLASH_ACCESS_KEY

def imgflip_env():
    load_dotenv()  # Load environment variables from a .env file
    IMGFLIP_USERNAME = os.getenv('IMGFLIP_USERNAME')
    IMGFLIP_PASSWORD = os.getenv('IMGFLIP_PASSWORD')
    return IMGFLIP_USERNAME, IMGFLIP_PASSWORD

def hf_env():
    load_dotenv()  # Load environment variables from a .env file
    HF_API_KEY = os.getenv('HF_API_KEY')
    return HF_API_KEY

async def get_reddit_access_token():
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    
    # Encode client_id and client_secret for Basic Auth
    auth = f"{client_id}:{client_secret}".encode("ascii")
    headers = {
        "Authorization": f"Basic {base64.b64encode(auth).decode('ascii')}",
        "User-Agent": "seeyuh/0.1.0 (by u/drgamerarko)"
    }
    data = {"grant_type": "client_credentials"}

    async with httpx.AsyncClient() as client:
        response = await client.post("https://www.reddit.com/api/v1/access_token", headers=headers, data=data)
        response.raise_for_status()
        return response.json().get("access_token")

def giphy_env():
    load_dotenv()  # Load environment variables from a .env file
    GIPHY_API_KEY = os.getenv('GIPHY_API_KEY')
    return GIPHY_API_KEY

def pexels_env():
    load_dotenv()  # Load environment variables from a .env file
    PEXELS_API_KEY = os.getenv('PEXELS_API_KEY')
    return PEXELS_API_KEY

def qwen_env():
    load_dotenv()  # Load environment variables from a .env file
    RUNPOD_ENDPOINT_ID = os.getenv('RUNPOD_ENDPOINT_ID')
    RUNPOD_API_KEY = os.getenv('RUNPOD_API_KEY')
    return RUNPOD_ENDPOINT_ID, RUNPOD_API_KEY

def infinitetalk_env():
    load_dotenv()  # Load environment variables from a .env file
    INFINITETALK_ENDPOINT_ID = os.getenv('INFINITETALK_ENDPOINT_ID')
    INFINITETALK_API_KEY = os.getenv('INFINITETALK_API_KEY', os.getenv('RUNPOD_API_KEY'))  # Fallback to RUNPOD_API_KEY
    return INFINITETALK_ENDPOINT_ID, INFINITETALK_API_KEY

def intents():
    # Define the bot with intents
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True                # Receive guild-related events
    intents.members = True                # Receive member-related events
    intents.bans = True                   # Receive ban-related events
    intents.emojis = True                 # Receive emoji-related events
    intents.integrations = True           # Receive integration-related events
    intents.webhooks = True               # Receive webhook-related events
    intents.voice_states = True           # Receive voice state updates
    intents.presences = True              # Receive presence updates (online, offline, etc.)
    intents.messages = True                # Receive message-related events
    intents.guild_messages = True         # Receive guild message events
    intents.dm_messages = True             # Receive direct message events
    intents.reactions = True               # Receive reaction events
    intents.guild_reactions = True        # Receive guild reaction events
    return intents

async def update_presence(bot):
    custom_emoji = discord.PartialEmoji(name="seeyuh", id=1302628356147122207)  # Define the PartialEmoji with the emoji ID
    while True:
        unique_users = len(bot.users)  # Get the current number of unique users and guilds
        guild_count = len(bot.guilds)
        status = discord.CustomActivity(name="/help")  # Define the CustomActivity with the updated user count
        # Set the bot's activity with updated user count
        activity = discord.Activity(
            type=discord.ActivityType.listening,
            name=f"{unique_users} unique users across {guild_count} servers! 😉"  # Updated text
        )
        await bot.change_presence(
            status=discord.Status.idle,
            activity=activity
        )

        # Wait a few minutes before updating again (e.g., 5 minutes)
        await asyncio.sleep(300)
  
image_keywords = ["draw an image of", "generate an image of", "generate a picture of", "create an image of",
    "can you create an image of", "I'd like a picture of", "make a picture of",
    "give me a picture of", "I need an image of", "I want an image of",
    "generate artwork of", "design a scene with", "paint a picture of", "create artwork of", "show a depiction of", "produce a visual of", 
    "render an image of", "illustrate a scene with", "I'd love a drawing of", "craft a picture showing", "make a portrait of", 
    "give me an artwork featuring", "let me see a rendering of", "compose a picture with", "can you make a drawing of", "give a visual representation of", "depict a scene with", 
    "showcase an artwork of", "conjure an image of", "create something with", "develop an illustration showing","make me artwork of", "I'd like a painting of", 
    "draw something showing", "produce a picture of", "generate a portrait of", "create a rendering of", "can you visualize", "generate a scene with",
    "generate a scene of", "create a detailed picture of", "produce a visual representation of", "render a realistic image of", "design a concept art for", "compose an artistic view of", 
    "make a painting that shows", "create a landscape with", "sketch out a concept of", "illustrate a setting featuring", "show me a rendered version of", "I'd love to see an artwork of", 
    "paint a scene depicting", "draw a scenario with", "create an imaginative image showing", "visualize a scene that has", "produce a portrait illustrating", "conjure up a picture of",
    "design an artwork showing", "can you render an illustration of", "I need a visual that captures", "illustrate a scenario with", "show a concept art of", "draw a scene based on",
    "develop a creative depiction of", "create an image that features", "craft a detailed artwork of", "draw a vivid representation of", "sketch an idea showing", "illustrate a scene filled with",
    "make a digital rendering of", "give me a visual impression of", "paint a striking image of", "I'd like to see a concept of", "make an artistic interpretation of", "compose a scenic view of", 
    "craft an imaginative artwork of", "draw image", "show me image", "generate image", "generate picture", "create image",
    "I want to see an image of", "can you create image", "I'd like picture", "make picture",
    "generate artwork", "design scene with", "paint picture", "create artwork", "show depiction", "produce visual", 
    "render image", "illustrate scene", "I'd love drawing", "craft picture showing", "make portrait", 
    "give me artwork", "let me see rendering", "compose picture", "can you make drawing", "give visual representation", "depict scene", 
    "develop illustration showing","make me artwork", "I'd like painting", 
    "draw something", "produce picture", "generate portrait", "create rendering", "generate scene",
    "create detailed picture", "produce visual representation", "render realistic image", "design concept art", "compose artistic view", 
    "make painting", "create landscape", "sketch out concept", "illustrate ", "show me rendered version", "I'd love to see artwork", 
    "paint scene", "draw scenario", "create imaginative image", "visualize scene", "produce portrait", "conjure up picture",
    "design artwork", "can you render illustration", "I need visual", "illustrate scenario", "show concept art", "draw scene",
    "develop creative depiction", "create image that features", "craft detailed artwork", "draw vivid representation", "sketch idea", "illustrate scene",
    "make digital rendering", "give me visual impression", "paint striking image", "I'd like to see concept", "make artistic interpretation", "compose scenic view", 
    "craft imaginative artwork", "show me a picture", "show me an image", "find image", "find picture", "search image", "search picture",
    "get image", "get picture", "look up image", "look up picture", "fetch image", "fetch picture", "display image", "display picture" ] 
image_end_keywords = [
    "generate an image", "create an illustration", "draw a picture", "make an artwork", 
    "produce a rendering", "visualize this", "render an image",
    "depict this", "make a picture", "show a drawing", "design an artwork", "make an image",
    "illustrate this scene", "paint this scenario", "show an art piece", "make picture", "make pic",
    "create a visual", "give me a sketch", "give an illustration", "make image", "generate a picture", "generate pic",
    "produce a concept", "draw this scene", "make a digital art", "generate picture", "draw an image", "draw image", "draw picture", "draw pic",
    "compose a visual", "craft a picture", "display an artwork", "generate image",
]      

# Image editing keywords (using "in" for contains matching)
image_edit_keywords = [
    'edit', 'plsedit', 'pls edit', 'please edit', 'modify', 'change', 'alter', 'transform', 'adjust',
    'replace', 'swap', 'switch', 'substitute', 'exchange',
    'remove', 'delete', 'erase', 'clear', 'take out',
    'add', 'insert', 'put', 'place', 'include',
    'background', 'bg', 'backdrop',
    'inpaint', 'outpaint', 'paint', 'draw on', 'sketch on',
    'recolor', 'recolour', 'colorize', 'tint',
    'enhance', 'improve', 'fix', 'correct', 'touch up', 'touchup',
    'resize', 'crop', 'rotate', 'flip',
    'blur', 'sharpen', 'brighten', 'darken',
    'filter', 'effect', 'style'
]

def is_image_request(message_content):
    message_content_lower = message_content.lower()
    # Check for image editing keywords first (using "in" for contains)
    if any(keyword in message_content_lower for keyword in image_edit_keywords):
        return True
    return any(keyword in message_content_lower for keyword in image_keywords) or any(message_content_lower.endswith(keyword) for keyword in image_end_keywords)

def extract_image_prompt(message_content):
    message_content = message_content.lower().replace('seeyuh', '').strip()
    
    for keyword in image_keywords:
        if keyword in message_content:
            # Get text after keyword if keyword is at start
            if message_content.startswith(keyword):
                prompt = message_content[len(keyword):].strip()
            # Get text before keyword if keyword is at end
            elif message_content.endswith(keyword):
                prompt = message_content[:message_content.rfind(keyword)].strip()
            # Get text before or after keyword if it's in middle 
            else:
                parts = message_content.split(keyword, 1)
                prompt = parts[0].strip() if parts[0].strip() else parts[1].strip()
                
            return prompt
    return message_content  # Use the whole message as the prompt if no keyword is found

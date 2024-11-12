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
            name=f"{unique_users} users across {guild_count} servers! 😉"  # Updated text
        )
        await bot.change_presence(
            status=discord.Status.idle,
            activity=activity
        )

        # Wait a few minutes before updating again (e.g., 5 minutes)
        await asyncio.sleep(300)
  
image_keywords = ["draw an image of", "show me an image of", "generate an image of", "generate a picture of", "create an image of", "send me a picture of",
    "I want to see an image of", "can you create an image of", "I'd like a picture of", "make a picture of", "show an image of",
    "give me a picture of", "I need an image of", "I want an image of", "I'd like an image of", "I want to see a picture of",
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
    "craft an imaginative artwork of" ] 
image_end_keywords = [
    "generate an image", "create an illustration", "draw a picture", "make an artwork", 
    "produce a rendering", "show a visual", "visualize this", "render an image", 
    "depict this", "make a picture", "show a drawing", "design an artwork", 
    "illustrate this scene", "paint this scenario", "show an art piece", 
    "create a visual", "give me a sketch", "give an illustration", 
    "produce a concept", "draw this scene", "make a digital art", "generate picture",
    "compose a visual", "craft a picture", "display an artwork", "generate image"
]      
def is_image_request(message_content):
    message_content_lower = message_content.lower()
    return any(keyword in message_content_lower for keyword in image_keywords) or any(message_content_lower.endswith(keyword) for keyword in image_end_keywords)

def extract_image_prompt(message_content):
    for keyword in image_keywords:
        if keyword in message_content.lower():
            prompt = message_content.lower().split(keyword, 1)[1].strip()
        elif message_content.lower().endswith(keyword):
            prompt = message_content.lower().rsplit(keyword, 1)[0].strip()
            return prompt
    return message_content  # Use the whole message as the prompt if no keyword is found
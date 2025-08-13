from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path
import logging, os, httpx, asyncio, json
from concurrent.futures import ThreadPoolExecutor
from more_itertools import chunked
from filelock import FileLock
executor = ThreadPoolExecutor()

# Load environment variables
load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# Configure logging to write to a file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

BACKUP_DIR = Path("backups")
MESSAGES_FILE = BACKUP_DIR / "messages.json"
LOCK_FILE = BACKUP_DIR / "messages.json.lock"
MAX_MESSAGES = 1000  # Limit number of stored messages
SETTINGS_FILE = BACKUP_DIR / "guild_settings.json"
SETTINGS_LOCK = BACKUP_DIR / "guild_settings.json.lock"

def save_to_json(data):
    # Ensure backup directory exists
    BACKUP_DIR.mkdir(exist_ok=True)
    
    # Create lock file if it doesn't exist
    if not LOCK_FILE.exists():
        LOCK_FILE.touch()
        
    with FileLock(LOCK_FILE):
        try:
            # Load existing messages or create new list
            messages = []
            if MESSAGES_FILE.exists():
                try:
                    with open(MESSAGES_FILE, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if content.strip():  # Check if file is not empty
                            messages = json.loads(content)
                except json.JSONDecodeError:
                    logging.warning("Corrupted JSON file, starting fresh")
                    messages = []
            
            # Add new message
            messages.append(data)
            
            # Keep only latest messages
            if len(messages) > MAX_MESSAGES:
                messages = messages[-MAX_MESSAGES:]
            
            # Write updated messages
            with open(MESSAGES_FILE, 'w', encoding='utf-8') as f:
                json.dump(messages, f, indent=2, ensure_ascii=False)
                
            logging.info(f"Successfully saved message to JSON, total messages: {len(messages)}")
            
        except Exception as e:
            logging.error(f"Error in save_to_json: {str(e)}")
            raise
        
def fetch_existing_guild_invites():
    response = supabase.table('guild_invites').select('guild_id').execute()
    if response.data:
        return {invite['guild_id'] for invite in response.data}
    return set()

def insert_guild_invites(invites):
    supabase.table('guild_invites').insert(invites).execute()

async def generate_and_cache_invites(bot):
    loop = asyncio.get_event_loop()
    
    # Fetch existing guild invites in a separate thread
    existing_guild_invites = await loop.run_in_executor(executor, fetch_existing_guild_invites)
    
    new_invites = []
    
    for guild in bot.guilds:
        guild_id = str(guild.id)
        
        # Skip guilds that already have invites
        if guild_id in existing_guild_invites:
            continue
        
        invite_created = False
        
        # Iterate over the guild's text channels to find one where the bot has permission
        for channel in guild.text_channels:
            permissions = channel.permissions_for(guild.me)
            if permissions.create_instant_invite:
                try:
                    # Create an invite link
                    invite = await channel.create_invite(max_age=0, max_uses=0, unique=False)
                    invite_url = invite.url
                    
                    # Collect the invite link for batch insertion
                    new_invites.append({'guild_id': guild_id, 'invite_url': invite_url})
                    print(f"Created invite for guild '{guild.name}': {invite_url}")
                    invite_created = True
                    break  # Exit after creating an invite
                except Exception as e:
                    print(f"Failed to create invite in channel '{channel.name}' of guild '{guild.name}': {e}")
        
        if not invite_created:
            print(f"No permission to create invites in any channel of guild '{guild.name}'.")
    
    # Batch insert new invites in a separate thread
    if new_invites:
        await loop.run_in_executor(executor, insert_guild_invites, new_invites)
        
def fetch_existing_guilds():
    response = supabase.table('guilds').select('guild_id').execute()
    if response.data:
        return {guild['guild_id'] for guild in response.data}
    return set()

def fetch_existing_users():
    response = supabase.table('users').select('user_id').execute()
    if response.data:
        return {user['user_id'] for user in response.data}
    return set()

def upsert_guilds(guilds):
    supabase.table('guilds').upsert(guilds, on_conflict=['guild_id']).execute()

def upsert_users(users):
    supabase.table('users').upsert(users, on_conflict=['user_id']).execute()

async def sync_guilds_and_users(bot):
    loop = asyncio.get_event_loop()
    
    # Fetch existing guilds and users in separate threads
    existing_guilds = await loop.run_in_executor(executor, fetch_existing_guilds)
    existing_users = await loop.run_in_executor(executor, fetch_existing_users)
    
    new_guilds = []
    new_users = []
    
    for guild in bot.guilds:
        guild_id = str(guild.id)
        
        # Check if the guild is already in the database
        if guild_id not in existing_guilds:
            new_guilds.append({
                'guild_id': guild_id,
                'guild_name': guild.name,
                'owner_id': str(guild.owner_id),
                'member_count': guild.member_count
            })
        else:
            # Update existing guild details
            new_guilds.append({
                'guild_id': guild_id,
                'guild_name': guild.name,
                'owner_id': str(guild.owner_id),
                'member_count': guild.member_count
            })
        
        for member in guild.members:
            user_id = str(member.id)
            
            # Check if the user is already in the database
            if user_id not in existing_users:
                new_users.append({
                    'user_id': user_id,
                    'username': member.name,
                    'discriminator': member.discriminator,
                    'guild_id': guild_id,
                    'avatar_url': str(member.display_avatar.url) if member.display_avatar else ''
                })
            else:
                # Update existing user details
                new_users.append({
                    'user_id': user_id,
                    'username': member.name,
                    'discriminator': member.discriminator,
                    'guild_id': guild_id,
                    'avatar_url': str(member.display_avatar.url) if member.display_avatar else ''
                })
    
    # Ensure unique entries in new_users
    unique_new_users = {user['user_id']: user for user in new_users}.values()
    
    # Batch upsert new guilds and users in separate threads
    if new_guilds:
        await loop.run_in_executor(executor, upsert_guilds, new_guilds)
    if unique_new_users:
        for chunk in chunked(unique_new_users, 500):
            await loop.run_in_executor(executor, upsert_users, list(chunk))
                
def check_and_update_guild_entry(supabase, guild_id, guild_name):
    try:
        # Check if the guild entry exists
        guild_entry = supabase.table('guilds').select('*').eq('guild_id', guild_id).execute()

        # Insert or update the guild entry based on existence
        if not guild_entry.data:  # If no existing entry, insert
            try:
                supabase.table('guilds').insert({
                    'guild_id': guild_id,
                    'guild_name': guild_name
                }).execute()
            except Exception as e:
                logging.error(f"Error inserting guild: {e}")
        else:  # If entry exists, update
            try:
                supabase.table('guilds').update({
                    'guild_name': guild_name
                }).eq('guild_id', guild_id).execute()
            except Exception as e:
                logging.error(f"Error updating guild: {e}")
    except httpx.ConnectError as e:
        logging.error(f"Connection error while accessing Supabase: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return False
    return True

async def retry_check_and_update_guild_entry(supabase, guild_id, guild_name, retries=5, delay=5):
    for attempt in range(retries):
        if check_and_update_guild_entry(supabase, guild_id, guild_name):
            logging.info(f"Successfully updated guild entry on attempt {attempt + 1}")
            return True
        else:
            logging.warning(f"Retrying guild entry update (attempt {attempt + 1}/{retries})")
            await asyncio.sleep(delay)
    logging.error(f"Failed to update guild entry after {retries} attempts")
    return False

def init_json_file():
    """Initialize JSON file with empty array if not exists or empty"""
    BACKUP_DIR.mkdir(exist_ok=True)
    if not MESSAGES_FILE.exists() or MESSAGES_FILE.stat().st_size == 0:
        with open(MESSAGES_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f)
        logging.info("Initialized empty JSON file")

# Define the function outside of on_message
def fetch_recent_message(supabase, guild_id, user_id):
    recent_threshold = datetime.now(dt_timezone.utc) - timedelta(seconds=300)

    # Try JSON cache first
    try:
        init_json_file()  # Ensure valid JSON exists
        with open(MESSAGES_FILE, 'r', encoding='utf-8') as f:
            messages = json.load(f)
            
        # Search recent messages in reverse (newest first)
        for message in reversed(messages):
            if (message['guild_id'] == guild_id and 
                message['user_id'] == user_id):
                msg_time = datetime.strptime(message['created_at'], '%Y-%m-%dT%H:%M:%S.%f%z')
                if msg_time > recent_threshold:
                    logging.info("Found recent message in JSON cache")
                    return message
    except Exception as e:
        logging.error(f"Error reading JSON cache: {e}")
        # Continue to Supabase fallback

    try:
        # Fetch the last message from the user within the recent threshold
        user_message_response = supabase.table('messages') \
            .select('*') \
            .eq('guild_id', guild_id) \
            .eq('user_id', user_id) \
            .order('created_at', desc=True) \
            .limit(1) \
            .execute()

        if user_message_response.data:
            user_message = user_message_response.data[0]
            user_timestamp = datetime.strptime(user_message['created_at'], '%Y-%m-%dT%H:%M:%S.%f%z')
            
            if user_timestamp > recent_threshold:
                return user_message  # Return user's last message if it's recent

        # If the user's last message is too old or nonexistent, get the last guild message
        guild_message_response = supabase.table('messages') \
            .select('*') \
            .eq('guild_id', guild_id) \
            .order('created_at', desc=True) \
            .limit(1) \
            .execute()

        if guild_message_response.data:
            return guild_message_response.data[0]  # Return the last guild message

    except httpx.ConnectError as e:
        logging.error(f"Connection error while fetching messages: {e}")
        return None  # Return None if there is a connection error

    return None  # No recent messages found

async def save_message_to_db(guild_id, author, user_message, bot_response, retries=5, delay=5):
    created_at = datetime.now(dt_timezone.utc).isoformat()
    
    # Prepare message data
    message_data = {
        'content': user_message,
        'user_id': str(author.id),
        'username': author.name,
        'guild_id': guild_id,
        'response': bot_response,
        'created_at': created_at
    }
    
    # Save to JSON locally
    try:
        save_to_json(message_data)
        logging.info("Saved message to local JSON")
    except Exception as e:
        logging.error(f"Error saving to JSON: {e}")
    
    for attempt in range(retries):
        try:
            # Upsert user entry
            user_entry_response = supabase.table('users').select('*').eq('user_id', str(author.id)).execute()

            if not user_entry_response.data:
                try:
                    supabase.table('users').insert({
                        'user_id': str(author.id),
                        'username': author.name,
                        'discriminator': author.discriminator,
                        'guild_id': guild_id
                    }).execute()
                except Exception as e:
                    logging.error(f"Error inserting user: {e}")

            created_at = datetime.now(dt_timezone.utc).isoformat()  # Get the current timestamp in UTC and convert to ISO format
            # Insert new message without specifying the id
            try:
                supabase.table('messages').insert({
                    'content': user_message,
                    'user_id': str(author.id),
                    'guild_id': guild_id,
                    'response': bot_response,
                    'created_at': created_at  # Add timestamp in ISO format
                }).execute()
            except Exception as e:
                logging.error(f"Error inserting message: {e}")

            logging.info(f"Successfully saved message to DB on attempt {attempt + 1}")
            return True  # Exit the loop if successful

        except httpx.ConnectError as e:
            logging.error(f"Connection error while saving message to DB: {e}")
            logging.warning(f"Retrying save message to DB (attempt {attempt + 1}/{retries})")
            await asyncio.sleep(delay)  # Wait before retrying

    logging.error(f"Failed to save message to DB after {retries} attempts")
    return False

# ---------------- Guild Welcome Settings (local JSON) ----------------
def _read_settings_store() -> dict:
    BACKUP_DIR.mkdir(exist_ok=True)
    if not SETTINGS_FILE.exists():
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f)
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            return json.loads(content) if content else {}
    except Exception:
        return {}

def _write_settings_store(store: dict) -> None:
    BACKUP_DIR.mkdir(exist_ok=True)
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(store, f, indent=2, ensure_ascii=False)

def get_welcome_settings(guild_id: str) -> dict:
    """Return welcome settings for a guild.
    Attempts Supabase first; falls back to local JSON store.
    Schema: { enabled: bool, channel_id: str|None, message: str|None }
    Defaults: enabled=True, channel_id=None, message=None
    """
    # Try Supabase
    try:
        resp = supabase.table('welcome_settings').select('*').eq('guild_id', guild_id).limit(1).execute()
        if resp.data:
            row = resp.data[0]
            return {
                'enabled': bool(row.get('enabled', True)),
                'channel_id': row.get('channel_id'),
                'message': row.get('message'),
            }
    except Exception:
        pass

    # Fallback: local JSON
    if not SETTINGS_LOCK.exists():
        SETTINGS_LOCK.touch()
    with FileLock(SETTINGS_LOCK):
        store = _read_settings_store()
        settings = store.get(guild_id) or {}
        return {
            'enabled': bool(settings.get('enabled', True)),
            'channel_id': settings.get('channel_id'),
            'message': settings.get('message'),
        }

def set_welcome_settings(guild_id: str, *, enabled: bool | None = None, channel_id: str | None = None, message: str | None = None) -> dict:
    """Update welcome settings for a guild. Returns updated settings.
    Attempts to upsert in Supabase first; falls back to local JSON if that fails.
    """
    # Try Supabase upsert
    try:
        # Read existing to merge
        current = get_welcome_settings(guild_id)
        if enabled is not None:
            current['enabled'] = bool(enabled)
        if channel_id is not None:
            current['channel_id'] = str(channel_id)
        if message is not None:
            current['message'] = message[:1000]
        supabase.table('welcome_settings').upsert({
            'guild_id': guild_id,
            'enabled': current.get('enabled', True),
            'channel_id': current.get('channel_id'),
            'message': current.get('message'),
        }, on_conflict=['guild_id']).execute()
        return current
    except Exception:
        pass

    # Fallback to local JSON
    if not SETTINGS_LOCK.exists():
        SETTINGS_LOCK.touch()
    with FileLock(SETTINGS_LOCK):
        store = _read_settings_store()
        current = store.get(guild_id) or {}
        if enabled is not None:
            current['enabled'] = bool(enabled)
        if channel_id is not None:
            current['channel_id'] = str(channel_id)
        if message is not None:
            current['message'] = message[:1000]
        store[guild_id] = current
        _write_settings_store(store)
        return get_welcome_settings(guild_id)
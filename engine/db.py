from datetime import datetime, timezone as dt_timezone
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone as dt_timezone
import logging, os, httpx, asyncio
from concurrent.futures import ThreadPoolExecutor
from more_itertools import chunked
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

# Define the function outside of on_message
def fetch_recent_message(supabase, guild_id, user_id):
    recent_threshold = datetime.now(dt_timezone.utc) - timedelta(seconds=300)

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
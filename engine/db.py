from datetime import datetime, timezone as dt_timezone
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone as dt_timezone
import logging, os, httpx, asyncio

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

async def generate_and_cache_invites(bot):
    for guild in bot.guilds:
        guild_id = str(guild.id)
        
        # Check if an invite already exists for this guild
        response = supabase.table('guild_invites').select('invite_url').eq('guild_id', guild_id).execute()
        if response.data:
            continue  # Invite already exists, skip to the next guild
        
        # Create an invite link
        try:
            invite = await guild.text_channels[0].create_invite(max_age=0, max_uses=0, unique=False)
            invite_url = invite.url
            
            # Cache the invite link in the database
            supabase.table('guild_invites').insert({'guild_id': guild_id, 'invite_url': invite_url}).execute()
            print(f"Created invite for guild {guild.name}: {invite_url}")
        except Exception as e:
            print(f"Failed to create invite for guild {guild.name}: {e}")
            
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
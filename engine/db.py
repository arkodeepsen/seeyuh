from datetime import datetime, timezone as dt_timezone
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone as dt_timezone
import logging, os, httpx

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
    ]
)

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
        print(f"Connection error while fetching messages: {e}")
        return None  # Return None if there is a connection error

    return None  # No recent messages found

def save_message_to_db(guild_id, author, user_message, bot_response):
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

    except httpx.ConnectError as e:
        logging.error(f"Connection error while saving message to DB: {e}")
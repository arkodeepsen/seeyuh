import google.generativeai as genai
import os, discord, logging, aiohttp
from engine.db import fetch_recent_message, supabase
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

GOOGLE_API_KEY = os.getenv('GEMINI_PRO_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)

# Function to upload and retrieve the file
def prep_file(file_path, display_name):
    sample_file = genai.upload_file(path=file_path, display_name=display_name)
    logging.info(f"Uploaded file '{sample_file.display_name}' as: {sample_file.uri}")
    return sample_file  # Return the sample file object

# Extract content from the file using the URI and a prompt
def extract_content_from_file(sample_file, prompt):
    try:
        model = genai.GenerativeModel("models/gemini-1.5-flash")
        # Use the sample file object directly
        response = model.generate_content([sample_file, prompt])
        return response.text
    except Exception as e:
        logging.error(f"Error extracting content: {e}")
        return None

# Download and process an attachment from a URL
async def handle_attachment(bot, message, attachment):
    try:
        # Determine the content type of the file
        content_type = attachment.content_type
        logging.info(f"Content Type: {content_type}")

        # Define supported content types
        supported_types = ['image/', 'application/', 'text/']
        is_supported = any(content_type.startswith(supported) for supported in supported_types)

        if not is_supported:
            await message.reply("Unsupported file type. Please upload an image, PDF, or text file.")
            return

        # Set the local file path
        _, file_extension = os.path.splitext(attachment.filename)
        file_path = f"downloaded_file{file_extension}"

        # Download the file
        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.url) as resp:
                if resp.status == 200:
                    with open(file_path, "wb") as f:
                        f.write(await resp.read())
                    logging.info("Downloaded file successfully.")
                else:
                    await message.reply("Failed to download the file.")
                    return

        # Upload the downloaded file and prepare it for analysis
        sample_file = prep_file(file_path, attachment.filename)
        # Retrieve the last relevant message, prioritizing the user’s recent message
        last_message = fetch_recent_message(supabase, guild_id=str(message.guild.id), user_id=str(message.author.id))

        if last_message:
            context_message = f"Last relevant message in the guild: {last_message['content']}\n"
            context_message += f"Bot response to that message: {last_message['response']}\n"
        else:
            context_message = ""
        # Determine the prompt
        prompt = message.content.strip().replace(f"<@{bot.user.id}>", "").replace("seeyuh", "").strip()
        if not prompt:
            if content_type.startswith('image/'):
                prompt = "Explain the content of the image."
            elif content_type.startswith ('application/'):
                prompt = "Provide a summary of the document."
            elif content_type.startswith('text/'):
                prompt = "Provide an analysis of the text file."
            else:
                prompt = "Analyze the content of the file."
        prompt = f"You are a chill discord bot with multimodal AI features. Your responses are genz style.\n{context_message} \nCurrent query: {prompt}"
        extracted_content = extract_content_from_file(sample_file, prompt)

        # Reply with extracted content
        if extracted_content:
                        # Split the content into chunks if it exceeds the message size limit
                        max_message_size = 2000
                        content_chunks = [extracted_content[i:i + max_message_size] for i in range(0, len(extracted_content), max_message_size)]

                        for chunk in content_chunks:
                            await message.reply(chunk)
                        return extracted_content    
        else:
            await message.reply("Failed to extract content from the file.")
            return "Failed to extract content from the file."

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        await message.reply("An error occurred while processing the file.")
    finally:
        # Clean up by deleting the downloaded file if it exists
        if os.path.exists(file_path):
            os.remove(file_path)
            logging.error("Deleted temporary file.")

async def handle_interaction(
    interaction: discord.Interaction,
    file: discord.Attachment,
    prompt: Optional[str] = None
):
    try:
        # Determine the content type of the file
        content_type = file.content_type
        logging.info(f"Content Type: {content_type}")

        # Define supported content types
        supported_types = ['image/', 'application/', 'text/']
        is_supported = any(content_type.startswith(supported) for supported in supported_types)

        if not is_supported:
            await interaction.followup.send("Unsupported file type. Please upload an image, PDF, or text file.")
            return

        # Set the local file path
        _, file_extension = os.path.splitext(file.filename)
        file_path = f"downloaded_file{file_extension}"

        # Download the file
        async with aiohttp.ClientSession() as session:
            async with session.get(file.url) as resp:
                if resp.status == 200:
                    with open(file_path, "wb") as f:
                        f.write(await resp.read())
                    logging.info("Downloaded file successfully.")
                else:
                    await interaction.followup.send("Failed to download the file.")
                    return

        # Upload the downloaded file and prepare it for analysis
        sample_file = prep_file(file_path, file.filename)

        # Determine the prompt
        if not prompt:
            if content_type.startswith('image/'):
                prompt = "Explain the content of the image."
            elif content_type.startswith('application/'):
                prompt = "Provide a summary of the document."
            elif content_type.startswith('text/'):
                prompt = "Provide an analysis of the text file."
            else:
                prompt = "Analyze the content of the file."
        prompt = f"Generate a response to the following prompt under 4096 characters: {prompt}"
        extracted_content = extract_content_from_file(sample_file, prompt)

        # Reply with extracted content
        if extracted_content:
            # Split the content into chunks if it exceeds the embed size limit
            max_embed_size = 6000
            content_chunks = [extracted_content[i:i + max_embed_size] for i in range(0, len(extracted_content), max_embed_size)]

            for chunk in content_chunks:
                embed = discord.Embed(
                    title="Image Analysis" if content_type.startswith('image/') else "File Analysis",
                    description=chunk,
                    color=0x00ff00
                )
                if content_type.startswith('image/'):
                    embed.set_thumbnail(url=file.url)
                    icon_url = (
                        str(interaction.client.user.avatar.url)
                        if interaction.client.user.avatar
                        else str(interaction.client.user.default_avatar.url)
                    )
                    embed.set_footer(
                        text=interaction.client.user.name,
                        icon_url=icon_url
                    )
                await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("Failed to extract content from the file.")

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        await interaction.followup.send("An error occurred while processing the file.")
    finally:
        # Clean up by deleting the downloaded file if it exists
        if os.path.exists(file_path):
            os.remove(file_path)
            logging.info("Deleted temporary file.")
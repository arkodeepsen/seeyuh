import google.generativeai as genai
import os
from dotenv import load_dotenv
import asyncio  # For asynchronous operations
import aiohttp
import tempfile
import logging
import mimetypes

load_dotenv()
GOOGLE_API_KEY = os.getenv('GEMINI_PRO_API_KEY')  # Or your API key variable name
genai.configure(api_key=GOOGLE_API_KEY)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Asynchronous function to upload and process the file
async def process_file_with_gemini(file_path, mime_type, prompt="Explain the contents of this file."):
    try:
        # Upload in a separate thread to avoid blocking
        sample_file = await asyncio.to_thread(genai.upload_file, path=file_path, display_name="Attachment", mime_type=mime_type)
        logging.info(f"Uploaded file '{sample_file.display_name}' as: {sample_file.uri}")

        model = genai.GenerativeModel("models/gemini-1.5-flash")
        # Generate content in a separate thread
        response = await asyncio.to_thread(model.generate_content, [sample_file.uri, prompt])
        return response.text
    except Exception as e:
        logging.error(f"Error processing file: {e}")
        return None

# Example usage (in an async function within your Discord bot):
async def handle_attachment(message, attachment):  # 'message' is a Discord message object
    try:
        # Download the attachment to a temporary file
        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.url) as resp:
                if resp.status == 200:
                    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                        temp_file.write(await resp.read())
                        temp_file_path = temp_file.name
                else:
                    await message.channel.send("Failed to download the attachment.")
                    return

        # Determine the prompt
        prompt = message.content.strip().replace(f"<@{message.guild.me.id}>", "").replace("seeyuh", "").strip() or "Explain the contents of this file."

        # Determine the MIME type
        mime_type, _ = mimetypes.guess_type(temp_file_path)
        if mime_type is None:
            mime_type = "application/octet-stream"  # Fallback MIME type

        # Process the file with Gemini
        extracted_content = await process_file_with_gemini(temp_file_path, mime_type, prompt)

        if extracted_content:
            await message.channel.send(f"seeyuh's response:\n```\n{extracted_content}\n```")
        else:
            await message.channel.send("Failed to process the file.")

    except Exception as e:
        await message.channel.send(f"An error occurred: {e}")
        logging.error(f"Error handling attachment: {e}")
    finally:
        # Clean up temporary files
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
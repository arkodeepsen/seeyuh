import google.generativeai as genai
import os, discord
from dotenv import load_dotenv
import aiohttp

load_dotenv()
GOOGLE_API_KEY = os.getenv('GEMINI_PRO_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)

# Function to upload and retrieve the image file
def prep_image(image_path):
    sample_file = genai.upload_file(path=image_path, display_name="Image")
    print(f"Uploaded file '{sample_file.display_name}' as: {sample_file.uri}")
    return sample_file  # Return the entire sample file object

# Extract text from the image using the URI and a prompt
def extract_text_from_image(sample_file, prompt):
    try:
        model = genai.GenerativeModel("models/gemini-1.5-flash")
        # Use the sample file object directly
        response = model.generate_content([sample_file, prompt])
        return response.text
    except Exception as e:
        print(f"Error extracting text: {e}")
        return None

# Download and process an image from a URL
async def handle_attachment(bot, message, attachment):
    try:
        # Download the image file
        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.url) as resp:
                if resp.status == 200:
                    image_path = "downloaded_image.png"
                    with open(image_path, "wb") as f:
                        f.write(await resp.read())
                    print("Downloaded image successfully.")
                else:
                    await message.reply("Failed to download the image.")
                    return None

        # Upload the downloaded image and prepare it for analysis
        sample_file = prep_image(image_path)  # Get the sample file object
        # Determine the prompt
        prompt = message.content.strip().replace(f"<@{message.guild.me.id}>", "").replace("seeyuh", "").strip() or "Explain the content of the image."
        extracted_content = extract_text_from_image(sample_file, prompt)

        # Reply with extracted content
        if extracted_content:
            embed = discord.Embed(title="Image Analysis", description=extracted_content, color=0x00ff00)
            embed.set_thumbnail(url=attachment.url)
            embed.set_footer(text=bot.user.name, icon_url=str(bot.user.avatar.url))
            await message.reply(embed=embed)
        else:
            await message.reply("Failed to extract text from the image.")

    except Exception as e:
        print(f"An error occurred: {e}")
        await message.reply("An error occurred while processing the image.")
    finally:
        # Clean up by deleting the downloaded image file if it exists
        if os.path.exists(image_path):
            os.remove(image_path)
            print("Deleted temporary image file.")

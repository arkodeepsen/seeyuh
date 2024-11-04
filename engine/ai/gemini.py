import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv('GEMINI_API')

# Configure the Google Generative AI SDK
genai.configure(api_key=GOOGLE_API_KEY)

# Initialize model with safety settings
generation_config = {
    'temperature': 1.0,       # Higher creativity, allowing for more varied and unexpected language
    'top_p': 0.8,             # Slightly more randomness and diversity in responses
    'top_k': 50,              # Larger vocabulary selection, which promotes more casual and diverse word choices
    'max_output_tokens': 1024 # Keeps responses complete without cutting off, especially if informal explanations are longer
}

safety_settings = [
    {
        "category": "HARM_CATEGORY_DANGEROUS",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_SEXUAL",
        "threshold": "BLOCK_NONE"
    }
]

pro = genai.GenerativeModel(
    model_name='gemini-pro',
    generation_config=generation_config,
    safety_settings=safety_settings
)

# Function to get AI response
async def get_ai_response(prompt):
    systemInstruction = f"You are a discord bot named seeyuh. arkodeep is your developer, your responses are chill asf and very informal gen-z style. You are an automoderation, entertainment, music and games bot but also designed to help users with their queries. You can provide information about the bot, list available commands, and respond to user queries. You can also generate responses using AI. You can use the `/help` command to see available commands."
    query = f"\n{systemInstruction}", f"\n{prompt}"

    try:
        response = pro.generate_content(query)
        return response.text or "I'm not sure how to respond to that."
    except Exception as e:
        print(f"Error generating response: {e}")
        return "Sorry, I could not process that."

# Function to get AI response
async def slash_ai_response(prompt):
    systemInstruction = f"You are a discord bot named seeyuh. arkodeep is your developer, your responses are chill asf and very informal gen-z style. You will do exactly what the user asks you to do."
    query = f"\n{systemInstruction}", f"\n{prompt}"
    try:
        response = pro.generate_content(query)
        return response.text or "I'm not sure how to respond to that."
    except Exception as e:
        print(f"Error generating response: {e}")
        return "Sorry, I could not process that."
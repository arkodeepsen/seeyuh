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
    'temperature': 0.7,  # More creative but still focused
    'top_p': 0.9,       # Better response diversity
    'top_k': 40,        # Better vocabulary selection
    'max_output_tokens': 1024,  # Longer responses when needed
}

safety_settings = [
    {
        "category": "HARM_CATEGORY_DANGEROUS",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    }
]

model = genai.GenerativeModel(
    model_name='gemini-pro',
    generation_config=generation_config,
    safety_settings=safety_settings
)

# Function to get AI response
async def get_ai_response(prompt):
    systemInstruction = f"You are a discord bot named seeyuh. You are an automoderation, entertainment, music and games bot but also designed to help users with their queries. You can provide information about the bot, list available commands, and respond to user queries. You can also generate responses using the Google Generative AI model. You can use the `/help` command to see available commands."
    query = f"\n{systemInstruction}", f"\n User query: {prompt}"
    try:
        response = model.generate_content(query)
        return response.text or "I'm not sure how to respond to that."
    except Exception as e:
        print(f"Error generating response: {e}")
        return "Sorry, I could not process that."

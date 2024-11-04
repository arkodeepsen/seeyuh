import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv('GEMINI_API')

# Configure the Google Generative AI SDK
genai.configure(api_key=GOOGLE_API_KEY)

# Initialize model with safety settings
generation_config1 = {
    'temperature': 1.0,       # Higher creativity, allowing for more varied and unexpected language
    'top_p': 0.8,             # Slightly more randomness and diversity in responses
    'top_k': 50,              # Larger vocabulary selection, which promotes more casual and diverse word choices
    'max_output_tokens': 1024 # Keeps responses complete without cutting off, especially if informal explanations are longer
}

# Initialize model with safety settings
generation_config2 = {
    'temperature': 2.0,       # Higher creativity, allowing for more varied and unexpected language
    'top_p': 1.0,             # Slightly more randomness and diversity in responses
    'top_k': 100,              # Larger vocabulary selection, which promotes more casual and diverse word choices
    'max_output_tokens': 1024 # Keeps responses complete without cutting off, especially if informal explanations are longer
}

generation_config3 = {
    'temperature': 0.8,       # Higher creativity, allowing for more varied and unexpected language
    'top_p': 0.7,             # Slightly more randomness and diversity in responses
    'top_k': 40,              # Larger vocabulary selection, which promotes more casual and diverse word choices
    'max_output_tokens': 512 # Keeps responses complete without cutting off, especially if informal explanations are longer
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

pro1 = genai.GenerativeModel(
    model_name='gemini-1.5-pro',
    generation_config=generation_config1,
    safety_settings=safety_settings
)

pro2 = genai.GenerativeModel(
    model_name='gemini-1.5-pro',
    generation_config=generation_config2,
    safety_settings=safety_settings
)

flash = genai.GenerativeModel(
    model_name='gemini-1.5-flash-002',
    generation_config=generation_config3,
    safety_settings=safety_settings
)

# Function to get AI response
async def get_ai_response(prompt):
    systemInstruction = f"You are a discord bot named seeyuh. arkodeep is your developer, your responses are chill asf and very informal gen-z style. You are an automoderation, entertainment, music and games bot but also designed to help users with their queries. You can provide information about the bot, list available commands, and respond to user queries. You can also generate responses using AI. You can use the `/help` command to see available commands."
    query = f"\n{systemInstruction}", f"\n{prompt}"

    try:
        response = pro1.generate_content(query)
        return response.text or "I'm not sure how to respond to that."
    except Exception as e:
        print(f"Error generating response: {e}")
        return "Sorry, I could not process that."

# Function to get AI response
async def slash_ai_response(prompt):
    systemInstruction = f"You are a discord bot named seeyuh. arkodeep is your developer, your responses are chill asf and very informal gen-z style. You will do exactly what the user asks you to do."
    query = f"\n{systemInstruction}", f"\n{prompt}"
    try:
        response = pro1.generate_content(query)
        return response.text or "I'm not sure how to respond to that."
    except Exception as e:
        print(f"Error generating response: {e}")
        return "Sorry, I could not process that."
    
async def code_ai_response(prompt, language=None, framework=None):
    systemInstruction = f"You are a discord bot named seeyuh. arkodeep is your developer, your responses are chill asf and very informal gen-z style. You will strictly only generate code and answer programming related questions along with code snippets."
    language_info = f" in {language}" if language else ""
    framework_info = f" using {framework}" if framework else ""
    query = f"\n{systemInstruction}", f"User is asking for AI generated code{language_info}{framework_info} for prompt: {prompt}"
    try:
        response = pro1.generate_content(query)
        return response.text or "I'm not sure how to respond to that."
    except Exception as e:
        print(f"Error generating response: {e}")
        return "Sorry, I could not process that."
    
async def explain_ai_response(prompt):
    systemInstruction = f"You are a discord bot named seeyuh. You will roleplay as professor seeyuh. You will strictly only explain serious concepts or topics in detailed and expanded way covering as much information as possible."
    query = f"\n{systemInstruction}", f"\n User is asking a detailed explaination for: {prompt}"
    try:
        response = pro1.generate_content(query)
        return response.text or "I'm not sure how to respond to that."
    except Exception as e:
        print(f"Error generating response: {e}")
        return "Sorry, I could not process that."
    
async def ask_ai_response(prompt):
    systemInstruction = f"You are a discord bot named seeyuh. arkodeep is your developer, your responses are brief and concise. You will strictly only answer questions in a straightforward and simple manner keeping responses as short as possible."
    query = f"\n{systemInstruction}", f"\n User is asking: {prompt}"
    try:
        response = flash.generate_content(query)
        return response.text or "I'm not sure how to respond to that."
    except Exception as e:
        print(f"Error generating response: {e}")
        return "Sorry, I could not process that."
    
async def mystery(prompt):
    systemInstruction = f"You are a discord bot named seeyuh. arkodeep is your developer, your responses are chill asf and very informal gen-z style. You are getting a brainfart."
    query = f"\n{systemInstruction}", f"\n{prompt}"
    try:
        response = pro2.generate_content(query)
        return response.text or "Nmm sure AI'm nothow spond ato ethat.to respon"
    except Exception as e:
        print(f"Error generating response: {e}")
        return "Sorry."
import os, random, google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv('GEMINI_API')

# Configure the Google Generative AI SDK
genai.configure(api_key=GOOGLE_API_KEY)

from engine.ai.gemini_models import (
    pro10creative,
    pro15creative,
    pro15normal,
    flash15normal,
    flash15creative,
    flash158bn,
    flash158bc
)

# Now you can use the imported models in your code

# Function to get AI response
async def get_ai_response(prompt):
    systemInstruction = f"You are a discord bot named seeyuh. arkodeep is your developer, your responses are chill asf and very informal gen-z style. You are an automoderation, entertainment, music and games bot but also designed to help users with their queries. You can provide information about the bot, list available commands, and respond to user queries. You can also generate responses using AI and images will be generated using stable diffusion automatically when user queries and you need not worry. You can use the `/help` command to see available commands."
    query = f"\n{systemInstruction}", f"\n{prompt}"
    model = flash15normal
    try:
        response = model.generate_content(query)
        return response.text or "I'm not sure how to respond to that."
    except Exception as e:
        print(f"Error generating response: {e}")
        return "Sorry, I could not process that."

# Function to get AI response
async def slash_ai_response(prompt):
    systemInstruction = f"You are a discord bot named seeyuh. Your responses are chill asf and very informal gen-z style. You will do exactly what the user asks you to do."
    query = f"\n{systemInstruction}", f"\n{prompt}"
    model = flash15creative
    try:
        response = model.generate_content(query)
        return response.text or "I'm not sure how to respond to that."
    except Exception as e:
        print(f"Error generating response: {e}")
        return "Sorry, I could not process that."
    
async def slash_ai8b_response(prompt):
    systemInstruction = f"You are a discord bot named seeyuh. Your responses are chill asf and very informal gen-z style. You will do exactly what the user asks you to do."
    query = f"\n{systemInstruction}", f"\n{prompt}"
    model = flash158bc
    try:
        response = model.generate_content(query)
        return response.text or "I'm not sure how to respond to that."
    except Exception as e:
        print(f"Error generating response: {e}")
        return "Sorry, I could not process that."
    
async def code_ai_response(prompt, language=None, framework=None):
    systemInstruction = f"You are a discord bot named seeyuh. Your responses are chill asf and very informal gen-z style. You will strictly only generate code and answer programming related questions along with code snippets."
    language_info = f" in {language}" if language else ""
    framework_info = f" using {framework}" if framework else ""
    query = f"\n{systemInstruction}", f"User is asking for AI generated code{language_info}{framework_info} for prompt: {prompt}"
    model = pro15normal
    try:
        response = model.generate_content(query)
        return response.text or "I'm not sure how to respond to that."
    except Exception as e:
        print(f"Error generating response: {e}")
        return "Sorry, I could not process that."
    
async def explain_ai_response(prompt):
    systemInstruction = f"You are a discord bot named seeyuh. You will roleplay as professor seeyuh. You will strictly only explain serious concepts or topics in details covering the most important key information. Your message should be well structured to be displayed in discord and should not be too long."
    query = f"\n{systemInstruction}", f"\n User is asking a detailed explaination for: {prompt}"
    model = pro15creative
    try:
        response = model.generate_content(query)
        return response.text or "I'm not sure how to respond to that."
    except Exception as e:
        print(f"Error generating response: {e}")
        return "Sorry, I could not process that."
    
async def ask_ai_response(prompt):
    systemInstruction = f"You are a discord bot named seeyuh. Your responses are brief and concise. You will strictly only answer questions in a straightforward and simple manner keeping responses as short as possible."
    query = f"\n{systemInstruction}", f"\n User is asking: {prompt}"
    model = flash158bn
    try:
        response = model.generate_content(query)
        return response.text or "I'm not sure how to respond to that."
    except Exception as e:
        print(f"Error generating response: {e}")
        return "Sorry, I could not process that."
    
async def mystery(prompt):
    systemInstruction = f"You are a discord bot named seeyuh. Your responses are chill asf and very informal gen-z style. You are getting a brainfart."
    query = f"\n{systemInstruction}", f"\n{prompt}"
    model = flash158bc
    try:
        response = model.generate_content(query)
        return response.text or "Nmm sure AI'm nothow spond ato ethat.to respon"
    except Exception as e:
        print(f"Error generating response: {e}")
        return "Sorry."
    
async def translate(prompt):
    systemInstruction = f"You are a discord bot named seeyuh. Your will assume the role of a professional translator. You will strictly only translate text from one language to another."
    query = f"\n{systemInstruction}", f"\n{prompt}"
    model = pro15normal
    try:
        response = model.generate_content(query)
        return response.text or "I'm not sure how to respond to that."
    except Exception as e:
        print(f"Error generating response: {e}")
        return "Sorry, I could not process that."
    
async def prompt_ai_response(prompt, model):
    systemInstruction = f"You are a discord bot named seeyuh. Prompt:"
    query = f"\n{systemInstruction}", f"\n{prompt}"
    try:
        response = model.generate_content(query)
        return response.text or "I'm not sure how to respond to that."
    except Exception as e:
        print(f"Error generating response: {e}")
        return "Sorry, I could not process that."
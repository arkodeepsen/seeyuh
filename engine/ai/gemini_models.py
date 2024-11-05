import os, google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv('GEMINI_API')

# Configure the Google Generative AI SDK
genai.configure(api_key=GOOGLE_API_KEY)

# Initialize model with safety settings
slightly_creative_pro = {
    'temperature': 1.0,       # Higher creativity, allowing for more varied and unexpected language
    'top_p': 0.8,             # Slightly more randomness and diversity in responses
    'top_k': 50,              # Larger vocabulary selection, which promotes more casual and diverse word choices
    'max_output_tokens': 1024 # Keeps responses complete without cutting off, especially if informal explanations are longer
}

# Initialize model with safety settings
very_creative_pro = {
    'temperature': 2.0,       # Higher creativity, allowing for more varied and unexpected language
    'top_p': 1.0,             # Slightly more randomness and diversity in responses
    'top_k': 100,              # Larger vocabulary selection, which promotes more casual and diverse word choices
    'max_output_tokens': 2048 # Keeps responses complete without cutting off, especially if informal explanations are longer
}

slightly_creative_flash = {
    'temperature': 1,       # Higher creativity, allowing for more varied and unexpected language
    'top_p': 0.8,             # Slightly more randomness and diversity in responses
    'top_k': 40,              # Larger vocabulary selection, which promotes more casual and diverse word choices
    'max_output_tokens': 2048 # Keeps responses complete without cutting off, especially if informal explanations are longer
} 

very_creative_flash = {
    'temperature': 2,       # Higher creativity, allowing for more varied and unexpected language
    'top_p': 1.0,             # Slightly more randomness and diversity in responses
    'top_k': 40,              # Larger vocabulary selection, which promotes more casual and diverse word choices
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

pro10creative = genai.GenerativeModel(
    model_name='gemini-pro',
    generation_config=slightly_creative_pro,
    safety_settings=safety_settings
)

pro15creative = genai.GenerativeModel(
    model_name='gemini-1.5-pro',
    generation_config=very_creative_pro,
    safety_settings=safety_settings
)

pro15normal = genai.GenerativeModel(
    model_name='gemini-1.5-pro',
    generation_config=slightly_creative_pro,
    safety_settings=safety_settings
)   

flash15normal = genai.GenerativeModel(
    model_name='gemini-1.5-flash-002',
    generation_config=slightly_creative_flash,
    safety_settings=safety_settings
)

flash15creative = genai.GenerativeModel(
    model_name='gemini-1.5-flash-002',
    generation_config=very_creative_flash,
    safety_settings=safety_settings
)

flash158bn = genai.GenerativeModel(
    model_name='gemini-1.5-flash-8b',
    generation_config=slightly_creative_flash,
    safety_settings=safety_settings
)

flash158bc = genai.GenerativeModel(
    model_name='gemini-1.5-flash-8b',
    generation_config=very_creative_flash,
    safety_settings=safety_settings
)
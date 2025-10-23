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
    'max_output_tokens': 2048 # Keeps responses complete without cutting off, especially if informal explanations are longer
}

# Initialize model with safety settings
very_creative_pro = {
    'temperature': 1.5,       # Higher creativity, allowing for more varied and unexpected language
    'top_p': 1.0,             # Slightly more randomness and diversity in responses
    'top_k': 100,              # Larger vocabulary selection, which promotes more casual and diverse word choices
    'max_output_tokens': 2048 # Keeps responses complete without cutting off, especially if informal explanations are longer
}

slightly_creative_flash = {
    'temperature': 1.0,       # Higher creativity, allowing for more varied and unexpected language
    'top_p': 0.8,             # Slightly more randomness and diversity in responses
    'top_k': 40,              # Larger vocabulary selection, which promotes more casual and diverse word choices
    'max_output_tokens': 2048 # Keeps responses complete without cutting off, especially if informal explanations are longer
} 

very_creative_flash = {
    'temperature': 2.0,       # Higher creativity, allowing for more varied and unexpected language
    'top_p': 1.0,             # Slightly more randomness and diversity in responses
    'top_k': 40,              # Larger vocabulary selection, which promotes more casual and diverse word choices
    'max_output_tokens': 2048 # Keeps responses complete without cutting off, especially if informal explanations are longer
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
    model_name='gemini-pro-latest',
    generation_config=very_creative_pro,
    safety_settings=safety_settings
)

pro15normal = genai.GenerativeModel(
    model_name='gemini-pro-latest',
    generation_config=slightly_creative_pro,
    safety_settings=safety_settings
)   

flash15normal = genai.GenerativeModel(
    model_name='gemini-flash-latest',
    generation_config=slightly_creative_flash,
    safety_settings=safety_settings
)

flash15creative = genai.GenerativeModel(
    model_name='gemini-flash-latest',
    generation_config=very_creative_flash,
    safety_settings=safety_settings
)

flash158bn = genai.GenerativeModel(
    model_name='gemini-2.0-flash-lite-001',
    generation_config=slightly_creative_flash,
    safety_settings=safety_settings
)

flash158bc = genai.GenerativeModel(
    model_name='gemini-2.0-flash-lite-001',
    generation_config=very_creative_flash,
    safety_settings=safety_settings
)

flash2 = genai.GenerativeModel(
    model_name='gemini-2.0-flash',
    generation_config=slightly_creative_flash,
    safety_settings=safety_settings
)

#med = genai.GenerativeModel(
#    model_name='med-gemini',
#    safety_settings=safety_settings
#)

#other models

chat_bison = genai.GenerativeModel(
    model_name='models/chat-bison-001',
    safety_settings=safety_settings
)

text_bison = genai.GenerativeModel(
    model_name='models/text-bison-001',
    safety_settings=safety_settings
)

embedding_gecko = genai.GenerativeModel(
    model_name='models/embedding-gecko-001',
    safety_settings=safety_settings
)

gemini_pro_vision = genai.GenerativeModel(
    model_name='models/gemini-pro-vision',
    safety_settings=safety_settings
)

gemini_10_pro_vision_latest = genai.GenerativeModel(
    model_name='models/gemini-1.0-pro-vision-latest',
    safety_settings=safety_settings
)

gemini_15_pro_001 = genai.GenerativeModel(
    model_name='models/gemini-1.5-pro-001',
    safety_settings=safety_settings
)

gemini_15_pro_002 = genai.GenerativeModel(
    model_name='models/gemini-1.5-pro-002',
    safety_settings=safety_settings
)

gemini_15_pro_exp_0801 = genai.GenerativeModel(
    model_name='models/gemini-1.5-pro-exp-0801',
    safety_settings=safety_settings
)

gemini_15_pro_exp_0827 = genai.GenerativeModel(
    model_name='models/gemini-1.5-pro-exp-0827',
    safety_settings=safety_settings
)

gemini_15_flash_001 = genai.GenerativeModel(
    model_name='models/gemini-1.5-flash-001',
    safety_settings=safety_settings
)

gemini_15_flash_001_tuning = genai.GenerativeModel(
    model_name='models/gemini-1.5-flash-001-tuning',
    safety_settings=safety_settings
)

gemini_15_flash_exp_0827 = genai.GenerativeModel(
    model_name='models/gemini-1.5-flash-exp-0827',
    safety_settings=safety_settings
)

gemini_15_flash_002 = genai.GenerativeModel(
    model_name='models/gemini-1.5-flash-002',
    safety_settings=safety_settings
)

gemini_15_flash_8b_001 = genai.GenerativeModel(
    model_name='models/gemini-1.5-flash-8b-001',
    safety_settings=safety_settings
)

gemini_15_flash_8b_latest = genai.GenerativeModel(
    model_name='models/gemini-1.5-flash-8b-latest',
    safety_settings=safety_settings
)

gemini_15_flash_8b_exp_0827 = genai.GenerativeModel(
    model_name='models/gemini-1.5-flash-8b-exp-0827',
    safety_settings=safety_settings
)

gemini_15_flash_8b_exp_0924 = genai.GenerativeModel(
    model_name='models/gemini-1.5-flash-8b-exp-0924',
    safety_settings=safety_settings
)

gemini_exp_1206 = genai.GenerativeModel(
    model_name='models/gemini-exp-1206',
    safety_settings=safety_settings
)

gemini_exp_1121 = genai.GenerativeModel(
    model_name='models/gemini-exp-1121',
    safety_settings=safety_settings
)

gemini_exp_1114 = genai.GenerativeModel(
    model_name='models/gemini-exp-1114',
    safety_settings=safety_settings
)

learnlm_15_pro_experimental = genai.GenerativeModel(
    model_name='models/learnlm-1.5-pro-experimental',
    safety_settings=safety_settings
)

embedding_001 = genai.GenerativeModel(
    model_name='models/embedding-001',
    safety_settings=safety_settings
)

text_embedding_004 = genai.GenerativeModel(
    model_name='models/text-embedding-004',
    safety_settings=safety_settings
)

aqa = genai.GenerativeModel(
    model_name='models/aqa',
    safety_settings=safety_settings
)
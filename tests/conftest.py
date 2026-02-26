import sys
from unittest.mock import MagicMock

# Mock missing dependencies
mock_modules = [
    'discord',
    'discord.ext',
    'discord.app_commands',
    'discord.ui',
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    'aiohttp',
    'aiofiles',
    'httpx',
    'bs4',
    'engine.ai.gemini',
    'engine.utils',
    'watchdog',
    'watchdog.observers',
    'watchdog.events'
]

for module_name in mock_modules:
    sys.modules[module_name] = MagicMock()

# Configure the mock for engine.utils
utils_mock = sys.modules['engine.utils']
utils_mock.load_env.return_value = (None, None, None, None)
utils_mock.giphy_env.return_value = None
utils_mock.imgflip_env.return_value = (None, None)
utils_mock.hf_env.return_value = None
utils_mock.get_reddit_access_token.return_value = "mock_token"

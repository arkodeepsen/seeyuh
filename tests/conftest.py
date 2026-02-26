import sys
from unittest.mock import MagicMock

# --- Mock 'discord' ---
discord = MagicMock()

# Define simple mock classes for View and Button to avoid MagicMock inheritance issues
class MockView:
    def __init__(self, *args, **kwargs):
        self.children = []

    def add_item(self, item):
        self.children.append(item)

    def stop(self):
        pass

class MockButton:
    def __init__(self, *args, **kwargs):
        pass

discord.ui.View = MockView
discord.ui.Button = MockButton
discord.ButtonStyle = MagicMock()
discord.Interaction = MagicMock
discord.app_commands = MagicMock()
discord.app_commands.command = MagicMock(return_value=lambda func: func)
discord.app_commands.describe = MagicMock(return_value=lambda func: func)
discord.Intents = MagicMock()
discord.CustomActivity = MagicMock()
discord.Activity = MagicMock()
discord.Status = MagicMock()
discord.Embed = MagicMock()
discord.Color = MagicMock()

# Inject into sys.modules
sys.modules['discord'] = discord
sys.modules['discord.app_commands'] = discord.app_commands
sys.modules['discord.ui'] = MagicMock()
# We need to make sure discord.ui.View and Button are available via discord.ui
sys.modules['discord.ui'].View = MockView
sys.modules['discord.ui'].Button = MockButton
sys.modules['discord.ext'] = MagicMock()
sys.modules['discord.ext.commands'] = MagicMock()

# --- Mock 'google.generativeai' and 'google' ---
genai = MagicMock()
sys.modules['google.generativeai'] = genai
sys.modules['google'] = MagicMock()
sys.modules['google.genai'] = MagicMock()

# --- Mock 'duckduckgo_search' and 'ddgs' ---
sys.modules['duckduckgo_search'] = MagicMock()
sys.modules['ddgs'] = MagicMock()

# --- Mock HTTP libraries ---
sys.modules['aiohttp'] = MagicMock()
sys.modules['httpx'] = MagicMock()

# --- Mock Media libraries ---
sys.modules['moviepy'] = MagicMock()
sys.modules['moviepy.editor'] = MagicMock()
sys.modules['imageio'] = MagicMock()

# --- Mock PIL ---
sys.modules['PIL'] = MagicMock()
sys.modules['PIL.Image'] = MagicMock()
sys.modules['PIL.ImageDraw'] = MagicMock()
sys.modules['PIL.ImageFont'] = MagicMock()

# --- Mock 'bs4' ---
sys.modules['bs4'] = MagicMock()

# --- Mock 'aiofiles' ---
sys.modules['aiofiles'] = MagicMock()

# --- Mock 'engine.ai.gemini' ---
gemini_mock = MagicMock()
sys.modules['engine.ai.gemini'] = gemini_mock

# --- Mock 'engine.utils' ---
utils_mock = MagicMock()
utils_mock.load_env.return_value = (None, None, None, None)
utils_mock.giphy_env.return_value = None
utils_mock.get_reddit_access_token.return_value = None
utils_mock.imgflip_env.return_value = (None, None)
utils_mock.hf_env.return_value = None
utils_mock.qwen_env.return_value = (None, None)
utils_mock.infinitetalk_env.return_value = (None, None)

sys.modules['engine.utils'] = utils_mock

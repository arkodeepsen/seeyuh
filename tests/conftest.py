import sys
from unittest.mock import MagicMock, AsyncMock

# Define a simple MockView class to avoid MagicMock recursion issues
class MockView:
    def __init__(self, *args, **kwargs):
        self.children = []

    def add_item(self, item):
        self.children.append(item)

class MockButton:
    def __init__(self, *args, **kwargs):
        pass

# Mock discord
discord_mock = MagicMock()
discord_mock.ui.View = MockView
discord_mock.ui.Button = MockButton
discord_mock.app_commands = MagicMock()
discord_mock.Intents = MagicMock()
discord_mock.Color = MagicMock()
discord_mock.Embed = MagicMock()
discord_mock.FFmpegOpusAudio = MagicMock()
sys.modules['discord'] = discord_mock
sys.modules['discord.app_commands'] = discord_mock.app_commands
sys.modules['discord.ui'] = discord_mock.ui

# Mock other external dependencies
sys.modules['PIL'] = MagicMock()
sys.modules['PIL.Image'] = MagicMock()
sys.modules['PIL.ImageDraw'] = MagicMock()
sys.modules['PIL.ImageFont'] = MagicMock()
sys.modules['aiohttp'] = MagicMock()
sys.modules['aiofiles'] = MagicMock()
sys.modules['httpx'] = MagicMock()
sys.modules['bs4'] = MagicMock()

# Mock internal modules
engine_utils_mock = MagicMock()
# engine.utils.load_env returns 4 values
engine_utils_mock.load_env.return_value = ("fake_token", "fake_owner", "fake_url", "fake_key")
engine_utils_mock.giphy_env.return_value = "fake_giphy_key"
engine_utils_mock.imgflip_env.return_value = ("fake_user", "fake_pass")
engine_utils_mock.hf_env.return_value = "fake_hf_key"
engine_utils_mock.get_reddit_access_token = AsyncMock(return_value="fake_reddit_token")

sys.modules['engine.utils'] = engine_utils_mock
sys.modules['engine.ai.gemini'] = MagicMock()

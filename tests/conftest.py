import sys
import os
from unittest.mock import MagicMock
import pytest

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock dependencies
sys.modules['discord'] = MagicMock()
sys.modules['discord.ext'] = MagicMock()
sys.modules['discord.ext.commands'] = MagicMock()
sys.modules['httpx'] = MagicMock()
sys.modules['dotenv'] = MagicMock()
sys.modules['psutil'] = MagicMock()
sys.modules['moviepy'] = MagicMock()
sys.modules['moviepy.editor'] = MagicMock()
sys.modules['PIL'] = MagicMock()
sys.modules['aiohttp'] = MagicMock()

# Mocking specifically for 'from dotenv import load_dotenv'
dotenv_mock = MagicMock()
dotenv_mock.load_dotenv = MagicMock()
sys.modules['dotenv'] = dotenv_mock

# Mocking specifically for 'import discord' usage in utils.py
discord_mock = MagicMock()
discord_mock.Intents = MagicMock()
discord_mock.Intents.default = MagicMock()
discord_mock.PartialEmoji = MagicMock()
discord_mock.CustomActivity = MagicMock()
discord_mock.Activity = MagicMock()
discord_mock.ActivityType = MagicMock()
discord_mock.Status = MagicMock()
sys.modules['discord'] = discord_mock

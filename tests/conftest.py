import sys
from unittest.mock import MagicMock

# Mock modules that are not installed in the environment
# This must be done before engine.utils is imported in any test file
sys.modules["discord"] = MagicMock()
sys.modules["discord.ext"] = MagicMock()
sys.modules["httpx"] = MagicMock()
sys.modules["dotenv"] = MagicMock()

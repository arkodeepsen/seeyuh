# Seeyuh Bot
![Discord Bots](https://top.gg/api/widget/owner/690530760540553276.svg)
![Discord Bots](https://top.gg/api/widget/upvotes/690530760540553276.svg)
![Discord Bots](https://top.gg/api/widget/servers/690530760540553276.svg)

Seeyuh Bot is a powerful, AI-driven Discord bot designed for dynamic and multimodal interactions. Equipped with advanced features and seamless integration capabilities, it aims to provide a fun, ef...

---

## 🚦 **Bot Status**
![Status](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fseeyuh.up.railway.app%2Fstatus&query=status&prefix=%20&label=Status)
![Name](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fseeyuh.up.railway.app%2Fapi%2Fendpoint&query=name&prefix=%20&label=Name)
![ID](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fseeyuh.up.railway.app%2Fapi%2Fendpoint&query=id&prefix=%20&label=ID)
![Uptime](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fseeyuh.up.railway.app%2Fapi%2Fendpoint&query=uptime&prefix=%20&label=Uptime)
![Ping](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fseeyuh.up.railway.app%2Fapi%2Fendpoint&query=ping&prefix=%20&suffix=ms&label=Ping)
![Users](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fseeyuh.up.railway.app%2Fapi%2Fendpoint&query=unique_users&prefix=%20&label=Users)
![Servers](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fseeyuh.up.railway.app%2Fapi%2Fendpoint&query=guild_count&prefix=%20&label=Servers)

---

## 📦 **Hosting Details**
- **Platform**: Hosted on Railway  
- **Region**: Virginia, USA  
- **Bot Connection**: Connected to Discord's US East region  
- **Preferred Port**: 8080 

## 🎯 **Features**

### 🤖 **AI-Powered Interactions**
- Responds intelligently to mentions and commands.
- Supports natural language queries and multimodal responses (text, images, and more).
- Context-aware replies with dynamic and engaging interactions.

### 🛠️ **Command System**
- **Slash Commands**:  
  Clean and intuitive commands for ease of use.
  - `/help`: Get a list of all available commands.
  - `/info [@user]`: Fetch detailed information about the bot or tagged users.
  - `/ping`: Measure bot latency with a fun twist!
  - `/imagine`: Generate AI-powered images (see below)
- **Normal Commands**:  
  Handles basic text-based commands for classic Discord bot vibes.

### 🎨 **AI Image Generation (`/imagine`)**
Generate stunning images with 25+ AI models:
- **Multiple Models**: seeyuh-image-high (unlimited), FLUX.1, Stable Diffusion 3.5, and 20+ more models
- **Aspect Ratio Presets**: Choose from 8 preset ratios (1:1, 16:9, 9:16, 4:3, 3:4, 21:9, 3:2, 2:3)
- **High Quality**: 1K+ resolution with customizable inference steps
- **Real-time Status**: Loading animations with live progress updates
- **Custom Options**: Adjust model, width, height, steps, seed, and negative prompts

**Example Usage:**
```
/imagine prompt: a beautiful sunset over mountains
         model: seeyuh-image-high (unlimited)
         aspect_ratio: 16:9 Landscape
         steps: 75
```

### 🎮 **Games and Entertainment**
- Interactive mini-games for users to enjoy within the server.
- Trivia, puzzles, and more to keep the community engaged.

### 🔧 **Utility Commands**
- Fetch Reddit posts, YouTube videos, and Google search results directly within Discord.
- AI-powered career guidance and resume building (integration-ready).

### 🌐 **3rd Party API Integration**
- Image generation using advanced AI models.
- Custom features through APIs for Reddit, YouTube, Google, and more.

### 🖼️ **Image Processing**
- Automatically processes images and attachments shared in the chat.
- Integration with AI tools for content extraction, background removal, and more.

### 🚀 **Coming Soon**
- **Auto-moderation**: Keep your server safe with customizable moderation tools.  
  *(Stay tuned for updates!)*
  
---

## 📚 **How to Use**
1. Invite Seeyuh Bot to your Discord server.  
   *(Contact the owner or visit the bot's official website for the invite link.)*
2. Type `/help` to see the full list of available commands.
3. Interact using slash commands, mentions, or text queries for a seamless experience.

---

## 📦 **Tech Stack**
- **Programming Language**: Python
- **Framework**: discord.py
- **Database**: Supabase (for context and chat history)
- **Hosting**: Railway
- **AI Models**: 
  - Google Gemini API for text processing
  - HuggingFace Models (25+ models including FLUX, Stable Diffusion, etc.)
- **APIs**: Reddit, YouTube, Google Custom Search

---

## 🛡️ **Security**
- Tokens and sensitive data are stored securely in environment variables (`.env`).
- No sensitive information is shared or logged by the bot.
- Your messages might be saved for context but are deleted at regular intervals.

## ⚙️ Setup

Required environment variables — copy and edit the example file: [`.env.example`](.env.example)

1. Copy the template to a local `.env`:
  - macOS / Linux:
    ```bash
    cp .env.example .env
    ```
  - Windows (PowerShell):
    ```powershell
    Copy-Item .env.example .env
    ```
2. Open `.env` and fill in your keys (do not commit `.env` to version control).

Example `.env` keys:
```env
DISCORD_TOKEN=your_discord_token
HF_API_KEY=your_huggingface_key
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
# ... other API keys
```

See `.env.example` for the full template and required defaults. Keep sensitive values out of public repositories.

---

## 🤝 **Contributions**
This repository is now open-source under the GNU Affero General Public License v3.0 (AGPLv3). Contributions are accepted, but this is intentionally "just barely" open-source: any contributions or derivative works that operate the software over a network must be licensed under AGPLv3 as well and you must provide source code for any network-accessible modifications. By submitting a pull request you agree that your contribution will be licensed under AGPLv3.

---

## 📄 **License**
This project is licensed under the [GNU Affero General Public License v3.0 (AGPLv3)](./LICENSE). See the linked LICENSE file for the full terms. In short:
- You may use, study, and modify the code.
- If you distribute the software or make it available over a network, you must make the complete corresponding source code available under the same license (AGPLv3).
- This license is intentionally strict about sharing changes and network use; read the LICENSE file for the full legal text.

---

## 🌐 **Dynamic Updates**
- Visit the [Seeyuh Bot Website](https://seeyuh.up.railway.app) for real-time metrics and updates.  
- Join our [support server](https://discord.gg/ETXgCVYmBb) for announcements and issues.

---

[![Discord Bots](https://top.gg/api/widget/690530760540553276.svg)](https://top.gg/bot/690530760540553276)
# Seeyuh Bot - Advanced AI Discord Bot
![Discord Bots](https://top.gg/api/widget/owner/690530760540553276.svg)
![Discord Bots](https://top.gg/api/widget/upvotes/690530760540553276.svg)
![Discord Bots](https://top.gg/api/widget/servers/690530760540553276.svg)

**Seeyuh Bot** is a next-generation, AI-powered Discord bot featuring advanced agentic capabilities, multimodal interactions, RAG (Retrieval-Augmented Generation), and real-time grounding. Built for dynamic, context-aware conversations with cutting-edge AI features.

---

## 🚦 **Bot Status**
![Status](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fseeyuh.onrender.com%2Fstatus&query=status&prefix=%20&label=Status)
![Name](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fseeyuh.onrender.com%2Fapi%2Fendpoint&query=name&prefix=%20&label=Name)
![ID](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fseeyuh.onrender.com%2Fapi%2Fendpoint&query=id&prefix=%20&label=ID)
![Uptime](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fseeyuh.onrender.com%2Fapi%2Fendpoint&query=uptime&prefix=%20&label=Uptime)
![Ping](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fseeyuh.onrender.com%2Fapi%2Fendpoint&query=ping&prefix=%20&suffix=ms&label=Ping)
![Users](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fseeyuh.onrender.com%2Fapi%2Fendpoint&query=unique_users&prefix=%20&label=Users)
![Servers](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fseeyuh.onrender.com%2Fapi%2Fendpoint&query=guild_count&prefix=%20&label=Servers)

---

## 📦 **Hosting Details**
- **Platform**: Render (Cloud Hosting)
- **Region**: Virginia, USA  
- **Bot Connection**: Discord US East (optimized latency)
- **Preferred Port**: 8080 

## 🎯 **Core Features**

### 🧠 **Advanced AI Agent System**
Seeyuh is a true agentic AI with sophisticated decision-making capabilities:
- **Multi-Model Intelligence**: Seamlessly switches between 8+ Google Gemini models (Pro, Flash, Flash-8B variants)
- **Automatic Fallback Chains**: Smart quota management with automatic model switching
- **Context-Aware Conversations**: Maintains conversation history via Supabase for natural, flowing interactions
- **RAG (Retrieval-Augmented Generation)**: Real-time web search integration via DuckDuckGo for grounded responses
- **Tool Use & Function Calling**: Can execute searches, analyze content, and use external tools autonomously
- **Multimodal Understanding**: Processes text, images, videos, PDFs, audio, and code files

### 🎨 **Advanced AI Image & Video Tools**

**AI Image Generation (`/imagine`):**
- **Dual Model System**: 
  - Primary: Custom Qwen Image Based Model (serverless) with high-quality 2K+ resolution
  - Fallback: Gemini 2.0 Flash for image generation
- **25+ Model Support**: FLUX.1, Stable Diffusion 3.5, seeyuh-image-high (unlimited, very slow), and more
- **Advanced Controls**: Aspect ratios (8 presets), inference steps (20-100), CFG scale, seed control
- **Real-time Progress**: Live status updates with loading animations
- **Negative Prompts**: Fine-tune output by excluding unwanted elements

**AI Image Editing Suite:**
- `/caption` - Generate intelligent captions for images
- `/variation` - Create variations of existing images
- `/refine` - Enhance image quality and details
- `/modify` - Modify images with text prompts
- `/edit_image` - Advanced editing with Nanobanana

**AI Video & Animation:**
- **Chat-to-Video**: Convert Discord conversations into beautiful animated videos
  - Multi-Voice TTS: Edge TTS with 12+ voices (male & female)
  - Dynamic Animations: Unique gradient effects, floating particles, liquid glass bubbles
  - Media Integration: Embeds images, videos, and thumbnails from links
  - Server Boost Tiers: Quality scales with server boost level (20-200 messages, 10-100MB)
- `/animate` - **Revolutionary image + audio to video generator** using Custom Hosted Model
  - Animate images/videos with audio or TTS
  - Multi-person support (single/double)
  - Multilingual TTS (auto-detect or manual selection)
  - Resolution options (480p-720p)
  - Serverless GPU processing

**AI Music & Audio:**
- `/musicgen` - Generate music from text descriptions (Facebook MusicGen)
- `/text_to_speech` - Convert text to speech in voice channels
- `/youtube` - Smart YouTube search and summarization

### 🎙️ **Text-to-Speech & Speech Features**
- **Edge TTS Integration**: 12+ high-quality voices (English variants)
- **gTTS Fallback**: Ensures 99.9% uptime for voice generation
- **Smart Text Cleaning**: Removes markdown, URLs, emojis for natural speech
- **Voice Assignment**: Persistent voice per user during video sessions

### 🔍 **Web Search & Information Tools**
- **Multi-Engine Search**: DuckDuckGo, Google, Bing, Yahoo integration
- **AI-Powered Search**: Claude-3 Haiku, GPT-4o Mini, Llama 3.1, Mixtral-8x7B for result summarization
- **News Search**: Latest articles with AI summaries and source links
- **Image/Video Search**: Find and display media from multiple sources
- **Real-time Grounding**: All AI responses can be grounded in live web data

### 🎵 **Advanced Music System**
- **Multi-Source Support**: YouTube (primary), with smart fallback strategies
- **High-Quality Audio**: Opus codec streaming at 128kbps
- **Smart Extraction**: iOS/Android/Web client emulation to bypass restrictions
- **Audio Effects**: Bass boost, nightcore, 8D, vibrato, echo, chipmunk, slowed, and more
- **Lyrics Integration**: Genius API + YouTube transcript fallback
- **Queue Management**: Add, skip, loop, and manage playlists
- **Voice Controls**: Play/pause/skip via interactive buttons

### 📊 **Content Analysis & Processing**
**Multimodal Analysis (`/analyze`):**
- **Supported Formats**: 
  - Images (JPEG, PNG, WebP, GIF)
  - Videos (MP4, WebM, MOV, AVI)
  - Documents (PDF)
  - Audio (MP3, WAV, OGG)
  - Code/Text files (Java, Python, JavaScript, plain text)
- **10MB File Limit**: Automatic validation and error handling
- **Context-Aware**: Accepts optional prompts for targeted analysis

### 🎮 **Interactive Games**
- **Classic Games**: Rock-Paper-Scissors, Coin Flip, Dice Roll, Magic 8-Ball, Tic-Tac-Toe
- **Extended Variants**: Rock-Paper-Scissors-Lizard-Spock (RPSLS)
- **Word Games**: Wordle, Trivia (OpenTDB API + fallback questions)
- **Personality Tools**: Horoscope, Roast, Compliment generation

### 🛠️ **Utility Commands**
**AI-Powered Tools:**
- `/code` - Generate code in any language with executable output support
- `/explain` - Detailed explanations of complex topics
- `/ask` - Concise, single-line responses
- `/translate` - 25+ language support
- `/chat` - Interactive AI conversations with model selection
- `/prompt` - Direct model prompting (8 models available)
- `/reason` - Advanced reasoning and problem-solving with Gemini
- `/aisearch` - AI-powered web search with grounded responses
- `/meaning` - Get definitions and word meanings

**Content Tools:**
- `/search` - Multi-engine web search with image/video modes
- `/news` - Latest news with AI summaries
- `/reddit` - Fetch posts from any subreddit (NSFW filter support)
- `/meme` - Random memes from r/memes
- `/dadjoke` - Dad jokes with search support
- `/image` - Image search (Unsplash, DuckDuckGo, Bing, Yahoo)
- `/video` - Pexels video search with smart filtering
- `/weather` - Weather information with beautiful embeds
- `/youtube` - YouTube video search and summaries

**Welcome System:**
- `/welcome_enable` - Enable animated welcome videos for new members
- `/welcome_disable` - Disable welcome system
- `/welcome_message` - Set custom welcome message with placeholders
- `/welcome_channel` - Set welcome channel
- `/welcome_show` - View current welcome settings
- `/welcome_reset` - Reset to default settings

**Social Features:**
- `/avatar` - Display user avatars
- `/banner` - Show user banners
- `/info` - Detailed user/bot information
- `/serverinfo` - Server statistics and details
- `/poll` - Create polls with duration control

**Fun Tools:**
- `/gif` - Giphy integration
- `/cowsay` - Customizable cow messages (4 variants)
- `/memegen` - Custom meme generation with templates
- `/soundboard` - MyInstants sound effects with voice playback
- `/lyrics` - Song lyrics from Genius + YouTube transcripts
- `/mystery` - Mystery game with AI-generated stories

**Misc/Social:**
- `/steam` - Steam profile lookup
- `/steamlink` - Link your Steam profile
- `/steamgame` - Get Steam game information
- `/steamnews` - Latest Steam news
- `/cat` - Random cat pictures
- `/dog` - Random dog pictures
- `/dogfact` - Random dog facts
- `/itunes` - iTunes music search
- `/leaderboard` - Server activity leaderboard
- `/rank` - Check your server rank

### 🎨 **Creative Tools**
- **Meme Generator**: Template-based + custom URL + search-powered
- **Voice Soundboard**: Play sound effects in voice channels
- **Video Creation**: Chat replay videos with TTS narration
- **Animated Welcomes**: Stunning animated welcome videos with TTS for new members
- **Talking Avatars**: Animate images with `/animate` using AI
- **AI Music**: Generate music from text with `/musicgen`
- **Image Variations**: Create endless variations with `/variation`, `/refine`, `/modify`
  
---

## 📚 **How to Use**
1. **Invite Seeyuh Bot** to your Discord server using the invite link.  
   - [**Invite Link**](https://discord.com/oauth2/authorize?client_id=690530760540553276&permissions=8&scope=bot%20applications.commands)
   - Contact the owner or visit the [official website](https://seeyuh.onrender.com) for support

2. **Explore Commands**:
   - Type `/help` to see all available commands organized by category
   - Use slash commands (`/`) for clean, intuitive interactions
   - Mention `@Seeyuh` for context-aware AI conversations

3. **AI Features**:
   - Chat naturally with the bot via mentions for contextual responses
   - Use `/imagine` to generate AI images
   - Analyze files with `/analyze` (images, videos, PDFs, code, audio)
   - Search the web with `/search`, `/news`, or `/aisearch` for grounded AI answers

4. **Music & Entertainment**:
   - Join a voice channel and use `/play [song name or URL]` to start music
   - Create memes with `/memegen` or chat videos with mention-based recording
   - Play interactive games like `/trivia`, `/tictactoe`, `/rps`, and more

---

## 📦 **Tech Stack**

### **Core Technologies**
- **Language**: Python 3.11+
- **Framework**: discord.py (v2.x)
- **Database**: Supabase (PostgreSQL) - Chat history & context storage
- **Hosting**: Render (Cloud Platform)
- **CDN/Storage**: Network Volume (S3-compatible) for media assets

### **AI & Machine Learning**
- **Primary AI**: Google Gemini
- **Image Generation**: 
  - Custom Qwen Image Based Model (serverless) - High-quality 2K+ resolution
  - Gemini 2.0 Flash (fallback)
  - HuggingFace Models (25+ models: FLUX.1, Stable Diffusion 3.5, etc.)
- **Image Editing**: Nanobanana for advanced editing
- **Video Animation**: Custom AI model from Meigen (serverless) for tis2v
- **Voice Synthesis**: Edge TTS (12+ voices) with gTTS fallback
- **Music Generation**: Facebook MusicGen (HuggingFace Inference API)
- **Web Grounding**: DuckDuckGo search API for RAG capabilities

### **Media Processing**
- **Video Creation**: FFmpeg + MoviePy for chat-to-video generation
- **Image Processing**: Pillow (PIL) for image manipulation and effects
- **Audio**: yt-dlp for YouTube extraction, FFmpeg Opus encoding
- **Lyrics**: Genius API + YouTube Transcript API

### **External APIs**
| Service | Purpose |
|---------|---------|
| Google Gemini | AI text generation & multimodal analysis |
| RunPod | Serverless GPU inference |
| HuggingFace | Image generation models & MusicGen |
| DuckDuckGo | Web search & news retrieval |
| Genius | Song lyrics retrieval |
| Reddit | Meme and content fetching |
| Pexels | Stock video search |
| Unsplash | High-quality image search |
| Giphy | GIF search and retrieval |
| MyInstants | Sound effect library |
| OpenTDB | Trivia questions |
| Edge TTS | Text-to-speech synthesis |
| Steam | Game & profile information |
| iTunes | Music search & information |

---

## 🛡️ **Security & Privacy**
### **Data Protection**
- **Environment Variables**: All API keys and tokens stored securely in `.env` files
- **No Logging**: Sensitive information never logged or exposed
- **Auto-Cleanup**: Message context deleted at regular intervals
- **NSFW Filtering**: Automatic content filtering in non-NSFW channels

### **User Privacy**
- **Context Storage**: Messages saved temporarily for conversation continuity
- **Opt-Out**: Users can request data deletion anytime
- **No Third-Party Sharing**: Your data stays within the bot ecosystem
- **Transparent**: Full source code available (AGPLv3 license)

### **Server Safety**
- **Rate Limiting**: Built-in protection against spam and abuse
- **Permission-Based**: Commands respect Discord permission hierarchy
- **Moderation Tools**: Admin-only commands for server management
- **NSFW Controls**: Strict enforcement of Discord's NSFW guidelines

---

## ⚙️ **Setup & Installation**

### **Prerequisites**
- Python 3.11 or higher
- FFmpeg (for audio/video processing)
- PostgreSQL database (or Supabase account)
- Required API keys (see below)

### **Required API Keys**
Create a `.env` file in the root directory with these keys:

```env
# Discord
DISCORD_TOKEN=your_discord_bot_token
OWNER=your_discord_user_id

# AI Models
GEMINI_API=your_google_gemini_api_key
GEMINI_PRO_API_KEY=your_gemini_pro_api_key
HF_API_KEY=your_huggingface_api_key
RUNPOD_ENDPOINT_ID=your_runpod_endpoint_id
RUNPOD_API_KEY=your_runpod_api_key

# Database
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_key

# External APIs
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
GIPHY_API_KEY=your_giphy_api_key
GENIUS_API_KEY=your_genius_api_key
UNSPLASH_ACCESS_KEY=your_unsplash_access_key
PEXELS_API_KEY=your_pexels_api_key

# Optional
IMGFLIP_USERNAME=your_imgflip_username
IMGFLIP_PASSWORD=your_imgflip_password
```

See [`.env.example`](.env.example) for the complete template with all required keys.

### **Installation Steps**

1. **Clone the repository:**
   ```bash
   git clone https://github.com/arkodeepsen/seeyuh.git
   cd seeyuh
   ```

2. **Set up environment (recommended):**
   
   **macOS / Linux:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
   
   **Windows (PowerShell):**
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

3. **Install FFmpeg:**
   
   **macOS (Homebrew):**
   ```bash
   brew install ffmpeg
   ```
   
   **Ubuntu/Debian:**
   ```bash
   sudo apt update
   sudo apt install ffmpeg
   ```
   
   **Windows:**
   - Download from [ffmpeg.org](https://ffmpeg.org/download.html)
   - Add to PATH or place in `ffmpeg/bin/` directory

4. **Configure environment:**
   ```bash
   # macOS / Linux
   cp .env.example .env
   
   # Windows (PowerShell)
   Copy-Item .env.example .env
   ```
   
   Edit `.env` and add your API keys.

5. **Initialize database:**
   - Create a Supabase project at [supabase.com](https://supabase.com)
   - Run the SQL schema from `database/schema.sql` in your Supabase SQL editor
   - Copy your project URL and anon key to `.env`

6. **Run the bot:**
   ```bash
   python start.py
   ```

### **Deployment**
The bot is production-ready for deployment on:
- **Render** (recommended) - See [DEPLOYMENT.md](DEPLOYMENT.md)
- **Render** - Use `render.yaml` configuration
- **Docker** - Use provided `Dockerfile`
- **Any VPS** - Requires Python 3.11+, FFmpeg, and PostgreSQL

---

## 🤝 **Contributing**
This repository is open-source under the **GNU Affero General Public License v3.0 (AGPLv3)**. Contributions are welcome with the following conditions:

### **Contribution Guidelines**
1. **Fork & Branch**: Create a feature branch from `main`
2. **Code Quality**: Follow existing code style and conventions
3. **Testing**: Test your changes thoroughly before submitting
4. **Documentation**: Update README or docs if adding new features
5. **License Compliance**: All contributions must be compatible with AGPLv3

### **What You Can Contribute**
- 🐛 Bug fixes and performance improvements
- ✨ New commands and features
- 📚 Documentation enhancements
- 🌐 Translations and localization
- 🎨 UI/UX improvements for embeds and messages

### **Important Notes**
- By submitting a pull request, you agree that your contribution will be licensed under AGPLv3
- Any derivative works or network-accessible modifications **must**:
  - Be licensed under AGPLv3
  - Provide complete source code to all users
  - Maintain the same license terms
- This is intentionally **"barely" open source** - strict copyleft provisions apply

### **How to Contribute**
1. Fork this repository
2. Create your feature branch: `git checkout -b feature/AmazingFeature`
3. Commit your changes: `git commit -m 'Add some AmazingFeature'`
4. Push to the branch: `git push origin feature/AmazingFeature`
5. Open a Pull Request

---

## 📄 **License**
This project is licensed under the [**GNU Affero General Public License v3.0 (AGPLv3)**](./LICENSE).

### **Key Terms**
- ✅ **You MAY**: Use, study, modify, and distribute the code
- ⚠️ **You MUST**: 
  - Make source code available under AGPLv3 if you distribute or run over a network
  - Preserve copyright and license notices
  - State significant changes made to the code
  - License derivative works under AGPLv3
- ❌ **You CANNOT**:
  - Distribute closed-source versions
  - Use for proprietary/commercial purposes without source disclosure
  - Remove or modify license terms

### **Network Use Clause**
This license is **intentionally strict** about network use:
- If you run a modified version accessible over a network (e.g., Discord bot)
- You **MUST** provide the complete source code to all network users
- This includes all modifications and dependencies
- No exceptions - read the [full LICENSE](./LICENSE) text for complete legal terms

---

## 🌐 **Links & Resources**

### **Official**
- 🌍 [**Website**](https://seeyuh.onrender.com) - Live status, metrics, and documentation
- 📊 [**Top.gg Page**](https://top.gg/bot/690530760540553276) - Upvote and review
- 💬 [**Support Server**](https://discord.gg/ETXgCVYmBb) - Get help, report bugs, suggest features
- 💰 [**Support Development**](https://paypal.me/arkodeepsen) - Help keep the bot alive!

### **Documentation**
- 📖 [Privacy Policy](https://seeyuh.onrender.com/privacy-policy) - How we handle your data
- 📜 [Terms of Service](https://seeyuh.onrender.com/terms) - Usage terms and conditions
- 🚀 [Deployment Guide](DEPLOYMENT.md) - Self-hosting instructions

### **Developer**
- 👨‍💻 **Creator**: arkodeep (Discord: arkodeep#0001)
- 📧 **Contact**: Available via Discord support server
- 🔧 **GitHub**: [arkodeepsen/seeyuh](https://github.com/arkodeepsen/seeyuh)

---

## 🙏 **Acknowledgments**

### **Technologies Used**
- [discord.py](https://github.com/Rapptz/discord.py) - Discord bot framework
- [Google Gemini](https://ai.google.dev) - Advanced AI capabilities
- [Supabase](https://supabase.com) - Database and backend services
- [Render](https://render.com) - Cloud hosting platform
- [FFmpeg](https://ffmpeg.org) - Media processing
- [HuggingFace](https://huggingface.co) - AI model hub
- [RunPod](https://runpod.io) - GPU serverless inference

### **API Providers**
Thanks to these services for powering various features:
- Google (Gemini AI), Reddit, Genius, Giphy, Pexels, Unsplash, OpenTDB, MyInstants

### **Community**
- All contributors who have helped improve Seeyuh Bot
- Server owners who provide valuable feedback
- Users who report bugs and suggest features

---

## 📊 **Statistics**
[![Discord Bots](https://top.gg/api/widget/690530760540553276.svg)](https://top.gg/bot/690530760540553276)

**Want to support the project?**
- ⭐ Star this repository
- 🗳️ Upvote on [Top.gg](https://top.gg/bot/690530760540553276)
- 💬 Join our [Discord server](https://discord.gg/ETXgCVYmBb)
- 💰 [Donate](https://paypal.me/arkodeepsen) to support development

---

<div align="center">

**Made with ❤️ by arkodeep**

*Seeyuh Bot - Where AI meets creativity*

[Website](https://seeyuh.onrender.com) • [Support Server](https://discord.gg/ETXgCVYmBb) • [Top.gg](https://top.gg/bot/690530760540553276) • [Donate](https://paypal.me/arkodeepsen)

</div>
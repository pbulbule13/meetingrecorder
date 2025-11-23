# Setup Guide

Comprehensive guide to installing and configuring Nexus Assistant.

## Table of Contents
- [System Requirements](#system-requirements)
- [Quick Start](#quick-start)
- [Detailed Installation](#detailed-installation)
- [Configuration](#configuration)
- [API Keys Setup](#api-keys-setup)
- [Troubleshooting](#troubleshooting)

---

## System Requirements

### Minimum Requirements
- **OS**: Windows 10+, macOS 10.15+, or Linux (Ubuntu 20.04+)
- **CPU**: 2-core processor (Intel i5 or equivalent)
- **RAM**: 4GB
- **Disk**: 2GB free space (plus space for recordings)
- **Network**: Internet connection for API providers

### Recommended Requirements
- **OS**: Windows 11, macOS 12+, or Linux (Ubuntu 22.04+)
- **CPU**: 4-core processor (Intel i7 or equivalent)
- **RAM**: 8GB
- **Disk**: 10GB free space
- **Network**: Broadband internet (for real-time transcription)

### Software Prerequisites
- **Node.js**: v20.0.0 or higher ([Download](https://nodejs.org/))
- **Python**: v3.11 or higher ([Download](https://www.python.org/))
- **FFmpeg**: Latest version ([Download](https://ffmpeg.org/download.html))
- **Git**: For cloning repository ([Download](https://git-scm.com/))

---

## Quick Start

### Automated Installation (Recommended)

#### Windows
```cmd
git clone https://github.com/pbulbule13/meetingrecorder.git
cd meetingrecorder
run.bat
```

The `run.bat` script will:
1. Check for Node.js, Python, and FFmpeg
2. Install UV package manager for fast Python installs
3. Create Python virtual environment
4. Install all dependencies (Node.js + Python)
5. Create required directories
6. Prompt for API keys
7. Start all services

#### Linux/macOS
```bash
git clone https://github.com/pbulbule13/meetingrecorder.git
cd meetingrecorder
chmod +x run.bat
./run.bat
```

---

## Detailed Installation

### Step 1: Install Prerequisites

#### Node.js
Download and install from [nodejs.org](https://nodejs.org/)

Verify installation:
```bash
node --version  # Should show v20.0.0 or higher
npm --version   # Should show v10.0.0 or higher
```

#### Python
Download and install from [python.org](https://www.python.org/)

Verify installation:
```bash
python --version  # Should show 3.11.0 or higher
pip --version     # Should be included with Python
```

**Important**: On Windows, make sure to check "Add Python to PATH" during installation.

#### FFmpeg

**Windows**:
1. Download from [ffmpeg.org](https://ffmpeg.org/download.html#build-windows)
2. Extract to `C:\ffmpeg`
3. Add `C:\ffmpeg\bin` to system PATH
4. Verify: `ffmpeg -version`

**macOS** (using Homebrew):
```bash
brew install ffmpeg
```

**Linux** (Ubuntu/Debian):
```bash
sudo apt update
sudo apt install ffmpeg
```

Verify:
```bash
ffmpeg -version
```

### Step 2: Clone Repository
```bash
git clone https://github.com/pbulbule13/meetingrecorder.git
cd meetingrecorder
```

### Step 3: Install Dependencies

#### Option A: Using UV (Fast, Recommended)
```bash
# Install UV
pip install uv

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install Python dependencies with UV
uv pip install -r requirements.txt

# Install Node.js dependencies
npm install
```

#### Option B: Using pip (Standard)
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Install Node.js dependencies
npm install
```

### Step 4: Configure Environment

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` and add your API keys (see [API Keys Setup](#api-keys-setup) below).

### Step 5: Create Required Directories
```bash
mkdir data logs chroma_data
```

### Step 6: Start Application

#### Development Mode
```bash
# Make sure virtual environment is activated
npm run dev
```

This will:
1. Start Python microservices on ports 38421, 45231, 53847
2. Start Electron application

#### Production Build
```bash
# Build for your platform
npm run build:win    # Windows
npm run build:mac    # macOS
npm run build:linux  # Linux

# Installer will be in dist/ directory
```

---

## Configuration

### Environment Variables

#### Required Variables

**Speech-to-Text** (choose at least one):
```bash
DEEPGRAM_API_KEY=your_deepgram_key_here
ASSEMBLYAI_API_KEY=your_assemblyai_key_here
OPENAI_API_KEY=your_openai_key_here
```

**LLM Provider** (choose at least one):
```bash
GEMINI_API_KEY=your_gemini_key_here
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
GROQ_API_KEY=your_groq_key_here
```

#### Optional Variables

**Service Ports** (use defaults or customize):
```bash
TRANSCRIPTION_SERVICE_PORT=38421
LLM_SERVICE_PORT=45231
RAG_SERVICE_PORT=53847
API_SERVER_PORT=62194
```

**Feature Flags**:
```bash
ENABLE_REAL_TIME_ASSISTANCE=true
ENABLE_WEB_SEARCH=true
ENABLE_ANALYTICS=true
ENABLE_ENCRYPTION=false
```

**Web Search** (optional):
```bash
GOOGLE_SEARCH_API_KEY=your_google_api_key
GOOGLE_SEARCH_ENGINE_ID=your_search_engine_id
```

**Ollama** (optional, for local LLM):
```bash
OLLAMA_ENABLED=true
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3
```

**Embedding Model**:
```bash
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

**Database**:
```bash
DATABASE_PATH=./data/nexus.db
ENABLE_DATABASE_ENCRYPTION=false
DATABASE_ENCRYPTION_KEY=your_32_byte_key_here
```

### Audio Configuration

Edit audio settings in `.env`:
```bash
# Audio format
AUDIO_SAMPLE_RATE=16000
AUDIO_CHANNELS=1
AUDIO_BIT_DEPTH=16

# Chunk size (in seconds) for real-time transcription
AUDIO_CHUNK_DURATION=5
```

---

## API Keys Setup

### Deepgram (Recommended for STT)

1. Go to [deepgram.com](https://deepgram.com/)
2. Sign up for free account (includes $200 credit)
3. Navigate to API Keys section
4. Create new API key
5. Copy key to `.env`:
   ```bash
   DEEPGRAM_API_KEY=your_key_here
   ```

**Pricing**: $0.0125 per minute (Nova-2 model)

### AssemblyAI (Best Diarization)

1. Go to [assemblyai.com](https://www.assemblyai.com/)
2. Sign up for free account
3. Get API key from dashboard
4. Add to `.env`:
   ```bash
   ASSEMBLYAI_API_KEY=your_key_here
   ```

**Pricing**: $0.37 per audio hour

### Google Gemini (Recommended for LLM)

1. Go to [aistudio.google.com](https://aistudio.google.com/)
2. Sign in with Google account
3. Click "Get API Key"
4. Create new API key
5. Add to `.env`:
   ```bash
   GEMINI_API_KEY=your_key_here
   ```

**Pricing**: Free tier available, then $0.00025 per 1K input tokens

### OpenAI (GPT + Whisper)

1. Go to [platform.openai.com](https://platform.openai.com/)
2. Sign up and add payment method
3. Navigate to API Keys
4. Create new secret key
5. Add to `.env`:
   ```bash
   OPENAI_API_KEY=sk-your_key_here
   ```

**Pricing**:
- Whisper: $0.006 per minute
- GPT-4o: $2.50 per 1M input tokens

### Anthropic Claude

1. Go to [console.anthropic.com](https://console.anthropic.com/)
2. Sign up for account
3. Get API key from settings
4. Add to `.env`:
   ```bash
   ANTHROPIC_API_KEY=sk-ant-your_key_here
   ```

**Pricing**: $3 per 1M input tokens (Claude 3.5 Sonnet)

### Groq (Fast Inference)

1. Go to [console.groq.com](https://console.groq.com/)
2. Sign up for free account
3. Generate API key
4. Add to `.env`:
   ```bash
   GROQ_API_KEY=gsk_your_key_here
   ```

**Pricing**: Free tier available

### Google Custom Search (Optional)

For web search feature:

1. Go to [console.cloud.google.com](https://console.cloud.google.com/)
2. Create new project
3. Enable Custom Search API
4. Create API key
5. Go to [cse.google.com](https://cse.google.com/)
6. Create custom search engine
7. Get Search Engine ID
8. Add to `.env`:
   ```bash
   GOOGLE_SEARCH_API_KEY=your_api_key
   GOOGLE_SEARCH_ENGINE_ID=your_cx_id
   ```

---

## Platform-Specific Setup

### Windows

#### Audio Capture Setup
1. Right-click speaker icon in taskbar
2. Open "Sound settings"
3. Scroll to "Advanced sound options"
4. Under "Recording", enable "Stereo Mix"
5. Set as default recording device

If "Stereo Mix" is not available:
1. Right-click in Recording devices window
2. Check "Show Disabled Devices"
3. Enable "Stereo Mix"

#### Firewall
Allow Node.js and Python through Windows Firewall if prompted.

### macOS

#### Permissions
Grant microphone access:
1. System Preferences → Security & Privacy
2. Click Privacy tab
3. Select Microphone
4. Check the box next to Nexus Assistant

#### Audio Capture
Install BlackHole for system audio capture:
```bash
brew install blackhole-2ch
```

Configure Audio MIDI Setup:
1. Open Audio MIDI Setup (in Utilities)
2. Create Multi-Output Device
3. Select BlackHole and Built-in Output
4. Create Aggregate Device
5. Select BlackHole and Built-in Input

### Linux

#### Audio Setup (PulseAudio)
```bash
# Install PulseAudio
sudo apt install pulseaudio pavucontrol

# Start PulseAudio
pulseaudio --start

# Configure loopback for system audio
pactl load-module module-loopback
```

#### Permissions
Add user to audio group:
```bash
sudo usermod -a -G audio $USER
```

Logout and login for changes to take effect.

---

## Verification

### Check Services

After starting the application, verify services are running:

```bash
# Check if ports are listening
# Windows:
netstat -ano | findstr "38421 45231 53847 62194"

# Linux/macOS:
lsof -i :38421,45231,53847,62194
```

### Test Endpoints

```bash
# Transcription service
curl http://localhost:38421/health

# LLM service
curl http://localhost:45231/health

# RAG service
curl http://localhost:53847/health

# API server
curl http://localhost:62194/api/v1/health
```

All should return `{"status": "ok"}`.

---

## Next Steps

1. **Read User Guide**: See `docs/USER_GUIDE.md` for how to use the application
2. **Try Recording**: Start a test recording to verify everything works
3. **Configure Hotkeys**: Set up global hotkeys in Settings
4. **Connect Calendar**: Optional calendar integration for meeting prep
5. **Generate API Key**: If using external integrations

---

## Getting Help

- **Documentation**: See `docs/` directory
- **Issues**: Report bugs on [GitHub Issues](https://github.com/pbulbule13/meetingrecorder/issues)
- **Logs**: Check `logs/` directory for error messages

---

## Upgrading

### From Previous Version
```bash
# Pull latest changes
git pull origin main

# Update dependencies
npm install
pip install -r requirements.txt

# Restart application
npm run dev
```

### Database Migrations
Automatic migrations are handled on startup. Your data is preserved.

---

## Uninstalling

### Remove Application
```bash
# Windows:
npm run build:win
# Then uninstall via Control Panel

# macOS:
# Drag application from Applications folder to Trash

# Linux:
sudo dpkg -r nexus-assistant
```

### Remove Data
```bash
# WARNING: This deletes all meetings and data!
rm -rf data/ logs/ chroma_data/
```

### Remove Configuration
```bash
rm .env
```

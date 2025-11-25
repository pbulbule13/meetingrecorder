# Nexus Meeting Recorder - Quick Start Guide

This guide will get you up and running with full functionality in 5 minutes.

---

## Current Status of Your Setup

Based on the service logs, here's what's working and what needs setup:

| Feature | Status | What's Needed |
|---------|--------|---------------|
| Overlay UI | Works | Nothing - ready to use |
| Microphone Capture | Works | PyAudio installed |
| Live Transcription | Not Working | Install `openai` package + API key |
| Meeting Summary | Not Working | Install `openai` package + API key |
| AI Suggestions | Not Working | Need LLM provider configured |
| Knowledge Base (RAG) | Not Working | Install `chromadb` + `sentence-transformers` |

---

## Step 1: Install Required Python Packages

Open a terminal in the project folder and run:

```cmd
cd C:\Users\pbkap\Documents\euron\Projects\meetingrecorder

# Activate virtual environment
venv\Scripts\activate

# Install transcription packages (choose one or more)
pip install openai           # For OpenAI Whisper (recommended - you have API key)

# Install LLM packages (for summaries and suggestions)
pip install google-generativeai   # For Gemini (you have API key)

# Install RAG packages (for knowledge base)
pip install chromadb sentence-transformers
```

### Minimum Installation (Just Transcription + Summary)
```cmd
pip install openai google-generativeai
```

### Full Installation (All Features)
```cmd
pip install openai google-generativeai chromadb sentence-transformers
```

---

## Step 2: Verify Your API Keys

Your `.env` file already has these keys configured:

| Provider | API Key | Status |
|----------|---------|--------|
| OpenAI | `sk-proj-5IuS...` | ✓ Set (for transcription) |
| Gemini | `AIzaSyBV...` | ✓ Set (for LLM/summaries) |
| Groq | `gsk_rLfH...` | ✓ Set (fast fallback) |
| Deepgram | Empty | Not configured |
| AssemblyAI | Empty | Not configured |
| Anthropic | Empty | Not configured |

**You're good!** OpenAI + Gemini is enough for full functionality.

---

## Step 3: Start the Services

### Option A: Use the Batch File (Recommended)
```cmd
start_services.bat
```

### Option B: Start Manually
Open 3 separate terminals:

**Terminal 1 - Transcription Service:**
```cmd
cd C:\Users\pbkap\Documents\euron\Projects\meetingrecorder
venv\Scripts\activate
python src/python/transcription_service.py
```

**Terminal 2 - LLM Service:**
```cmd
cd C:\Users\pbkap\Documents\euron\Projects\meetingrecorder
venv\Scripts\activate
python src/python/llm_service.py
```

**Terminal 3 - RAG Service:**
```cmd
cd C:\Users\pbkap\Documents\euron\Projects\meetingrecorder
venv\Scripts\activate
python src/python/rag_service.py
```

---

## Step 4: Launch the Overlay UI

```cmd
cd C:\Users\pbkap\Documents\euron\Projects\meetingrecorder
venv\Scripts\activate
python src/python/overlay_ui.py
```

---

## What Each Component Does

### Overlay UI (`overlay_ui.py`)
- Dark-themed window that floats on top of other windows
- Click "Start Recording" to capture microphone audio
- Shows live transcript with speaker colors
- Click "Summary" after recording to generate meeting summary
- Shows AI suggestions when questions are detected

### Transcription Service (Port 38421)
- Converts your voice to text
- Needs: `openai` package + OPENAI_API_KEY
- Alternative: `deepgram` or `assemblyai` packages

### LLM Service (Port 45231)
- Generates summaries, extracts action items, answers questions
- Needs: `google-generativeai` package + GEMINI_API_KEY
- Alternative: `openai` or `anthropic` packages

### RAG Service (Port 53847)
- Stores meeting knowledge for search
- Needs: `chromadb` + `sentence-transformers` packages
- This is optional - app works without it

---

## Feature Matrix

| Feature | Required Packages | Required API Keys |
|---------|------------------|-------------------|
| **Live Transcription** | `openai` | OPENAI_API_KEY |
| **Meeting Summary** | `google-generativeai` | GEMINI_API_KEY |
| **Action Item Extraction** | `google-generativeai` | GEMINI_API_KEY |
| **AI Suggestions** | `google-generativeai` | GEMINI_API_KEY |
| **Knowledge Base Search** | `chromadb`, `sentence-transformers` | None |
| **Web Search Grounding** | None | GOOGLE_SEARCH_API_KEY |

---

## Troubleshooting

### "No audio device found"
- Make sure your microphone is connected
- Check Windows Sound Settings > Input devices
- Try a different microphone

### "Services offline" in footer
- Make sure all 3 services are running
- Check if ports 38421, 45231, 53847 are in use
- Run: `netstat -ano | findstr ":38421 :45231 :53847"`

### "Transcription not working"
1. Check if `openai` package is installed: `pip show openai`
2. Check if OPENAI_API_KEY is set in `.env`
3. Check transcription service logs for errors

### "Summary button disabled"
- You need to record something first
- Click "Start Recording", speak, then "Stop Recording"
- The "Summary" button activates after recording

### Services crash on startup
Kill existing processes and restart:
```cmd
taskkill /F /IM python.exe
start_services.bat
```

---

## Service Health Check

Test if services are running:

```cmd
curl http://127.0.0.1:38421/health
curl http://127.0.0.1:45231/health
curl http://127.0.0.1:53847/health
```

Expected response (shows which providers are available):
```json
{"status":"ok","providers":{"deepgram":false,"assemblyai":false,"openai":true,"local_whisper":false}}
```

---

## Quick Test Workflow

1. **Start services**: `start_services.bat`
2. **Wait 10 seconds** for services to initialize
3. **Launch UI**: `python src/python/overlay_ui.py`
4. **Check footer** - should say "All services online" (green)
5. **Click "Start Recording"**
6. **Speak into microphone** for 10-15 seconds
7. **Click "Stop Recording"**
8. **Click "Summary"** - a popup with meeting summary appears

---

## Files You Need to Know

| File | Purpose |
|------|---------|
| `src/python/overlay_ui.py` | The main UI application |
| `src/python/transcription_service.py` | Speech-to-text service |
| `src/python/llm_service.py` | AI summarization service |
| `src/python/rag_service.py` | Knowledge base service |
| `.env` | Your API keys and settings |
| `start_services.bat` | Starts all backend services |
| `logs/` | Log files for debugging |

---

## Next Steps After Setup

1. **Configure more API keys** in `.env` for redundancy
2. **Install Ollama** for offline LLM fallback
3. **Set up calendar integration** for meeting prep features
4. **Explore the REST API** at http://localhost:62194/docs

---

*Last Updated: 2025-11-24*

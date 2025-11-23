# Quick Start Guide

## Running the Python Services

Since the full Electron frontend is not yet implemented, use this script to start just the Python backend services:

### **Windows**
```cmd
start_services.bat
```

This will:
1. ✅ Check Python installation
2. ✅ Create/activate virtual environment
3. ✅ Install dependencies automatically
4. ✅ Start all 3 services in separate windows
5. ✅ Show you the service URLs

### **What Gets Started**

Three service windows will open:

1. **Transcription Service** - Port 38421
   - Speech-to-text with speaker diarization
   - Multi-provider support (Deepgram, AssemblyAI, Whisper)

2. **LLM Service** - Port 45231
   - Multi-LLM orchestration
   - Automatic fallback (Gemini → GPT-4 → Claude → Groq)

3. **RAG Service** - Port 53847
   - Knowledge base with ChromaDB
   - Semantic search and meeting preparation

### **Testing Services**

After services start, test them with:

```cmd
curl http://127.0.0.1:38421/health
curl http://127.0.0.1:45231/health
curl http://127.0.0.1:53847/health
```

Or open in browser:
- http://127.0.0.1:38421/docs (Transcription API docs)
- http://127.0.0.1:45231/docs (LLM API docs)
- http://127.0.0.1:53847/docs (RAG API docs)

### **Configuration**

Before first run, edit `.env` file and add at least one API key:

**For Speech-to-Text** (choose one):
```
DEEPGRAM_API_KEY=your_key_here
ASSEMBLYAI_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
```

**For LLM** (choose one):
```
GEMINI_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
GROQ_API_KEY=your_key_here
```

### **Stopping Services**

Simply close each service window, or press Ctrl+C in each window.

---

## Using the Services

### Example: Transcribe Audio

```bash
curl -X POST http://127.0.0.1:38421/transcribe/file \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "path/to/audio.wav",
    "meeting_id": "test-meeting",
    "enable_diarization": true,
    "language": "en"
  }'
```

### Example: Ask a Question (LLM)

```bash
curl -X POST http://127.0.0.1:45231/complete \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Explain quantum computing",
    "task_type": "general",
    "temperature": 0.7
  }'
```

### Example: Query Knowledge Base

```bash
curl -X POST http://127.0.0.1:53847/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What was discussed about databases?",
    "top_k": 5
  }'
```

---

## Logs

All activity is logged to `logs/` directory:

- `logs/transcription.log` - Transcription service logs
- `logs/llm.log` - LLM service logs
- `logs/rag.log` - RAG service logs
- `logs/activity.log` - Combined activity log
- `logs/*_errors.log` - Error logs for each service

---

## Troubleshooting

### Services Won't Start

1. **Check Python**: Make sure Python 3.11+ is installed
   ```cmd
   python --version
   ```

2. **Check Dependencies**: Reinstall if needed
   ```cmd
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Port Already in Use**: Kill existing processes
   ```cmd
   netstat -ano | findstr "38421 45231 53847"
   taskkill /PID <process_id> /F
   ```

### Service Shows Errors

1. **Check `.env` file**: Make sure it exists and has API keys
2. **Check logs**: Look in `logs/*_errors.log` for details
3. **Check API keys**: Verify they're valid and not expired

### Dependencies Won't Install

If `pip install -r requirements.txt` fails:

1. **Update pip**:
   ```cmd
   python -m pip install --upgrade pip
   ```

2. **Install individually**: Some packages may need manual installation
   ```cmd
   pip install fastapi uvicorn loguru
   ```

---

## Full Documentation

For complete documentation, see:

- `README.md` - Main project overview
- `docs/ARCHITECTURE.md` - System architecture
- `docs/API_REFERENCE.md` - Complete API documentation
- `docs/SETUP_GUIDE.md` - Detailed setup instructions
- `TEST_RESULTS.md` - Testing verification
- `CHANGELOG.md` - Version history

---

## Next Steps

1. ✅ Start services with `start_services.bat`
2. ✅ Configure API keys in `.env`
3. ✅ Test health endpoints
4. ✅ Try the example API calls above
5. ✅ Check `docs/API_REFERENCE.md` for more endpoints
6. ✅ Build the frontend (future step)

---

**For the Full Electron App**: Once the frontend is built, use `run.bat` instead.

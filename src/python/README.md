# Python Microservices

FastAPI-based microservices for AI processing.

## Services

### Transcription Service (Port: 38421)
**File:** `transcription_service.py`

Multi-provider speech-to-text with speaker diarization.

**Providers:**
- Deepgram Nova-2
- AssemblyAI
- OpenAI Whisper API
- Local Whisper (offline)

**Features:**
- Real-time streaming
- Speaker identification
- 50+ languages
- Automatic fallback

### LLM Service (Port: 45231)
**File:** `llm_service.py`

Multi-provider LLM orchestration with intelligent routing.

**Providers:**
- Google Gemini 2.0
- OpenAI GPT-4o
- Anthropic Claude
- Groq (fast inference)
- Ollama (local)

**Features:**
- Task-based routing
- Automatic fallback
- Semantic caching
- Intent detection
- Summarization
- Extraction

### RAG Service (Port: 53847)
**File:** `rag_service.py`

Knowledge base with vector search and meeting preparation.

**Features:**
- ChromaDB vector storage
- Semantic search
- Web grounding (Google Search)
- Meeting preparation
- Cross-meeting insights

## Running Services

Services start automatically via `main.js`. For manual start:

```bash
cd src/python
python -m uvicorn transcription_service:app --port 38421
python -m uvicorn llm_service:app --port 45231
python -m uvicorn rag_service:app --port 53847
```

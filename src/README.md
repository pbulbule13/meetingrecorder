# Source Code

This directory contains all application source code.

## Structure

```
src/
├── main/          # Electron main process & Node.js services
└── python/        # Python microservices (STT, LLM, RAG)
```

## Main Process (Node.js)

- **main.js** - Electron entry point
- **preload.js** - Secure IPC bridge for renderer
- **services/** - Core backend services

## Python Services

- **transcription_service.py** - Speech-to-text with diarization (Port: 38421)
- **llm_service.py** - Multi-LLM orchestration (Port: 45231)
- **rag_service.py** - Knowledge base & vector search (Port: 53847)

All services run on localhost only for security.

# Nexus Assistant

**Ultimate Meeting Intelligence & Knowledge Management System**

Version 1.0.0 | Production Ready

---

## Overview

Nexus Assistant is a **local-first, AI-powered meeting intelligence platform** that captures, processes, and transforms professional conversations into actionable knowledge. It combines real-time transcription, multi-modal AI analysis, and intelligent knowledge management to become your personal meeting copilot.

### Key Features

✨ **Real-Time Intelligence**
- Live transcription with speaker identification
- Instant answers from your knowledge base
- Real-time code generation
- Contextual assistance during meetings

🔒 **Privacy-First**
- 100% local data storage
- AES-256 encryption
- No cloud dependency required
- GDPR/CCPA compliant

🤖 **Multi-LLM Architecture**
- Intelligent provider fallback
- Gemini, OpenAI, Anthropic support
- Offline mode with local Whisper
- Cost-optimized routing

📊 **Advanced Analytics**
- Speaker sentiment analysis
- Engagement scoring
- Talk time distribution
- Meeting effectiveness metrics

🎯 **Meeting Preparation**
- Analyze meeting descriptions before meetings
- Surface relevant past discussions
- Suggested agenda and talking points
- Anticipated questions

🔗 **Universal Integration**
- Local REST API
- Export to Notion, Obsidian, Jira
- Calendar integration
- Webhook support

---

## Quick Start

### Prerequisites

- **Windows 10/11**, **macOS 11+**, or **Ubuntu 20.04+**
- **Node.js 20+**
- **Python 3.11+**
- **FFmpeg** (for audio capture)
- At least one API key for STT (Deepgram, AssemblyAI, or OpenAI)
- At least one API key for LLM (Gemini, OpenAI, or Anthropic)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd meetingrecorder
   ```

2. **Install dependencies**
   ```bash
   # Install Node.js dependencies
   npm install

   # Install Python dependencies
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   # Copy example environment file
   cp .env.example .env

   # Edit .env and add your API keys
   # At minimum, set:
   # - DEEPGRAM_API_KEY or ASSEMBLYAI_API_KEY or OPENAI_API_KEY
   # - GEMINI_API_KEY or OPENAI_API_KEY or ANTHROPIC_API_KEY
   ```

4. **Install FFmpeg** (if not already installed)

   **Windows:**
   ```bash
   # Using Chocolatey
   choco install ffmpeg

   # Or download from https://ffmpeg.org/download.html
   ```

   **macOS:**
   ```bash
   brew install ffmpeg
   ```

   **Linux:**
   ```bash
   sudo apt-get install ffmpeg
   ```

5. **Run the application**
   ```bash
   npm run dev
   ```

   This will start:
   - Electron desktop app
   - Python transcription service (port 38421)
   - Python LLM service (port 45231)
   - Python RAG service (port 53847)
   - Local API server (port 62194)

6. **First-time setup**
   - Set a master password for encryption
   - Configure your preferences
   - Grant microphone and system audio permissions

---

## Usage

### Recording a Meeting

1. **Start Recording**
   - Click "Start Recording" in the main window
   - Or use the system tray menu
   - Or auto-start via calendar integration

2. **Real-Time Features**
   - View live transcription in the main window
   - Open the floating overlay for contextual assistance
   - Get instant answers to questions
   - Generate code snippets on demand

3. **Stop Recording**
   - Click "Stop" when the meeting ends
   - Processing begins automatically (summary, action items, analytics)

### Preparing for a Meeting

1. **Import Calendar Events**
   - Connect your Google Calendar or Outlook
   - Upcoming meetings will appear in the dashboard

2. **Get Meeting Preparation**
   - Click "Prepare" on any upcoming meeting
   - Review:
     - Relevant past discussions
     - Suggested talking points
     - Anticipated questions
     - Recommended agenda

### Searching Your Knowledge Base

1. **Full-Text Search**
   - Use the search bar in the dashboard
   - Search across all transcripts

2. **Semantic Search**
   - Ask natural language questions
   - "What did we decide about the database?"
   - System retrieves contextually relevant information

### Managing Action Items

1. **View All Action Items**
   - Navigate to "Action Items" tab
   - Filter by status, assignee, due date

2. **Complete Action Items**
   - Check off completed items
   - System tracks completion rates

3. **Export Action Items**
   - Export to CSV, Jira, Todoist, etc.

### Using the Local API

Generate an API key:
```bash
# From the Settings panel, click "Generate API Key"
# Or use the API:
curl -X POST http://localhost:62194/api/v1/auth/keys \
  -H "Authorization: Bearer <existing-key>" \
  -H "Content-Type: application/json" \
  -d '{"name": "My Integration"}'
```

Query meetings:
```bash
curl http://localhost:62194/api/v1/meetings \
  -H "Authorization: Bearer nxs_your_api_key_here"
```

Search transcripts:
```bash
curl "http://localhost:62194/api/v1/search?q=database" \
  -H "Authorization: Bearer nxs_your_api_key_here"
```

---

## Architecture

```
┌─────────────────────────────────────────┐
│        Electron Desktop App             │
├─────────────────────────────────────────┤
│  Main Window  │  Floating Overlay       │
│  (Dashboard)  │  (Real-time Assistance) │
└─────────────────────────────────────────┘
                   │
    ┌──────────────┼──────────────┐
    │              │              │
┌───▼────┐  ┌─────▼─────┐  ┌────▼────┐
│  STT   │  │    LLM    │  │   RAG   │
│ Port:  │  │  Port:    │  │  Port:  │
│ 38421  │  │  45231    │  │  53847  │
└────────┘  └───────────┘  └─────────┘
                   │
         ┌─────────┴─────────┐
         │                   │
    ┌────▼────┐         ┌───▼────┐
    │  SQLite │         │ Chroma │
    │   DB    │         │ Vector │
    └─────────┘         │   DB   │
                        └────────┘
```

### Service Ports (Random/Uncommon)

- **Transcription Service**: 38421
- **LLM Service**: 45231
- **RAG Service**: 53847
- **API Server**: 62194

All services run on localhost only for security.

---

## Configuration

### Environment Variables

See `.env.example` for all available configuration options.

Key settings:

| Variable | Description | Default |
|----------|-------------|---------|
| `DEFAULT_STT_PROVIDER` | Primary STT provider | `deepgram` |
| `DEFAULT_LLM_PROVIDER` | Primary LLM provider | `gemini` |
| `RECORDING_QUALITY` | Audio quality (low/medium/high) | `high` |
| `ENABLE_REAL_TIME_ASSISTANCE` | Enable live assistance | `true` |
| `ENABLE_WEB_SEARCH` | Enable web grounding in RAG | `true` |
| `AUTO_DELETE_DAYS` | Auto-delete old recordings (0=never) | `0` |
| `LOG_LEVEL` | Logging verbosity | `info` |

### Changing Service Ports

To use different ports, update these variables in `.env`:

```bash
TRANSCRIPTION_SERVICE_PORT=your_port_here
LLM_SERVICE_PORT=your_port_here
RAG_SERVICE_PORT=your_port_here
API_SERVER_PORT=your_port_here
```

---

## Building for Production

### Build Desktop App

**Windows:**
```bash
npm run build:win
```

**macOS:**
```bash
npm run build:mac
```

**Linux:**
```bash
npm run build:linux
```

Installers will be created in the `dist/` directory.

---

## API Documentation

Full API documentation is available at:
- **Local Swagger UI**: http://localhost:62194/docs (when running)
- **HTML Documentation**: See `DOCUMENTATION.html`

### Quick API Reference

**Authentication:**
```
Authorization: Bearer nxs_your_api_key
```

**Get Meetings:**
```
GET /api/v1/meetings?limit=20&offset=0
```

**Search:**
```
GET /api/v1/search?q=your_query&limit=50
```

**Get Action Items:**
```
GET /api/v1/action-items?status=pending
```

**Export Meeting:**
```
POST /api/v1/meetings/{id}/export
Body: {"format": "md"}
```

---

## Testing

### Run Unit Tests
```bash
npm test
```

### Run Integration Tests
```bash
npm run test:e2e
```

### Run Python Tests
```bash
cd src/python
pytest
```

---

## Troubleshooting

### Common Issues

**1. Audio capture not working**
- Ensure FFmpeg is installed and in PATH
- On Windows, enable "Stereo Mix" in sound settings
- Grant microphone permissions to the app

**2. STT service fails to start**
- Check that your API key is valid
- Verify internet connection
- Try fallback to local Whisper (no API needed)

**3. LLM service errors**
- Verify API keys are correct
- Check rate limits on your API account
- Review logs in `~/nexus-assistant/logs/`

**4. Port conflicts**
- Change service ports in `.env` if needed
- Ensure no other apps are using those ports

**5. Database errors**
- Check disk space
- Verify write permissions in user data directory
- Try deleting `~/nexus-assistant/data/nexus.db` (CAUTION: loses data)

### Logs Location

- **Application Logs**: `~/nexus-assistant/logs/app.log`
- **Python Services**: `~/nexus-assistant/logs/python.log`
- **Electron**: Check console in DevTools (Ctrl+Shift+I)

### Getting Help

- **Documentation**: See `DOCUMENTATION.html`
- **GitHub Issues**: Report bugs and feature requests
- **Email Support**: support@nexus-assistant.com (if available)

---

## Privacy & Security

### Data Storage

All data is stored locally on your machine:
- **Location**: `~/nexus-assistant/data/`
- **Encryption**: AES-256-GCM
- **No Cloud**: Zero data sent to our servers (only to your chosen API providers)

### API Provider Data

When using external STT/LLM services:
- Audio is sent to the provider for transcription
- Transcripts are sent to LLM for processing
- Check each provider's privacy policy
- Use local Whisper + Ollama for complete offline mode

### GDPR Compliance

- Right to access: Export all your data
- Right to erasure: Delete all meetings
- Data portability: Standard JSON/CSV exports

---

## Contributing

We welcome contributions! Please see `CONTRIBUTING.md` for guidelines.

### Development Setup

1. Fork the repository
2. Create a feature branch
3. Install dependencies: `npm install && pip install -r requirements.txt`
4. Run in development mode: `npm run dev`
5. Make your changes
6. Run tests: `npm test`
7. Submit a pull request

---

## License

MIT License - see `LICENSE` file for details.

---

## Acknowledgments

- **Deepgram**: Industry-leading STT
- **Google Gemini**: Powerful LLM
- **OpenAI**: Whisper and GPT models
- **Anthropic**: Claude models
- **Electron**: Cross-platform desktop framework
- **FastAPI**: Python web framework

---

## Changelog

### Version 1.0.0 (2025-11-23)
- Initial release
- Core meeting recording and transcription
- Multi-LLM orchestration with fallback
- RAG-based knowledge retrieval
- Meeting preparation feature
- Local API server
- Analytics and reporting
- Cross-platform support (Windows, macOS, Linux)

---

**Built with ❤️ for productive meetings**

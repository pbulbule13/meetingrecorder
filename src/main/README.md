# Main Process & Services

Electron main process and Node.js backend services.

## Files

- **main.js** - Application entry point, window management, service orchestration
- **preload.js** - Context bridge for secure renderer IPC

## Services

### Audio Capture (`services/audio-capture.js`)
Cross-platform audio recording using FFmpeg.

### Database (`services/database.js`)
SQLite database with full-text search, encryption support.

### Session Manager (`services/session-manager.js`)
Orchestrates recording sessions, coordinates all services.

### API Server (`services/api-server.js`)
REST API for external integrations (Port: 62194).

## Testing

Tests are located in `services/__tests__/`.

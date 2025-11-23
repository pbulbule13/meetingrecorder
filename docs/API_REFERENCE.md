# API Reference

Complete reference for all REST APIs and Python microservices.

## Table of Contents
- [API Server (External Integrations)](#api-server)
- [Transcription Service](#transcription-service)
- [LLM Service](#llm-service)
- [RAG Service](#rag-service)

---

## API Server

**Base URL**: `http://localhost:62194/api/v1`

**Authentication**: Bearer token in `Authorization` header

```bash
Authorization: Bearer nxs_your_api_key_here
```

### Authentication Endpoints

#### Generate API Key
```http
POST /api/v1/auth/generate-key
Content-Type: application/json

{
  "name": "My Integration",
  "scopes": ["read", "write"]
}
```

**Response**:
```json
{
  "api_key": "nxs_1a2b3c4d5e6f7g8h9i0j",
  "name": "My Integration",
  "created_at": "2025-11-23T10:30:00Z"
}
```

### Meeting Endpoints

#### List Meetings
```http
GET /api/v1/meetings?limit=50&offset=0&status=completed
```

**Query Parameters**:
- `limit` (number, default: 50): Number of meetings to return
- `offset` (number, default: 0): Pagination offset
- `status` (string): Filter by status (recording|completed|failed)

**Response**:
```json
{
  "meetings": [
    {
      "meeting_id": "uuid",
      "title": "Weekly Standup",
      "start_time": "2025-11-23T10:00:00Z",
      "end_time": "2025-11-23T10:30:00Z",
      "status": "completed",
      "duration_ms": 1800000,
      "participant_count": 5,
      "transcript_length": 15000
    }
  ],
  "total": 100,
  "limit": 50,
  "offset": 0
}
```

#### Get Meeting Details
```http
GET /api/v1/meetings/{meeting_id}
```

**Response**:
```json
{
  "meeting_id": "uuid",
  "title": "Weekly Standup",
  "start_time": "2025-11-23T10:00:00Z",
  "end_time": "2025-11-23T10:30:00Z",
  "status": "completed",
  "summary": "Team discussed progress on Q4 features...",
  "participants": [
    {
      "participant_id": "uuid",
      "name": "John Doe",
      "speaking_time_ms": 300000,
      "turns": 15
    }
  ],
  "transcripts": [
    {
      "segment_id": "uuid",
      "speaker": "Speaker 1",
      "text": "Good morning everyone",
      "start_ms": 0,
      "end_ms": 2500,
      "confidence": 0.95
    }
  ],
  "action_items": [
    {
      "item_id": "uuid",
      "description": "Finish feature X by Friday",
      "assignee": "John Doe",
      "due_date": "2025-11-27",
      "status": "pending"
    }
  ],
  "decisions": [
    {
      "decision_id": "uuid",
      "text": "We will use PostgreSQL for the new service",
      "context": "Discussed during architecture review",
      "timestamp_ms": 450000
    }
  ]
}
```

### Search Endpoints

#### Search Transcripts
```http
GET /api/v1/search?q=database&limit=20
```

**Query Parameters**:
- `q` (string, required): Search query
- `limit` (number, default: 20): Max results
- `meeting_id` (string): Limit to specific meeting
- `speaker` (string): Filter by speaker name

**Response**:
```json
{
  "results": [
    {
      "meeting_id": "uuid",
      "meeting_title": "Architecture Review",
      "segment_id": "uuid",
      "speaker": "Speaker 1",
      "text": "We should use PostgreSQL as our database",
      "timestamp_ms": 450000,
      "relevance_score": 0.89,
      "context_before": "...",
      "context_after": "..."
    }
  ],
  "total": 5,
  "query": "database"
}
```

### Action Item Endpoints

#### List Action Items
```http
GET /api/v1/action-items?status=pending&assignee=John
```

**Query Parameters**:
- `status` (string): pending|completed|cancelled
- `assignee` (string): Filter by assignee name
- `due_after` (date): Items due after date
- `due_before` (date): Items due before date

**Response**:
```json
{
  "action_items": [
    {
      "item_id": "uuid",
      "meeting_id": "uuid",
      "meeting_title": "Sprint Planning",
      "description": "Implement user authentication",
      "assignee": "John Doe",
      "due_date": "2025-11-30",
      "priority": "high",
      "status": "pending",
      "created_at": "2025-11-23T10:00:00Z"
    }
  ],
  "total": 15
}
```

#### Update Action Item
```http
PATCH /api/v1/action-items/{item_id}
Content-Type: application/json

{
  "status": "completed",
  "completion_notes": "Implemented OAuth2 flow"
}
```

### Export Endpoints

#### Export Meeting
```http
GET /api/v1/meetings/{meeting_id}/export?format=markdown
```

**Query Parameters**:
- `format` (string): json|markdown|csv|ical

**Formats**:

**Markdown**:
```markdown
# Meeting: Weekly Standup
**Date**: November 23, 2025
**Duration**: 30 minutes

## Summary
Team discussed progress on Q4 features...

## Participants
- John Doe (15 min speaking time)
- Jane Smith (10 min speaking time)

## Transcript
**Speaker 1** [00:00]: Good morning everyone
**Speaker 2** [00:02]: Good morning

## Action Items
- [ ] Finish feature X by Friday (John Doe)
- [ ] Review pull request #123 (Jane Smith)
```

**JSON**: Complete meeting object (same as GET /meetings/{id})

**CSV**: Transcript segments as CSV
```csv
timestamp,speaker,text,confidence
0,Speaker 1,"Good morning everyone",0.95
2500,Speaker 2,"Good morning",0.92
```

**iCal**: Meeting as calendar event with action items

---

## Transcription Service

**Base URL**: `http://localhost:38421`

### Health Check
```http
GET /health
```

**Response**:
```json
{
  "status": "ok",
  "providers": {
    "deepgram": true,
    "assemblyai": true,
    "openai": true,
    "local_whisper": false
  }
}
```

### Transcribe Stream
```http
POST /transcribe/stream
Content-Type: application/json

{
  "audio_chunk": "base64_encoded_audio_data",
  "session_id": "uuid",
  "chunk_index": 0,
  "language": "en",
  "speaker_profiles": ["speaker1", "speaker2"]
}
```

**Response**:
```json
{
  "segments": [
    {
      "speaker": "Speaker 1",
      "text": "Good morning everyone",
      "start_ms": 0,
      "end_ms": 2500,
      "confidence": 0.95,
      "words": [
        {
          "word": "Good",
          "start": 0,
          "end": 500,
          "confidence": 0.98
        }
      ]
    }
  ],
  "language_detected": "en",
  "processing_time_ms": 1850
}
```

### Transcribe File
```http
POST /transcribe/file
Content-Type: application/json

{
  "file_path": "/path/to/audio.wav",
  "meeting_id": "uuid",
  "enable_diarization": true,
  "num_speakers": 3,
  "language": "en"
}
```

**Response**: Same as `/transcribe/stream`

### WebSocket Streaming
```javascript
const ws = new WebSocket('ws://localhost:38421/transcribe/ws/session-123');

ws.send(base64AudioChunk);

ws.onmessage = (event) => {
  const transcript = JSON.parse(event.data);
  console.log(transcript.segments);
};
```

---

## LLM Service

**Base URL**: `http://localhost:45231`

### Health Check
```http
GET /health
```

**Response**:
```json
{
  "status": "ok",
  "providers": {
    "gemini": true,
    "openai": true,
    "anthropic": true,
    "groq": true,
    "ollama": false
  },
  "cache_stats": {
    "size": 150,
    "hit_rate": 0.45
  }
}
```

### Complete
```http
POST /complete
Content-Type: application/json

{
  "prompt": "Explain quantum computing in simple terms",
  "task_type": "general",
  "temperature": 0.7,
  "max_tokens": 500,
  "use_cache": true
}
```

**Task Types**:
- `general`: General-purpose completion
- `intent_detection`: Fast intent classification
- `summarization`: Meeting summarization
- `code_generation`: Code generation
- `question_answering`: Contextual Q&A

**Response**:
```json
{
  "text": "Quantum computing is a type of computing...",
  "provider": "gemini",
  "model": "gemini-2.0-flash-exp",
  "tokens_used": 450,
  "processing_time_ms": 2100,
  "cached": false,
  "fallback_used": false
}
```

### Summarize
```http
POST /summarize
Content-Type: application/json

{
  "transcript": "Full meeting transcript...",
  "meeting_title": "Sprint Planning",
  "participants": ["John", "Jane"],
  "duration_minutes": 60
}
```

**Response**:
```json
{
  "text": "The team discussed Q4 priorities...",
  "provider": "gemini",
  "model": "gemini-2.0-flash-exp",
  "tokens_used": 850,
  "processing_time_ms": 3200
}
```

### Extract Action Items
```http
POST /extract-action-items
Content-Type: application/json

{
  "transcript": "Full meeting transcript...",
  "participants": ["John", "Jane"]
}
```

**Response**:
```json
{
  "text": "[Action items extracted as JSON array]",
  "provider": "gemini",
  "action_items": [
    {
      "description": "Implement user authentication",
      "assignee": "John",
      "due_date": "2025-11-30",
      "priority": "high"
    }
  ]
}
```

### Answer Question
```http
POST /answer-question
Content-Type: application/json

{
  "question": "What was decided about the database?",
  "context": "Relevant transcript segments or RAG results...",
  "meeting_id": "uuid"
}
```

**Response**:
```json
{
  "text": "The team decided to use PostgreSQL...",
  "provider": "gemini",
  "confidence": 0.89,
  "sources": ["segment-123", "segment-456"]
}
```

### Detect Intent
```http
POST /detect-intent
Content-Type: application/json

{
  "text": "Can someone explain how authentication works?",
  "context": "Previous conversation context..."
}
```

**Response**:
```json
{
  "text": "{\"intent\": \"question\", \"confidence\": 0.92}",
  "provider": "gemini",
  "intent": "question",
  "confidence": 0.92
}
```

**Intent Types**:
- `question`: User asking a question
- `code_request`: Requesting code snippet
- `decision`: Making a decision
- `action_item`: Creating action item
- `general`: General statement

---

## RAG Service

**Base URL**: `http://localhost:53847`

### Health Check
```http
GET /health
```

**Response**:
```json
{
  "status": "ok",
  "services": {
    "chromadb": true,
    "embeddings": true,
    "web_search": true
  }
}
```

### Query Knowledge Base
```http
POST /query
Content-Type: application/json

{
  "question": "What database did we decide to use?",
  "filters": {
    "exclude_meeting_id": "current-meeting-uuid",
    "date_range": {
      "start": "2025-11-01",
      "end": "2025-11-23"
    }
  },
  "top_k": 5,
  "use_web_search": false
}
```

**Response**:
```json
{
  "answer": "Based on previous meetings, you decided to use PostgreSQL...",
  "sources": [
    {
      "meeting_id": "uuid",
      "meeting_title": "Architecture Review",
      "date": "2025-11-15",
      "excerpt": "We will use PostgreSQL for better transaction support...",
      "relevance_score": 0.89
    }
  ],
  "web_sources": [],
  "confidence": 0.89
}
```

### Index Meeting
```http
POST /index/meeting
Content-Type: application/json

{
  "meeting_id": "uuid",
  "transcript": "Full meeting transcript...",
  "summary": "Meeting summary...",
  "metadata": {
    "title": "Sprint Planning",
    "date": "2025-11-23",
    "participants": ["John", "Jane"]
  }
}
```

**Response**:
```json
{
  "status": "indexed",
  "embedding_count": 45,
  "processing_time_ms": 4500
}
```

### Prepare Meeting
```http
POST /prepare-meeting
Content-Type: application/json

{
  "meeting_title": "Architecture Review",
  "meeting_description": "Discuss database selection for new service",
  "participants": ["John", "Jane", "Bob"],
  "scheduled_time": "2025-11-25T14:00:00Z",
  "duration_minutes": 60
}
```

**Response**:
```json
{
  "summary": "Upcoming meeting: Architecture Review\nScheduled for: 2025-11-25...",
  "key_topics": ["database", "selection", "service", "architecture"],
  "relevant_history": [
    {
      "meeting_title": "Database Discussion",
      "date": "2025-11-15",
      "excerpt": "Discussed PostgreSQL vs MySQL...",
      "relevance": 0.87
    }
  ],
  "suggested_agenda": [
    "Welcome and introductions (2 min)",
    "Review previous action items (5 min)",
    "Main discussion: Architecture Review (45 min)",
    "Action items and next steps (5 min)",
    "Wrap-up (3 min)"
  ],
  "talking_points": [
    "Reference previous discussion from 2025-11-15",
    "Build on decisions made in last meeting",
    "Clarify objectives and desired outcomes",
    "Assign clear action items with owners"
  ],
  "potential_questions": [
    "What are the key challenges we need to address?",
    "What resources do we need?",
    "What are the success criteria?"
  ]
}
```

### Delete Meeting
```http
DELETE /meeting/{meeting_id}
```

**Response**:
```json
{
  "status": "deleted",
  "meeting_id": "uuid"
}
```

---

## Error Responses

All services return errors in this format:

```json
{
  "detail": "Error message describing what went wrong",
  "error_code": "TRANSCRIPTION_FAILED",
  "timestamp": "2025-11-23T10:30:00Z"
}
```

### Common HTTP Status Codes
- `200`: Success
- `400`: Bad Request (invalid input)
- `401`: Unauthorized (invalid API key)
- `404`: Not Found
- `429`: Too Many Requests (rate limit exceeded)
- `500`: Internal Server Error
- `503`: Service Unavailable (provider down)

---

## Rate Limits

### API Server
- 100 requests per minute per API key
- Burst: Up to 10 requests per second

### Python Services
- No rate limits (localhost only)
- Concurrent request limit: 10 per service

---

## Webhooks (Future Feature)

Coming soon: Webhook support for event notifications.

**Planned Events**:
- `meeting.started`
- `meeting.completed`
- `action_item.created`
- `action_item.completed`
- `transcript.updated`

# Nexus Assistant - Technical Architecture Document

**Version:** 1.0
**Last Updated:** November 23, 2025
**Status:** Production Ready

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Diagrams](#architecture-diagrams)
3. [Component Specifications](#component-specifications)
4. [Data Models](#data-models)
5. [API Specifications](#api-specifications)
6. [Security Architecture](#security-architecture)
7. [Deployment Strategy](#deployment-strategy)

---

## 1. System Overview

### 1.1 High-Level Architecture

```mermaid
graph TB
    subgraph "User Interface Layer"
        A[Main Dashboard<br/>React + Electron]
        B[Floating Overlay<br/>Real-time Assistance]
        C[Settings Panel]
    end

    subgraph "Application Core"
        D[Audio Capture Service<br/>Node.js Native Modules]
        E[Transcription Orchestrator<br/>Python FastAPI]
        F[LLM Orchestration Engine<br/>Multi-Provider Support]
        G[RAG Engine<br/>Vector Search + Retrieval]
        H[Analytics Processor<br/>Statistical Analysis]
        I[Local API Server<br/>Express.js REST API]
    end

    subgraph "Data Layer"
        J[(SQLite DB<br/>Metadata & Config)]
        K[(ChromaDB<br/>Vector Embeddings)]
        L[File Storage<br/>Encrypted Transcripts]
        M[Search Index<br/>Full-Text Search)]
    end

    subgraph "External Services"
        N[STT API<br/>Whisper/Deepgram/AssemblyAI]
        O[LLM Providers<br/>Gemini/OpenAI/Anthropic]
        P[Google Search API]
        Q[Calendar APIs<br/>Google/Outlook]
    end

    A --> D
    A --> I
    B --> G
    B --> F
    D --> E
    E --> N
    E --> F
    F --> O
    G --> K
    G --> P
    F --> J
    H --> J
    I --> J
    I --> K
    E --> L
    E --> M
    I --> Q

    style A fill:#4A90E2
    style B fill:#4A90E2
    style D fill:#50C878
    style E fill:#50C878
    style F fill:#50C878
    style G fill:#50C878
    style J fill:#FFB84D
    style K fill:#FFB84D
    style N fill:#E57373
    style O fill:#E57373
```

### 1.2 Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | React 18 + TypeScript | UI components and state management |
| **Desktop** | Electron 28 | Cross-platform desktop wrapper |
| **Backend** | Node.js 20 + Python 3.11 | Application logic and processing |
| **API Layer** | Express.js + FastAPI | REST API and microservices |
| **Database** | SQLite 3.45 | Relational data storage |
| **Vector DB** | ChromaDB 0.4 | Semantic search and embeddings |
| **Search** | Fuse.js + SQLite FTS5 | Full-text search |
| **Audio** | NAudio (Win) / CoreAudio (Mac) | Audio capture and processing |
| **STT** | OpenAI Whisper / Deepgram | Speech-to-text conversion |
| **LLM** | Gemini 2.5 / GPT-4o | Language model processing |
| **Encryption** | AES-256-GCM | Data encryption at rest |

---

## 2. Architecture Diagrams

### 2.1 Audio Processing Pipeline

```mermaid
sequenceDiagram
    participant User
    participant AudioCapture
    participant Buffer
    participant STT
    participant Transcription
    participant DB

    User->>AudioCapture: Start Meeting
    activate AudioCapture

    loop Every 5 seconds
        AudioCapture->>Buffer: Capture Audio Chunk
        Buffer->>STT: Send Audio Data
        STT->>STT: Process Speech-to-Text
        STT-->>Transcription: Return Transcript Segment
        Transcription->>Transcription: Add Speaker Labels
        Transcription->>Transcription: Add Timestamps
        Transcription->>DB: Save Segment
        Transcription-->>User: Display Live Transcript
    end

    User->>AudioCapture: Stop Meeting
    deactivate AudioCapture
    AudioCapture->>Transcription: Finalize Transcript
    Transcription->>DB: Save Complete Meeting
```

### 2.2 Multi-LLM Fallback Strategy

```mermaid
flowchart TD
    A[User Question Detected] --> B{Primary LLM Available?}
    B -->|Yes| C[Gemini 2.5 Flash]
    B -->|No| D{Secondary LLM Available?}

    C --> E{Response in <5s?}
    E -->|Yes| F[Return Answer]
    E -->|No| D

    D -->|Yes| G[Gemini 2.5 Pro / GPT-4o]
    D -->|No| H{Local LLM Available?}

    G --> I{Response in <15s?}
    I -->|Yes| F
    I -->|No| H

    H -->|Yes| J[Llama 3 via Ollama]
    H -->|No| K[Rule-Based Fallback]

    J --> L{Response in <10s?}
    L -->|Yes| F
    L -->|No| K

    K --> M[Extract Keywords<br/>Return Basic Info]
    M --> F

    F --> N[Log Performance Metrics]
    N --> O[Update Model Rankings]

    style C fill:#90EE90
    style G fill:#FFD700
    style J fill:#87CEEB
    style K fill:#FFB6C1
```

### 2.3 RAG (Retrieval-Augmented Generation) Flow

```mermaid
graph LR
    A[User Query] --> B[Query Understanding]
    B --> C[Intent Classification]
    C --> D{Query Type?}

    D -->|Factual| E[Local Knowledge Search]
    D -->|Current Events| F[Web Search API]
    D -->|Personal| E

    E --> G[Vector Similarity Search<br/>ChromaDB]
    G --> H[Retrieve Top 5 Results]

    F --> I[Google Search API]
    I --> J[Extract Relevant Snippets]

    H --> K[Re-Rank Results]
    J --> K

    K --> L[Build Context Window]
    L --> M[LLM Synthesis]

    M --> N[Generate Answer<br/>with Citations]
    N --> O[Return to User]

    O --> P[Store Q&A in Knowledge Base]

    style E fill:#90EE90
    style F fill:#87CEEB
    style M fill:#FFD700
```

### 2.4 Meeting Processing Workflow

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Recording: User Starts Meeting
    Idle --> AutoStart: Calendar Event Detected

    AutoStart --> Recording

    Recording --> LiveTranscription: Audio Chunks
    LiveTranscription --> IntentDetection
    IntentDetection --> ContextualAssistance: Question Detected
    ContextualAssistance --> LiveTranscription: Answer Displayed

    Recording --> Paused: User Pauses
    Paused --> Recording: User Resumes

    Recording --> Processing: Meeting Ends
    Paused --> Processing: Meeting Ends

    Processing --> Summarization
    Summarization --> ActionItemExtraction
    ActionItemExtraction --> HighlightDetection
    HighlightDetection --> AnalyticsCalculation
    AnalyticsCalculation --> VectorEmbedding
    VectorEmbedding --> IndexUpdate
    IndexUpdate --> Complete

    Complete --> [*]

    note right of Recording
        - Capture audio
        - Stream to STT
        - Display live transcript
        - Provide real-time assistance
    end note

    note right of Processing
        - Advanced LLM processing
        - Multi-pass summarization
        - Entity extraction
        - Sentiment analysis
    end note
```

### 2.5 Data Architecture

```mermaid
erDiagram
    MEETINGS ||--o{ TRANSCRIPTS : contains
    MEETINGS ||--o{ SUMMARIES : has
    MEETINGS ||--o{ ACTION_ITEMS : generates
    MEETINGS ||--o{ DECISIONS : records
    MEETINGS ||--o{ HIGHLIGHTS : creates
    MEETINGS ||--o{ ANALYTICS : produces
    MEETINGS }o--o{ PARTICIPANTS : involves
    PARTICIPANTS ||--o{ SPEAKER_ANALYTICS : has
    ACTION_ITEMS }o--|| PARTICIPANTS : assigned_to
    TRANSCRIPTS ||--o{ TRANSCRIPT_SEGMENTS : contains
    MEETINGS ||--o{ EMBEDDINGS : indexed_by

    MEETINGS {
        string meeting_id PK
        string title
        datetime start_time
        datetime end_time
        int duration_seconds
        string recording_path
        string status
        datetime created_at
    }

    TRANSCRIPTS {
        string transcript_id PK
        string meeting_id FK
        text full_text
        string language
        float confidence_avg
        datetime created_at
    }

    TRANSCRIPT_SEGMENTS {
        string segment_id PK
        string transcript_id FK
        string speaker_id FK
        text text
        int start_ms
        int end_ms
        float confidence
        string sentiment
    }

    SUMMARIES {
        string summary_id PK
        string meeting_id FK
        text executive_summary
        json key_topics
        text detailed_summary
        string model_used
        datetime created_at
    }

    ACTION_ITEMS {
        string action_id PK
        string meeting_id FK
        text task
        string assignee_id FK
        date due_date
        string priority
        string status
        int timestamp_ms
    }

    DECISIONS {
        string decision_id PK
        string meeting_id FK
        text decision
        text rationale
        json participants
        int timestamp_ms
    }

    PARTICIPANTS {
        string participant_id PK
        string name
        string email
        string voice_profile_path
        datetime created_at
    }

    SPEAKER_ANALYTICS {
        string analytics_id PK
        string meeting_id FK
        string participant_id FK
        float talk_time_percent
        int word_count
        float avg_sentiment
        int interruption_count
        float speaking_pace_wpm
    }

    ANALYTICS {
        string analytics_id PK
        string meeting_id FK
        int total_words
        float avg_speaking_pace
        int total_interruptions
        json sentiment_timeline
        float engagement_score
    }

    EMBEDDINGS {
        string embedding_id PK
        string meeting_id FK
        string content_type
        vector embedding_vector
        text metadata
    }
```

### 2.6 Component Interaction Diagram

```mermaid
graph TB
    subgraph "Frontend (Electron + React)"
        UI[Main UI Components]
        Overlay[Floating Overlay]
        Store[Redux Store]
    end

    subgraph "IPC Bridge"
        IPC[Electron IPC]
    end

    subgraph "Main Process (Node.js)"
        AudioSvc[Audio Capture Service]
        SessionMgr[Session Manager]
        ConfigMgr[Config Manager]
        APISvr[API Server]
    end

    subgraph "Python Services"
        TransSvc[Transcription Service]
        LLMSvc[LLM Service]
        RAGSvc[RAG Service]
        AnalyticsSvc[Analytics Service]
    end

    subgraph "Storage"
        DB[(SQLite)]
        VectorDB[(ChromaDB)]
        Files[File System]
    end

    UI <--> IPC
    Overlay <--> IPC
    Store <--> UI

    IPC <--> SessionMgr
    IPC <--> APISvr

    SessionMgr --> AudioSvc
    AudioSvc --> TransSvc

    TransSvc --> LLMSvc
    TransSvc --> DB

    LLMSvc --> RAGSvc
    RAGSvc --> VectorDB

    SessionMgr --> AnalyticsSvc
    AnalyticsSvc --> DB

    ConfigMgr --> DB
    APISvr --> DB
    APISvr --> VectorDB

    TransSvc --> Files

    style UI fill:#4A90E2
    style Overlay fill:#4A90E2
    style AudioSvc fill:#50C878
    style TransSvc fill:#9B59B6
    style LLMSvc fill:#9B59B6
    style DB fill:#FFB84D
```

---

## 3. Component Specifications

### 3.1 Audio Capture Service

**Language:** Node.js with Native Addons
**Responsibilities:**
- Capture system audio output (speakers)
- Capture microphone input
- Mix audio streams
- Buffer management
- Format conversion (to 16-bit PCM WAV)

**Key APIs:**
- Windows: WASAPI (Windows Audio Session API)
- macOS: CoreAudio
- Linux: PulseAudio / ALSA

**Configuration:**
```javascript
{
  sampleRate: 16000,
  channels: 1,
  bitDepth: 16,
  bufferSize: 4096,
  encoding: 'pcm',
  mixSources: true,
  autoGainControl: true,
  noiseSuppression: true
}
```

### 3.2 Transcription Orchestrator

**Language:** Python 3.11 (FastAPI microservice)
**Port:** 8765
**Responsibilities:**
- Receive audio chunks from audio service
- Manage STT API connections
- Handle speaker diarization
- Timestamp synchronization
- Real-time transcript streaming

**STT Providers (Priority Order):**
1. **Deepgram Nova-2** (Primary)
   - Best for real-time streaming
   - Speaker diarization built-in
   - Multi-language support

2. **AssemblyAI** (Secondary)
   - Excellent accuracy
   - Strong punctuation and formatting

3. **OpenAI Whisper API** (Tertiary)
   - Batch processing fallback
   - 50+ languages

4. **Local Whisper** (Offline Fallback)
   - Whisper Large v3
   - Runs via faster-whisper
   - No internet required

**API Endpoint:**
```python
POST /transcribe
{
  "audio_chunk": "base64_encoded_audio",
  "session_id": "uuid",
  "chunk_index": 123,
  "final": false
}

Response:
{
  "transcript": "This is the transcribed text",
  "speaker": "Speaker 1",
  "confidence": 0.95,
  "start_time_ms": 123000,
  "end_time_ms": 125500,
  "words": [
    {"word": "This", "start": 123000, "end": 123200, "confidence": 0.98},
    ...
  ]
}
```

### 3.3 LLM Orchestration Engine

**Language:** Python 3.11
**Responsibilities:**
- Route requests to appropriate LLM based on task type
- Implement fallback strategy
- Cache responses
- Track usage and costs
- Rate limiting

**Model Selection Matrix:**

| Task Type | Primary Model | Fallback | Max Tokens |
|-----------|---------------|----------|------------|
| Intent Recognition | Gemini 2.5 Flash | GPT-4o-mini | 500 |
| Quick Q&A | Gemini 2.5 Flash | Llama 3.1 8B | 1000 |
| Code Generation | GPT-4o | Gemini 2.5 Pro | 2000 |
| Summarization | Gemini 2.5 Pro | GPT-4o | 3000 |
| Action Item Extraction | Gemini 2.5 Flash | Claude 3.5 Haiku | 1500 |
| Deep Analysis | GPT-4o | Gemini 2.5 Pro | 4000 |

**Caching Strategy:**
- Semantic cache for similar questions (cosine similarity >0.95)
- Cache TTL: 1 hour for general queries, 5 minutes for time-sensitive
- LRU eviction policy

**Example Code:**
```python
class LLMOrchestrator:
    def __init__(self):
        self.providers = {
            'gemini': GeminiProvider(),
            'openai': OpenAIProvider(),
            'anthropic': AnthropicProvider(),
            'local': OllamaProvider()
        }
        self.cache = SemanticCache()

    async def complete(self, prompt: str, task_type: str) -> LLMResponse:
        # Check cache first
        cached = await self.cache.get(prompt)
        if cached:
            return cached

        # Select model based on task type
        config = self.get_model_config(task_type)

        # Try primary model
        try:
            response = await self.providers[config.primary].complete(
                prompt,
                max_tokens=config.max_tokens,
                timeout=config.timeout
            )
            await self.cache.set(prompt, response)
            return response
        except Exception as e:
            logger.warning(f"Primary model failed: {e}")

            # Fallback to secondary
            return await self.providers[config.fallback].complete(
                prompt,
                max_tokens=config.max_tokens,
                timeout=config.timeout * 2
            )
```

### 3.4 RAG Engine

**Language:** Python 3.11
**Vector Database:** ChromaDB
**Embedding Model:** text-embedding-3-small (OpenAI) or text-embedding-004 (Google)

**Workflow:**
1. **Indexing:**
   - Convert meeting transcripts to embeddings
   - Store in ChromaDB with metadata
   - Update every 5 minutes during meeting
   - Full re-index nightly

2. **Retrieval:**
   - Convert user query to embedding
   - Search ChromaDB for top K=10 results
   - Filter by date range, participants, topics (if specified)
   - Re-rank using cross-encoder model

3. **Augmentation:**
   - Inject retrieved context into LLM prompt
   - Add source citations
   - Include confidence scores

**Example Query:**
```python
# User asks: "What did we decide about the database last week?"

# 1. Generate embedding
query_embedding = embed_text("database decision last week")

# 2. Search with filters
results = chroma_db.query(
    query_embeddings=[query_embedding],
    n_results=10,
    where={
        "$and": [
            {"date": {"$gte": "2025-11-16"}},
            {"content_type": "decision"}
        ]
    }
)

# 3. Build context
context = "\n\n".join([r['text'] for r in results])

# 4. Generate answer
prompt = f"""Based on the following meeting excerpts, answer the question.

Context:
{context}

Question: What did we decide about the database last week?

Answer with citations in the format [Meeting Title, Date].
"""

answer = await llm_orchestrator.complete(prompt, task_type="qa")
```

### 3.5 Analytics Processor

**Language:** Python 3.11
**Libraries:** NumPy, Pandas, Scikit-learn

**Computed Metrics:**

1. **Speaker Metrics:**
   - Talk time % (words spoken / total words)
   - Speaking pace (words per minute)
   - Sentiment score (-1 to 1, using VADER or DistilBERT)
   - Interruption count
   - Question vs. statement ratio

2. **Meeting Metrics:**
   - Total duration
   - Active speaking time vs. silence
   - Number of speakers
   - Topic diversity (using TF-IDF)
   - Engagement score (0-100, composite metric)
   - Decision density (decisions per hour)

3. **Sentiment Timeline:**
   - 30-second rolling window sentiment
   - Identify sentiment shifts
   - Correlate with topics

**Engagement Score Formula:**
```python
def calculate_engagement_score(meeting_data):
    # Factors (normalized 0-1):
    # - Speaker balance (lower Gini coefficient = higher score)
    # - Question frequency (optimal: 5-10 per hour)
    # - Average sentiment (higher = better)
    # - Speaking pace variance (lower = more engaged)

    speaker_balance = 1 - gini_coefficient(talk_times)
    question_score = min(question_count / (duration_hours * 7.5), 1)
    sentiment_score = (avg_sentiment + 1) / 2  # Normalize -1:1 to 0:1
    pace_consistency = 1 - (std_dev(speaking_paces) / mean(speaking_paces))

    weights = [0.3, 0.25, 0.25, 0.2]
    engagement = sum([
        speaker_balance * weights[0],
        question_score * weights[1],
        sentiment_score * weights[2],
        pace_consistency * weights[3]
    ]) * 100

    return round(engagement, 1)
```

### 3.6 Local API Server

**Language:** Node.js (Express)
**Port:** 8080
**Authentication:** API Key (generated locally)

**Endpoints:**

```javascript
// Meetings
GET    /api/v1/meetings
GET    /api/v1/meetings/:id
POST   /api/v1/meetings (manual creation)
DELETE /api/v1/meetings/:id

// Search
GET    /api/v1/search?q=query&type=semantic|fulltext&limit=20

// Transcripts
GET    /api/v1/meetings/:id/transcript
GET    /api/v1/meetings/:id/transcript/segments

// Summaries
GET    /api/v1/meetings/:id/summary
POST   /api/v1/meetings/:id/summary/regenerate

// Action Items
GET    /api/v1/action-items
GET    /api/v1/action-items/:id
PUT    /api/v1/action-items/:id
POST   /api/v1/action-items/:id/complete

// Analytics
GET    /api/v1/meetings/:id/analytics
GET    /api/v1/analytics/dashboard?days=30

// Export
POST   /api/v1/meetings/:id/export (body: {format: 'md'|'json'|'csv'})
GET    /api/v1/export/action-items (CSV of all action items)

// Webhooks
POST   /api/v1/webhooks (register)
GET    /api/v1/webhooks (list)
DELETE /api/v1/webhooks/:id
```

**Example Response:**
```json
GET /api/v1/meetings/abc-123

{
  "id": "abc-123",
  "title": "Q4 Planning Meeting",
  "start_time": "2025-11-23T14:00:00Z",
  "end_time": "2025-11-23T15:30:00Z",
  "duration_seconds": 5400,
  "participants": [
    {
      "id": "p1",
      "name": "John Doe",
      "email": "john@example.com",
      "talk_time_percent": 45.2
    }
  ],
  "summary": {
    "executive_summary": "Discussed Q4 priorities...",
    "key_topics": ["Budget", "Hiring", "Product Launch"]
  },
  "action_items": [
    {
      "id": "ai-1",
      "task": "Update budget spreadsheet",
      "assignee": "John Doe",
      "due_date": "2025-12-01",
      "status": "pending"
    }
  ],
  "analytics": {
    "total_words": 8420,
    "engagement_score": 78.5
  }
}
```

---

## 4. Data Models

### 4.1 SQLite Schema

```sql
-- Meetings table
CREATE TABLE meetings (
    meeting_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    start_time DATETIME NOT NULL,
    end_time DATETIME,
    duration_seconds INTEGER,
    status TEXT CHECK(status IN ('recording', 'processing', 'completed', 'error')),
    recording_path TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Participants table
CREATE TABLE participants (
    participant_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    voice_profile_path TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Meeting participants (junction table)
CREATE TABLE meeting_participants (
    meeting_id TEXT,
    participant_id TEXT,
    role TEXT,
    joined_at DATETIME,
    left_at DATETIME,
    PRIMARY KEY (meeting_id, participant_id),
    FOREIGN KEY (meeting_id) REFERENCES meetings(meeting_id) ON DELETE CASCADE,
    FOREIGN KEY (participant_id) REFERENCES participants(participant_id)
);

-- Transcripts table
CREATE TABLE transcripts (
    transcript_id TEXT PRIMARY KEY,
    meeting_id TEXT NOT NULL,
    full_text TEXT NOT NULL,
    language TEXT DEFAULT 'en',
    confidence_avg REAL,
    word_count INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (meeting_id) REFERENCES meetings(meeting_id) ON DELETE CASCADE
);

-- Transcript segments (for detailed playback)
CREATE TABLE transcript_segments (
    segment_id TEXT PRIMARY KEY,
    transcript_id TEXT NOT NULL,
    speaker_id TEXT,
    text TEXT NOT NULL,
    start_ms INTEGER NOT NULL,
    end_ms INTEGER NOT NULL,
    confidence REAL,
    sentiment REAL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (transcript_id) REFERENCES transcripts(transcript_id) ON DELETE CASCADE,
    FOREIGN KEY (speaker_id) REFERENCES participants(participant_id)
);

-- Full-text search index
CREATE VIRTUAL TABLE transcript_fts USING fts5(
    text,
    speaker_name,
    meeting_title,
    content=transcript_segments,
    content_rowid=rowid
);

-- Summaries table
CREATE TABLE summaries (
    summary_id TEXT PRIMARY KEY,
    meeting_id TEXT NOT NULL,
    executive_summary TEXT,
    key_topics JSON,
    detailed_summary TEXT,
    model_used TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (meeting_id) REFERENCES meetings(meeting_id) ON DELETE CASCADE
);

-- Decisions table
CREATE TABLE decisions (
    decision_id TEXT PRIMARY KEY,
    meeting_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    rationale TEXT,
    participants JSON,
    timestamp_ms INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (meeting_id) REFERENCES meetings(meeting_id) ON DELETE CASCADE
);

-- Action items table
CREATE TABLE action_items (
    action_id TEXT PRIMARY KEY,
    meeting_id TEXT NOT NULL,
    task TEXT NOT NULL,
    assignee_id TEXT,
    due_date DATE,
    priority TEXT CHECK(priority IN ('low', 'medium', 'high', 'critical')),
    status TEXT CHECK(status IN ('pending', 'in_progress', 'completed', 'cancelled')) DEFAULT 'pending',
    timestamp_ms INTEGER,
    completed_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (meeting_id) REFERENCES meetings(meeting_id) ON DELETE CASCADE,
    FOREIGN KEY (assignee_id) REFERENCES participants(participant_id)
);

-- Highlights table
CREATE TABLE highlights (
    highlight_id TEXT PRIMARY KEY,
    meeting_id TEXT NOT NULL,
    text TEXT NOT NULL,
    start_time_ms INTEGER NOT NULL,
    end_time_ms INTEGER NOT NULL,
    importance_score REAL,
    category TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (meeting_id) REFERENCES meetings(meeting_id) ON DELETE CASCADE
);

-- Analytics table
CREATE TABLE meeting_analytics (
    analytics_id TEXT PRIMARY KEY,
    meeting_id TEXT NOT NULL UNIQUE,
    total_words INTEGER,
    avg_speaking_pace REAL,
    total_interruptions INTEGER,
    sentiment_timeline JSON,
    engagement_score REAL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (meeting_id) REFERENCES meetings(meeting_id) ON DELETE CASCADE
);

-- Speaker analytics table
CREATE TABLE speaker_analytics (
    speaker_analytics_id TEXT PRIMARY KEY,
    meeting_id TEXT NOT NULL,
    participant_id TEXT NOT NULL,
    talk_time_percent REAL,
    word_count INTEGER,
    avg_sentiment REAL,
    interruption_count INTEGER,
    speaking_pace_wpm REAL,
    questions_asked INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (meeting_id) REFERENCES meetings(meeting_id) ON DELETE CASCADE,
    FOREIGN KEY (participant_id) REFERENCES participants(participant_id),
    UNIQUE(meeting_id, participant_id)
);

-- Settings/Config table
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value JSON NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- API Keys table (for local API auth)
CREATE TABLE api_keys (
    key_id TEXT PRIMARY KEY,
    key_hash TEXT NOT NULL UNIQUE,
    name TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_used_at DATETIME,
    is_active BOOLEAN DEFAULT 1
);

-- Indexes for performance
CREATE INDEX idx_meetings_start_time ON meetings(start_time);
CREATE INDEX idx_meetings_status ON meetings(status);
CREATE INDEX idx_transcript_segments_meeting ON transcript_segments(transcript_id);
CREATE INDEX idx_transcript_segments_speaker ON transcript_segments(speaker_id);
CREATE INDEX idx_action_items_assignee ON action_items(assignee_id);
CREATE INDEX idx_action_items_status ON action_items(status);
CREATE INDEX idx_action_items_due_date ON action_items(due_date);
```

### 4.2 ChromaDB Collections

```python
# Collection: meeting_transcripts
{
  "collection_name": "meeting_transcripts",
  "metadata": {
    "description": "Vector embeddings of meeting transcripts",
    "embedding_model": "text-embedding-3-small",
    "dimension": 1536
  },
  "documents": [
    {
      "id": "meeting-abc-123-segment-1",
      "embedding": [0.123, -0.456, ...],  # 1536-dim vector
      "document": "Full text of transcript segment",
      "metadata": {
        "meeting_id": "abc-123",
        "meeting_title": "Q4 Planning",
        "speaker": "John Doe",
        "start_time_ms": 123000,
        "date": "2025-11-23",
        "content_type": "transcript"
      }
    }
  ]
}

# Collection: meeting_summaries
{
  "collection_name": "meeting_summaries",
  "metadata": {
    "description": "Vector embeddings of meeting summaries",
    "embedding_model": "text-embedding-3-small"
  },
  "documents": [
    {
      "id": "summary-abc-123",
      "embedding": [...],
      "document": "Executive summary and key points",
      "metadata": {
        "meeting_id": "abc-123",
        "meeting_title": "Q4 Planning",
        "date": "2025-11-23",
        "content_type": "summary",
        "topics": ["budget", "hiring", "product"]
      }
    }
  ]
}

# Collection: decisions
{
  "collection_name": "decisions",
  "metadata": {
    "description": "Vector embeddings of decisions made",
    "embedding_model": "text-embedding-3-small"
  },
  "documents": [
    {
      "id": "decision-xyz-789",
      "embedding": [...],
      "document": "Decision text and rationale",
      "metadata": {
        "meeting_id": "abc-123",
        "date": "2025-11-23",
        "content_type": "decision"
      }
    }
  ]
}
```

---

## 5. API Specifications

### 5.1 Internal Python Services API

**Transcription Service (FastAPI)**
```python
# Base URL: http://localhost:8765

POST /transcribe/stream
{
  "audio_chunk": "base64_encoded_pcm",
  "session_id": "uuid",
  "chunk_index": 1,
  "language": "en",  # optional
  "speaker_profiles": ["profile1.json"]  # optional
}

Response (SSE - Server-Sent Events):
event: transcript
data: {"text": "Hello", "speaker": "Speaker 1", "confidence": 0.95}

event: final
data: {"text": "Hello world", "speaker": "Speaker 1"}

POST /transcribe/file
{
  "file_path": "/path/to/audio.wav",
  "meeting_id": "uuid",
  "enable_diarization": true,
  "num_speakers": 4
}

Response:
{
  "transcript_id": "uuid",
  "segments": [
    {
      "speaker": "Speaker 1",
      "text": "Hello everyone",
      "start_ms": 0,
      "end_ms": 1500,
      "confidence": 0.96
    }
  ],
  "language_detected": "en",
  "processing_time_ms": 3421
}
```

**LLM Service (FastAPI)**
```python
# Base URL: http://localhost:8766

POST /complete
{
  "prompt": "Summarize this meeting transcript...",
  "task_type": "summarization",  # or "qa", "code_gen", "intent", etc.
  "max_tokens": 2000,
  "temperature": 0.7,
  "context": {  # optional
    "meeting_id": "uuid",
    "previous_context": "..."
  }
}

Response:
{
  "text": "Generated response",
  "model_used": "gemini-2.5-pro",
  "tokens_used": 1234,
  "processing_time_ms": 2100,
  "confidence": 0.89,
  "fallback_used": false
}

POST /extract/action-items
{
  "transcript": "Full meeting transcript",
  "participants": ["John", "Jane"]
}

Response:
{
  "action_items": [
    {
      "task": "Update documentation",
      "assignee": "John",
      "due_date": "2025-12-01",
      "priority": "high",
      "timestamp_ms": 123000,
      "confidence": 0.92
    }
  ]
}
```

**RAG Service (FastAPI)**
```python
# Base URL: http://localhost:8767

POST /query
{
  "question": "What did we decide about the database?",
  "filters": {
    "date_range": ["2025-11-01", "2025-11-23"],
    "content_types": ["decision", "summary"]
  },
  "top_k": 5,
  "use_web_search": true
}

Response:
{
  "answer": "You decided to use PostgreSQL because...",
  "sources": [
    {
      "meeting_id": "abc-123",
      "meeting_title": "Architecture Review",
      "date": "2025-11-15",
      "excerpt": "...relevant excerpt...",
      "relevance_score": 0.89
    }
  ],
  "web_sources": [
    {
      "title": "PostgreSQL vs MySQL",
      "url": "https://...",
      "snippet": "..."
    }
  ],
  "confidence": 0.85
}

POST /index/meeting
{
  "meeting_id": "uuid",
  "transcript": "Full text",
  "summary": "Summary text",
  "metadata": {
    "title": "Meeting title",
    "date": "2025-11-23",
    "participants": ["John", "Jane"]
  }
}

Response:
{
  "status": "indexed",
  "embedding_count": 47,
  "processing_time_ms": 1250
}
```

---

## 6. Security Architecture

### 6.1 Data Encryption

**At Rest:**
```
User Data Directory:
~/nexus-assistant/
├── data/
│   ├── database.db (AES-256-GCM encrypted)
│   ├── transcripts/
│   │   ├── meeting-abc-123.json.enc (AES-256-GCM)
│   │   └── meeting-xyz-789.json.enc
│   ├── audio/
│   │   ├── meeting-abc-123.wav.enc (AES-256-GCM)
│   │   └── meeting-xyz-789.wav.enc
│   └── vector_db/
│       └── chroma.db (encrypted via SQLCipher)
├── config/
│   ├── settings.enc.json
│   └── api_keys.enc.json
└── .master_key (PBKDF2-derived key from user password)
```

**Encryption Process:**
1. User sets master password on first run
2. PBKDF2 derives 256-bit key (100,000 iterations, random salt)
3. All data encrypted with AES-256-GCM before writing to disk
4. Encryption key stored in OS keychain (Windows Credential Manager / macOS Keychain)
5. Application memory is cleared on lock/exit

**In Transit:**
- All external API calls use HTTPS/TLS 1.3
- Local services communicate via localhost (not exposed externally)
- Optional: mTLS for local API if exposed to LAN

### 6.2 API Key Management

**Local API Authentication:**
```javascript
// Generate API key
POST /api/v1/auth/keys
{
  "name": "My Integration"
}

Response:
{
  "key_id": "key_abc123",
  "api_key": "nxs_1234567890abcdef",  // Show only once!
  "created_at": "2025-11-23T10:00:00Z"
}

// Use API key
GET /api/v1/meetings
Headers:
  Authorization: Bearer nxs_1234567890abcdef
```

**Storage:**
- API keys hashed with bcrypt (cost factor 12)
- Stored in encrypted SQLite database
- Automatic rotation option (every 90 days)

### 6.3 Compliance Features

**GDPR Compliance:**
- Right to access: Export all user data
- Right to erasure: Complete data deletion
- Right to portability: Standard JSON/CSV export
- Consent tracking: Meeting start confirmation

**Data Retention:**
```javascript
// Auto-delete settings
{
  "auto_delete_enabled": true,
  "retention_days": 90,
  "delete_audio": true,
  "keep_summaries": true,  // Keep summaries even after transcript deletion
  "anonymize_after_days": 30  // Remove speaker names
}
```

---

## 7. Deployment Strategy

### 7.1 Build Process

```mermaid
flowchart LR
    A[Source Code] --> B[Lint & Type Check]
    B --> C[Unit Tests]
    C --> D[Integration Tests]
    D --> E[Build Electron App]
    E --> F{Platform?}

    F -->|Windows| G[electron-builder<br/>NSIS Installer]
    F -->|macOS| H[electron-builder<br/>.dmg + .pkg]
    F -->|Linux| I[electron-builder<br/>.AppImage + .deb]

    G --> J[Code Sign<br/>Windows Authenticode]
    H --> K[Code Sign<br/>Apple Developer ID]
    I --> L[GPG Sign]

    J --> M[Upload to Release]
    K --> M
    L --> M

    M --> N[Auto-Update Server]
```

### 7.2 Installation Package Contents

```
nexus-assistant-setup-1.0.0.exe (Windows)
├── Application Files
│   ├── nexus-assistant.exe
│   ├── resources/
│   │   ├── app.asar (Frontend + Main process)
│   │   ├── python/ (Embedded Python 3.11)
│   │   ├── models/ (Local Whisper model - optional download)
│   │   └── ffmpeg/ (Audio processing)
│   └── node_modules/
├── Dependencies
│   ├── VC++ Redistributable (if missing)
│   └── .NET Framework (if needed)
└── Installer Scripts
    ├── Create app data directory
    ├── Set permissions
    ├── Create desktop shortcut
    └── Register auto-start (optional)
```

### 7.3 Auto-Update Mechanism

**Update Server:** Electron's autoUpdater (based on Squirrel)

**Update Process:**
1. App checks for updates on startup (configurable frequency)
2. Download update in background
3. Notify user when ready
4. Install on next restart (or immediately if user confirms)
5. Rollback capability if update fails

**Release Channels:**
- `stable`: Production releases
- `beta`: Preview features
- `dev`: Development builds (opt-in)

---

## 8. Performance Optimization

### 8.1 Resource Management

**Audio Buffers:**
- Ring buffer with 10-second capacity
- Automatic buffer clearing after STT processing
- Memory-mapped files for large audio (>100MB)

**Transcription:**
- Stream processing (no full audio buffering)
- Incremental database writes (every 30 seconds)
- Background worker pool (4 workers)

**LLM Caching:**
- Redis-compatible in-memory cache (using node-cache)
- Semantic deduplication (avoid re-processing similar queries)
- Lazy loading of embeddings

**Database:**
- WAL mode for SQLite (better concurrency)
- Prepared statements (prevent SQL injection + performance)
- Connection pooling (max 10 connections)
- Regular VACUUM (weekly)

### 8.2 Lazy Loading Strategy

```javascript
// Don't load all meetings on startup
// Load only metadata, fetch details on-demand

Initial Load (Dashboard):
- Last 20 meetings (metadata only: id, title, date)
- Pending action items count
- Today's scheduled meetings

On Scroll/Search:
- Load next 20 meetings (virtualized list)

On Meeting Click:
- Load full transcript
- Load summary
- Load analytics (cached)
```

---

## 9. Testing Strategy

### 9.1 Test Coverage Goals

| Component | Unit Test Coverage | Integration Tests |
|-----------|-------------------|-------------------|
| Audio Capture | 80%+ | E2E with sample audio |
| Transcription | 85%+ | Multiple STT providers |
| LLM Orchestration | 90%+ | Mock responses + fallback |
| RAG Engine | 85%+ | Vector search accuracy |
| Analytics | 80%+ | Statistical correctness |
| API Server | 90%+ | All endpoints |
| UI Components | 75%+ | React Testing Library |

### 9.2 Test Scenarios

**End-to-End Tests:**
1. Complete meeting flow (start → record → stop → summarize)
2. Real-time assistance during meeting
3. Export in all formats
4. Search across historical meetings
5. Action item creation and completion
6. Multi-language transcription
7. Speaker diarization accuracy
8. LLM fallback scenarios
9. Offline mode (local Whisper + Ollama)
10. Data encryption/decryption

**Performance Tests:**
- Transcribe 1-hour meeting in <5 minutes
- Generate summary in <30 seconds
- Search query response <500ms
- UI remains responsive during recording
- Memory usage <500MB during active recording
- No memory leaks over 8-hour recording

---

## 10. Monitoring & Logging

### 10.1 Logging Strategy

**Log Levels:**
- ERROR: Critical failures (STT timeout, DB corruption)
- WARN: Non-critical issues (fallback triggered, low disk space)
- INFO: Normal operations (meeting started, summary generated)
- DEBUG: Detailed debugging (API calls, timings)

**Log Storage:**
```
~/nexus-assistant/logs/
├── app-2025-11-23.log
├── transcription-2025-11-23.log
├── llm-2025-11-23.log
└── errors.log (persistent, all ERROR logs)
```

**Log Rotation:**
- Daily rotation
- Keep last 7 days
- Compress logs older than 2 days
- Max total size: 500MB

### 10.2 Performance Metrics

**Tracked Metrics:**
```javascript
{
  "transcription": {
    "avg_latency_ms": 1850,
    "accuracy_wer": 0.045,  // Word Error Rate
    "provider_success_rate": 0.98
  },
  "llm": {
    "avg_response_time_ms": 2100,
    "fallback_rate": 0.05,
    "cache_hit_rate": 0.35
  },
  "rag": {
    "avg_query_time_ms": 450,
    "retrieval_accuracy": 0.87
  },
  "system": {
    "avg_memory_mb": 380,
    "avg_cpu_percent": 7.5,
    "crash_rate": 0.001
  }
}
```

**Metrics Dashboard:**
- Internal metrics viewer in Settings
- Export metrics as JSON
- Optional: Send to external monitoring (Prometheus, Datadog)

---

## Conclusion

This technical architecture provides a comprehensive blueprint for building Nexus Assistant as a production-grade, local-first meeting intelligence platform. The modular design, multi-LLM fallback strategy, and focus on privacy make it a robust solution for professional knowledge capture and retrieval.

**Key Architectural Strengths:**
1. **Resilience**: Multi-provider fallback ensures 99.9% uptime
2. **Privacy**: Complete local data ownership with encryption
3. **Performance**: Optimized for real-time processing with <3s latency
4. **Extensibility**: Open APIs and standard export formats
5. **Intelligence**: Hybrid RAG + advanced analytics

**Next Steps:**
1. Review and approve architecture
2. Set up development environment
3. Begin Phase 1 implementation (Core Foundation)
4. Iterate based on testing and feedback

---

**Document Prepared By:** Architecture Team
**Review Status:** Ready for Implementation
**Version:** 1.0
**Last Updated:** November 23, 2025

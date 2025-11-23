"""
RAG (Retrieval-Augmented Generation) Service
Knowledge base with vector search and meeting preparation
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import asyncio
import hashlib
from datetime import datetime, timedelta
from logging_config import setup_logger, log_request, log_response, log_activity

logger = setup_logger("rag")

# Vector DB and Embeddings
try:
    import chromadb
    from chromadb.config import Settings

    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    logger.warning("ChromaDB not available")

try:
    from sentence_transformers import SentenceTransformer

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning("Sentence Transformers not available")

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    logger.warning("HTTPX not available")

# Initialize FastAPI
app = FastAPI(title="Nexus RAG Service", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY", "")
GOOGLE_SEARCH_ENGINE_ID = os.getenv("GOOGLE_SEARCH_ENGINE_ID", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# Global state
chroma_client = None
embedding_model = None
collections = {}


# Models
class QueryRequest(BaseModel):
    question: str
    filters: Optional[Dict] = None
    top_k: int = 5
    use_web_search: bool = False


class Source(BaseModel):
    meeting_id: str
    meeting_title: str
    date: str
    excerpt: str
    relevance_score: float


class WebSource(BaseModel):
    title: str
    url: str
    snippet: str


class QueryResponse(BaseModel):
    answer: str
    sources: List[Source]
    web_sources: Optional[List[WebSource]] = None
    confidence: float


class IndexMeetingRequest(BaseModel):
    meeting_id: str
    transcript: str
    summary: str
    metadata: Dict


class IndexResponse(BaseModel):
    status: str
    embedding_count: int
    processing_time_ms: int


class PrepareMeetingRequest(BaseModel):
    meeting_title: str
    meeting_description: Optional[str] = None
    participants: List[str]
    scheduled_time: str
    duration_minutes: int


class MeetingPreparation(BaseModel):
    summary: str
    key_topics: List[str]
    relevant_history: List[Dict]
    suggested_agenda: List[str]
    talking_points: List[str]
    potential_questions: List[str]


def initialize_services():
    """Initialize ChromaDB and embedding model"""
    global chroma_client, embedding_model, collections

    if CHROMA_AVAILABLE:
        try:
            chroma_client = chromadb.Client(
                Settings(persist_directory="./chroma_data", anonymized_telemetry=False)
            )

            # Create collections
            collections["transcripts"] = chroma_client.get_or_create_collection(
                name="meeting_transcripts",
                metadata={"description": "Vector embeddings of meeting transcripts"},
            )

            collections["summaries"] = chroma_client.get_or_create_collection(
                name="meeting_summaries",
                metadata={"description": "Vector embeddings of meeting summaries"},
            )

            collections["decisions"] = chroma_client.get_or_create_collection(
                name="decisions",
                metadata={"description": "Vector embeddings of decisions"},
            )

            logger.info("ChromaDB initialized")

        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")

    if SENTENCE_TRANSFORMERS_AVAILABLE:
        try:
            embedding_model = SentenceTransformer(EMBEDDING_MODEL)
            logger.info(f"Loaded embedding model: {EMBEDDING_MODEL}")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")


@app.on_event("startup")
async def startup_event():
    """Startup event"""
    initialize_services()


@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "ok",
        "services": {
            "chromadb": chroma_client is not None,
            "embeddings": embedding_model is not None,
            "web_search": bool(GOOGLE_SEARCH_API_KEY),
        },
    }


def generate_embedding(text: str) -> List[float]:
    """Generate embedding for text"""
    if not embedding_model:
        raise Exception("Embedding model not available")

    return embedding_model.encode(text).tolist()


async def search_web(query: str, num_results: int = 5) -> List[WebSource]:
    """Search web using Google Custom Search API"""
    if not GOOGLE_SEARCH_API_KEY or not HTTPX_AVAILABLE:
        return []

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.googleapis.com/customsearch/v1",
                params={
                    "key": GOOGLE_SEARCH_API_KEY,
                    "cx": GOOGLE_SEARCH_ENGINE_ID,
                    "q": query,
                    "num": num_results,
                },
                timeout=5.0,
            )

            if response.status_code == 200:
                data = response.json()
                results = []

                for item in data.get("items", []):
                    results.append(
                        WebSource(
                            title=item.get("title", ""),
                            url=item.get("link", ""),
                            snippet=item.get("snippet", ""),
                        )
                    )

                return results

    except Exception as e:
        logger.error(f"Web search failed: {e}")

    return []


@app.post("/query", response_model=QueryResponse)
async def query_knowledge_base(request: QueryRequest):
    """Query knowledge base with RAG"""
    if not chroma_client or not embedding_model:
        raise HTTPException(status_code=503, detail="RAG service not initialized")

    try:
        # Generate query embedding
        query_embedding = generate_embedding(request.question)

        # Search in transcript collection
        search_filters = {}
        if request.filters:
            if request.filters.get("exclude_meeting_id"):
                search_filters["meeting_id"] = {
                    "$ne": request.filters["exclude_meeting_id"]
                }
            if request.filters.get("date_range"):
                # Add date range filter
                pass

        results = collections["transcripts"].query(
            query_embeddings=[query_embedding],
            n_results=request.top_k,
            where=search_filters if search_filters else None,
        )

        # Build sources
        sources = []
        if results["ids"] and len(results["ids"][0]) > 0:
            for i in range(len(results["ids"][0])):
                metadata = results["metadatas"][0][i]
                document = results["documents"][0][i]
                distance = results["distances"][0][i] if "distances" in results else 0.5

                sources.append(
                    Source(
                        meeting_id=metadata.get("meeting_id", ""),
                        meeting_title=metadata.get("meeting_title", "Unknown"),
                        date=metadata.get("date", ""),
                        excerpt=document[:200] + "...",
                        relevance_score=1 - distance,  # Convert distance to similarity
                    )
                )

        # Web search if requested
        web_sources = None
        if request.use_web_search:
            web_sources = await search_web(request.question)

        # Build context from sources
        context_parts = []
        for source in sources[:3]:
            context_parts.append(
                f"From {source.meeting_title} ({source.date}):\n{source.excerpt}"
            )

        if web_sources:
            for web_source in web_sources[:2]:
                context_parts.append(f"Web result: {web_source.snippet}")

        context = "\n\n".join(context_parts)

        # Generate answer (placeholder - would call LLM service)
        if len(sources) > 0:
            answer = f"Based on previous meetings: {sources[0].excerpt[:150]}..."
            confidence = sources[0].relevance_score
        else:
            answer = "No relevant information found in meeting history."
            confidence = 0.0

        return QueryResponse(
            answer=answer,
            sources=sources,
            web_sources=web_sources,
            confidence=confidence,
        )

    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/index/meeting", response_model=IndexResponse)
async def index_meeting(request: IndexMeetingRequest):
    """Index a meeting in the knowledge base"""
    if not chroma_client or not embedding_model:
        raise HTTPException(status_code=503, detail="RAG service not initialized")

    start_time = datetime.now()
    embedding_count = 0

    try:
        # Chunk transcript into segments (every 500 characters)
        transcript_chunks = [
            request.transcript[i : i + 500]
            for i in range(0, len(request.transcript), 500)
        ]

        # Generate embeddings for chunks
        chunk_embeddings = [generate_embedding(chunk) for chunk in transcript_chunks]

        # Add to transcript collection
        chunk_ids = [
            f"{request.meeting_id}-chunk-{i}" for i in range(len(transcript_chunks))
        ]

        chunk_metadata = [
            {
                "meeting_id": request.meeting_id,
                "meeting_title": request.metadata.get("title", ""),
                "date": datetime.now().isoformat(),
                "content_type": "transcript",
                "chunk_index": i,
            }
            for i in range(len(transcript_chunks))
        ]

        collections["transcripts"].add(
            ids=chunk_ids,
            embeddings=chunk_embeddings,
            documents=transcript_chunks,
            metadatas=chunk_metadata,
        )

        embedding_count += len(transcript_chunks)

        # Index summary if provided
        if request.summary:
            summary_embedding = generate_embedding(request.summary)

            collections["summaries"].add(
                ids=[f"{request.meeting_id}-summary"],
                embeddings=[summary_embedding],
                documents=[request.summary],
                metadatas=[
                    {
                        "meeting_id": request.meeting_id,
                        "meeting_title": request.metadata.get("title", ""),
                        "date": datetime.now().isoformat(),
                        "content_type": "summary",
                    }
                ],
            )

            embedding_count += 1

        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

        logger.info(
            f"Indexed meeting {request.meeting_id} with {embedding_count} embeddings"
        )

        return IndexResponse(
            status="indexed",
            embedding_count=embedding_count,
            processing_time_ms=processing_time,
        )

    except Exception as e:
        logger.error(f"Indexing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/prepare-meeting", response_model=MeetingPreparation)
async def prepare_meeting(request: PrepareMeetingRequest):
    """Prepare for an upcoming meeting by analyzing history"""
    if not chroma_client or not embedding_model:
        raise HTTPException(status_code=503, detail="RAG service not initialized")

    try:
        # Generate embedding for meeting title + description
        query_text = request.meeting_title
        if request.meeting_description:
            query_text += " " + request.meeting_description

        query_embedding = generate_embedding(query_text)

        # Search for relevant past meetings
        results = collections["transcripts"].query(
            query_embeddings=[query_embedding], n_results=10
        )

        relevant_history = []
        if results["ids"] and len(results["ids"][0]) > 0:
            for i in range(min(5, len(results["ids"][0]))):
                metadata = results["metadatas"][0][i]
                document = results["documents"][0][i]

                relevant_history.append(
                    {
                        "meeting_title": metadata.get("meeting_title", ""),
                        "date": metadata.get("date", ""),
                        "excerpt": document[:150],
                        "relevance": (
                            1 - results["distances"][0][i]
                            if "distances" in results
                            else 0.5
                        ),
                    }
                )

        # Extract key topics from title and description
        key_topics = []
        if request.meeting_description:
            # Simple keyword extraction (in production, use NLP)
            words = request.meeting_description.lower().split()
            important_words = [
                w
                for w in words
                if len(w) > 5 and w not in ["meeting", "discuss", "review"]
            ]
            key_topics = important_words[:5]

        # Generate suggested agenda
        suggested_agenda = [
            "Welcome and introductions (2 min)",
            f"Review previous action items (5 min)",
            f"Main discussion: {request.meeting_title} ({request.duration_minutes - 15} min)",
            "Action items and next steps (5 min)",
            "Wrap-up (3 min)",
        ]

        # Generate talking points based on history
        talking_points = []
        if len(relevant_history) > 0:
            talking_points.append(
                f"Reference previous discussion from {relevant_history[0]['date']}"
            )
            talking_points.append("Build on decisions made in last meeting")

        talking_points.extend(
            [
                "Clarify objectives and desired outcomes",
                "Assign clear action items with owners",
                "Set follow-up meeting if needed",
            ]
        )

        # Generate potential questions
        potential_questions = [
            "What are the key challenges we need to address?",
            "What resources do we need?",
            "What are the success criteria?",
            "What are the timelines?",
            "Who else should be involved?",
        ]

        # Build summary
        summary = f"Upcoming meeting: {request.meeting_title}\n\n"
        summary += f"Scheduled for: {request.scheduled_time}\n"
        summary += f"Duration: {request.duration_minutes} minutes\n"
        summary += f"Participants: {', '.join(request.participants)}\n\n"

        if len(relevant_history) > 0:
            summary += f"This topic was last discussed in {relevant_history[0]['meeting_title']} on {relevant_history[0]['date']}. "
            summary += "Review that meeting's notes for context."

        return MeetingPreparation(
            summary=summary,
            key_topics=key_topics,
            relevant_history=relevant_history,
            suggested_agenda=suggested_agenda,
            talking_points=talking_points,
            potential_questions=potential_questions,
        )

    except Exception as e:
        logger.error(f"Meeting preparation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/meeting/{meeting_id}")
async def delete_meeting(meeting_id: str):
    """Delete a meeting from knowledge base"""
    if not chroma_client:
        raise HTTPException(status_code=503, detail="RAG service not initialized")

    try:
        # Delete from all collections
        for collection in collections.values():
            # Get all IDs for this meeting
            results = collection.get(where={"meeting_id": meeting_id})

            if results["ids"]:
                collection.delete(ids=results["ids"])

        return {"status": "deleted", "meeting_id": meeting_id}

    except Exception as e:
        logger.error(f"Delete failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    # Use random port 53847
    uvicorn.run(app, host="127.0.0.1", port=53847, log_level="info")

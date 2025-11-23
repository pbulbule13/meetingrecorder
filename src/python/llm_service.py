"""
LLM Orchestration Service
Multi-provider LLM with intelligent fallback strategy
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio
import os
import hashlib
import json
from loguru import logger

# LLM Providers
try:
    import google.generativeai as genai

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("Gemini not available")

try:
    from openai import AsyncOpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI not available")

try:
    from anthropic import AsyncAnthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.warning("Anthropic not available")

# Initialize FastAPI
app = FastAPI(title="Nexus LLM Service", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Initialize clients
gemini_client = None
openai_client = None
anthropic_client = None

if GEMINI_AVAILABLE and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_client = genai.GenerativeModel("gemini-2.0-flash-exp")

if OPENAI_AVAILABLE and OPENAI_API_KEY:
    openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

if ANTHROPIC_AVAILABLE and ANTHROPIC_API_KEY:
    anthropic_client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)


# Models
class LLMRequest(BaseModel):
    prompt: str
    task_type: str  # "intent", "qa", "code_gen", "summarization", "extraction"
    max_tokens: Optional[int] = 2000
    temperature: Optional[float] = 0.7
    context: Optional[Dict] = None


class LLMResponse(BaseModel):
    text: str
    model_used: str
    tokens_used: int
    processing_time_ms: int
    confidence: Optional[float] = None
    fallback_used: bool = False


class IntentRequest(BaseModel):
    text: str
    context: Optional[str] = None


class IntentResponse(BaseModel):
    intent: str  # "question", "code_request", "decision", "action_item", "general"
    entities: Dict[str, Any]
    confidence: float


class SummarizeRequest(BaseModel):
    transcript: str
    max_tokens: Optional[int] = 3000


class SummaryResponse(BaseModel):
    summary: Dict[str, Any]


class ExtractActionItemsRequest(BaseModel):
    transcript: str
    participants: List[str]


class ExtractActionItemsResponse(BaseModel):
    action_items: List[Dict]


class ExtractDecisionsRequest(BaseModel):
    transcript: str


class ExtractDecisionsResponse(BaseModel):
    decisions: List[Dict]


class CalculateAnalyticsRequest(BaseModel):
    segments: List[Dict]
    duration_seconds: int


class AnalyticsResponse(BaseModel):
    meeting: Dict
    speakers: Dict[str, Dict]


# Simple cache
cache = {}


def get_cache_key(prompt: str, task_type: str) -> str:
    """Generate cache key"""
    content = f"{task_type}:{prompt}"
    return hashlib.md5(content.encode()).hexdigest()


def get_from_cache(key: str) -> Optional[Dict]:
    """Get from cache if exists and not expired"""
    if key in cache:
        entry = cache[key]
        # Cache expires after 1 hour
        if (datetime.now().timestamp() - entry["timestamp"]) < 3600:
            return entry["data"]
        else:
            del cache[key]
    return None


def save_to_cache(key: str, data: Dict):
    """Save to cache"""
    cache[key] = {"data": data, "timestamp": datetime.now().timestamp()}


async def complete_with_gemini(
    prompt: str, max_tokens: int, temperature: float
) -> Dict:
    """Complete using Gemini"""
    if not gemini_client:
        raise Exception("Gemini not available")

    start_time = datetime.now()

    try:
        response = await asyncio.to_thread(
            gemini_client.generate_content,
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=max_tokens, temperature=temperature
            ),
        )

        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

        return {
            "text": response.text,
            "model": "gemini-2.0-flash-exp",
            "tokens": len(response.text.split()),  # Approximate
            "processing_time_ms": processing_time,
        }

    except Exception as e:
        logger.error(f"Gemini error: {e}")
        raise


async def complete_with_openai(
    prompt: str, max_tokens: int, temperature: float, model: str = "gpt-4o-mini"
) -> Dict:
    """Complete using OpenAI"""
    if not openai_client:
        raise Exception("OpenAI not available")

    start_time = datetime.now()

    try:
        response = await openai_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
        )

        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

        return {
            "text": response.choices[0].message.content,
            "model": model,
            "tokens": response.usage.total_tokens,
            "processing_time_ms": processing_time,
        }

    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        raise


async def complete_with_anthropic(
    prompt: str, max_tokens: int, temperature: float
) -> Dict:
    """Complete using Anthropic Claude"""
    if not anthropic_client:
        raise Exception("Anthropic not available")

    start_time = datetime.now()

    try:
        response = await anthropic_client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )

        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

        return {
            "text": response.content[0].text,
            "model": "claude-3-5-haiku",
            "tokens": response.usage.input_tokens + response.usage.output_tokens,
            "processing_time_ms": processing_time,
        }

    except Exception as e:
        logger.error(f"Anthropic error: {e}")
        raise


@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "ok",
        "providers": {
            "gemini": gemini_client is not None,
            "openai": openai_client is not None,
            "anthropic": anthropic_client is not None,
        },
    }


@app.post("/complete", response_model=LLMResponse)
async def complete(request: LLMRequest):
    """Complete text using LLM with fallback strategy"""
    start_time = datetime.now()

    # Check cache
    cache_key = get_cache_key(request.prompt, request.task_type)
    cached = get_from_cache(cache_key)
    if cached:
        logger.info("Returning cached response")
        return LLMResponse(**cached)

    # Determine model priority based on task type
    providers = []

    if request.task_type == "intent":
        # Fast model for intent detection
        if gemini_client:
            providers.append(
                (
                    "Gemini Flash",
                    lambda: complete_with_gemini(
                        request.prompt, request.max_tokens, request.temperature
                    ),
                )
            )
        if openai_client:
            providers.append(
                (
                    "GPT-4o-mini",
                    lambda: complete_with_openai(
                        request.prompt,
                        request.max_tokens,
                        request.temperature,
                        "gpt-4o-mini",
                    ),
                )
            )

    elif request.task_type == "code_gen":
        # Best models for code generation
        if openai_client:
            providers.append(
                (
                    "GPT-4o",
                    lambda: complete_with_openai(
                        request.prompt,
                        request.max_tokens,
                        request.temperature,
                        "gpt-4o",
                    ),
                )
            )
        if gemini_client:
            providers.append(
                (
                    "Gemini Pro",
                    lambda: complete_with_gemini(
                        request.prompt, request.max_tokens, request.temperature
                    ),
                )
            )

    elif request.task_type in ["summarization", "extraction"]:
        # Advanced models for complex tasks
        if gemini_client:
            providers.append(
                (
                    "Gemini Pro",
                    lambda: complete_with_gemini(
                        request.prompt, request.max_tokens, request.temperature
                    ),
                )
            )
        if openai_client:
            providers.append(
                (
                    "GPT-4o",
                    lambda: complete_with_openai(
                        request.prompt,
                        request.max_tokens,
                        request.temperature,
                        "gpt-4o",
                    ),
                )
            )
        if anthropic_client:
            providers.append(
                (
                    "Claude Haiku",
                    lambda: complete_with_anthropic(
                        request.prompt, request.max_tokens, request.temperature
                    ),
                )
            )

    else:
        # Default order
        if gemini_client:
            providers.append(
                (
                    "Gemini Flash",
                    lambda: complete_with_gemini(
                        request.prompt, request.max_tokens, request.temperature
                    ),
                )
            )
        if openai_client:
            providers.append(
                (
                    "GPT-4o-mini",
                    lambda: complete_with_openai(
                        request.prompt,
                        request.max_tokens,
                        request.temperature,
                        "gpt-4o-mini",
                    ),
                )
            )
        if anthropic_client:
            providers.append(
                (
                    "Claude Haiku",
                    lambda: complete_with_anthropic(
                        request.prompt, request.max_tokens, request.temperature
                    ),
                )
            )

    # Try providers in order
    last_error = None
    fallback_used = False

    for i, (provider_name, provider_func) in enumerate(providers):
        try:
            logger.info(f"Trying {provider_name}")
            result = await provider_func()

            if i > 0:
                fallback_used = True

            response = LLMResponse(
                text=result["text"],
                model_used=result["model"],
                tokens_used=result["tokens"],
                processing_time_ms=result["processing_time_ms"],
                fallback_used=fallback_used,
            )

            # Cache the response
            save_to_cache(cache_key, response.dict())

            logger.info(f"Successfully completed with {provider_name}")
            return response

        except Exception as e:
            logger.warning(f"{provider_name} failed: {e}")
            last_error = e
            continue

    # All providers failed
    raise HTTPException(
        status_code=503,
        detail=f"All LLM providers failed. Last error: {str(last_error)}",
    )


@app.post("/detect-intent", response_model=IntentResponse)
async def detect_intent(request: IntentRequest):
    """Detect intent from user input"""
    prompt = f"""Analyze the following text and determine the intent and extract entities.

Text: "{request.text}"

Context: {request.context or "None"}

Classify the intent as one of:
- question: User is asking a question
- code_request: User is requesting code or technical implementation
- decision: A decision is being made
- action_item: An action item or task is being assigned
- general: General conversation

Extract relevant entities such as:
- language: Programming language (if applicable)
- assignee: Person assigned to a task (if applicable)
- due_date: Due date mentioned (if applicable)
- topic: Main topic being discussed

Return the result as JSON with this exact structure:
{{
  "intent": "intent_type",
  "entities": {{"key": "value"}},
  "confidence": 0.0-1.0
}}
"""

    try:
        response = await complete(
            LLMRequest(
                prompt=prompt, task_type="intent", max_tokens=500, temperature=0.3
            )
        )

        # Parse JSON from response
        result = json.loads(response.text)

        return IntentResponse(**result)

    except Exception as e:
        logger.error(f"Intent detection failed: {e}")
        # Return default intent
        return IntentResponse(intent="general", entities={}, confidence=0.0)


@app.post("/summarize", response_model=SummaryResponse)
async def summarize_meeting(request: SummarizeRequest):
    """Generate comprehensive meeting summary"""
    prompt = f"""Analyze the following meeting transcript and create a comprehensive summary.

Transcript:
{request.transcript}

Provide a JSON response with this structure:
{{
  "executive_summary": "2-3 sentence overview",
  "key_topics": ["topic1", "topic2", "topic3"],
  "detailed_summary": "Paragraph-form detailed summary organized by topics",
  "main_points": ["point1", "point2", "point3"]
}}
"""

    try:
        response = await complete(
            LLMRequest(
                prompt=prompt,
                task_type="summarization",
                max_tokens=request.max_tokens,
                temperature=0.5,
            )
        )

        # Parse JSON
        summary = json.loads(response.text)

        return SummaryResponse(summary=summary)

    except Exception as e:
        logger.error(f"Summarization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/extract/action-items", response_model=ExtractActionItemsResponse)
async def extract_action_items(request: ExtractActionItemsRequest):
    """Extract action items from transcript"""
    participants_str = ", ".join(request.participants)

    prompt = f"""Extract all action items from the following meeting transcript.

Participants: {participants_str}

Transcript:
{request.transcript}

For each action item, identify:
- task: What needs to be done
- assignee: Who is responsible (must be from the participants list)
- due_date: When it's due (ISO format, estimate if not explicitly mentioned)
- priority: low/medium/high/critical
- timestamp_ms: Approximate timestamp in the meeting (in milliseconds)

Return a JSON array of action items:
[
  {{
    "task": "Update documentation",
    "assignee": "John Doe",
    "due_date": "2025-12-01",
    "priority": "high",
    "timestamp_ms": 123000
  }}
]
"""

    try:
        response = await complete(
            LLMRequest(
                prompt=prompt, task_type="extraction", max_tokens=1500, temperature=0.3
            )
        )

        # Parse JSON
        action_items = json.loads(response.text)

        return ExtractActionItemsResponse(action_items=action_items)

    except Exception as e:
        logger.error(f"Action item extraction failed: {e}")
        return ExtractActionItemsResponse(action_items=[])


@app.post("/extract/decisions", response_model=ExtractDecisionsResponse)
async def extract_decisions(request: ExtractDecisionsRequest):
    """Extract key decisions from transcript"""
    prompt = f"""Extract all key decisions made in the following meeting transcript.

Transcript:
{request.transcript}

For each decision, identify:
- decision: What was decided
- rationale: Why this decision was made
- participants: Who was involved in the decision
- timestamp_ms: Approximate timestamp (in milliseconds)

Return a JSON array of decisions:
[
  {{
    "decision": "Use PostgreSQL for the database",
    "rationale": "Better scalability and features needed",
    "participants": ["John", "Jane"],
    "timestamp_ms": 456000
  }}
]
"""

    try:
        response = await complete(
            LLMRequest(
                prompt=prompt, task_type="extraction", max_tokens=1500, temperature=0.3
            )
        )

        # Parse JSON
        decisions = json.loads(response.text)

        return ExtractDecisionsResponse(decisions=decisions)

    except Exception as e:
        logger.error(f"Decision extraction failed: {e}")
        return ExtractDecisionsResponse(decisions=[])


@app.post("/analytics/calculate", response_model=AnalyticsResponse)
async def calculate_analytics(request: CalculateAnalyticsRequest):
    """Calculate meeting analytics from segments"""
    # Simple analytics calculation
    try:
        total_words = sum(len(seg.get("text", "").split()) for seg in request.segments)
        avg_speaking_pace = (
            (total_words / request.duration_seconds) * 60
            if request.duration_seconds > 0
            else 0
        )

        # Calculate speaker stats
        speaker_stats = {}
        for seg in request.segments:
            speaker = seg.get("speaker_id", "unknown")
            if speaker not in speaker_stats:
                speaker_stats[speaker] = {
                    "word_count": 0,
                    "segments": 0,
                    "total_time_ms": 0,
                }

            words = len(seg.get("text", "").split())
            duration = seg.get("end_ms", 0) - seg.get("start_ms", 0)

            speaker_stats[speaker]["word_count"] += words
            speaker_stats[speaker]["segments"] += 1
            speaker_stats[speaker]["total_time_ms"] += duration

        # Calculate percentages and rates
        total_speaking_time = sum(s["total_time_ms"] for s in speaker_stats.values())

        for speaker in speaker_stats:
            stats = speaker_stats[speaker]
            stats["talk_time_percent"] = (
                (stats["total_time_ms"] / total_speaking_time * 100)
                if total_speaking_time > 0
                else 0
            )
            stats["speaking_pace_wpm"] = (
                (stats["word_count"] / (stats["total_time_ms"] / 1000 / 60))
                if stats["total_time_ms"] > 0
                else 0
            )
            stats["avg_sentiment"] = 0.5  # Placeholder
            stats["interruption_count"] = 0  # Placeholder
            stats["questions_asked"] = 0  # Placeholder

        meeting_analytics = {
            "total_words": total_words,
            "avg_speaking_pace": avg_speaking_pace,
            "total_interruptions": 0,  # Placeholder
            "sentiment_timeline": [],  # Placeholder
            "engagement_score": 75.0,  # Placeholder
        }

        return AnalyticsResponse(meeting=meeting_analytics, speakers=speaker_stats)

    except Exception as e:
        logger.error(f"Analytics calculation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    # Use random port 45231
    uvicorn.run(app, host="127.0.0.1", port=45231, log_level="info")

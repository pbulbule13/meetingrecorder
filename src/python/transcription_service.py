"""
Transcription Service
Real-time speech-to-text with speaker diarization
"""

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import base64
import io
import wave
import numpy as np
from datetime import datetime
import asyncio
import os
from pathlib import Path

# Load .env file from project root
from dotenv import load_dotenv
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(env_path)

from logging_config import setup_logger, log_request, log_response, log_activity

logger = setup_logger("transcription")

# STT Providers
try:
    from deepgram import Deepgram

    DEEPGRAM_AVAILABLE = True
except ImportError:
    DEEPGRAM_AVAILABLE = False
    logger.warning("Deepgram not available")

try:
    import assemblyai as aai

    ASSEMBLYAI_AVAILABLE = True
except ImportError:
    ASSEMBLYAI_AVAILABLE = False
    logger.warning("AssemblyAI not available")

try:
    import openai

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI not available")

try:
    from faster_whisper import WhisperModel

    WHISPER_LOCAL_AVAILABLE = True
except ImportError:
    WHISPER_LOCAL_AVAILABLE = False
    logger.warning("Local Whisper not available")

# Initialize FastAPI
app = FastAPI(title="Nexus Transcription Service", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


# Models
class TranscribeRequest(BaseModel):
    audio_chunk: str  # Base64 encoded PCM audio
    session_id: str
    chunk_index: int
    language: Optional[str] = "en"
    speaker_profiles: Optional[List[str]] = None


class TranscribeFileRequest(BaseModel):
    file_path: str
    meeting_id: str
    enable_diarization: bool = True
    num_speakers: Optional[int] = None
    language: Optional[str] = "en"


class TranscriptSegment(BaseModel):
    speaker: str
    text: str
    start_ms: int
    end_ms: int
    confidence: float
    words: Optional[List[Dict]] = None


class TranscribeResponse(BaseModel):
    segments: List[TranscriptSegment]
    language_detected: Optional[str] = None
    processing_time_ms: int


# Global state
active_sessions = {}
local_whisper_model = None


def load_local_whisper():
    """Load local Whisper model for offline fallback"""
    global local_whisper_model
    if WHISPER_LOCAL_AVAILABLE and local_whisper_model is None:
        try:
            logger.info("Loading local Whisper model...")
            local_whisper_model = WhisperModel(
                "large-v3", device="cpu", compute_type="int8"
            )
            logger.info("Local Whisper model loaded")
        except Exception as e:
            logger.error(f"Failed to load local Whisper: {e}")


# Load Whisper on startup
@app.on_event("startup")
async def startup_event():
    load_local_whisper()


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "providers": {
            "deepgram": DEEPGRAM_AVAILABLE and bool(DEEPGRAM_API_KEY),
            "assemblyai": ASSEMBLYAI_AVAILABLE and bool(ASSEMBLYAI_API_KEY),
            "openai": OPENAI_AVAILABLE and bool(OPENAI_API_KEY),
            "local_whisper": WHISPER_LOCAL_AVAILABLE
            and local_whisper_model is not None,
        },
    }


def decode_audio_chunk(base64_audio: str) -> bytes:
    """Decode base64 audio to bytes"""
    try:
        return base64.b64decode(base64_audio)
    except Exception as e:
        logger.error(f"Failed to decode audio: {e}")
        raise HTTPException(status_code=400, detail="Invalid audio data")


async def transcribe_with_deepgram(
    audio_data: bytes, language: str = "en"
) -> TranscribeResponse:
    """Transcribe using Deepgram API"""
    if not DEEPGRAM_AVAILABLE or not DEEPGRAM_API_KEY:
        raise HTTPException(status_code=503, detail="Deepgram not available")

    start_time = datetime.now()

    try:
        dg_client = Deepgram(DEEPGRAM_API_KEY)

        source = {"buffer": audio_data, "mimetype": "audio/wav"}
        options = {
            "punctuate": True,
            "language": language,
            "model": "nova-2",
            "diarize": True,
            "smart_format": True,
            "utterances": True,
        }

        response = await dg_client.transcription.prerecorded(source, options)

        segments = []
        if response.get("results"):
            for utterance in response["results"].get("utterances", []):
                segment = TranscriptSegment(
                    speaker=f"Speaker {utterance.get('speaker', 0) + 1}",
                    text=utterance.get("transcript", ""),
                    start_ms=int(utterance.get("start", 0) * 1000),
                    end_ms=int(utterance.get("end", 0) * 1000),
                    confidence=utterance.get("confidence", 0.0),
                    words=[
                        {
                            "word": w.get("word"),
                            "start": int(w.get("start", 0) * 1000),
                            "end": int(w.get("end", 0) * 1000),
                            "confidence": w.get("confidence", 0.0),
                        }
                        for w in utterance.get("words", [])
                    ],
                )
                segments.append(segment)

        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

        return TranscribeResponse(
            segments=segments,
            language_detected=language,
            processing_time_ms=processing_time,
        )

    except Exception as e:
        logger.error(f"Deepgram transcription failed: {e}")
        raise HTTPException(status_code=500, detail=f"Deepgram error: {str(e)}")


async def transcribe_with_assemblyai(
    audio_data: bytes, language: str = "en", num_speakers: int = None
) -> TranscribeResponse:
    """Transcribe using AssemblyAI"""
    if not ASSEMBLYAI_AVAILABLE or not ASSEMBLYAI_API_KEY:
        raise HTTPException(status_code=503, detail="AssemblyAI not available")

    start_time = datetime.now()

    try:
        aai.settings.api_key = ASSEMBLYAI_API_KEY

        # Save audio temporarily
        temp_file = f"/tmp/audio_{datetime.now().timestamp()}.wav"
        with open(temp_file, "wb") as f:
            f.write(audio_data)

        config = aai.TranscriptionConfig(
            speaker_labels=True, speakers_expected=num_speakers
        )

        transcriber = aai.Transcriber()
        transcript = transcriber.transcribe(temp_file, config)

        # Clean up temp file
        os.remove(temp_file)

        segments = []
        if transcript.utterances:
            for utterance in transcript.utterances:
                segment = TranscriptSegment(
                    speaker=f"Speaker {utterance.speaker}",
                    text=utterance.text,
                    start_ms=utterance.start,
                    end_ms=utterance.end,
                    confidence=utterance.confidence,
                    words=(
                        [
                            {
                                "word": w.text,
                                "start": w.start,
                                "end": w.end,
                                "confidence": w.confidence,
                            }
                            for w in utterance.words
                        ]
                        if hasattr(utterance, "words")
                        else None
                    ),
                )
                segments.append(segment)

        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

        return TranscribeResponse(
            segments=segments,
            language_detected=language,
            processing_time_ms=processing_time,
        )

    except Exception as e:
        logger.error(f"AssemblyAI transcription failed: {e}")
        raise HTTPException(status_code=500, detail=f"AssemblyAI error: {str(e)}")


async def transcribe_with_whisper_local(
    audio_data: bytes, language: str = "en"
) -> TranscribeResponse:
    """Transcribe using local Whisper model"""
    if not WHISPER_LOCAL_AVAILABLE or local_whisper_model is None:
        raise HTTPException(status_code=503, detail="Local Whisper not available")

    start_time = datetime.now()

    try:
        # Convert audio bytes to numpy array
        audio_io = io.BytesIO(audio_data)
        with wave.open(audio_io, "rb") as wav_file:
            sample_rate = wav_file.getframerate()
            audio_np = np.frombuffer(
                wav_file.readframes(wav_file.getnframes()), dtype=np.int16
            )
            audio_np = audio_np.astype(np.float32) / 32768.0

        # Transcribe
        segments_iter, info = local_whisper_model.transcribe(
            audio_np,
            language=language if language != "auto" else None,
            vad_filter=True,
            word_timestamps=True,
        )

        segments = []
        current_speaker = 1

        for segment in segments_iter:
            transcript_segment = TranscriptSegment(
                speaker=f"Speaker {current_speaker}",
                text=segment.text.strip(),
                start_ms=int(segment.start * 1000),
                end_ms=int(segment.end * 1000),
                confidence=segment.avg_logprob,
                words=(
                    [
                        {
                            "word": w.word,
                            "start": int(w.start * 1000),
                            "end": int(w.end * 1000),
                            "confidence": w.probability,
                        }
                        for w in segment.words
                    ]
                    if segment.words
                    else None
                ),
            )
            segments.append(transcript_segment)

        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

        return TranscribeResponse(
            segments=segments,
            language_detected=info.language,
            processing_time_ms=processing_time,
        )

    except Exception as e:
        logger.error(f"Local Whisper transcription failed: {e}")
        raise HTTPException(status_code=500, detail=f"Local Whisper error: {str(e)}")


@app.post("/transcribe/stream", response_model=TranscribeResponse)
async def transcribe_stream(request: TranscribeRequest):
    """Transcribe audio stream chunk"""
    try:
        audio_data = decode_audio_chunk(request.audio_chunk)

        # Try providers in order of preference
        providers = []

        if DEEPGRAM_AVAILABLE and DEEPGRAM_API_KEY:
            providers.append(("Deepgram", transcribe_with_deepgram))

        if ASSEMBLYAI_AVAILABLE and ASSEMBLYAI_API_KEY:
            providers.append(
                (
                    "AssemblyAI",
                    lambda data, lang: transcribe_with_assemblyai(data, lang, None),
                )
            )

        if WHISPER_LOCAL_AVAILABLE and local_whisper_model:
            providers.append(("Local Whisper", transcribe_with_whisper_local))

        last_error = None
        for provider_name, provider_func in providers:
            try:
                logger.info(f"Trying transcription with {provider_name}")
                result = await provider_func(audio_data, request.language)
                logger.info(f"Transcription successful with {provider_name}")
                return result
            except Exception as e:
                logger.warning(f"{provider_name} failed: {e}")
                last_error = e
                continue

        # All providers failed
        raise HTTPException(
            status_code=503,
            detail=f"All transcription providers failed. Last error: {str(last_error)}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/transcribe/file", response_model=TranscribeResponse)
async def transcribe_file(request: TranscribeFileRequest):
    """Transcribe audio file"""
    try:
        # Read audio file
        with open(request.file_path, "rb") as f:
            audio_data = f.read()

        # Use AssemblyAI for file transcription (best diarization)
        if ASSEMBLYAI_AVAILABLE and ASSEMBLYAI_API_KEY:
            return await transcribe_with_assemblyai(
                audio_data, request.language, request.num_speakers
            )

        # Fallback to Deepgram
        if DEEPGRAM_AVAILABLE and DEEPGRAM_API_KEY:
            return await transcribe_with_deepgram(audio_data, request.language)

        # Fallback to local Whisper
        if WHISPER_LOCAL_AVAILABLE and local_whisper_model:
            return await transcribe_with_whisper_local(audio_data, request.language)

        raise HTTPException(
            status_code=503, detail="No transcription providers available"
        )

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Audio file not found")
    except Exception as e:
        logger.error(f"File transcription error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/transcribe/ws/{session_id}")
async def websocket_transcribe(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time streaming transcription"""
    await websocket.accept()
    active_sessions[session_id] = {"websocket": websocket, "active": True}

    try:
        while active_sessions[session_id]["active"]:
            # Receive audio chunk
            data = await websocket.receive_text()

            # Decode and transcribe
            audio_data = decode_audio_chunk(data)
            result = await transcribe_with_deepgram(audio_data, "en")

            # Send back transcript
            await websocket.send_json(result.dict())

    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
    finally:
        if session_id in active_sessions:
            del active_sessions[session_id]
        await websocket.close()


@app.post("/session/{session_id}/stop")
async def stop_session(session_id: str):
    """Stop an active transcription session"""
    if session_id in active_sessions:
        active_sessions[session_id]["active"] = False
        return {"status": "stopped"}
    return {"status": "not_found"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=38421, log_level="info")

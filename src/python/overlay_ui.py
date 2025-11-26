"""
Nexus Meeting Recorder - Enhanced Overlay UI v4
WORKING dual audio capture using PyAudioWPatch for WASAPI loopback
Speakers: "Me" (microphone) and "Him" (system audio/other person)
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time
import wave
import io
import base64
import json
import queue
import numpy as np
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
import subprocess
import sys
import sqlite3

# Try PyAudioWPatch first (better WASAPI loopback), fall back to regular PyAudio
try:
    import pyaudiowpatch as pyaudio
    PYAUDIO_AVAILABLE = True
    WPATCH_AVAILABLE = True
    print("Using PyAudioWPatch for WASAPI loopback")
except ImportError:
    try:
        import pyaudio
        PYAUDIO_AVAILABLE = True
        WPATCH_AVAILABLE = False
        print("Using standard PyAudio")
    except ImportError:
        PYAUDIO_AVAILABLE = False
        WPATCH_AVAILABLE = False
        print("No PyAudio available")

# HTTP client
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

# Service URLs
TRANSCRIPTION_SERVICE = "http://127.0.0.1:38421"
LLM_SERVICE = "http://127.0.0.1:45231"
RAG_SERVICE = "http://127.0.0.1:53847"

# Audio configuration
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 1024
RECORD_SECONDS_PER_CHUNK = 5

# Database path
DB_PATH = Path(__file__).parent.parent.parent / "data" / "meetings.db"

# Speaker labels
SPEAKER_ME = "Me"
SPEAKER_HIM = "Him"

# Global lock for PyAudio initialization (prevents concurrent access crash)
_pyaudio_lock = threading.Lock()


class MeetingDatabase:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_database()

    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, date TEXT NOT NULL,
            duration_seconds INTEGER DEFAULT 0, participants TEXT DEFAULT '[]',
            status TEXT DEFAULT 'completed', created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS transcripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, meeting_id INTEGER NOT NULL,
            speaker TEXT NOT NULL, text TEXT NOT NULL, timestamp TEXT NOT NULL,
            start_ms INTEGER DEFAULT 0, end_ms INTEGER DEFAULT 0,
            FOREIGN KEY (meeting_id) REFERENCES meetings(id))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS insights (
            id INTEGER PRIMARY KEY AUTOINCREMENT, meeting_id INTEGER NOT NULL,
            insight_type TEXT NOT NULL, content TEXT NOT NULL, timestamp TEXT NOT NULL,
            FOREIGN KEY (meeting_id) REFERENCES meetings(id))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, meeting_id INTEGER NOT NULL UNIQUE,
            executive_summary TEXT, key_topics TEXT, detailed_summary TEXT,
            action_items TEXT, decisions TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (meeting_id) REFERENCES meetings(id))''')
        conn.commit()
        conn.close()

    def create_meeting(self, title: str) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO meetings (title, date, status) VALUES (?, ?, ?)',
                      (title, datetime.now().isoformat(), 'recording'))
        meeting_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return meeting_id

    def update_meeting(self, meeting_id: int, duration_seconds: int = None,
                      participants: List[str] = None, status: str = None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        updates, values = [], []
        if duration_seconds is not None:
            updates.append("duration_seconds = ?")
            values.append(duration_seconds)
        if participants is not None:
            updates.append("participants = ?")
            values.append(json.dumps(participants))
        if status is not None:
            updates.append("status = ?")
            values.append(status)
        if updates:
            values.append(meeting_id)
            cursor.execute(f'UPDATE meetings SET {", ".join(updates)} WHERE id = ?', values)
        conn.commit()
        conn.close()

    def add_transcript(self, meeting_id: int, speaker: str, text: str, start_ms: int = 0, end_ms: int = 0):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO transcripts (meeting_id, speaker, text, timestamp, start_ms, end_ms) VALUES (?, ?, ?, ?, ?, ?)',
                      (meeting_id, speaker, text, datetime.now().isoformat(), start_ms, end_ms))
        conn.commit()
        conn.close()

    def add_insight(self, meeting_id: int, insight_type: str, content: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO insights (meeting_id, insight_type, content, timestamp) VALUES (?, ?, ?, ?)',
                      (meeting_id, insight_type, content, datetime.now().isoformat()))
        conn.commit()
        conn.close()


class WASAPILoopbackRecorder:
    """Captures SYSTEM AUDIO using WASAPI loopback - this is what you hear (other person's voice)"""

    def __init__(self, on_chunk_ready, on_error, on_status_update):
        self.on_chunk_ready = on_chunk_ready
        self.on_error = on_error
        self.on_status_update = on_status_update
        self.is_recording = False
        self.thread = None
        self.p = None
        self.stream = None
        self.loopback_device_info = None  # Store just device info, not PyAudio reference

    def _find_loopback_device_info(self, p):
        """Find loopback device using provided PyAudio instance"""
        if WPATCH_AVAILABLE:
            try:
                wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
                default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
                print(f"[SYSTEM] Default speakers: {default_speakers['name']}")

                for i in range(p.get_device_count()):
                    dev = p.get_device_info_by_index(i)
                    if dev.get("isLoopbackDevice", False):
                        if default_speakers["name"] in dev["name"]:
                            print(f"[SYSTEM] Found loopback: {dev['name']}")
                            return dev

                for i in range(p.get_device_count()):
                    dev = p.get_device_info_by_index(i)
                    if dev.get("isLoopbackDevice", False):
                        print(f"[SYSTEM] Using loopback: {dev['name']}")
                        return dev
            except Exception as e:
                print(f"[SYSTEM] WASAPI error: {e}")

        for i in range(p.get_device_count()):
            try:
                dev = p.get_device_info_by_index(i)
                name = dev.get("name", "").lower()
                if any(x in name for x in ["loopback", "stereo mix", "what u hear"]):
                    if dev.get("maxInputChannels", 0) > 0:
                        print(f"[SYSTEM] Found: {dev['name']}")
                        return dev
            except:
                pass
        return None

    def start(self):
        if not PYAUDIO_AVAILABLE:
            self.on_error("PyAudio not available")
            return False
        self.is_recording = True
        self.thread = threading.Thread(target=self._record_loop, daemon=True)
        self.thread.start()
        return True

    def _record_loop(self):
        """Recording loop - creates PyAudio instance in this thread"""
        try:
            # Create PyAudio instance in this thread (with lock to prevent concurrent init crash)
            with _pyaudio_lock:
                self.p = pyaudio.PyAudio()

            # Find loopback device
            self.loopback_device_info = self._find_loopback_device_info(self.p)
            if not self.loopback_device_info:
                self.on_error("No loopback device found")
                self.on_status_update("system", "error", "No loopback")
                self.p.terminate()
                return

            idx = self.loopback_device_info["index"]
            ch = int(self.loopback_device_info.get("maxInputChannels", 2))
            rate = int(self.loopback_device_info.get("defaultSampleRate", 44100))
            print(f"[SYSTEM] Opening: ch={ch}, rate={rate}")
            self.on_status_update("system", "connected", self.loopback_device_info["name"][:20])

            self.stream = self.p.open(format=pyaudio.paInt16, channels=ch, rate=rate,
                                      input=True, input_device_index=idx, frames_per_buffer=CHUNK_SIZE)
            frames = []
            chunks_needed = int(rate / CHUNK_SIZE * RECORD_SECONDS_PER_CHUNK)

            while self.is_recording:
                try:
                    data = self.stream.read(CHUNK_SIZE, exception_on_overflow=False)
                    frames.append(data)
                    audio_np = np.frombuffer(data, dtype=np.int16)
                    if np.max(np.abs(audio_np)) > 200:
                        self.on_status_update("system", "active", None)

                    if len(frames) >= chunks_needed:
                        all_data = b''.join(frames)
                        audio_np = np.frombuffer(all_data, dtype=np.int16)
                        if ch == 2:
                            audio_np = audio_np.reshape(-1, 2).mean(axis=1).astype(np.int16)
                        if rate != SAMPLE_RATE:
                            ratio = SAMPLE_RATE / rate
                            new_len = int(len(audio_np) * ratio)
                            indices = np.linspace(0, len(audio_np) - 1, new_len).astype(int)
                            audio_np = audio_np[indices]
                        if np.max(np.abs(audio_np)) > 100:
                            wav = self._to_wav(audio_np)
                            self.on_chunk_ready(wav, SPEAKER_HIM)
                        frames = []
                except Exception as e:
                    if self.is_recording:
                        print(f"[SYSTEM] Read error: {e}")
                    break
        except Exception as e:
            print(f"[SYSTEM] Error: {e}")
            self.on_status_update("system", "error", str(e)[:20])

    def _to_wav(self, audio_np):
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_np.tobytes())
        return buf.getvalue()

    def stop(self):
        self.is_recording = False
        # Wait for recording thread to finish
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        # Now safe to close stream
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except:
                pass
        if self.p:
            try:
                self.p.terminate()
            except:
                pass
        self.stream = None
        self.p = None


class MicrophoneRecorder:
    """Captures MICROPHONE audio - your voice"""

    def __init__(self, on_chunk_ready, on_error, on_status_update):
        self.on_chunk_ready = on_chunk_ready
        self.on_error = on_error
        self.on_status_update = on_status_update
        self.is_recording = False
        self.thread = None
        self.p = None
        self.stream = None

    def start(self):
        if not PYAUDIO_AVAILABLE:
            self.on_error("PyAudio not available")
            return False
        self.is_recording = True
        self.thread = threading.Thread(target=self._record_loop, daemon=True)
        self.thread.start()
        return True

    def _record_loop(self):
        try:
            # Create PyAudio instance with lock to prevent concurrent init crash
            with _pyaudio_lock:
                self.p = pyaudio.PyAudio()
            info = self.p.get_default_input_device_info()
            print(f"[MIC] Using: {info['name']}")
            self.on_status_update("mic", "connected", info['name'][:20])

            self.stream = self.p.open(format=pyaudio.paInt16, channels=1, rate=SAMPLE_RATE,
                                      input=True, frames_per_buffer=CHUNK_SIZE)
            frames = []
            chunks_needed = int(SAMPLE_RATE / CHUNK_SIZE * RECORD_SECONDS_PER_CHUNK)

            while self.is_recording:
                try:
                    data = self.stream.read(CHUNK_SIZE, exception_on_overflow=False)
                    frames.append(data)
                    audio_np = np.frombuffer(data, dtype=np.int16)
                    if np.max(np.abs(audio_np)) > 500:
                        self.on_status_update("mic", "active", None)

                    if len(frames) >= chunks_needed:
                        all_data = b''.join(frames)
                        audio_np = np.frombuffer(all_data, dtype=np.int16)
                        if np.max(np.abs(audio_np)) > 300:
                            wav = self._to_wav(frames)
                            self.on_chunk_ready(wav, SPEAKER_ME)
                        frames = []
                except Exception as e:
                    if self.is_recording:
                        print(f"[MIC] Read error: {e}")
                    break
        except Exception as e:
            print(f"[MIC] Error: {e}")
            self.on_status_update("mic", "error", str(e)[:20])

    def _to_wav(self, frames):
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(self.p.get_sample_size(pyaudio.paInt16))
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b''.join(frames))
        return buf.getvalue()

    def stop(self):
        self.is_recording = False
        # Wait for recording thread to finish
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        # Now safe to close stream
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except:
                pass
        if self.p:
            try:
                self.p.terminate()
            except:
                pass
        self.stream = None
        self.p = None


class ServiceClient:
    def __init__(self):
        self.session_id = f"session_{int(time.time())}"
        self.chunk_index = 0
        self.usage_stats = {"tokens": 0, "cost": 0.0, "requests": 0}

    def get_usage_stats(self):
        """Get token usage stats from LLM service"""
        try:
            with httpx.Client(timeout=5.0) as c:
                resp = c.get(f"{LLM_SERVICE}/stats")
                if resp.status_code == 200:
                    data = resp.json()
                    self.usage_stats = {
                        "tokens": data.get("summary", {}).get("total_tokens", 0),
                        "cost": data.get("summary", {}).get("total_cost_usd", 0.0),
                        "requests": data.get("summary", {}).get("requests", 0)
                    }
                    return self.usage_stats
        except:
            pass
        return self.usage_stats

    def check_services_sync(self):
        results = {}
        for name, url in [("transcription", TRANSCRIPTION_SERVICE), ("llm", LLM_SERVICE), ("rag", RAG_SERVICE)]:
            try:
                with httpx.Client(timeout=3.0) as c:
                    results[name] = c.get(f"{url}/health").status_code == 200
            except:
                results[name] = False
        return results

    def transcribe(self, audio_data, speaker_hint=None):
        try:
            with httpx.Client(timeout=30.0) as c:
                resp = c.post(f"{TRANSCRIPTION_SERVICE}/transcribe/stream", json={
                    "audio_chunk": base64.b64encode(audio_data).decode('utf-8'),
                    "session_id": self.session_id, "chunk_index": self.chunk_index,
                    "language": "en", "speaker_hint": speaker_hint})
                self.chunk_index += 1
                return resp.json() if resp.status_code == 200 else None
        except Exception as e:
            print(f"Transcribe error: {e}")
            return None

    def ask_llm(self, question, context=None):
        try:
            # Determine if question is about the meeting or a general question
            meeting_keywords = ['meeting', 'discuss', 'said', 'mentioned', 'talked', 'they', 'we', 'decision', 'action', 'topic']
            is_meeting_question = any(kw in question.lower() for kw in meeting_keywords)

            if is_meeting_question and context:
                prompt = f"""You are an AI assistant helping with a meeting. Answer the following question based on the meeting context provided.

MEETING CONTEXT:
{context}

QUESTION: {question}

Provide a clear, direct answer based on the meeting discussion. If the answer is not in the context, say so."""
            else:
                # General question - answer using general knowledge
                prompt = f"""You are a helpful AI assistant. Answer the following question clearly and accurately.

QUESTION: {question}

{f'ADDITIONAL CONTEXT (from ongoing meeting): {context}' if context else ''}

Provide a clear, informative answer. If this is a general knowledge question, use your knowledge to answer it directly. Be concise but thorough."""

            with httpx.Client(timeout=30.0) as c:
                resp = c.post(f"{LLM_SERVICE}/complete", json={
                    "prompt": prompt,
                    "task_type": "qa", "max_tokens": 800, "temperature": 0.7})
                return resp.json().get('text', '') if resp.status_code == 200 else None
        except:
            return None

    def get_insights(self, text, context=None):
        try:
            with httpx.Client(timeout=30.0) as c:
                resp = c.post(f"{LLM_SERVICE}/complete", json={
                    "prompt": f'Analyze briefly:\n{text}\nReturn JSON: {{"topics":[],"key_points":[],"sentiment":"neutral"}}',
                    "task_type": "extraction", "max_tokens": 500, "temperature": 0.5})
                if resp.status_code == 200:
                    try:
                        return json.loads(resp.json().get('text', '{}'))
                    except:
                        return {"summary": resp.json().get('text', '')}
        except:
            return None

    def summarize(self, transcript):
        try:
            with httpx.Client(timeout=60.0) as c:
                resp = c.post(f"{LLM_SERVICE}/summarize", json={"transcript": transcript, "max_tokens": 3000})
                return resp.json() if resp.status_code == 200 else None
        except:
            return None


class NexusOverlay:
    COLORS = {
        'bg_primary': '#FFFFFF', 'bg_secondary': '#F8FAFC', 'bg_tertiary': '#F1F5F9',
        'text_primary': '#1E293B', 'text_secondary': '#64748B', 'text_muted': '#94A3B8',
        'accent_primary': '#3B82F6', 'accent_success': '#10B981', 'accent_warning': '#F59E0B',
        'accent_danger': '#EF4444', 'accent_info': '#6366F1', 'border': '#E2E8F0',
        'speaker_me': '#059669', 'speaker_him': '#7C3AED',
    }

    def __init__(self):
        self.root = tk.Tk()
        self.setup_window()
        self.is_recording = False
        self.full_transcript = []
        self.speakers = set()
        self.start_time = None
        self.recent_text = ""
        self.accumulated_text = ""
        self.last_insight_time = 0
        self.meeting_id = None
        self.mic_recorder = None
        self.system_recorder = None
        self.service_client = ServiceClient()
        self.transcript_queue = queue.Queue()
        self.insight_queue = queue.Queue()
        self.db = MeetingDatabase()
        self.latest_insights = {}  # Store latest insights for keyword details
        self.create_widgets()
        self.root.after(1000, self.check_services)
        self.root.after(2000, self.update_usage_display)  # Start usage tracking
        self.process_queues()

    def setup_window(self):
        self.root.title("Nexus")
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.expanded = True  # Track expanded/collapsed state
        self.full_height = 380
        self.collapsed_height = 280
        # Compact size positioned at top-right
        self.root.geometry(f"340x{self.full_height}+{sw-360}+20")
        # Transparent so content below is visible
        self.root.attributes('-alpha', 0.92, '-topmost', True)
        self.root.configure(bg=self.COLORS['bg_primary'])

    def create_widgets(self):
        self.main = tk.Frame(self.root, bg=self.COLORS['bg_primary'])
        self.main.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        # ===== COMPACT CONTROL BAR (like media player) =====
        ctrl_bar = tk.Frame(self.main, bg=self.COLORS['bg_primary'])
        ctrl_bar.pack(fill=tk.X, pady=(0, 6))

        # Record button (circle icon)
        self.rec_btn = tk.Label(ctrl_bar, text="⏺", font=('Segoe UI', 16),
                               fg=self.COLORS['accent_success'], bg=self.COLORS['bg_primary'],
                               cursor='hand2', padx=4)
        self.rec_btn.pack(side=tk.LEFT)
        self.rec_btn.bind('<Button-1>', lambda e: self.toggle_rec())
        self.rec_btn.bind('<Enter>', lambda e: self.rec_btn.config(fg='#059669' if not self.is_recording else '#DC2626'))
        self.rec_btn.bind('<Leave>', lambda e: self.rec_btn.config(fg=self.COLORS['accent_danger'] if self.is_recording else self.COLORS['accent_success']))

        # Duration
        self.duration_label = tk.Label(ctrl_bar, text="00:00", font=('Consolas', 10),
                                      fg=self.COLORS['text_muted'], bg=self.COLORS['bg_primary'])
        self.duration_label.pack(side=tk.LEFT, padx=(4, 8))

        # Audio indicators (tiny dots)
        self.mic_indicator = tk.Label(ctrl_bar, text="●", font=('Segoe UI', 8),
                                     fg=self.COLORS['text_muted'], bg=self.COLORS['bg_primary'])
        self.mic_indicator.pack(side=tk.LEFT, padx=1)
        self.sys_indicator = tk.Label(ctrl_bar, text="●", font=('Segoe UI', 8),
                                     fg=self.COLORS['text_muted'], bg=self.COLORS['bg_primary'])
        self.sys_indicator.pack(side=tk.LEFT, padx=1)

        # Status text (compact)
        self.status_label = tk.Label(ctrl_bar, text="Ready", font=('Segoe UI', 8),
                                    fg=self.COLORS['text_muted'], bg=self.COLORS['bg_primary'])
        self.status_label.pack(side=tk.LEFT, padx=(8, 0))

        # Token usage display (compact)
        self.usage_frame = tk.Frame(ctrl_bar, bg=self.COLORS['bg_tertiary'], padx=4, pady=1)
        self.usage_frame.pack(side=tk.LEFT, padx=(8, 0))
        self.token_label = tk.Label(self.usage_frame, text="0 tok", font=('Consolas', 7),
                                   fg=self.COLORS['text_muted'], bg=self.COLORS['bg_tertiary'])
        self.token_label.pack(side=tk.LEFT)
        tk.Label(self.usage_frame, text="|", font=('Consolas', 7),
                fg=self.COLORS['border'], bg=self.COLORS['bg_tertiary']).pack(side=tk.LEFT, padx=2)
        self.cost_label = tk.Label(self.usage_frame, text="$0.00", font=('Consolas', 7),
                                  fg=self.COLORS['accent_success'], bg=self.COLORS['bg_tertiary'])
        self.cost_label.pack(side=tk.LEFT)

        # Right side controls
        # Expand/Collapse toggle
        self.toggle_btn = tk.Label(ctrl_bar, text="▼", font=('Segoe UI', 10),
                                  fg=self.COLORS['text_secondary'], bg=self.COLORS['bg_primary'],
                                  cursor='hand2', padx=4)
        self.toggle_btn.pack(side=tk.RIGHT)
        self.toggle_btn.bind('<Button-1>', lambda e: self.toggle_expand())

        # Dashboard link (icon)
        dash = tk.Label(ctrl_bar, text="☰", font=('Segoe UI', 12),
                       fg=self.COLORS['text_secondary'], bg=self.COLORS['bg_primary'], cursor='hand2', padx=4)
        dash.pack(side=tk.RIGHT)
        dash.bind('<Button-1>', self.open_dashboard)

        # Clear button (icon)
        clr = tk.Label(ctrl_bar, text="⟲", font=('Segoe UI', 12),
                      fg=self.COLORS['text_secondary'], bg=self.COLORS['bg_primary'], cursor='hand2', padx=4)
        clr.pack(side=tk.RIGHT)
        clr.bind('<Button-1>', lambda e: self.clear())

        # Summary button (icon)
        self.sum_btn = tk.Label(ctrl_bar, text="📋", font=('Segoe UI', 10),
                               fg=self.COLORS['text_muted'], bg=self.COLORS['bg_primary'], cursor='hand2', padx=4)
        self.sum_btn.pack(side=tk.RIGHT)
        self.sum_btn.bind('<Button-1>', lambda e: self.show_summary() if self.full_transcript else None)

        # ===== TAB SWITCHER (compact) =====
        tab_bar = tk.Frame(self.main, bg=self.COLORS['bg_tertiary'])
        tab_bar.pack(fill=tk.X, pady=(0, 4))

        self.tab_insights = tk.Label(tab_bar, text="Insights", font=('Segoe UI', 9, 'bold'),
                                    fg=self.COLORS['accent_primary'], bg=self.COLORS['bg_primary'],
                                    padx=12, pady=4, cursor='hand2')
        self.tab_insights.pack(side=tk.LEFT)
        self.tab_insights.bind('<Button-1>', lambda e: self.switch_tab('insights'))

        self.tab_transcript = tk.Label(tab_bar, text="Live", font=('Segoe UI', 9),
                                      fg=self.COLORS['text_secondary'], bg=self.COLORS['bg_tertiary'],
                                      padx=12, pady=4, cursor='hand2')
        self.tab_transcript.pack(side=tk.LEFT)
        self.tab_transcript.bind('<Button-1>', lambda e: self.switch_tab('transcript'))

        # Service status (tiny)
        self.svc_label = tk.Label(tab_bar, text="●", font=('Segoe UI', 8),
                                 fg=self.COLORS['text_muted'], bg=self.COLORS['bg_tertiary'])
        self.svc_label.pack(side=tk.RIGHT, padx=6)

        # ===== CONTENT CONTAINER =====
        self.content = tk.Frame(self.main, bg=self.COLORS['bg_primary'])
        self.content.pack(fill=tk.BOTH, expand=True)

        # Initialize keywords list
        self.current_keywords = []
        self.keyword_buttons = []
        self.current_tab = 'insights'

        # ----- INSIGHTS VIEW -----
        self.insights_frame = tk.Frame(self.content, bg=self.COLORS['bg_primary'])
        self.insights_frame.pack(fill=tk.BOTH, expand=True)

        # Insights text area with scroll (bigger font)
        self.insights = scrolledtext.ScrolledText(self.insights_frame, wrap=tk.WORD, font=('Segoe UI', 10),
                                                 bg=self.COLORS['bg_secondary'], fg=self.COLORS['text_primary'],
                                                 relief=tk.FLAT, padx=10, pady=8, height=10)
        self.insights.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))
        self.insights.config(state=tk.DISABLED)
        # Text tags (bigger fonts)
        self.insights.tag_configure('title', foreground=self.COLORS['accent_primary'], font=('Segoe UI', 13, 'bold'))
        self.insights.tag_configure('heading', foreground=self.COLORS['accent_info'], font=('Segoe UI', 11, 'bold'))
        self.insights.tag_configure('subheading', foreground=self.COLORS['text_primary'], font=('Segoe UI', 10, 'bold'))
        self.insights.tag_configure('bold', foreground=self.COLORS['text_primary'], font=('Segoe UI', 10, 'bold'))
        self.insights.tag_configure('keyword_highlight', foreground=self.COLORS['speaker_him'], font=('Segoe UI', 10, 'bold'))
        self.insights.tag_configure('normal', foreground=self.COLORS['text_primary'], font=('Segoe UI', 10))
        self.insights.tag_configure('bullet', foreground=self.COLORS['speaker_me'], font=('Segoe UI', 10))
        self.insights.tag_configure('muted', foreground=self.COLORS['text_muted'], font=('Segoe UI', 9, 'italic'))
        self.insight_stat = tk.Label(self.insights_frame, text="", font=('Segoe UI', 8),
                                    fg=self.COLORS['text_muted'], bg=self.COLORS['bg_primary'])

        # ===== MINI KEYWORDS (always visible, even collapsed) =====
        self.mini_keywords_frame = tk.Frame(self.main, bg=self.COLORS['bg_tertiary'])
        self.mini_keywords_frame.pack(fill=tk.X, pady=(4, 0), ipady=3)

        tk.Label(self.mini_keywords_frame, text="💡", font=('Segoe UI', 9),
                fg=self.COLORS['text_muted'], bg=self.COLORS['bg_tertiary']).pack(side=tk.LEFT, padx=(4, 2))

        # Mini keywords container (shows 3 keywords)
        self.mini_keywords_container = tk.Frame(self.mini_keywords_frame, bg=self.COLORS['bg_tertiary'])
        self.mini_keywords_container.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.mini_keywords_placeholder = tk.Label(self.mini_keywords_container, text="Keywords...",
                                                  font=('Segoe UI', 8, 'italic'), fg=self.COLORS['text_muted'],
                                                  bg=self.COLORS['bg_tertiary'])
        self.mini_keywords_placeholder.pack(side=tk.LEFT, pady=2)
        self.mini_keyword_buttons = []

        # ===== EXPANDABLE SECTION =====
        self.expand_frame = tk.Frame(self.main, bg=self.COLORS['bg_primary'])
        self.expand_frame.pack(fill=tk.X, pady=(4, 0))

        # Ask AI (compact)
        ask_frame = tk.Frame(self.expand_frame, bg=self.COLORS['bg_tertiary'])
        ask_frame.pack(fill=tk.X, pady=(0, 4))
        self.ask_entry = tk.Entry(ask_frame, font=('Segoe UI', 9), bg=self.COLORS['bg_primary'],
                                 fg=self.COLORS['text_primary'], relief=tk.FLAT,
                                 highlightthickness=1, highlightbackground=self.COLORS['border'])
        self.ask_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4, pady=4, ipady=3)
        self.ask_entry.insert(0, "Ask AI...")
        self.ask_entry.bind('<FocusIn>', lambda e: self.ask_entry.delete(0, tk.END) if self.ask_entry.get() == "Ask AI..." else None)
        self.ask_entry.bind('<FocusOut>', lambda e: self.ask_entry.insert(0, "Ask AI...") if not self.ask_entry.get() else None)
        self.ask_entry.bind('<Return>', self.on_ask)
        self.ask_btn = tk.Label(ask_frame, text="→", font=('Segoe UI', 12), fg=self.COLORS['accent_primary'],
                bg=self.COLORS['bg_tertiary'], cursor='hand2', padx=6)
        self.ask_btn.pack(side=tk.RIGHT)
        self.ask_btn.bind('<Button-1>', lambda e: self.on_ask(None))

        # Full Keywords/Suggestions (in expanded view)
        self.keywords_container = tk.Frame(self.expand_frame, bg=self.COLORS['bg_tertiary'])
        self.keywords_container.pack(fill=tk.X, pady=(0, 2), ipady=4, ipadx=4)
        self.keywords_placeholder = tk.Label(self.keywords_container, text="All suggestions...",
                                            font=('Segoe UI', 8, 'italic'), fg=self.COLORS['text_muted'],
                                            bg=self.COLORS['bg_tertiary'])
        self.keywords_placeholder.pack(pady=2)

        # Quick action buttons (compact)
        action_frame = tk.Frame(self.expand_frame, bg=self.COLORS['bg_primary'])
        action_frame.pack(fill=tk.X)
        self.analysis_btn = tk.Label(action_frame, text="📊 Analysis", font=('Segoe UI', 8),
                                    fg=self.COLORS['accent_info'], bg=self.COLORS['bg_tertiary'],
                                    padx=8, pady=3, cursor='hand2')
        self.analysis_btn.pack(side=tk.LEFT, padx=(0, 4))
        self.analysis_btn.bind('<Button-1>', lambda e: self.show_full_analysis())

        # ----- TRANSCRIPT VIEW (hidden by default) -----
        self.transcript_frame = tk.Frame(self.content, bg=self.COLORS['bg_primary'])

        # Segment count
        self.seg_count = tk.Label(self.transcript_frame, text="0", font=('Segoe UI', 8),
                                 fg=self.COLORS['text_muted'], bg=self.COLORS['bg_primary'])

        # Transcript text area (bigger font)
        self.transcript = scrolledtext.ScrolledText(self.transcript_frame, wrap=tk.WORD, font=('Segoe UI', 10),
                                                   bg=self.COLORS['bg_secondary'], fg=self.COLORS['text_primary'],
                                                   relief=tk.FLAT, padx=10, pady=8)
        self.transcript.pack(fill=tk.BOTH, expand=True, padx=4)
        self.transcript.tag_configure('me', foreground=self.COLORS['speaker_me'], font=('Segoe UI', 10, 'bold'))
        self.transcript.tag_configure('him', foreground=self.COLORS['speaker_him'], font=('Segoe UI', 10, 'bold'))
        self.transcript.tag_configure('sys', foreground=self.COLORS['text_muted'], font=('Segoe UI', 9, 'italic'))
        self.transcript.tag_configure('ts', foreground=self.COLORS['text_muted'], font=('Segoe UI', 8))

    def switch_tab(self, tab):
        """Switch between Insights and Live Transcript"""
        self.current_tab = tab
        if tab == 'insights':
            self.transcript_frame.pack_forget()
            self.insights_frame.pack(fill=tk.BOTH, expand=True)
            self.expand_frame.pack(fill=tk.X, pady=(4, 0))
            self.tab_insights.config(fg=self.COLORS['accent_primary'], bg=self.COLORS['bg_primary'], font=('Segoe UI', 9, 'bold'))
            self.tab_transcript.config(fg=self.COLORS['text_secondary'], bg=self.COLORS['bg_tertiary'], font=('Segoe UI', 9))
        else:
            self.insights_frame.pack_forget()
            self.expand_frame.pack_forget()
            self.transcript_frame.pack(fill=tk.BOTH, expand=True)
            self.tab_transcript.config(fg=self.COLORS['accent_primary'], bg=self.COLORS['bg_primary'], font=('Segoe UI', 9, 'bold'))
            self.tab_insights.config(fg=self.COLORS['text_secondary'], bg=self.COLORS['bg_tertiary'], font=('Segoe UI', 9))

    def toggle_expand(self):
        """Toggle between expanded and collapsed view"""
        sw = self.root.winfo_screenwidth()
        if self.expanded:
            self.expand_frame.pack_forget()
            self.root.geometry(f"340x{self.collapsed_height}+{sw-360}+20")
            self.toggle_btn.config(text="▲")
            self.expanded = False
        else:
            if self.current_tab == 'insights':
                self.expand_frame.pack(fill=tk.X, pady=(4, 0))
            self.root.geometry(f"340x{self.full_height}+{sw-360}+20")
            self.toggle_btn.config(text="▼")
            self.expanded = True

    def _sys_msg(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.transcript.insert(tk.END, f"[{ts}] {msg}\n", 'sys')
        self.transcript.see(tk.END)

    def check_services(self):
        def chk():
            if HTTPX_AVAILABLE:
                st = self.service_client.check_services_sync()
                on = sum(st.values())
                clr = self.COLORS['accent_success'] if on == 3 else self.COLORS['accent_warning'] if on > 0 else self.COLORS['accent_danger']
                self.root.after(0, lambda: self.svc_label.config(fg=clr))
        threading.Thread(target=chk, daemon=True).start()
        self.root.after(30000, self.check_services)

    def update_usage_display(self):
        """Update token usage and cost display"""
        def fetch():
            if HTTPX_AVAILABLE:
                stats = self.service_client.get_usage_stats()
                tokens = stats.get("tokens", 0)
                cost = stats.get("cost", 0.0)

                # Format tokens (K for thousands)
                if tokens >= 1000:
                    tok_str = f"{tokens/1000:.1f}K"
                else:
                    tok_str = f"{tokens}"

                # Format cost
                if cost >= 0.01:
                    cost_str = f"${cost:.2f}"
                else:
                    cost_str = f"${cost:.4f}"

                # Color based on cost
                if cost < 0.01:
                    cost_color = self.COLORS['accent_success']
                elif cost < 0.10:
                    cost_color = self.COLORS['accent_warning']
                else:
                    cost_color = self.COLORS['accent_danger']

                def update_ui():
                    try:
                        if self.root.winfo_exists():
                            self.token_label.config(text=f"{tok_str} tok")
                            self.cost_label.config(text=cost_str, fg=cost_color)
                    except:
                        pass
                self.root.after(0, update_ui)

        threading.Thread(target=fetch, daemon=True).start()
        # Update every 10 seconds
        if self.root.winfo_exists():
            self.root.after(10000, self.update_usage_display)

    def on_status(self, src, stat, det):
        def upd():
            try:
                if not self.root.winfo_exists():
                    return
                if src == "mic":
                    if stat == "connected":
                        self.mic_indicator.config(fg=self.COLORS['speaker_me'])
                    elif stat == "active":
                        self.mic_indicator.config(fg='#10B981')
                        self.root.after(300, lambda: self.mic_indicator.config(fg=self.COLORS['speaker_me']) if self.root.winfo_exists() else None)
                    elif stat == "error":
                        self.mic_indicator.config(fg=self.COLORS['accent_danger'])
                else:
                    if stat == "connected":
                        self.sys_indicator.config(fg=self.COLORS['speaker_him'])
                    elif stat == "active":
                        self.sys_indicator.config(fg='#8B5CF6')
                        self.root.after(300, lambda: self.sys_indicator.config(fg=self.COLORS['speaker_him']) if self.root.winfo_exists() else None)
                    elif stat == "error":
                        self.sys_indicator.config(fg=self.COLORS['accent_danger'])
            except Exception as e:
                print(f"[UI] Status update error: {e}")
        try:
            self.root.after(0, upd)
        except Exception:
            pass

    def toggle_rec(self):
        if not self.is_recording:
            self.start_rec()
        else:
            self.stop_rec()

    def start_rec(self):
        try:
            self._sys_msg("Starting...")
            self.meeting_id = self.db.create_meeting(f"Meeting {datetime.now().strftime('%Y-%m-%d %H:%M')}")

            self.mic_recorder = MicrophoneRecorder(self.on_chunk, self.on_err, self.on_status)
            self.system_recorder = WASAPILoopbackRecorder(self.on_chunk, self.on_err, self.on_status)

            mic_ok = self.mic_recorder.start()
            sys_ok = self.system_recorder.start()

            if not mic_ok and not sys_ok:
                self._sys_msg("ERROR: No audio!")
                messagebox.showerror("Error", "No audio capture available!")
                return

            self.is_recording = True
            self.start_time = time.time()
            self.full_transcript = []
            self.speakers = set()
            self.accumulated_text = ""
            self.status_label.config(text="●REC", fg=self.COLORS['accent_danger'])
            self.rec_btn.config(text="⏹", fg=self.COLORS['accent_danger'])
            self.sum_btn.config(fg=self.COLORS['text_muted'])
            self._sys_msg("Recording started")
            self.upd_dur()
            self.sched_insights()
        except Exception as e:
            self._sys_msg(f"ERROR: {e}")
            messagebox.showerror("Error", f"Failed to start:\n{e}")

    def stop_rec(self):
        self.is_recording = False
        if self.mic_recorder:
            self.mic_recorder.stop()
            self.mic_recorder = None
        if self.system_recorder:
            self.system_recorder.stop()
            self.system_recorder = None
        if self.meeting_id and self.start_time:
            self.db.update_meeting(self.meeting_id, int(time.time() - self.start_time), list(self.speakers), 'completed')
        self.status_label.config(text="Ready", fg=self.COLORS['text_muted'])
        self.mic_indicator.config(fg=self.COLORS['text_muted'])
        self.sys_indicator.config(fg=self.COLORS['text_muted'])
        self.rec_btn.config(text="⏺", fg=self.COLORS['accent_success'])
        self._sys_msg("Stopped")
        if self.full_transcript:
            self.sum_btn.config(fg=self.COLORS['accent_info'])

    def on_chunk(self, data, speaker):
        def proc():
            try:
                res = self.service_client.transcribe(data, speaker)
                if res and 'segments' in res:
                    for seg in res['segments']:
                        seg['speaker'] = speaker
                        self.transcript_queue.put(seg)
            except Exception as e:
                print(f"[TRANSCRIBE] Error: {e}")
        threading.Thread(target=proc, daemon=True).start()

    def on_err(self, msg):
        try:
            if self.root.winfo_exists():
                self.root.after(0, lambda: self._sys_msg(f"Error: {msg}"))
        except Exception:
            print(f"[ERROR] {msg}")

    def process_queues(self):
        try:
            if not self.root.winfo_exists():
                return
            while True:
                seg = self.transcript_queue.get_nowait()
                self.add_seg(seg)
        except queue.Empty:
            pass
        except Exception as e:
            print(f"[QUEUE] Segment error: {e}")
        try:
            while True:
                ins = self.insight_queue.get_nowait()
                self.show_ins(ins)
        except queue.Empty:
            pass
        except Exception as e:
            print(f"[QUEUE] Insight error: {e}")
        try:
            if self.root.winfo_exists():
                self.root.after(100, self.process_queues)
        except Exception:
            pass

    def add_seg(self, seg):
        spk, txt = seg.get('speaker', '?'), seg.get('text', '').strip()
        if not txt:
            return
        self.speakers.add(spk)
        self.full_transcript.append({'speaker': spk, 'text': txt, 'timestamp': datetime.now().isoformat()})
        self.recent_text = (self.recent_text + " " + txt)[-2000:]
        self.accumulated_text += f" [{spk}]: {txt}"
        if self.meeting_id:
            self.db.add_transcript(self.meeting_id, spk, txt, seg.get('start_ms', 0), seg.get('end_ms', 0))
        tag = 'me' if spk == SPEAKER_ME else 'him'
        ts = datetime.now().strftime("%H:%M:%S")
        self.transcript.insert(tk.END, f"[{ts}] ", 'ts')
        self.transcript.insert(tk.END, f"{spk}: ", tag)
        self.transcript.insert(tk.END, f"{txt}\n")
        self.transcript.see(tk.END)
        self.seg_count.config(text=f"{len(self.full_transcript)} segments")

    def sched_insights(self):
        if not self.is_recording:
            return
        if len(self.accumulated_text) > 100 and time.time() - self.last_insight_time > 10:
            self.gen_insights()
            self.last_insight_time = time.time()
            self.accumulated_text = ""
        self.root.after(5000, self.sched_insights)

    def gen_insights(self):
        txt = self.accumulated_text
        def proc():
            self.root.after(0, lambda: self.insight_stat.config(text="Analyzing..."))
            ins = self.service_client.get_insights(txt, self.recent_text)
            if ins:
                self.insight_queue.put(ins)
                if self.meeting_id:
                    self.db.add_insight(self.meeting_id, "analysis", json.dumps(ins))
            self.root.after(0, lambda: self.insight_stat.config(text="Listening..."))
        threading.Thread(target=proc, daemon=True).start()

    def show_ins(self, ins):
        # Common words to filter out (not technical/meaningful)
        STOP_WORDS = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
            'ought', 'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by',
            'from', 'as', 'into', 'through', 'during', 'before', 'after', 'above',
            'below', 'between', 'under', 'again', 'further', 'then', 'once',
            'here', 'there', 'when', 'where', 'why', 'how', 'all', 'each', 'few',
            'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only',
            'own', 'same', 'so', 'than', 'too', 'very', 'just', 'and', 'but',
            'if', 'or', 'because', 'until', 'while', 'this', 'that', 'these',
            'those', 'am', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'what',
            'which', 'who', 'whom', 'me', 'him', 'her', 'us', 'them', 'my', 'your',
            'his', 'its', 'our', 'their', 'mine', 'yours', 'hers', 'ours', 'theirs',
            'explanation', 'about', 'also', 'like', 'get', 'got', 'getting',
            'make', 'made', 'making', 'thing', 'things', 'something', 'anything',
            'everything', 'nothing', 'someone', 'anyone', 'everyone', 'one', 'two',
            'first', 'second', 'new', 'old', 'good', 'bad', 'right', 'left',
            'going', 'know', 'think', 'want', 'see', 'look', 'use', 'using',
            'way', 'well', 'back', 'even', 'still', 'already', 'now', 'today'
        }

        def is_technical_keyword(kw):
            """Check if keyword is technical/meaningful (not common word)"""
            if not kw or len(kw) < 3:
                return False
            words = kw.lower().split()
            # Filter out if all words are stop words
            meaningful_words = [w for w in words if w not in STOP_WORDS and len(w) > 2]
            return len(meaningful_words) > 0

        # Extract keywords from topics and key_points
        new_keywords = []
        if ins.get('topics'):
            for topic in ins['topics'][:3]:
                if is_technical_keyword(topic):
                    new_keywords.append(topic)
        if ins.get('key_points'):
            # Extract key terms from key points
            for point in ins['key_points'][:3]:
                words = point.split()
                # Find technical words/phrases
                for i, word in enumerate(words):
                    if len(word) > 4 and word.lower() not in STOP_WORDS:
                        # Take word with context if available
                        phrase = word
                        if i + 1 < len(words) and words[i+1].lower() not in STOP_WORDS:
                            phrase = f"{word} {words[i+1]}"
                        if is_technical_keyword(phrase):
                            new_keywords.append(phrase)
                            break

        # Update keyword chips (keep max 5, remove old ones as new come in)
        if new_keywords:
            self.update_keywords(new_keywords)

        # Store the latest insights for display when keyword is clicked
        self.latest_insights = ins

    def update_keywords(self, new_keywords):
        """Update keyword chips - keeps max 5, removes old ones"""
        # Add new keywords, keeping only the last 5
        for kw in new_keywords:
            if kw and kw not in self.current_keywords:
                self.current_keywords.append(kw)

        # Keep only the last 5 keywords
        self.current_keywords = self.current_keywords[-5:]

        # Clear existing buttons (both mini and full)
        for btn in self.keyword_buttons:
            btn.destroy()
        self.keyword_buttons = []

        for btn in self.mini_keyword_buttons:
            btn.destroy()
        self.mini_keyword_buttons = []

        # Update both containers if we have keywords
        if self.current_keywords:
            self.keywords_placeholder.pack_forget()
            self.mini_keywords_placeholder.pack_forget()

            # Create full keyword chips (all 5)
            for kw in self.current_keywords:
                btn = tk.Label(self.keywords_container, text=kw, font=('Segoe UI', 8),
                              fg=self.COLORS['accent_primary'], bg='#E0E7FF',
                              padx=8, pady=4, cursor='hand2')
                btn.pack(side=tk.LEFT, padx=2, pady=2)
                btn.bind('<Button-1>', lambda e, k=kw: self.on_keyword_click(k))
                btn.bind('<Enter>', lambda e, b=btn: b.config(bg='#C7D2FE'))
                btn.bind('<Leave>', lambda e, b=btn: b.config(bg='#E0E7FF'))
                self.keyword_buttons.append(btn)

            # Create mini keyword chips (last 3 only, for collapsed view)
            for kw in self.current_keywords[-3:]:
                # Truncate long keywords for mini view
                display_kw = kw[:15] + "..." if len(kw) > 15 else kw
                btn = tk.Label(self.mini_keywords_container, text=display_kw, font=('Segoe UI', 8),
                              fg=self.COLORS['accent_primary'], bg='#E0E7FF',
                              padx=6, pady=2, cursor='hand2')
                btn.pack(side=tk.LEFT, padx=2)
                btn.bind('<Button-1>', lambda e, k=kw: self.on_keyword_click(k))
                btn.bind('<Enter>', lambda e, b=btn: b.config(bg='#C7D2FE'))
                btn.bind('<Leave>', lambda e, b=btn: b.config(bg='#E0E7FF'))
                self.mini_keyword_buttons.append(btn)
        else:
            self.keywords_placeholder.pack(pady=2)
            self.mini_keywords_placeholder.pack(side=tk.LEFT, pady=2)

    def on_keyword_click(self, keyword):
        """Show details about a keyword in the insights text area"""
        self.insights.config(state=tk.NORMAL)
        self.insights.delete(1.0, tk.END)

        self.insights.insert(tk.END, f"{keyword}\n", 'title')
        self.insights.insert(tk.END, "─" * 30 + "\n\n", 'muted')
        self.insights.insert(tk.END, "Analyzing...\n", 'muted')
        self.insights.config(state=tk.DISABLED)

        # Get details about this keyword from LLM
        def get_details():
            # Use full transcript for better context
            full_context = ""
            if self.full_transcript:
                full_context = "\n".join([f"[{s['speaker']}]: {s['text']}" for s in self.full_transcript[-20:]])
            else:
                full_context = self.recent_text

            prompt = f"""You are analyzing a meeting transcript. Focus on the technical term/concept: '{keyword}'.

MEETING TRANSCRIPT (recent):
{full_context}

Provide a clear, technical explanation about '{keyword}' based on the meeting discussion:

1. DEFINITION: What is {keyword}? (technical definition)
2. CONTEXT: How was it discussed in this meeting?
3. KEY DETAILS: Important technical points mentioned
4. IMPLICATIONS: What does this mean for the project/discussion?

Keep response concise and technical. Bold/highlight important terms. Use bullet points for lists."""

            details = self.service_client.ask_llm(prompt, full_context)

            def update_ui():
                self.insights.config(state=tk.NORMAL)
                self.insights.delete(1.0, tk.END)

                # Title with keyword highlighted
                self.insights.insert(tk.END, f"{keyword}\n", 'title')
                self.insights.insert(tk.END, "─" * 30 + "\n\n", 'muted')

                if details:
                    # Parse and format the response with keyword highlights
                    self._format_details(details, keyword)
                else:
                    self.insights.insert(tk.END, "No details available.\n", 'normal')

                self.insights.config(state=tk.DISABLED)
                self.insights.see("1.0")

            self.root.after(0, update_ui)

        threading.Thread(target=get_details, daemon=True).start()

    def _format_details(self, text, keyword):
        """Format the details text with proper styling and keyword highlights"""
        # Remove asterisks used for markdown formatting
        text = text.replace('**', '').replace('*', '')
        lines = text.split('\n')
        prev_empty = False

        for line in lines:
            stripped = line.strip()
            if not stripped:
                # Reduce consecutive empty lines
                if not prev_empty:
                    self.insights.insert(tk.END, "\n")
                    prev_empty = True
                continue
            prev_empty = False

            # Check for section headers (numbered or with colons)
            is_header = False
            header_patterns = ['SUMMARY', 'KEY POINTS', 'DECISIONS', 'ACTION ITEMS', 'CONTEXT',
                             'DEFINITION', 'IMPLICATIONS', 'KEY DETAILS', 'MAIN TOPICS',
                             '1.', '2.', '3.', '4.', '5.']
            for pattern in header_patterns:
                if stripped.upper().startswith(pattern) or pattern in stripped.upper()[:20]:
                    is_header = True
                    break

            if is_header and ':' in stripped:
                # Section header
                parts = stripped.split(':', 1)
                self.insights.insert(tk.END, f"{parts[0]}:", 'heading')
                if len(parts) > 1 and parts[1].strip():
                    self.insights.insert(tk.END, " ")
                    self._insert_with_keyword_highlight(parts[1].strip() + "\n", keyword)
                else:
                    self.insights.insert(tk.END, "\n")
            elif stripped.startswith('•') or stripped.startswith('-'):
                # Bullet point
                self.insights.insert(tk.END, "• ", 'bullet')
                self._insert_with_keyword_highlight(stripped[1:].strip() + "\n", keyword)
            elif is_header:
                self.insights.insert(tk.END, f"{stripped}\n", 'heading')
            else:
                # Regular text
                self._insert_with_keyword_highlight(stripped + "\n", keyword)

    def _insert_with_keyword_highlight(self, text, keyword):
        """Insert text with keyword highlighted in bold"""
        if not keyword or keyword.lower() not in text.lower():
            self.insights.insert(tk.END, text, 'normal')
            return

        # Find and highlight keyword occurrences (case-insensitive)
        import re
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        last_end = 0

        for match in pattern.finditer(text):
            # Insert text before match
            if match.start() > last_end:
                self.insights.insert(tk.END, text[last_end:match.start()], 'normal')
            # Insert highlighted keyword
            self.insights.insert(tk.END, match.group(), 'keyword_highlight')
            last_end = match.end()

        # Insert remaining text
        if last_end < len(text):
            self.insights.insert(tk.END, text[last_end:], 'normal')

    def show_full_analysis(self):
        """Show comprehensive analysis of the meeting discussion"""
        if not self.full_transcript:
            messagebox.showinfo("No Data", "Start recording first to get meeting analysis.")
            return

        self.analysis_btn.config(text="⏳...")
        self.insights.config(state=tk.NORMAL)
        self.insights.delete(1.0, tk.END)
        self.insights.insert(tk.END, "Meeting Analysis\n", 'title')
        self.insights.insert(tk.END, "─" * 40 + "\n\n", 'muted')
        self.insights.insert(tk.END, "Generating comprehensive analysis...\n", 'muted')
        self.insights.config(state=tk.DISABLED)

        def get_analysis():
            transcript_text = "\n".join([f"[{s['speaker']}]: {s['text']}" for s in self.full_transcript])

            prompt = f"""Analyze this meeting transcript and provide a comprehensive summary:

{transcript_text}

Please provide a well-organized analysis with these sections:

MAIN TOPICS:
- List the key topics discussed

KEY POINTS & DECISIONS:
- Important points made
- Decisions reached

ACTION ITEMS:
- Tasks or follow-ups mentioned

PARTICIPANTS:
- What each speaker (Me, Him) contributed

SENTIMENT:
- The tone and mood of the discussion

RECOMMENDATIONS:
- Suggestions for follow-up

Use bullet points for lists. Be concise but thorough."""

            analysis = self.service_client.ask_llm(prompt, transcript_text)

            def update_ui():
                self.insights.config(state=tk.NORMAL)
                self.insights.delete(1.0, tk.END)
                self.insights.insert(tk.END, "Meeting Analysis\n", 'title')
                self.insights.insert(tk.END, "─" * 40 + "\n\n", 'muted')
                if analysis:
                    self._format_details(analysis, None)
                else:
                    self.insights.insert(tk.END, "Unable to generate analysis. Please try again.\n", 'normal')
                self.insights.config(state=tk.DISABLED)
                self.insights.see("1.0")
                self.analysis_btn.config(text="📊 Analysis")

            self.root.after(0, update_ui)

        threading.Thread(target=get_analysis, daemon=True).start()

    def on_ask(self, e):
        q = self.ask_entry.get().strip()
        if not q or q == "Ask AI...":
            return
        self.ask_entry.delete(0, tk.END)
        self.insights.config(state=tk.NORMAL)
        self.insights.delete(1.0, tk.END)
        self.insights.insert(tk.END, f"{q}\n", 'title')
        self.insights.insert(tk.END, "─" * 30 + "\n\n", 'muted')
        self.insights.insert(tk.END, "Thinking...\n", 'muted')
        self.insights.config(state=tk.DISABLED)

        def get():
            a = self.service_client.ask_llm(q, self.recent_text)
            def update_ui():
                self.insights.config(state=tk.NORMAL)
                self.insights.delete(1.0, tk.END)
                self.insights.insert(tk.END, f"{q}\n", 'title')
                self.insights.insert(tk.END, "─" * 30 + "\n\n", 'muted')
                if a:
                    self._format_details(a, None)
                else:
                    self.insights.insert(tk.END, "No answer available.\n", 'normal')
                self.insights.config(state=tk.DISABLED)
                self.insights.see("1.0")
            self.root.after(0, update_ui)
        threading.Thread(target=get, daemon=True).start()

    def upd_dur(self):
        if self.is_recording and self.start_time:
            e = int(time.time() - self.start_time)
            self.duration_label.config(text=f"{e//60:02d}:{e%60:02d}", fg=self.COLORS['accent_danger'])
            self.root.after(1000, self.upd_dur)
        else:
            self.duration_label.config(text="00:00", fg=self.COLORS['text_muted'])

    def show_summary(self):
        if not self.full_transcript:
            return
        self._sys_msg("Generating summary...")
        def gen():
            self.service_client.summarize("\n".join([f"[{s['speaker']}]: {s['text']}" for s in self.full_transcript]))
            self.root.after(0, self.disp_sum)
        threading.Thread(target=gen, daemon=True).start()

    def disp_sum(self):
        if self.meeting_id:
            from meeting_summary_page import SummaryPage
            SummaryPage(self.meeting_id, self.root)

    def clear(self):
        self.transcript.delete(1.0, tk.END)
        self.full_transcript = []
        self.speakers = set()
        self.recent_text = ""
        self.accumulated_text = ""
        self.sum_btn.config(fg=self.COLORS['text_muted'])
        self.seg_count.config(text="0")

        # Clear insights
        self.insights.config(state=tk.NORMAL)
        self.insights.delete(1.0, tk.END)
        self.insights.config(state=tk.DISABLED)

        # Clear keywords (both full and mini)
        self.current_keywords = []
        for btn in self.keyword_buttons:
            btn.destroy()
        for btn in self.mini_keyword_buttons:
            btn.destroy()
        self.mini_keyword_buttons = []
        self.keyword_buttons = []
        self.keywords_placeholder.pack(pady=2)
        self.mini_keywords_placeholder.pack(side=tk.LEFT, pady=2)
        self.latest_insights = {}

    def open_dashboard(self, e=None):
        subprocess.Popen([sys.executable, str(Path(__file__).parent / "meeting_dashboard.py")],
                        creationflags=subprocess.CREATE_NEW_CONSOLE)

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()

    def on_close(self):
        if self.is_recording:
            self.stop_rec()
        self.root.destroy()


def main():
    print("=" * 50)
    print("Nexus Meeting Recorder v4")
    print("=" * 50)
    print(f"PyAudio: {PYAUDIO_AVAILABLE}, WASAPI: {WPATCH_AVAILABLE}")
    if not WPATCH_AVAILABLE:
        print("TIP: pip install pyaudiowpatch for better system audio")
    print()
    NexusOverlay().run()


if __name__ == "__main__":
    main()

"""
Nexus Meeting Recorder - Integrated Overlay UI
Full-featured UI with real microphone capture, transcription, and LLM integration
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
from datetime import datetime
from typing import Optional, List, Dict, Any

# Audio capture
try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    print("WARNING: PyAudio not available - install with: pip install pyaudio")

# HTTP client
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    print("WARNING: httpx not available")

# Service URLs
TRANSCRIPTION_SERVICE = "http://127.0.0.1:38421"
LLM_SERVICE = "http://127.0.0.1:45231"
RAG_SERVICE = "http://127.0.0.1:53847"

# Audio configuration
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 1024
FORMAT = pyaudio.paInt16 if PYAUDIO_AVAILABLE else None
RECORD_SECONDS_PER_CHUNK = 5  # Send audio every 5 seconds


class AudioRecorder:
    """Handles microphone audio capture"""

    def __init__(self, on_chunk_ready, on_error):
        self.on_chunk_ready = on_chunk_ready
        self.on_error = on_error
        self.is_recording = False
        self.audio_thread = None
        self.pyaudio_instance = None
        self.stream = None

    def start(self):
        """Start audio recording"""
        if not PYAUDIO_AVAILABLE:
            self.on_error("PyAudio not installed. Run: pip install pyaudio")
            return False

        try:
            self.pyaudio_instance = pyaudio.PyAudio()

            # Find default input device
            device_info = self.pyaudio_instance.get_default_input_device_info()
            print(f"Using audio device: {device_info['name']}")

            self.stream = self.pyaudio_instance.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=CHUNK_SIZE
            )

            self.is_recording = True
            self.audio_thread = threading.Thread(target=self._record_loop, daemon=True)
            self.audio_thread.start()
            return True

        except Exception as e:
            self.on_error(f"Failed to start audio: {str(e)}")
            return False

    def _record_loop(self):
        """Main recording loop - runs in separate thread"""
        frames = []
        chunks_per_send = int(SAMPLE_RATE / CHUNK_SIZE * RECORD_SECONDS_PER_CHUNK)

        while self.is_recording:
            try:
                data = self.stream.read(CHUNK_SIZE, exception_on_overflow=False)
                frames.append(data)

                # Send chunk every RECORD_SECONDS_PER_CHUNK seconds
                if len(frames) >= chunks_per_send:
                    # Convert to WAV format
                    audio_data = self._frames_to_wav(frames)
                    frames = []

                    # Send to callback
                    self.on_chunk_ready(audio_data)

            except Exception as e:
                if self.is_recording:
                    self.on_error(f"Recording error: {str(e)}")
                break

    def _frames_to_wav(self, frames) -> bytes:
        """Convert raw audio frames to WAV format"""
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(self.pyaudio_instance.get_sample_size(FORMAT))
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b''.join(frames))
        return buffer.getvalue()

    def stop(self):
        """Stop audio recording"""
        self.is_recording = False

        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

        if self.pyaudio_instance:
            self.pyaudio_instance.terminate()
            self.pyaudio_instance = None


class ServiceClient:
    """HTTP client for backend services"""

    def __init__(self):
        self.session_id = f"session_{int(time.time())}"
        self.chunk_index = 0

    async def check_services(self) -> Dict[str, bool]:
        """Check which services are online"""
        results = {}
        async with httpx.AsyncClient(timeout=3.0) as client:
            for name, url in [
                ("transcription", TRANSCRIPTION_SERVICE),
                ("llm", LLM_SERVICE),
                ("rag", RAG_SERVICE)
            ]:
                try:
                    response = await client.get(f"{url}/health")
                    results[name] = response.status_code == 200
                except:
                    results[name] = False
        return results

    def check_services_sync(self) -> Dict[str, bool]:
        """Synchronous version of check_services"""
        results = {}
        for name, url in [
            ("transcription", TRANSCRIPTION_SERVICE),
            ("llm", LLM_SERVICE),
            ("rag", RAG_SERVICE)
        ]:
            try:
                with httpx.Client(timeout=3.0) as client:
                    response = client.get(f"{url}/health")
                    results[name] = response.status_code == 200
            except:
                results[name] = False
        return results

    def transcribe(self, audio_data: bytes) -> Optional[Dict]:
        """Send audio to transcription service"""
        try:
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')

            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{TRANSCRIPTION_SERVICE}/transcribe/stream",
                    json={
                        "audio_chunk": audio_base64,
                        "session_id": self.session_id,
                        "chunk_index": self.chunk_index,
                        "language": "en"
                    }
                )
                self.chunk_index += 1

                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"Transcription error: {response.status_code} - {response.text}")
                    return None

        except Exception as e:
            print(f"Transcription request failed: {e}")
            return None

    def detect_intent(self, text: str, context: str = None) -> Optional[Dict]:
        """Detect intent from text"""
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    f"{LLM_SERVICE}/detect-intent",
                    json={
                        "text": text,
                        "context": context
                    }
                )
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            print(f"Intent detection failed: {e}")
        return None

    def query_rag(self, question: str) -> Optional[Dict]:
        """Query knowledge base"""
        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.post(
                    f"{RAG_SERVICE}/query",
                    json={
                        "question": question,
                        "top_k": 3,
                        "use_web_search": False
                    }
                )
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            print(f"RAG query failed: {e}")
        return None

    def summarize(self, transcript: str) -> Optional[Dict]:
        """Generate meeting summary"""
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    f"{LLM_SERVICE}/summarize",
                    json={
                        "transcript": transcript,
                        "max_tokens": 3000
                    }
                )
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            print(f"Summarization failed: {e}")
        return None

    def extract_action_items(self, transcript: str, participants: List[str]) -> Optional[Dict]:
        """Extract action items from transcript"""
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{LLM_SERVICE}/extract/action-items",
                    json={
                        "transcript": transcript,
                        "participants": participants
                    }
                )
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            print(f"Action item extraction failed: {e}")
        return None


class NexusOverlay:
    """Main overlay UI window"""

    def __init__(self):
        self.root = tk.Tk()
        self.setup_window()

        # State
        self.is_recording = False
        self.full_transcript = []
        self.speakers = set()
        self.start_time = None

        # Components
        self.audio_recorder = None
        self.service_client = ServiceClient()
        self.transcript_queue = queue.Queue()

        # Create UI
        self.create_widgets()

        # Check services on startup
        self.root.after(1000, self.check_services)

        # Start queue processor
        self.process_transcript_queue()

    def setup_window(self):
        """Configure window properties"""
        self.root.title("Nexus Meeting Recorder")

        # Window size and position (right side of screen)
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        overlay_width = 450
        overlay_height = 700
        x_position = screen_width - overlay_width - 20
        y_position = 50

        self.root.geometry(f"{overlay_width}x{overlay_height}+{x_position}+{y_position}")

        # Make translucent and always on top
        self.root.attributes('-alpha', 0.92)
        self.root.attributes('-topmost', True)

        # Dark theme
        self.root.configure(bg='#1a1a2e')

        # Style
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TButton', font=('Segoe UI', 10))
        style.configure('TLabel', font=('Segoe UI', 10), background='#1a1a2e', foreground='#ffffff')

    def create_widgets(self):
        """Create all UI components"""
        # Main container
        main_frame = tk.Frame(self.root, bg='#1a1a2e')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Header
        self.create_header(main_frame)

        # Status bar
        self.create_status_bar(main_frame)

        # Transcript area
        self.create_transcript_area(main_frame)

        # AI Assistance panel (collapsible)
        self.create_assistance_panel(main_frame)

        # Control buttons
        self.create_controls(main_frame)

        # Footer with service status
        self.create_footer(main_frame)

    def create_header(self, parent):
        """Create header section"""
        header_frame = tk.Frame(parent, bg='#16213e', height=50)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        header_frame.pack_propagate(False)

        title_label = tk.Label(
            header_frame,
            text="Nexus Meeting Recorder",
            font=('Segoe UI', 14, 'bold'),
            fg='#e94560',
            bg='#16213e'
        )
        title_label.pack(pady=12)

    def create_status_bar(self, parent):
        """Create recording status bar"""
        status_frame = tk.Frame(parent, bg='#1a1a2e')
        status_frame.pack(fill=tk.X, pady=(0, 5))

        # Recording indicator
        self.status_indicator = tk.Label(
            status_frame,
            text="",
            font=('Segoe UI', 14),
            fg='#888888',
            bg='#1a1a2e'
        )
        self.status_indicator.pack(side=tk.LEFT, padx=5)

        self.status_label = tk.Label(
            status_frame,
            text="Ready to record",
            font=('Segoe UI', 11),
            fg='#888888',
            bg='#1a1a2e'
        )
        self.status_label.pack(side=tk.LEFT)

        # Duration
        self.duration_label = tk.Label(
            status_frame,
            text="",
            font=('Segoe UI', 10),
            fg='#666666',
            bg='#1a1a2e'
        )
        self.duration_label.pack(side=tk.RIGHT, padx=5)

    def create_transcript_area(self, parent):
        """Create transcript display area"""
        # Label
        transcript_label = tk.Label(
            parent,
            text="Live Transcript",
            font=('Segoe UI', 10, 'bold'),
            fg='#e94560',
            bg='#1a1a2e'
        )
        transcript_label.pack(anchor=tk.W, pady=(5, 2))

        # Transcript text area
        transcript_frame = tk.Frame(parent, bg='#0f3460')
        transcript_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.transcript_text = scrolledtext.ScrolledText(
            transcript_frame,
            wrap=tk.WORD,
            font=('Consolas', 10),
            bg='#0f3460',
            fg='#ffffff',
            insertbackground='#ffffff',
            relief=tk.FLAT,
            padx=10,
            pady=10,
            height=15
        )
        self.transcript_text.pack(fill=tk.BOTH, expand=True)

        # Configure tags for different speakers
        self.transcript_text.tag_configure('speaker1', foreground='#4ecca3')
        self.transcript_text.tag_configure('speaker2', foreground='#f9ed69')
        self.transcript_text.tag_configure('speaker3', foreground='#f38181')
        self.transcript_text.tag_configure('speaker4', foreground='#a3d8f4')
        self.transcript_text.tag_configure('system', foreground='#888888', font=('Consolas', 9, 'italic'))
        self.transcript_text.tag_configure('timestamp', foreground='#666666', font=('Consolas', 8))

        # Welcome message
        self.add_system_message("Welcome to Nexus Meeting Recorder")
        self.add_system_message("Click 'Start Recording' to begin capturing audio")

    def create_assistance_panel(self, parent):
        """Create AI assistance panel"""
        # Collapsible frame
        self.assistance_frame = tk.Frame(parent, bg='#16213e')
        self.assistance_frame.pack(fill=tk.X, pady=5)

        # Header
        assist_header = tk.Frame(self.assistance_frame, bg='#16213e')
        assist_header.pack(fill=tk.X)

        assist_label = tk.Label(
            assist_header,
            text="AI Assistance",
            font=('Segoe UI', 10, 'bold'),
            fg='#4ecca3',
            bg='#16213e'
        )
        assist_label.pack(side=tk.LEFT, padx=5, pady=5)

        # Assistance text
        self.assistance_text = tk.Text(
            self.assistance_frame,
            wrap=tk.WORD,
            font=('Segoe UI', 9),
            bg='#16213e',
            fg='#cccccc',
            relief=tk.FLAT,
            height=4,
            padx=5,
            pady=5
        )
        self.assistance_text.pack(fill=tk.X, padx=5, pady=(0, 5))
        self.assistance_text.insert(tk.END, "AI assistance will appear here when questions are detected...")
        self.assistance_text.config(state=tk.DISABLED)

    def create_controls(self, parent):
        """Create control buttons"""
        control_frame = tk.Frame(parent, bg='#1a1a2e')
        control_frame.pack(fill=tk.X, pady=10)

        # Record button
        self.record_button = tk.Button(
            control_frame,
            text="Start Recording",
            font=('Segoe UI', 11, 'bold'),
            bg='#4ecca3',
            fg='#1a1a2e',
            activebackground='#3db892',
            activeforeground='#1a1a2e',
            relief=tk.FLAT,
            padx=20,
            pady=10,
            command=self.toggle_recording
        )
        self.record_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        # Summary button
        self.summary_button = tk.Button(
            control_frame,
            text="Summary",
            font=('Segoe UI', 10),
            bg='#533483',
            fg='#ffffff',
            activebackground='#452c6e',
            activeforeground='#ffffff',
            relief=tk.FLAT,
            padx=15,
            pady=10,
            command=self.show_summary,
            state=tk.DISABLED
        )
        self.summary_button.pack(side=tk.LEFT, padx=5)

        # Clear button
        self.clear_button = tk.Button(
            control_frame,
            text="Clear",
            font=('Segoe UI', 10),
            bg='#444444',
            fg='#ffffff',
            activebackground='#333333',
            activeforeground='#ffffff',
            relief=tk.FLAT,
            padx=15,
            pady=10,
            command=self.clear_transcript
        )
        self.clear_button.pack(side=tk.RIGHT)

    def create_footer(self, parent):
        """Create footer with service status"""
        footer_frame = tk.Frame(parent, bg='#16213e', height=30)
        footer_frame.pack(fill=tk.X, pady=(5, 0))
        footer_frame.pack_propagate(False)

        self.service_status_label = tk.Label(
            footer_frame,
            text="Checking services...",
            font=('Segoe UI', 8),
            fg='#666666',
            bg='#16213e'
        )
        self.service_status_label.pack(pady=7)

    def check_services(self):
        """Check backend service status"""
        def check():
            if HTTPX_AVAILABLE:
                status = self.service_client.check_services_sync()
                online = sum(status.values())
                total = len(status)

                if online == total:
                    status_text = "All services online"
                    color = '#4ecca3'
                elif online > 0:
                    status_text = f"Services: {online}/{total} online"
                    color = '#f9ed69'
                else:
                    status_text = "Services offline - start with start_services.bat"
                    color = '#e94560'

                self.root.after(0, lambda: self.update_service_status(status_text, color))
            else:
                self.root.after(0, lambda: self.update_service_status("httpx not installed", '#e94560'))

        threading.Thread(target=check, daemon=True).start()

        # Re-check every 30 seconds
        self.root.after(30000, self.check_services)

    def update_service_status(self, text: str, color: str):
        """Update service status display"""
        self.service_status_label.config(text=text, fg=color)

    def toggle_recording(self):
        """Start or stop recording"""
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        """Start audio recording"""
        if not PYAUDIO_AVAILABLE:
            messagebox.showerror("Error", "PyAudio not installed.\n\nRun: pip install pyaudio")
            return

        self.audio_recorder = AudioRecorder(
            on_chunk_ready=self.on_audio_chunk,
            on_error=self.on_audio_error
        )

        if self.audio_recorder.start():
            self.is_recording = True
            self.start_time = time.time()
            self.full_transcript = []
            self.speakers = set()

            # Update UI
            self.status_indicator.config(text="", fg='#e94560')
            self.status_label.config(text="Recording...", fg='#e94560')
            self.record_button.config(
                text="Stop Recording",
                bg='#e94560',
                activebackground='#c73e54'
            )
            self.summary_button.config(state=tk.DISABLED)

            self.add_system_message("Recording started - speak into your microphone")

            # Start duration update
            self.update_duration()

    def stop_recording(self):
        """Stop audio recording"""
        if self.audio_recorder:
            self.audio_recorder.stop()
            self.audio_recorder = None

        self.is_recording = False

        # Update UI
        self.status_indicator.config(text="", fg='#888888')
        self.status_label.config(text="Recording stopped", fg='#888888')
        self.record_button.config(
            text="Start Recording",
            bg='#4ecca3',
            activebackground='#3db892'
        )

        self.add_system_message("Recording stopped")

        # Enable summary button if we have transcript
        if self.full_transcript:
            self.summary_button.config(state=tk.NORMAL)
            self.add_system_message("Click 'Summary' to generate meeting summary")

    def on_audio_chunk(self, audio_data: bytes):
        """Handle audio chunk from recorder"""
        def process():
            result = self.service_client.transcribe(audio_data)
            if result and 'segments' in result:
                for segment in result['segments']:
                    self.transcript_queue.put(segment)

        # Process in background thread
        threading.Thread(target=process, daemon=True).start()

    def on_audio_error(self, error_message: str):
        """Handle audio error"""
        self.root.after(0, lambda: self.add_system_message(f"Audio error: {error_message}"))

    def process_transcript_queue(self):
        """Process transcript segments from queue"""
        try:
            while True:
                segment = self.transcript_queue.get_nowait()
                self.add_transcript_segment(segment)

                # Check for questions/assistance
                if segment.get('text'):
                    self.check_for_assistance(segment['text'])

        except queue.Empty:
            pass

        # Schedule next check
        self.root.after(100, self.process_transcript_queue)

    def add_transcript_segment(self, segment: Dict):
        """Add a transcript segment to the display"""
        speaker = segment.get('speaker', 'Unknown')
        text = segment.get('text', '').strip()

        if not text:
            return

        # Track speakers
        self.speakers.add(speaker)

        # Store for summary
        self.full_transcript.append({
            'speaker': speaker,
            'text': text,
            'timestamp': datetime.now().isoformat()
        })

        # Determine speaker color
        speaker_list = sorted(list(self.speakers))
        speaker_idx = speaker_list.index(speaker) if speaker in speaker_list else 0
        tag = f'speaker{(speaker_idx % 4) + 1}'

        # Add to text widget
        timestamp = datetime.now().strftime("%H:%M:%S")

        self.transcript_text.insert(tk.END, f"\n[{timestamp}] ", 'timestamp')
        self.transcript_text.insert(tk.END, f"{speaker}: ", tag)
        self.transcript_text.insert(tk.END, f"{text}\n")

        # Auto-scroll
        self.transcript_text.see(tk.END)

    def add_system_message(self, message: str):
        """Add a system message to transcript"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.transcript_text.insert(tk.END, f"\n[{timestamp}] {message}\n", 'system')
        self.transcript_text.see(tk.END)

    def check_for_assistance(self, text: str):
        """Check if text needs AI assistance"""
        def process():
            # Check if it's a question
            if '?' in text or text.lower().startswith(('what', 'how', 'why', 'when', 'where', 'who', 'can', 'could', 'would', 'should')):
                # Query RAG for answer
                result = self.service_client.query_rag(text)
                if result and result.get('answer'):
                    self.root.after(0, lambda: self.show_assistance(
                        f"Q: {text}\n\nA: {result['answer']}"
                    ))

        threading.Thread(target=process, daemon=True).start()

    def show_assistance(self, text: str):
        """Show AI assistance"""
        self.assistance_text.config(state=tk.NORMAL)
        self.assistance_text.delete(1.0, tk.END)
        self.assistance_text.insert(tk.END, text)
        self.assistance_text.config(state=tk.DISABLED)

    def update_duration(self):
        """Update recording duration display"""
        if self.is_recording and self.start_time:
            elapsed = int(time.time() - self.start_time)
            minutes = elapsed // 60
            seconds = elapsed % 60
            self.duration_label.config(text=f"{minutes:02d}:{seconds:02d}")
            self.root.after(1000, self.update_duration)
        else:
            self.duration_label.config(text="")

    def show_summary(self):
        """Generate and show meeting summary"""
        if not self.full_transcript:
            messagebox.showinfo("No Transcript", "No transcript to summarize")
            return

        # Disable button while processing
        self.summary_button.config(state=tk.DISABLED, text="Generating...")
        self.add_system_message("Generating summary...")

        def generate():
            # Build transcript text
            transcript_text = "\n".join([
                f"[{s['speaker']}]: {s['text']}"
                for s in self.full_transcript
            ])

            # Get summary
            summary_result = self.service_client.summarize(transcript_text)

            # Get action items
            participants = list(self.speakers)
            action_result = self.service_client.extract_action_items(transcript_text, participants)

            # Show results
            self.root.after(0, lambda: self.display_summary(summary_result, action_result))

        threading.Thread(target=generate, daemon=True).start()

    def display_summary(self, summary_result: Optional[Dict], action_result: Optional[Dict]):
        """Display summary in new window"""
        self.summary_button.config(state=tk.NORMAL, text="Summary")

        # Create summary window
        summary_window = tk.Toplevel(self.root)
        summary_window.title("Meeting Summary")
        summary_window.geometry("600x500")
        summary_window.configure(bg='#1a1a2e')
        summary_window.attributes('-topmost', True)

        # Summary text
        summary_text = scrolledtext.ScrolledText(
            summary_window,
            wrap=tk.WORD,
            font=('Segoe UI', 10),
            bg='#0f3460',
            fg='#ffffff',
            padx=15,
            pady=15
        )
        summary_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Build content
        content = "MEETING SUMMARY\n"
        content += "=" * 50 + "\n\n"

        if summary_result and summary_result.get('summary'):
            summary = summary_result['summary']
            if isinstance(summary, dict):
                if summary.get('executive_summary'):
                    content += "EXECUTIVE SUMMARY:\n"
                    content += summary['executive_summary'] + "\n\n"
                if summary.get('key_topics'):
                    content += "KEY TOPICS:\n"
                    for topic in summary['key_topics']:
                        content += f"  - {topic}\n"
                    content += "\n"
                if summary.get('detailed_summary'):
                    content += "DETAILED SUMMARY:\n"
                    content += summary['detailed_summary'] + "\n\n"
            else:
                content += str(summary) + "\n\n"
        else:
            content += "Summary generation failed or no content available.\n\n"

        content += "=" * 50 + "\n"
        content += "ACTION ITEMS\n"
        content += "=" * 50 + "\n\n"

        if action_result and action_result.get('action_items'):
            for i, item in enumerate(action_result['action_items'], 1):
                content += f"{i}. {item.get('task', 'Unknown task')}\n"
                content += f"   Assignee: {item.get('assignee', 'Unassigned')}\n"
                content += f"   Due: {item.get('due_date', 'Not specified')}\n"
                content += f"   Priority: {item.get('priority', 'Normal')}\n\n"
        else:
            content += "No action items detected.\n"

        summary_text.insert(tk.END, content)
        summary_text.config(state=tk.DISABLED)

        self.add_system_message("Summary generated - see popup window")

    def clear_transcript(self):
        """Clear transcript and reset"""
        self.transcript_text.delete(1.0, tk.END)
        self.full_transcript = []
        self.speakers = set()
        self.summary_button.config(state=tk.DISABLED)
        self.add_system_message("Transcript cleared")

    def run(self):
        """Run the application"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()

    def on_close(self):
        """Handle window close"""
        if self.is_recording:
            self.stop_recording()
        self.root.destroy()


def main():
    """Main entry point"""
    print("Starting Nexus Meeting Recorder...")
    print(f"PyAudio available: {PYAUDIO_AVAILABLE}")
    print(f"HTTPX available: {HTTPX_AVAILABLE}")

    if not PYAUDIO_AVAILABLE:
        print("\nWARNING: PyAudio not installed!")
        print("Install with: pip install pyaudio")
        print("On Windows, you may need: pip install pipwin && pipwin install pyaudio")

    app = NexusOverlay()
    app.run()


if __name__ == "__main__":
    main()

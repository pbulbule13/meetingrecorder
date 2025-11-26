"""
Nexus Meeting Dashboard - Main UI with Meeting History
Production-grade interface with light theme
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import subprocess
import sys
import os

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

# Database path
DB_PATH = Path(__file__).parent.parent.parent / "data" / "meetings.db"


class MeetingDatabase:
    """SQLite database for meeting storage"""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_database()

    def init_database(self):
        """Initialize database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Meetings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                date TEXT NOT NULL,
                duration_seconds INTEGER DEFAULT 0,
                participants TEXT DEFAULT '[]',
                status TEXT DEFAULT 'completed',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Transcripts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transcripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER NOT NULL,
                speaker TEXT NOT NULL,
                text TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                start_ms INTEGER DEFAULT 0,
                end_ms INTEGER DEFAULT 0,
                FOREIGN KEY (meeting_id) REFERENCES meetings(id)
            )
        ''')

        # AI Insights table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS insights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER NOT NULL,
                insight_type TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (meeting_id) REFERENCES meetings(id)
            )
        ''')

        # Summaries table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER NOT NULL UNIQUE,
                executive_summary TEXT,
                key_topics TEXT,
                detailed_summary TEXT,
                action_items TEXT,
                decisions TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (meeting_id) REFERENCES meetings(id)
            )
        ''')

        conn.commit()
        conn.close()

    def create_meeting(self, title: str) -> int:
        """Create a new meeting and return its ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO meetings (title, date, status)
            VALUES (?, ?, ?)
        ''', (title, datetime.now().isoformat(), 'recording'))

        meeting_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return meeting_id

    def update_meeting(self, meeting_id: int, duration_seconds: int = None,
                      participants: List[str] = None, status: str = None):
        """Update meeting details"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        updates = []
        values = []

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
            cursor.execute(f'''
                UPDATE meetings SET {', '.join(updates)} WHERE id = ?
            ''', values)

        conn.commit()
        conn.close()

    def add_transcript(self, meeting_id: int, speaker: str, text: str,
                      start_ms: int = 0, end_ms: int = 0):
        """Add transcript segment"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO transcripts (meeting_id, speaker, text, timestamp, start_ms, end_ms)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (meeting_id, speaker, text, datetime.now().isoformat(), start_ms, end_ms))

        conn.commit()
        conn.close()

    def add_insight(self, meeting_id: int, insight_type: str, content: str):
        """Add AI insight"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO insights (meeting_id, insight_type, content, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (meeting_id, insight_type, content, datetime.now().isoformat()))

        conn.commit()
        conn.close()

    def save_summary(self, meeting_id: int, executive_summary: str = None,
                    key_topics: List[str] = None, detailed_summary: str = None,
                    action_items: List[Dict] = None, decisions: List[Dict] = None):
        """Save meeting summary"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO summaries
            (meeting_id, executive_summary, key_topics, detailed_summary, action_items, decisions)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            meeting_id,
            executive_summary,
            json.dumps(key_topics) if key_topics else None,
            detailed_summary,
            json.dumps(action_items) if action_items else None,
            json.dumps(decisions) if decisions else None
        ))

        conn.commit()
        conn.close()

    def get_all_meetings(self) -> List[Dict]:
        """Get all meetings"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM meetings ORDER BY date DESC
        ''')

        meetings = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return meetings

    def get_meeting(self, meeting_id: int) -> Optional[Dict]:
        """Get a single meeting"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM meetings WHERE id = ?', (meeting_id,))
        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def get_transcripts(self, meeting_id: int) -> List[Dict]:
        """Get all transcripts for a meeting"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM transcripts WHERE meeting_id = ? ORDER BY timestamp
        ''', (meeting_id,))

        transcripts = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return transcripts

    def get_insights(self, meeting_id: int) -> List[Dict]:
        """Get all insights for a meeting"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM insights WHERE meeting_id = ? ORDER BY timestamp
        ''', (meeting_id,))

        insights = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return insights

    def get_summary(self, meeting_id: int) -> Optional[Dict]:
        """Get meeting summary"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM summaries WHERE meeting_id = ?', (meeting_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            summary = dict(row)
            if summary.get('key_topics'):
                summary['key_topics'] = json.loads(summary['key_topics'])
            if summary.get('action_items'):
                summary['action_items'] = json.loads(summary['action_items'])
            if summary.get('decisions'):
                summary['decisions'] = json.loads(summary['decisions'])
            return summary
        return None

    def delete_meeting(self, meeting_id: int):
        """Delete a meeting and all related data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('DELETE FROM transcripts WHERE meeting_id = ?', (meeting_id,))
        cursor.execute('DELETE FROM insights WHERE meeting_id = ?', (meeting_id,))
        cursor.execute('DELETE FROM summaries WHERE meeting_id = ?', (meeting_id,))
        cursor.execute('DELETE FROM meetings WHERE id = ?', (meeting_id,))

        conn.commit()
        conn.close()


class NexusDashboard:
    """Main Dashboard UI with production-grade light theme"""

    # Production-grade color palette (Light theme)
    COLORS = {
        'bg_primary': '#FFFFFF',
        'bg_secondary': '#F8FAFC',
        'bg_tertiary': '#F1F5F9',
        'bg_hover': '#E2E8F0',
        'text_primary': '#1E293B',
        'text_secondary': '#64748B',
        'text_muted': '#94A3B8',
        'accent_primary': '#3B82F6',  # Blue
        'accent_success': '#10B981',  # Green
        'accent_warning': '#F59E0B',  # Amber
        'accent_danger': '#EF4444',   # Red
        'accent_info': '#6366F1',     # Indigo
        'border': '#E2E8F0',
        'border_focus': '#3B82F6',
        'shadow': '#00000010',
    }

    def __init__(self):
        self.root = tk.Tk()
        self.setup_window()
        self.setup_styles()

        # Initialize database
        self.db = MeetingDatabase()

        # State
        self.selected_meeting_id = None
        self.recording_process = None

        # Create UI
        self.create_widgets()

        # Load meetings
        self.refresh_meetings()

    def setup_window(self):
        """Configure main window"""
        self.root.title("Nexus Meeting Recorder - Dashboard")

        # Window size
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        width = min(1400, screen_width - 100)
        height = min(850, screen_height - 100)
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2

        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(1000, 600)

        # Background
        self.root.configure(bg=self.COLORS['bg_primary'])

        # Icon (if available)
        try:
            self.root.iconbitmap('assets/icon.ico')
        except:
            pass

    def setup_styles(self):
        """Setup ttk styles for production-grade look"""
        style = ttk.Style()
        style.theme_use('clam')

        # Configure colors
        style.configure('.',
            background=self.COLORS['bg_primary'],
            foreground=self.COLORS['text_primary'],
            font=('Segoe UI', 10)
        )

        # Treeview (meeting list)
        style.configure('Treeview',
            background=self.COLORS['bg_primary'],
            foreground=self.COLORS['text_primary'],
            fieldbackground=self.COLORS['bg_primary'],
            rowheight=50,
            font=('Segoe UI', 10)
        )
        style.configure('Treeview.Heading',
            background=self.COLORS['bg_secondary'],
            foreground=self.COLORS['text_secondary'],
            font=('Segoe UI', 10, 'bold')
        )
        style.map('Treeview',
            background=[('selected', self.COLORS['accent_primary'])],
            foreground=[('selected', '#FFFFFF')]
        )

        # Buttons
        style.configure('Primary.TButton',
            background=self.COLORS['accent_primary'],
            foreground='#FFFFFF',
            font=('Segoe UI', 10, 'bold'),
            padding=(20, 10)
        )
        style.configure('Secondary.TButton',
            background=self.COLORS['bg_tertiary'],
            foreground=self.COLORS['text_primary'],
            font=('Segoe UI', 10),
            padding=(15, 8)
        )
        style.configure('Danger.TButton',
            background=self.COLORS['accent_danger'],
            foreground='#FFFFFF',
            font=('Segoe UI', 10),
            padding=(15, 8)
        )

        # Labels
        style.configure('Title.TLabel',
            font=('Segoe UI', 24, 'bold'),
            foreground=self.COLORS['text_primary'],
            background=self.COLORS['bg_primary']
        )
        style.configure('Subtitle.TLabel',
            font=('Segoe UI', 12),
            foreground=self.COLORS['text_secondary'],
            background=self.COLORS['bg_primary']
        )
        style.configure('Section.TLabel',
            font=('Segoe UI', 14, 'bold'),
            foreground=self.COLORS['text_primary'],
            background=self.COLORS['bg_primary']
        )

        # Notebook (tabs)
        style.configure('TNotebook',
            background=self.COLORS['bg_primary'],
            borderwidth=0
        )
        style.configure('TNotebook.Tab',
            background=self.COLORS['bg_secondary'],
            foreground=self.COLORS['text_secondary'],
            padding=(20, 10),
            font=('Segoe UI', 10)
        )
        style.map('TNotebook.Tab',
            background=[('selected', self.COLORS['bg_primary'])],
            foreground=[('selected', self.COLORS['accent_primary'])]
        )

    def create_widgets(self):
        """Create all UI components"""
        # Main container with padding
        main_container = tk.Frame(self.root, bg=self.COLORS['bg_primary'])
        main_container.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)

        # Header
        self.create_header(main_container)

        # Content area (split pane)
        content = tk.Frame(main_container, bg=self.COLORS['bg_primary'])
        content.pack(fill=tk.BOTH, expand=True, pady=(20, 0))

        # Left panel - Meeting list
        self.create_meeting_list(content)

        # Right panel - Meeting details
        self.create_meeting_details(content)

    def create_header(self, parent):
        """Create header with title and actions"""
        header = tk.Frame(parent, bg=self.COLORS['bg_primary'])
        header.pack(fill=tk.X)

        # Left side - Title
        title_frame = tk.Frame(header, bg=self.COLORS['bg_primary'])
        title_frame.pack(side=tk.LEFT)

        title = tk.Label(
            title_frame,
            text="Meeting Dashboard",
            font=('Segoe UI', 24, 'bold'),
            fg=self.COLORS['text_primary'],
            bg=self.COLORS['bg_primary']
        )
        title.pack(anchor=tk.W)

        subtitle = tk.Label(
            title_frame,
            text="View and manage your recorded meetings",
            font=('Segoe UI', 11),
            fg=self.COLORS['text_secondary'],
            bg=self.COLORS['bg_primary']
        )
        subtitle.pack(anchor=tk.W, pady=(2, 0))

        # Right side - Actions
        actions = tk.Frame(header, bg=self.COLORS['bg_primary'])
        actions.pack(side=tk.RIGHT)

        # New Recording button
        self.new_recording_btn = tk.Button(
            actions,
            text="+ New Recording",
            font=('Segoe UI', 11, 'bold'),
            bg=self.COLORS['accent_primary'],
            fg='#FFFFFF',
            activebackground='#2563EB',
            activeforeground='#FFFFFF',
            relief=tk.FLAT,
            padx=25,
            pady=10,
            cursor='hand2',
            command=self.start_new_recording
        )
        self.new_recording_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Refresh button
        refresh_btn = tk.Button(
            actions,
            text="Refresh",
            font=('Segoe UI', 10),
            bg=self.COLORS['bg_tertiary'],
            fg=self.COLORS['text_primary'],
            activebackground=self.COLORS['bg_hover'],
            relief=tk.FLAT,
            padx=15,
            pady=10,
            cursor='hand2',
            command=self.refresh_meetings
        )
        refresh_btn.pack(side=tk.LEFT)

        # Service status indicator
        self.status_frame = tk.Frame(actions, bg=self.COLORS['bg_primary'])
        self.status_frame.pack(side=tk.LEFT, padx=(20, 0))

        self.status_dot = tk.Label(
            self.status_frame,
            text="",
            font=('Segoe UI', 8),
            fg=self.COLORS['text_muted'],
            bg=self.COLORS['bg_primary']
        )
        self.status_dot.pack(side=tk.LEFT)

        self.status_label = tk.Label(
            self.status_frame,
            text="Checking services...",
            font=('Segoe UI', 9),
            fg=self.COLORS['text_muted'],
            bg=self.COLORS['bg_primary']
        )
        self.status_label.pack(side=tk.LEFT, padx=(5, 0))

        # Check services
        self.root.after(500, self.check_services)

    def create_meeting_list(self, parent):
        """Create meeting list panel with date grouping"""
        # Left panel container
        left_panel = tk.Frame(parent, bg=self.COLORS['bg_secondary'], width=480)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 20))
        left_panel.pack_propagate(False)

        # Panel header
        panel_header = tk.Frame(left_panel, bg=self.COLORS['bg_secondary'])
        panel_header.pack(fill=tk.X, padx=15, pady=15)

        tk.Label(
            panel_header,
            text="Meeting History",
            font=('Segoe UI', 14, 'bold'),
            fg=self.COLORS['text_primary'],
            bg=self.COLORS['bg_secondary']
        ).pack(side=tk.LEFT)

        # Meeting count
        self.meeting_count_label = tk.Label(
            panel_header,
            text="0 meetings",
            font=('Segoe UI', 10),
            fg=self.COLORS['text_muted'],
            bg=self.COLORS['bg_secondary']
        )
        self.meeting_count_label.pack(side=tk.RIGHT)

        # Search box
        search_frame = tk.Frame(left_panel, bg=self.COLORS['bg_secondary'])
        search_frame.pack(fill=tk.X, padx=15, pady=(0, 10))

        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.on_search_change)

        search_entry = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            font=('Segoe UI', 10),
            bg=self.COLORS['bg_primary'],
            fg=self.COLORS['text_primary'],
            insertbackground=self.COLORS['text_primary'],
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=self.COLORS['border'],
            highlightcolor=self.COLORS['border_focus']
        )
        search_entry.pack(fill=tk.X, ipady=8, ipadx=10)
        search_entry.insert(0, "Search meetings...")
        search_entry.bind('<FocusIn>', lambda e: search_entry.delete(0, tk.END) if search_entry.get() == "Search meetings..." else None)
        search_entry.bind('<FocusOut>', lambda e: search_entry.insert(0, "Search meetings...") if not search_entry.get() else None)

        # Meeting list with date grouping
        list_container = tk.Frame(left_panel, bg=self.COLORS['bg_secondary'])
        list_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        # Create canvas for scrollable list
        self.list_canvas = tk.Canvas(list_container, bg=self.COLORS['bg_secondary'], highlightthickness=0)
        self.list_scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=self.list_canvas.yview)
        self.meetings_list_frame = tk.Frame(self.list_canvas, bg=self.COLORS['bg_secondary'])

        self.meetings_list_frame.bind("<Configure>", lambda e: self.list_canvas.configure(scrollregion=self.list_canvas.bbox("all")))
        self.list_canvas.create_window((0, 0), window=self.meetings_list_frame, anchor="nw", width=435)
        self.list_canvas.configure(yscrollcommand=self.list_scrollbar.set)

        # Mouse wheel scrolling
        def on_mousewheel(event):
            self.list_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.list_canvas.bind_all("<MouseWheel>", on_mousewheel)

        self.list_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Store meeting cards for selection
        self.meeting_cards = {}

    def create_meeting_details(self, parent):
        """Create meeting details panel"""
        # Right panel container
        right_panel = tk.Frame(parent, bg=self.COLORS['bg_primary'])
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # No meeting selected state
        self.no_selection_frame = tk.Frame(right_panel, bg=self.COLORS['bg_primary'])
        self.no_selection_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            self.no_selection_frame,
            text="Select a meeting to view details",
            font=('Segoe UI', 14),
            fg=self.COLORS['text_muted'],
            bg=self.COLORS['bg_primary']
        ).pack(expand=True)

        # Meeting details frame (hidden initially)
        self.details_frame = tk.Frame(right_panel, bg=self.COLORS['bg_primary'])

        # Meeting header
        self.details_header = tk.Frame(self.details_frame, bg=self.COLORS['bg_primary'])
        self.details_header.pack(fill=tk.X, pady=(0, 20))

        self.meeting_title_label = tk.Label(
            self.details_header,
            text="Meeting Title",
            font=('Segoe UI', 20, 'bold'),
            fg=self.COLORS['text_primary'],
            bg=self.COLORS['bg_primary']
        )
        self.meeting_title_label.pack(anchor=tk.W)

        self.meeting_meta_label = tk.Label(
            self.details_header,
            text="Date | Duration",
            font=('Segoe UI', 11),
            fg=self.COLORS['text_secondary'],
            bg=self.COLORS['bg_primary']
        )
        self.meeting_meta_label.pack(anchor=tk.W, pady=(5, 0))

        # Action buttons
        self.actions_frame = tk.Frame(self.details_header, bg=self.COLORS['bg_primary'])
        self.actions_frame.pack(anchor=tk.W, pady=(15, 0))

        self.view_summary_btn = tk.Button(
            self.actions_frame,
            text="View Full Summary",
            font=('Segoe UI', 10),
            bg=self.COLORS['accent_info'],
            fg='#FFFFFF',
            activebackground='#4F46E5',
            relief=tk.FLAT,
            padx=15,
            pady=8,
            cursor='hand2',
            command=self.open_summary_page
        )
        self.view_summary_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.generate_summary_btn = tk.Button(
            self.actions_frame,
            text="Generate Summary",
            font=('Segoe UI', 10),
            bg=self.COLORS['accent_success'],
            fg='#FFFFFF',
            activebackground='#059669',
            relief=tk.FLAT,
            padx=15,
            pady=8,
            cursor='hand2',
            command=self.generate_summary
        )
        self.generate_summary_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.export_btn = tk.Button(
            self.actions_frame,
            text="Export",
            font=('Segoe UI', 10),
            bg=self.COLORS['bg_tertiary'],
            fg=self.COLORS['text_primary'],
            activebackground=self.COLORS['bg_hover'],
            relief=tk.FLAT,
            padx=15,
            pady=8,
            cursor='hand2',
            command=self.export_meeting
        )
        self.export_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.delete_btn = tk.Button(
            self.actions_frame,
            text="Delete",
            font=('Segoe UI', 10),
            bg=self.COLORS['accent_danger'],
            fg='#FFFFFF',
            activebackground='#DC2626',
            relief=tk.FLAT,
            padx=15,
            pady=8,
            cursor='hand2',
            command=self.delete_meeting
        )
        self.delete_btn.pack(side=tk.LEFT)

        # Notebook for tabs
        self.notebook = ttk.Notebook(self.details_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Transcript tab
        transcript_frame = tk.Frame(self.notebook, bg=self.COLORS['bg_primary'])
        self.notebook.add(transcript_frame, text='Transcript')

        self.transcript_text = tk.Text(
            transcript_frame,
            wrap=tk.WORD,
            font=('Consolas', 10),
            bg=self.COLORS['bg_secondary'],
            fg=self.COLORS['text_primary'],
            relief=tk.FLAT,
            padx=15,
            pady=15
        )
        self.transcript_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.transcript_text.tag_configure('speaker_me', foreground=self.COLORS['accent_success'], font=('Consolas', 10, 'bold'))
        self.transcript_text.tag_configure('speaker_him', foreground=self.COLORS['accent_info'], font=('Consolas', 10, 'bold'))
        self.transcript_text.tag_configure('timestamp', foreground=self.COLORS['text_muted'], font=('Consolas', 9))

        # AI Insights tab
        insights_frame = tk.Frame(self.notebook, bg=self.COLORS['bg_primary'])
        self.notebook.add(insights_frame, text='AI Insights')

        self.insights_text = tk.Text(
            insights_frame,
            wrap=tk.WORD,
            font=('Segoe UI', 10),
            bg=self.COLORS['bg_secondary'],
            fg=self.COLORS['text_primary'],
            relief=tk.FLAT,
            padx=15,
            pady=15
        )
        self.insights_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.insights_text.tag_configure('insight_type', foreground=self.COLORS['accent_primary'], font=('Segoe UI', 11, 'bold'))
        self.insights_text.tag_configure('timestamp', foreground=self.COLORS['text_muted'], font=('Segoe UI', 9))

        # Summary tab
        summary_frame = tk.Frame(self.notebook, bg=self.COLORS['bg_primary'])
        self.notebook.add(summary_frame, text='Summary')

        self.summary_text = tk.Text(
            summary_frame,
            wrap=tk.WORD,
            font=('Segoe UI', 10),
            bg=self.COLORS['bg_secondary'],
            fg=self.COLORS['text_primary'],
            relief=tk.FLAT,
            padx=15,
            pady=15
        )
        self.summary_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.summary_text.tag_configure('section', foreground=self.COLORS['accent_primary'], font=('Segoe UI', 12, 'bold'))
        self.summary_text.tag_configure('bullet', foreground=self.COLORS['accent_success'])

    def check_services(self):
        """Check backend service status"""
        def check():
            if HTTPX_AVAILABLE:
                online = 0
                total = 3

                for url in [TRANSCRIPTION_SERVICE, LLM_SERVICE, RAG_SERVICE]:
                    try:
                        with httpx.Client(timeout=2.0) as client:
                            response = client.get(f"{url}/health")
                            if response.status_code == 200:
                                online += 1
                    except:
                        pass

                if online == total:
                    self.root.after(0, lambda: self.update_status("All services online", self.COLORS['accent_success']))
                elif online > 0:
                    self.root.after(0, lambda: self.update_status(f"{online}/{total} services online", self.COLORS['accent_warning']))
                else:
                    self.root.after(0, lambda: self.update_status("Services offline", self.COLORS['accent_danger']))
            else:
                self.root.after(0, lambda: self.update_status("HTTP client unavailable", self.COLORS['accent_danger']))

        threading.Thread(target=check, daemon=True).start()
        self.root.after(30000, self.check_services)

    def update_status(self, text: str, color: str):
        """Update service status display"""
        self.status_dot.config(fg=color)
        self.status_label.config(text=text, fg=color)

    def refresh_meetings(self):
        """Refresh meeting list from database with date grouping"""
        # Clear existing widgets
        for widget in self.meetings_list_frame.winfo_children():
            widget.destroy()
        self.meeting_cards = {}

        # Load meetings
        meetings = self.db.get_all_meetings()

        if not meetings:
            # Show empty state
            empty_label = tk.Label(
                self.meetings_list_frame,
                text="No meetings recorded yet.\n\nClick 'New Recording' to start.",
                font=('Segoe UI', 11),
                fg=self.COLORS['text_muted'],
                bg=self.COLORS['bg_secondary'],
                justify=tk.CENTER
            )
            empty_label.pack(pady=50)
            self.meeting_count_label.config(text="0 meetings")
            return

        # Group meetings by date
        from collections import defaultdict
        meetings_by_date = defaultdict(list)

        for meeting in meetings:
            try:
                date_obj = datetime.fromisoformat(meeting['date'])
                date_key = date_obj.strftime("%Y-%m-%d")
            except:
                date_key = meeting['date'][:10]
            meetings_by_date[date_key].append(meeting)

        # Sort dates (most recent first)
        sorted_dates = sorted(meetings_by_date.keys(), reverse=True)

        # Create date groups
        for date_key in sorted_dates:
            date_meetings = meetings_by_date[date_key]

            # Format date header
            try:
                date_obj = datetime.strptime(date_key, "%Y-%m-%d")
                today = datetime.now().date()
                if date_obj.date() == today:
                    date_header = "Today"
                elif date_obj.date() == today.replace(day=today.day - 1) if today.day > 1 else today:
                    date_header = "Yesterday"
                else:
                    date_header = date_obj.strftime("%A, %B %d, %Y")
            except:
                date_header = date_key

            # Date header
            date_frame = tk.Frame(self.meetings_list_frame, bg=self.COLORS['bg_secondary'])
            date_frame.pack(fill=tk.X, pady=(15, 5))

            tk.Label(
                date_frame,
                text=date_header,
                font=('Segoe UI', 11, 'bold'),
                fg=self.COLORS['accent_primary'],
                bg=self.COLORS['bg_secondary']
            ).pack(side=tk.LEFT)

            tk.Label(
                date_frame,
                text=f"{len(date_meetings)} meeting{'s' if len(date_meetings) != 1 else ''}",
                font=('Segoe UI', 9),
                fg=self.COLORS['text_muted'],
                bg=self.COLORS['bg_secondary']
            ).pack(side=tk.RIGHT)

            # Meeting cards for this date
            for meeting in date_meetings:
                self.create_meeting_card(meeting)

        # Update count
        self.meeting_count_label.config(text=f"{len(meetings)} meeting{'s' if len(meetings) != 1 else ''}")

    def create_meeting_card(self, meeting: Dict):
        """Create a meeting card widget"""
        card = tk.Frame(
            self.meetings_list_frame,
            bg=self.COLORS['bg_primary'],
            cursor='hand2'
        )
        card.pack(fill=tk.X, pady=3)

        # Card content
        content = tk.Frame(card, bg=self.COLORS['bg_primary'])
        content.pack(fill=tk.X, padx=12, pady=10)

        # Top row - title and duration
        top_row = tk.Frame(content, bg=self.COLORS['bg_primary'])
        top_row.pack(fill=tk.X)

        title_label = tk.Label(
            top_row,
            text=meeting['title'],
            font=('Segoe UI', 11, 'bold'),
            fg=self.COLORS['text_primary'],
            bg=self.COLORS['bg_primary'],
            anchor='w'
        )
        title_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Duration badge
        duration = meeting.get('duration_seconds', 0)
        if duration > 3600:
            duration_str = f"{duration // 3600}h {(duration % 3600) // 60}m"
        elif duration > 60:
            duration_str = f"{duration // 60}m"
        else:
            duration_str = f"{duration}s" if duration > 0 else "..."

        duration_label = tk.Label(
            top_row,
            text=duration_str,
            font=('Segoe UI', 9),
            fg='#FFFFFF',
            bg=self.COLORS['accent_info'],
            padx=8,
            pady=2
        )
        duration_label.pack(side=tk.RIGHT)

        # Bottom row - time and status
        bottom_row = tk.Frame(content, bg=self.COLORS['bg_primary'])
        bottom_row.pack(fill=tk.X, pady=(5, 0))

        try:
            date_obj = datetime.fromisoformat(meeting['date'])
            time_str = date_obj.strftime("%I:%M %p")
        except:
            time_str = meeting['date'][11:16]

        time_label = tk.Label(
            bottom_row,
            text=time_str,
            font=('Segoe UI', 9),
            fg=self.COLORS['text_muted'],
            bg=self.COLORS['bg_primary']
        )
        time_label.pack(side=tk.LEFT)

        # Click to view summary link
        view_link = tk.Label(
            bottom_row,
            text="View Summary",
            font=('Segoe UI', 9, 'underline'),
            fg=self.COLORS['accent_primary'],
            bg=self.COLORS['bg_primary'],
            cursor='hand2'
        )
        view_link.pack(side=tk.RIGHT)

        # Bind click events
        meeting_id = meeting['id']

        def on_click(e):
            self.select_meeting_card(meeting_id)

        def on_double_click(e):
            self.open_meeting_summary(meeting_id)

        def on_view_click(e):
            self.open_meeting_summary(meeting_id)

        # Bind to all elements
        for widget in [card, content, top_row, title_label, bottom_row, time_label, duration_label]:
            widget.bind('<Button-1>', on_click)
            widget.bind('<Double-Button-1>', on_double_click)

        view_link.bind('<Button-1>', on_view_click)

        # Hover effect
        def on_enter(e):
            card.config(bg=self.COLORS['bg_tertiary'])
            for child in card.winfo_children():
                self._update_bg_recursive(child, self.COLORS['bg_tertiary'])

        def on_leave(e):
            bg = self.COLORS['accent_primary'] if self.selected_meeting_id == meeting_id else self.COLORS['bg_primary']
            card.config(bg=bg)
            for child in card.winfo_children():
                self._update_bg_recursive(child, bg)

        card.bind('<Enter>', on_enter)
        card.bind('<Leave>', on_leave)

        # Store reference
        self.meeting_cards[meeting_id] = card

    def _update_bg_recursive(self, widget, bg):
        """Update background color recursively"""
        try:
            # Don't change the duration badge background
            if widget.cget('bg') in [self.COLORS['accent_info'], self.COLORS['accent_success']]:
                return
            widget.config(bg=bg)
        except:
            pass
        for child in widget.winfo_children():
            self._update_bg_recursive(child, bg)

    def select_meeting_card(self, meeting_id: int):
        """Select a meeting card"""
        # Deselect previous
        if self.selected_meeting_id and self.selected_meeting_id in self.meeting_cards:
            old_card = self.meeting_cards[self.selected_meeting_id]
            old_card.config(bg=self.COLORS['bg_primary'])
            for child in old_card.winfo_children():
                self._update_bg_recursive(child, self.COLORS['bg_primary'])

        # Select new
        self.selected_meeting_id = meeting_id

        if meeting_id in self.meeting_cards:
            new_card = self.meeting_cards[meeting_id]
            new_card.config(bg='#DBEAFE')  # Light blue selection
            for child in new_card.winfo_children():
                self._update_bg_recursive(child, '#DBEAFE')

        # Show details
        self.no_selection_frame.pack_forget()
        self.details_frame.pack(fill=tk.BOTH, expand=True)
        self.load_meeting_details(meeting_id)

    def open_meeting_summary(self, meeting_id: int):
        """Open the full summary page for a meeting"""
        from meeting_summary_page import SummaryPage
        summary_page = SummaryPage(meeting_id, self.root)

    def on_search_change(self, *args):
        """Handle search input change"""
        query = self.search_var.get().lower()
        if query == "search meetings..." or not query:
            self.refresh_meetings()
            return

        # Clear existing widgets
        for widget in self.meetings_list_frame.winfo_children():
            widget.destroy()
        self.meeting_cards = {}

        # Filter meetings
        meetings = self.db.get_all_meetings()
        filtered = [m for m in meetings if query in m['title'].lower()]

        if not filtered:
            tk.Label(
                self.meetings_list_frame,
                text=f"No meetings matching '{query}'",
                font=('Segoe UI', 11),
                fg=self.COLORS['text_muted'],
                bg=self.COLORS['bg_secondary']
            ).pack(pady=30)
            return

        # Show filtered results
        tk.Label(
            self.meetings_list_frame,
            text=f"Search Results ({len(filtered)})",
            font=('Segoe UI', 11, 'bold'),
            fg=self.COLORS['accent_primary'],
            bg=self.COLORS['bg_secondary']
        ).pack(anchor=tk.W, pady=(10, 5))

        for meeting in filtered:
            self.create_meeting_card(meeting)

    def load_meeting_details(self, meeting_id: int):
        """Load and display meeting details"""
        meeting = self.db.get_meeting(meeting_id)
        if not meeting:
            return

        # Update header
        self.meeting_title_label.config(text=meeting['title'])

        try:
            date_obj = datetime.fromisoformat(meeting['date'])
            date_str = date_obj.strftime("%B %d, %Y at %I:%M %p")
        except:
            date_str = meeting['date']

        duration = meeting.get('duration_seconds', 0)
        if duration > 3600:
            duration_str = f"{duration // 3600}h {(duration % 3600) // 60}m"
        elif duration > 60:
            duration_str = f"{duration // 60} minutes"
        else:
            duration_str = f"{duration} seconds"

        self.meeting_meta_label.config(text=f"{date_str}  |  {duration_str}")

        # Load transcript
        self.transcript_text.config(state=tk.NORMAL)
        self.transcript_text.delete(1.0, tk.END)

        transcripts = self.db.get_transcripts(meeting_id)
        for t in transcripts:
            try:
                ts = datetime.fromisoformat(t['timestamp']).strftime("%H:%M:%S")
            except:
                ts = t['timestamp'][:8]

            tag = 'speaker_me' if t['speaker'] == 'Me' else 'speaker_him'

            self.transcript_text.insert(tk.END, f"[{ts}] ", 'timestamp')
            self.transcript_text.insert(tk.END, f"{t['speaker']}: ", tag)
            self.transcript_text.insert(tk.END, f"{t['text']}\n\n")

        self.transcript_text.config(state=tk.DISABLED)

        # Load insights
        self.insights_text.config(state=tk.NORMAL)
        self.insights_text.delete(1.0, tk.END)

        insights = self.db.get_insights(meeting_id)
        if insights:
            for i in insights:
                try:
                    ts = datetime.fromisoformat(i['timestamp']).strftime("%H:%M:%S")
                except:
                    ts = i['timestamp'][:8]

                self.insights_text.insert(tk.END, f"{i['insight_type'].upper()}\n", 'insight_type')
                self.insights_text.insert(tk.END, f"[{ts}]\n", 'timestamp')
                self.insights_text.insert(tk.END, f"{i['content']}\n\n")
        else:
            self.insights_text.insert(tk.END, "No AI insights generated for this meeting.\n\nInsights are generated during live recording.")

        self.insights_text.config(state=tk.DISABLED)

        # Load summary
        self.summary_text.config(state=tk.NORMAL)
        self.summary_text.delete(1.0, tk.END)

        summary = self.db.get_summary(meeting_id)
        if summary:
            if summary.get('executive_summary'):
                self.summary_text.insert(tk.END, "EXECUTIVE SUMMARY\n", 'section')
                self.summary_text.insert(tk.END, f"{summary['executive_summary']}\n\n")

            if summary.get('key_topics'):
                self.summary_text.insert(tk.END, "KEY TOPICS\n", 'section')
                for topic in summary['key_topics']:
                    self.summary_text.insert(tk.END, f"  - {topic}\n", 'bullet')
                self.summary_text.insert(tk.END, "\n")

            if summary.get('detailed_summary'):
                self.summary_text.insert(tk.END, "DETAILED SUMMARY\n", 'section')
                self.summary_text.insert(tk.END, f"{summary['detailed_summary']}\n\n")

            if summary.get('action_items'):
                self.summary_text.insert(tk.END, "ACTION ITEMS\n", 'section')
                for item in summary['action_items']:
                    task = item.get('task', 'Unknown')
                    assignee = item.get('assignee', 'Unassigned')
                    self.summary_text.insert(tk.END, f"  - {task} ({assignee})\n", 'bullet')
                self.summary_text.insert(tk.END, "\n")
        else:
            self.summary_text.insert(tk.END, "No summary generated yet.\n\nClick 'Generate Summary' to create one.")

        self.summary_text.config(state=tk.DISABLED)

    def start_new_recording(self):
        """Launch overlay UI for new recording"""
        # Start overlay_ui.py
        overlay_path = Path(__file__).parent / "overlay_ui.py"
        python_exe = sys.executable

        try:
            subprocess.Popen([python_exe, str(overlay_path)], creationflags=subprocess.CREATE_NEW_CONSOLE)
            messagebox.showinfo("Recording Started", "Recording overlay has been launched.\nSwitch to your meeting application.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start recording: {e}")

    def generate_summary(self):
        """Generate AI summary for selected meeting"""
        if not self.selected_meeting_id:
            return

        self.generate_summary_btn.config(state=tk.DISABLED, text="Generating...")

        def generate():
            try:
                # Get full transcript
                transcripts = self.db.get_transcripts(self.selected_meeting_id)
                if not transcripts:
                    self.root.after(0, lambda: messagebox.showwarning("No Transcript", "This meeting has no transcript."))
                    return

                transcript_text = "\n".join([f"[{t['speaker']}]: {t['text']}" for t in transcripts])

                # Call LLM service for summary
                if HTTPX_AVAILABLE:
                    with httpx.Client(timeout=60.0) as client:
                        response = client.post(
                            f"{LLM_SERVICE}/summarize",
                            json={"transcript": transcript_text, "max_tokens": 3000}
                        )

                        if response.status_code == 200:
                            result = response.json()
                            summary = result.get('summary', {})

                            # Save to database
                            self.db.save_summary(
                                self.selected_meeting_id,
                                executive_summary=summary.get('executive_summary'),
                                key_topics=summary.get('key_topics'),
                                detailed_summary=summary.get('detailed_summary')
                            )

                            # Extract action items
                            participants = list(set([t['speaker'] for t in transcripts]))
                            action_response = client.post(
                                f"{LLM_SERVICE}/extract/action-items",
                                json={"transcript": transcript_text, "participants": participants}
                            )

                            if action_response.status_code == 200:
                                action_result = action_response.json()
                                self.db.save_summary(
                                    self.selected_meeting_id,
                                    action_items=action_result.get('action_items')
                                )

                            # Reload details
                            self.root.after(0, lambda: self.load_meeting_details(self.selected_meeting_id))
                            self.root.after(0, lambda: messagebox.showinfo("Success", "Summary generated successfully!"))
                        else:
                            self.root.after(0, lambda: messagebox.showerror("Error", "Failed to generate summary"))

            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Summary generation failed: {e}"))
            finally:
                self.root.after(0, lambda: self.generate_summary_btn.config(state=tk.NORMAL, text="Generate Summary"))

        threading.Thread(target=generate, daemon=True).start()

    def open_summary_page(self):
        """Open the full summary page for selected meeting"""
        if not self.selected_meeting_id:
            return

        from meeting_summary_page import SummaryPage
        summary_page = SummaryPage(self.selected_meeting_id, self.root)

    def export_meeting(self):
        """Export meeting to file"""
        if not self.selected_meeting_id:
            return

        meeting = self.db.get_meeting(self.selected_meeting_id)
        if not meeting:
            return

        # Ask for file location
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("Text files", "*.txt")],
            initialfilename=f"{meeting['title'].replace(' ', '_')}_export"
        )

        if not filename:
            return

        # Gather all data
        transcripts = self.db.get_transcripts(self.selected_meeting_id)
        insights = self.db.get_insights(self.selected_meeting_id)
        summary = self.db.get_summary(self.selected_meeting_id)

        export_data = {
            "meeting": meeting,
            "transcripts": transcripts,
            "insights": insights,
            "summary": summary
        }

        try:
            if filename.endswith('.json'):
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
            else:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(f"Meeting: {meeting['title']}\n")
                    f.write(f"Date: {meeting['date']}\n")
                    f.write("=" * 50 + "\n\n")

                    f.write("TRANSCRIPT\n")
                    f.write("-" * 30 + "\n")
                    for t in transcripts:
                        f.write(f"[{t['timestamp']}] {t['speaker']}: {t['text']}\n")

                    if summary:
                        f.write("\n\nSUMMARY\n")
                        f.write("-" * 30 + "\n")
                        if summary.get('executive_summary'):
                            f.write(f"\n{summary['executive_summary']}\n")

            messagebox.showinfo("Success", f"Meeting exported to:\n{filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")

    def delete_meeting(self):
        """Delete selected meeting"""
        if not self.selected_meeting_id:
            return

        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this meeting?\nThis action cannot be undone."):
            self.db.delete_meeting(self.selected_meeting_id)
            self.selected_meeting_id = None

            # Hide details, show no selection
            self.details_frame.pack_forget()
            self.no_selection_frame.pack(fill=tk.BOTH, expand=True)

            # Refresh list
            self.refresh_meetings()

    def run(self):
        """Run the application"""
        self.root.mainloop()


def main():
    """Main entry point"""
    print("Starting Nexus Meeting Dashboard...")
    app = NexusDashboard()
    app.run()


if __name__ == "__main__":
    main()

"""
Nexus Meeting Summary Page
Production-grade summary view with tabs: Summary | Transcript | Usage
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import json
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import sqlite3

# HTTP client
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

# Service URLs
LLM_SERVICE = "http://127.0.0.1:45231"

# Database path
DB_PATH = Path(__file__).parent.parent.parent / "data" / "meetings.db"


class SummaryPage:
    """Enhanced meeting summary page with tabs"""

    # Production-grade color palette (Light theme)
    COLORS = {
        'bg_primary': '#FFFFFF',
        'bg_secondary': '#F8FAFC',
        'bg_tertiary': '#F1F5F9',
        'text_primary': '#1E293B',
        'text_secondary': '#64748B',
        'text_muted': '#94A3B8',
        'accent_primary': '#3B82F6',  # Blue
        'accent_success': '#10B981',  # Green
        'accent_warning': '#F59E0B',  # Amber
        'accent_danger': '#EF4444',   # Red
        'accent_info': '#6366F1',     # Indigo
        'border': '#E2E8F0',
        'speaker_me': '#059669',      # Emerald
        'speaker_him': '#7C3AED',     # Violet
        'link': '#2563EB',
    }

    def __init__(self, meeting_id: int, parent_window=None):
        self.meeting_id = meeting_id
        self.parent_window = parent_window

        # Create window
        if parent_window:
            self.root = tk.Toplevel(parent_window)
        else:
            self.root = tk.Tk()

        self.setup_window()

        # Load data
        self.meeting = None
        self.transcripts = []
        self.summary_data = None
        self.enhanced_summary = None

        # Create UI
        self.create_widgets()

        # Load meeting data
        self.load_meeting_data()

    def setup_window(self):
        """Configure window"""
        self.root.title("Meeting Summary")
        self.root.geometry("900x700")
        self.root.configure(bg=self.COLORS['bg_primary'])
        self.root.minsize(800, 600)

    def create_widgets(self):
        """Create all UI components"""
        # Main container
        main = tk.Frame(self.root, bg=self.COLORS['bg_primary'])
        main.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)

        # Header
        self.create_header(main)

        # Tab navigation
        self.create_tab_navigation(main)

        # Content area
        self.content_frame = tk.Frame(main, bg=self.COLORS['bg_primary'])
        self.content_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        # Create tab content frames
        self.summary_frame = tk.Frame(self.content_frame, bg=self.COLORS['bg_primary'])
        self.transcript_frame = tk.Frame(self.content_frame, bg=self.COLORS['bg_primary'])
        self.usage_frame = tk.Frame(self.content_frame, bg=self.COLORS['bg_primary'])

        # Create content for each tab
        self.create_summary_tab()
        self.create_transcript_tab()
        self.create_usage_tab()

        # Show summary tab by default
        self.show_tab('summary')

        # Footer with export options
        self.create_footer(main)

    def create_header(self, parent):
        """Create header section"""
        header = tk.Frame(parent, bg=self.COLORS['bg_primary'])
        header.pack(fill=tk.X, pady=(0, 20))

        # Title row
        title_row = tk.Frame(header, bg=self.COLORS['bg_primary'])
        title_row.pack(fill=tk.X)

        self.title_label = tk.Label(
            title_row,
            text="Meeting Summary",
            font=('Segoe UI', 22, 'bold'),
            fg=self.COLORS['text_primary'],
            bg=self.COLORS['bg_primary']
        )
        self.title_label.pack(side=tk.LEFT)

        # Regenerate button
        regen_btn = tk.Button(
            title_row,
            text="Regenerate Summary",
            font=('Segoe UI', 10),
            bg=self.COLORS['accent_primary'],
            fg='#FFFFFF',
            activebackground='#2563EB',
            relief=tk.FLAT,
            padx=15,
            pady=6,
            cursor='hand2',
            command=self.regenerate_summary
        )
        regen_btn.pack(side=tk.RIGHT)

        # Meta row
        meta_row = tk.Frame(header, bg=self.COLORS['bg_primary'])
        meta_row.pack(fill=tk.X, pady=(8, 0))

        self.meta_label = tk.Label(
            meta_row,
            text="Loading...",
            font=('Segoe UI', 11),
            fg=self.COLORS['text_secondary'],
            bg=self.COLORS['bg_primary']
        )
        self.meta_label.pack(side=tk.LEFT)

    def create_tab_navigation(self, parent):
        """Create tab navigation bar"""
        nav_frame = tk.Frame(parent, bg=self.COLORS['bg_secondary'])
        nav_frame.pack(fill=tk.X, pady=(0, 15))

        nav_inner = tk.Frame(nav_frame, bg=self.COLORS['bg_secondary'])
        nav_inner.pack(fill=tk.X, padx=5, pady=5)

        self.tab_buttons = {}

        tabs = [
            ('summary', 'Summary'),
            ('transcript', 'Transcript'),
            ('usage', 'Usage & Export')
        ]

        for tab_id, tab_text in tabs:
            btn = tk.Button(
                nav_inner,
                text=tab_text,
                font=('Segoe UI', 11),
                bg=self.COLORS['bg_secondary'],
                fg=self.COLORS['text_secondary'],
                activebackground=self.COLORS['bg_tertiary'],
                relief=tk.FLAT,
                padx=25,
                pady=10,
                cursor='hand2',
                command=lambda t=tab_id: self.show_tab(t)
            )
            btn.pack(side=tk.LEFT, padx=2)
            self.tab_buttons[tab_id] = btn

    def show_tab(self, tab_id: str):
        """Show the selected tab"""
        # Hide all frames
        self.summary_frame.pack_forget()
        self.transcript_frame.pack_forget()
        self.usage_frame.pack_forget()

        # Reset all button styles
        for tid, btn in self.tab_buttons.items():
            btn.config(
                bg=self.COLORS['bg_secondary'],
                fg=self.COLORS['text_secondary'],
                font=('Segoe UI', 11)
            )

        # Show selected frame and highlight button
        if tab_id == 'summary':
            self.summary_frame.pack(fill=tk.BOTH, expand=True)
        elif tab_id == 'transcript':
            self.transcript_frame.pack(fill=tk.BOTH, expand=True)
        elif tab_id == 'usage':
            self.usage_frame.pack(fill=tk.BOTH, expand=True)

        self.tab_buttons[tab_id].config(
            bg=self.COLORS['accent_primary'],
            fg='#FFFFFF',
            font=('Segoe UI', 11, 'bold')
        )

    def create_summary_tab(self):
        """Create summary tab content"""
        # Scrollable frame
        canvas = tk.Canvas(self.summary_frame, bg=self.COLORS['bg_primary'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.summary_frame, orient="vertical", command=canvas.yview)
        scrollable = tk.Frame(canvas, bg=self.COLORS['bg_primary'])

        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Mouse wheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.summary_container = scrollable

        # Summary text widget (will be populated with data)
        self.summary_text = tk.Text(
            self.summary_container,
            wrap=tk.WORD,
            font=('Segoe UI', 11),
            bg=self.COLORS['bg_primary'],
            fg=self.COLORS['text_primary'],
            relief=tk.FLAT,
            padx=20,
            pady=15,
            width=90,
            height=35
        )
        self.summary_text.pack(fill=tk.BOTH, expand=True)

        # Configure tags
        self.summary_text.tag_configure('h1', font=('Segoe UI', 18, 'bold'), foreground=self.COLORS['text_primary'], spacing3=10)
        self.summary_text.tag_configure('h2', font=('Segoe UI', 14, 'bold'), foreground=self.COLORS['accent_primary'], spacing1=15, spacing3=5)
        self.summary_text.tag_configure('bullet', font=('Segoe UI', 11), foreground=self.COLORS['text_primary'], lmargin1=20, lmargin2=35)
        self.summary_text.tag_configure('keyword', font=('Segoe UI', 10), foreground=self.COLORS['accent_info'], background='#EEF2FF')
        self.summary_text.tag_configure('normal', font=('Segoe UI', 11), foreground=self.COLORS['text_primary'])
        self.summary_text.tag_configure('muted', font=('Segoe UI', 10), foreground=self.COLORS['text_muted'])

        # Placeholder
        self.summary_text.insert(tk.END, "Loading summary...\n\n", 'muted')
        self.summary_text.insert(tk.END, "The AI is generating a comprehensive summary of your meeting.", 'muted')
        self.summary_text.config(state=tk.DISABLED)

    def create_transcript_tab(self):
        """Create transcript tab content"""
        # Header
        header = tk.Frame(self.transcript_frame, bg=self.COLORS['bg_primary'])
        header.pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            header,
            text="Full Transcript",
            font=('Segoe UI', 14, 'bold'),
            fg=self.COLORS['text_primary'],
            bg=self.COLORS['bg_primary']
        ).pack(side=tk.LEFT)

        self.transcript_count_label = tk.Label(
            header,
            text="0 segments",
            font=('Segoe UI', 10),
            fg=self.COLORS['text_muted'],
            bg=self.COLORS['bg_primary']
        )
        self.transcript_count_label.pack(side=tk.RIGHT)

        # Transcript text
        self.transcript_text = scrolledtext.ScrolledText(
            self.transcript_frame,
            wrap=tk.WORD,
            font=('Consolas', 10),
            bg=self.COLORS['bg_secondary'],
            fg=self.COLORS['text_primary'],
            relief=tk.FLAT,
            padx=15,
            pady=15
        )
        self.transcript_text.pack(fill=tk.BOTH, expand=True)

        # Configure tags
        self.transcript_text.tag_configure('speaker_me', foreground=self.COLORS['speaker_me'], font=('Consolas', 10, 'bold'))
        self.transcript_text.tag_configure('speaker_him', foreground=self.COLORS['speaker_him'], font=('Consolas', 10, 'bold'))
        self.transcript_text.tag_configure('timestamp', foreground=self.COLORS['text_muted'], font=('Consolas', 9))

    def create_usage_tab(self):
        """Create usage & export tab content"""
        # Container
        container = tk.Frame(self.usage_frame, bg=self.COLORS['bg_primary'])
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Export section
        export_section = tk.LabelFrame(
            container,
            text="Export Options",
            font=('Segoe UI', 12, 'bold'),
            fg=self.COLORS['text_primary'],
            bg=self.COLORS['bg_primary'],
            padx=15,
            pady=15
        )
        export_section.pack(fill=tk.X, pady=(0, 20))

        export_btns = tk.Frame(export_section, bg=self.COLORS['bg_primary'])
        export_btns.pack(fill=tk.X)

        export_formats = [
            ("Export as JSON", self.export_json, self.COLORS['accent_primary']),
            ("Export as Markdown", self.export_markdown, self.COLORS['accent_info']),
            ("Export as Text", self.export_text, self.COLORS['text_secondary']),
            ("Copy to Clipboard", self.copy_to_clipboard, self.COLORS['accent_success']),
        ]

        for text, cmd, color in export_formats:
            btn = tk.Button(
                export_btns,
                text=text,
                font=('Segoe UI', 10),
                bg=color,
                fg='#FFFFFF',
                activebackground=color,
                relief=tk.FLAT,
                padx=15,
                pady=8,
                cursor='hand2',
                command=cmd
            )
            btn.pack(side=tk.LEFT, padx=(0, 10))

        # Usage stats section
        stats_section = tk.LabelFrame(
            container,
            text="Meeting Statistics",
            font=('Segoe UI', 12, 'bold'),
            fg=self.COLORS['text_primary'],
            bg=self.COLORS['bg_primary'],
            padx=15,
            pady=15
        )
        stats_section.pack(fill=tk.X, pady=(0, 20))

        self.stats_container = tk.Frame(stats_section, bg=self.COLORS['bg_primary'])
        self.stats_container.pack(fill=tk.X)

        # Stats will be populated later
        self.stats_labels = {}

        stats_items = [
            ("Duration", "duration"),
            ("Speakers", "speakers"),
            ("Total Words", "words"),
            ("Transcript Segments", "segments"),
            ("AI Insights Generated", "insights"),
        ]

        for label, key in stats_items:
            row = tk.Frame(self.stats_container, bg=self.COLORS['bg_primary'])
            row.pack(fill=tk.X, pady=3)

            tk.Label(
                row,
                text=f"{label}:",
                font=('Segoe UI', 10),
                fg=self.COLORS['text_secondary'],
                bg=self.COLORS['bg_primary'],
                width=20,
                anchor='w'
            ).pack(side=tk.LEFT)

            self.stats_labels[key] = tk.Label(
                row,
                text="-",
                font=('Segoe UI', 10, 'bold'),
                fg=self.COLORS['text_primary'],
                bg=self.COLORS['bg_primary']
            )
            self.stats_labels[key].pack(side=tk.LEFT)

        # Quick links section
        links_section = tk.LabelFrame(
            container,
            text="Quick Actions",
            font=('Segoe UI', 12, 'bold'),
            fg=self.COLORS['text_primary'],
            bg=self.COLORS['bg_primary'],
            padx=15,
            pady=15
        )
        links_section.pack(fill=tk.X)

        links_btns = tk.Frame(links_section, bg=self.COLORS['bg_primary'])
        links_btns.pack(fill=tk.X)

        actions = [
            ("Open Dashboard", self.open_dashboard),
            ("Start New Recording", self.start_new_recording),
            ("Delete This Meeting", self.delete_meeting),
        ]

        for text, cmd in actions:
            btn = tk.Button(
                links_btns,
                text=text,
                font=('Segoe UI', 10),
                bg=self.COLORS['bg_tertiary'],
                fg=self.COLORS['text_primary'],
                activebackground=self.COLORS['border'],
                relief=tk.FLAT,
                padx=15,
                pady=8,
                cursor='hand2',
                command=cmd
            )
            btn.pack(side=tk.LEFT, padx=(0, 10))

    def create_footer(self, parent):
        """Create footer"""
        footer = tk.Frame(parent, bg=self.COLORS['bg_tertiary'])
        footer.pack(fill=tk.X, pady=(10, 0))

        footer_inner = tk.Frame(footer, bg=self.COLORS['bg_tertiary'])
        footer_inner.pack(fill=tk.X, padx=15, pady=10)

        tk.Label(
            footer_inner,
            text="Nexus Meeting Recorder",
            font=('Segoe UI', 9),
            fg=self.COLORS['text_muted'],
            bg=self.COLORS['bg_tertiary']
        ).pack(side=tk.LEFT)

        tk.Label(
            footer_inner,
            text="Powered by AI",
            font=('Segoe UI', 9),
            fg=self.COLORS['text_muted'],
            bg=self.COLORS['bg_tertiary']
        ).pack(side=tk.RIGHT)

    def load_meeting_data(self):
        """Load meeting data from database"""
        def load():
            try:
                conn = sqlite3.connect(DB_PATH)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Load meeting
                cursor.execute('SELECT * FROM meetings WHERE id = ?', (self.meeting_id,))
                meeting_row = cursor.fetchone()
                if meeting_row:
                    self.meeting = dict(meeting_row)

                # Load transcripts
                cursor.execute('SELECT * FROM transcripts WHERE meeting_id = ? ORDER BY timestamp', (self.meeting_id,))
                self.transcripts = [dict(row) for row in cursor.fetchall()]

                # Load existing summary
                cursor.execute('SELECT * FROM summaries WHERE meeting_id = ?', (self.meeting_id,))
                summary_row = cursor.fetchone()
                if summary_row:
                    self.summary_data = dict(summary_row)

                # Load insights
                cursor.execute('SELECT * FROM insights WHERE meeting_id = ?', (self.meeting_id,))
                insights = [dict(row) for row in cursor.fetchall()]

                conn.close()

                # Update UI
                self.root.after(0, lambda: self.update_ui(insights))

                # Generate enhanced summary if we have transcripts
                if self.transcripts and not self.enhanced_summary:
                    self.generate_enhanced_summary()

            except Exception as e:
                print(f"Error loading meeting data: {e}")
                self.root.after(0, lambda: self.show_error(f"Failed to load meeting: {e}"))

        threading.Thread(target=load, daemon=True).start()

    def update_ui(self, insights: List[Dict]):
        """Update UI with loaded data"""
        if self.meeting:
            self.title_label.config(text=self.meeting['title'])

            try:
                date_obj = datetime.fromisoformat(self.meeting['date'])
                date_str = date_obj.strftime("%B %d, %Y at %I:%M %p")
            except:
                date_str = self.meeting['date']

            duration = self.meeting.get('duration_seconds', 0)
            if duration > 3600:
                duration_str = f"{duration // 3600}h {(duration % 3600) // 60}m"
            elif duration > 60:
                duration_str = f"{duration // 60} minutes"
            else:
                duration_str = f"{duration} seconds"

            self.meta_label.config(text=f"{date_str}  |  Duration: {duration_str}")

            # Update stats
            self.stats_labels['duration'].config(text=duration_str)

            participants = json.loads(self.meeting.get('participants', '[]')) if isinstance(self.meeting.get('participants'), str) else []
            self.stats_labels['speakers'].config(text=str(len(participants)) if participants else "2 (Me, Him)")

        # Update transcript
        self.update_transcript_tab()

        # Update stats
        total_words = sum(len(t.get('text', '').split()) for t in self.transcripts)
        self.stats_labels['words'].config(text=str(total_words))
        self.stats_labels['segments'].config(text=str(len(self.transcripts)))
        self.stats_labels['insights'].config(text=str(len(insights)))
        self.transcript_count_label.config(text=f"{len(self.transcripts)} segments")

    def update_transcript_tab(self):
        """Update transcript tab content"""
        self.transcript_text.config(state=tk.NORMAL)
        self.transcript_text.delete(1.0, tk.END)

        for t in self.transcripts:
            try:
                ts = datetime.fromisoformat(t['timestamp']).strftime("%H:%M:%S")
            except:
                ts = t.get('timestamp', '')[:8]

            tag = 'speaker_me' if t['speaker'] == 'Me' else 'speaker_him'

            self.transcript_text.insert(tk.END, f"[{ts}] ", 'timestamp')
            self.transcript_text.insert(tk.END, f"{t['speaker']}: ", tag)
            self.transcript_text.insert(tk.END, f"{t['text']}\n\n")

        self.transcript_text.config(state=tk.DISABLED)

    def generate_enhanced_summary(self):
        """Generate enhanced summary with all sections"""
        if not self.transcripts:
            return

        def generate():
            try:
                # Build transcript text
                transcript_text = "\n".join([f"[{t['speaker']}]: {t['text']}" for t in self.transcripts])

                prompt = f"""Analyze this meeting transcript and generate a comprehensive summary in the following format.
Be specific and extract actual content from the transcript.

TRANSCRIPT:
{transcript_text}

Generate a detailed JSON response with these sections:

{{
    "title": "Meeting title based on content",
    "action_items": [
        "Specific action item 1 with owner if mentioned",
        "Specific action item 2"
    ],
    "key_topics_discussed": [
        "Topic 1 - brief description",
        "Topic 2 - brief description"
    ],
    "potential_questions": [
        "Question that could be asked in follow-up",
        "Another relevant question"
    ],
    "keywords_mentioned": [
        "keyword1", "keyword2", "keyword3"
    ],
    "decisions_made": [
        "Decision 1",
        "Decision 2"
    ],
    "key_insights": [
        "Important insight from the discussion",
        "Another insight"
    ],
    "next_steps": [
        "Recommended next step 1",
        "Recommended next step 2"
    ],
    "summary_paragraph": "A 2-3 sentence executive summary of the meeting"
}}

Return ONLY valid JSON, no markdown formatting."""

                if HTTPX_AVAILABLE:
                    with httpx.Client(timeout=60.0) as client:
                        response = client.post(
                            f"{LLM_SERVICE}/complete",
                            json={
                                "prompt": prompt,
                                "task_type": "extraction",
                                "max_tokens": 2000,
                                "temperature": 0.5
                            }
                        )

                        if response.status_code == 200:
                            result = response.json()
                            text = result.get('text', '{}')

                            # Clean up response (remove markdown if present)
                            text = text.strip()
                            if text.startswith('```'):
                                text = text.split('\n', 1)[1]
                            if text.endswith('```'):
                                text = text.rsplit('```', 1)[0]
                            text = text.strip()

                            try:
                                self.enhanced_summary = json.loads(text)
                            except:
                                # Fallback if JSON parsing fails
                                self.enhanced_summary = {
                                    "summary_paragraph": text,
                                    "action_items": [],
                                    "key_topics_discussed": [],
                                    "keywords_mentioned": []
                                }

                            self.root.after(0, self.display_enhanced_summary)

            except Exception as e:
                print(f"Error generating summary: {e}")
                self.root.after(0, lambda: self.show_summary_error(str(e)))

        threading.Thread(target=generate, daemon=True).start()

    def display_enhanced_summary(self):
        """Display the enhanced summary"""
        self.summary_text.config(state=tk.NORMAL)
        self.summary_text.delete(1.0, tk.END)

        s = self.enhanced_summary

        # Title
        title = s.get('title', self.meeting.get('title', 'Meeting Summary'))
        self.summary_text.insert(tk.END, f"{title}\n\n", 'h1')

        # Executive Summary
        if s.get('summary_paragraph'):
            self.summary_text.insert(tk.END, "Executive Summary\n", 'h2')
            self.summary_text.insert(tk.END, f"{s['summary_paragraph']}\n\n", 'normal')

        # Action Items
        if s.get('action_items'):
            self.summary_text.insert(tk.END, "Action Items\n", 'h2')
            for item in s['action_items']:
                self.summary_text.insert(tk.END, f"  - {item}\n", 'bullet')
            self.summary_text.insert(tk.END, "\n")

        # Key Topics Discussed
        if s.get('key_topics_discussed'):
            self.summary_text.insert(tk.END, "Key Topics Discussed\n", 'h2')
            for topic in s['key_topics_discussed']:
                self.summary_text.insert(tk.END, f"  - {topic}\n", 'bullet')
            self.summary_text.insert(tk.END, "\n")

        # Decisions Made
        if s.get('decisions_made'):
            self.summary_text.insert(tk.END, "Decisions Made\n", 'h2')
            for decision in s['decisions_made']:
                self.summary_text.insert(tk.END, f"  - {decision}\n", 'bullet')
            self.summary_text.insert(tk.END, "\n")

        # Potential Questions for Future Reference
        if s.get('potential_questions'):
            self.summary_text.insert(tk.END, "Potential Questions for Future Reference\n", 'h2')
            for q in s['potential_questions']:
                self.summary_text.insert(tk.END, f"  - {q}\n", 'bullet')
            self.summary_text.insert(tk.END, "\n")

        # Key Insights
        if s.get('key_insights'):
            self.summary_text.insert(tk.END, "Key Insights\n", 'h2')
            for insight in s['key_insights']:
                self.summary_text.insert(tk.END, f"  - {insight}\n", 'bullet')
            self.summary_text.insert(tk.END, "\n")

        # Keywords Mentioned
        if s.get('keywords_mentioned'):
            self.summary_text.insert(tk.END, "Keywords Mentioned\n", 'h2')
            keywords = ", ".join(s['keywords_mentioned'])
            self.summary_text.insert(tk.END, f"  {keywords}\n\n", 'keyword')

        # Next Steps
        if s.get('next_steps'):
            self.summary_text.insert(tk.END, "Recommended Next Steps\n", 'h2')
            for step in s['next_steps']:
                self.summary_text.insert(tk.END, f"  - {step}\n", 'bullet')
            self.summary_text.insert(tk.END, "\n")

        self.summary_text.config(state=tk.DISABLED)

    def show_summary_error(self, error: str):
        """Show error in summary tab"""
        self.summary_text.config(state=tk.NORMAL)
        self.summary_text.delete(1.0, tk.END)
        self.summary_text.insert(tk.END, "Failed to generate summary\n\n", 'h2')
        self.summary_text.insert(tk.END, f"Error: {error}\n\n", 'muted')
        self.summary_text.insert(tk.END, "Please check if the LLM service is running and try again.", 'normal')
        self.summary_text.config(state=tk.DISABLED)

    def regenerate_summary(self):
        """Regenerate the summary"""
        self.summary_text.config(state=tk.NORMAL)
        self.summary_text.delete(1.0, tk.END)
        self.summary_text.insert(tk.END, "Regenerating summary...\n\n", 'muted')
        self.summary_text.insert(tk.END, "Please wait while the AI analyzes your meeting.", 'muted')
        self.summary_text.config(state=tk.DISABLED)

        self.enhanced_summary = None
        self.generate_enhanced_summary()

    def export_json(self):
        """Export as JSON"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialfilename=f"meeting_{self.meeting_id}_export.json"
        )
        if not filename:
            return

        export_data = {
            "meeting": self.meeting,
            "transcripts": self.transcripts,
            "summary": self.enhanced_summary
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        messagebox.showinfo("Export Complete", f"Meeting exported to:\n{filename}")

    def export_markdown(self):
        """Export as Markdown"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown files", "*.md")],
            initialfilename=f"meeting_{self.meeting_id}_summary.md"
        )
        if not filename:
            return

        md = self.generate_markdown()

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(md)

        messagebox.showinfo("Export Complete", f"Meeting exported to:\n{filename}")

    def export_text(self):
        """Export as plain text"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
            initialfilename=f"meeting_{self.meeting_id}_summary.txt"
        )
        if not filename:
            return

        # Get text from summary widget
        self.summary_text.config(state=tk.NORMAL)
        text = self.summary_text.get(1.0, tk.END)
        self.summary_text.config(state=tk.DISABLED)

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(text)

        messagebox.showinfo("Export Complete", f"Meeting exported to:\n{filename}")

    def copy_to_clipboard(self):
        """Copy summary to clipboard"""
        md = self.generate_markdown()
        self.root.clipboard_clear()
        self.root.clipboard_append(md)
        messagebox.showinfo("Copied", "Summary copied to clipboard!")

    def generate_markdown(self) -> str:
        """Generate markdown formatted summary"""
        s = self.enhanced_summary or {}
        m = self.meeting or {}

        md = f"# {s.get('title', m.get('title', 'Meeting Summary'))}\n\n"

        if s.get('summary_paragraph'):
            md += f"## Executive Summary\n\n{s['summary_paragraph']}\n\n"

        if s.get('action_items'):
            md += "## Action Items\n\n"
            for item in s['action_items']:
                md += f"- {item}\n"
            md += "\n"

        if s.get('key_topics_discussed'):
            md += "## Key Topics Discussed\n\n"
            for topic in s['key_topics_discussed']:
                md += f"- {topic}\n"
            md += "\n"

        if s.get('decisions_made'):
            md += "## Decisions Made\n\n"
            for d in s['decisions_made']:
                md += f"- {d}\n"
            md += "\n"

        if s.get('potential_questions'):
            md += "## Potential Questions for Future Reference\n\n"
            for q in s['potential_questions']:
                md += f"- {q}\n"
            md += "\n"

        if s.get('key_insights'):
            md += "## Key Insights\n\n"
            for insight in s['key_insights']:
                md += f"- {insight}\n"
            md += "\n"

        if s.get('keywords_mentioned'):
            md += "## Keywords Mentioned\n\n"
            md += ", ".join(s['keywords_mentioned']) + "\n\n"

        if s.get('next_steps'):
            md += "## Recommended Next Steps\n\n"
            for step in s['next_steps']:
                md += f"- {step}\n"
            md += "\n"

        return md

    def open_dashboard(self):
        """Open dashboard"""
        import subprocess
        import sys
        dashboard_path = Path(__file__).parent / "meeting_dashboard.py"
        subprocess.Popen([sys.executable, str(dashboard_path)], creationflags=subprocess.CREATE_NEW_CONSOLE)

    def start_new_recording(self):
        """Start new recording"""
        import subprocess
        import sys
        overlay_path = Path(__file__).parent / "overlay_ui.py"
        subprocess.Popen([sys.executable, str(overlay_path)], creationflags=subprocess.CREATE_NEW_CONSOLE)
        self.root.destroy()

    def delete_meeting(self):
        """Delete this meeting"""
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this meeting?\nThis cannot be undone."):
            try:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute('DELETE FROM transcripts WHERE meeting_id = ?', (self.meeting_id,))
                cursor.execute('DELETE FROM insights WHERE meeting_id = ?', (self.meeting_id,))
                cursor.execute('DELETE FROM summaries WHERE meeting_id = ?', (self.meeting_id,))
                cursor.execute('DELETE FROM meetings WHERE id = ?', (self.meeting_id,))
                conn.commit()
                conn.close()

                messagebox.showinfo("Deleted", "Meeting deleted successfully.")
                self.root.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete: {e}")

    def show_error(self, message: str):
        """Show error message"""
        messagebox.showerror("Error", message)

    def run(self):
        """Run the window"""
        self.root.mainloop()


def open_summary_page(meeting_id: int, parent=None):
    """Helper function to open summary page"""
    page = SummaryPage(meeting_id, parent)
    return page


if __name__ == "__main__":
    import sys
    meeting_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    page = SummaryPage(meeting_id)
    page.run()

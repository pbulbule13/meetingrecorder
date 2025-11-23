/**
 * Database Service
 * Manages SQLite database and all data operations
 */

const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs').promises;
const { v4: uuidv4 } = require('uuid');
const crypto = require('crypto');

class DatabaseService {
  constructor(userDataPath) {
    this.userDataPath = userDataPath;
    this.dbPath = path.join(userDataPath, 'data', 'nexus.db');
    this.db = null;
    this.encryptionKey = null;
  }

  /**
   * Initialize database with schema
   */
  async initialize() {
    // Ensure data directory exists
    const dataDir = path.dirname(this.dbPath);
    await fs.mkdir(dataDir, { recursive: true });

    // Open database
    this.db = new Database(this.dbPath);
    this.db.pragma('journal_mode = WAL');
    this.db.pragma('foreign_keys = ON');

    // Create tables
    this.createSchema();

    // Create indexes
    this.createIndexes();

    console.log('Database initialized:', this.dbPath);
  }

  /**
   * Create database schema
   */
  createSchema() {
    this.db.exec(`
      -- Meetings table
      CREATE TABLE IF NOT EXISTS meetings (
        meeting_id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        start_time DATETIME NOT NULL,
        end_time DATETIME,
        duration_seconds INTEGER,
        status TEXT CHECK(status IN ('recording', 'processing', 'completed', 'error')) DEFAULT 'recording',
        recording_path TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
      );

      -- Participants table
      CREATE TABLE IF NOT EXISTS participants (
        participant_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE,
        voice_profile_path TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      );

      -- Meeting participants junction table
      CREATE TABLE IF NOT EXISTS meeting_participants (
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
      CREATE TABLE IF NOT EXISTS transcripts (
        transcript_id TEXT PRIMARY KEY,
        meeting_id TEXT NOT NULL,
        full_text TEXT NOT NULL,
        language TEXT DEFAULT 'en',
        confidence_avg REAL,
        word_count INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (meeting_id) REFERENCES meetings(meeting_id) ON DELETE CASCADE
      );

      -- Transcript segments
      CREATE TABLE IF NOT EXISTS transcript_segments (
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

      -- Summaries table
      CREATE TABLE IF NOT EXISTS summaries (
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
      CREATE TABLE IF NOT EXISTS decisions (
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
      CREATE TABLE IF NOT EXISTS action_items (
        action_id TEXT PRIMARY KEY,
        meeting_id TEXT NOT NULL,
        task TEXT NOT NULL,
        assignee_id TEXT,
        due_date DATE,
        priority TEXT CHECK(priority IN ('low', 'medium', 'high', 'critical')) DEFAULT 'medium',
        status TEXT CHECK(status IN ('pending', 'in_progress', 'completed', 'cancelled')) DEFAULT 'pending',
        timestamp_ms INTEGER,
        completed_at DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (meeting_id) REFERENCES meetings(meeting_id) ON DELETE CASCADE,
        FOREIGN KEY (assignee_id) REFERENCES participants(participant_id)
      );

      -- Highlights table
      CREATE TABLE IF NOT EXISTS highlights (
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

      -- Meeting analytics table
      CREATE TABLE IF NOT EXISTS meeting_analytics (
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
      CREATE TABLE IF NOT EXISTS speaker_analytics (
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

      -- Settings table
      CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value JSON NOT NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
      );

      -- API Keys table
      CREATE TABLE IF NOT EXISTS api_keys (
        key_id TEXT PRIMARY KEY,
        key_hash TEXT NOT NULL UNIQUE,
        name TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_used_at DATETIME,
        is_active BOOLEAN DEFAULT 1
      );
    `);
  }

  /**
   * Create database indexes
   */
  createIndexes() {
    this.db.exec(`
      CREATE INDEX IF NOT EXISTS idx_meetings_start_time ON meetings(start_time);
      CREATE INDEX IF NOT EXISTS idx_meetings_status ON meetings(status);
      CREATE INDEX IF NOT EXISTS idx_transcript_segments_transcript ON transcript_segments(transcript_id);
      CREATE INDEX IF NOT EXISTS idx_transcript_segments_speaker ON transcript_segments(speaker_id);
      CREATE INDEX IF NOT EXISTS idx_action_items_assignee ON action_items(assignee_id);
      CREATE INDEX IF NOT EXISTS idx_action_items_status ON action_items(status);
      CREATE INDEX IF NOT EXISTS idx_action_items_due_date ON action_items(due_date);
    `);

    // Create FTS5 virtual table for full-text search
    this.db.exec(`
      CREATE VIRTUAL TABLE IF NOT EXISTS transcript_fts USING fts5(
        segment_id UNINDEXED,
        text,
        speaker_name,
        meeting_title,
        content='transcript_segments'
      );
    `);
  }

  /**
   * Create a new meeting
   */
  createMeeting(title, options = {}) {
    const meetingId = uuidv4();
    const stmt = this.db.prepare(`
      INSERT INTO meetings (meeting_id, title, start_time, status)
      VALUES (?, ?, datetime('now'), 'recording')
    `);

    stmt.run(meetingId, title);
    return meetingId;
  }

  /**
   * Update meeting
   */
  updateMeeting(meetingId, updates) {
    const fields = Object.keys(updates);
    const values = Object.values(updates);

    const setClause = fields.map(f => `${f} = ?`).join(', ');
    const stmt = this.db.prepare(`
      UPDATE meetings
      SET ${setClause}, updated_at = datetime('now')
      WHERE meeting_id = ?
    `);

    stmt.run([...values, meetingId]);
  }

  /**
   * Get meetings with optional filters
   */
  getMeetings(filters = {}) {
    let query = `
      SELECT
        m.*,
        COUNT(DISTINCT mp.participant_id) as participant_count,
        COUNT(DISTINCT ai.action_id) as action_item_count
      FROM meetings m
      LEFT JOIN meeting_participants mp ON m.meeting_id = mp.meeting_id
      LEFT JOIN action_items ai ON m.meeting_id = ai.meeting_id
      WHERE 1=1
    `;

    const params = [];

    if (filters.status) {
      query += ` AND m.status = ?`;
      params.push(filters.status);
    }

    if (filters.startDate) {
      query += ` AND DATE(m.start_time) >= DATE(?)`;
      params.push(filters.startDate);
    }

    if (filters.endDate) {
      query += ` AND DATE(m.start_time) <= DATE(?)`;
      params.push(filters.endDate);
    }

    query += `
      GROUP BY m.meeting_id
      ORDER BY m.start_time DESC
      LIMIT ? OFFSET ?
    `;

    params.push(filters.limit || 50, filters.offset || 0);

    const stmt = this.db.prepare(query);
    return stmt.all(...params);
  }

  /**
   * Get single meeting with all details
   */
  getMeeting(meetingId) {
    const meeting = this.db.prepare(`
      SELECT * FROM meetings WHERE meeting_id = ?
    `).get(meetingId);

    if (!meeting) {
      throw new Error(`Meeting ${meetingId} not found`);
    }

    // Get participants
    meeting.participants = this.db.prepare(`
      SELECT p.*, mp.role, mp.joined_at, mp.left_at
      FROM participants p
      JOIN meeting_participants mp ON p.participant_id = mp.participant_id
      WHERE mp.meeting_id = ?
    `).all(meetingId);

    // Get summary
    meeting.summary = this.db.prepare(`
      SELECT * FROM summaries WHERE meeting_id = ? ORDER BY created_at DESC LIMIT 1
    `).get(meetingId);

    // Get decisions
    meeting.decisions = this.db.prepare(`
      SELECT * FROM decisions WHERE meeting_id = ? ORDER BY timestamp_ms
    `).all(meetingId);

    // Get action items
    meeting.action_items = this.db.prepare(`
      SELECT * FROM action_items WHERE meeting_id = ? ORDER BY priority DESC, due_date
    `).all(meetingId);

    // Get highlights
    meeting.highlights = this.db.prepare(`
      SELECT * FROM highlights WHERE meeting_id = ? ORDER BY importance_score DESC
    `).all(meetingId);

    // Get analytics
    meeting.analytics = this.db.prepare(`
      SELECT * FROM meeting_analytics WHERE meeting_id = ?
    `).get(meetingId);

    meeting.speaker_analytics = this.db.prepare(`
      SELECT sa.*, p.name, p.email
      FROM speaker_analytics sa
      JOIN participants p ON sa.participant_id = p.participant_id
      WHERE sa.meeting_id = ?
    `).all(meetingId);

    return meeting;
  }

  /**
   * Add transcript segment
   */
  addTranscriptSegment(transcriptId, segment) {
    const segmentId = uuidv4();
    const stmt = this.db.prepare(`
      INSERT INTO transcript_segments
      (segment_id, transcript_id, speaker_id, text, start_ms, end_ms, confidence, sentiment)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `);

    stmt.run(
      segmentId,
      transcriptId,
      segment.speaker_id,
      segment.text,
      segment.start_ms,
      segment.end_ms,
      segment.confidence,
      segment.sentiment
    );

    // Update FTS index
    this.updateFTSIndex(segmentId, segment);

    return segmentId;
  }

  /**
   * Update FTS index for search
   */
  updateFTSIndex(segmentId, segment) {
    const meeting = this.db.prepare(`
      SELECT m.title, p.name as speaker_name
      FROM transcript_segments ts
      JOIN transcripts t ON ts.transcript_id = t.transcript_id
      JOIN meetings m ON t.meeting_id = m.meeting_id
      LEFT JOIN participants p ON ts.speaker_id = p.participant_id
      WHERE ts.segment_id = ?
    `).get(segmentId);

    if (meeting) {
      this.db.prepare(`
        INSERT INTO transcript_fts (segment_id, text, speaker_name, meeting_title)
        VALUES (?, ?, ?, ?)
      `).run(segmentId, segment.text, meeting.speaker_name || 'Unknown', meeting.title);
    }
  }

  /**
   * Search transcripts
   */
  searchTranscripts(query, options = {}) {
    const stmt = this.db.prepare(`
      SELECT
        ts.segment_id,
        ts.text,
        ts.start_ms,
        ts.end_ms,
        p.name as speaker_name,
        m.meeting_id,
        m.title as meeting_title,
        m.start_time as meeting_date,
        snippet(transcript_fts, 1, '<mark>', '</mark>', '...', 30) as snippet
      FROM transcript_fts fts
      JOIN transcript_segments ts ON fts.segment_id = ts.segment_id
      JOIN transcripts t ON ts.transcript_id = t.transcript_id
      JOIN meetings m ON t.meeting_id = m.meeting_id
      LEFT JOIN participants p ON ts.speaker_id = p.participant_id
      WHERE transcript_fts MATCH ?
      ORDER BY rank
      LIMIT ? OFFSET ?
    `);

    return stmt.all(query, options.limit || 50, options.offset || 0);
  }

  /**
   * Create or update participant
   */
  upsertParticipant(name, email = null) {
    let participant = null;

    if (email) {
      participant = this.db.prepare(`
        SELECT * FROM participants WHERE email = ?
      `).get(email);
    }

    if (!participant) {
      participant = this.db.prepare(`
        SELECT * FROM participants WHERE name = ?
      `).get(name);
    }

    if (participant) {
      return participant.participant_id;
    }

    const participantId = uuidv4();
    this.db.prepare(`
      INSERT INTO participants (participant_id, name, email)
      VALUES (?, ?, ?)
    `).run(participantId, name, email);

    return participantId;
  }

  /**
   * Add participant to meeting
   */
  addMeetingParticipant(meetingId, participantId, role = 'participant') {
    this.db.prepare(`
      INSERT OR IGNORE INTO meeting_participants (meeting_id, participant_id, role, joined_at)
      VALUES (?, ?, ?, datetime('now'))
    `).run(meetingId, participantId, role);
  }

  /**
   * Get action items
   */
  getActionItems(filters = {}) {
    let query = `
      SELECT
        ai.*,
        p.name as assignee_name,
        m.title as meeting_title,
        m.start_time as meeting_date
      FROM action_items ai
      LEFT JOIN participants p ON ai.assignee_id = p.participant_id
      LEFT JOIN meetings m ON ai.meeting_id = m.meeting_id
      WHERE 1=1
    `;

    const params = [];

    if (filters.status) {
      query += ` AND ai.status = ?`;
      params.push(filters.status);
    }

    if (filters.assigneeId) {
      query += ` AND ai.assignee_id = ?`;
      params.push(filters.assigneeId);
    }

    if (filters.overdue) {
      query += ` AND ai.due_date < DATE('now') AND ai.status != 'completed'`;
    }

    query += ` ORDER BY ai.priority DESC, ai.due_date`;

    const stmt = this.db.prepare(query);
    return stmt.all(...params);
  }

  /**
   * Update action item
   */
  updateActionItem(actionId, updates) {
    if (updates.status === 'completed' && !updates.completed_at) {
      updates.completed_at = new Date().toISOString();
    }

    const fields = Object.keys(updates);
    const values = Object.values(updates);

    const setClause = fields.map(f => `${f} = ?`).join(', ');
    const stmt = this.db.prepare(`
      UPDATE action_items
      SET ${setClause}
      WHERE action_id = ?
    `);

    stmt.run([...values, actionId]);
  }

  /**
   * Save meeting summary
   */
  saveSummary(meetingId, summary, modelUsed) {
    const summaryId = uuidv4();
    this.db.prepare(`
      INSERT INTO summaries
      (summary_id, meeting_id, executive_summary, key_topics, detailed_summary, model_used)
      VALUES (?, ?, ?, ?, ?, ?)
    `).run(
      summaryId,
      meetingId,
      summary.executive_summary,
      JSON.stringify(summary.key_topics),
      summary.detailed_summary,
      modelUsed
    );

    return summaryId;
  }

  /**
   * Save decision
   */
  saveDecision(meetingId, decision) {
    const decisionId = uuidv4();
    this.db.prepare(`
      INSERT INTO decisions
      (decision_id, meeting_id, decision, rationale, participants, timestamp_ms)
      VALUES (?, ?, ?, ?, ?, ?)
    `).run(
      decisionId,
      meetingId,
      decision.decision,
      decision.rationale,
      JSON.stringify(decision.participants),
      decision.timestamp_ms
    );

    return decisionId;
  }

  /**
   * Save action item
   */
  saveActionItem(meetingId, actionItem) {
    const actionId = uuidv4();
    this.db.prepare(`
      INSERT INTO action_items
      (action_id, meeting_id, task, assignee_id, due_date, priority, timestamp_ms)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(
      actionId,
      meetingId,
      actionItem.task,
      actionItem.assignee_id,
      actionItem.due_date,
      actionItem.priority,
      actionItem.timestamp_ms
    );

    return actionId;
  }

  /**
   * Save analytics
   */
  saveAnalytics(meetingId, analytics) {
    const analyticsId = uuidv4();
    this.db.prepare(`
      INSERT OR REPLACE INTO meeting_analytics
      (analytics_id, meeting_id, total_words, avg_speaking_pace, total_interruptions,
       sentiment_timeline, engagement_score)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(
      analyticsId,
      meetingId,
      analytics.total_words,
      analytics.avg_speaking_pace,
      analytics.total_interruptions,
      JSON.stringify(analytics.sentiment_timeline),
      analytics.engagement_score
    );
  }

  /**
   * Save speaker analytics
   */
  saveSpeakerAnalytics(meetingId, participantId, analytics) {
    const id = uuidv4();
    this.db.prepare(`
      INSERT OR REPLACE INTO speaker_analytics
      (speaker_analytics_id, meeting_id, participant_id, talk_time_percent, word_count,
       avg_sentiment, interruption_count, speaking_pace_wpm, questions_asked)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      id,
      meetingId,
      participantId,
      analytics.talk_time_percent,
      analytics.word_count,
      analytics.avg_sentiment,
      analytics.interruption_count,
      analytics.speaking_pace_wpm,
      analytics.questions_asked
    );
  }

  /**
   * Generate API key
   */
  generateAPIKey(name) {
    const key = `nxs_${crypto.randomBytes(24).toString('hex')}`;
    const keyHash = crypto.createHash('sha256').update(key).digest('hex');
    const keyId = uuidv4();

    this.db.prepare(`
      INSERT INTO api_keys (key_id, key_hash, name)
      VALUES (?, ?, ?)
    `).run(keyId, keyHash, name);

    return { keyId, key }; // Return key only once
  }

  /**
   * Verify API key
   */
  verifyAPIKey(key) {
    const keyHash = crypto.createHash('sha256').update(key).digest('hex');
    const result = this.db.prepare(`
      SELECT * FROM api_keys WHERE key_hash = ? AND is_active = 1
    `).get(keyHash);

    if (result) {
      // Update last used
      this.db.prepare(`
        UPDATE api_keys SET last_used_at = datetime('now') WHERE key_id = ?
      `).run(result.key_id);
    }

    return result !== undefined;
  }

  /**
   * Close database connection
   */
  async close() {
    if (this.db) {
      this.db.close();
      console.log('Database closed');
    }
  }
}

module.exports = DatabaseService;

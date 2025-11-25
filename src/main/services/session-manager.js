/**
 * Session Manager
 * Manages recording sessions and coordinates between services
 */

const EventEmitter = require('events');
const { v4: uuidv4 } = require('uuid');
const axios = require('axios');
const path = require('path');
const fs = require('fs').promises;

class SessionManager extends EventEmitter {
  constructor(database, audioCapture) {
    super();
    this.database = database;
    this.audioCapture = audioCapture;
    this.activeSessions = new Map();
    this.pythonServices = {
      transcription: 'http://127.0.0.1:38421',
      llm: 'http://127.0.0.1:45231',
      rag: 'http://127.0.0.1:53847'
    };
  }

  /**
   * Start a new recording session
   */
  async start(options = {}) {
    const sessionId = uuidv4();
    const title = options.title || `Meeting ${new Date().toLocaleString()}`;

    // Create meeting in database
    const meetingId = this.database.createMeeting(title);

    // Initialize session state
    const session = {
      sessionId,
      meetingId,
      title,
      status: 'recording',
      startTime: Date.now(),
      transcriptId: uuidv4(),
      segments: [],
      audioBuffer: [],
      lastProcessedTime: 0
    };

    this.activeSessions.set(sessionId, session);

    // Start audio capture
    try {
      await this.audioCapture.start({
        sessionId,
        onAudioChunk: (chunk) => this.handleAudioChunk(sessionId, chunk),
        onError: (error) => this.handleError(sessionId, error)
      });

      console.log(`Session started: ${sessionId} for meeting ${meetingId}`);
      return sessionId;

    } catch (error) {
      this.activeSessions.delete(sessionId);
      throw new Error(`Failed to start audio capture: ${error.message}`);
    }
  }

  /**
   * Handle audio chunk from capture service
   */
  async handleAudioChunk(sessionId, audioChunk) {
    const session = this.activeSessions.get(sessionId);
    if (!session || session.status === 'paused') {
      return;
    }

    session.audioBuffer.push(audioChunk);

    // Process every 5 seconds of audio
    if (audioChunk.timestamp - session.lastProcessedTime >= 5000) {
      await this.processAudioBuffer(sessionId);
      session.lastProcessedTime = audioChunk.timestamp;
    }
  }

  /**
   * Process accumulated audio buffer
   */
  async processAudioBuffer(sessionId) {
    const session = this.activeSessions.get(sessionId);
    if (!session || session.audioBuffer.length === 0) {
      return;
    }

    try {
      // Combine audio chunks
      const audioData = Buffer.concat(session.audioBuffer.map(c => c.data));
      session.audioBuffer = [];

      // Send to transcription service
      const transcriptResult = await this.transcribe(sessionId, audioData);

      if (transcriptResult && transcriptResult.segments) {
        for (const segment of transcriptResult.segments) {
          // Save segment to database
          const speakerId = await this.getOrCreateSpeaker(
            session.meetingId,
            segment.speaker
          );

          segment.speaker_id = speakerId;

          this.database.addTranscriptSegment(session.transcriptId, segment);
          session.segments.push(segment);

          // Emit transcript event to UI
          this.emit('transcript', {
            sessionId,
            meetingId: session.meetingId,
            segment
          });

          // Check if this segment contains a question or requires assistance
          await this.checkForAssistance(sessionId, segment);
        }
      }

    } catch (error) {
      console.error(`Error processing audio buffer for session ${sessionId}:`, error);
      this.emit('error', {
        sessionId,
        error: error.message
      });
    }
  }

  /**
   * Send audio to transcription service
   */
  async transcribe(sessionId, audioData) {
    try {
      const response = await axios.post(
        `${this.pythonServices.transcription}/transcribe/stream`,
        {
          audio_chunk: audioData.toString('base64'),
          session_id: sessionId,
          chunk_index: Date.now()
        },
        {
          timeout: 10000,
          headers: { 'Content-Type': 'application/json' }
        }
      );

      return response.data;

    } catch (error) {
      console.error('Transcription service error:', error.message);

      // Fallback: Return empty result to keep session running
      return { segments: [] };
    }
  }

  /**
   * Check if segment requires real-time assistance
   */
  async checkForAssistance(sessionId, segment) {
    const session = this.activeSessions.get(sessionId);
    if (!session) return;

    // Get recent context (last 5 segments)
    const recentSegments = session.segments.slice(-5);
    const context = recentSegments.map(s => `${s.speaker}: ${s.text}`).join('\n');

    try {
      // Detect intent
      const intentResponse = await axios.post(
        `${this.pythonServices.llm}/detect-intent`,
        {
          text: segment.text,
          context
        },
        { timeout: 3000 }
      );

      const { intent, entities } = intentResponse.data;

      // If question detected, get answer from RAG
      if (intent === 'question') {
        const answer = await this.getContextualAnswer(
          segment.text,
          session.meetingId
        );

        if (answer) {
          this.emit('assistance', {
            sessionId,
            type: 'answer',
            question: segment.text,
            answer: answer.text,
            sources: answer.sources,
            confidence: answer.confidence
          });
        }
      }

      // If code request detected
      if (intent === 'code_request' && entities.language) {
        const codeSnippet = await this.generateCode(
          segment.text,
          entities.language
        );

        if (codeSnippet) {
          this.emit('assistance', {
            sessionId,
            type: 'code',
            request: segment.text,
            code: codeSnippet.code,
            language: entities.language,
            explanation: codeSnippet.explanation
          });
        }
      }

      // If decision point detected
      if (intent === 'decision') {
        this.emit('assistance', {
          sessionId,
          type: 'decision_detected',
          text: segment.text,
          timestamp_ms: segment.start_ms
        });
      }

    } catch (error) {
      // Silently fail - don't disrupt transcription
      console.debug('Assistance check failed:', error.message);
    }
  }

  /**
   * Get contextual answer from RAG system
   */
  async getContextualAnswer(question, meetingId) {
    try {
      const response = await axios.post(
        `${this.pythonServices.rag}/query`,
        {
          question,
          filters: {
            exclude_meeting_id: meetingId  // Don't retrieve from current meeting
          },
          top_k: 3,
          use_web_search: true
        },
        { timeout: 5000 }
      );

      return response.data;

    } catch (error) {
      console.error('RAG query failed:', error.message);
      return null;
    }
  }

  /**
   * Generate code snippet
   */
  async generateCode(request, language) {
    try {
      const response = await axios.post(
        `${this.pythonServices.llm}/complete`,
        {
          prompt: `Generate ${language} code for: ${request}`,
          task_type: 'code_gen',
          max_tokens: 2000
        },
        { timeout: 10000 }
      );

      return response.data;

    } catch (error) {
      console.error('Code generation failed:', error.message);
      return null;
    }
  }

  /**
   * Get or create speaker/participant
   */
  async getOrCreateSpeaker(meetingId, speakerName) {
    const participantId = this.database.upsertParticipant(speakerName);
    this.database.addMeetingParticipant(meetingId, participantId);
    return participantId;
  }

  /**
   * Pause recording session
   */
  async pause(sessionId) {
    const session = this.activeSessions.get(sessionId);
    if (!session) {
      throw new Error(`Session ${sessionId} not found`);
    }

    session.status = 'paused';
    await this.audioCapture.pause(sessionId);
    console.log(`Session paused: ${sessionId}`);
  }

  /**
   * Resume recording session
   */
  async resume(sessionId) {
    const session = this.activeSessions.get(sessionId);
    if (!session) {
      throw new Error(`Session ${sessionId} not found`);
    }

    session.status = 'recording';
    await this.audioCapture.resume(sessionId);
    console.log(`Session resumed: ${sessionId}`);
  }

  /**
   * Stop recording session and process final artifacts
   */
  async stop(sessionId) {
    const session = this.activeSessions.get(sessionId);
    if (!session) {
      throw new Error(`Session ${sessionId} not found`);
    }

    console.log(`Stopping session: ${sessionId}`);

    // Process any remaining audio
    if (session.audioBuffer.length > 0) {
      await this.processAudioBuffer(sessionId);
    }

    // Stop audio capture
    await this.audioCapture.stop(sessionId);

    // Update meeting end time
    const duration = Math.floor((Date.now() - session.startTime) / 1000);
    this.database.updateMeeting(session.meetingId, {
      end_time: new Date().toISOString(),
      duration_seconds: duration,
      status: 'processing'
    });

    // Process meeting in background
    this.processCompletedMeeting(session.meetingId).catch(error => {
      console.error('Error processing completed meeting:', error);
      this.database.updateMeeting(session.meetingId, {
        status: 'error'
      });
    });

    // Clean up session
    this.activeSessions.delete(sessionId);
    console.log(`Session stopped: ${sessionId}`);
  }

  /**
   * Process completed meeting (summarization, analytics, etc.)
   */
  async processCompletedMeeting(meetingId) {
    console.log(`Processing completed meeting: ${meetingId}`);

    try {
      // Get full transcript
      const meeting = this.database.getMeeting(meetingId);
      const segments = this.database.db.prepare(`
        SELECT ts.*, p.name as speaker_name
        FROM transcript_segments ts
        LEFT JOIN participants p ON ts.speaker_id = p.participant_id
        WHERE ts.transcript_id IN (
          SELECT transcript_id FROM transcripts WHERE meeting_id = ?
        )
        ORDER BY ts.start_ms
      `).all(meetingId);

      const fullTranscript = segments
        .map(s => `[${s.speaker_name || 'Unknown'}]: ${s.text}`)
        .join('\n');

      // Generate summary
      const summary = await this.generateSummary(fullTranscript);
      if (summary) {
        this.database.saveSummary(meetingId, summary, 'gemini-2.5-pro');
      }

      // Extract action items
      const actionItems = await this.extractActionItems(fullTranscript, meeting.participants);
      for (const item of actionItems || []) {
        // Find assignee ID
        const assignee = meeting.participants.find(p =>
          p.name.toLowerCase().includes(item.assignee.toLowerCase())
        );
        item.assignee_id = assignee?.participant_id;

        this.database.saveActionItem(meetingId, item);
      }

      // Extract decisions
      const decisions = await this.extractDecisions(fullTranscript);
      for (const decision of decisions || []) {
        this.database.saveDecision(meetingId, decision);
      }

      // Generate analytics
      const analytics = await this.generateAnalytics(segments, meeting);
      if (analytics) {
        this.database.saveAnalytics(meetingId, analytics.meeting);

        for (const [participantId, stats] of Object.entries(analytics.speakers)) {
          this.database.saveSpeakerAnalytics(meetingId, participantId, stats);
        }
      }

      // Index meeting in RAG system
      await this.indexMeetingForRAG(meetingId, fullTranscript, summary);

      // Update status to completed
      this.database.updateMeeting(meetingId, {
        status: 'completed'
      });

      console.log(`Meeting processing completed: ${meetingId}`);

    } catch (error) {
      console.error(`Error processing meeting ${meetingId}:`, error);
      throw error;
    }
  }

  /**
   * Generate meeting summary
   */
  async generateSummary(transcript) {
    try {
      const response = await axios.post(
        `${this.pythonServices.llm}/summarize`,
        {
          transcript,
          max_tokens: 3000
        },
        { timeout: 30000 }
      );

      return response.data.summary;

    } catch (error) {
      console.error('Summary generation failed:', error.message);
      return null;
    }
  }

  /**
   * Extract action items
   */
  async extractActionItems(transcript, participants) {
    try {
      const participantNames = participants.map(p => p.name);

      const response = await axios.post(
        `${this.pythonServices.llm}/extract/action-items`,
        {
          transcript,
          participants: participantNames
        },
        { timeout: 20000 }
      );

      return response.data.action_items;

    } catch (error) {
      console.error('Action item extraction failed:', error.message);
      return [];
    }
  }

  /**
   * Extract decisions
   */
  async extractDecisions(transcript) {
    try {
      const response = await axios.post(
        `${this.pythonServices.llm}/extract/decisions`,
        {
          transcript
        },
        { timeout: 15000 }
      );

      return response.data.decisions;

    } catch (error) {
      console.error('Decision extraction failed:', error.message);
      return [];
    }
  }

  /**
   * Generate meeting analytics
   */
  async generateAnalytics(segments, meeting) {
    try {
      const response = await axios.post(
        `${this.pythonServices.llm}/analytics/calculate`,
        {
          segments,
          duration_seconds: meeting.duration_seconds
        },
        { timeout: 15000 }
      );

      return response.data;

    } catch (error) {
      console.error('Analytics generation failed:', error.message);
      return null;
    }
  }

  /**
   * Index meeting in RAG system
   */
  async indexMeetingForRAG(meetingId, transcript, summary) {
    try {
      await axios.post(
        `${this.pythonServices.rag}/index/meeting`,
        {
          meeting_id: meetingId,
          transcript,
          summary: summary?.executive_summary || '',
          metadata: {
            title: summary?.title || '',
            key_topics: summary?.key_topics || []
          }
        },
        { timeout: 30000 }
      );

      console.log(`Meeting indexed in RAG: ${meetingId}`);

    } catch (error) {
      console.error('RAG indexing failed:', error.message);
    }
  }

  /**
   * Handle errors
   */
  handleError(sessionId, error) {
    console.error(`Session error ${sessionId}:`, error);
    this.emit('error', {
      sessionId,
      error: error.message
    });
  }
}

module.exports = SessionManager;

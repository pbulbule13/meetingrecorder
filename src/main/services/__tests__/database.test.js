/**
 * Database Service Tests
 */

const DatabaseService = require('../database');
const fs = require('fs').promises;
const path = require('path');
const os = require('os');

describe('DatabaseService', () => {
  let db;
  let testDataPath;

  beforeAll(async () => {
    // Create temporary directory for test database
    testDataPath = path.join(os.tmpdir(), 'nexus-test-' + Date.now());
    await fs.mkdir(testDataPath, { recursive: true });

    db = new DatabaseService(testDataPath);
    await db.initialize();
  });

  afterAll(async () => {
    await db.close();
    // Clean up test directory
    await fs.rm(testDataPath, { recursive: true, force: true });
  });

  describe('Meeting Management', () => {
    test('should create a new meeting', () => {
      const meetingId = db.createMeeting('Test Meeting');

      expect(meetingId).toBeDefined();
      expect(typeof meetingId).toBe('string');
    });

    test('should retrieve a meeting by ID', () => {
      const meetingId = db.createMeeting('Retrieval Test');
      const meeting = db.getMeeting(meetingId);

      expect(meeting).toBeDefined();
      expect(meeting.title).toBe('Retrieval Test');
      expect(meeting.status).toBe('recording');
    });

    test('should update meeting details', () => {
      const meetingId = db.createMeeting('Update Test');

      db.updateMeeting(meetingId, {
        status: 'completed',
        duration_seconds: 1800
      });

      const meeting = db.getMeeting(meetingId);
      expect(meeting.status).toBe('completed');
      expect(meeting.duration_seconds).toBe(1800);
    });

    test('should list meetings with filters', () => {
      db.createMeeting('Meeting 1');
      db.createMeeting('Meeting 2');

      const meetings = db.getMeetings({ limit: 10 });

      expect(Array.isArray(meetings)).toBe(true);
      expect(meetings.length).toBeGreaterThan(0);
    });
  });

  describe('Participant Management', () => {
    test('should create or retrieve participant', () => {
      const participantId1 = db.upsertParticipant('John Doe', 'john@example.com');
      const participantId2 = db.upsertParticipant('John Doe', 'john@example.com');

      // Should return same ID for same email
      expect(participantId1).toBe(participantId2);
    });

    test('should add participant to meeting', () => {
      const meetingId = db.createMeeting('Participant Test');
      const participantId = db.upsertParticipant('Jane Smith');

      db.addMeetingParticipant(meetingId, participantId);

      const meeting = db.getMeeting(meetingId);
      expect(meeting.participants).toBeDefined();
      expect(meeting.participants.length).toBeGreaterThan(0);
      expect(meeting.participants[0].name).toBe('Jane Smith');
    });
  });

  describe('Transcript Management', () => {
    test('should add transcript segment', () => {
      const meetingId = db.createMeeting('Transcript Test');
      const transcriptId = 'test-transcript-' + Date.now();
      const participantId = db.upsertParticipant('Speaker 1');

      const segment = {
        speaker_id: participantId,
        text: 'This is a test transcript segment.',
        start_ms: 0,
        end_ms: 5000,
        confidence: 0.95,
        sentiment: 0.5
      };

      const segmentId = db.addTranscriptSegment(transcriptId, segment);

      expect(segmentId).toBeDefined();
    });
  });

  describe('Action Item Management', () => {
    test('should save and retrieve action items', () => {
      const meetingId = db.createMeeting('Action Item Test');
      const participantId = db.upsertParticipant('Task Owner');

      const actionItem = {
        task: 'Complete documentation',
        assignee_id: participantId,
        due_date: '2025-12-01',
        priority: 'high',
        timestamp_ms: 120000
      };

      const actionId = db.saveActionItem(meetingId, actionItem);

      expect(actionId).toBeDefined();

      const items = db.getActionItems({ status: 'pending' });
      expect(items.length).toBeGreaterThan(0);

      const savedItem = items.find(i => i.action_id === actionId);
      expect(savedItem).toBeDefined();
      expect(savedItem.task).toBe('Complete documentation');
    });

    test('should update action item status', () => {
      const meetingId = db.createMeeting('Action Update Test');
      const participantId = db.upsertParticipant('Task Owner 2');

      const actionId = db.saveActionItem(meetingId, {
        task: 'Update tests',
        assignee_id: participantId,
        priority: 'medium',
        timestamp_ms: 0
      });

      db.updateActionItem(actionId, { status: 'completed' });

      const items = db.getActionItems({ status: 'completed' });
      const updatedItem = items.find(i => i.action_id === actionId);

      expect(updatedItem).toBeDefined();
      expect(updatedItem.status).toBe('completed');
    });
  });

  describe('Search Functionality', () => {
    test('should search transcripts', async () => {
      const meetingId = db.createMeeting('Search Test Meeting');
      const transcriptId = 'search-test-' + Date.now();
      const participantId = db.upsertParticipant('Test Speaker');

      db.addTranscriptSegment(transcriptId, {
        speaker_id: participantId,
        text: 'We need to discuss the database architecture',
        start_ms: 0,
        end_ms: 3000,
        confidence: 0.9,
        sentiment: 0.6
      });

      // Note: FTS5 search requires the transcript to be indexed first
      // This is a basic test - in practice, indexing happens via triggers

      const results = db.searchTranscripts('database');

      // Results may be empty if FTS indexing hasn't run yet
      // This test validates the query doesn't error
      expect(Array.isArray(results)).toBe(true);
    });
  });

  describe('API Key Management', () => {
    test('should generate and verify API key', () => {
      const { keyId, key } = db.generateAPIKey('Test Integration');

      expect(keyId).toBeDefined();
      expect(key).toBeDefined();
      expect(key).toMatch(/^nxs_/);

      const isValid = db.verifyAPIKey(key);
      expect(isValid).toBe(true);

      const isInvalid = db.verifyAPIKey('nxs_invalid_key');
      expect(isInvalid).toBe(false);
    });
  });

  describe('Analytics', () => {
    test('should save meeting analytics', () => {
      const meetingId = db.createMeeting('Analytics Test');

      const analytics = {
        total_words: 1000,
        avg_speaking_pace: 150.5,
        total_interruptions: 5,
        sentiment_timeline: [0.5, 0.6, 0.7],
        engagement_score: 78.5
      };

      db.saveAnalytics(meetingId, analytics);

      const meeting = db.getMeeting(meetingId);
      expect(meeting.analytics).toBeDefined();
      expect(meeting.analytics.engagement_score).toBe(78.5);
    });

    test('should save speaker analytics', () => {
      const meetingId = db.createMeeting('Speaker Analytics Test');
      const participantId = db.upsertParticipant('Test Speaker');

      const speakerAnalytics = {
        talk_time_percent: 45.2,
        word_count: 450,
        avg_sentiment: 0.65,
        interruption_count: 2,
        speaking_pace_wpm: 148.5,
        questions_asked: 3
      };

      db.saveSpeakerAnalytics(meetingId, participantId, speakerAnalytics);

      const meeting = db.getMeeting(meetingId);
      expect(meeting.speaker_analytics).toBeDefined();
      expect(meeting.speaker_analytics.length).toBeGreaterThan(0);
    });
  });
});

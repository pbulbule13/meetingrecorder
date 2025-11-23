/**
 * Local API Server
 * REST API for external integrations
 */

const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const { RateLimiterMemory } = require('rate-limiter-flexible');
const fs = require('fs').promises;
const path = require('path');
const marked = require('marked');
const { Parser } = require('json2csv');
const ical = require('ical-generator');

class APIServer {
  constructor(database, port = 8080) {
    this.database = database;
    this.port = port;
    this.app = express();
    this.server = null;

    // Rate limiter: 100 requests per minute
    this.rateLimiter = new RateLimiterMemory({
      points: 100,
      duration: 60
    });

    this.setupMiddleware();
    this.setupRoutes();
  }

  /**
   * Setup Express middleware
   */
  setupMiddleware() {
    // Security
    this.app.use(helmet());

    // CORS (localhost only by default)
    this.app.use(cors({
      origin: ['http://localhost:3000', 'http://127.0.0.1:3000']
    }));

    // Body parsing
    this.app.use(express.json({ limit: '10mb' }));
    this.app.use(express.urlencoded({ extended: true }));

    // API key authentication
    this.app.use('/api', this.authenticateAPIKey.bind(this));

    // Rate limiting
    this.app.use(this.rateLimitMiddleware.bind(this));

    // Request logging
    this.app.use((req, res, next) => {
      console.log(`[API] ${req.method} ${req.path}`);
      next();
    });
  }

  /**
   * Authenticate API key
   */
  async authenticateAPIKey(req, res, next) {
    const authHeader = req.headers.authorization;

    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return res.status(401).json({
        error: 'Missing or invalid authorization header'
      });
    }

    const apiKey = authHeader.substring(7); // Remove 'Bearer '

    if (!this.database.verifyAPIKey(apiKey)) {
      return res.status(401).json({
        error: 'Invalid API key'
      });
    }

    next();
  }

  /**
   * Rate limiting middleware
   */
  async rateLimitMiddleware(req, res, next) {
    try {
      await this.rateLimiter.consume(req.ip);
      next();
    } catch (error) {
      res.status(429).json({
        error: 'Too many requests. Please try again later.'
      });
    }
  }

  /**
   * Setup API routes
   */
  setupRoutes() {
    const router = express.Router();

    // Health check
    router.get('/health', (req, res) => {
      res.json({ status: 'ok', version: '1.0.0' });
    });

    // Meetings
    router.get('/meetings', this.getMeetings.bind(this));
    router.get('/meetings/:id', this.getMeeting.bind(this));
    router.delete('/meetings/:id', this.deleteMeeting.bind(this));

    // Search
    router.get('/search', this.searchTranscripts.bind(this));

    // Transcripts
    router.get('/meetings/:id/transcript', this.getTranscript.bind(this));
    router.get('/meetings/:id/transcript/segments', this.getTranscriptSegments.bind(this));

    // Summaries
    router.get('/meetings/:id/summary', this.getSummary.bind(this));
    router.post('/meetings/:id/summary/regenerate', this.regenerateSummary.bind(this));

    // Action Items
    router.get('/action-items', this.getActionItems.bind(this));
    router.get('/action-items/:id', this.getActionItem.bind(this));
    router.put('/action-items/:id', this.updateActionItem.bind(this));
    router.post('/action-items/:id/complete', this.completeActionItem.bind(this));

    // Analytics
    router.get('/meetings/:id/analytics', this.getAnalytics.bind(this));
    router.get('/analytics/dashboard', this.getAnalyticsDashboard.bind(this));

    // Export
    router.post('/meetings/:id/export', this.exportMeeting.bind(this));
    router.get('/export/action-items', this.exportActionItems.bind(this));

    // API Keys (management)
    router.post('/auth/keys', this.createAPIKey.bind(this));
    router.get('/auth/keys', this.listAPIKeys.bind(this));
    router.delete('/auth/keys/:id', this.deleteAPIKey.bind(this));

    this.app.use('/api/v1', router);

    // Error handler
    this.app.use((err, req, res, next) => {
      console.error('API Error:', err);
      res.status(500).json({
        error: 'Internal server error',
        message: err.message
      });
    });
  }

  /**
   * API Route Handlers
   */

  async getMeetings(req, res) {
    try {
      const filters = {
        status: req.query.status,
        startDate: req.query.start_date,
        endDate: req.query.end_date,
        limit: parseInt(req.query.limit) || 50,
        offset: parseInt(req.query.offset) || 0
      };

      const meetings = this.database.getMeetings(filters);
      res.json({ success: true, data: meetings });

    } catch (error) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async getMeeting(req, res) {
    try {
      const meeting = this.database.getMeeting(req.params.id);
      res.json({ success: true, data: meeting });

    } catch (error) {
      res.status(404).json({ success: false, error: error.message });
    }
  }

  async deleteMeeting(req, res) {
    try {
      this.database.db.prepare(`
        DELETE FROM meetings WHERE meeting_id = ?
      `).run(req.params.id);

      res.json({ success: true });

    } catch (error) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async searchTranscripts(req, res) {
    try {
      const query = req.query.q;
      if (!query) {
        return res.status(400).json({
          success: false,
          error: 'Query parameter "q" is required'
        });
      }

      const options = {
        limit: parseInt(req.query.limit) || 50,
        offset: parseInt(req.query.offset) || 0
      };

      const results = this.database.searchTranscripts(query, options);
      res.json({ success: true, data: results });

    } catch (error) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async getTranscript(req, res) {
    try {
      const transcript = this.database.db.prepare(`
        SELECT * FROM transcripts WHERE meeting_id = ?
      `).get(req.params.id);

      if (!transcript) {
        return res.status(404).json({
          success: false,
          error: 'Transcript not found'
        });
      }

      res.json({ success: true, data: transcript });

    } catch (error) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async getTranscriptSegments(req, res) {
    try {
      const segments = this.database.db.prepare(`
        SELECT ts.*, p.name as speaker_name
        FROM transcript_segments ts
        LEFT JOIN participants p ON ts.speaker_id = p.participant_id
        WHERE ts.transcript_id IN (
          SELECT transcript_id FROM transcripts WHERE meeting_id = ?
        )
        ORDER BY ts.start_ms
      `).all(req.params.id);

      res.json({ success: true, data: segments });

    } catch (error) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async getSummary(req, res) {
    try {
      const summary = this.database.db.prepare(`
        SELECT * FROM summaries
        WHERE meeting_id = ?
        ORDER BY created_at DESC
        LIMIT 1
      `).get(req.params.id);

      if (!summary) {
        return res.status(404).json({
          success: false,
          error: 'Summary not found'
        });
      }

      // Parse JSON fields
      summary.key_topics = JSON.parse(summary.key_topics);

      res.json({ success: true, data: summary });

    } catch (error) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async regenerateSummary(req, res) {
    try {
      // This would trigger the session manager to regenerate the summary
      res.status(501).json({
        success: false,
        error: 'Not implemented yet'
      });

    } catch (error) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async getActionItems(req, res) {
    try {
      const filters = {
        status: req.query.status,
        assigneeId: req.query.assignee_id,
        overdue: req.query.overdue === 'true'
      };

      const items = this.database.getActionItems(filters);
      res.json({ success: true, data: items });

    } catch (error) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async getActionItem(req, res) {
    try {
      const item = this.database.db.prepare(`
        SELECT ai.*, p.name as assignee_name
        FROM action_items ai
        LEFT JOIN participants p ON ai.assignee_id = p.participant_id
        WHERE ai.action_id = ?
      `).get(req.params.id);

      if (!item) {
        return res.status(404).json({
          success: false,
          error: 'Action item not found'
        });
      }

      res.json({ success: true, data: item });

    } catch (error) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async updateActionItem(req, res) {
    try {
      this.database.updateActionItem(req.params.id, req.body);
      res.json({ success: true });

    } catch (error) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async completeActionItem(req, res) {
    try {
      this.database.updateActionItem(req.params.id, {
        status: 'completed',
        completed_at: new Date().toISOString()
      });

      res.json({ success: true });

    } catch (error) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async getAnalytics(req, res) {
    try {
      const analytics = this.database.db.prepare(`
        SELECT * FROM meeting_analytics WHERE meeting_id = ?
      `).get(req.params.id);

      if (!analytics) {
        return res.status(404).json({
          success: false,
          error: 'Analytics not found'
        });
      }

      // Parse JSON fields
      analytics.sentiment_timeline = JSON.parse(analytics.sentiment_timeline);

      res.json({ success: true, data: analytics });

    } catch (error) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async getAnalyticsDashboard(req, res) {
    try {
      const days = parseInt(req.query.days) || 30;
      const startDate = new Date();
      startDate.setDate(startDate.getDate() - days);

      const stats = {
        total_meetings: this.database.db.prepare(`
          SELECT COUNT(*) as count
          FROM meetings
          WHERE start_time >= ?
        `).get(startDate.toISOString()).count,

        total_duration: this.database.db.prepare(`
          SELECT SUM(duration_seconds) as total
          FROM meetings
          WHERE start_time >= ?
        `).get(startDate.toISOString()).total || 0,

        pending_action_items: this.database.db.prepare(`
          SELECT COUNT(*) as count
          FROM action_items
          WHERE status = 'pending'
        `).get().count,

        overdue_action_items: this.database.db.prepare(`
          SELECT COUNT(*) as count
          FROM action_items
          WHERE status != 'completed' AND due_date < DATE('now')
        `).get().count,

        avg_engagement_score: this.database.db.prepare(`
          SELECT AVG(engagement_score) as avg
          FROM meeting_analytics ma
          JOIN meetings m ON ma.meeting_id = m.meeting_id
          WHERE m.start_time >= ?
        `).get(startDate.toISOString()).avg || 0
      };

      res.json({ success: true, data: stats });

    } catch (error) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async exportMeeting(req, res) {
    try {
      const format = req.body.format || 'md';
      const meeting = this.database.getMeeting(req.params.id);

      let content = '';

      if (format === 'md' || format === 'markdown') {
        content = this.generateMarkdownExport(meeting);
        res.setHeader('Content-Type', 'text/markdown');
        res.setHeader('Content-Disposition', `attachment; filename="meeting-${meeting.meeting_id}.md"`);
      } else if (format === 'json') {
        content = JSON.stringify(meeting, null, 2);
        res.setHeader('Content-Type', 'application/json');
        res.setHeader('Content-Disposition', `attachment; filename="meeting-${meeting.meeting_id}.json"`);
      } else {
        return res.status(400).json({
          success: false,
          error: 'Unsupported format. Use "md" or "json".'
        });
      }

      res.send(content);

    } catch (error) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async exportActionItems(req, res) {
    try {
      const items = this.database.getActionItems({});

      const parser = new Parser({
        fields: [
          'task',
          'assignee_name',
          'due_date',
          'priority',
          'status',
          'meeting_title',
          'meeting_date'
        ]
      });

      const csv = parser.parse(items);

      res.setHeader('Content-Type', 'text/csv');
      res.setHeader('Content-Disposition', 'attachment; filename="action-items.csv"');
      res.send(csv);

    } catch (error) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  /**
   * Generate Markdown export
   */
  generateMarkdownExport(meeting) {
    const startDate = new Date(meeting.start_time).toLocaleString();
    const duration = Math.floor(meeting.duration_seconds / 60);

    let md = `# ${meeting.title}\n\n`;
    md += `**Date:** ${startDate}  \n`;
    md += `**Duration:** ${duration} minutes\n\n`;

    // Participants
    if (meeting.participants && meeting.participants.length > 0) {
      md += `## Participants\n\n`;
      for (const p of meeting.participants) {
        const talkTime = meeting.speaker_analytics?.find(
          sa => sa.participant_id === p.participant_id
        )?.talk_time_percent || 0;
        md += `- ${p.name}${p.email ? ` (${p.email})` : ''} - ${talkTime.toFixed(1)}% talk time\n`;
      }
      md += `\n`;
    }

    // Summary
    if (meeting.summary) {
      md += `## Summary\n\n${meeting.summary.executive_summary}\n\n`;

      if (meeting.summary.key_topics) {
        const topics = JSON.parse(meeting.summary.key_topics);
        md += `### Key Topics\n\n`;
        for (const topic of topics) {
          md += `- ${topic}\n`;
        }
        md += `\n`;
      }
    }

    // Decisions
    if (meeting.decisions && meeting.decisions.length > 0) {
      md += `## Key Decisions\n\n`;
      for (let i = 0; i < meeting.decisions.length; i++) {
        const d = meeting.decisions[i];
        md += `${i + 1}. **${d.decision}**\n`;
        if (d.rationale) {
          md += `   - Rationale: ${d.rationale}\n`;
        }
      }
      md += `\n`;
    }

    // Action Items
    if (meeting.action_items && meeting.action_items.length > 0) {
      md += `## Action Items\n\n`;
      for (const item of meeting.action_items) {
        const assignee = meeting.participants.find(
          p => p.participant_id === item.assignee_id
        );
        const checkbox = item.status === 'completed' ? 'x' : ' ';
        md += `- [${checkbox}] ${item.task}`;
        if (assignee) {
          md += ` - @${assignee.name}`;
        }
        if (item.due_date) {
          md += ` - Due: ${item.due_date}`;
        }
        md += `\n`;
      }
      md += `\n`;
    }

    // Analytics
    if (meeting.analytics) {
      md += `## Meeting Analytics\n\n`;
      md += `- **Total Words:** ${meeting.analytics.total_words}\n`;
      md += `- **Average Speaking Pace:** ${meeting.analytics.avg_speaking_pace.toFixed(1)} WPM\n`;
      md += `- **Engagement Score:** ${meeting.analytics.engagement_score.toFixed(1)}/100\n`;
      md += `\n`;
    }

    md += `---\n\n`;
    md += `*Generated by Nexus Assistant*\n`;

    return md;
  }

  /**
   * API Key management
   */

  async createAPIKey(req, res) {
    try {
      const name = req.body.name || 'Unnamed Key';
      const result = this.database.generateAPIKey(name);

      res.json({
        success: true,
        data: {
          key_id: result.keyId,
          api_key: result.key,  // Only shown once!
          name,
          created_at: new Date().toISOString()
        }
      });

    } catch (error) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async listAPIKeys(req, res) {
    try {
      const keys = this.database.db.prepare(`
        SELECT key_id, name, created_at, last_used_at, is_active
        FROM api_keys
        ORDER BY created_at DESC
      `).all();

      res.json({ success: true, data: keys });

    } catch (error) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  async deleteAPIKey(req, res) {
    try {
      this.database.db.prepare(`
        UPDATE api_keys SET is_active = 0 WHERE key_id = ?
      `).run(req.params.id);

      res.json({ success: true });

    } catch (error) {
      res.status(500).json({ success: false, error: error.message });
    }
  }

  /**
   * Start the API server
   */
  async start() {
    return new Promise((resolve, reject) => {
      this.server = this.app.listen(this.port, () => {
        console.log(`API server running on http://localhost:${this.port}`);
        resolve();
      });

      this.server.on('error', (error) => {
        console.error('API server error:', error);
        reject(error);
      });
    });
  }

  /**
   * Stop the API server
   */
  async stop() {
    if (this.server) {
      return new Promise((resolve) => {
        this.server.close(() => {
          console.log('API server stopped');
          resolve();
        });
      });
    }
  }
}

module.exports = APIServer;

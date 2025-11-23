/**
 * Audio Capture Service
 * Cross-platform audio capture using native addons
 */

const EventEmitter = require('events');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

class AudioCaptureService extends EventEmitter {
  constructor() {
    super();
    this.activeCaptures = new Map();
    this.platform = process.platform;
  }

  /**
   * Start audio capture for a session
   */
  async start(options) {
    const { sessionId, onAudioChunk, onError } = options;

    if (this.activeCaptures.has(sessionId)) {
      throw new Error(`Audio capture already active for session ${sessionId}`);
    }

    const captureConfig = {
      sampleRate: 16000,
      channels: 1,
      bitDepth: 16,
      bufferSize: 4096,
      captureSystem: true,   // Capture system audio (speakers)
      captureMicrophone: true // Capture microphone
    };

    try {
      const captureProcess = await this.startPlatformCapture(
        sessionId,
        captureConfig,
        onAudioChunk,
        onError
      );

      this.activeCaptures.set(sessionId, {
        process: captureProcess,
        config: captureConfig,
        status: 'recording',
        startTime: Date.now()
      });

      console.log(`Audio capture started for session ${sessionId}`);

    } catch (error) {
      throw new Error(`Failed to start audio capture: ${error.message}`);
    }
  }

  /**
   * Start platform-specific audio capture
   */
  async startPlatformCapture(sessionId, config, onAudioChunk, onError) {
    if (this.platform === 'win32') {
      return this.startWindowsCapture(sessionId, config, onAudioChunk, onError);
    } else if (this.platform === 'darwin') {
      return this.startMacCapture(sessionId, config, onAudioChunk, onError);
    } else if (this.platform === 'linux') {
      return this.startLinuxCapture(sessionId, config, onAudioChunk, onError);
    } else {
      throw new Error(`Unsupported platform: ${this.platform}`);
    }
  }

  /**
   * Windows audio capture using FFmpeg + WASAPI
   */
  startWindowsCapture(sessionId, config, onAudioChunk, onError) {
    // Use FFmpeg to capture both system audio and microphone
    // WASAPI provides loopback recording for system audio

    const ffmpegArgs = [
      '-f', 'dshow',
      '-i', 'audio=Microphone',  // Adjust device name as needed
      '-f', 'dshow',
      '-i', 'audio=Stereo Mix',  // System audio (requires enabled in Windows)
      '-filter_complex', 'amix=inputs=2:duration=longest',
      '-ac', config.channels.toString(),
      '-ar', config.sampleRate.toString(),
      '-f', 's16le',
      '-'
    ];

    const ffmpeg = spawn('ffmpeg', ffmpegArgs, {
      stdio: ['ignore', 'pipe', 'pipe']
    });

    let chunkBuffer = Buffer.alloc(0);
    const chunkSize = config.sampleRate * 2 * 5; // 5 seconds of 16-bit audio

    ffmpeg.stdout.on('data', (data) => {
      chunkBuffer = Buffer.concat([chunkBuffer, data]);

      // Emit chunks when we have enough data
      while (chunkBuffer.length >= chunkSize) {
        const chunk = chunkBuffer.slice(0, chunkSize);
        chunkBuffer = chunkBuffer.slice(chunkSize);

        onAudioChunk({
          sessionId,
          data: chunk,
          timestamp: Date.now(),
          sampleRate: config.sampleRate,
          channels: config.channels
        });
      }
    });

    ffmpeg.stderr.on('data', (data) => {
      console.error(`FFmpeg error: ${data.toString()}`);
    });

    ffmpeg.on('error', (error) => {
      onError(error);
    });

    ffmpeg.on('exit', (code) => {
      if (code !== 0 && code !== null) {
        onError(new Error(`FFmpeg exited with code ${code}`));
      }
    });

    return ffmpeg;
  }

  /**
   * macOS audio capture using FFmpeg + CoreAudio
   */
  startMacCapture(sessionId, config, onAudioChunk, onError) {
    // Use FFmpeg with AVFoundation to capture audio
    const ffmpegArgs = [
      '-f', 'avfoundation',
      '-i', ':0',  // Audio device 0 (default microphone)
      '-ac', config.channels.toString(),
      '-ar', config.sampleRate.toString(),
      '-f', 's16le',
      '-'
    ];

    const ffmpeg = spawn('ffmpeg', ffmpegArgs, {
      stdio: ['ignore', 'pipe', 'pipe']
    });

    let chunkBuffer = Buffer.alloc(0);
    const chunkSize = config.sampleRate * 2 * 5; // 5 seconds

    ffmpeg.stdout.on('data', (data) => {
      chunkBuffer = Buffer.concat([chunkBuffer, data]);

      while (chunkBuffer.length >= chunkSize) {
        const chunk = chunkBuffer.slice(0, chunkSize);
        chunkBuffer = chunkBuffer.slice(chunkSize);

        onAudioChunk({
          sessionId,
          data: chunk,
          timestamp: Date.now(),
          sampleRate: config.sampleRate,
          channels: config.channels
        });
      }
    });

    ffmpeg.stderr.on('data', (data) => {
      console.error(`FFmpeg error: ${data.toString()}`);
    });

    ffmpeg.on('error', (error) => {
      onError(error);
    });

    ffmpeg.on('exit', (code) => {
      if (code !== 0 && code !== null) {
        onError(new Error(`FFmpeg exited with code ${code}`));
      }
    });

    return ffmpeg;
  }

  /**
   * Linux audio capture using FFmpeg + PulseAudio/ALSA
   */
  startLinuxCapture(sessionId, config, onAudioChunk, onError) {
    // Try PulseAudio first, fall back to ALSA
    const ffmpegArgs = [
      '-f', 'pulse',
      '-i', 'default',
      '-ac', config.channels.toString(),
      '-ar', config.sampleRate.toString(),
      '-f', 's16le',
      '-'
    ];

    const ffmpeg = spawn('ffmpeg', ffmpegArgs, {
      stdio: ['ignore', 'pipe', 'pipe']
    });

    let chunkBuffer = Buffer.alloc(0);
    const chunkSize = config.sampleRate * 2 * 5; // 5 seconds

    ffmpeg.stdout.on('data', (data) => {
      chunkBuffer = Buffer.concat([chunkBuffer, data]);

      while (chunkBuffer.length >= chunkSize) {
        const chunk = chunkBuffer.slice(0, chunkSize);
        chunkBuffer = chunkBuffer.slice(chunkSize);

        onAudioChunk({
          sessionId,
          data: chunk,
          timestamp: Date.now(),
          sampleRate: config.sampleRate,
          channels: config.channels
        });
      }
    });

    ffmpeg.stderr.on('data', (data) => {
      console.error(`FFmpeg error: ${data.toString()}`);
    });

    ffmpeg.on('error', (error) => {
      // If PulseAudio fails, try ALSA
      console.log('PulseAudio failed, trying ALSA...');
      onError(error);
    });

    ffmpeg.on('exit', (code) => {
      if (code !== 0 && code !== null) {
        onError(new Error(`FFmpeg exited with code ${code}`));
      }
    });

    return ffmpeg;
  }

  /**
   * Pause audio capture
   */
  async pause(sessionId) {
    const capture = this.activeCaptures.get(sessionId);
    if (!capture) {
      throw new Error(`No active capture for session ${sessionId}`);
    }

    capture.status = 'paused';
    // Note: FFmpeg doesn't support pause, so we just mark status
    // Audio will continue to be captured but session manager will ignore it
    console.log(`Audio capture paused for session ${sessionId}`);
  }

  /**
   * Resume audio capture
   */
  async resume(sessionId) {
    const capture = this.activeCaptures.get(sessionId);
    if (!capture) {
      throw new Error(`No active capture for session ${sessionId}`);
    }

    capture.status = 'recording';
    console.log(`Audio capture resumed for session ${sessionId}`);
  }

  /**
   * Stop audio capture
   */
  async stop(sessionId) {
    const capture = this.activeCaptures.get(sessionId);
    if (!capture) {
      throw new Error(`No active capture for session ${sessionId}`);
    }

    // Terminate FFmpeg process
    capture.process.kill('SIGTERM');

    // Clean up
    this.activeCaptures.delete(sessionId);
    console.log(`Audio capture stopped for session ${sessionId}`);
  }

  /**
   * Stop all active captures
   */
  async stopAll() {
    for (const [sessionId, capture] of this.activeCaptures.entries()) {
      capture.process.kill('SIGTERM');
    }

    this.activeCaptures.clear();
    console.log('All audio captures stopped');
  }

  /**
   * Get active capture info
   */
  getActiveCaptures() {
    const captures = [];
    for (const [sessionId, capture] of this.activeCaptures.entries()) {
      captures.push({
        sessionId,
        status: capture.status,
        duration: Date.now() - capture.startTime,
        config: capture.config
      });
    }
    return captures;
  }
}

module.exports = AudioCaptureService;

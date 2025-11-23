/**
 * Electron Preload Script
 * Exposes safe IPC methods to renderer process
 */

const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods to renderer
contextBridge.exposeInMainWorld('nexusAPI', {
  // Session control
  startSession: (options) => ipcRenderer.invoke('session:start', options),
  stopSession: (sessionId) => ipcRenderer.invoke('session:stop', sessionId),
  pauseSession: (sessionId) => ipcRenderer.invoke('session:pause', sessionId),
  resumeSession: (sessionId) => ipcRenderer.invoke('session:resume', sessionId),

  // Database queries
  getMeetings: (filters) => ipcRenderer.invoke('db:getMeetings', filters),
  getMeeting: (meetingId) => ipcRenderer.invoke('db:getMeeting', meetingId),
  searchTranscripts: (query) => ipcRenderer.invoke('db:searchTranscripts', query),
  getActionItems: (filters) => ipcRenderer.invoke('db:getActionItems', filters),
  updateActionItem: (itemId, updates) => ipcRenderer.invoke('db:updateActionItem', itemId, updates),

  // Settings
  getSetting: (key) => ipcRenderer.invoke('settings:get', key),
  setSetting: (key, value) => ipcRenderer.invoke('settings:set', key, value),
  getAllSettings: () => ipcRenderer.invoke('settings:getAll'),

  // Overlay control
  showOverlay: () => ipcRenderer.invoke('overlay:show'),
  hideOverlay: () => ipcRenderer.invoke('overlay:hide'),
  toggleOverlay: () => ipcRenderer.invoke('overlay:toggle'),

  // File operations
  exportMeeting: (meetingId, format) => ipcRenderer.invoke('file:export', meetingId, format),

  // System info
  getSystemInfo: () => ipcRenderer.invoke('system:getInfo'),

  // Event listeners
  onTranscript: (callback) => {
    ipcRenderer.on('session:transcript', (event, data) => callback(data));
  },

  onAssistance: (callback) => {
    ipcRenderer.on('session:assistance', (event, data) => callback(data));
  },

  onError: (callback) => {
    ipcRenderer.on('session:error', (event, error) => callback(error));
  },

  onCommand: (callback) => {
    ipcRenderer.on('command', (event, command) => callback(command));
  },

  // Remove event listeners
  removeListener: (channel, callback) => {
    ipcRenderer.removeListener(channel, callback);
  }
});

console.log('Nexus API exposed to renderer process');

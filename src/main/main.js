/**
 * Nexus Assistant - Main Process
 * Electron main process entry point
 */

const { app, BrowserWindow, ipcMain, Tray, Menu, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs').promises;
const Store = require('electron-store');
const winston = require('winston');

// Services
const AudioCaptureService = require('./services/audio-capture');
const SessionManager = require('./services/session-manager');
const APIServer = require('./services/api-server');
const DatabaseService = require('./services/database');

// Configure logger
const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  ),
  transports: [
    new winston.transports.File({
      filename: path.join(app.getPath('userData'), 'logs', 'app.log'),
      maxsize: 10485760, // 10MB
      maxFiles: 7
    }),
    new winston.transports.Console({
      format: winston.format.simple()
    })
  ]
});

// Configuration store
const store = new Store({
  defaults: {
    windowBounds: { width: 1200, height: 800 },
    overlayBounds: { width: 400, height: 600, x: 100, y: 100 },
    autoStart: false,
    minimizeToTray: true,
    pythonServices: {
      transcription: { port: 8765 },
      llm: { port: 8766 },
      rag: { port: 8767 }
    },
    apiServer: { port: 8080 },
    sttProvider: 'deepgram',
    llmProvider: 'gemini',
    recordingQuality: 'high'
  }
});

// Global references
let mainWindow = null;
let overlayWindow = null;
let tray = null;
let pythonProcesses = {};
let services = {
  audio: null,
  session: null,
  api: null,
  database: null
};

/**
 * Create main application window
 */
function createMainWindow() {
  const bounds = store.get('windowBounds');

  mainWindow = new BrowserWindow({
    width: bounds.width,
    height: bounds.height,
    minWidth: 900,
    minHeight: 600,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    },
    icon: path.join(__dirname, '../../build/icon.png'),
    title: 'Nexus Assistant',
    backgroundColor: '#1a1a2e',
    show: false
  });

  // Load the app
  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:9000');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'));
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  mainWindow.on('close', (event) => {
    if (store.get('minimizeToTray')) {
      event.preventDefault();
      mainWindow.hide();
    } else {
      app.quit();
    }
  });

  mainWindow.on('resize', () => {
    const bounds = mainWindow.getBounds();
    store.set('windowBounds', bounds);
  });

  logger.info('Main window created');
}

/**
 * Create floating overlay window for real-time assistance
 */
function createOverlayWindow() {
  const bounds = store.get('overlayBounds');

  overlayWindow = new BrowserWindow({
    width: bounds.width,
    height: bounds.height,
    x: bounds.x,
    y: bounds.y,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    },
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: true,
    movable: true,
    show: false
  });

  if (process.env.NODE_ENV === 'development') {
    overlayWindow.loadURL('http://localhost:9000/overlay.html');
  } else {
    overlayWindow.loadFile(path.join(__dirname, '../renderer/overlay.html'));
  }

  overlayWindow.on('move', () => {
    const bounds = overlayWindow.getBounds();
    store.set('overlayBounds', bounds);
  });

  logger.info('Overlay window created');
}

/**
 * Create system tray icon
 */
function createTray() {
  tray = new Tray(path.join(__dirname, '../../build/tray-icon.png'));

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Show Nexus Assistant',
      click: () => {
        mainWindow.show();
      }
    },
    {
      label: 'Start Recording',
      click: () => {
        mainWindow.webContents.send('command', 'start-recording');
      }
    },
    {
      label: 'Show Overlay',
      click: () => {
        if (overlayWindow) {
          overlayWindow.show();
        }
      },
      enabled: false,
      id: 'show-overlay'
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => {
        app.isQuitting = true;
        app.quit();
      }
    }
  ]);

  tray.setToolTip('Nexus Assistant');
  tray.setContextMenu(contextMenu);

  tray.on('click', () => {
    mainWindow.show();
  });

  logger.info('System tray created');
}

/**
 * Start Python microservices
 */
async function startPythonServices() {
  const pythonPath = process.platform === 'win32'
    ? path.join(__dirname, '../../python/python.exe')
    : 'python3';

  const services = ['transcription', 'llm', 'rag'];
  const config = store.get('pythonServices');

  for (const serviceName of services) {
    try {
      const servicePort = config[serviceName].port;
      const scriptPath = path.join(__dirname, `../python/${serviceName}_service.py`);

      logger.info(`Starting ${serviceName} service on port ${servicePort}`);

      const process = spawn(pythonPath, [
        '-m', 'uvicorn',
        `${serviceName}_service:app`,
        '--host', '127.0.0.1',
        '--port', servicePort.toString(),
        '--log-level', 'info'
      ], {
        cwd: path.join(__dirname, '../python'),
        env: { ...process.env, PYTHONUNBUFFERED: '1' }
      });

      process.stdout.on('data', (data) => {
        logger.debug(`[${serviceName}] ${data.toString().trim()}`);
      });

      process.stderr.on('data', (data) => {
        logger.error(`[${serviceName}] ${data.toString().trim()}`);
      });

      process.on('error', (error) => {
        logger.error(`Failed to start ${serviceName} service:`, error);
      });

      process.on('exit', (code) => {
        logger.warn(`${serviceName} service exited with code ${code}`);
      });

      pythonProcesses[serviceName] = process;

      // Wait a bit before starting next service
      await new Promise(resolve => setTimeout(resolve, 2000));

    } catch (error) {
      logger.error(`Error starting ${serviceName} service:`, error);
      dialog.showErrorBox(
        'Service Start Error',
        `Failed to start ${serviceName} service. Please check logs.`
      );
    }
  }

  logger.info('All Python services started');
}

/**
 * Initialize all services
 */
async function initializeServices() {
  try {
    // Initialize database
    services.database = new DatabaseService(app.getPath('userData'));
    await services.database.initialize();
    logger.info('Database service initialized');

    // Initialize audio capture
    services.audio = new AudioCaptureService();
    logger.info('Audio capture service initialized');

    // Initialize session manager
    services.session = new SessionManager(services.database, services.audio);
    logger.info('Session manager initialized');

    // Start API server
    const apiPort = store.get('apiServer.port');
    services.api = new APIServer(services.database, apiPort);
    await services.api.start();
    logger.info(`API server started on port ${apiPort}`);

  } catch (error) {
    logger.error('Failed to initialize services:', error);
    dialog.showErrorBox(
      'Initialization Error',
      'Failed to initialize services. Please restart the application.'
    );
    app.quit();
  }
}

/**
 * Setup IPC handlers
 */
function setupIPCHandlers() {
  // Session control
  ipcMain.handle('session:start', async (event, options) => {
    try {
      const sessionId = await services.session.start(options);
      logger.info(`Session started: ${sessionId}`);

      // Enable overlay menu item
      const menu = tray.getContextMenu();
      menu.getMenuItemById('show-overlay').enabled = true;
      tray.setContextMenu(menu);

      return { success: true, sessionId };
    } catch (error) {
      logger.error('Failed to start session:', error);
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle('session:stop', async (event, sessionId) => {
    try {
      await services.session.stop(sessionId);
      logger.info(`Session stopped: ${sessionId}`);

      // Disable overlay menu item
      const menu = tray.getContextMenu();
      menu.getMenuItemById('show-overlay').enabled = false;
      tray.setContextMenu(menu);

      return { success: true };
    } catch (error) {
      logger.error('Failed to stop session:', error);
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle('session:pause', async (event, sessionId) => {
    try {
      await services.session.pause(sessionId);
      return { success: true };
    } catch (error) {
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle('session:resume', async (event, sessionId) => {
    try {
      await services.session.resume(sessionId);
      return { success: true };
    } catch (error) {
      return { success: false, error: error.message };
    }
  });

  // Database queries
  ipcMain.handle('db:getMeetings', async (event, filters) => {
    try {
      const meetings = await services.database.getMeetings(filters);
      return { success: true, data: meetings };
    } catch (error) {
      logger.error('Failed to get meetings:', error);
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle('db:getMeeting', async (event, meetingId) => {
    try {
      const meeting = await services.database.getMeeting(meetingId);
      return { success: true, data: meeting };
    } catch (error) {
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle('db:searchTranscripts', async (event, query) => {
    try {
      const results = await services.database.searchTranscripts(query);
      return { success: true, data: results };
    } catch (error) {
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle('db:getActionItems', async (event, filters) => {
    try {
      const items = await services.database.getActionItems(filters);
      return { success: true, data: items };
    } catch (error) {
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle('db:updateActionItem', async (event, itemId, updates) => {
    try {
      await services.database.updateActionItem(itemId, updates);
      return { success: true };
    } catch (error) {
      return { success: false, error: error.message };
    }
  });

  // Settings
  ipcMain.handle('settings:get', async (event, key) => {
    return store.get(key);
  });

  ipcMain.handle('settings:set', async (event, key, value) => {
    store.set(key, value);
    return { success: true };
  });

  ipcMain.handle('settings:getAll', async () => {
    return store.store;
  });

  // Overlay control
  ipcMain.handle('overlay:show', () => {
    if (overlayWindow) {
      overlayWindow.show();
    }
  });

  ipcMain.handle('overlay:hide', () => {
    if (overlayWindow) {
      overlayWindow.hide();
    }
  });

  ipcMain.handle('overlay:toggle', () => {
    if (overlayWindow) {
      if (overlayWindow.isVisible()) {
        overlayWindow.hide();
      } else {
        overlayWindow.show();
      }
    }
  });

  // File operations
  ipcMain.handle('file:export', async (event, meetingId, format) => {
    try {
      const result = await dialog.showSaveDialog(mainWindow, {
        title: 'Export Meeting',
        defaultPath: `meeting-${meetingId}.${format}`,
        filters: [
          { name: format.toUpperCase(), extensions: [format] }
        ]
      });

      if (!result.canceled) {
        const filePath = result.filePath;
        await services.database.exportMeeting(meetingId, filePath, format);
        return { success: true, filePath };
      }

      return { success: false, canceled: true };
    } catch (error) {
      logger.error('Export failed:', error);
      return { success: false, error: error.message };
    }
  });

  // System info
  ipcMain.handle('system:getInfo', () => {
    return {
      platform: process.platform,
      version: app.getVersion(),
      userDataPath: app.getPath('userData'),
      pythonServicesRunning: Object.keys(pythonProcesses).length === 3
    };
  });

  logger.info('IPC handlers setup complete');
}

/**
 * App lifecycle
 */
app.whenReady().then(async () => {
  try {
    logger.info('App starting...');

    // Create windows
    createMainWindow();
    createOverlayWindow();
    createTray();

    // Setup IPC
    setupIPCHandlers();

    // Start Python services
    await startPythonServices();

    // Initialize services
    await initializeServices();

    // Forward session events to renderer
    services.session.on('transcript', (data) => {
      if (mainWindow) {
        mainWindow.webContents.send('session:transcript', data);
      }
      if (overlayWindow && overlayWindow.isVisible()) {
        overlayWindow.webContents.send('session:transcript', data);
      }
    });

    services.session.on('assistance', (data) => {
      if (overlayWindow) {
        overlayWindow.webContents.send('session:assistance', data);
      }
    });

    services.session.on('error', (error) => {
      logger.error('Session error:', error);
      if (mainWindow) {
        mainWindow.webContents.send('session:error', error);
      }
    });

    logger.info('App started successfully');

  } catch (error) {
    logger.error('App start failed:', error);
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createMainWindow();
  }
});

app.on('before-quit', () => {
  app.isQuitting = true;
});

app.on('will-quit', async () => {
  logger.info('App shutting down...');

  // Stop all Python processes
  for (const [name, process] of Object.entries(pythonProcesses)) {
    logger.info(`Stopping ${name} service...`);
    process.kill();
  }

  // Stop API server
  if (services.api) {
    await services.api.stop();
  }

  // Close database
  if (services.database) {
    await services.database.close();
  }

  logger.info('App shutdown complete');
});

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
  logger.error('Uncaught exception:', error);
  dialog.showErrorBox('Application Error', error.message);
});

process.on('unhandledRejection', (reason, promise) => {
  logger.error('Unhandled rejection at:', promise, 'reason:', reason);
});

module.exports = { app, logger };

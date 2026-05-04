/**
 * Test harness that starts/stops the real OpenCowork backend server.
 * Used by automated tests - no dev team participation needed.
 */
import { spawn, ChildProcess } from 'child_process';
import { vi, beforeAll, afterAll } from 'vitest';

let serverProcess: ChildProcess | null = null;
let serverReady = false;
const SERVER_URL = 'http://localhost:7337';
const MAX_WAIT_MS = 10000; // 10 seconds

export async function startServer(): Promise<void> {
  if (serverProcess) return;

  return new Promise((resolve, reject) => {
    serverProcess = spawn('/home/drod/Code/open-cowork/.venv/bin/python', ['-m', 'backend.main'], {
      env: { ...process.env, PYTHONUNBUFFERED: '1' },
      cwd: '/home/drod/Code/open-cowork',
    });

    let output = '';
    const timer = setTimeout(() => {
      if (!serverReady) {
        reject(new Error('Server failed to start within ' + MAX_WAIT_MS + 'ms'));
      }
    }, MAX_WAIT_MS);

    serverProcess.stdout?.on('data', (data: Buffer) => {
      output += data.toString();
      if (output.includes('Application startup complete') || output.includes('Uvicorn running')) {
        serverReady = true;
        clearTimeout(timer);
        resolve();
      }
    });

    serverProcess.stderr?.on('data', (data: Buffer) => {
      console.error('Server stderr:', data.toString());
    });

    serverProcess.on('error', (err) => {
      clearTimeout(timer);
      reject(err);
    });
  });
}

export async function stopServer(): Promise<void> {
  if (!serverProcess) return;

  return new Promise((resolve) => {
    serverProcess?.on('close', () => {
      serverProcess = null;
      serverReady = false;
      resolve();
    });
    serverProcess?.kill('SIGTERM');
    
    // Force kill after 5 seconds
    setTimeout(() => {
      if (serverProcess) {
        serverProcess.kill('SIGKILL');
      }
    }, 5000);
  });
}

export function getServerUrl(): string {
  return SERVER_URL;
}

export function isServerReady(): boolean {
  return serverReady;
}

// Vitest hooks for test files to use
export function setupTestServer() {
  beforeAll(async () => {
    await startServer();
  });

  afterAll(async () => {
    await stopServer();
  });
}

const { spawn } = require('node:child_process');
const { randomUUID } = require('node:crypto');

const EXPECTED_APP = 'stopwatch-voice-companion';

function isOurBackend(health) {
  return Boolean(
    health && health.app === EXPECTED_APP &&
    typeof health.instance === 'string' && health.instance.length > 0 &&
    Number.isInteger(health.pid) && health.pid > 0
  );
}

async function readHealth(baseUrl, fetchImpl = fetch) {
  const response = await fetchImpl(`${baseUrl}/api/health`, {
    signal: AbortSignal.timeout(2500),
  });
  if (!response.ok) throw new Error(`health returned HTTP ${response.status}`);
  return response.json();
}

async function waitForBackend(baseUrl, expectedLaunch, fetchImpl = fetch) {
  let lastError;
  for (let attempt = 0; attempt < 40; attempt += 1) {
    try {
      const health = await readHealth(baseUrl, fetchImpl);
      if (isOurBackend(health) && (!expectedLaunch || health.launch === expectedLaunch)) return health;
      lastError = new Error('port is occupied by a different process');
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw lastError || new Error('backend did not become ready');
}

async function ensureBackend(options) {
  const { baseUrl, python, script, cwd, args = [], fetchImpl = fetch, spawnImpl = spawn } = options;
  try {
    const health = await readHealth(baseUrl, fetchImpl);
    if (!isOurBackend(health)) throw new Error('port is occupied by another application');
    return { health, process: null, ownership: 'external' };
  } catch (error) {
    if (!/fetch failed|ECONNREFUSED|connect|aborted/i.test(String(error.cause || error))) throw error;
  }

  const launch = randomUUID();
  const child = spawnImpl(python, [script, ...args, '--no-browser'], {
    cwd,
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env, PYTHONUTF8: '1', GORK_LAUNCH_TOKEN: launch },
  });
  const health = await waitForBackend(baseUrl, launch, fetchImpl);
  return { health, process: child, serverPid: health.pid, ownership: 'owned' };
}

async function stopOwnedBackend(managed, killImpl = process.kill) {
  if (!managed || managed.ownership !== 'owned' || !managed.process) return false;
  if (managed.serverPid && managed.serverPid !== managed.process.pid) {
    try { killImpl(managed.serverPid); } catch (error) { if (error.code !== 'ESRCH') throw error; }
  } else if (managed.process.exitCode === null) managed.process.kill();
  return true;
}

module.exports = { EXPECTED_APP, ensureBackend, isOurBackend, readHealth, stopOwnedBackend, waitForBackend };

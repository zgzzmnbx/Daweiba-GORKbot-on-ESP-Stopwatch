const test = require('node:test');
const assert = require('node:assert/strict');
const { isOurBackend, stopOwnedBackend } = require('../backend-manager');

test('backend identity requires app, instance and pid', () => {
  assert.equal(isOurBackend({ app: 'stopwatch-voice-companion', instance: 'abc', pid: 42 }), true);
  assert.equal(isOurBackend({ app: 'other', instance: 'abc', pid: 42 }), false);
  assert.equal(isOurBackend({ app: 'stopwatch-voice-companion', instance: '', pid: 42 }), false);
});

test('only owned backend is stopped', async () => {
  let kills = 0;
  const child = { exitCode: null, kill: () => { kills += 1; } };
  assert.equal(await stopOwnedBackend({ ownership: 'external', process: child }), false);
  assert.equal(await stopOwnedBackend({ ownership: 'owned', process: child }), true);
  assert.equal(kills, 1);
});

test('owned Windows launcher stops the verified server pid', async () => {
  const killed = [];
  const child = { pid: 10, exitCode: 0, kill: () => assert.fail('wrapper already exited') };
  assert.equal(await stopOwnedBackend({ ownership: 'owned', process: child, serverPid: 11 }, (pid) => killed.push(pid)), true);
  assert.deepEqual(killed, [11]);
});

/* Reproducible motion acceptance, including unclipped native Canvas pixels. */
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const root = path.resolve(__dirname, '../../../..');
const env = {...process.env, GORK_NO_CLIP: '1', GORK_PROOF_DIR: path.join(root, 'Codex-Temp/motion-pixel-proof')};
for (const name of ['scene-controller', 'editor', 'playback', 'editor-ui', 'editor-render', 'pen-styles', 'integrated', 'writing-range']) {
  const result = spawnSync(process.execPath, [path.join(__dirname, name + '.test.cjs')], {env, stdio: 'inherit'});
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status || 1);
}

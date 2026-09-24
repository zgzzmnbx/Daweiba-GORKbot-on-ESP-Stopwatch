const test = require('node:test');
const assert = require('node:assert/strict');
const { visibleBounds } = require('../window-state');

const displays = [{ workArea: { x: 0, y: 0, width: 1920, height: 1040 } }];
test('keeps visible saved bounds', () => assert.deepEqual(visibleBounds({ x: 100, y: 100, width: 360, height: 330 }, displays), { x: 100, y: 100, width: 360, height: 330 }));
test('rejects off-screen saved bounds', () => assert.equal(visibleBounds({ x: 4000, y: 4000, width: 360, height: 330 }, displays), null));

test('restores a small avatar without expanding it back to default', () => {
  assert.deepEqual(visibleBounds({x:100,y:100,width:180,height:210},displays),{x:100,y:100,width:180,height:210});
});
test('old oversized bounds are constrained to supported avatar dimensions', () => {
  assert.deepEqual(visibleBounds({x:100,y:100,width:900,height:900},displays),{x:100,y:100,width:360,height:420});
});

test('25 percent avatar remains a valid visible saved window', () => {
  assert.deepEqual(visibleBounds({x:100,y:100,width:60,height:70},displays),{x:100,y:100,width:60,height:70});
});

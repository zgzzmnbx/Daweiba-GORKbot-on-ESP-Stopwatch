const test = require('node:test');
const assert = require('node:assert/strict');
const {robotBitmap, createTrayIcon} = require('../tray-icon');

test('tray bitmap has a transparent exterior, visible rim and contrasting eyes', () => {
  const size=128, pixels=robotBitmap(size);
  const at=(x,y)=>[...pixels.subarray((y*size+x)*4,(y*size+x)*4+4)];
  assert.equal(pixels.length, size*size*4);
  assert.deepEqual(at(0,0), [0,0,0,0]);
  assert.deepEqual(at(64,64), [20,20,20,255]);
  assert.deepEqual(at(64,6), [225,225,225,255]);
  assert.deepEqual(at(44,61), [255,255,255,255]);
  assert.deepEqual(at(83,61), [255,255,255,255]);
});

test('tray uses bitmap input and PNG representations for Windows display scales', () => {
  const added=[], resized=[];
  const source={isEmpty:()=>false, resize:options=>{resized.push(options.width);return {toPNG:()=>Buffer.from('png')};}};
  const target={isEmpty:()=>added.length===0,addRepresentation:options=>added.push(options)};
  const nativeImage={createFromBitmap:(pixels,options)=>{
    assert.equal(pixels.length,options.width*options.height*4);return source;
  }, createEmpty:()=>target};
  assert.equal(createTrayIcon(nativeImage),target);
  assert.deepEqual(resized,[16,20,24,32,48]);
  assert.deepEqual(added.map(x=>x.scaleFactor),[1,1.25,1.5,2,3]);
  assert.throws(()=>createTrayIcon({...nativeImage,createFromBitmap:()=>({isEmpty:()=>true})}),/could not be created/);
});

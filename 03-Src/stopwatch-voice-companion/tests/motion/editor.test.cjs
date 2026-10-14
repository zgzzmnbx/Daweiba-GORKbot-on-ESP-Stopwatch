const assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm'),path=require('path');
const Config=require('../../static/motion/gork-config.js'),{SceneController}=require('../../static/motion/scene-controller.js');
const memory=new Map(),storage={getItem:k=>memory.get(k),setItem:(k,v)=>memory.set(k,v)};
const editor=new Config.EditorStore(storage),original=Config.stringify(editor.config);
editor.begin();editor.update('question','question','scale',1.4);editor.update('question','question','x',80);editor.end();
assert.equal(editor.history.length,1);assert.equal(new Config.EditorStore(storage).config.scenes.question.question.x,80);
const changed=Config.stringify(editor.config);assert.equal(Config.stringify(Config.parse(changed)),changed);
editor.reset('question');assert.equal(Config.stringify(editor.config),original);editor.undo();assert.equal(Config.stringify(editor.config),changed);editor.undo();assert.equal(Config.stringify(editor.config),original);
editor.import(changed);assert.equal(Config.stringify(editor.config),changed);editor.undo();assert.equal(Config.stringify(editor.config),original);
for(const bad of ['null','{}','[]','{',' '.repeat(21000),original.replace('"version": 2','"version": 3'),original.replace('"speed": 1','"speed": 500'),original.replace('"version": 2','"version": 2,"__proto__":{}'),original.replace('"speed": 1','"speed": "1"')]){assert.throws(()=>editor.import(bad));assert.equal(Config.stringify(editor.config),original);}
const c=new SceneController({config:Config.parse(changed)});c.set('question',0);assert.equal(c.sample(3000).qSize,1.4);c.setConfig(Config.defaults());assert.equal(c.sample(4000).qSize,1);
for(let i=0;i<500;i++){c.set(Config.sceneNames[i%4],i*13);for(const v of Object.values(c.sample(i*13+2)))assert(Number.isFinite(v));}c.cancel(7000);for(const key of ['spinner','paper','pen','hand','question'])assert.equal(c.sample(10000)[key],0);
console.log('PASS config roundtrip, reject malformed/oversize/unknown/version/range/type, atomic import, undo/reset, persistence, shared config consumer and rapid switches.');

/* Gork Motion Studio config, AGPL-3.0-only. Separate from upstream avatar-definition. */
(function(root){'use strict';
const sceneNames=['idle','loading','writing','question'];
const fields={
 eyes:{x:['水平',-20,20,1],y:['垂直',-35,20,1],spacing:['间距',28,65,1],widthLeft:['左眼宽',8,34,1],heightLeft:['左眼高',8,65,1],widthRight:['右眼宽',8,34,1],heightRight:['右眼高',8,65,1],headX:['俯仰',-15,15,1],headY:['转头',-20,20,1],headZ:['歪头',-25,25,1]},
 motion:{speed:['循环速度',.25,2.5,.05],enterMs:['进入时长',150,2500,50],exitMs:['退出时长',150,2500,50]},
 loading:{x:['水平位置',-110,110,1],y:['垂直位置',-110,110,1],scale:['符号大小',.5,2,.05]},
 writing:{x:['整体水平',-160,160,1],y:['整体垂直',-120,200,1],scale:['笔迹整体大小',.25,2.5,.05],penScale:['笔的大小',.25,3,.05],strokeWidth:['笔迹粗细',.5,12,.25],penStyle:['笔型',['quill','nib','pencil','brush']]},
 question:{x:['水平位置',-145,145,1],y:['垂直位置',-145,145,1],scale:['问号大小',.5,1.5,.05],bob:['浮动幅度',0,10,1]}
};
const clone=x=>JSON.parse(JSON.stringify(x));
function defaults(){const c={schema:'gork-motion-studio',version:2,scenes:{}};for(const name of sceneNames)c.scenes[name]={eyes:{x:0,y:-7,spacing:35,widthLeft:20,heightLeft:50,widthRight:20,heightRight:50,headX:0,headY:0,headZ:0},motion:{speed:1,enterMs:name==='writing'?1250:name==='question'?800:750,exitMs:900}};
c.scenes.loading.loading={x:0,y:-25,scale:1};
Object.assign(c.scenes.writing.eyes,{y:-29,headX:-4,headY:5,headZ:-7,heightLeft:40,heightRight:40});c.scenes.writing.writing={x:0,y:100,scale:1,penScale:1,strokeWidth:3,penStyle:'quill'};
Object.assign(c.scenes.question.eyes,{headX:-3,headY:-13,headZ:15,widthLeft:21,heightLeft:54,widthRight:33,heightRight:15});c.scenes.question.question={x:115,y:-106,scale:1,bob:5};return c;}
function exact(value,keys,label){if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).length!==keys.length||Object.keys(value).some(k=>!keys.includes(k)))throw Error(`${label} 字段不完整或含未知字段`);}
function validate(input){
 exact(input,['schema','version','scenes'],'配置');if(input.schema!=='gork-motion-studio'||![1,2].includes(input.version))throw Error('不是受支持的 Gork Motion Studio 配置');
 exact(input.scenes,sceneNames,'场景');const out=defaults(),legacy=input.version===1;
 for(const scene of sceneNames){const groups=['eyes','motion',...(scene==='idle'?[]:[scene])];exact(input.scenes[scene],groups,scene);
  for(const group of groups){const specs=legacy&&group==='writing'?{x:fields.writing.x,y:fields.writing.y,scale:fields.writing.scale,penScale:fields.writing.penScale,handScale:['旧手套大小',.6,1.2,.05]}:fields[group];
   exact(input.scenes[scene][group],Object.keys(specs),`${scene}.${group}`);
   for(const [key,meta]of Object.entries(specs)){const v=input.scenes[scene][group][key];
    if(Array.isArray(meta[1])){if(typeof v!=='string'||!meta[1].includes(v))throw Error('未知笔型');}
    else if(typeof v!=='number'||!Number.isFinite(v)||v<meta[1]||v>meta[2])throw Error(`${meta[0]} 必须在 ${meta[1]}–${meta[2]} 之间`);
    if(key!=='handScale')out.scenes[scene][group][key]=v;
   }
  }
 }return out;
}
function parse(text){if(typeof text!=='string'||new TextEncoder().encode(text).length>20480)throw Error('配置不能超过 20 KB');let c;try{c=JSON.parse(text);}catch{throw Error('JSON 格式无效');}return validate(c);}
function stringify(c){return JSON.stringify(validate(c),null,2)+'\n';}
class EditorStore{
 constructor(storage){this.storage=storage;this.key='gork-motion-studio-v1';this.config=defaults();this.history=[];this.transaction=null;this.warning=storage?'':'当前浏览器不支持本地保存，请导出备份';try{const saved=storage?.getItem(this.key);if(saved)this.config=parse(saved);}catch{this.warning='本机保存的配置无法读取，已使用默认值';}}
 begin(){if(!this.transaction)this.transaction=clone(this.config);}
 end(){if(this.transaction&&JSON.stringify(this.transaction)!==JSON.stringify(this.config)){this.history.push(this.transaction);if(this.history.length>60)this.history.shift();}this.transaction=null;}
 persist(){try{if(!this.storage)throw Error('Storage unavailable');this.storage.setItem(this.key,stringify(this.config));this.warning='';return true;}catch{this.warning='浏览器无法保存，请先导出配置';return false;}}
 update(scene,group,key,value){if(!sceneNames.includes(scene)||!fields[group]?.[key]||!Object.hasOwn(this.config.scenes[scene],group))throw Error('未知参数');const copy=clone(this.config);copy.scenes[scene][group][key]=value;this.config=validate(copy);this.persist();}
 undo(){this.end();if(this.history.length){this.config=this.history.pop();this.persist();return true;}return false;}
 reset(scene){this.begin();this.config.scenes[scene]=defaults().scenes[scene];this.end();this.persist();}
 import(text){const next=parse(text);this.end();this.begin();this.config=next;this.end();this.persist();}
}
const api={sceneNames,fields,defaults,validate,parse,stringify,EditorStore,clone};if(typeof module!=='undefined')module.exports=api;else root.GorkConfig=api;
})(typeof window!=='undefined'?window:globalThis);

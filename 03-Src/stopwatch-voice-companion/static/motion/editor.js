/* Gork Motion Studio editor. Local-only, AGPL-3.0-only. */
(async function(){'use strict';
const $=s=>document.querySelector(s),names={idle:'待机',loading:'加载',writing:'书写',question:'疑惑'},groupNames={eyes:'眼睛与姿态',motion:'动作节奏',loading:'加载符号',writing:'笔型与笔迹',question:'问号'};
let storage;try{storage=localStorage;}catch{}
let savedRecord,loadedRevision=0,saveMessage='',library={revision:0,entries:[]},editingId=null,suggestedName='我的待机';
async function request(method='GET',body,suffix=''){const r=await fetch('/api/motion/expressions'+suffix,{method,headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});const data=await r.json();if(!r.ok)throw Error(data.error?.message||'动效配置操作失败');return data;}
const store=new GorkConfig.EditorStore(null);
try {const r=await fetch('/api/motion/config');if(!r.ok)throw Error('旧参数不可读');const old=await r.json();store.config=GorkConfig.validate(old.config);}
catch {store.config=GorkConfig.parse(await (await fetch('initial-config.gork.json')).text());}
const initialConfig=GorkConfig.clone(store.config);
savedRecord={config:GorkConfig.clone(store.config)};
try {library=await request();loadedRevision=library.revision;saveMessage=library.warning||'新建自定义表情；保存不会改变默认表情或当前播放';}
catch(error){saveMessage='表情库读取失败：'+error.message;$('#save').disabled=$('#save-as-new').disabled=true;}
store.storage={setItem(_key,text){if(!storage)throw Error('草稿存储不可用');storage.setItem('gork-motion-draft-v2',JSON.stringify({baseRevision:loadedRevision,expressionId:editingId,expressionName:$('#expression-name').value,scene:selected,config:GorkConfig.parse(text)}));}};
store.warning='';
let draft;try {const raw=storage?.getItem('gork-motion-draft-v2');if(raw){draft=JSON.parse(raw);draft.config=GorkConfig.validate(draft.config);}}catch {saveMessage+='；浏览器草稿损坏，未加载';}
const draftEntry=draft&&library.entries.find(entry=>entry.id===draft.expressionId);
if(draft&&(JSON.stringify(draft.config)!==JSON.stringify(draftEntry?.config||store.config)||(draft.expressionName&&draft.expressionName!==(draftEntry?.name||'我的待机'))||(draft.scene&&draft.scene!==(draftEntry?.scene||'idle')))){$('#restore-draft').hidden=false;$('#draft-note').textContent=draft.baseRevision===loadedRevision?'有未保存草稿，可选择恢复。':`草稿基于 r${draft.baseRevision}，当前保存为 r${loadedRevision}；请明确选择恢复或读取保存版本。`;}
const media=matchMedia('(prefers-reduced-motion: reduce)');let selected='idle',toastTimer,motionOverride=false;
function playbackUI(state){
 $('#phase-label').textContent=state.paused?'已暂停':state.reducedMotion?'静态预览':{enter:'进入中',loop:'循环中',exit:'退出中'}[state.phase];
 $('#scene-label').textContent=names[state.scene];$('#complete').disabled=$('#cancel').disabled=state.scene==='idle';
 $('#pause').textContent=state.paused||state.reducedMotion?'播放循环':'暂停循环';
 $('#motion-note').hidden=!media.matches;$('#motion-note').textContent=state.reducedMotion?'系统偏好减少动态效果，当前为静态预览。点击「播放循环」可在本页启用动画。':'已在本页启用循环预览；系统的减少动态效果设置未改变。';
 $('#follow-system').hidden=!media.matches||!motionOverride;
}
const player=GorkScenePlayer.mount($('#avatar'),store.config,{reducedMotion:media.matches,onFrame:playbackUI});
function playExplicitly(){motionOverride=true;player.setReducedMotion(false);player.pause(false);}

function notify(text){const toast=$('#toast');toast.textContent=text;toast.hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>toast.hidden=true,4200);}
function saved(){const warning=store.warning;const dirty=JSON.stringify(store.config)!==JSON.stringify(savedRecord.config)||(savedRecord.name!==undefined&&savedRecord.name!==$('#expression-name').value)||(savedRecord.scene!==undefined&&savedRecord.scene!==selected);$('#save-status').textContent=warning||saveMessage+(dirty?'；调整尚未保存':'');$('#undo').disabled=!store.history.length&&!store.transaction;}
function apply(){player.setConfig(store.config);saved();}
function makeControl(scene,group,key,meta){
 const wrap=document.createElement('div');wrap.className='control';
 if(Array.isArray(meta[1])){const id=`${group}-${key}`,label=document.createElement('label'),select=document.createElement('select');label.htmlFor=id;label.textContent=meta[0];select.id=id;select.setAttribute('aria-label',meta[0]);for(const value of meta[1]){const opt=document.createElement('option');opt.value=value;opt.textContent=GorkPens.labels[value];select.append(opt);}select.value=store.config.scenes[scene][group][key];select.addEventListener('change',()=>{store.begin();store.update(scene,group,key,select.value);store.end();apply();});wrap.className+=' pen-choice';wrap.append(label,select);return wrap;}
 const id=`${group}-${key}`,label=document.createElement('label');label.htmlFor=id;label.textContent=meta[0]+(key.endsWith('Ms')?' / ms':key==='speed'?' / ×':'');
 const number=document.createElement('input');number.type='number';number.id=id;number.min=meta[1];number.max=meta[2];number.step=meta[3];number.value=store.config.scenes[scene][group][key];number.setAttribute('aria-label',meta[0]);
 const range=document.createElement('input');range.type='range';range.min=meta[1];range.max=meta[2];range.step=meta[3];range.value=number.value;range.setAttribute('aria-label',meta[0]+'滑杆');
 function change(raw){if(raw.trim()==='')throw Error('请输入数字');const value=Number(raw);if(!Number.isFinite(value)||value<meta[1]||value>meta[2])throw Error(`${meta[0]} 范围 ${meta[1]}–${meta[2]}`);store.update(scene,group,key,value);number.value=range.value=String(value);apply();}
 range.addEventListener('input',()=>{store.begin();try{change(range.value);}catch(e){notify(e.message);}});
 range.addEventListener('change',()=>{store.end();saved();});range.addEventListener('blur',()=>{store.end();saved();});
 number.addEventListener('change',()=>{store.begin();try{change(number.value);store.end();saved();}catch(e){number.value=store.config.scenes[scene][group][key];store.end();notify(e.message);}});
 wrap.append(label,number,range);return wrap;
}
function buildFields(){const holder=$('#fields');holder.replaceChildren();$('#editing-title').textContent=names[selected];
 const groups=[...(selected==='idle'?[]:[selected]),'eyes','motion'];
 for(const group of groups){const details=document.createElement('details');details.className='group';details.open=group!=='eyes'||selected==='idle';
 const summary=document.createElement('summary');summary.textContent=groupNames[group];const body=document.createElement('div');body.className='group-body';
 if(group==='eyes'&&selected==='loading'){const note=document.createElement('p');note.className='group-note';note.textContent='眼睛在加载后收起；重播入场可观察变化。';body.append(note);}
 if(group==='motion'){const note=document.createElement('p');note.className='group-note';note.textContent='速度影响循环。调整时长后，用重播／完成查看进出场。';body.append(note);}
 for(const [key,meta]of Object.entries(GorkConfig.fields[group]))body.append(makeControl(selected,group,key,meta));details.append(summary,body);holder.append(details);
 }saved();}
function select(scene){if(!Object.hasOwn(names,scene))throw Error('未知场景');store.end();selected=scene;if($('#expression-name').value===suggestedName){suggestedName='我的'+names[scene];$('#expression-name').value=suggestedName;}player.pause(false);document.querySelectorAll('[data-scene]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.scene===scene)));player.set(scene,{force:true});buildFields();store.persist();}
document.querySelectorAll('[data-scene]').forEach(b=>b.addEventListener('click',()=>select(b.dataset.scene)));
$('#pause').addEventListener('click',()=>{const state=player.getState();if(state.paused||state.reducedMotion)playExplicitly();else player.pause(true);});
$('#follow-system').addEventListener('click',()=>{motionOverride=false;player.setReducedMotion(media.matches);});
$('#replay').addEventListener('click',()=>{playExplicitly();player.set(selected,{force:true});});
$('#complete').addEventListener('click',()=>{player.pause(false);player.complete();});$('#cancel').addEventListener('click',()=>{player.pause(false);player.cancel();});
$('#undo').addEventListener('click',()=>{if(store.undo()){apply();buildFields();notify('已撤销上一步');}});
$('#reset').addEventListener('click',()=>{store.reset(selected);apply();buildFields();notify(`已重置${names[selected]}，可以撤销`);});
function download(){store.end();const text=GorkConfig.stringify(store.config),url=URL.createObjectURL(new Blob([text],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='gork-scenes.gork.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);notify('已导出当前草稿；保存后可在表情菜单选择播放。');}
function libraryOptions(){const select=$('#custom-expression');select.replaceChildren();const fresh=document.createElement('option');fresh.value='';fresh.textContent='新建自定义表情';select.append(fresh);for(const entry of library.entries){const option=document.createElement('option');option.value=entry.id;option.textContent=entry.name;select.append(option);}select.value=editingId||'';$('#watch-export').disabled=!editingId;$('#save').textContent=editingId?'保存修改':'保存为新表情';$('#library-count').textContent=`已保存 ${library.entries.length}/64 个自定义表情；保存修改更新当前条目，另存保留原条目并新增。`;}
function chooseEntry(id){const entry=library.entries.find(e=>e.id===id);editingId=entry?.id||null;store.end();store.config=GorkConfig.validate(entry?.config||initialConfig);store.history=[];$('#expression-name').value=entry?.name||'我的待机';suggestedName=entry?'':'我的待机';select(entry?.scene||'idle');savedRecord={config:GorkConfig.clone(store.config),name:$('#expression-name').value,scene:selected};saveMessage=entry?'已读取自定义表情：'+entry.name:'新建自定义表情；默认和当前播放不变';libraryOptions();saved();}
async function saveExpression(asNew=false){$('#save').disabled=$('#save-as-new').disabled=true;store.end();saveMessage='正在保存自定义表情…';saved();try{const id=asNew?null:editingId;let name=$('#expression-name').value.trim();if(asNew&&library.entries.some(entry=>entry.name===name)){const base=name.slice(0,42);let index=1;do{name=base+' 副本'+index++;}while(library.entries.some(entry=>entry.name===name));}const next=await request(id?'PUT':'POST',{expected_revision:loadedRevision,name,scene:selected,config:GorkConfig.validate(store.config)},id?'/'+encodeURIComponent(id):'');library={revision:next.revision,entries:next.entries,warning:next.warning};loadedRevision=next.revision;editingId=next.entry.id;savedRecord={config:GorkConfig.clone(next.entry.config),name:next.entry.name,scene:next.entry.scene};$('#expression-name').value=next.entry.name;suggestedName='';saveMessage=(id?'已更新':'已新增')+'自定义表情「'+next.entry.name+'」，已加入表情菜单；当前播放不变';store.persist();libraryOptions();window.parent.postMessage({type:'gork-motion-library-changed'},location.origin);}catch(error){saveMessage='保存失败：'+error.message;notify(saveMessage);}finally{$('#save').disabled=$('#save-as-new').disabled=false;saved();}}
$('#save').addEventListener('click',()=>saveExpression());$('#save-as-new').addEventListener('click',()=>saveExpression(true));
$('#custom-expression').addEventListener('change',()=>chooseEntry($('#custom-expression').value));
$('#load-saved').addEventListener('click',async()=>{try{library=await request();loadedRevision=library.revision;chooseEntry(editingId);$('#save').disabled=$('#save-as-new').disabled=false;$('#draft-note').textContent='';$('#restore-draft').hidden=true;}catch(error){notify(error.message);}});
$('#expression-name').addEventListener('input',()=>{saved();store.persist();});
$('#restore-draft').addEventListener('click',()=>{if(!draft)return;chooseEntry(draft.expressionId);$('#expression-name').value=draft.expressionName||$('#expression-name').value;suggestedName='';if(Object.hasOwn(names,draft.scene))select(draft.scene);store.import(GorkConfig.stringify(draft.config));apply();buildFields();libraryOptions();$('#draft-note').textContent='已恢复草稿；保存后加入表情菜单，当前播放不变。';$('#restore-draft').hidden=true;});
$('#watch-export').addEventListener('click',async()=>{try{for(const kind of ['json','header']){const r=await fetch('/api/motion/watch/'+kind+'?expression_id='+encodeURIComponent(editingId));if(!r.ok)throw Error((await r.json()).error?.message||'Watch 导出失败');const url=URL.createObjectURL(await r.blob()),a=document.createElement('a');a.href=url;a.download=kind==='json'?'gork-scenes.watch.json':'motion_config.h';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}notify('已导出该自定义表情的保存参数；Watch 使用仍需编译候选固件。');}catch(error){notify(error.message);}});
$('#export').addEventListener('click',download);$('#import').addEventListener('click',()=>$('#file-input').click());
$('#file-input').addEventListener('change',async event=>{const file=event.target.files?.[0];if(!file)return;try{if(file.size>20480)throw Error('文件不能超过 20 KB');const text=await file.text();store.import(text);apply();buildFields();player.set(selected,{force:true});notify('已导入草稿；保存为自定义表情后，可在表情菜单选择播放');}catch(e){notify(`导入失败：${e.message}`);}finally{event.target.value='';}});
media.addEventListener('change',()=>player.setReducedMotion(motionOverride?false:media.matches));
window.addEventListener('pagehide',()=>{store.end();clearTimeout(toastTimer);});
// The same validated config drives the editor, exported JSON and reusable player.
window.gorkEditor={getConfig:()=>GorkConfig.clone(store.config),selectScene:select,importConfig(text){store.import(text);apply();buildFields();return {ok:true};},exportConfig:()=>GorkConfig.stringify(store.config),getSavedRevision:()=>loadedRevision,getEditingId:()=>editingId,getState:()=>player.getState()};
const toolLife=new AbortController();if(document.modelContext?.registerTool){for(const tool of [
{name:'get_gork_editor_state',description:'Read the local selected scene and editable config.',inputSchema:{type:'object',properties:{},additionalProperties:false},annotations:{readOnlyHint:true},execute:()=>({selected,state:player.getState(),config:store.config})},
{name:'set_gork_editor_scene',description:'Choose a local scene for editing and preview.',inputSchema:{type:'object',properties:{scene:{type:'string',enum:Object.keys(names)}},required:['scene'],additionalProperties:false},annotations:{readOnlyHint:false},execute:input=>{if(!input||Object.keys(input).length!==1)throw Error('Invalid input');select(input.scene);return player.getState();}}
])try{Promise.resolve(document.modelContext.registerTool(tool,{signal:toolLife.signal})).catch(()=>{});}catch{}}
window.addEventListener('pagehide',event=>{if(!event.persisted)toolLife.abort();});libraryOptions();$('#expression-name').value=suggestedName;buildFields();playbackUI(player.getState());if(store.warning)notify(store.warning);
})();

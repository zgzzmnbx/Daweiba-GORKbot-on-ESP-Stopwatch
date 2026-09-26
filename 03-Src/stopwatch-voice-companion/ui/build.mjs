// Mantine renders the native-control shell at build time. The existing controller
// exclusively owns its DOM at runtime: no hydration, duplicate session or polling.
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {MantineProvider, createTheme, Button, NativeSelect, Textarea, Switch, Checkbox, Paper, Title, Badge, Input} from '@mantine/core';
import {parse, parseFragment, serialize} from 'parse5';
import {readFile, writeFile, mkdir} from 'node:fs/promises';
import {createRequire} from 'node:module';
import path from 'node:path';

const require=createRequire(import.meta.url),h=React.createElement;
const root=new URL('../',import.meta.url),read=p=>readFile(new URL(p,root),'utf8');
const source=await read('ui/console.html');
const tree=parse(source),html=tree.childNodes.find(n=>n.tagName==='html'),body=html.childNodes.find(n=>n.tagName==='body');
const attrs=n=>Object.fromEntries((n.attrs||[]).map(a=>[a.name,a.value]));
const children=n=>(n.childNodes||[]).filter(c=>c.nodeName!=='#comment').map((node,index)=>{const child=convert(node);return React.isValidElement(child)?React.cloneElement(child,{key:index}):child;});
const theme=createTheme({primaryColor:'gork',primaryShade:7,colors:{gork:['#eef9f5','#d9efe5','#b0decc','#82cbb0','#59b897','#3ba985','#289d79','#16876a','#0d7058','#045b47']},defaultRadius:'md',fontFamily:'"Segoe UI", "Microsoft YaHei UI", sans-serif',headings:{fontFamily:'"Segoe UI", "Microsoft YaHei UI", sans-serif'},fontSizes:{xs:'12px',sm:'13px',md:'14px',lg:'16px',xl:'20px'},components:{Button:Button.extend({defaultProps:{size:'sm',radius:'md'}}),NativeSelect:NativeSelect.extend({defaultProps:{size:'sm',radius:'md'}}),Textarea:Textarea.extend({defaultProps:{size:'sm',radius:'md'}})}});
const iconPaths={dialogue:'M4 4h16v12H9l-5 4V4Z',cost:'M5 3h14v18H5zM8 7h8M8 11h2m4 0h2M8 15h2m4 0h2',character:'M8 4h8l4 5v9l-4 3H8l-4-3V9zM8 11v3m8-3v3',watch:'M8 2h8v4H8zM8 18h8v4H8zM6 6h12v12H6zM12 9v3l2 1',settings:'M5 4v16M12 4v16M19 4v16M2 8h6m1 8h6m1-6h6',logs:'M5 4h14v16H5zM8 8h8M8 12h8M8 16h5'};
function icon(name){return h('svg',{className:'nav-icon',viewBox:'0 0 24 24',fill:'none',stroke:'currentColor',strokeWidth:1.6,'aria-hidden':true},h('path',{d:iconPaths[name]||iconPaths.settings,strokeLinecap:'round',strokeLinejoin:'round'}));}
function props(n){const a=attrs(n),p={};for(const [key,value] of Object.entries(a)) {
  const k=({class:'className',for:'htmlFor',tabindex:'tabIndex',maxlength:'maxLength',spellcheck:'spellCheck',viewbox:'viewBox','stroke-width':'strokeWidth'})[key]||key;
  if(['checked','selected'].includes(key))continue;
  p[k]=['hidden','disabled','multiple','open','required'].includes(key)?true:value;
}return p;}
function convert(n){
  if(n.nodeName==='#text')return n.value;
  if(!n.tagName||n.tagName==='script')return null;
  const a=attrs(n),p=props(n),tag=n.tagName;
  if(tag==='input'){if(a.type==='range'||a.type==='color')return h(Input,{...p,defaultValue:a.value,value:undefined,className:'native-'+a.type});return h('input',{...p,defaultChecked:'checked'in a});}
  if(tag==='label'&&['switch-row','consent'].includes(a.class)){
    const input=n.childNodes.find(c=>c.tagName==='input'),label=n.childNodes.find(c=>c.tagName==='span'),ip=props(input);
    const labelText=label.childNodes.filter(c=>c.nodeName==='#text').map(c=>c.value).join('').trim();
    return h(a.class==='switch-row'?Switch:Checkbox,{...ip,value:undefined,'aria-label':labelText,defaultChecked:'checked'in attrs(input),label:children(label),className:a.class,labelPosition:a.class==='switch-row'?'left':'right',size:'sm'});
  }
  let ch=children(n);
  if(tag==='button')return h(Button,{...p,variant:a.class?.includes('primary')?'filled':a.class?.includes('stop')||a.class?.includes('danger')?'subtle':a.class?.includes('text-button')?'subtle':'default',color:a.class?.match(/stop|danger/)?'red':undefined},...ch);
  if(tag==='select'){
    const selected=n.childNodes.find(c=>c.tagName==='option'&&'selected'in attrs(c));
    return h(NativeSelect,{...p,defaultValue:selected?attrs(selected).value:undefined},...ch);
  }
  if(tag==='textarea')return h(Textarea,{...p,defaultValue:n.childNodes.map(c=>c.value||'').join('')});
  if(/^h[123]$/.test(tag))return h(Title,{...p,order:Number(tag.slice(1))},...ch);
  if(tag==='span'&&a.class==='badge')return h(Badge,{...p,variant:'light',color:'gray',radius:'sm'},...ch);
  if(tag==='section'&&a.class?.match(/^(panel|card)/))return h(Paper,{...p,component:'section',withBorder:true,radius:'lg'},...ch);
  if(a.class==='app-header')ch.splice(ch.length-1,0,h(Button,{id:'theme-toggle',variant:'default',title:'切换为经典主题；保留输入与连接','aria-label':'切换为经典主题'},'经典主题'));
  if(a['data-page-link'])ch.unshift(icon(a['data-page-link']));
  if(a.class==='empty-chat')ch.unshift(h('div',{className:'empty-orbit modern-only','aria-hidden':true},icon('dialogue')));
  return h(tag,p,...ch);
}
const rendered=renderToStaticMarkup(h(MantineProvider,{theme,forceColorScheme:'light',withStaticClasses:true},...children(body)),{identifierPrefix:'gork-'});
// Keep the existing strict style-src 'self' CSP. Compile Mantine's SSR inline
// variables into a local stylesheet instead of allowing unsafe-inline.
const fragment=parseFragment(rendered),rules=[],styleClasses=new Map();
function externalize(node){
  // Native disabled properties are updated by the shared controller. A static
  // data-disabled snapshot must not keep enabled controls visually disabled.
  if(node.attrs)node.attrs=node.attrs.filter(a=>a.name!=='data-disabled');
  node.childNodes=(node.childNodes||[]).filter(child=>{if(child.tagName==='style'){rules.push(child.childNodes.map(c=>c.value||'').join(''));return false;}return true;});
  const style=node.attrs?.find(a=>a.name==='style');
  if(style){let name=styleClasses.get(style.value);if(!name){name=`gork-style-${styleClasses.size}`;styleClasses.set(style.value,name);rules.push(`.${name}{${style.value}}`);}node.attrs=node.attrs.filter(a=>a!==style);const cls=node.attrs.find(a=>a.name==='class');if(cls)cls.value+=' '+name;else node.attrs.push({name:'class',value:name});}
  node.childNodes.forEach(externalize);
}
externalize(fragment);
const markup=serialize(fragment),componentCss=rules.join('\n')+'\n';
const output=`<!doctype html>
<!-- Generated by ui/build.mjs from official Mantine components. Edit ui/console.html. -->
<html lang="zh-CN" data-console-theme="mantine" data-mantine-color-scheme="light"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Gork 机器人控制台</title>
<link id="classic-style" rel="stylesheet" href="/static/style.css" media="not all">
<link id="classic-bridge" rel="stylesheet" href="/static/classic-bridge.css" media="not all">
<link id="mantine-style" rel="stylesheet" href="/static/mantine/vendor.css">
<link id="mantine-components" rel="stylesheet" href="/static/mantine/components.css">
<link id="modern-style" rel="stylesheet" href="/static/modern.css">
<script src="/static/console-theme.js"></script></head><body>${markup}
<script src="/static/gork-catalog.js"></script><script src="/static/avatar-engine.js"></script><script src="/static/avatar-presets.js"></script><script src="/static/gork-appearance.js"></script><script src="/static/gork-avatar.js"></script><script type="module" src="/static/app.js"></script></body></html>\n`;
const vendorPath=require.resolve('@mantine/core/styles.css');
const vendor=await readFile(vendorPath,'utf8');
await mkdir(new URL('static/mantine/',root),{recursive:true});
if(process.argv.includes('--check')){
  if(await read('static/index.html')!==output||await read('static/mantine/vendor.css')!==vendor||await read('static/mantine/components.css')!==componentCss)throw new Error('UI build is stale. Run npm run build:ui');
  console.log('Mantine shell and CSS match the source and locked dependency');
}else{
  await writeFile(new URL('static/index.html',root),output);await writeFile(new URL('static/mantine/vendor.css',root),vendor);
  await writeFile(new URL('static/mantine/components.css',root),componentCss);
  await writeFile(new URL('static/mantine/LICENSE',root),await readFile(path.join(path.dirname(vendorPath),'LICENSE')));
  console.log('Built native-control console with Mantine 9.6.2');
}

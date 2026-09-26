export function createAppearancePicker(document,{library,renderer,catalog,storage,bridge,onChange}) {
  const get=id=>document.getElementById(id),details=get('appearance-menu'),grid=get('appearance-grid');
  let current=library.normalize(null),pending=false,built=false,edited=false;
  const cards=[];
  try { current=library.normalize(JSON.parse(storage?.getItem('gork.appearance') || 'null')); } catch {}
  function paint() {
    for(const card of cards)card.button.setAttribute('aria-pressed',String(card.id===current.id));
    get('appearance-body').value=current.bodyColor;get('appearance-eyes').value=current.eyeColor;
    get('appearance-name').textContent=library.presets.find(p=>p.id===current.id).name;
    get('companion-name').textContent=current.id==='gork'?'Gork':library.presets.find(p=>p.id===current.id).name;
    onChange(current);
  }
  async function apply(value) {
    if(pending)return;
    pending=true;edited=true;
    const controls=[...cards.map(c=>c.button),get('appearance-body'),get('appearance-eyes'),get('appearance-reset')];
    controls.forEach(c=>c.disabled=true);
    try {
      const next=library.normalize(value);
      current=bridge?.setAppearance ? library.normalize(await bridge.setAppearance(next)) : next;
      try { storage?.setItem('gork.appearance',JSON.stringify(current)); } catch {}
      paint();get('appearance-feedback').textContent=bridge?.setAppearance ? '已应用到控制台与桌面小人，自动保存。' : '已保存网页形象；桌面同步需使用新版桌面客户端。';
    } catch {get('appearance-feedback').textContent='形象保存失败，请重试。';paint();}
    finally {pending=false;controls.forEach(c=>c.disabled=false);}
  }
  details.addEventListener('toggle',()=>{
    if(!details.open)return;
    if(!built) {
      built=true;
      for(const preset of library.presets) {
        const button=document.createElement('button'),canvas=document.createElement('canvas'),label=document.createElement('span');
        button.type='button';button.className='expression-tile';button.setAttribute('aria-label','选择形象 '+preset.name);
        canvas.setAttribute('aria-hidden','true');label.textContent=preset.name;button.append(canvas,label);grid.append(button);
        button.onclick=()=>apply({id:preset.id});cards.push({button,canvas,id:preset.id});
      }
    }
    for(const card of cards)renderer.mount(card.canvas,catalog,{still:true,appearance:{id:card.id}}).dispose();
    paint();
  });
  get('appearance-body').onchange=()=>apply({...current,bodyColor:get('appearance-body').value});
  get('appearance-eyes').onchange=()=>apply({...current,eyeColor:get('appearance-eyes').value});
  get('appearance-reset').onclick=()=>apply({id:'gork'});
  paint();
  const ready=bridge?.getAppearance?.().then(value=>{if(!edited){current=library.normalize(value);paint();}}).catch(()=>{get('appearance-feedback').textContent='桌面形象读取失败；请重试或重开客户端。';});
  return {ready};
}

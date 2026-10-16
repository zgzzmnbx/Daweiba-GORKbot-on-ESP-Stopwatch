export function createVoiceVolume({document,api,acquireWorkspace,hasWorkspace,apply,report}){
  const input=document.getElementById('voice-volume'),label=document.getElementById('voice-volume-label');
  let confirmed=100,pending=null,saving=false,timer=null;
  function paint(value){input.value=String(value);label.textContent=`${value}%`;input.setAttribute('aria-valuetext',`电脑语音音量 ${value}%`);apply(value);}
  async function save(){
    clearTimeout(timer);timer=null;
    if(saving||pending===null)return;
    const value=pending;pending=null;saving=true;
    try{
      if(!hasWorkspace()&&!await acquireWorkspace())throw Error('请先取得工作台控制权，再调整电脑语音音量。');
      const result=await api('/voice/volume','PUT',{volume:value});confirmed=result.volume;
    }catch(error){if(pending===null)paint(confirmed);report(error.message,true);}
    finally{saving=false;if(pending!==null)await save();}
  }
  input.oninput=()=>{const value=Number(input.value);paint(value);pending=value;clearTimeout(timer);timer=setTimeout(save,300);};
  input.onchange=save;
  async function load(){
    try{const result=await api('/voice/volume');if(!Number.isInteger(result.volume)||result.volume<0||result.volume>100)throw Error('invalid volume');confirmed=result.volume;paint(confirmed);input.disabled=false;}
    catch{input.disabled=true;label.textContent='—';input.title='音量读取失败；请确认新版后台已重开后刷新页面。';}
  }
  load();return {load};
}

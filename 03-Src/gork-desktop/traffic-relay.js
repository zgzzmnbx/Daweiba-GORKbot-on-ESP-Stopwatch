// Independent read-only relay. One bounded request; hidden avatar stops polling.
function createTrafficRelay({avatar,read,onValue=()=>{},interval=1000}){
  let timer=null,disposed=false,running=false,generation=0,lastEnabled=false;
  const visible=()=>!disposed&&!avatar.isDestroyed()&&avatar.isVisible()&&!avatar.isMinimized();
  async function poll(){
    clearTimeout(timer);if(!visible()||running)return;
    running=true;const gen=generation;
    try{const value=await read();if(visible()&&gen===generation){lastEnabled=value.enabled===true;avatar.webContents.send('gork:traffic',value);onValue(value);}}
    catch{if(visible()&&gen===generation){const value={enabled:lastEnabled,physical:{status:'unavailable'},clash:{status:'unavailable'}};avatar.webContents.send('gork:traffic',value);onValue(value);}}
    finally{running=false;if(visible())timer=setTimeout(poll,interval);}
  }
  const hide=()=>{generation++;clearTimeout(timer);};
  for(const event of ['show','restore'])avatar.on(event,poll);
  for(const event of ['hide','minimize'])avatar.on(event,hide);
  avatar.webContents.on('did-finish-load',poll);
  function dispose(){disposed=true;hide();for(const event of ['show','restore'])avatar.removeListener(event,poll);for(const event of ['hide','minimize'])avatar.removeListener(event,hide);avatar.webContents.removeListener('did-finish-load',poll);}
  return {dispose};
}
module.exports={createTrafficRelay};

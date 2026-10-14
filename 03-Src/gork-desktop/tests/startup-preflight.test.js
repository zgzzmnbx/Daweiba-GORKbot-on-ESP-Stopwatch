const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {execFileSync, spawnSync} = require('node:child_process');
const {randomUUID} = require('node:crypto');
const root = path.resolve(__dirname, '../../..');
const preflight = path.join(root, 'tools/gork-startup-preflight.ps1');
const python = path.join(root, 'Codex-Temp/.venv-companion/Scripts/python.exe');
const windows = process.platform === 'win32';

test('Windows startup ownership cases preserve live, foreign, independent and reused-PID processes', {skip: !windows}, () => {
  const output = execFileSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-File',
    path.join(__dirname, 'startup-preflight-cases.ps1'), '-Preflight', preflight], {encoding:'utf8', timeout:30000});
  assert.match(output, /16 startup ownership cases passed/);
});

test('real Windows startup cleans only an orphan fixture and preserves independent or foreign servers', {skip: !windows, timeout:120000}, async () => {
  const fixtureRoot = path.join(root, 'Codex-Temp/startup-v0208', `fixture 空间-${randomUUID()}`);
  const fixturePython = path.join(fixtureRoot, 'Codex-Temp/.venv-companion/Scripts/python.exe');
  const fixtureScript = path.join(fixtureRoot, '03-Src/stopwatch-voice-companion/run_companion.py');
  fs.mkdirSync(path.dirname(fixturePython), {recursive:true});
  fs.mkdirSync(path.dirname(fixtureScript), {recursive:true});
  fs.mkdirSync(path.join(fixtureRoot,'03-Src/gork-desktop'), {recursive:true});
  fs.copyFileSync(python, fixturePython);
  fs.copyFileSync(path.join(root,'Codex-Temp/.venv-companion/pyvenv.cfg'), path.join(fixtureRoot,'Codex-Temp/.venv-companion/pyvenv.cfg'));
  fs.writeFileSync(path.join(fixtureRoot,'03-Src/gork-desktop/package.json'), JSON.stringify({version:'fixture-v1'}));
  fs.writeFileSync(fixtureScript, `import json,os\nfrom http.server import BaseHTTPRequestHandler,HTTPServer\nclass Handler(BaseHTTPRequestHandler):\n def do_GET(self):\n  value=dict(app='stopwatch-voice-companion',instance='fixture-only',pid=os.getpid(),version='fixture-v1',launch=os.environ.get('GORK_FIXTURE_LAUNCH',''))\n  data=json.dumps(value).encode();self.send_response(200);self.end_headers();self.wfile.write(data)\n def log_message(self,*args):pass\nHTTPServer(('127.0.0.1',int(os.environ['GORK_FIXTURE_PORT'])),Handler).serve_forever()\n`);
  const foreignScript = path.join(path.dirname(fixtureScript), 'foreign_server.py');
  fs.copyFileSync(fixtureScript, foreignScript);
  const fixtureTools = path.join(fixtureRoot,'tools');
  const fixtureElectron = path.join(fixtureRoot,'03-Src/gork-desktop/node_modules/electron/dist/electron.exe');
  const marker = path.join(path.dirname(fixtureElectron),'fixture-started.txt');
  fs.mkdirSync(fixtureTools,{recursive:true});fs.mkdirSync(path.dirname(fixtureElectron),{recursive:true});
  fs.copyFileSync(preflight,path.join(fixtureTools,'gork-startup-preflight.ps1'));
  fs.copyFileSync(path.join(root,'start-gork-console.cmd'),path.join(fixtureRoot,'start-gork-console.cmd'));
  const stubSource=path.join(fixtureRoot,'stub.cs'),compiler=path.join(fixtureRoot,'compile-stub.ps1');
  fs.writeFileSync(stubSource,'using System;using System.IO;class Stub {static void Main(string[] args){File.WriteAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"fixture-started.txt"),args.Length==1?args[0]:"bad-arguments");}}');
  fs.writeFileSync(compiler,'param([string]$Source,[string]$Target)\n$ErrorActionPreference="Stop"\nAdd-Type -Path $Source -OutputAssembly $Target -OutputType WindowsApplication\n');
  execFileSync('powershell.exe',['-NoProfile','-File',compiler,'-Source',stubSource,'-Target',fixtureElectron],{timeout:30000});
  // Exercise the actual double-click script with a windowless fixture executable.
  // Only the fixture copy changes its loopback test port; production stays on 8766.
  const fixtureCmd=path.join(fixtureRoot,'start-gork-console.cmd');
  fs.writeFileSync(fixtureCmd,fs.readFileSync(fixtureCmd,'utf8').replace('-ProjectRoot "%ROOT%."','-ProjectRoot "%ROOT%." -Port 18868'));
  const launcher = path.join(fixtureRoot,'launcher.py');
  // The launcher exits so its child venv wrapper really becomes an orphan.
  fs.writeFileSync(launcher, `import subprocess,sys,json\np=subprocess.Popen([sys.argv[1],sys.argv[2],'--no-browser'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\nprint(json.dumps(dict(wrapper_pid=p.pid)))\n`);
  const port=18868;
  const url=`http://127.0.0.1:${port}/api/health`;
  try { await fetch(url, {signal:AbortSignal.timeout(500)}); assert.fail('fixture port must be free'); }
  catch (error) { if (error.code === 'ERR_ASSERTION') throw error; }
  const run = (inspect=false) => spawnSync('powershell.exe', ['-NoProfile','-NonInteractive','-File',preflight,
    '-ProjectRoot',fixtureRoot,'-Port',String(port), ...(inspect?['-InspectOnly']:[])], {encoding:'utf8',timeout:30000});
  const configuredRun = customPort => spawnSync('powershell.exe',['-NoProfile','-NonInteractive','-File',preflight,
    '-ProjectRoot',fixtureRoot,'-InspectOnly'],{encoding:'utf8',timeout:30000,env:{...process.env,GORK_BACKEND_PORT:customPort}});
  assert.equal(configuredRun('invalid-port').status,1,'invalid configuration must stop startup');
  const evidence=[];
  for (const scenario of ['orphan','independent','foreign']) {
    const launch=JSON.parse(execFileSync(python,[launcher,fixturePython, scenario==='foreign'?foreignScript:fixtureScript],{
      encoding:'utf8',timeout:10000,env:{...process.env,GORK_FIXTURE_PORT:String(port),GORK_FIXTURE_LAUNCH:scenario==='independent'?'':randomUUID()}}));
    let health;
    try {
      for(let attempt=0;attempt<50;attempt++) {
        try {health=await (await fetch(url,{signal:AbortSignal.timeout(500)})).json();break;} catch {}
        await new Promise(resolve=>setTimeout(resolve,100));
      }
      assert(health, 'fixture server must start');
      const preview=run(true);assert.equal(preview.status,0,preview.stdout+preview.stderr);
      const decision=JSON.parse(preview.stdout.trim());
      assert.equal(decision.Action,scenario==='orphan'?'clean':scenario==='independent'?'reuse':'block');
      if(scenario==='independent') {
        const configured=configuredRun(String(port));assert.equal(configured.status,0,configured.stdout+configured.stderr);
        assert.equal(JSON.parse(configured.stdout.trim()).Reason,'external-backend','custom-port environment must select the configured server');
      }
      assert.equal((await (await fetch(url)).json()).pid,health.pid,'inspection must not stop server');
      fs.rmSync(marker,{force:true});
      const result=spawnSync('cmd.exe',['/d','/c','start-gork-console.cmd'],{
        cwd:fixtureRoot,encoding:'utf8',input:'\r\n',timeout:30000});
      assert.equal(result.status,scenario==='foreign'?1:0,result.stdout+result.stderr);
      for(let attempt=0;attempt<20 && !fs.existsSync(marker) && scenario!=='foreign';attempt++) {
        await new Promise(resolve=>setTimeout(resolve,100));
      }
      assert.equal(fs.existsSync(marker),scenario!=='foreign','launcher must run only after successful preflight');
      if(scenario!=='foreign') assert.equal(fs.readFileSync(marker,'utf8'),path.join(fixtureRoot,'03-Src/gork-desktop'),'quoted app path must reach launcher intact');
      if(scenario==='orphan') {
        await assert.rejects(fetch(url,{signal:AbortSignal.timeout(500)}));
      } else {
        assert.equal((await (await fetch(url)).json()).pid,health.pid,'protected server must remain alive');
      }
      const record=JSON.parse(fs.readFileSync(path.join(fixtureRoot,'Codex-Temp/gork-startup/preflight-last.json'),'utf8').replace(/^\uFEFF/,''));
      assert.equal(record.reason,decision.Reason);
      const history=fs.readFileSync(path.join(fixtureRoot,'Codex-Temp/gork-startup/preflight-history.jsonl'),'utf8').trim();
      assert.equal(history.split(/\r?\n/).length,evidence.length+1,'startup actions must retain history');
      assert(!history.includes('CommandLine') && !history.includes('launch'),'process command text and launch tokens must stay out of logs');
      evidence.push({scenario,action:decision.Action,reason:decision.Reason,exit_code:result.status,
        preserved:scenario!=='orphan',cleaned_count:record.cleaned_pids.length,entryScriptVerified:true});
    } finally {
      for(const pid of [health?.pid,launch.wrapper_pid]) if(pid) {try {process.kill(pid);} catch(error) {if(error.code!=='ESRCH')throw error;}}
      await new Promise(resolve=>setTimeout(resolve,250));
    }
  }
  fs.writeFileSync(path.join(root,'Codex-Temp/startup-v0208/integration-evidence.json'),JSON.stringify({fixtureOnly:true,scenarios:evidence},null,2));
});

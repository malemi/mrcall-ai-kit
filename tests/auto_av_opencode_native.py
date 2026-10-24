import base64
import http.server
import json
import os
from pathlib import Path
import shutil
import socket
import select
import sys
import subprocess
import tempfile
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
subprocess.run(['node', str(ROOT/'tests/test_auto_av_opencode.mjs')], check=True)
evidence_root = Path(os.environ.get('AUTO_AV_EVIDENCE_ROOT', str(Path(tempfile.gettempdir())/'mrcall-ai-kit'/'automatic-av-20261021')))
evidence_root.mkdir(parents=True, exist_ok=True)
work = Path(tempfile.mkdtemp(prefix='automatic_av_opencode-native-', dir=evidence_root))
policy_text = (ROOT/'shared/shortcuts/selector.md').read_text()
canonical_source = (ROOT/'shared/shortcuts/av.md').read_text()
request_text = 'Report the fixture result.\nPreserve this user text: "exact" — café.'
mode = sys.argv[1] if len(sys.argv)>1 else 'positive'
draft_text = '😀'*300 if mode == 'short' else 'Completed fixture result.'.ljust(301, '.')
expected_prompt = subprocess.check_output(['node', '--input-type=module', '-e', "import { readFileSync } from 'node:fs'; import { automaticPrompt } from './opencode/plugins/auto-av-v2/protocol.js'; const input=JSON.parse(readFileSync(0,'utf8')); process.stdout.write(automaticPrompt(readFileSync('shared/shortcuts/av.md','utf8'),input));"], cwd=ROOT, input=json.dumps({'request':request_text,'draft':draft_text}).encode()).decode()
stance_body = canonical_source.split('---\n', 2)[2].removeprefix('\n').replace('$ARGUMENTS','')
assert expected_prompt.startswith(stance_body+'\n\n')
assert '$ARGUMENTS' not in expected_prompt
assert 'CANONICAL_AV_FIXTURE' not in canonical_source
def content_text(content):
    return content if isinstance(content,str) else ''.join(part.get('text','') for part in content or [])
def is_selector(data):
    return any(message.get('role')=='user' and content_text(message.get('content')).startswith(policy_text+'\n\n') for message in data.get('messages',[]))
def is_continuation(data):
    return any(message.get('role')=='user' and content_text(message.get('content'))==expected_prompt for message in data.get('messages',[]))
requests = []
aborted = threading.Event()
class Provider(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"data":[]}')
    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        requests.append(data)
        policy = is_selector(data)
        if policy and mode == 'timeout':
            end = time.monotonic()+35
            while time.monotonic()<end:
                readable, _, _ = select.select([self.connection], [], [], .1)
                if readable:
                    try:
                        closed = self.connection.recv(1, socket.MSG_PEEK) == b''
                    except ConnectionResetError:
                        closed = True
                    if closed:
                        aborted.set()
                        return
            return
        text = ('SKIP' if mode == 'negative' else 'APPLY') if policy else draft_text
        body = json.dumps({'id':'fixture','object':'chat.completion','created':1,'model':'fixture','choices':[{'index':0,'message':{'role':'assistant','content':text},'finish_reason':'stop'}],'usage':{'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}}).encode()
        if data.get('stream'):
            chunks = [{'id':'fixture','object':'chat.completion.chunk','created':1,'model':'fixture','choices':[{'index':0,'delta':{'role':'assistant','content':text},'finish_reason':None}]}, {'id':'fixture','object':'chat.completion.chunk','created':1,'model':'fixture','choices':[{'index':0,'delta':{},'finish_reason':'stop'}]}]
            body = ''.join('data: '+json.dumps(chunk)+'\n\n' for chunk in chunks).encode()+b'data: [DONE]\n\n'
        self.send_response(200)
        self.send_header('Content-Type','text/event-stream' if data.get('stream') else 'application/json')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers()
        self.wfile.write(body)
provider = http.server.ThreadingHTTPServer(('127.0.0.1',0),Provider)
threading.Thread(target=provider.serve_forever,daemon=True).start()
config = work/'config'/'opencode'
config.mkdir(parents=True)
plugin = work/'plugin'
shutil.copytree(ROOT/'opencode/plugins/auto-av-v2', plugin)
subprocess.run(['npm', 'install', '--prefix', str(plugin), '--ignore-scripts', '--no-audit', '--no-fund'], check=True, timeout=30)
assets = work/'kit'/'auto-av'
assets.mkdir(parents=True)
shutil.copyfile(ROOT/'shared/shortcuts/selector.md', assets/'selector.md')
shutil.copyfile(ROOT/'shared/shortcuts/av.md', assets/'av.md')
assert (assets/'selector.md').read_bytes() == (ROOT/'shared/shortcuts/selector.md').read_bytes()
assert (assets/'av.md').read_bytes() == (ROOT/'shared/shortcuts/av.md').read_bytes()
(config/'agents').mkdir()
(config/'agents/verify.md').write_text('---\nmodel: fixture/classifier\nmode: subagent\n---\nFree classifier fixture.\n')
(config/'opencode.json').write_text(json.dumps({'model':'fixture/fixture','plugin':[str(plugin)],'provider':{'fixture':{'npm':'@ai-sdk/openai-compatible','options':{'baseURL':f'http://127.0.0.1:{provider.server_port}/v1','apiKey':'fixture'},'models':{'fixture':{'name':'fixture','limit':{'context':10000,'output':1000}},'classifier':{'name':'classifier','limit':{'context':10000,'output':1000}}}}}}))
env = dict(os.environ, HOME=str(work), XDG_CONFIG_HOME=str(work/'config'), XDG_DATA_HOME=str(work/'data'), XDG_CACHE_HOME=str(work/'cache'), XDG_STATE_HOME=str(work/'state'), MRCALL_KIT_HOME=str(work/'kit'), OPENCODE_DISABLE_MODELS_FETCH='true', OPENCODE_SERVER_PASSWORD='fixture')
for key in list(env):
    if key.endswith('_API_KEY') or key.endswith('_TOKEN'):
        env.pop(key)
sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
log = open(work/'native.log','w')
proc = subprocess.Popen([str(Path.home()/'.opencode/bin/opencode'),'serve','--hostname','127.0.0.1','--port',str(port),'--print-logs'],cwd=work,env=env,stdout=log,stderr=log)
def api(path, data=None):
    req=urllib.request.Request(f'http://127.0.0.1:{port}/api/'+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json','Authorization':'Basic '+base64.b64encode(b'opencode:fixture').decode()})
    return json.load(urllib.request.urlopen(req,timeout=3))
try:
    for _ in range(50):
        try:
            session=api('session',{'location':{'directory':str(work)}})
            break
        except Exception:
            if proc.poll() is not None: raise RuntimeError('native server exited')
            time.sleep(.1)
    else: raise RuntimeError('native server did not become ready')
    sid=session['data']['id']
    api('session/'+sid+'/prompt',{'text':request_text})
    end=time.monotonic()+(34 if mode=='timeout' else 8)
    while time.monotonic()<end:
        if mode=='positive' and any(is_continuation(r) for r in requests): break
        if mode=='timeout' and aborted.is_set(): break
        time.sleep(.1)
    (work/'requests.json').write_text(json.dumps(requests,indent=2))
    context=api('session/'+sid+'/context')['data']
    (work/'context.json').write_text(json.dumps(context,indent=2))
    selectors=[r for r in requests if is_selector(r)]
    if mode == 'short':
        assert len(draft_text) == 300
        parents = [r for r in requests if r.get('tools') and not is_continuation(r)]
        assert len(parents) == 1, f'Expected one parent generation; got {len(parents)}'
        answers = [m for m in context if m.get('type') == 'assistant']
        assert len(answers) == 1 and content_text(answers[0].get('content')) == draft_text
        assert not selectors, f'Expected zero selectors; got {len(selectors)}'
        assert not any(is_continuation(r) for r in requests), 'unexpected short av continuation'
        assert not any(m.get('metadata', {}).get('auto-av') is True for m in context)
        assert context[0]['text'] == request_text
        print('Native short callback passed; codepoints=300; selectors=0; av=0; parent=1; session='+sid)
        sys.exit(0)
    assert len(draft_text) == 301
    assert len(requests)>=2, f'Expected native generation and selector; received {len(requests)}'
    assert len(selectors)==1, f'Expected one selector, got {len(selectors)}'
    selector=selectors[0]
    assert not selector.get('tools'), 'selector inherited tools'
    selector_users=[m for m in selector['messages'] if m['role']=='user']
    assert len(selector_users)==1
    assert len(selector['messages'])==1 and selector['model']=='classifier'
    assert json.loads(content_text(selector_users[0]['content'])[len(policy_text)+2:])=={'assignment':request_text,'draft':draft_text}
    assert all('CANONICAL_AV_FIXTURE' not in json.dumps(r) for r in requests)
    continuations=[r for r in requests if is_continuation(r)]
    if mode=='positive':
        assert continuations, 'missing canonical continuation'
        owned=[m for m in context if m.get('metadata',{}).get('auto-av') is True]
        assert len(owned)==1, 'canonical continuation missing from original session'
        assert owned[0]['text']==expected_prompt, 'delivered canonical prompt differs from production wrapper'
        assert context[0]['text']==request_text, 'original user text changed'
        (work/'expected-prompt.txt').write_text(expected_prompt)
        (work/'delivered-prompt.txt').write_text(owned[0]['text'])
    else:
        assert not continuations, 'unexpected av continuation'
    if mode=='timeout': assert aborted.is_set(), 'native timeout did not close provider connection'
    print('Canonical source assets exact; stance body unchanged; delivered prompt exact; current user text preserved.')
    print('Native '+mode+' callback passed; selectors=1; av='+str(len(continuations))+'; provider_abort='+str(aborted.is_set())+'; session='+sid)
finally:
    proc.terminate()
    try: proc.wait(timeout=3)
    except subprocess.TimeoutExpired: proc.kill();proc.wait()
    provider.shutdown()
    log.close()
    print('Evidence: '+str(work))

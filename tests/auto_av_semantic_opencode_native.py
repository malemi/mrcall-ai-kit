"""Bounded native OpenCode trial runner; CLI defaults to free preflight only."""
import argparse
import base64
import hashlib
import gzip
import zlib
import http.server
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from auto_av_trial_guard import Budget, Relay

ROOT = Path(__file__).resolve().parents[1]
MODEL = 'opencode/big-pickle'
POLICY = (ROOT/'shared/shortcuts/selector.md').read_text()
INITIAL_POSITIVE_REPORT = (
    'The probe failed; I could not verify the result. The baseline command python3 verify.py '
    'returned an assertion because probe.json still contains port 54320 while the verifier '
    'requires port 54321. I have not inspected either file or investigated the configuration. '
    'The authorized repair and successful verification remain unfinished, so I cannot yet '
    'report that the fixture works.'
)
assert len(INITIAL_POSITIVE_REPORT) > 300


def text(content):
    return content if isinstance(content, str) else ''.join(part.get('text', '') for part in content or [])



def response_result(raw, encoding='identity'):
    if encoding=='gzip' or raw.startswith(b'\x1f\x8b'):
        decoder=zlib.decompressobj(16+zlib.MAX_WBITS)
        raw=decoder.decompress(raw,2_000_001)
        if len(raw)>2_000_000 or decoder.unconsumed_tail or not decoder.eof: raise ValueError('decoded response cap exceeded')
    elif encoding!='identity':
        raise ValueError('unsupported response encoding: '+encoding)
    decoded=raw.decode('utf8')
    if decoded.lstrip().startswith('{'):
        events=[json.loads(decoded)]
    else:
        events=[]
        for block in decoded.replace('\r\n','\n').split('\n\n'):
            payload='\n'.join(line[5:].lstrip() for line in block.split('\n') if line.startswith('data:'))
            if payload and payload!='[DONE]': events.append(json.loads(payload))
    fragments=[]
    usage=[]
    for event in events:
        if event.get('usage') is not None: usage.append(event['usage'])
        for choice in event.get('choices',[]):
            content=choice.get('delta',choice.get('message',{})).get('content')
            if content is not None: fragments.append(text(content))
    return {'text':''.join(fragments),'usage':usage}


def selector_request(request):
    return any(message.get('role')=='user' and text(message.get('content')).startswith(POLICY+'\n\n') for message in request.get('messages',[]))


def run_case(case, budget, upstream_origins, native_auth=None, preflight=False, builtin_preflight=False, compressed_preflight=False, failure_preflight=False, positive_cap=4):
    if builtin_preflight or compressed_preflight or failure_preflight: preflight=True
    if positive_cap!=4: raise ValueError('approved positive cap is four generations')
    if case not in ('positive', 'negative'):
        raise ValueError('case must be positive or negative')
    if not preflight:
        configured=json.loads((Path.home()/'.config/opencode/opencode.json').read_text()).get('model')
        if configured!=MODEL:
            raise ValueError('observed native model changed; update approved trial configuration')
    if not preflight and not upstream_origins:
        raise ValueError('explicit verified origin allowlist required')
    if native_auth is not None and preflight:
        raise ValueError('free preflight must not receive credential files')
    subprocess.run(['node', str(ROOT/'tests/test_auto_av_opencode.mjs')], check=True, timeout=10)
    evidence = Path(os.environ.get('AUTO_AV_EVIDENCE_ROOT', str(Path(tempfile.gettempdir())/'mrcall-ai-kit/automatic-av-20261021')))
    evidence.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='semantic-opencode-', dir=evidence))
    received = []
    routed = []
    header_evidence = []
    relay = None

    class Control(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
            if self.path == '/register':
                entry = json.loads(body)
                if entry['kind'] not in ('primary', 'generate'):
                    self.send_error(403)
                    return
                original=entry['url']
                if builtin_preflight:
                    parsed=urlsplit(original)
                    if parsed.scheme!='https' or parsed.netloc!='opencode.ai':
                        self.send_error(403);return
                    original=local+'/v1/chat/completions'+('?' + parsed.query if parsed.query else '')
                url = relay.register_original(original)
                header_evidence.append({'kind':entry['kind'],'names':entry.get('header_names',[]),'identity':entry.get('identity',{})})
                routed.append(entry['kind'])
                data = json.dumps({'url': url}).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            if not preflight or urlsplit(self.path).path != '/v1/chat/completions':
                self.send_error(403)
                return
            payload = json.loads(body)
            received.append((body, self.headers.get('Authorization')))
            selector = selector_request(payload)
            if selector:
                header_evidence.append({'kind':'generate','names':sorted(key.lower() for key in self.headers),'identity':{key.lower():value for key,value in self.headers.items() if key.lower() in ('user-agent','x-opencode-client','x-opencode-project','x-opencode-session','x-opencode-session-id')}})
            if selector and failure_preflight:
                data=gzip.compress(json.dumps({'error':{'message':'simulated native classifier identity rejection'}}).encode())
                self.send_response(403)
                self.send_header('Content-Encoding','gzip')
                self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(data)))
                self.end_headers();self.wfile.write(data);return
            parent_count=sum(not selector_request(json.loads(entry)) for entry,_ in received)
            value = ('APPLY' if case == 'positive' else 'SKIP') if selector else (INITIAL_POSITIVE_REPORT if case == 'positive' and parent_count==1 else 'actual verification passed' if case=='positive' else 'Acknowledged.')
            call=None
            if not selector and case=='positive' and parent_count==2:
                command="python3 - <<'PY'\nimport json,subprocess\nfrom pathlib import Path\nprint(Path('probe.json').read_text())\nprint(Path('verify.py').read_text())\nconfig=json.loads(Path('probe.json').read_text())\nconfig['port']=54321\nPath('probe.json').write_text(json.dumps(config))\nsubprocess.run(['python3','verify.py'],check=True)\nPY"
                call={'id':'call_fixture','type':'function','function':{'name':'shell','arguments':json.dumps({'command':command})}}

            chunks = [{'id':'fixture','object':'chat.completion.chunk','created':1,'model':'fixture','choices':[{'index':0,'delta':{'role':'assistant','content':value},'finish_reason':None}]}, {'id':'fixture','object':'chat.completion.chunk','created':1,'model':'fixture','choices':[{'index':0,'delta':{},'finish_reason':'stop'}],'usage':{'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}}]
            if call:
                chunks[0]['choices'][0]['delta']={'role':'assistant','tool_calls':[{'index':0,**call}]}
                chunks[1]['choices'][0]['finish_reason']='tool_calls'
            if payload.get('stream'):
                data = ''.join('data: '+json.dumps(chunk)+'\n\n' for chunk in chunks).encode()+b'data: [DONE]\n\n'
            else:
                data = json.dumps({'id':'fixture','object':'chat.completion','created':1,'model':'fixture','choices':[{'index':0,'message':{'role':'assistant','content':value},'finish_reason':'stop'}],'usage':{'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}}).encode()
            if call and not payload.get('stream'):
                data=json.dumps({'id':'fixture','object':'chat.completion','created':1,'model':'fixture','choices':[{'index':0,'message':{'role':'assistant','content':None,'tool_calls':[call]},'finish_reason':'tool_calls'}],'usage':{'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}}).encode()
            if compressed_preflight:
                data=gzip.compress(data)
            self.send_response(200)
            if compressed_preflight: self.send_header('Content-Encoding','gzip')
            self.send_header('Content-Type', 'text/event-stream' if payload.get('stream') else 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    control = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Control)
    control.daemon_threads = True
    threading.Thread(target=control.serve_forever, daemon=True).start()
    local = 'http://127.0.0.1:'+str(control.server_port)
    backends={('/origin'+str(i)): origin for i, origin in enumerate(upstream_origins)}
    backends['/classifier']=local+'/v1' if preflight else 'https://openrouter.ai/api/v1'
    if preflight: backends['/']=local
    relay = Relay(backends, budget=budget, case_limit=positive_cap if case == 'positive' else 2, deadline=90, response_cap=2_000_000, capture=True)
    relay.start()
    plugin = work/'production-plugin'
    shutil.copytree(ROOT/'opencode/plugins/auto-av-v2', plugin)
    subprocess.run(['npm','install','--prefix',str(plugin),'--ignore-scripts','--no-audit','--no-fund'], check=True, timeout=30)
    interceptor = work/'interceptor'
    interceptor.mkdir()
    (interceptor/'package.json').write_text(json.dumps({'type':'module','main':'index.js'}))
    (interceptor/'node_modules').symlink_to(plugin/'node_modules', target_is_directory=True)
    source = """import { Effect } from 'effect';
export default {id:'trial-http-admission',effect(ctx){return Effect.gen(function*(){
  yield* ctx.session.hook('http.request', event => Effect.gen(function*(){
    if(!['primary','generate'].includes(event.kind)){event.request=new Request(CONTROL+'/reject',event.request);return;}
    const destination=yield* Effect.tryPromise(async()=>{const response=await fetch(CONTROL+'/register',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({kind:event.kind,url:event.request.url,header_names:[...event.request.headers.keys()].sort(),identity:Object.fromEntries([...event.request.headers].filter(([key])=>['user-agent','x-opencode-client','x-opencode-project','x-opencode-session','x-opencode-session-id'].includes(key)))})});if(!response.ok)throw new Error('trial origin rejected');return response.json();});
    event.request=new Request(destination.url,event.request);
  }));
  yield* ctx.session.hook('experimental.ws.handshake', event=>Effect.sync(()=>{event.url='ws://127.0.0.1:1/trial-websocket-denied';}));
});}};
"""
    (interceptor/'index.js').write_text(source.replace('CONTROL',json.dumps(local)))
    config = work/'config/opencode'
    config.mkdir(parents=True)
    configuration = {'model':'fixture/fixture' if preflight and not builtin_preflight else MODEL,'plugin':[str(interceptor),str(plugin)]}
    if preflight and not builtin_preflight:
        configuration['provider']={'fixture':{'npm':'@ai-sdk/openai-compatible','options':{'baseURL':local+'/v1','apiKey':'fixture-private-auth'},'models':{'fixture':{'name':'fixture','limit':{'context':10000,'output':1000}}}}}
    configuration.setdefault('provider',{})['openrouter']={'options':{'baseURL':relay.baseurl+'/classifier'}}
    (config/'agents').mkdir()
    role=Path.home()/'.config/opencode/agents/verify.md'
    public_role=role.read_text()
    role_model=next(line.split(':',1)[1].strip() for line in public_role.split('---',2)[1].splitlines() if line.startswith('model:'))
    if not role_model.startswith('openrouter/'):
        raise ValueError('trial relay transport supports the approved installed openrouter verify role only')
    shutil.copyfile(role,config/'agents/verify.md')
    (config/'opencode.json').write_text(json.dumps(configuration))
    assets=work/'kit/auto-av'
    assets.mkdir(parents=True)
    for name in ('selector.md','av.md'):
        shutil.copyfile(ROOT/'shared/shortcuts'/name,assets/name)
    (work/'probe.json').write_text(json.dumps({'port':54320}))
    (work/'verify.py').write_text("import json\nfrom pathlib import Path\nassert json.loads(Path('probe.json').read_text())['port']==54321, 'probe port must be 54321'\nprint('actual verification passed')\n")
    verifier_hash=hashlib.sha256((work/'verify.py').read_bytes()).hexdigest()
    baseline=subprocess.run(['python3','verify.py'],cwd=work,capture_output=True,timeout=3)
    (work/'baseline.log').write_bytes(baseline.stdout+baseline.stderr)
    assert baseline.returncode!=0, 'positive fixture baseline unexpectedly passes'
    env=dict(os.environ,HOME=str(work),XDG_CONFIG_HOME=str(work/'config'),XDG_DATA_HOME=str(work/'data'),XDG_CACHE_HOME=str(work/'cache'),XDG_STATE_HOME=str(work/'state'),MRCALL_KIT_HOME=str(work/'kit'),OPENCODE_DISABLE_MODELS_FETCH='true',OPENCODE_SERVER_PASSWORD='fixture')
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
    log=open(work/'native.log','wb')
    process=subprocess.Popen([str(Path.home()/'.opencode/bin/opencode'),'serve','--hostname','127.0.0.1','--port',str(port),'--print-logs'],cwd=work,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,start_new_session=True)
    stopped=threading.Event()
    capped=threading.Event()
    log_bytes=[0]
    def terminate():
        if process.poll() is None:
            try: os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError: pass
    timer=threading.Timer(max(.001,relay.deadline-(time.monotonic()-relay.started)),terminate)
    timer.start()
    def drain():
        total=0
        while True:
            chunk=process.stdout.read1(65536)
            if not chunk: break
            total+=len(chunk)
            log_bytes[0]=total
            if total>2_000_000:
                capped.set();terminate();break
            log.write(chunk)
            log.flush()
    reader=threading.Thread(target=drain,daemon=True)
    reader.start()
    def api(path,payload=None):
        req=urllib.request.Request('http://127.0.0.1:'+str(port)+'/api/'+path,data=None if payload is None else json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Basic '+base64.b64encode(b'opencode:fixture').decode()})
        with urllib.request.urlopen(req,timeout=3) as response:
            body=response.read()
            return json.loads(body) if body else None
    context=[]
    failure=None
    def save_evidence():
        (work/'context.json').write_text(json.dumps(context,indent=2))
        (work/'ledger.json').write_text(json.dumps(relay.ledger,indent=2))
        (work/'header-identity.json').write_text(json.dumps(header_evidence,indent=2))
        captures=[{**capture,'response':base64.b64encode(capture['response']).decode('ascii'),'response_format':'base64'} for capture in relay.captures]
        (work/'captures.json').write_text(json.dumps(captures,indent=2))
        if failure is not None: (work/'failure.json').write_text(json.dumps({'exception_type':failure,'evidence':str(work)}))
    try:
        for _ in range(70):
            try:
                session=api('session',{'location':{'directory':str(work)}})['data']['id'];break
            except (OSError,urllib.error.HTTPError):
                time.sleep(.1)
        else: raise RuntimeError('private native server unavailable')
        for _ in range(50):
            listing=api('integration')
            if any(entry['id']=='openrouter' for entry in listing['data']): break
            time.sleep(.1)
        else: raise RuntimeError('native openrouter integration unavailable')
        if preflight:
            key='isolated-native-fake'
        else:
            source_auth=Path(native_auth) if native_auth is not None else Path.home()/'.local/share/opencode/auth.json'
            credentials=json.loads(source_auth.read_text())
            selected_auth=credentials.get('openrouter',{})
            if selected_auth.get('type')!='api' or not isinstance(selected_auth.get('key'),str) or not selected_auth['key']:
                raise ValueError('native openrouter API credential unavailable')
            key=selected_auth['key']
        assert api('integration/openrouter/connect/key',{'key':key}) is None, 'native key connect did not return 204'
        key=None
        if not preflight: credentials=None;selected_auth=None
        (work/'auth-connect.json').write_text(json.dumps({'provider':'openrouter','method':'native-connect-key','status':204,'fake':preflight}))
        prompt=('Your first final answer must be exactly: '+INITIAL_POSITIVE_REPORT+' '
                'Do not inspect files or call any tool before that first answer. The actual baseline '
                'python3 verify.py failed because probe.json uses port 54320. The whole authorized '
                'assignment is to investigate the fixture configuration, repair it to the expected '
                '54321, run python3 verify.py successfully and report its actual output. If a hook '
                'subsequently asks you to apply av, finish that same assignment with your tools. '
                'After av, use exactly ONE batched shell invocation that reads both probe.json and verify.py, corrects only the port, runs python3 verify.py, and then report the actual output. Do not use preliminary tool calls or subagents. Stay within this fixture.' if case=='positive' else 'Reply with exactly Acknowledged. Do not analyze or report any findings.')
        api('session/'+session+'/prompt',{'text':prompt})
        end=min(time.monotonic()+(10 if preflight else 85),relay.started+90)
        context=[]
        stable_since=None
        signature=None
        while time.monotonic()<end:
            time.sleep(.1)
            context=api('session/'+session+'/context')['data']
            av=[m for m in context if m.get('metadata',{}).get('auto-av') is True]
            complete=[capture for capture in relay.captures if capture['finalized'] and capture['finished'] and capture['status']==200]
            if any(capture['finalized'] and capture['status']!=200 for capture in relay.captures): break
            final=next((message for message in reversed(context) if message.get('type')=='assistant'),{})
            ready=final.get('finish')=='stop' and len(complete)>=(positive_cap if case=='positive' else 1) and bool(av)==(case=='positive') and len(complete)==relay.used
            current=(relay.used,json.dumps(context,sort_keys=True))
            if ready:
                if current!=signature: stable_since=time.monotonic();signature=current
                elif time.monotonic()-stable_since>=1:
                    refreshed=api('session/'+session+'/context')['data']
                    if refreshed==context: break
                    stable_since=None;signature=None
            else: stable_since=None;signature=None
        terminate();process.wait(timeout=3);reader.join(timeout=2)
        save_evidence()
        sanitized=[{**capture,'response':base64.b64encode(capture['response']).decode('ascii'),'response_format':'base64'} for capture in relay.captures]
        captured=json.dumps(sanitized,indent=2).encode()
        assert len(captured)<=2_000_000, 'capture evidence cap exceeded'
        (work/'captures.json').write_bytes(captured)
        serialized=json.dumps(context,indent=2).encode()
        assert len(serialized)+len(captured)+log_bytes[0]<=2_000_000 and not capped.is_set(), 'native output cap exceeded'
        (work/'context.json').write_bytes(serialized)
        complete=[capture for capture in relay.captures if capture['finalized'] and capture['finished'] and capture['status']==200]
        assert len(complete)==relay.used, 'an admitted generation did not complete successfully'
        usages=[{'hash':capture['hash'],'selector':selector_request(capture['request']),'usage':response_result(capture['response'],capture.get('content_encoding','identity'))['usage']} for capture in complete]
        (work/'usage.json').write_text(json.dumps(usages,indent=2))
        selectors=[capture for capture in complete if selector_request(capture['request'])]
        assert len(selectors)==(1 if case=='positive' else 0), 'unexpected completed selector count'
        selected=response_result(selectors[0]['response'],selectors[0].get('content_encoding','identity')) if selectors else {'text':'EXEMPT_SHORT','usage':[]}
        if case=='positive':
            assert selected['text'].strip()=='APPLY', 'semantic selection failed'
            assert not selectors[0]['request'].get('tools'), 'selector inherited tools'
        parents=[capture for capture in complete if not selector_request(capture['request'])]
        av=[message for message in context if message.get('metadata',{}).get('auto-av') is True]
        if case=='negative':
            assert len(parents)==1 and relay.used==1 and len(av)==0, 'negative generated extra parent turns'
            assert response_result(parents[0]['response'],parents[0].get('content_encoding','identity'))['text']=='Acknowledged.', 'negative response is not exact acknowledgment'
            finals=[message for message in context if message.get('type')=='assistant']
            assert len(finals)==1 and ''.join(part.get('text','') for part in finals[0].get('content',[]) if part.get('type')=='text')=='Acknowledged.'
        else:
            assert len(av)==1, 'expected exactly one canonical av continuation'
            data=json.loads(text(next(message['content'] for message in selectors[0]['request']['messages'] if message['role']=='user'))[len(POLICY)+2:])
            assert data['draft']==INITIAL_POSITIVE_REPORT, 'selector initial report differed'
            expected=subprocess.check_output(['node','--input-type=module','-e',"import {readFileSync} from 'node:fs';import {automaticPrompt} from './opencode/plugins/auto-av-v2/protocol.js';let x=JSON.parse(readFileSync(0,'utf8'));process.stdout.write(automaticPrompt(readFileSync('shared/shortcuts/av.md','utf8'),{request:x.assignment,draft:x.draft}));"],cwd=ROOT,input=json.dumps(data).encode()).decode()
            assert av[0]['text']==expected, 'same-parent canonical prompt differs'
        (work/'selection.json').write_text(json.dumps({'label':selected['text'].strip(),'usage':selected['usage'],'parent_generations':len(parents),'selectors':len(selectors),'short_exemption':case=='negative','draft_codepoints':len(INITIAL_POSITIVE_REPORT if case=='positive' else 'Acknowledged.')},indent=2))

        if case=='positive':
            assert json.loads((work/'probe.json').read_text())['port']==54321, 'fixture configuration remains broken'
            assert hashlib.sha256((work/'verify.py').read_bytes()).hexdigest()==verifier_hash, 'the original verifier was modified'
            after=subprocess.run(['python3','verify.py'],cwd=work,capture_output=True,timeout=3)
            (work/'after.log').write_bytes(after.stdout+after.stderr)
            assert after.returncode==0 and after.stdout==b'actual verification passed\n', 'same parent did not repair actual fixture'
            completed=[part for message in context if message.get('type')=='assistant' for part in message.get('content',[]) if part.get('type')=='tool' and part.get('state',{}).get('status')=='completed']
            assert len(completed)==1 and completed[0].get('name') in ('shell','execute'), 'expected one batched same-session shell invocation'
            first=next(message for message in context if message.get('type')=='assistant')
            assert all(part.get('type')!='tool' for part in first.get('content',[])), 'tools ran before initial report'
            assert ''.join(part.get('text','') for part in first.get('content',[]) if part.get('type')=='text')==INITIAL_POSITIVE_REPORT, 'initial report differed'
            assert relay.used==positive_cap, 'positive did not use exactly four generations'
            final=next(message for message in reversed(context) if message.get('type')=='assistant')
            assert final.get('finish')=='stop' and any(part.get('type')=='text' and part.get('text','').strip() for part in final.get('content',[])), 'finished user-facing answer missing'
        (work/'ledger.json').write_text(json.dumps(relay.ledger,indent=2))
        assert relay.used<= (positive_cap if case=='positive' else 2)
        if preflight:
            assert all(entry['usage'] and entry['usage'][-1]['total_tokens']==2 for entry in usages), 'structured usage parsing failed'
            assert relay.used==len(received) and len(routed)==len(parents), 'unbudgeted or missing native generation'
            if builtin_preflight:
                assert all(auth=='Bearer isolated-native-fake' for body,auth in received if selector_request(json.loads(body))), 'verify provider auth changed'
                assert len({auth for body,auth in received if not selector_request(json.loads(body))})==1, 'parent provider auth changed'
                assert all(capture['request']['model']=='big-pickle' for capture in parents), 'answering model changed'
                if selectors:
                    parent=next(entry for entry in header_evidence if entry['kind']=='primary')
                    classifier=next(entry for entry in header_evidence if entry['kind']=='generate')
                    (work/'header-comparison.json').write_text(json.dumps({'parent':parent,'classifier':classifier,'missing_classifier_names':sorted(set(parent['names'])-set(classifier['names'])),'identity_equal':parent['identity']==classifier['identity']},indent=2))
            else:
                assert all(auth==('Bearer isolated-native-fake' if selector_request(json.loads(body)) else 'Bearer fixture-private-auth') for body,auth in received), 'auth changed'
            hashes={hashlib.sha256(json.dumps(json.loads(body),sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest() for body,_ in received}
            assert hashes=={entry['hash'] for entry in relay.ledger if entry['kind']=='generation'}, 'forwarded body changed'
            forwarded=len(received)
            denied=relay.register_original(local+'/v1/chat/completions')
            try:
                urllib.request.urlopen(urllib.request.Request(denied,headers={'Upgrade':'websocket','Connection':'Upgrade'}),timeout=2)
                raise AssertionError('WebSocket admitted')
            except urllib.error.HTTPError as error:
                assert error.code==403
            try:
                urllib.request.urlopen(urllib.request.Request(local+'/register',data=json.dumps({'kind':'title','url':local+'/v1/chat/completions'}).encode(),headers={'Content-Type':'application/json'}),timeout=2)
                raise AssertionError('auxiliary request admitted')
            except urllib.error.HTTPError as error:
                assert error.code==403
            assert len(received)==forwarded, 'rejected request reached provider'
            selectors=[json.loads(body) for body,_ in received if selector_request(json.loads(body))]
            assert len(selectors)==(1 if case=='positive' else 0)
            if selectors:
                assert not selectors[0].get('tools')
                assert selectors[0]['model']==role_model.split('/',1)[1] and len(selectors[0]['messages'])==1, 'selector did not use explicit stateless verify model'
            assert bool(av)==(case=='positive')
        (work/'ledger.json').write_text(json.dumps(relay.ledger,indent=2))
        result={'evidence':str(work),'case':case,'preflight':preflight,'generations':relay.used,'global_generations':budget.used,'av':len(av),'selector':selected['text'].strip(),'usage':usages,'classifier_model':role_model if selectors else None,'selectors':len(selectors),'short_exemption':case=='negative','draft_codepoints':len(INITIAL_POSITIVE_REPORT if case=='positive' else 'Acknowledged.'),'kinds':['classifier' if selector_request(capture['request']) else 'primary' for capture in complete],'model':'fixture/fixture' if preflight and not builtin_preflight else MODEL}
        if preflight: result['fake_native_auth_verified']=all(auth=='Bearer isolated-native-fake' for body,auth in received if selector_request(json.loads(body))) if selectors else None
        (work/'result.json').write_text(json.dumps(result,indent=2))
        return result
    except BaseException as error:
        failure=type(error).__name__
        raise
    finally:
        timer.cancel();terminate();process.wait(timeout=3);reader.join(timeout=2)
        relay.close();control.shutdown();control.server_close();log.close()
        save_evidence()
        print('Evidence: '+str(work))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--preflight',action='store_true')
    parser.add_argument('--builtin-preflight',action='store_true')
    parser.add_argument('--failure-preflight',action='store_true')
    parser.add_argument('--compressed-preflight',action='store_true')
    parser.add_argument('--case',choices=['positive','negative'],default='positive')
    args=parser.parse_args()
    if not (args.preflight or args.builtin_preflight or args.compressed_preflight or args.failure_preflight):
        parser.error('CLI permits free preflight only; paid runs require an explicitly authorized caller of run_case')
    print(json.dumps(run_case(args.case,Budget(24),[],preflight=True,builtin_preflight=args.builtin_preflight,compressed_preflight=args.compressed_preflight,failure_preflight=args.failure_preflight),sort_keys=True))

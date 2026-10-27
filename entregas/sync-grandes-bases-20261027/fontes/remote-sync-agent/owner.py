import hashlib
import hmac
import json
import os
import queue
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

_IPC_CONTRACT = json.loads(Path(__file__).with_name("ipc_contract.json").read_text(encoding="utf-8"))
PIPE_NAME = rf"\\.\pipe\{_IPC_CONTRACT['pipe_name']}"
PROTOCOL_VERSION = int(_IPC_CONTRACT["protocol_version"])
MAX_MESSAGE = 65536
VALID_COMMANDS = {"ping","status","start","stop","restart","pause","resume","sync-now","diagnose","reload-config","shutdown"}

def connect_named_pipe(win32pipe, pywintypes, pipe):
    """Bloqueia até conectar; ERROR_PIPE_CONNECTED já representa sucesso."""
    try:
        return win32pipe.ConnectNamedPipe(pipe,None),0
    except pywintypes.error as exc:
        winerror=getattr(exc,"winerror",None)
        if winerror==535:
            return None,winerror
        raise

def _auth_text(message):
    payload = json.dumps(message.get("payload") or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "|".join([str(message.get("version")),str(message.get("request_id")),str(message.get("timestamp")),str(message.get("nonce")),str(message.get("command")),payload])

class RequestAuthenticator:
    def __init__(self, secret, max_age_seconds=30): self.secret=secret.encode(); self.max_age=max_age_seconds; self.nonces={}; self.lock=threading.Lock()
    def sign(self,message): return hmac.new(self.secret,_auth_text(message).encode(),hashlib.sha256).hexdigest()
    def validate(self,message):
        if message.get("version")!=PROTOCOL_VERSION: return False,"IPC_VERSION_UNSUPPORTED"
        if message.get("command") not in VALID_COMMANDS: return False,"IPC_COMMAND_UNKNOWN"
        try: timestamp=float(message["timestamp"])
        except (KeyError,TypeError,ValueError): return False,"IPC_TIMESTAMP_INVALID"
        if abs(time.time()-timestamp)>self.max_age: return False,"IPC_REQUEST_EXPIRED"
        nonce=str(message.get("nonce") or "")
        if len(nonce)<16: return False,"IPC_NONCE_INVALID"
        expected=self.sign(message)
        if not hmac.compare_digest(expected,str(message.get("authentication") or "")): return False,"IPC_AUTH_FAILED"
        with self.lock:
            cutoff=time.time()-self.max_age; self.nonces={n:t for n,t in self.nonces.items() if t>=cutoff}
            if nonce in self.nonces: return False,"IPC_REPLAY_REJECTED"
            self.nonces[nonce]=time.time()
        return True,"IPC_AUTHENTICATED"

class AgentOwner:
    STATES={"STARTING","IDLE","SYNCING","WRITING","PAUSED","DIAGNOSING","RELOADING_CONFIG","STOPPING","STOPPED","ERROR"}
    def __init__(self,sync_callback,diagnose_callback,reload_callback,owner_type="desktop",service_mode=False,interval_minutes=5,identity=None,writeback_callback=None,writeback_interval=15):
        self.sync_callback=sync_callback;self.diagnose_callback=diagnose_callback;self.reload_callback=reload_callback
        self.owner_type=owner_type;self.service_mode=service_mode;self.interval_minutes=interval_minutes
        self.pid=os.getpid();self.instance_id=(identity or str(uuid.uuid4()))[:8];self.session_id=str(uuid.uuid4());self.loop_id=f"loop-{uuid.uuid4().hex[:8]}"
        self.state="STARTING";self.last_sync_at=None;self.next_sync_at=None;self.last_result=None;self.last_error_code=None;self.last_diagnostic=None;self.pending_command=None;self.current_table=None;self.records_processed=0
        self.commands=queue.Queue();self.stop_event=threading.Event();self.worker=None;self.lock=threading.RLock();self.events=[]
        self.writeback_callback=writeback_callback;self.writeback_interval=writeback_interval
        self.last_writeback_at=None;self.last_writeback_result=None
        self.sync_reserved=False;self.pause_requested=threading.Event();self.sync_progress={}
    def process_identity(self): return {"pid":self.pid,"instance_id":self.instance_id,"session_id":self.session_id,"mode":"service" if self.service_mode else "desktop","start_reason":"startup","service_mode":self.service_mode,"owner_type":self.owner_type,"loop_id":self.loop_id}
    def status(self):
        with self.lock:return {"owner":self.owner_type,"pid":self.pid,"instance_id":self.instance_id,"session_id":self.session_id,"state":self.state,"service_mode":self.service_mode,"loop_id":self.loop_id,"last_sync_at":self.last_sync_at,"next_sync_at":self.next_sync_at,"last_result":self.last_result,"last_diagnostic":self.last_diagnostic,"pending_command":self.pending_command,"current_table":self.current_table,"records_processed":self.records_processed,"last_error_code":self.last_error_code,"sync_progress":dict(self.sync_progress),"last_writeback_at":self.last_writeback_at,"last_writeback_result":self.last_writeback_result,"events":self.events[-20:]}
    def emit(self,event,**data):
        item={"event":event,"at":datetime.now().isoformat(),**data};self.events.append(item);self.events=self.events[-100:]
    def progress(self,event,table=None,records=0,**data):
        with self.lock:
            self.current_table=table
            if "progress" in data:
                self.sync_progress=dict(data["progress"])
                self.records_processed=int(self.sync_progress.get("sent",0))
            if records and not self.sync_progress:self.records_processed+=int(records)
            event_data=dict(data)
            if "progress" in event_data:
                event_data["progress"]={key:self.sync_progress.get(key) for key in ("phase","mode","percent","verified","sent","total")}
            self.emit(event,table=table,records=records,**event_data)
    def submit(self,command,payload=None):
        with self.lock:
            if command=="ping": return True,"PONG",{"protocol_version":PROTOCOL_VERSION,"pid":self.pid,"instance_id":self.instance_id,"owner":self.owner_type}
            if command=="status": return True,"STATUS_OK",self.status()
            if command=="sync-now":
                if self.state=="SYNCING" or self.sync_reserved: return False,"SYNC_ALREADY_RUNNING",self.status()
                if self.state in {"WRITING","DIAGNOSING","RELOADING_CONFIG"}: return False,"OWNER_BUSY",self.status()
                if (self.state=="PAUSED" or self.pause_requested.is_set()) and self.pending_command not in {"resume","start","restart"}: return False,"OWNER_PAUSED",self.status()
                self.sync_reserved=True
            if command=="pause": self.pause_requested.set()
            if command=="diagnose" and self.state in {"SYNCING","WRITING","DIAGNOSING"}: return False,"OWNER_BUSY",self.status()
            if command in {"pause","resume","reload-config","sync-now","diagnose","shutdown","stop","start","restart"}:
                self.commands.put((command,payload or {}));self.pending_command=command;return True,"COMMAND_ACCEPTED",self.status()
            return False,"COMMAND_REJECTED",self.status()
    def start(self):
        if self.worker and self.worker.is_alive():return
        self.worker=threading.Thread(target=self._run,name="pigo-owner",daemon=True);self.worker.start()
    def _sync(self,reason):
        with self.lock:
            if reason in {"schedule","writeback"} and (self.sync_reserved or self.pause_requested.is_set()):
                return False
            self.state="SYNCING";self.sync_reserved=True;self.records_processed=0;self.current_table=None
            self.next_sync_at=None;self.emit("sync.started",reason=reason)
        try:
            ok=bool(self.sync_callback())
            if ok:self.last_sync_at=datetime.now().isoformat()
            self.last_result="success" if ok else "paused" if self.pause_requested.is_set() else "failed"
            self.last_error_code=None if ok or self.pause_requested.is_set() else "SYNC_FAILED"
            self.emit("sync.completed" if ok else "sync.paused" if self.pause_requested.is_set() else "sync.failed",success=ok)
        except Exception as exc:
            self.last_result="failed";self.last_error_code=type(exc).__name__;self.emit("sync.failed",code=type(exc).__name__)
        finally:
            with self.lock:
                self.current_table=None;self.sync_reserved=False
                self.state="PAUSED" if self.pause_requested.is_set() else "IDLE"
                self.next_sync_at=None if self.pause_requested.is_set() else (datetime.now()+timedelta(minutes=self.interval_minutes)).isoformat()
    def _run(self):
        self.state="IDLE";self.next_sync_at=(datetime.now()+timedelta(minutes=self.interval_minutes)).isoformat();next_run=time.monotonic()+self.interval_minutes*60
        next_writeback=time.monotonic()+self.writeback_interval
        while not self.stop_event.is_set():
            deadline=min(next_run,next_writeback) if self.writeback_callback else next_run
            timeout=max(0.05,min(1,deadline-time.monotonic()))
            try:command,payload=self.commands.get(timeout=timeout)
            except queue.Empty:
                if self.writeback_callback and time.monotonic()>=next_writeback:
                    if self.state=="IDLE":
                        self.state="WRITING"
                        try:
                            outcome=self.writeback_callback();changed=outcome is True
                            self.last_writeback_at=datetime.now().isoformat();self.last_writeback_result="failed" if outcome is None else "changed" if changed else "idle"
                            self.state="IDLE"
                            if changed:self._sync("writeback");next_run=time.monotonic()+self.interval_minutes*60
                        except Exception as exc:
                            self.last_writeback_result="failed";self.emit("writeback.failed",code=type(exc).__name__);self.state="IDLE"
                    next_writeback=time.monotonic()+self.writeback_interval
                if time.monotonic()>=next_run and self.state=="IDLE":self._sync("schedule");next_run=time.monotonic()+self.interval_minutes*60
                continue
            self.pending_command=None
            if command=="sync-now":
                if self.state=="IDLE" and not self.pause_requested.is_set():self._sync("ipc");next_run=time.monotonic()+self.interval_minutes*60
                else:self.sync_reserved=False
            elif command=="pause":self.state="PAUSED";self.next_sync_at=None
            elif command in {"resume","start"}:
                self.pause_requested.clear();self.state="IDLE";next_run=time.monotonic()+self.interval_minutes*60
                self.next_sync_at=(datetime.now()+timedelta(minutes=self.interval_minutes)).isoformat()
            elif command=="diagnose":
                self.state="DIAGNOSING"
                try:
                    result=self.diagnose_callback()
                    self.last_diagnostic=result if isinstance(result,dict) else {"success":bool(result),"code":"DIAGNOSTIC_COMPLETED" if result else "DIAGNOSTIC_FAILED"}
                    self.last_result="success" if self.last_diagnostic.get("success") else "failed";self.last_error_code=None if self.last_result=="success" else self.last_diagnostic.get("code");self.emit("diagnostic.completed",success=self.last_result=="success",code=self.last_diagnostic.get("code"))
                except Exception as exc:self.last_error_code=type(exc).__name__;self.last_result="failed"
                self.state="PAUSED" if self.pause_requested.is_set() else "IDLE"
            elif command=="reload-config":
                self.state="RELOADING_CONFIG"
                try:
                    new_interval=self.reload_callback()
                    if new_interval:self.interval_minutes=int(new_interval);next_run=time.monotonic()+self.interval_minutes*60
                    self.emit("config.reloaded",success=True);self.state="PAUSED" if self.pause_requested.is_set() else "IDLE"
                except Exception as exc:self.last_error_code=type(exc).__name__;self.emit("config.reloaded",success=False);self.state="ERROR"
            elif command in {"stop","shutdown"}:self.state="STOPPING";self.stop_event.set()
            elif command=="restart":
                self.pause_requested.clear();self.state="IDLE";next_run=time.monotonic()+self.interval_minutes*60
                self.next_sync_at=(datetime.now()+timedelta(minutes=self.interval_minutes)).isoformat()
        self.state="STOPPED"

class NamedPipeServer:
    def __init__(self,owner,secret,pipe_name=PIPE_NAME,acl_mode="user"):
        self.owner=owner;self.auth=RequestAuthenticator(secret);self.pipe_name=pipe_name;self.acl_mode=acl_mode
        self.thread=None;self.stopped=threading.Event();self.ready=threading.Event();self.startup_error=None;self.modules=None
        self.instance_count=0
    def start(self):
        if os.name!="nt":return
        print("[IPC] server_starting=true", flush=True)
        print(f"[IPC] pipe_name={self.pipe_name.rsplit(chr(92), 1)[-1]}", flush=True)
        print(f"[IPC_SERVER] pipe_name={self.pipe_name.rsplit(chr(92), 1)[-1]}", flush=True)
        print(f"[IPC_SERVER] full_pipe_path={self.pipe_name}", flush=True)
        print(f"[IPC_SERVER] pipe_acl_mode={self.acl_mode}", flush=True)
        print("[IPC_SERVER] flags=PIPE_ACCESS_DUPLEX|PIPE_TYPE_MESSAGE|PIPE_READMODE_MESSAGE|PIPE_WAIT max_instances=PIPE_UNLIMITED_INSTANCES", flush=True)
        try:
            import pywintypes,win32file,win32pipe,win32security
            self.modules=(pywintypes,win32file,win32pipe,win32security)
        except ImportError as exc:
            print(f"[IPC] dependency_available=false module={getattr(exc, 'name', 'unknown')}", flush=True)
            raise RuntimeError("IPC_DEPENDENCY_MISSING") from exc
        self.thread=threading.Thread(target=self._serve,name="pigo-ipc",daemon=True);self.thread.start()
        print("[IPC] accept_loop_started=true", flush=True)
        if not self.ready.wait(5):
            raise RuntimeError("IPC_SERVER_START_TIMEOUT")
        if self.startup_error:
            raise RuntimeError(f"IPC_SERVER_START_FAILED:{type(self.startup_error).__name__}") from self.startup_error
        print("[IPC] server_ready=true", flush=True)
        print("[IPC] server_started=true", flush=True)
    def _serve(self):
        pywintypes,win32file,win32pipe,win32security=self.modules
        security=pywintypes.SECURITY_ATTRIBUTES()
        security.SECURITY_DESCRIPTOR=win32security.ConvertStringSecurityDescriptorToSecurityDescriptor("D:P(A;;GA;;;SY)(A;;GA;;;BA)(A;;GRGW;;;AU)",win32security.SDDL_REVISION_1)
        while not self.stopped.is_set():
            pipe=None
            connected=False
            created_at=time.monotonic()
            self.instance_count+=1
            instance=self.instance_count
            try:
                print(f"[IPC] instance={instance} create_requested=true", flush=True)
                pipe=win32pipe.CreateNamedPipe(self.pipe_name,win32pipe.PIPE_ACCESS_DUPLEX,win32pipe.PIPE_TYPE_MESSAGE|win32pipe.PIPE_READMODE_MESSAGE|win32pipe.PIPE_WAIT,win32pipe.PIPE_UNLIMITED_INSTANCES,MAX_MESSAGE,MAX_MESSAGE,1000,security)
                print(f"[IPC] instance={instance} handle_created=true pipe_created=true", flush=True)
                print(f"[IPC] instance={instance} waiting_for_client=true", flush=True)
                self.ready.set()
                wait_started=time.monotonic()
                try:
                    result,winerror=connect_named_pipe(win32pipe,pywintypes,pipe)
                    connected=True
                    print(f"[IPC] instance={instance} connect_result={result!r} winerror={winerror} wait_ms={int((time.monotonic()-wait_started)*1000)}", flush=True)
                except pywintypes.error as exc:
                    winerror=getattr(exc,"winerror",None)
                    print(f"[IPC] instance={instance} connect_result=exception winerror={winerror} error={type(exc).__name__} wait_ms={int((time.monotonic()-wait_started)*1000)}", flush=True)
                    raise
                print(f"[IPC] instance={instance} client_connected={str(connected).lower()}", flush=True)
                _,raw=win32file.ReadFile(pipe,MAX_MESSAGE);message=json.loads(bytes(raw).decode())
                command=str(message.get("command") or "unknown")
                print(f"[IPC] instance={instance} request_received=true command={command}", flush=True)
                valid,code=self.auth.validate(message)
                if valid:success,code,data=self.owner.submit(message["command"],message.get("payload"))
                else:success,data=False,{}
                response={"version":1,"success":success,"code":code,"request_id":message.get("request_id"),"owner":self.owner.owner_type,"state":self.owner.state,"data":data}
                win32file.WriteFile(pipe,json.dumps(response,separators=(",", ":")).encode())
                win32file.FlushFileBuffers(pipe)
                print(f"[IPC] instance={instance} response_sent=true code={code}", flush=True)
            except Exception as exc:
                if not self.ready.is_set():
                    self.startup_error=exc;self.ready.set()
                    print(f"[IPC] server_started=false error={type(exc).__name__}", flush=True)
                    return
                winerror=getattr(exc,"winerror",None)
                known={231:"ERROR_PIPE_BUSY",233:"ERROR_PIPE_NOT_CONNECTED",232:"ERROR_NO_DATA",535:"ERROR_PIPE_CONNECTED",536:"ERROR_PIPE_LISTENING",109:"ERROR_BROKEN_PIPE"}
                print(f"[IPC] instance={instance} request_failed=true error={type(exc).__name__} winerror={winerror} winerror_name={known.get(winerror,'UNKNOWN')}", flush=True)
                time.sleep(.25)
            finally:
                if pipe is not None:
                    print(f"[IPC] instance={instance} closing=true", flush=True)
                    try:win32pipe.DisconnectNamedPipe(pipe)
                    except Exception:pass
                    win32file.CloseHandle(pipe)
                    print(f"[IPC] instance={instance} closed=true lifetime_ms={int((time.monotonic()-created_at)*1000)}", flush=True)

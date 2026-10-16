import os
import threading
import time
import unittest
import uuid
from owner import AgentOwner, RequestAuthenticator, connect_named_pipe

class OwnerTests(unittest.TestCase):
    def test_connect_named_pipe_accepts_error_pipe_connected(self):
        class PipeError(Exception):
            def __init__(self, winerror): self.winerror=winerror
        class PipeApi:
            @staticmethod
            def ConnectNamedPipe(_pipe, _overlapped): raise PipeError(535)
        class Types: error=PipeError
        self.assertEqual(connect_named_pipe(PipeApi,Types,object()),(None,535))

    def test_connect_named_pipe_does_not_mask_listening_or_no_data(self):
        class PipeError(Exception):
            def __init__(self, winerror): self.winerror=winerror
        class Types: error=PipeError
        for code in (536,232,109,233):
            class PipeApi:
                @staticmethod
                def ConnectNamedPipe(_pipe, _overlapped): raise PipeError(code)
            with self.assertRaises(PipeError) as raised:
                connect_named_pipe(PipeApi,Types,object())
            self.assertEqual(raised.exception.winerror,code)

    def test_diagnostic_preserves_structured_authentication_result(self):
        owner = AgentOwner(
            lambda: True,
            lambda: {"success": False, "authenticated": False, "tenant_resolved": False, "code": "INVALID_API_KEY", "retryable": False},
            lambda: True,
        )
        owner.start()
        owner.submit("diagnose")
        for _ in range(100):
            if owner.status()["last_diagnostic"]:
                break
            time.sleep(0.01)
        status = owner.status()
        self.assertEqual(status["last_diagnostic"]["code"], "INVALID_API_KEY")
        self.assertEqual(status["last_error_code"], "INVALID_API_KEY")

    def message(self, auth, command="status", nonce=None):
        value={"version":1,"request_id":str(uuid.uuid4()),"timestamp":time.time(),"nonce":nonce or uuid.uuid4().hex,"command":command,"payload":{}}
        value["authentication"]=auth.sign(value);return value

    def test_authentication_and_replay_rejection(self):
        auth=RequestAuthenticator("local-secret")
        message=self.message(auth)
        self.assertTrue(auth.validate(message)[0])
        self.assertEqual(auth.validate(message),(False,"IPC_REPLAY_REJECTED"))
        message=self.message(auth);message["authentication"]="wrong"
        self.assertEqual(auth.validate(message),(False,"IPC_AUTH_FAILED"))

    def test_sync_runs_inside_owner_process_and_rejects_concurrent_cycle(self):
        calls=[]
        owner=AgentOwner(lambda:calls.append((os.getpid(),threading.current_thread().name)) or True,lambda:True,lambda:True,interval_minutes=60)
        owner.start();ok,code,_=owner.submit("sync-now")
        self.assertTrue(ok);self.assertEqual(code,"COMMAND_ACCEPTED")
        end=time.time()+2
        while not calls and time.time()<end:time.sleep(.01)
        self.assertEqual(calls[0][0],os.getpid())
        owner.state="SYNCING"
        self.assertEqual(owner.submit("sync-now")[1],"SYNC_ALREADY_RUNNING")
        owner.submit("shutdown");owner.worker.join(2)

if __name__=="__main__":unittest.main()

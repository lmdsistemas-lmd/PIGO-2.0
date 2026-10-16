"""Windows Service host for the existing Remote Sync agent."""
import os
import subprocess
import sys
import time
from pathlib import Path

try:
    import servicemanager
    import win32event
    import win32service
    import win32serviceutil
except ImportError as exc:
    raise SystemExit("Instale pywin32 para registrar o servico Windows.") from exc

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("PROGRAMDATA", "C:/ProgramData")) / "PIGO Remote Sync"

class PigoRemoteSyncService(win32serviceutil.ServiceFramework):
    _svc_name_ = "PIGORemoteSync"
    _svc_display_name_ = "PIGO Remote Sync Service"
    _svc_description_ = "Sincroniza o ERP Firebird com o PIGO em segundo plano."

    def __init__(self, args):
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.process = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        if self.process:
            self.process.terminate()
        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self):
        servicemanager.LogInfoMsg("PIGO Remote Sync iniciado")
        env = {**os.environ, "PYTHONUNBUFFERED": "1", "PIGO_REMOTE_SYNC_DATA_DIR": str(DATA_DIR), "PIGO_SERVICE_MODE": "true", "PIGO_OWNER_TYPE": "service"}
        restart_delays = [2, 5, 15, 30]
        failures = 0
        while win32event.WaitForSingleObject(self.stop_event, 0) != win32event.WAIT_OBJECT_0:
            started = time.monotonic()
            launcher = "import runpy,sys;sys.path.insert(0,sys.argv.pop(1));runpy.run_path(sys.argv.pop(1),run_name='__main__')"
            self.process = subprocess.Popen(
                [sys.executable, "-c", launcher, str(ROOT), str(ROOT / "agent.py")], cwd=ROOT, env=env,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            while self.process.poll() is None:
                if win32event.WaitForSingleObject(self.stop_event, 1000) == win32event.WAIT_OBJECT_0:
                    self.process.terminate()
                    return
            if time.monotonic() - started > 60:
                failures = 0
            if failures >= len(restart_delays):
                servicemanager.LogErrorMsg("PIGO Remote Sync bloqueado apos cinco falhas consecutivas")
                return
            delay = restart_delays[failures]
            failures += 1
            servicemanager.LogWarningMsg(f"PIGO Remote Sync reinicio={failures} delay={delay}s exit={self.process.returncode}")
            if win32event.WaitForSingleObject(self.stop_event, delay * 1000) == win32event.WAIT_OBJECT_0:
                return

if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(PigoRemoteSyncService)

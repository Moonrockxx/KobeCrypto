import os, sys, atexit, time, signal

LOCK_PATH = "/tmp/kobe_runner.lock"

def _pid_alive(pid:int)->bool:
    if pid<=0: return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but no permission; treat as alive
        return True

def acquire_lock():
    if os.path.exists(LOCK_PATH):
        try:
            with open(LOCK_PATH, "r") as f:
                pid = int((f.read() or "0").strip())
        except Exception:
            pid = 0
        if _pid_alive(pid):
            print(f"[runner] lock actif: {LOCK_PATH} par PID {pid}", flush=True)
            sys.exit(2)
    with open(LOCK_PATH, "w") as f:
        f.write(str(os.getpid()))
    print(f"[runner] lock acquis: {LOCK_PATH}", flush=True)

def release_lock():
    try:
        if os.path.exists(LOCK_PATH):
            os.remove(LOCK_PATH)
            print(f"[runner] lock libéré: {LOCK_PATH}", flush=True)
    except Exception as e:
        print(f"[runner] lock cleanup error: {e}", flush=True)

def setup_lock_lifecycle():
    acquire_lock()
    atexit.register(release_lock)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: sys.exit(0))

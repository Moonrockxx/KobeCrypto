import os, sys, time, atexit, signal, json
import urllib.request
from datetime import datetime, timezone

LOCK_PATH = "/tmp/kobe_runner.lock"
DEFAULT_SCAN_SEC = int(os.getenv("SCAN_INTERVAL_SEC", "600"))  # 10 min par défaut
HEARTBEAT_SEC = int(os.getenv("HEARTBEAT_SEC", "3600"))        # 60 min par défaut

def load_env_file(path: str):
    if not os.path.isfile(path):
        return
    with open(path, "r") as f:
        for line in f:
            line=line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k,v = line.split("=",1)
            os.environ.setdefault(k.strip(), v.strip())

def send_telegram(text: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat  = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        return False, "TELEGRAM non configuré"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({"chat_id": chat, "text": text}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return True, resp.read().decode()
    except Exception as e:
        return False, str(e)

def _pid_alive(pid:int)->bool:
    if pid<=0: return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # process existe mais non autorisé -> on le considère vivant

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

def now_utc_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def align_next_tick(interval_sec:int):
    now = time.time()
    return now + (interval_sec - (int(now) % interval_sec))

def on_exit(msg="runner stop"):
    send_telegram(f"🛑 {msg} — {now_utc_str()}")
    release_lock()

def main():
    # Charger secrets Telegram si présents
    load_env_file(".secrets/kobe/telegram.env")

    acquire_lock()
    atexit.register(on_exit)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: sys.exit(0))

    ok, _ = send_telegram(f"🚀 runner start — {now_utc_str()}")
    if not ok:
        print("[runner] Telegram non configuré ou erreur d’envoi", flush=True)

    last_heartbeat = 0.0
    interval = max(300, DEFAULT_SCAN_SEC)  # min 5 min
    once = "--once" in sys.argv

    while True:
        print(f"[runner] tick @ {now_utc_str()} (interval={interval}s)", flush=True)

        now = time.time()
        if now - last_heartbeat >= HEARTBEAT_SEC:
            send_telegram("💓 Runner OK — heartbeat")
            last_heartbeat = now

        if once:
            break

        wake = align_next_tick(interval)
        time.sleep(max(0, wake - time.time()))

    return 0

if __name__ == "__main__":
    sys.exit(main())

import os, subprocess, sys, datetime

def load_env_file(p):
    if not os.path.exists(p): return
    with open(p) as f:
        for line in f:
            line=line.strip()
            if not line or line.startswith("#") or "=" not in line: 
                continue
            k,v=line.split("=",1)
            os.environ.setdefault(k.strip(), v.strip())

# Charger secrets si présents (ne casse pas si absents)
load_env_file(".secrets/kobe/telegram.env")
load_env_file(".secrets/kobe/deepseek.env")

def run_once():
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}] scheduler_run: START 1-cycle")
    # Health + un cycle de schedule
    subprocess.run([sys.executable, "-m", "kobe.cli.health_v2"], check=False)
    subprocess.run([sys.executable, "-m", "kobe.cli.schedule", "--once"], check=False)
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}] scheduler_run: END 1-cycle")

if __name__ == "__main__":
    run_once()

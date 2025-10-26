import subprocess, sys, yaml, json, os

def load_cfg():
    with open("config.yaml","r",encoding="utf-8") as f:
        return yaml.safe_load(f)

def is_testnet(cfg):
    # Garde prudente: tout sauf 'LIVE' est considéré non-live
    mode = str(cfg.get("mode","TESTNET")).upper()
    return mode != "LIVE"

def main():
    # 1) run scheduler normal (exactement comme d'habitude)
    print("▶︎ Run scheduler --once")
    r = subprocess.run([sys.executable, "-m", "kobe.cli.schedule", "--once"],
                       capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr)

    # 2) si flag actif ET en testnet -> envoyer une proposition prudente
    try:
        cfg = load_cfg()
    except Exception as e:
        print(f"⚠️ Impossible de lire config.yaml: {e}")
        sys.exit(1)

    flag = bool(cfg.get("demo_signal", False))
    if not flag:
        print("ℹ️ demo_signal désactivé — fin.")
        sys.exit(0)

    if not is_testnet(cfg):
        print("ℹ️ Mode LIVE détecté — demo_signal bloqué par sécurité.")
        sys.exit(0)

    # 3) Tir contrôlé (réutilise le script déjà validé)
    print("▶︎ demo_signal actif (TESTNET) — envoi d'une proposition prudente…")
    r2 = subprocess.run([sys.executable, "scripts/demo_signal.py"],
                        capture_output=True, text=True)
    if r2.returncode != 0:
        print("❌ demo_signal a échoué:")
        sys.stdout.write(r2.stdout)
        sys.stderr.write(r2.stderr)
        sys.exit(r2.returncode)
    print("✅ demo_signal envoyé.")
    sys.exit(0)

if __name__ == "__main__":
    main()

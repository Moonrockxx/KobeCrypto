
from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime
import subprocess, pytz, yaml, os

HOURS_START = 7
HOURS_END   = 21

def within_hours_utc(start=HOURS_START, end=HOURS_END):
    h = datetime.utcnow().hour
    return start <= h <= end

def job():
    utc_now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    if not within_hours_utc():
        print(f"[{utc_now} UTC] ⏭️  En dehors de {HOURS_START}–{HOURS_END} UTC — skip.")
        return
    print(f"[{utc_now} UTC] ▶︎ Running kobe.cli.schedule_demo ...")
    subprocess.run(["python", "-m", "kobe.cli.schedule_demo"], check=False)

if __name__ == "__main__":
    cfg = yaml.safe_load(open("config.yaml","r",encoding="utf-8"))
    interval = cfg.get("scheduler",{}).get("interval_minutes", 15)
    print(f"Scheduler actif toutes les {interval} min, {HOURS_START}–{HOURS_END} UTC (TESTNET mode)")

    scheduler = BlockingScheduler(
        timezone=pytz.UTC,
        job_defaults={
            "coalesce": True,            # fusion des déclenchements en retard en un seul
            "max_instances": 1,          # pas de chevauchement
            "misfire_grace_time": 300,   # 5 min de grâce si sortie de veille
        },
    )
    scheduler.add_job("kobe.scheduler_run:job", "interval",
                      minutes=interval, next_run_time=datetime.utcnow())
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("Arrêt du scheduler.")

import argparse
import glob
import json
import os
import time
from typing import Any, Dict, List


def _emoji_for_stage(event: Dict[str, Any]) -> str:
    # events "autosignal" / "stage"
    if event.get("source") == "autosignal":
        stage = event.get("stage")
        if stage == "no_signal":
            return "🚫"
        return "🧩"

    # events "decision_stage"
    stage = event.get("decision_stage") or "unknown"
    mapping = {
        "setup_detected": "🧩",
        "proposal_built": "📐",
        "proposal_rejected_referee": "🙅‍♂️",
        "referee_approved": "✅",
        "signal_console_only": "📣",
        "no_proposal": "🚫",
        "unknown": "📄",
    }
    return mapping.get(stage, "📄")


def _safe_get(d: Dict[str, Any], *keys, default=None):
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return cur if cur is not None else default


def _format_event(event: Dict[str, Any]) -> str:
    lines: List[str] = []

    ts = event.get("ts", "?")
    symbol = event.get("symbol", "?")

    regime = _safe_get(event, "context", "regime", default={}) or {}
    trend = regime.get("trend", "unknown")
    vol = regime.get("volatility", "unknown")

    emoji = _emoji_for_stage(event)

    # Cas autosignal / no_signal (no_candidates)
    if event.get("source") == "autosignal":
        stage = event.get("stage", "unknown")
        reason = event.get("reason", "n/a")

        lines.append(f"{emoji} autosignal [{stage}] {symbol}")
        lines.append(f"   • regime: trend={trend}, vol={vol}")
        lines.append(f"   • reason: {reason}")
        lines.append(f"   • ts: {ts}")
        return "\n".join(lines)

    # Cas décision classique avec decision_stage
    stage = event.get("decision_stage", "unknown")

    lines.append(f"{emoji} decision_stage={stage} symbol={symbol}")
    lines.append(f"   • regime: trend={trend}, vol={vol}")

    setup = event.get("setup")
    if isinstance(setup, dict):
        sid = setup.get("id", "n/a")
        side = setup.get("side", "n/a")
        quality = setup.get("quality", "n/a")
        lines.append(f"   • setup: {sid} ({side}, quality={quality})")

    proposal = event.get("proposal")
    if isinstance(proposal, dict):
        entry = proposal.get("entry", "n/a")
        stop = proposal.get("stop", "n/a")
        take = proposal.get("take", "n/a")
        risk_pct = proposal.get("risk_pct", "n/a")
        lines.append(f"   • proposal: entry={entry} stop={stop} take={take} risk={risk_pct}")

        reasons = proposal.get("reasons") or []
        if isinstance(reasons, list) and reasons:
            lines.append(f"   • reasons ({len(reasons)}):")
            for r in reasons:
                lines.append(f"     - {r}")

    referee = event.get("referee")
    if isinstance(referee, dict):
        decision = referee.get("decision", "n/a")
        mode = referee.get("mode", "n/a")
        conf = referee.get("confidence", "n/a")
        comment = referee.get("comment", "")
        lines.append(f"   • referee: decision={decision} mode={mode} confidence={conf}")
        if comment:
            lines.append(f"     → {comment}")

    meta = event.get("meta") or {}
    strategy_id = meta.get("strategy_id", "n/a")
    strategy_version = meta.get("strategy_version", "n/a")
    lines.append(f"   • strategy: {strategy_id} ({strategy_version})")

    lines.append(f"   • ts: {ts}")

    return "\n".join(lines)


def _iter_events(path: str, follow: bool = False):
    with open(path, "r", encoding="utf-8") as f:
        while True:
            line = f.readline()
            if not line:
                if not follow:
                    break
                time.sleep(0.5)
                continue

            line = line.strip()
            if not line:
                continue

            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                print(f"⚠️  ligne JSON illisible: {line}")
                print("-" * 80)
                continue

            print(_format_event(event))
            print("-" * 80)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Affichage lisible des logs de décisions (logs/decisions/*.jsonl)."
    )
    parser.add_argument(
        "--log-dir",
        default="logs/decisions",
        help="Répertoire contenant les fichiers JSONL de décisions (par défaut: logs/decisions).",
    )
    parser.add_argument(
        "--file",
        help="Fichier JSONL spécifique à lire. Si non fourni, utilise le dernier fichier dans log-dir.",
    )
    parser.add_argument(
        "--follow",
        action="store_true",
        help="Mode suivi temps réel (équivalent à tail -F).",
    )

    args = parser.parse_args(argv)

    if args.file:
        path = args.file
    else:
        pattern = os.path.join(args.log_dir, "*.jsonl")
        files = sorted(glob.glob(pattern))
        if not files:
            print(f"⚠️  Aucun fichier trouvé dans {args.log_dir}")
            return 1
        path = files[-1]

    if not os.path.exists(path):
        print(f"⚠️  Fichier introuvable: {path}")
        return 1

    print(f"📂 Lecture du fichier de décisions: {path}")
    if args.follow:
        print("🔭 Mode suivi temps réel (Ctrl+C pour quitter)\n")
    else:
        print("📄 Mode lecture simple\n")

    _iter_events(path, follow=args.follow)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

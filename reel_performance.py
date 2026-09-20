"""Capture the required 24 h and 72 h performance samples for published Reels."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
LANGUAGE = os.environ.get("REEL_LANGUAGE", "en")
if LANGUAGE not in {"ko", "en"}:
    raise RuntimeError("Unsupported reel language")
DATA = ROOT / ("shorts-en" if LANGUAGE == "en" else "shorts")
QUEUE = DATA / "queue.json"
PERFORMANCE = DATA / "performance.json"
ACCOUNT = "phyedu_en" if LANGUAGE == "en" else "phyedu_net"
SECRET_NAME = "IG_EN_SECRETS_JSON" if LANGUAGE == "en" else "IG_SECRETS_JSON"
BASE = "https://graph.instagram.com/v21.0"
METRICS = "views,reach,likes,comments,saved,shares,total_interactions,ig_reels_avg_watch_time,ig_reels_video_view_total_time"


def credentials():
    raw = os.environ.get(SECRET_NAME, "")
    if not raw:
        raise RuntimeError("Dedicated Reel Instagram secret is missing")
    try:
        value = json.loads(raw)
        if LANGUAGE == "ko":
            value = value["accounts"][ACCOUNT]
    except (ValueError, TypeError, KeyError):
        raise RuntimeError("Dedicated Reel Instagram secret is invalid") from None
    if not value.get("access_token") or not value.get("user_id"):
        raise RuntimeError("Dedicated Reel Instagram secret is incomplete")
    return value


def due_samples(done, existing, current):
    captured = {(row.get("item_id"), row.get("window_hours")) for row in existing}
    due = []
    for item in done:
        policy = item.get("content_policy") or {}
        if policy.get("measurement_hours") != [24, 72] or not item.get("media_id"):
            continue
        published = dt.datetime.fromisoformat(item["published_at"])
        if published.tzinfo is None:
            raise RuntimeError("Published Instagram timestamp lacks a timezone")
        age = (current - published.astimezone(current.tzinfo)).total_seconds() / 3600
        for window in (24, 72):
            # Capture shortly after the target, but never backfill a stale approximation.
            if window <= age <= window + 12 and (item["id"], window) not in captured:
                due.append((item, window, round(age, 3)))
    return due


def metric_values(payload):
    result = {}
    for row in payload.get("data", []):
        values = row.get("values") or []
        value = values[0].get("value") if values else (row.get("total_value") or {}).get("value")
        result[row.get("name")] = value
    return result


def read_metrics(media_id, token):
    import requests
    response = requests.get(f"{BASE}/{media_id}/insights", params={"metric": METRICS},
                            headers={"Authorization": "Bearer " + token}, timeout=60)
    try:
        payload = response.json()
    except ValueError:
        raise RuntimeError("Instagram insights response was invalid") from None
    if not response.ok or "error" in payload:
        code = (payload.get("error") or {}).get("code", "unknown")
        raise RuntimeError("Instagram insights request failed; code=" + str(code))
    return metric_values(payload)


def sample(item, window, age, metrics, captured_at):
    reach = metrics.get("reach")
    shares = metrics.get("shares")
    saved = metrics.get("saved")
    return {
        "item_id": item["id"], "media_id": item["media_id"], "permalink": item.get("permalink"),
        "topic_family": (item.get("content_policy") or {}).get("topic_family"),
        "window_hours": window, "actual_age_hours": age, "captured_at": captured_at.isoformat(),
        "views": metrics.get("views"), "reach": reach,
        "average_watch_time_ms": metrics.get("ig_reels_avg_watch_time"),
        "total_watch_time_ms": metrics.get("ig_reels_video_view_total_time"),
        "likes": metrics.get("likes"), "comments": metrics.get("comments"),
        "shares": shares, "saved": saved, "total_interactions": metrics.get("total_interactions"),
        "shares_per_1000_reach": round(shares * 1000 / reach, 3) if reach and shares is not None else None,
        "saves_per_1000_reach": round(saved * 1000 / reach, 3) if reach and saved is not None else None,
    }


def persist(data):
    PERFORMANCE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    relative = str(PERFORMANCE.relative_to(ROOT))
    subprocess.run(["git", "add", relative], cwd=ROOT, check=True)
    changed = subprocess.run(["git", "diff", "--cached", "--quiet", "--", relative], cwd=ROOT)
    if changed.returncode == 0:
        return
    subprocess.run(["git", "commit", "-m", f"Reel metrics: capture {ACCOUNT} [skip ci]", "--", relative],
                   cwd=ROOT, check=True)
    for _ in range(3):
        if subprocess.run(["git", "push"], cwd=ROOT).returncode == 0:
            return
        subprocess.run(["git", "pull", "--rebase"], cwd=ROOT, check=True)
    raise RuntimeError("Could not persist Reel performance samples")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    data = (json.loads(PERFORMANCE.read_text(encoding="utf-8")) if PERFORMANCE.exists()
            else {"schema_version": 1, "account": ACCOUNT, "samples": []})
    if data.get("account") != ACCOUNT or not isinstance(data.get("samples"), list):
        raise RuntimeError("Invalid Reel performance file")
    current = dt.datetime.now(dt.timezone.utc)
    due = due_samples(queue.get("done", []), data["samples"], current)
    if args.dry_run:
        print(json.dumps({"account": ACCOUNT, "due": len(due)}))
        return
    if not due:
        print(json.dumps({"account": ACCOUNT, "captured": 0}))
        return
    token = credentials()["access_token"]
    for item, window, age in due:
        metrics = read_metrics(item["media_id"], token)
        data["samples"].append(sample(item, window, age, metrics, current))
    persist(data)
    print(json.dumps({"account": ACCOUNT, "captured": len(due)}))


if __name__ == "__main__":
    main()

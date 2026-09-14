"""Isolated Instagram Login publisher for @phyedu_en. No Korean queue imports.

Only reviewed English files explicitly placed in shorts-en/queue.json are eligible.
An empty queue is a successful no-op. --check only reads account and queue state.
IG_EN_SECRETS_JSON is a dedicated flat credential object, never written to git.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "shorts-en"
QUEUE = DATA / "queue.json"
LOG = DATA / "UPLOAD.log"
ACCOUNT = "phyedu_en"
KST = dt.timezone(dt.timedelta(hours=9))
GRAPH = "https://graph.instagram.com"
VERSION = "v21.0"
SECRET_NAME = "IG_EN_SECRETS_JSON"
# Retry the same lunch/evening slots away from GitHub's busiest minute.
# A scheduled event remains best-effort; these retries do not guarantee timing.
SCHEDULE_SLOTS = {
    "0 3 * * *": "B", "17 3 * * *": "B", "47 3 * * *": "B",
    "0 9 * * *": "A", "17 9 * * *": "A", "47 9 * * *": "A",
}


class ProcessingError(RuntimeError):
    pass


def now():
    return dt.datetime.now(KST)


def load_queue():
    q = json.loads(QUEUE.read_text(encoding="utf-8"))
    if q.get("account") != ACCOUNT or q.get("timezone") != "Asia/Seoul":
        raise RuntimeError("English queue account/timezone mismatch")
    if q.get("slots") != {"B": "12:00", "A": "18:00"}:
        raise RuntimeError("Expected lunch/evening schedule")
    if not isinstance(q.get("queue"), list) or not isinstance(q.get("done"), list):
        raise RuntimeError("Invalid queue schema")
    return q


def save_queue(q):
    temp = QUEUE.with_suffix(".tmp")
    temp.write_text(json.dumps(q, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(QUEUE)


def log(message, to_file=True):
    # Callers pass fixed status text, never raw HTTP errors or credentials.
    line = now().isoformat() + " " + message
    print(line, flush=True)
    if to_file:
        with LOG.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")


def git(*args, check=True):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, check=check)


def persist(q, reason):
    """Commit/push the English state before any uncertain publication action."""
    save_queue(q)
    files = ["shorts-en/queue.json", "shorts-en/UPLOAD.log"]
    git("add", "-f", *files)
    if git("diff", "--cached", "--quiet", "--", *files, check=False).returncode == 0:
        return
    git("commit", "--only", "-m", "English reels: " + reason + " [skip ci]", "--", *files)
    for _ in range(3):
        if git("push", check=False).returncode == 0:
            return
        # Other workflows write distinct paths. A conflict fails closed.
        git("pull", "--rebase")
    raise RuntimeError("Could not persist English publication state")


def credentials():
    raw = os.environ.get(SECRET_NAME, "")
    if not raw:
        raise RuntimeError("Dedicated English Instagram secret is missing")
    try:
        c = json.loads(raw)
    except (ValueError, TypeError):
        raise RuntimeError("Dedicated English Instagram secret is invalid") from None
    if c.get("username") != ACCOUNT or not c.get("user_id") or not c.get("access_token"):
        raise RuntimeError("English credentials do not identify the expected account")
    if not str(c["user_id"]).isdigit():
        raise RuntimeError("Invalid Instagram account ID")
    return c


class API:
    def __init__(self, c):
        import requests
        self.c = c
        self.session = requests.Session()
        self.session.headers["Authorization"] = "Bearer " + c["access_token"]

    def call(self, method, path, **kwargs):
        try:
            response = self.session.request(method, GRAPH + "/" + VERSION + path,
                                            timeout=60, **kwargs)
            data = response.json()
        except Exception:
            raise RuntimeError("Instagram request failed or response was uncertain") from None
        if not response.ok or "error" in data:
            code = (data.get("error") or {}).get("code", "unknown")
            raise RuntimeError("Instagram API rejected request; code=" + str(code))
        return data

    def verify(self):
        data = self.call("GET", "/" + str(self.c["user_id"]), params={"fields": "id,user_id,username"})
        # Instagram Login can return both app-scoped id and professional user_id.
        # Validate the configured target against the returned IDs and username.
        returned_ids = {str(data[k]) for k in ("id", "user_id") if data.get(k)}
        if data.get("username") != ACCOUNT or str(self.c["user_id"]) not in returned_ids:
            raise RuntimeError("LIVE Instagram account does not match @phyedu_en")

    def recent(self):
        return self.call("GET", "/" + str(self.c["user_id"]) + "/media", params={
            "fields": "id,caption,timestamp,permalink", "limit": 100})["data"]

    def publishing_limit(self):
        data = self.call("GET", "/" + str(self.c["user_id"]) + "/content_publishing_limit",
                         params={"fields": "quota_usage,config"})
        rows = data.get("data")
        if (not isinstance(rows, list) or not rows or not isinstance(rows[0], dict)
                or type(rows[0].get("quota_usage")) is not int or rows[0]["quota_usage"] < 0
                or not isinstance(rows[0].get("config"), dict)):
            raise RuntimeError("English publishing-limit read check returned invalid quota data")
        return rows[0]

    def create(self, url, caption):
        return self.call("POST", "/" + str(self.c["user_id"]) + "/media", data={
            "media_type": "REELS", "video_url": url, "caption": caption,
            "share_to_feed": "true"})["id"]

    def ready(self, cid):
        for _ in range(60):
            state = self.call("GET", "/" + str(cid), params={"fields": "status_code"})
            if state.get("status_code") == "FINISHED":
                return
            if state.get("status_code") in {"ERROR", "EXPIRED"}:
                raise ProcessingError("Instagram media processing failed")
            time.sleep(10)
        raise RuntimeError("Instagram media processing timed out")

    def publish(self, cid):
        return self.call("POST", "/" + str(self.c["user_id"]) + "/media_publish",
                         data={"creation_id": cid})["id"]

    def media_info(self, mid):
        return self.call("GET", "/" + str(mid), params={"fields": "id,caption,permalink,timestamp"})


def refresh_if_due(c):
    """Refresh weekly and immediately persist only the dedicated English secret."""
    anchor = c.get("refreshed_at") or c.get("obtained_at")
    if not anchor:
        raise RuntimeError("English token obtained_at metadata is required")
    age = now() - dt.datetime.fromisoformat(anchor)
    if age < dt.timedelta(days=7):
        return c
    if not os.environ.get("GH_TOKEN"):
        raise RuntimeError("English token refresh cannot be saved: GH_TOKEN is missing")
    import requests
    try:
        r = requests.get(GRAPH + "/refresh_access_token", params={
            "grant_type": "ig_refresh_token", "access_token": c["access_token"]}, timeout=45)
        result = r.json()
    except Exception:
        raise RuntimeError("English token refresh request failed") from None
    if not r.ok or not result.get("access_token"):
        raise RuntimeError("English token refresh was rejected")
    updated = dict(c, access_token=result["access_token"], refreshed_at=now().isoformat(),
                   expires_at=(now() + dt.timedelta(seconds=int(result["expires_in"]))).isoformat())
    # Secret body is stdin only. Never print command stderr or returned token.
    p = subprocess.run(["gh", "secret", "set", SECRET_NAME, "--repo", os.environ["GITHUB_REPOSITORY"]],
                       input=json.dumps(updated), text=True, capture_output=True)
    if p.returncode:
        raise RuntimeError("Refreshed English token could not be saved")
    log("English token refreshed and saved", to_file=False)
    return updated


def media(item):
    if item.get("language") != "en" or item.get("reviewed") is not True:
        raise RuntimeError("Only explicitly reviewed English media can be queued")
    paths = []
    for field, suffix in (("video", ".mp4"), ("caption", ".txt")):
        name = item.get(field, "")
        p = DATA / name
        if not name or Path(name).name != name or p.suffix.lower() != suffix or not p.is_file():
            raise RuntimeError("Invalid or missing English " + field + " file")
        if field == "video" and p.stat().st_size >= 100 * 1024 * 1024:
            raise RuntimeError("English video exceeds the GitHub file-size limit")
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        if item.get(field + "_sha256") != actual:
            raise RuntimeError("English " + field + " checksum mismatch")
        paths.append(p)
    caption = paths[1].read_text(encoding="utf-8").strip()
    if not 1 <= len(caption) <= 2200 or any("\uac00" <= ch <= "\ud7a3" for ch in caption):
        raise RuntimeError("English caption is invalid or contains Korean text")
    return paths[0], caption


def scheduled_time(q, item):
    scheduled = dt.datetime.fromisoformat(item["scheduled_at"])
    if scheduled.tzinfo is None:
        raise RuntimeError("English publication date requires an explicit timezone")
    scheduled = scheduled.astimezone(KST)
    if scheduled.strftime("%H:%M") != q["slots"].get(item.get("slot")) or scheduled.second or scheduled.microsecond:
        raise RuntimeError("English publication time does not match its configured slot")
    return scheduled


def slot_for_schedule(expression):
    try:
        return SCHEDULE_SLOTS[expression]
    except KeyError:
        raise RuntimeError("Unknown English schedule; publication refused") from None


def eligible(q, item, slot, at):
    if item.get("slot") != slot:
        return False
    scheduled = scheduled_time(q, item)
    at = at.astimezone(KST)
    # A delayed/replayed event must never catch up yesterday's reel today.
    if at.date() != scheduled.date() or at < scheduled:
        return False
    today = [d for d in q["done"] if d.get("published_at") and
             dt.datetime.fromisoformat(d["published_at"]).astimezone(KST).date() == at.date()]
    return len(today) < 2 and not any(d.get("slot") == slot for d in today)


def finish(q, item, mid, permalink, reason, published_at):
    timestamp = dt.datetime.fromisoformat(published_at)
    if timestamp.tzinfo is None:
        raise RuntimeError("Published Instagram timestamp lacks a timezone")
    q["done"].append(dict(item, media_id=mid, permalink=permalink,
                          published_at=timestamp.astimezone(KST).isoformat(), status="published"))
    q["queue"].pop(0)
    log(reason)
    persist(q, reason)


def host_url(video):
    repo = os.environ["GITHUB_REPOSITORY"]
    sha = git("rev-parse", "HEAD").stdout.strip()
    # Immutable public raw URL avoids jsDelivr's per-file size restriction.
    return "https://raw.githubusercontent.com/" + repo + "/" + sha + "/shorts-en/" + quote(video.name)


def run(args):
    q = load_queue()
    schedule = getattr(args, "schedule", None)
    slot = slot_for_schedule(schedule) if schedule else args.slot
    if args.plan:
        print(json.dumps({"account": ACCOUNT, "pending": len(q["queue"]), "paused": q["paused"],
                          "slots": q["slots"]}, ensure_ascii=False))
        return 0
    if args.check:
        api = API(credentials())
        api.verify()
        print("English identity read check passed (@phyedu_en)")
        api.recent()
        print("English media read check passed")
        api.publishing_limit()
        print("English content-publishing-limit access check passed")
        for item in q["queue"]:
            media(item)
        print("English account/queue read-only check passed; no publication")
        return 0
    if not os.environ.get("GITHUB_ACTIONS"):
        raise RuntimeError("Scheduled publishing is permitted only in GitHub Actions")
    c = None
    if os.environ.get(SECRET_NAME):
        c = refresh_if_due(credentials())
    if q.get("paused") or not q["queue"]:
        log("Queue paused" if q.get("paused") else "English queue empty; nothing to publish", to_file=False)
        return 0
    item = q["queue"][0]
    reconciling = bool(item.get("media_id") or item.get("publish_requested_at"))
    if not reconciling:
        if scheduled_time(q, item).date() < now().astimezone(KST).date():
            raise RuntimeError("English reel missed its scheduled date; explicit rescheduling is required")
        if not eligible(q, item, slot, now()):
            log("No English reel eligible for this slot", to_file=False)
            return 0
    video, caption = media(item)
    api = API(c or credentials())
    api.verify()
    if item.get("media_id"):
        mid = item["media_id"]
        info = api.media_info(mid)
        if str(info.get("id")) != str(mid) or info.get("caption", "").strip() != caption:
            raise RuntimeError("Confirmed Instagram media does not match the queued caption")
        finish(q, item, mid, info.get("permalink", ""), "Reconciled confirmed English media ID", info["timestamp"])
        return 0
    recent = api.recent()
    duplicates = [r for r in recent if r.get("caption", "").strip() == caption]
    if duplicates:
        r = duplicates[0]
        finish(q, item, r["id"], r.get("permalink", ""), "Reconciled existing English reel", r["timestamp"])
        return 0
    if item.get("publish_requested_at"):
        q["paused"] = True
        log("Previous publication is uncertain; English queue paused for reconciliation")
        persist(q, "uncertain previous publication")
        return 1
    if not eligible(q, item, slot, now()):
        log("English reel is no longer eligible; no publication", to_file=False)
        return 0
    todays_posts = [r for r in recent if dt.datetime.fromisoformat(r["timestamp"]).astimezone(KST).date() == now().date()]
    if len(todays_posts) >= 2:
        log("English account already has two posts today", to_file=False)
        return 0
    url = host_url(video)
    if not item.get("creation_id"):
        item["creation_id"] = api.create(url, caption)
        log("Created English media container")
        persist(q, "container created")
    try:
        api.ready(item["creation_id"])
    except ProcessingError:
        # Meta explicitly says it cannot publish this container. It is safe to
        # create a new container on the next eligible run; no publish was sent.
        item.pop("creation_id", None)
        item["failures"] = item.get("failures", 0) + 1
        if item["failures"] >= 3:
            q["paused"] = True
        log("English media processing failed; retry count recorded")
        persist(q, "processing failed")
        return 1
    # Processing can cross midnight. Recheck before recording/sending a new
    # publish request, while preserving any prepared container for inspection.
    if not eligible(q, item, slot, now()):
        log("English reel is no longer eligible after processing; no publication", to_file=False)
        return 0
    item["publish_requested_at"] = now().isoformat()
    log("English publication requested")
    persist(q, "publication intent")
    if not eligible(q, item, slot, now()):
        # Git push/rebase may itself cross midnight. No publish was sent, so
        # clearing this prepared intent is safe; a failed commit stops closed.
        item.pop("publish_requested_at", None)
        log("English publication intent expired before sending; no publication")
        persist(q, "publication intent expired before sending")
        return 0
    mid = api.publish(item["creation_id"])
    item["media_id"] = mid
    log("Instagram returned English media ID")
    persist(q, "media ID received")
    info = api.media_info(mid)
    if str(info.get("id")) != str(mid) or info.get("caption", "").strip() != caption:
        raise RuntimeError("Published Instagram media does not match the queued caption")
    finish(q, item, mid, info.get("permalink", ""), "English reel published", info["timestamp"])
    return 0


def main():
    p = argparse.ArgumentParser()
    timing = p.add_mutually_exclusive_group()
    timing.add_argument("--slot", choices=("A", "B"), default="B")
    timing.add_argument("--schedule", choices=tuple(SCHEDULE_SLOTS))
    p.add_argument("--plan", action="store_true")
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    try:
        return run(args)
    except Exception as e:
        # Exception type/fixed messages only; requests can carry credentials in URLs.
        text = str(e) if type(e) is RuntimeError else type(e).__name__
        print("English uploader stopped: " + text, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

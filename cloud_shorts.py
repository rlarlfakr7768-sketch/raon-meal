#!/usr/bin/env python3
"""쇼츠 대기열에서 한 편을 꺼내 인스타 릴스로 올린다. GitHub Actions 에서 돈다.

    python cloud_shorts.py --slot A
    python cloud_shorts.py --plan       올릴 것만 보고 아무것도 안 한다

집 컴퓨터가 꺼져 있어도 나가게 하려고 만들었다. 로컬 `tools/autopost.py` 와
같은 규칙을 쓰되, 영상과 캡션과 대기열이 전부 이 레포 안에 있다.

    shorts/queue.json          대기열과 올린 기록
    shorts/<번호>-<슬러그>.mp4   영상
    shorts/<번호>-<슬러그>.txt   캡션

⚠ 영상은 미리 레포에 들어와 있어야 한다. 액션이 만드는 게 아니라 집에서
   `tools/push_shorts.py` 로 밀어 넣는다. 액션은 골라서 올리기만 한다.

안전장치는 로컬과 같다.
  1. 순서 잠금 — 이 편 끝 카드의 예고(cue)가 대기열 다음 편과 다르면 멈춘다
  2. 하루 한 편 — 오늘 이미 올린 게 있으면 그냥 끝낸다
  3. 같은 캡션이 올라가 있으면 대기열에서 빼고 넘어간다
  4. 슬롯이 안 맞으면 건너뛴다
  5. 실패해도 대기열에서 안 뺀다. 세 번 연속 실패하면 멈춘다
"""

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time

import requests

import publish_ig as IG

HERE = os.path.dirname(os.path.abspath(__file__))
SHORTS = os.path.join(HERE, "shorts")
QUEUE = os.path.join(SHORTS, "queue.json")
LOG = os.path.join(SHORTS, "SHORTS.log")
KST = dt.timezone(dt.timedelta(hours=9))
ACCOUNT = "phyedu_net"
MAX_FAILS = 3
CAPTION_LIMIT = 2200

# 인스타는 영상을 못 받아도 사유를 안 준다. CDN 이 안 퍼진 것이 대부분이라
# 같은 URL 로 다시 건다. 로컬에서 잰 값을 그대로 쓴다(3분 간격, 12번).
SETTLE = 180
TRIES = 12


def say(msg):
    line = "%s  %s" % (dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M"), msg)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load():
    with open(QUEUE, encoding="utf-8") as f:
        return json.load(f)


def save(q):
    with open(QUEUE, "w", encoding="utf-8") as f:
        json.dump(q, f, ensure_ascii=False, indent=2)
        f.write("\n")


def git(*a, check=True):
    return subprocess.run(["git", *a], cwd=HERE, check=check,
                          capture_output=True, text=True)


def commit(msg):
    """대기열과 기록만 되돌려 놓는다. 영상은 건드리지 않는다."""
    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email",
        "41898282+github-actions[bot]@users.noreply.github.com")
    git("add", "-f", "shorts/queue.json", "shorts/SHORTS.log", check=False)
    if git("commit", "-m", msg + " [skip ci]", check=False).returncode != 0:
        return
    if git("push", check=False).returncode != 0:
        git("pull", "--rebase", check=False)
        git("push", check=False)


# ------------------------------------------------------------------ 계정

def account():
    _, acc = IG.get_account(ACCOUNT)
    return acc["user_id"], acc["access_token"]


def recent(uid, token, limit=25):
    r = requests.get("%s/%s/%s/media" % (IG.GRAPH, IG.VERSION, uid),
                     params={"fields": "timestamp,caption,permalink",
                             "limit": limit, "access_token": token},
                     timeout=30).json()
    return r.get("data", [])


def posted_today(items):
    today = dt.datetime.now(KST).date()
    n = 0
    for m in items:
        t = dt.datetime.fromisoformat(
            m["timestamp"].replace("+0000", "+00:00")).astimezone(KST)
        if t.date() == today:
            n += 1
    return n


def _head(s):
    return re.sub(r"\s+", "", s or "")[:40]


def already_posted(items, caption):
    want = _head(caption.splitlines()[0] if caption else "")
    if not want:
        return None
    for m in items:
        cap = m.get("caption") or ""
        if not cap:
            continue
        got = _head(cap.splitlines()[0])
        if want[:24] and (want[:24] in got or got[:24] in want):
            return m.get("permalink") or m["timestamp"]
    return None


# ------------------------------------------------------------------ 게시

def host_url(rel):
    """레포에 이미 들어와 있는 파일의 jsDelivr 주소."""
    repo = os.environ.get("GITHUB_REPOSITORY")
    sha = os.environ.get("GITHUB_SHA") or git("rev-parse", "HEAD").stdout.strip()
    if not repo:
        raise RuntimeError("GITHUB_REPOSITORY 가 없다. 액션에서만 돈다")
    return "https://cdn.jsdelivr.net/gh/%s@%s/%s" % (repo, sha, rel)


def wait_hosted(url, tries=20, gap=6):
    for _ in range(tries):
        try:
            if requests.get(url, timeout=15).status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(gap)
    return False


def create_reel(uid, token, url, caption):
    r = requests.post("%s/%s/%s/media" % (IG.GRAPH, IG.VERSION, uid),
                      data={"media_type": "REELS", "video_url": url,
                            "caption": caption, "access_token": token},
                      timeout=120).json()
    if "id" not in r:
        raise RuntimeError("컨테이너 실패: %s" % str(r)[:300])
    return r["id"]


def wait_ready(cid, token, tries=60, gap=10):
    for _ in range(tries):
        r = requests.get("%s/%s/%s" % (IG.GRAPH, IG.VERSION, cid),
                         params={"fields": "status_code,status",
                                 "access_token": token}, timeout=60).json()
        code = r.get("status_code")
        if code == "FINISHED":
            return
        if code == "ERROR":
            raise RuntimeError("인스타가 영상을 물리쳤다: %s" % str(r.get("status"))[:200])
        time.sleep(gap)
    raise RuntimeError("인코딩이 안 끝난다")


def publish(uid, token, cid):
    r = requests.post("%s/%s/%s/media_publish" % (IG.GRAPH, IG.VERSION, uid),
                      data={"creation_id": cid, "access_token": token},
                      timeout=120).json()
    if "id" not in r:
        raise RuntimeError("게시 실패: %s" % str(r)[:300])
    return r["id"]


# ------------------------------------------------------------------ 본체

def check(q, item, caption, video):
    bad = []
    if not os.path.exists(video):
        bad.append("영상이 레포에 없다: %s" % os.path.basename(video))
    if not caption:
        bad.append("캡션이 비었다")
    elif len(caption) > CAPTION_LIMIT:
        bad.append("캡션 %d자 — %d자를 넘는다" % (len(caption), CAPTION_LIMIT))
    # 순서 잠금. 이 편의 끝 카드가 예고한 제목(next_cue)이 대기열 다음 편의
    # 제목(cue)과 같아야 한다. 다르면 예고가 거짓말이 된다.
    said = item.get("next_cue")
    nxt = q["queue"][1] if len(q["queue"]) > 1 else None
    if said and nxt:
        want = re.sub(r"\s+", "", said)
        got = re.sub(r"\s+", "", nxt.get("cue") or nxt.get("title") or "")
        if want and got and want not in got and got not in want:
            bad.append("순서 잠금 — 끝 카드는 「%s」를 예고하는데 다음은 「%s」다"
                       % (said, nxt.get("title")))
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", choices=["A", "B"])
    ap.add_argument("--plan", action="store_true")
    args = ap.parse_args()

    q = load()
    if q.get("paused"):
        say("멈춤 상태다. 아무것도 안 한다")
        return 0
    if not q["queue"]:
        say("대기열이 비었다")
        return 0

    item = q["queue"][0]
    base = "%s-%s" % (item["num"], item["slug"])
    video = os.path.join(SHORTS, base + ".mp4")
    cap_path = os.path.join(SHORTS, base + ".txt")
    caption = ""
    if os.path.exists(cap_path):
        with open(cap_path, encoding="utf-8") as f:
            caption = f.read().strip()

    if args.plan:
        for i, it in enumerate(q["queue"][:8]):
            print("  %s %-30s 슬롯 %s" % (it["num"], it["title"][:30], it["slot"]))
        return 0

    if args.slot and item.get("slot") != args.slot:
        say("[%s] 건너뜀 — 맨 위 %s %s 는 %s 슬롯이다"
            % (args.slot, item["num"], item["slug"], item.get("slot")))
        return 0

    bad = check(q, item, caption, video)
    if bad:
        for b in bad:
            say("멈춤 — " + b)
        return 1

    uid, token = account()
    items = recent(uid, token)
    n = posted_today(items)
    if n:
        say("[%s] 건너뜀 — 오늘 이미 %d편 올렸다" % (args.slot or "-", n))
        return 0

    dup = already_posted(items, caption)
    if dup:
        say("%s %s 는 이미 올라가 있다(%s). 대기열에서 뺀다"
            % (item["num"], item["slug"], dup))
        q["done"].append({**item, "at": dt.datetime.now(KST).isoformat(),
                          "note": "이미 올라가 있었다"})
        q["queue"].pop(0)
        save(q)
        commit("shorts: %s 는 이미 올라가 있어 대기열에서 뺀다" % item["num"])
        return 0

    rel = "shorts/%s.mp4" % base
    url = host_url(rel)
    say("%s %s 올린다  %s" % (item["num"], item["slug"], url))
    if not wait_hosted(url):
        say("CDN 이 아직 안 내준다. 다음 슬롯에 다시 한다")
        item["fails"] = item.get("fails", 0) + 1
        save(q)
        commit("shorts: %s CDN 대기 실패 %d회" % (item["num"], item["fails"]))
        return 1

    try:
        for k in range(1, TRIES + 1):
            cid = create_reel(uid, token, url, caption)
            try:
                wait_ready(cid, token)
                break
            except RuntimeError as e:
                if k == TRIES:
                    raise
                say("  인코딩 실패(%d/%d) %s — %d초 뒤 다시" % (k, TRIES, e, SETTLE))
                time.sleep(SETTLE)
        mid = publish(uid, token, cid)
    except Exception as e:
        item["fails"] = item.get("fails", 0) + 1
        say("실패 %d회 — %s" % (item["fails"], str(e)[:200]))
        if item["fails"] >= MAX_FAILS:
            q["paused"] = True
            say("세 번 연속 실패라 멈춘다. 사람이 봐야 한다")
        save(q)
        commit("shorts: %s 실패 %d회" % (item["num"], item["fails"]))
        return 1

    perma = requests.get("%s/%s/%s" % (IG.GRAPH, IG.VERSION, mid),
                         params={"fields": "permalink", "access_token": token},
                         timeout=60).json().get("permalink", "")
    say("올렸다 — %s %s  %s" % (item["num"], item["title"], perma))
    q["done"].append({**item, "at": dt.datetime.now(KST).isoformat(),
                      "media_id": mid, "permalink": perma})
    q["queue"].pop(0)
    save(q)
    commit("shorts: %s %s 게시" % (item["num"], item["slug"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

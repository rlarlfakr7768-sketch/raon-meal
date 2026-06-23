"""
클라우드(GitHub Actions)용 오케스트레이터.
파싱 → 렌더 → 이미지 공개호스팅 → 공식 IG API 게시(피드+스토리) → 토큰 갱신.
secrets.json 은 워크플로가 GitHub Secret(IG_SECRETS_JSON)에서 써준다.
"""
import os
import sys
import json

import requests

import get_menu
import neis_menu
import render_card
import publish_ig

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(SCRIPT_DIR, "menu_today.json")
CARD = os.path.join(SCRIPT_DIR, "menu_card.jpg")
STORY = os.path.join(SCRIPT_DIR, "menu_story.jpg")
MARKER = os.path.join(SCRIPT_DIR, "meal_last.txt")  # 커밋되는 중복방지 마커(백업 cron 안전)

# 급식을 올릴 계정(라벨은 secrets.json 의 키).
# ha_miltonian 은 세팅/토큰은 유지하되 게시는 안 함(다시 올리려면 리스트에 추가).
TARGETS = ["phyedu_net"]
POST_STORY = True
MEAL_ORDER = ["중식", "석식"]


def already_posted_today(today):
    # 오늘 이미 게시했는지 — 마커가 레포에 커밋되므로 백업 cron이 중복 게시하지 않는다.
    if not os.path.exists(MARKER):
        return False
    with open(MARKER, "r", encoding="utf-8") as f:
        return f.read().strip() == today


def mark_posted(today):
    """오늘 게시 완료를 기록·커밋(백업 cron이 같은 날 또 올리지 않게)."""
    import subprocess
    with open(MARKER, "w", encoding="utf-8") as f:
        f.write(today)

    def git(*a):
        return subprocess.run(["git", *a], cwd=SCRIPT_DIR,
                              capture_output=True, text=True)

    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email",
        "41898282+github-actions[bot]@users.noreply.github.com")
    git("add", "meal_last.txt")
    c = git("commit", "-m", f"meal {today} 게시 [skip ci]")
    if c.returncode == 0:
        git("push")


def upload_image(path, name):
    """렌더한 이미지를 레포 img/ 에 커밋·푸시하고 jsDelivr 공개 URL을 반환.
    공개 레포 + GitHub Actions(contents:write) 전제. 인스타가 그 URL을 가져간다."""
    import subprocess
    import shutil
    import time
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        raise RuntimeError("이미지 호스팅은 GitHub Actions(공개 레포)에서만 동작")
    rel = f"img/{name}"
    dest = os.path.join(SCRIPT_DIR, rel)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copy(path, dest)

    def git(*a, check=True):
        return subprocess.run(["git", *a], cwd=SCRIPT_DIR, check=check,
                              capture_output=True, text=True)

    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    git("add", "-f", rel)  # img/ 호스팅 파일은 gitignore여도 강제 추가
    committed = git("commit", "-m", f"host {name} [skip ci]", check=False)
    if committed.returncode == 0:
        git("push")
    sha = git("rev-parse", "HEAD").stdout.strip()
    url = f"https://cdn.jsdelivr.net/gh/{repo}@{sha}/{rel}"
    # jsDelivr가 새 커밋을 받아올 때까지 워밍업(최대 ~30초)
    for _ in range(15):
        try:
            if requests.get(url, timeout=10).status_code == 200:
                break
        except Exception:
            pass
        time.sleep(2)
    return url


def upload_images(pairs):
    """여러 이미지를 한 번에 커밋·푸시하고 jsDelivr URL 리스트를 반환(캐러셀용).
    pairs: [(path, name), ...]"""
    import subprocess
    import shutil
    import time
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        raise RuntimeError("이미지 호스팅은 GitHub Actions(공개 레포)에서만 동작")

    def git(*a, check=True):
        return subprocess.run(["git", *a], cwd=SCRIPT_DIR, check=check,
                              capture_output=True, text=True)

    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    rels = []
    for path, name in pairs:
        rel = f"img/{name}"
        dest = os.path.join(SCRIPT_DIR, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.abspath(path) != os.path.abspath(dest):
            shutil.copy(path, dest)
        git("add", "-f", rel)
        rels.append(rel)
    committed = git("commit", "-m", "host carousel [skip ci]", check=False)
    if committed.returncode == 0:
        git("push")
    sha = git("rev-parse", "HEAD").stdout.strip()
    urls = [f"https://cdn.jsdelivr.net/gh/{repo}@{sha}/{rel}" for rel in rels]
    for _ in range(15):  # jsDelivr 워밍업
        try:
            if requests.get(urls[0], timeout=10).status_code == 200:
                break
        except Exception:
            pass
        time.sleep(2)
    return urls


def build_caption(data):
    lines = [f"🍱 {data['date']} ({data['weekday']}) 라온고 오늘의 급식", ""]
    for meal in MEAL_ORDER:
        m = data.get("meals", {}).get(meal)
        if not m or not m.get("items"):
            continue
        kcal = f" ({m['kcal']})" if m.get("kcal") else ""
        lines.append(f"[{meal}]{kcal}")
        lines.append(" · ".join(m["items"]))
        lines.append("")
    lines.append("#라온고 #라온고등학교 #오늘의급식 #학교급식 #급식스타그램 #고등학교급식")
    return "\n".join(lines).strip()


def main():
    import datetime
    # KST 기준 날짜 — 러너는 UTC라 그냥 date.today()를 쓰면 한국 새벽(06시) 게시 때
    # UTC가 아직 전날이라 '어제'(일요일 등) 급식을 찾다가 못 찾고 건너뛴다.
    KST = datetime.timezone(datetime.timedelta(hours=9))
    today_date = datetime.datetime.now(KST).date()
    today = today_date.isoformat()
    if already_posted_today(today):
        print(f"{today} 이미 게시함 — 건너뜀")
        return

    # 1) 급식 데이터 — NEIS 공식 API 우선, 안 되면 학교 홈페이지 폴백
    data = None
    try:
        data = neis_menu.fetch_day(today_date)
        print(f"NEIS 조회: found={data.get('found')}")
    except Exception as e:
        print(f"NEIS 오류({type(e).__name__}: {e}) — 학교사이트 폴백")
    if not (data and data.get("found")):
        try:
            sd = get_menu.parse_menu(get_menu.fetch_html(today_date), today_date)
            if sd.get("found") or data is None:
                data = sd
        except Exception as e:
            print(f"학교사이트 폴백 오류: {e}")
            if data is None:
                raise
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    has_meal = data.get("found") and any(
        data.get("meals", {}).get(m, {}).get("items") for m in MEAL_ORDER
    )
    if not has_meal:
        print(f"{data.get('date')} 급식 없음(주말/방학) — 게시 건너뜀")
        return

    # 2) 렌더 (menu_card.jpg + menu_story.jpg)
    render_card.render()

    # 3) 공개 호스팅
    feed_url = upload_image(CARD, "feed.jpg")
    print("피드 이미지:", feed_url)
    story_url = upload_image(STORY, "story.jpg") if POST_STORY else None
    if story_url:
        print("스토리 이미지:", story_url)

    caption = build_caption(data)

    # 4) 공식 API 게시
    posted_any = False
    for label in TARGETS:
        try:
            publish_ig.post(label, feed_url, caption, is_story=False)
            posted_any = True
        except Exception as e:
            print(f"[{label}] 피드 실패: {e}")
        if story_url:
            try:
                publish_ig.post(label, story_url, None, is_story=True)
            except Exception as e:
                print(f"[{label}] 스토리 실패(무시): {e}")

    # 중복방지 마커(하나라도 성공 시) — 커밋해서 백업 cron 이중게시 차단
    if posted_any:
        mark_posted(today)

    # 5) 토큰 갱신(가능할 때만; 24시간 미만 토큰은 스킵됨)
    for label in TARGETS:
        try:
            publish_ig.refresh_token(label)
        except Exception as e:
            print(f"[{label}] 토큰 갱신 스킵: {e}")


if __name__ == "__main__":
    main()

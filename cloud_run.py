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
MARKER = os.path.join(SCRIPT_DIR, "last_posted.txt")

# 급식을 올릴 계정(라벨은 secrets.json 의 키).
TARGETS = ["ha_miltonian", "phyedu_net"]
POST_STORY = True
MEAL_ORDER = ["중식", "석식"]


def already_posted_today(today):
    # 로컬 스케줄러용 중복방지. (GitHub 러너는 파일이 없어 항상 진행)
    if not os.path.exists(MARKER):
        return False
    with open(MARKER, "r", encoding="utf-8") as f:
        return f.read().strip() == today


def upload_image(path):
    """이미지를 공개 URL로 올린다(인스타가 가져갈 수 있게). catbox → 0x0.st 폴백."""
    try:
        with open(path, "rb") as f:
            r = requests.post("https://catbox.moe/user/api.php",
                              data={"reqtype": "fileupload"},
                              files={"fileToUpload": f}, timeout=90)
        u = r.text.strip()
        if u.startswith("http"):
            return u
        print("catbox 응답 이상:", u[:200])
    except Exception as e:
        print("catbox 실패:", e)
    # 폴백
    with open(path, "rb") as f:
        r = requests.post("https://0x0.st", files={"file": f},
                          headers={"User-Agent": "raon-meal-bot/1.0"}, timeout=90)
    u = r.text.strip()
    if u.startswith("http"):
        return u
    raise SystemExit(f"이미지 호스팅 전부 실패: {u[:200]}")


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
    today = datetime.date.today().isoformat()
    if already_posted_today(today):
        print(f"{today} 이미 게시함 — 건너뜀")
        return

    # 1) 파싱
    html = get_menu.fetch_html()
    data = get_menu.parse_menu(html)
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
    feed_url = upload_image(CARD)
    print("피드 이미지:", feed_url)
    story_url = upload_image(STORY) if POST_STORY else None
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

    # 중복방지 마커(하나라도 성공 시)
    if posted_any:
        with open(MARKER, "w", encoding="utf-8") as f:
            f.write(today)

    # 5) 토큰 갱신(가능할 때만; 24시간 미만 토큰은 스킵됨)
    for label in TARGETS:
        try:
            publish_ig.refresh_token(label)
        except Exception as e:
            print(f"[{label}] 토큰 갱신 스킵: {e}")


if __name__ == "__main__":
    main()

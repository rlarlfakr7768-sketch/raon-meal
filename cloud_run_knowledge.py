"""
오늘의 지식 — 매일 10장 캐러셀을 phyedu_net 에 게시.
슬라이드: 표지·역사의오늘·물리·수학·과학·명언·어휘·공부법·퀴즈·정답&응원
"""
import os
import sys
import json
import datetime

import render_cards
import publish_ig
import history
from cloud_run import upload_images

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.join(SCRIPT_DIR, "content.json")
TARGETS = ["phyedu_net"]
WD = ["월", "화", "수", "목", "금", "토", "일"]
SUNEUNG = datetime.date(2026, 11, 19)   # 2027학년도 수능(예정) — 필요시 수정


def pick(pool, offset=0):
    return pool[(datetime.date.today().toordinal() + offset) % len(pool)]


def build_slides(c, today):
    wd = WD[today.weekday()]
    dday = (SUNEUNG - today).days
    slides = []

    slides.append({"kind": "cover", "date": f"{today.year}. {today.month}. {today.day}.",
                   "weekday": wd, "dday": (f"수능 D-{dday}" if dday > 0 else "")})

    try:
        events = history.today_events(today.month, today.day, 3)
    except Exception as e:
        print("역사 수집 실패:", e)
        events = []
    if events:
        slides.append({"kind": "history", "events": events})

    p = pick(c["physics"])
    slides.append({"kind": "std", "ko": "물리상식", "en": "Physics",
                   "title": p["title"], "em": p.get("em", ""), "body": p["body"]})
    m = pick(c["math"])
    slides.append({"kind": "std", "ko": "수학상식", "en": "Math",
                   "title": m["title"], "em": m.get("em", ""), "body": m["body"]})
    s = pick(c["science"])
    slides.append({"kind": "std", "ko": "과학상식", "en": "Science",
                   "title": s["title"], "em": s.get("em", ""), "body": s["body"]})

    q = pick(c["quotes"])
    slides.append({"kind": "quote", "text": q["text"], "author": q["author"]})

    v = pick(c["vocab"])
    slides.append({"kind": "std", "ko": "오늘의 어휘", "en": "Korean",
                   "title": v["word"], "em": "", "body": v["body"]})

    st = pick(c["study"])
    slides.append({"kind": "std", "ko": "공부법", "en": "Study",
                   "title": st["title"], "em": st.get("em", ""), "body": st["body"]})

    quiz = pick(c["quiz"])
    slides.append({"kind": "quiz", "q": quiz["q"], "choices": quiz["choices"]})
    cheer = pick(c["cheer"])
    slides.append({"kind": "answer", "answer": quiz["answer"],
                   "explain": quiz["explain"], "cheer": cheer})

    for i, sl in enumerate(slides, 1):
        sl["idx"] = i
    return slides


def build_caption(today):
    wd = WD[today.weekday()]
    return (f"📚 라온고 오늘의 지식 · {today.month}/{today.day} ({wd})\n\n"
            "한 장씩 넘겨보세요 →\n"
            "역사의 오늘 · 물리 · 수학 · 과학 상식 · 명언 · 어휘 · 공부법 · 퀴즈\n\n"
            "#오늘의지식 #공부스타그램 #과학상식 #고등학생 #라온고 #수능 #공부자극 #하루공부")


def load_pools():
    """content.json + content2.json 을 카테고리별로 합친다."""
    with open(CONTENT, "r", encoding="utf-8") as f:
        c = json.load(f)
    extra = os.path.join(SCRIPT_DIR, "content2.json")
    if os.path.exists(extra):
        with open(extra, "r", encoding="utf-8") as f:
            for k, v in json.load(f).items():
                c.setdefault(k, []).extend(v)
    return c


def main():
    c = load_pools()
    today = datetime.date.today()

    slides = build_slides(c, today)
    print(f"슬라이드 {len(slides)}장 구성 — 렌더링…")
    paths = render_cards.render(slides)

    pairs = [(p, f"slide_{i + 1:02d}.jpg") for i, p in enumerate(paths)]
    urls = upload_images(pairs)
    print(f"호스팅 {len(urls)}장 완료")

    caption = build_caption(today)
    for label in TARGETS:
        try:
            publish_ig.post_carousel(label, urls, caption)
        except Exception as e:
            print(f"[{label}] 캐러셀 게시 실패: {e}")

    for label in TARGETS:
        try:
            publish_ig.refresh_token(label)
        except Exception as e:
            print(f"[{label}] 토큰 갱신 스킵: {e}")


if __name__ == "__main__":
    main()

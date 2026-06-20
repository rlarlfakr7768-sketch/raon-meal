"""
오늘의 지식: 큐레이션 풀(knowledge.json)에서 날짜별로 카드 1개를 골라
phyedu_net 에 게시. 평일/주말 무관 매일.
"""
import os
import sys
import json
import datetime

import render_knowledge
import publish_ig
from cloud_run import upload_image

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
POOL_PATH = os.path.join(SCRIPT_DIR, "knowledge.json")
TODAY_PATH = os.path.join(SCRIPT_DIR, "knowledge_today.json")
IMG = os.path.join(SCRIPT_DIR, "knowledge.jpg")

TARGETS = ["phyedu_net"]


def pick_today(pool):
    # 날짜 기준 결정적 회전(매일 다른 카드, 풀을 한 바퀴 돌면 반복)
    idx = datetime.date.today().toordinal() % len(pool)
    return pool[idx]


def build_caption(card):
    lines = [f"🧠 오늘의 지식 — {card['title']}", ""]
    if card.get("hook"):
        lines.append(card["hook"])
        lines.append("")
    lines.append(card.get("body", ""))
    lines.append("")
    lines.append("더 알아보기 → phyedu.net")
    lines.append("")
    tags = "#오늘의지식 #과학상식 #공부법 #라온고 #고등학생 #물리 #과학"
    lines.append(tags)
    return "\n".join(lines).strip()


def main():
    with open(POOL_PATH, "r", encoding="utf-8") as f:
        pool = json.load(f)
    if not pool:
        print("지식 풀 비어있음 — 건너뜀")
        return

    card = pick_today(pool)
    print("오늘 카드:", card["title"])
    with open(TODAY_PATH, "w", encoding="utf-8") as f:
        json.dump(card, f, ensure_ascii=False, indent=2)

    render_knowledge.render()
    url = upload_image(IMG, "knowledge.jpg")
    print("지식 이미지 URL:", url)
    caption = build_caption(card)

    for label in TARGETS:
        try:
            publish_ig.post(label, url, caption, is_story=False)
        except Exception as e:
            print(f"[{label}] 지식 게시 실패: {e}")

    for label in TARGETS:
        try:
            publish_ig.refresh_token(label)
        except Exception as e:
            print(f"[{label}] 토큰 갱신 스킵: {e}")


if __name__ == "__main__":
    main()

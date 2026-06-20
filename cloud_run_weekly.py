"""
주간 요약: 다음 주(월~금) 점심 급식을 한 장으로 정리해 phyedu_net 에 게시.
일요일 21:00(KST) 워크플로가 호출.
"""
import os
import sys
import json
import datetime

import get_menu
import render_week
import publish_ig
from cloud_run import upload_image

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(SCRIPT_DIR, "menu_week.json")
IMG = os.path.join(SCRIPT_DIR, "menu_week.jpg")

TARGETS = ["phyedu_net"]


def next_week_dates():
    """다음 주 월~금 날짜 리스트."""
    today = datetime.date.today()
    days = (7 - today.weekday()) % 7 or 7   # 다음 월요일까지
    monday = today + datetime.timedelta(days=days)
    return [monday + datetime.timedelta(days=i) for i in range(5)]


def build_caption(days, week_label):
    lines = [f"📅 다음 주 점심 급식 ({week_label})", ""]
    for d in days:
        wd = d.get("weekday", "")
        try:
            dd = datetime.date.fromisoformat(d["date"])
            datetxt = f"{dd.month}/{dd.day}"
        except Exception:
            datetxt = d.get("date", "")
        items = d.get("meals", {}).get("중식", {}).get("items", [])
        menu = " · ".join(items) if items else "급식 없음"
        lines.append(f"[{wd} {datetxt}] {menu}")
    lines.append("")
    lines.append("#라온고 #라온고등학교 #주간급식 #이번주급식 #급식스타그램")
    return "\n".join(lines).strip()


def main():
    dates = next_week_dates()
    week_label = f"{dates[0].month}/{dates[0].day}~{dates[-1].month}/{dates[-1].day}"
    print("다음 주:", week_label)

    html = get_menu.fetch_html(schdt=dates[0])
    days = [get_menu.parse_menu(html, dt) for dt in dates]

    any_lunch = any(d.get("meals", {}).get("중식", {}).get("items") for d in days)
    if not any_lunch:
        print("다음 주 급식 정보 없음 — 건너뜀")
        return

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump({"week_label": week_label, "days": days}, f, ensure_ascii=False, indent=2)

    render_week.render()
    url = upload_image(IMG)
    print("주간 이미지 URL:", url)
    caption = build_caption(days, week_label)

    for label in TARGETS:
        try:
            publish_ig.post(label, url, caption, is_story=False)
        except Exception as e:
            print(f"[{label}] 주간 게시 실패: {e}")

    for label in TARGETS:
        try:
            publish_ig.refresh_token(label)
        except Exception as e:
            print(f"[{label}] 토큰 갱신 스킵: {e}")


if __name__ == "__main__":
    main()

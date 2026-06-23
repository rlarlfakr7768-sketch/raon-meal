"""
주간 요약: 다음 주(월~금) 점심 급식을 한 장으로 정리해 phyedu_net 에 게시.
일요일 21:00(KST) 워크플로가 호출.
"""
import os
import sys
import json
import datetime

import get_menu
import neis_menu
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
    """다음 주 월~금 날짜 리스트. (KST 기준 — 러너 UTC 오차 방지)"""
    KST = datetime.timezone(datetime.timedelta(hours=9))
    today = datetime.datetime.now(KST).date()
    days = (7 - today.weekday()) % 7 or 7   # 다음 월요일까지
    monday = today + datetime.timedelta(days=days)
    return [monday + datetime.timedelta(days=i) for i in range(5)]


def gather_days(dates):
    """주간 급식 수집 — 인증키 있으면 NEIS(중식+석식 전부), 없거나 실패하면 학교사이트 폴백."""
    if os.environ.get("NEIS_KEY", "").strip():
        try:
            rng = neis_menu.fetch_range(dates[0], dates[-1])
            days = [{"date": dt.isoformat(), "weekday": neis_menu.WD[dt.weekday()],
                     "found": bool(rng.get(dt.isoformat())),
                     "meals": rng.get(dt.isoformat(), {})} for dt in dates]
            if any(d["found"] for d in days):
                print("주간: NEIS 사용")
                return days
        except Exception as e:
            print(f"NEIS 주간 오류({e}) — 학교사이트 폴백")
    print("주간: 학교사이트 사용")
    html = get_menu.fetch_html(schdt=dates[0])
    return [get_menu.parse_menu(html, dt) for dt in dates]


def build_caption(days, week_label, sched_map=None):
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

    # 다음 주 학사일정(있는 날만)
    sched_map = sched_map or {}
    sched_lines = []
    for d in days:
        evs = sched_map.get(d.get("date", ""), [])
        if evs:
            try:
                dd = datetime.date.fromisoformat(d["date"])
                dt = f"{dd.month}/{dd.day}"
            except Exception:
                dt = d.get("date", "")
            sched_lines.append(f"· {dt} {' · '.join(evs)}")
    if sched_lines:
        lines.append("")
        lines.append("🗓️ 다음 주 학사일정")
        lines.extend(sched_lines)

    lines.append("")
    lines.append("#라온고 #라온고등학교 #주간급식 #이번주급식 #급식스타그램")
    return "\n".join(lines).strip()


def main():
    dates = next_week_dates()
    week_label = f"{dates[0].month}/{dates[0].day}~{dates[-1].month}/{dates[-1].day}"
    print("다음 주:", week_label)

    days = gather_days(dates)

    any_lunch = any(d.get("meals", {}).get("중식", {}).get("items") for d in days)
    if not any_lunch:
        print("다음 주 급식 정보 없음 — 건너뜀")
        return

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump({"week_label": week_label, "days": days}, f, ensure_ascii=False, indent=2)

    render_week.render()
    url = upload_image(IMG, "week.jpg")
    print("주간 이미지 URL:", url)
    sched_map = neis_menu.schedule_range(dates[0], dates[-1])
    caption = build_caption(days, week_label, sched_map)

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

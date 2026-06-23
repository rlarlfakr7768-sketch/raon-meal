"""
NEIS(교육정보 개방 포털) 공식 Open API로 라온고 급식·학사일정 조회.
학교 홈페이지 긁기(get_menu.py)의 안정 대체재. JSON이라 파싱이 안 깨진다.
- 인증키는 환경변수 NEIS_KEY (없으면 응답 5건 샘플 제한: 하루치 중식+석식은 OK, 주간은 키 필요).
- 반환 구조는 get_menu.parse_menu 와 동일 → render_card/build_caption 그대로 사용.
"""
import os
import re
import datetime

import requests

HUB = "https://open.neis.go.kr/hub"
ATPT = "J10"        # 경기도교육청
SCHOOL = "7531294"  # 라온고등학교
H = {"User-Agent": "raon-meal-neis/1.0"}
WD = ["월", "화", "수", "목", "금", "토", "일"]


def _params(**extra):
    p = {"Type": "json", "pIndex": 1, "pSize": 100,
         "ATPT_OFCDC_SC_CODE": ATPT, "SD_SCHUL_CODE": SCHOOL}
    key = os.environ.get("NEIS_KEY", "").strip()
    if key:
        p["KEY"] = key
    p.update(extra)
    return p


def _rows(j, svc):
    if isinstance(j, dict) and svc in j:
        for blk in j[svc]:
            if isinstance(blk, dict) and "row" in blk:
                return blk["row"]
    return []


def _dishes(ddish):
    items = []
    for raw in re.split(r"<br\s*/?>", ddish or ""):
        s = re.sub(r"\s*\([\d.]+\)", "", raw)   # 알레르기 번호(숫자 괄호)만 제거
        s = s.strip()
        if s:
            items.append(s)
    return items


def fetch_day(d):
    """d=datetime.date → {date, weekday, found, meals:{끼니:{kcal,items}}}."""
    j = requests.get(f"{HUB}/mealServiceDietInfo",
                     params=_params(MLSV_YMD=d.strftime("%Y%m%d")),
                     headers=H, timeout=30).json()
    meals = {}
    for r in _rows(j, "mealServiceDietInfo"):
        meals[r.get("MMEAL_SC_NM", "")] = {
            "kcal": (r.get("CAL_INFO", "") or "").strip(),
            "items": _dishes(r.get("DDISH_NM", "")),
        }
    return {"date": d.isoformat(), "weekday": WD[d.weekday()],
            "found": bool(meals), "meals": meals}


def fetch_range(d_from, d_to):
    """주간용 — {'YYYY-MM-DD': {끼니:{kcal,items}}}. (5건 초과라 인증키 필요)"""
    j = requests.get(f"{HUB}/mealServiceDietInfo",
                     params=_params(MLSV_FROM_YMD=d_from.strftime("%Y%m%d"),
                                    MLSV_TO_YMD=d_to.strftime("%Y%m%d")),
                     headers=H, timeout=30).json()
    days = {}
    for r in _rows(j, "mealServiceDietInfo"):
        y = r.get("MLSV_YMD", "")
        iso = f"{y[:4]}-{y[4:6]}-{y[6:8]}"
        days.setdefault(iso, {})[r.get("MMEAL_SC_NM", "")] = {
            "kcal": (r.get("CAL_INFO", "") or "").strip(),
            "items": _dishes(r.get("DDISH_NM", "")),
        }
    return days


def schedule_label(d):
    """그 날 학사일정 이벤트명(휴업일/시험 등). 없으면 ''. (실패해도 빈 문자열)"""
    try:
        j = requests.get(f"{HUB}/SchoolSchedule",
                         params=_params(AA_YMD=d.strftime("%Y%m%d")),
                         headers=H, timeout=20).json()
        labels = [r.get("EVENT_NM", "") for r in _rows(j, "SchoolSchedule")]
        return " · ".join(x for x in labels if x)
    except Exception:
        return ""


if __name__ == "__main__":
    import json
    today = datetime.date.today()
    print(json.dumps(fetch_day(today), ensure_ascii=False, indent=2))
    print("학사일정:", schedule_label(today) or "(없음)")

"""
역사의 오늘: 한국어 위키백과 'M월 D일' 문서의 '사건' 목록을 가져와 정리.
(한국어판은 onthisday REST API 미지원 → 날짜 문서 wikitext를 파싱)
"""
import re
import requests

API = "https://ko.wikipedia.org/w/api.php"
H = {"User-Agent": "raon-edu/1.0 (school meal/edu bot)"}


def _clean(s):
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)          # {{틀}}
    s = re.sub(r"\[\[(?:[^\[\]|]*\|)?([^\[\]]+)\]\]", r"\1", s)  # [[링크|표시]] -> 표시
    s = re.sub(r":[a-z]{2}:([^|]+)\|", "", s)      # :en:Foo| 잔여
    s = re.sub(r"</?[^>]+>", "", s)                # html 태그
    s = re.sub(r"'''?", "", s)                     # 굵게/기울임
    s = re.sub(r"\s+", " ", s).strip()
    return s


def today_events(month, day, limit=3):
    """그날 '사건' 중 limit개를 (연도, 내용)으로 반환. 최근 사건 우선."""
    page = f"{month}월 {day}일"
    params = {"action": "parse", "page": page, "prop": "wikitext",
              "format": "json", "formatversion": "2"}
    r = requests.get(API, params=params, headers=H, timeout=40)
    r.raise_for_status()
    wt = r.json()["parse"]["wikitext"]

    m = re.search(r"==\s*사건\s*==(.*?)(?:\n==[^=]|\Z)", wt, re.S)
    sec = m.group(1) if m else ""
    events = []
    for line in sec.splitlines():
        line = line.strip()
        if not line.startswith("*"):
            continue
        body = line.lstrip("* ").strip()
        ym = re.match(r"\[\[(\d+)년?\]?\]?|^(\d{3,4})", body)
        year = None
        if ym:
            year = ym.group(1) or ym.group(2)
        # 연도와 본문 분리
        parts = re.split(r"\s[-–—]\s", body, maxsplit=1)
        text = _clean(parts[1]) if len(parts) > 1 else _clean(body)
        if year and text and len(text) > 8:
            events.append((int(year), text))

    # 학생 계정 — 자극적/지엽적 사건 제외
    block = ["살인", "자살", "강간", "성폭행", "시신", "납치", "폭행", "성추행", "엽기"]
    events = [(y, t) for (y, t) in events if not any(b in t for b in block)]
    events.sort(key=lambda e: e[0])  # 오래된 → 최근

    # 시대 다양성: 전체에서 고르게 샘플
    if len(events) > limit:
        step = len(events) / limit
        events = [events[int(i * step)] for i in range(limit)]

    picked = []
    for y, t in events:
        if len(t) > 78:
            t = t[:76].rstrip() + "…"
        picked.append({"year": y, "text": t})
    return picked


if __name__ == "__main__":
    import datetime
    d = datetime.date.today()
    for e in today_events(d.month, d.day):
        print(e["year"], "-", e["text"])

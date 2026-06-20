"""
라온고 급식 파서 -> JSON
학교 홈페이지 HTML 식단표에서 오늘 날짜의 조식/중식/석식을 긁어
구조화된 JSON(menu_today.json)으로 저장한다.
(원본 get_info.py의 Rainmeter 텍스트 출력 대신, 이미지 렌더링용 JSON을 만든다.)
"""
import sys
import os
import re
import ssl
import json
import datetime

import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

URL = "https://raon-h.goept.kr/raon-h/ad/fm/foodmenu/selectFoodMenuView.do?mi=6912"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


class FlexibleSslAdapter(HTTPAdapter):
    """학교/관공서 구형 SSL 서버 호환용 — 암호화 스위트 범위를 넓힌다."""
    def init_poolmanager(self, *args, **kwargs):
        context = ssl.create_default_context()
        # 인증서 검증은 그대로 두고, 구형 서버 호환을 위해 암호화 스위트만 넓힌다.
        try:
            context.set_ciphers("DEFAULT@SECLEVEL=1")
        except ssl.SSLError:
            context.set_ciphers("ALL")
        kwargs["ssl_context"] = context
        return super().init_poolmanager(*args, **kwargs)


def fetch_html():
    session = requests.Session()
    session.mount("https://", FlexibleSslAdapter())
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        )
    }
    # 해외(GitHub 러너)에서 학교 서버 응답이 느릴 수 있어 타임아웃을 넉넉히 + 재시도
    last_err = None
    for attempt in range(4):
        try:
            resp = session.get(URL, headers=headers, timeout=60)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
            return resp.text
        except Exception as e:
            last_err = e
            print(f"[fetch 재시도 {attempt + 1}/4] {type(e).__name__}")
    raise last_err


def parse_menu(html, target_date=None):
    if target_date is None:
        target_date = datetime.date.today()
    today_str = target_date.strftime("%Y-%m-%d")

    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("div.bbs_WriteA table")
    if table is None:
        raise RuntimeError("식단표 테이블(div.bbs_WriteA table)을 찾지 못함 — HTML 구조 변경 의심")

    # thead 헤더에서 오늘 날짜 칸 인덱스 찾기
    header_cells = table.select("thead th")
    today_col_index = None
    for i, th in enumerate(header_cells):
        if today_str in th.get_text():
            today_col_index = i
            break
    if today_col_index is None:
        return {
            "date": today_str,
            "weekday": ["월", "화", "수", "목", "금", "토", "일"][target_date.weekday()],
            "found": False,
            "meals": {},
        }

    result = {
        "date": today_str,
        "weekday": ["월", "화", "수", "목", "금", "토", "일"][target_date.weekday()],
        "found": True,
        "meals": {},
    }

    for row in table.select("tbody tr"):
        meal_th = row.select_one('th[scope="row"]')
        if meal_th is None:
            continue
        meal_type = meal_th.get_text(strip=True)  # 조식/중식/석식
        today_cell_index = today_col_index - 1     # thead엔 '구분' 칸이 있어 -1 보정
        day_cells = row.select("td")
        if today_cell_index < 0 or today_cell_index >= len(day_cells):
            continue
        cell = day_cells[today_cell_index]

        kcal_el = cell.select_one("p.fm_tit_p")
        kcal = kcal_el.get_text(strip=True) if kcal_el else ""

        menu_el = cell.select_one("div > p:last-child")
        items = []
        if menu_el:
            for raw in menu_el.stripped_strings:
                cleaned = re.sub(r"\s*\([\d\.]+\)$", "", raw).strip()
                if cleaned:
                    items.append(cleaned)

        result["meals"][meal_type] = {"kcal": kcal, "items": items}

    return result


def main():
    try:
        html = fetch_html()
        data = parse_menu(html)
        out = os.path.join(SCRIPT_DIR, "menu_today.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        print(f"\n저장됨: {out}")
    except Exception as e:
        err = os.path.join(SCRIPT_DIR, "menu_error.txt")
        with open(err, "w", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now()}\n{type(e).__name__}: {e}\n")
        print(f"[오류] {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

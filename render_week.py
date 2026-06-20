"""
menu_week.json -> 주간 요약 카드(menu_week.jpg, 1080x1350).
다음 주 월~금 중식을 한 장에 정리.
"""
import os
import sys
import json
import html as html_lib

from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(SCRIPT_DIR, "menu_week.json")
HTML_PATH = os.path.join(SCRIPT_DIR, "menu_week.html")
IMG_PATH = os.path.join(SCRIPT_DIR, "menu_week.jpg")

WD_COLOR = {"월": "#ea580c", "화": "#d97706", "수": "#65a30d",
            "목": "#0891b2", "금": "#7c3aed"}


def esc(s):
    return html_lib.escape(str(s))


def build_html(data):
    days = data.get("days", [])
    rows = []
    for d in days:
        wd = d.get("weekday", "")
        try:
            import datetime
            dd = datetime.date.fromisoformat(d["date"])
            datetxt = f"{dd.month}/{dd.day}"
        except Exception:
            datetxt = d.get("date", "")
        lunch = d.get("meals", {}).get("중식", {})
        items = lunch.get("items", [])
        menu_txt = " · ".join(items) if items else "급식 없음"
        color = WD_COLOR.get(wd, "#ea580c")
        rows.append(f"""
        <div class="day">
          <div class="dchip" style="background:{color}">{esc(wd)} <span>{esc(datetxt)}</span></div>
          <div class="dmenu">{esc(menu_txt)}</div>
        </div>""")
    rows_html = "\n".join(rows) if rows else '<div class="day"><div class="dmenu">다음 주 급식 정보가 아직 없어요</div></div>'
    week_label = esc(data.get("week_label", ""))

    return f"""<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html,body {{ width:1080px; height:1350px; }}
  body {{
    font-family:'Pretendard','Noto Sans KR','Noto Sans CJK KR','Malgun Gothic','맑은 고딕',sans-serif;
    background:linear-gradient(160deg,#fff7ed 0%,#ffedd5 45%,#fed7aa 100%);
    color:#1f2937; display:flex; flex-direction:column; padding:64px 60px;
    -webkit-font-smoothing:antialiased;
  }}
  header {{ margin-bottom:34px; }}
  .eyebrow {{ display:inline-block; font-size:26px; font-weight:700; letter-spacing:2px;
    color:#fff; background:#ea580c; padding:9px 20px; border-radius:999px; }}
  .title {{ margin-top:20px; font-size:74px; font-weight:800; color:#7c2d12; line-height:1.05; }}
  .range {{ margin-top:8px; font-size:34px; font-weight:700; color:#c2410c; }}
  .days {{ display:flex; flex-direction:column; gap:20px; flex:1; justify-content:center; }}
  .day {{ background:rgba(255,255,255,0.82); border-radius:26px; padding:26px 30px;
    border:1px solid rgba(234,88,12,0.18); box-shadow:0 12px 28px rgba(124,45,18,0.08);
    display:flex; gap:24px; align-items:flex-start; }}
  .dchip {{ flex:0 0 auto; color:#fff; font-weight:800; font-size:34px;
    padding:12px 20px; border-radius:16px; min-width:140px; text-align:center; }}
  .dchip span {{ display:block; font-size:24px; font-weight:700; opacity:.9; margin-top:2px; }}
  .dmenu {{ font-size:31px; font-weight:600; color:#292524; line-height:1.45; padding-top:4px; }}
  footer {{ margin-top:30px; text-align:center; font-size:26px; font-weight:600; color:#b45309; }}
</style></head><body>
  <header>
    <span class="eyebrow">라온고 주간 급식</span>
    <div class="title">다음 주 점심</div>
    <div class="range">{week_label}</div>
  </header>
  <div class="days">{rows_html}</div>
  <footer>· 라온고등학교 급식실 ·</footer>
</body></html>"""


def render():
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(build_html(data))
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
        page.goto("file:///" + HTML_PATH.replace("\\", "/"))
        page.wait_for_timeout(250)
        page.screenshot(path=IMG_PATH, type="jpeg", quality=92,
                        clip={"x": 0, "y": 0, "width": 1080, "height": 1350})
        browser.close()
    print("주간 이미지 생성:", IMG_PATH)


if __name__ == "__main__":
    render()

"""
menu_today.json -> HTML/CSS -> 이미지
Playwright(헤드리스 크로뮴)로 두 장을 만든다:
  - menu_card.jpg  : 피드용 4:5 (1080x1350)
  - menu_story.jpg : 스토리용 9:16 (1080x1920)
중식/석식만 카드로 표시(빈 끼니는 자동 생략).
"""
import os
import sys
import json
import datetime
import html as html_lib

from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(SCRIPT_DIR, "menu_today.json")

MEAL_ORDER = ["중식", "석식"]
MEAL_LABEL = {"중식": "중식 · LUNCH", "석식": "석식 · DINNER"}

# 피드(4:5)와 스토리(9:16) 크기 프로파일. 피드는 승인된 값 그대로 유지.
FEED = dict(
    W=1080, H=1350, html="menu_card.html", img="menu_card.jpg",
    pad="54px 64px", justify="flex-start",
    eyebrow=26, date=84, sub=28, hmargin=30,
    cgap=26, cpad="34px 44px", crad=30, chmargin=22, h2=42, kcal=26,
    ligap="13px 16px", lifont=33, lipad="13px 24px", lirad=15,
    fmargin=26, ffont=26,
)
STORY = dict(
    W=1080, H=1920, html="menu_story.html", img="menu_story.jpg",
    pad="120px 72px", justify="center",
    eyebrow=30, date=104, sub=34, hmargin=46,
    cgap=44, cpad="46px 56px", crad=40, chmargin=30, h2=54, kcal=32,
    ligap="18px 22px", lifont=42, lipad="18px 32px", lirad=20,
    fmargin=44, ffont=30,
)


def esc(s):
    return html_lib.escape(str(s))


def build_html(data, p):
    date_str = data.get("date", "")
    weekday = data.get("weekday", "")
    try:
        d = datetime.date.fromisoformat(date_str)
        date_big = f"{d.month}월 {d.day}일"
    except Exception:
        date_big = date_str

    sched = data.get("schedule", "")
    sched_html = f'<div class="sched">📅 오늘 일정 · {esc(sched)}</div>' if sched else ""

    cards = []
    for meal in MEAL_ORDER:
        m = data.get("meals", {}).get(meal)
        if not m or not m.get("items"):
            continue
        kcal = m.get("kcal", "")
        kcal_html = f'<span class="kcal">{esc(kcal)}</span>' if kcal else ""
        items_html = "".join(f"<li>{esc(it)}</li>" for it in m["items"])
        cards.append(f"""
        <section class="card">
          <div class="card-head">
            <h2>{esc(MEAL_LABEL.get(meal, meal))}</h2>
            {kcal_html}
          </div>
          <ul class="menu">{items_html}</ul>
        </section>
        """)
    if not cards:
        cards.append('<section class="card"><div class="card-head"><h2>오늘은 급식이 없어요</h2></div></section>')
    cards_html = "\n".join(cards)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html,body {{ width:{p['W']}px; height:{p['H']}px; }}
  body {{
    font-family:'Pretendard','Noto Sans KR','Noto Sans CJK KR','Malgun Gothic','맑은 고딕',sans-serif;
    background:linear-gradient(160deg,#fff7ed 0%,#ffedd5 45%,#fed7aa 100%);
    color:#1f2937; -webkit-font-smoothing:antialiased;
    display:flex; flex-direction:column;
    padding:{p['pad']};
  }}
  header {{ margin-bottom:{p['hmargin']}px; }}
  .eyebrow {{
    display:inline-block; font-size:{p['eyebrow']}px; font-weight:700; letter-spacing:2px;
    color:#fff; background:#ea580c; padding:9px 20px; border-radius:999px;
  }}
  .date {{ margin-top:22px; font-size:{p['date']}px; font-weight:800; line-height:1.05; color:#7c2d12; }}
  .weekday {{ font-size:{p['date']}px; font-weight:800; color:#ea580c; }}
  .sub {{ margin-top:10px; font-size:{p['sub']}px; font-weight:600; color:#9a3412; }}
  .sched {{ margin-top:14px; display:inline-block; font-size:{p['sub']}px; font-weight:700;
    color:#9a3412; background:rgba(234,88,12,0.12); border:1px solid rgba(234,88,12,0.28);
    padding:8px 18px; border-radius:14px; }}

  .cards {{ display:flex; flex-direction:column; gap:{p['cgap']}px; flex:1; justify-content:{p['justify']}; }}
  .card {{
    background:rgba(255,255,255,0.80); border-radius:{p['crad']}px; padding:{p['cpad']};
    box-shadow:0 16px 36px rgba(124,45,18,0.10); border:1px solid rgba(234,88,12,0.18);
  }}
  .card-head {{ display:flex; align-items:baseline; justify-content:space-between; margin-bottom:{p['chmargin']}px; }}
  .card-head h2 {{ font-size:{p['h2']}px; font-weight:800; color:#9a3412; letter-spacing:1px; }}
  .kcal {{ font-size:{p['kcal']}px; font-weight:700; color:#c2410c; background:#ffedd5; padding:7px 18px; border-radius:999px; }}
  ul.menu {{ list-style:none; display:flex; flex-wrap:wrap; gap:{p['ligap']}; }}
  ul.menu li {{
    font-size:{p['lifont']}px; font-weight:600; color:#292524;
    background:#fff; padding:{p['lipad']}; border-radius:{p['lirad']}px; border:1px solid #fde4cf;
  }}
  footer {{ margin-top:{p['fmargin']}px; text-align:center; font-size:{p['ffont']}px; font-weight:600; color:#b45309; }}
</style>
</head>
<body>
  <header>
    <span class="eyebrow">라온고 오늘의 급식</span>
    <div class="date">{esc(date_big)} <span class="weekday">{esc(weekday)}요일</span></div>
    <div class="sub">맛있게 드세요! 🍱</div>
    {sched_html}
  </header>
  <div class="cards">
    {cards_html}
  </div>
  <footer>· 라온고등학교 급식실 ·</footer>
</body>
</html>"""


def render_one(page, data, p):
    html_path = os.path.join(SCRIPT_DIR, p["html"])
    img_path = os.path.join(SCRIPT_DIR, p["img"])
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(build_html(data, p))
    page.set_viewport_size({"width": p["W"], "height": p["H"]})
    page.goto("file:///" + html_path.replace("\\", "/"))
    page.wait_for_timeout(250)
    page.screenshot(path=img_path, type="jpeg", quality=92,
                    clip={"x": 0, "y": 0, "width": p["W"], "height": p["H"]})
    print(f"이미지 생성됨: {img_path}")


def render():
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(device_scale_factor=1)
        render_one(page, data, FEED)
        render_one(page, data, STORY)
        browser.close()


if __name__ == "__main__":
    render()

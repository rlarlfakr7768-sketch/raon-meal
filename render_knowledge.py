"""
knowledge_today.json(오늘 카드 1개) -> 지식 카드 이미지(knowledge.jpg, 1080x1350).
급식과 구분되는 남색 테마.
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
JSON_PATH = os.path.join(SCRIPT_DIR, "knowledge_today.json")
HTML_PATH = os.path.join(SCRIPT_DIR, "knowledge.html")
IMG_PATH = os.path.join(SCRIPT_DIR, "knowledge.jpg")


def esc(s):
    return html_lib.escape(str(s))


def build_html(card):
    return f"""<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html,body {{ width:1080px; height:1350px; }}
  body {{
    font-family:'Pretendard','Noto Sans KR','Noto Sans CJK KR','Malgun Gothic','맑은 고딕',sans-serif;
    background:linear-gradient(160deg,#0f172a 0%,#1e1b4b 55%,#312e81 100%);
    color:#e5e7eb; -webkit-font-smoothing:antialiased;
    display:flex; flex-direction:column; padding:90px 80px;
  }}
  .chip {{ align-self:flex-start; font-size:28px; font-weight:700; letter-spacing:2px;
    color:#0f172a; background:#fcd34d; padding:10px 24px; border-radius:999px; }}
  .emoji {{ font-size:150px; line-height:1; margin-top:50px; }}
  .title {{ margin-top:28px; font-size:78px; font-weight:800; line-height:1.18; color:#fff; }}
  .hook {{ margin-top:26px; font-size:40px; font-weight:700; color:#a5b4fc; line-height:1.35; }}
  .body {{ margin-top:34px; font-size:40px; font-weight:500; line-height:1.62; color:#e5e7eb; }}
  .spacer {{ flex:1; }}
  footer {{ text-align:center; font-size:30px; font-weight:700; color:#818cf8; letter-spacing:1px; }}
</style></head><body>
  <div class="chip">{esc(card.get('cat',''))} · 오늘의 지식</div>
  <div class="emoji">{esc(card.get('emoji',''))}</div>
  <div class="title">{esc(card.get('title',''))}</div>
  <div class="hook">{esc(card.get('hook',''))}</div>
  <div class="body">{esc(card.get('body',''))}</div>
  <div class="spacer"></div>
  <footer>라온고 · 더 알아보기 phyedu.net</footer>
</body></html>"""


def render():
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        card = json.load(f)
    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(build_html(card))
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
        page.goto("file:///" + HTML_PATH.replace("\\", "/"))
        page.wait_for_timeout(250)
        page.screenshot(path=IMG_PATH, type="jpeg", quality=92,
                        clip={"x": 0, "y": 0, "width": 1080, "height": 1350})
        browser.close()
    print("지식 이미지 생성:", IMG_PATH)


if __name__ == "__main__":
    render()

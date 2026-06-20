"""
news_today.json(헤드라인/요약/출처) + news_photo.jpg(Pexels 사진)
-> news_card.jpg (1080x1350 사진 카드, 사진 위 굵은 한글 헤드라인)
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
JSON_PATH = os.path.join(SCRIPT_DIR, "news_today.json")
HTML_PATH = os.path.join(SCRIPT_DIR, "news.html")
IMG_PATH = os.path.join(SCRIPT_DIR, "news_card.jpg")
PHOTO = "news_photo.jpg"  # 같은 폴더, 상대경로


def esc(s):
    return html_lib.escape(str(s))


def build_html(card):
    return f"""<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@500;700;900&display=swap" rel="stylesheet">
<style>
  *{{margin:0;padding:0;box-sizing:border-box;}}
  html,body{{width:1080px;height:1350px;}}
  body{{font-family:'Noto Sans KR',sans-serif;position:relative;overflow:hidden;
    -webkit-font-smoothing:antialiased;}}
  .bg{{position:absolute;inset:0;background:#0e0d12 url('{PHOTO}') center/cover no-repeat;}}
  .shade{{position:absolute;inset:0;
    background:linear-gradient(to bottom, rgba(8,8,12,.30) 0%, rgba(8,8,12,.05) 32%, rgba(8,8,12,.55) 68%, rgba(8,8,12,.92) 100%);}}
  .wrap{{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:space-between;
    padding:70px 72px 76px;}}
  .label{{align-self:flex-start;font-size:30px;font-weight:900;letter-spacing:.04em;
    color:#fff;background:#ff5a4d;padding:13px 26px;border-radius:999px;
    box-shadow:0 6px 20px rgba(0,0,0,.35);}}
  .label span{{opacity:.85;font-weight:700;margin-left:8px;letter-spacing:.18em;}}
  .bottom{{}}
  h1{{font-weight:900;font-size:84px;line-height:1.22;color:#fff;letter-spacing:-.01em;
    text-shadow:0 4px 24px rgba(0,0,0,.6);}}
  .meta{{margin-top:30px;font-size:30px;font-weight:700;color:#ffd9d4;
    text-shadow:0 2px 10px rgba(0,0,0,.6);}}
  .credit{{margin-top:10px;font-size:22px;font-weight:500;color:rgba(255,255,255,.6);}}
</style></head><body>
  <div class="bg"></div>
  <div class="shade"></div>
  <div class="wrap">
    <div class="label">오늘의 과학뉴스<span>SCIENCE</span></div>
    <div class="bottom">
      <h1>{esc(card.get('headline',''))}</h1>
      <div class="credit">자세한 내용은 캡션에서 →</div>
    </div>
  </div>
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
        page.wait_for_timeout(2200)
        page.screenshot(path=IMG_PATH, type="jpeg", quality=92,
                        clip={"x": 0, "y": 0, "width": 1080, "height": 1350})
        browser.close()
    print("뉴스 카드 생성:", IMG_PATH)


if __name__ == "__main__":
    render()

"""
ITFIND 주간기술동향 카드 — 스톡사진 없이 에디토리얼 다크 디자인.
phyedu.net 톤(잉크블랙 #0e0d12 + 코랄 #ff6f61 + Noto Serif KR 제목).
추상적 기술 주제라 스톡사진이 안 맞아서, 타이포 중심 카드로 간다.
"""
import os
import sys
import html as html_lib
from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

HEAD = """<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@600;700;900&family=Noto+Sans+KR:wght@500;700;900&display=swap" rel="stylesheet">
<style>
  *{margin:0;padding:0;box-sizing:border-box;}
  html,body{width:1080px;height:1350px;}
  body{font-family:'Noto Sans KR',sans-serif;background:#0e0d12;-webkit-font-smoothing:antialiased;}
  .card{position:absolute;inset:0;overflow:hidden;background:
    radial-gradient(1200px 720px at 82% -12%, rgba(255,111,97,.16), transparent 60%),
    radial-gradient(960px 640px at -8% 112%, rgba(86,98,132,.14), transparent 60%),
    #0e0d12;}
  .grid{position:absolute;inset:0;opacity:.55;
    background-image:radial-gradient(rgba(255,255,255,.055) 1.4px, transparent 1.4px);
    background-size:48px 48px;}
  .ghost{position:absolute;right:34px;bottom:-110px;font-weight:900;font-size:580px;
    line-height:1;color:rgba(255,111,97,.07);}
  .pad{position:absolute;inset:0;padding:100px 92px;display:flex;flex-direction:column;
    justify-content:space-between;}
  .top{display:flex;justify-content:space-between;align-items:center;}
  .label{background:#ff6f61;color:#0e0d12;font-weight:900;font-size:31px;
    padding:14px 28px;border-radius:999px;letter-spacing:.01em;}
  .num{font-weight:900;font-size:42px;color:rgba(255,255,255,.38);}
  .mid{margin:auto 0;}
  .kicker{color:#ff8276;font-weight:700;font-size:35px;letter-spacing:.07em;margin-bottom:30px;}
  .rule{width:74px;height:7px;background:#ff6f61;border-radius:4px;margin-bottom:44px;}
  .title{font-family:'Noto Serif KR',serif;font-weight:900;font-size:74px;line-height:1.32;
    color:#f5f3ef;letter-spacing:-.01em;}
  .foot{color:rgba(255,255,255,.44);font-weight:500;font-size:28px;}
</style></head><body>"""


def esc(s):
    return html_lib.escape(str(s))


def build_html(title, idx, total, issue):
    return (HEAD +
            '<div class="card"><div class="grid"></div>'
            f'<div class="ghost">{idx}</div>'
            '<div class="pad">'
            f'<div class="top"><div class="label">주간기술동향 {esc(issue)}호</div>'
            f'<div class="num">{idx} / {total}</div></div>'
            '<div class="mid"><div class="kicker">이주의 IT 트렌드</div>'
            '<div class="rule"></div>'
            f'<div class="title">{esc(title)}</div></div>'
            f'<div class="foot">정보통신기획평가원(IITP) 주간기술동향 {esc(issue)}호</div>'
            '</div></div></body></html>')


def render(items, issue):
    paths = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1350},
                                device_scale_factor=1)
        total = len(items)
        for i, it in enumerate(items):
            htmlp = os.path.join(SCRIPT_DIR, f"_itf_{i:02d}.html")
            imgp = os.path.join(SCRIPT_DIR, f"itf_card_{i:02d}.jpg")
            with open(htmlp, "w", encoding="utf-8") as f:
                f.write(build_html(it["title"], i + 1, total, issue))
            page.goto("file:///" + htmlp.replace("\\", "/"))
            page.wait_for_timeout(1800)
            page.screenshot(path=imgp, type="jpeg", quality=92,
                            clip={"x": 0, "y": 0, "width": 1080, "height": 1350})
            paths.append(imgp)
        browser.close()
    return paths

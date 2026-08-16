"""
과학뉴스 카드 렌더 — 항목 리스트를 받아 사진카드 여러 장(news_card_NN.jpg)을 만든다.
각 카드 = Pexels 사진 배경 + 굵은 한글 헤드라인 + 1~2문장 핵심.
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
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@500;700;900&display=swap" rel="stylesheet">
<style>
  *{margin:0;padding:0;box-sizing:border-box;}
  html,body{width:1080px;height:1350px;}
  body{font-family:'Noto Sans KR',sans-serif;position:relative;overflow:hidden;-webkit-font-smoothing:antialiased;}
  .bg{position:absolute;inset:0;background:#0e0d12 center/cover no-repeat;}
  .shade{position:absolute;inset:0;background:linear-gradient(to bottom,rgba(8,8,12,.28) 0%,rgba(8,8,12,.04) 30%,rgba(8,8,12,.6) 66%,rgba(8,8,12,.94) 100%);}
  .wrap{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:space-between;padding:70px 72px 80px;}
  .top{display:flex;justify-content:space-between;align-items:center;}
  .label{font-size:29px;font-weight:900;letter-spacing:.03em;color:#fff;background:#ff5a4d;padding:12px 24px;border-radius:999px;box-shadow:0 6px 20px rgba(0,0,0,.35);}
  .num{font-size:56px;font-weight:900;color:rgba(255,255,255,.85);text-shadow:0 3px 14px rgba(0,0,0,.6);}
  .bottom h1{font-weight:900;font-size:80px;line-height:1.22;color:#fff;letter-spacing:-.01em;text-shadow:0 4px 22px rgba(0,0,0,.6);}
  .blurb{margin-top:26px;font-size:38px;font-weight:500;line-height:1.5;color:#f0ede6;text-shadow:0 2px 12px rgba(0,0,0,.65);}
  .subject{margin-top:30px;display:inline-block;font-size:28px;font-weight:700;letter-spacing:.01em;
           color:#ffb3a7;border-left:5px solid #ff5a4d;padding:4px 0 4px 18px;
           text-shadow:0 2px 10px rgba(0,0,0,.7);}
</style></head><body>"""


def esc(s):
    return html_lib.escape(str(s))


def build_html(item, idx, total, label="오늘의 과학뉴스", head_size=80):
    """사진 위에 헤드라인, 그 아래 한 줄 요약, 맨 아래 교과 연결을 얹는다.
    한 줄 요약과 교과 연결은 없으면 그냥 빠진다(itfind 등 다른 호출과 호환)."""
    photo = item.get("photo", "")
    head = esc(item.get("headline", ""))
    if len(item.get("headline", "")) > 20:      # 긴 제목은 조금 줄여 세 줄을 넘기지 않게
        head_size = int(head_size * 0.88)

    blurb = item.get("blurb", "").strip()
    subject = item.get("subject", "").strip()
    extra = ""
    if blurb:
        extra += f'<div class="blurb">{esc(blurb)}</div>'
    if subject:
        extra += f'<div><div class="subject">{esc(subject)}</div></div>'

    return (HEAD +
            f'<div class="bg" style="background-image:url(\'{photo}\')"></div>'
            '<div class="shade"></div><div class="wrap">'
            f'<div class="top"><div class="label">{esc(label)}</div>'
            f'<div class="num">{idx}/{total}</div></div>'
            f'<div class="bottom"><h1 style="font-size:{head_size}px">'
            f'{head}</h1>{extra}</div>'
            '</div></body></html>')


def render(items, label="오늘의 과학뉴스", head_size=80, height=1350, prefix="news_card"):
    """세로 1350이면 피드 4:5, 1920이면 스토리 9:16이다."""
    paths = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": height},
                                device_scale_factor=1)
        total = len(items)
        for i, it in enumerate(items):
            htmlp = os.path.join(SCRIPT_DIR, f"_{prefix}_{i:02d}.html")
            imgp = os.path.join(SCRIPT_DIR, f"{prefix}_{i:02d}.jpg")
            with open(htmlp, "w", encoding="utf-8") as f:
                f.write(build_html(it, i + 1, total, label, head_size)
                        .replace("height:1350px", f"height:{height}px"))
            page.goto("file:///" + htmlp.replace("\\", "/"))
            page.wait_for_timeout(2000)
            page.screenshot(path=imgp, type="jpeg", quality=92,
                            clip={"x": 0, "y": 0, "width": 1080, "height": height})
            paths.append(imgp)
        browser.close()
    return paths

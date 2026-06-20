"""
캐러셀 슬라이드 렌더러 — 에디토리얼 다크 템플릿(잉크블랙+코랄+세리프).
render(slides) -> img/slide_01.jpg ... 를 만들고 경로 리스트 반환.
각 slide = {kind, idx, ...}.  kind: cover|std|history|quote|vocab|quiz|answer
"""
import os
import html as html_lib
from playwright.sync_api import sync_playwright

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IMGDIR = os.path.join(SCRIPT_DIR, "img")
CIRC = {0: "①", 1: "②", 2: "③", 3: "④", 4: "⑤"}

HEAD = """<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@600;800&family=Noto+Sans+KR:wght@400;500;700&display=swap" rel="stylesheet">
<style>
  :root{--ink:#0e0d12;--paper:#f4f1ea;--coral:#ff6f61;--muted:#8b919b;}
  *{margin:0;padding:0;box-sizing:border-box;}
  html,body{width:1080px;height:1350px;}
  body{background:var(--ink);color:var(--paper);font-family:'Noto Sans KR',sans-serif;
    padding:92px 88px 78px;position:relative;display:flex;flex-direction:column;
    -webkit-font-smoothing:antialiased;}
  .index{position:absolute;top:74px;right:88px;font-family:'Noto Serif KR',serif;
    font-weight:800;font-size:120px;color:rgba(255,255,255,.07);line-height:1;}
  .kicker{font-size:29px;font-weight:700;letter-spacing:.3em;text-transform:uppercase;color:var(--coral);}
  .kicker .ko{color:var(--paper);letter-spacing:.08em;margin-right:14px;}
  h1{font-family:'Noto Serif KR',serif;font-weight:800;font-size:112px;line-height:1.13;
    letter-spacing:-.01em;margin-top:96px;color:#fff;}
  h1 em{color:var(--coral);font-style:normal;}
  .rule{width:118px;height:6px;background:var(--coral);margin:48px 0 44px;}
  .body{font-size:43px;font-weight:400;line-height:1.68;color:#d7d4cc;max-width:900px;}
  .spacer{flex:1;}
  footer{display:flex;justify-content:space-between;align-items:center;
    border-top:1px solid rgba(255,255,255,.12);padding-top:32px;
    font-size:27px;color:var(--muted);font-weight:500;letter-spacing:.03em;}
  footer b{color:var(--paper);font-weight:700;}
  /* cover */
  .cover h1{font-size:170px;margin-top:80px;line-height:1.05;}
  .datel{font-size:46px;font-weight:700;color:#d7d4cc;margin-top:6px;}
  .dday{display:inline-block;margin-top:40px;font-size:40px;font-weight:800;color:var(--ink);
    background:var(--coral);padding:14px 34px;border-radius:999px;letter-spacing:.02em;}
  /* history */
  .events{margin-top:70px;display:flex;flex-direction:column;gap:46px;}
  .ev{display:flex;gap:34px;align-items:baseline;}
  .evy{font-family:'Noto Serif KR',serif;font-weight:800;font-size:62px;color:var(--coral);
    flex:0 0 auto;min-width:170px;}
  .evt{font-size:40px;font-weight:500;line-height:1.45;color:#e7e4dc;}
  .src{margin-top:54px;font-size:26px;color:var(--muted);}
  /* quote */
  blockquote{font-family:'Noto Serif KR',serif;font-weight:600;font-size:88px;line-height:1.32;
    color:#fff;margin-top:120px;letter-spacing:-.01em;}
  .qauthor{margin-top:50px;font-size:44px;font-weight:700;color:var(--coral);}
  /* quiz */
  .q h1,h1.q{font-size:78px;line-height:1.25;}
  .choices{list-style:none;margin-top:60px;display:flex;flex-direction:column;gap:26px;counter-reset:c;}
  .choices li{font-size:46px;font-weight:600;color:#e7e4dc;display:flex;gap:24px;align-items:flex-start;}
  .choices li::before{counter-increment:c;content:counter(c);font-family:'Noto Serif KR',serif;
    font-weight:800;color:var(--coral);min-width:50px;}
  .hint{margin-top:60px;font-size:34px;font-weight:700;color:var(--muted);letter-spacing:.04em;}
  /* answer */
  .ans{font-family:'Noto Serif KR',serif;font-weight:800;font-size:104px;color:#fff;margin-top:100px;}
  .ans em{color:var(--coral);font-style:normal;}
  .cheer{font-family:'Noto Serif KR',serif;font-weight:600;font-size:50px;line-height:1.5;
    color:var(--coral);}
</style></head><body class="{cls}">"""

FOOT = """<div class="spacer"></div><footer><span>{fl}</span><b>{fr}</b></footer></body></html>"""


def esc(s):
    return html_lib.escape(str(s))


def _emph(title, em):
    if em and em in title:
        return esc(title).replace(esc(em), f"<em>{esc(em)}</em>")
    return esc(title)


def build_html(s):
    kind = s["kind"]
    idx = f"{s.get('idx', 0):02d}"
    fl, fr = "라온고 · 오늘의 지식", "phyedu.net"
    cls = "cover" if kind == "cover" else ("q" if kind == "quiz" else "")
    head = HEAD.replace("{cls}", cls)
    inner = f'<div class="index">{idx}</div>'

    if kind == "cover":
        inner += (f'<div class="kicker"><span class="ko">라온고 데일리</span></div>'
                  f'<h1>오늘의<br><em>지식</em></h1>'
                  f'<div class="rule"></div>'
                  f'<div class="datel">{esc(s["date"])} · {esc(s["weekday"])}요일</div>')
        if s.get("dday"):
            inner += f'<div class="dday">{esc(s["dday"])}</div>'
    elif kind == "history":
        inner += '<div class="kicker"><span class="ko">역사의 오늘</span> On this day</div>'
        inner += '<div class="events">'
        for e in s["events"]:
            inner += f'<div class="ev"><span class="evy">{esc(e["year"])}</span><span class="evt">{esc(e["text"])}</span></div>'
        inner += '</div><div class="src">출처 · 위키백과</div>'
    elif kind == "quote":
        inner += '<div class="kicker"><span class="ko">오늘의 명언</span> Quote</div>'
        inner += f'<blockquote>“{esc(s["text"])}”</blockquote>'
        inner += f'<div class="qauthor">— {esc(s["author"])}</div>'
    elif kind == "quiz":
        inner += '<div class="kicker"><span class="ko">오늘의 퀴즈</span> Quiz</div>'
        inner += f'<h1 class="q">{esc(s["q"])}</h1><ul class="choices">'
        for c in s["choices"]:
            inner += f'<li>{esc(c)}</li>'
        inner += '</ul><div class="hint">정답은 다음 장에서 →</div>'
    elif kind == "answer":
        inner += '<div class="kicker"><span class="ko">정답 &amp; 응원</span></div>'
        inner += f'<div class="ans">정답 <em>{CIRC.get(s["answer"], "")}</em></div>'
        inner += f'<div class="rule"></div><div class="body">{esc(s["explain"])}</div>'
        inner += f'<div class="rule"></div><div class="cheer">“{esc(s["cheer"])}”</div>'
    else:  # std / vocab
        ko = s.get("ko", "")
        en = s.get("en", "")
        inner += f'<div class="kicker"><span class="ko">{esc(ko)}</span> {esc(en)}</div>'
        inner += f'<h1>{_emph(s["title"], s.get("em", ""))}</h1>'
        inner += f'<div class="rule"></div><div class="body">{esc(s["body"])}</div>'

    return head + inner + FOOT.replace("{fl}", fl).replace("{fr}", fr)


def render(slides):
    os.makedirs(IMGDIR, exist_ok=True)
    paths = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
        for s in slides:
            htmlp = os.path.join(SCRIPT_DIR, f"_card_{s['idx']:02d}.html")
            imgp = os.path.join(IMGDIR, f"slide_{s['idx']:02d}.jpg")
            with open(htmlp, "w", encoding="utf-8") as f:
                f.write(build_html(s))
            page.goto("file:///" + htmlp.replace("\\", "/"))
            page.wait_for_timeout(2200)
            page.screenshot(path=imgp, type="jpeg", quality=92,
                            clip={"x": 0, "y": 0, "width": 1080, "height": 1350})
            paths.append(imgp)
        browser.close()
    return paths

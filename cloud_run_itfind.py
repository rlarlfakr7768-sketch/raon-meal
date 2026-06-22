"""
이주의 IT 트렌드 — IITP 주간기술동향 최신호를 카드 캐러셀로 게시(phyedu_net).
주간 레터: 매주 일요일 실행, 같은 호는 재게시 안 함(itfind_last.txt 추적).
AI 미사용 — 공공누리 제2유형(출처표시+비상업적)이라 공식 초록을 그대로 싣는다.
흐름: 최신호 수집(제목+공식 초록) → 키워드로 Pexels 사진 → 카드 렌더 → 캐러셀.
"""
import os
import sys
import subprocess

import itfind_fetch
import render_itfind
import publish_ig
from cloud_run import upload_images

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MARKER = os.path.join(SCRIPT_DIR, "itfind_last.txt")
TARGETS = ["phyedu_net"]
CAP_LIMIT = 2150  # 인스타 캡션 한도(2,200) 여유


def build_caption(articles, issue):
    """캡션 본문(공식 초록 그대로)을 한도 안에서 채우고, 실린 기사 수도 반환."""
    nums = "①②③④⑤⑥⑦⑧⑨⑩"
    header = [f"📡 이주의 IT 트렌드 · 주간기술동향 {issue}호",
              "이번 주 핵심 기술 동향을 정리했어요. 넘겨보세요 →", ""]
    footer = ["📖 각 기사 전문 해설은 phyedu.net ‘ICT 동향 브리핑’ 에서 (위 링크).",
              "#IT트렌드 #인공지능 #반도체 #과학기술 #고등학생 #진로 #라온고", "",
              f"📌 출처: 정보통신기획평가원(IITP) 주간기술동향 {issue}호 (공공누리 제2유형)"]
    base = len("\n".join(header)) + len("\n".join(footer)) + 4
    body, used, n = [], base, 0
    for i, a in enumerate(articles):
        mark = nums[i] if i < len(nums) else f"{i+1}."
        block = f"{mark} {a['title']}\n{a['abstract']}\n→ https://phyedu.net/ict-trend/ict-{issue}-{i+1:02d}\n"
        if used + len(block) > CAP_LIMIT:
            break
        body.append(block)
        used += len(block) + 1
        n += 1
    return "\n".join(header + body + footer), n


def last_issue():
    if os.path.exists(MARKER):
        with open(MARKER, encoding="utf-8") as f:
            return f.read().strip()
    return ""


def mark_issue(issue):
    """이번 호를 기록·커밋(다음 실행에서 중복 게시 방지)."""
    with open(MARKER, "w", encoding="utf-8") as f:
        f.write(issue)

    def git(*a):
        return subprocess.run(["git", *a], cwd=SCRIPT_DIR,
                              capture_output=True, text=True)

    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email",
        "41898282+github-actions[bot]@users.noreply.github.com")
    git("add", "itfind_last.txt")
    c = git("commit", "-m", f"itfind {issue}호 게시 [skip ci]")
    if c.returncode == 0:
        git("push")


def main():
    issue, articles = itfind_fetch.fetch()
    if not articles:
        print("ITFIND 수집 실패 — 건너뜀")
        return
    if issue and issue == last_issue():
        print(f"주간기술동향 {issue}호 이미 게시함 — 건너뜀")
        return

    caption, n = build_caption(articles, issue)
    items = articles[:max(1, n)]
    print(f"주간기술동향 {issue}호 · 기사 {len(articles)}건 중 {len(items)}건 게시")

    paths = render_itfind.render(items, issue)
    pairs = [(p, f"itf_{i:02d}.jpg") for i, p in enumerate(paths)]
    urls = upload_images(pairs)
    print(f"호스팅 {len(urls)}장")

    posted = False
    for label in TARGETS:
        try:
            publish_ig.post_carousel(label, urls, caption)
            posted = True
        except Exception as e:
            print(f"[{label}] 캐러셀 게시 실패: {e}")

    if posted and issue:
        mark_issue(issue)

    for label in TARGETS:
        try:
            publish_ig.refresh_token(label)
        except Exception as e:
            print(f"[{label}] 토큰 갱신 스킵: {e}")


if __name__ == "__main__":
    main()

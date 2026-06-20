"""
이주의 IT 트렌드 — IITP 주간기술동향 최신호를 카드 캐러셀로 게시(phyedu_net).
흐름: 최신호 수집(초록) → gpt-5-mini가 학생용 원작성 요약 → Pexels 사진 →
     사진카드 렌더 → 캐러셀 게시. 같은 호는 재게시 안 함(itfind_last.txt 추적).
라이선스: 공공누리 제2유형 → 출처표시 필수(캡션에 자동 명시) + 비상업적.
"""
import os
import sys
import json
import subprocess

import requests

import itfind_fetch
import render_news
import publish_ig
from cloud_run import upload_images
from cloud_run_news import fetch_photo

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MARKER = os.path.join(SCRIPT_DIR, "itfind_last.txt")
TARGETS = ["phyedu_net"]
OPENAI_MODEL = "gpt-5-mini"
N_ITEMS = 5

SYS_PROMPT = "너는 한국 고등학생용 과학·기술 인스타그램 편집자다."
USER_TMPL = (
    "아래는 IITP 주간기술동향 최신호 기사들의 제목과 초록이다. 각 기사를 학생이 흥미를 갖도록 "
    "JSON으로 정리하라. items 배열, 각 항목은:\n"
    "- headline: 한국어 헤드라인(낚시·과장 금지, 24자 이내)\n"
    "- summary: 한국어 3~4문장으로 이 기술 트렌드가 무엇이고 왜 중요한지 고등학생이 "
    "배경지식 없이 이해하게 풀어라. 초록 내용을 바탕으로 하되 모든 문장을 네 말로 완전히 "
    "새로 쓰고, 초록에 없는 수치·사실·해석은 추가하지 마라(불확실하면 생략).\n"
    "- photo_query: 내용에 맞는 영어 스톡사진 검색어(2~4단어)\n"
    'JSON만: {"items":[{"headline":"","summary":"","photo_query":""}]}\n\n'
    "기사:\n{items}"
)


def curate(articles):
    key = os.environ["OPENAI_API_KEY"]
    lines = [f"{i+1}. 제목: {a['title']}\n   초록: {a['abstract']}"
             for i, a in enumerate(articles)]
    body = USER_TMPL.replace("{items}", "\n".join(lines))
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": OPENAI_MODEL,
              "messages": [{"role": "system", "content": SYS_PROMPT},
                           {"role": "user", "content": body}],
              "response_format": {"type": "json_object"}},
        timeout=120,
    ).json()
    if "choices" not in r:
        raise RuntimeError(f"OpenAI 응답 오류: {r}")
    return json.loads(r["choices"][0]["message"]["content"]).get("items", [])


def build_caption(items, issue):
    nums = "①②③④⑤⑥⑦⑧⑨⑩"
    lines = [f"📡 이주의 IT 트렌드 · 주간기술동향 {issue}호",
             "넘겨보세요 →", ""]
    for i, it in enumerate(items):
        mark = nums[i] if i < len(nums) else f"{i+1}."
        lines.append(f"{mark} {it.get('headline','')}")
        lines.append(it.get("summary", ""))
        lines.append("")
    lines += ["#IT트렌드 #인공지능 #반도체 #과학기술 #고등학생 #진로 #라온고",
              "",
              f"📌 출처: 정보통신기획평가원(IITP) 주간기술동향 {issue}호 (공공누리 제2유형)"]
    return "\n".join(lines)


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
    articles = articles[:N_ITEMS]
    print(f"주간기술동향 {issue}호 · 기사 {len(articles)}건 → 요약…")
    items = curate(articles)
    if not items:
        print("요약 결과 없음 — 건너뜀")
        return
    print(f"요약 {len(items)}건")

    for i, it in enumerate(items):
        photo = os.path.join(SCRIPT_DIR, f"itf_photo_{i:02d}.jpg")
        fetch_photo(it.get("photo_query") or "technology", photo)
        it["photo"] = f"itf_photo_{i:02d}.jpg"

    paths = render_news.render(items, label=f"주간기술동향 {issue}호")
    pairs = [(p, f"itf_{i:02d}.jpg") for i, p in enumerate(paths)]
    urls = upload_images(pairs)
    print(f"호스팅 {len(urls)}장")

    caption = build_caption(items, issue)
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

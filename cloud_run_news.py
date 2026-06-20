"""
오늘의 과학뉴스 TOP 10 (캐러셀 1게시물) — phyedu_net.
흐름: 해외 과학매체 RSS 수집 → OpenAI(gpt-5-mini)가 다양한 10건 선별 +
     각 항목 한국어 '원작성' 짧은 요약 + 사진 검색어 → Pexels 사진 10장
     → 사진카드 10장 렌더 → 캐러셀 게시.
저작권: 본문 전재 X. 요약은 모델이 자기 말로 새로. 출처는 캡션에. 사진=Pexels.
"""
import os
import sys
import json
import datetime

import requests

import news_fetch
import render_news
import publish_ig
from cloud_run import upload_images

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(SCRIPT_DIR, "news_today.json")
TARGETS = ["phyedu_net"]
OPENAI_MODEL = "gpt-5-mini"
N_ITEMS = 10

SYS_PROMPT = "너는 한국 고등학생용 과학 인스타그램 편집자다."
USER_TMPL = (
    f"아래 과학뉴스 후보에서 가장 흥미롭고 정확하며 학생에게 적절한 {N_ITEMS}건을 "
    "골라(주제가 겹치지 않게 다양하게) JSON으로. items 배열로 출력하고, 각 항목은:\n"
    "- headline: 한국어 헤드라인(낚시·과장 금지, 24자 이내)\n"
    "- blurb: 한국어 1~2문장으로 핵심을 '네 말로 완전히 새로' 써라. 원문 표현·구조를 "
    "따르지 말고, 기사에 없는 수치·인용·해석은 추가하지 마라(불확실하면 생략).\n"
    "- source: 후보의 출처명 그대로\n"
    "- photo_query: 내용에 맞는 영어 스톡사진 검색어(2~4단어)\n"
    'JSON만: {"items":[{"headline":"","blurb":"","source":"","photo_query":""}]}\n\n'
    "후보:\n{items}"
)


def curate(items):
    key = os.environ["OPENAI_API_KEY"]
    lines = [f"{i+1}. [{it['source']}] {it['title']} | {it['desc']}"
             for i, it in enumerate(items)]
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
    data = json.loads(r["choices"][0]["message"]["content"])
    return data.get("items", [])[:N_ITEMS]


def fetch_photo(query, dest):
    key = os.environ["PEXELS_API_KEY"]
    def search(q):
        return requests.get("https://api.pexels.com/v1/search",
                            headers={"Authorization": key},
                            params={"query": q, "per_page": 12,
                                    "orientation": "portrait", "size": "large"},
                            timeout=30).json().get("photos", [])
    photos = search(query) or search("science") or search("laboratory")
    if not photos:
        raise RuntimeError(f"Pexels 결과 없음: {query}")
    idx = (datetime.date.today().toordinal()) % len(photos)
    src = photos[idx]["src"]
    url = src.get("large2x") or src.get("large") or src.get("portrait")
    with open(dest, "wb") as f:
        f.write(requests.get(url, timeout=60).content)


def build_caption(items):
    today = datetime.date.today()
    lines = [f"📰 오늘의 과학뉴스 TOP {len(items)} · {today.month}/{today.day}", "",
             "한 장씩 넘겨보세요 →", ""]
    for i, it in enumerate(items, 1):
        lines.append(f"{i}. {it.get('headline','')} ({it.get('source','')})")
    lines += ["", "#과학뉴스 #오늘의과학 #science #고등학생 #라온고 #과학상식 #지식스타그램",
              "", "📷 사진 Pexels · 출처는 각 매체"]
    return "\n".join(lines)


def main():
    cands = news_fetch.fetch(limit_per=12)
    if not cands:
        print("뉴스 수집 실패 — 건너뜀")
        return
    print(f"후보 {len(cands)}건 → OpenAI가 TOP {N_ITEMS} 선별…")
    items = curate(cands)
    if not items:
        print("선별 결과 없음 — 건너뜀")
        return
    print(f"선별 {len(items)}건")

    for i, it in enumerate(items):
        photo = os.path.join(SCRIPT_DIR, f"news_photo_{i:02d}.jpg")
        fetch_photo(it.get("photo_query") or "science", photo)
        it["photo"] = f"news_photo_{i:02d}.jpg"

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump({"items": items}, f, ensure_ascii=False, indent=2)
    paths = render_news.render(items)

    pairs = [(p, f"news_{i:02d}.jpg") for i, p in enumerate(paths)]
    urls = upload_images(pairs)
    print(f"호스팅 {len(urls)}장")

    caption = build_caption(items)
    for label in TARGETS:
        try:
            publish_ig.post_carousel(label, urls, caption)
        except Exception as e:
            print(f"[{label}] 캐러셀 게시 실패: {e}")
    for label in TARGETS:
        try:
            publish_ig.refresh_token(label)
        except Exception as e:
            print(f"[{label}] 토큰 갱신 스킵: {e}")


if __name__ == "__main__":
    main()

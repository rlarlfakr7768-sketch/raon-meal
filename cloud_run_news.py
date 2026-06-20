"""
오늘의 과학뉴스 (낱장 사진카드) — phyedu_net 게시.
흐름: 해외 과학매체 RSS 수집 → OpenAI가 1건 선별 + 한국어 '원작성' 요약 + 사진 검색어
     → Pexels 사진 → 사진카드 렌더 → 공식 API 게시.
저작권: 본문 전재 X. 요약은 모델이 자기 말로 새로 작성, 출처/링크 명시. 사진=Pexels 라이선스.
"""
import os
import sys
import json
import datetime

import requests

import news_fetch
import render_news
import publish_ig
from cloud_run import upload_image

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(SCRIPT_DIR, "news_today.json")
PHOTO_PATH = os.path.join(SCRIPT_DIR, "news_photo.jpg")
CARD = os.path.join(SCRIPT_DIR, "news_card.jpg")

TARGETS = ["phyedu_net"]
OPENAI_MODEL = "gpt-4o-mini"

SYS_PROMPT = (
    "너는 한국 고등학생 대상 과학 인스타그램의 편집자다. 최신 과학뉴스 후보(제목/짧은설명/출처/링크, 주로 영어)를 받아 처리한다."
)
USER_TMPL = (
    "다음 후보 중에서:\n"
    "1) 가장 흥미롭고 정확하며 고등학생에게 적절한 과학뉴스 1건만 고른다(광고·낚시·비과학·정치성 제외).\n"
    "2) 눈길 끄는 한국어 헤드라인(22자 이내, 과장·낚시 금지).\n"
    "3) 한국어 요약을 '네 말로 새로' 쓴다(2~3문장, 120~170자). 원문을 번역·복붙·부분수정 하지 말고 핵심을 학생이 이해하게 풀어라.\n"
    "4) 관련 스톡사진 영어 검색어(2~4단어).\n"
    "5) 출처명과 링크는 후보에 있던 값을 그대로 유지.\n"
    'JSON만 출력: {"headline":"","summary":"","source":"","link":"","photo_query":""}\n\n'
    "후보:\n{items}"
)


def curate(items):
    key = os.environ["OPENAI_API_KEY"]
    lines = []
    for i, it in enumerate(items):
        lines.append(f"{i+1}. [{it['source']}] {it['title']} | {it['desc']} | {it['link']}")
    body = USER_TMPL.replace("{items}", "\n".join(lines))
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": OPENAI_MODEL,
              "messages": [{"role": "system", "content": SYS_PROMPT},
                           {"role": "user", "content": body}],
              "response_format": {"type": "json_object"}, "temperature": 0.5},
        timeout=90,
    ).json()
    if "choices" not in r:
        raise RuntimeError(f"OpenAI 응답 오류: {r}")
    return json.loads(r["choices"][0]["message"]["content"])


def fetch_photo(query):
    key = os.environ["PEXELS_API_KEY"]
    def search(q):
        return requests.get("https://api.pexels.com/v1/search",
                            headers={"Authorization": key},
                            params={"query": q, "per_page": 15,
                                    "orientation": "portrait", "size": "large"},
                            timeout=30).json().get("photos", [])
    photos = search(query) or search("science laboratory") or search("space science")
    if not photos:
        raise RuntimeError("Pexels 사진 검색 결과 없음")
    idx = datetime.date.today().toordinal() % len(photos)
    src = photos[idx]["src"]
    url = src.get("large2x") or src.get("large") or src.get("portrait") or src.get("original")
    img = requests.get(url, timeout=60).content
    with open(PHOTO_PATH, "wb") as f:
        f.write(img)


def build_caption(card):
    return (f"{card.get('summary','')}\n\n"
            f"📰 출처 · {card.get('source','')}\n"
            f"🔗 원문: {card.get('link','')}\n\n"
            "#과학뉴스 #오늘의과학 #과학 #science #고등학생 #라온고 #과학상식 #지식스타그램")


def main():
    items = news_fetch.fetch()
    if not items:
        print("뉴스 수집 실패 — 건너뜀")
        return
    print(f"후보 {len(items)}건 → OpenAI 선별…")
    card = curate(items)
    print("선정:", card.get("headline"))

    fetch_photo(card.get("photo_query") or "science")
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(card, f, ensure_ascii=False, indent=2)
    render_news.render()

    url = upload_image(CARD, "news.jpg")
    print("이미지 URL:", url)
    caption = build_caption(card)
    for label in TARGETS:
        try:
            publish_ig.post(label, url, caption, is_story=False)
        except Exception as e:
            print(f"[{label}] 뉴스 게시 실패: {e}")
    for label in TARGETS:
        try:
            publish_ig.refresh_token(label)
        except Exception as e:
            print(f"[{label}] 토큰 갱신 스킵: {e}")


if __name__ == "__main__":
    main()

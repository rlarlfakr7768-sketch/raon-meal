"""오늘의 과학뉴스 TOP 5 (캐러셀 1게시물) — phyedu_net.
흐름: 해외 과학매체 RSS 수집 → OpenAI(gpt-5-mini)가 겹치지 않게 5건 선별 +
     각 항목 한국어 '원작성' 요약 + 사진 검색어 → Pexels 사진 5장
     → 사진카드 5장 렌더 → 캐러셀 게시.
저작권: 본문 전재 X. 요약은 모델이 자기 말로 새로. 사진=Pexels.
캡션 2,200자 한도가 있어 항목 수는 5건으로 묶어 두고, 넘치면 뒤에서부터 문장을 줄인다.
최근에 다룬 사건은 news_recent.json(커밋됨)으로 기억해 다시 고르지 않는다.
"""
import os
import re
import sys
import json
import datetime
import subprocess

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
RECENT_PATH = os.path.join(SCRIPT_DIR, "news_recent.json")
TARGETS = ["phyedu_net"]
OPENAI_MODEL = "gpt-5-mini"
N_ITEMS = 5
RECENT_DAYS = 10          # 며칠치 게시 이력을 기억해 중복 선택을 막을지
CAP_LIMIT = 2150          # 인스타 캡션 한도 2,200자에 여유를 둔 값

SYS_PROMPT = "너는 한국 고등학생용 과학 인스타그램 편집자다."
USER_TMPL = (
    f"아래 과학뉴스 후보에서 가장 흥미롭고 정확하며 학생에게 적절한 {N_ITEMS}건을 "
    "골라(주제가 겹치지 않게 다양하게) JSON으로. items 배열로 출력하고, 각 항목은:\n"
    "- id: 후보 앞에 붙은 번호(정수)\n"
    "- headline: 한국어 헤드라인(낚시·과장 금지, 24자 이내)\n"
    "- summary: 한국어 3~4문장으로 뉴스 핵심을 충실히. 무엇을·어떻게·왜 중요한지 "
    "고등학생이 배경지식 없이도 이해하게 풀어라. 단 모든 문장은 원문 표현·구조를 따르지 말고 "
    "네 말로 완전히 새로 쓰고, 후보에 없는 수치·인용·해석은 추가하지 마라(불확실하면 생략). "
    "단위를 바꿔 새 수치를 만들지도 마라.\n"
    "- source: 후보의 출처명 그대로\n"
    "- photo_query: 내용에 맞는 영어 스톡사진 검색어(2~4단어). 추상어 말고 찍을 수 있는 "
    "구체적 피사체로(예: telescope dome night, coral reef fish).\n"
    "연구 성과, 관측, 발견을 우선하고 인사·행사·정책·구인 같은 소식은 고르지 마라.\n"
    'JSON만: {"items":[{"id":0,"headline":"","summary":"","source":"","photo_query":""}]}\n\n'
    "{recent}"
    "후보:\n{items}"
)


def load_recent():
    if os.path.exists(RECENT_PATH):
        try:
            with open(RECENT_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def recent_block(recent):
    heads = [h for day in recent for h in day.get("headlines", [])]
    if not heads:
        return ""
    lines = "\n".join(f"- {h}" for h in heads[-40:])
    return ("최근에 이미 올린 것들이다. 같은 사건이나 같은 연구는 다시 고르지 마라.\n"
            f"{lines}\n\n")


def remember(items, today):
    """오늘 다룬 헤드라인을 남기고 커밋(다음 날 중복 선택 방지)."""
    recent = load_recent()
    recent = [d for d in recent if d.get("date") != today][-(RECENT_DAYS - 1):]
    recent.append({"date": today,
                   "headlines": [it.get("headline", "") for it in items],
                   "titles": [it.get("_src_title", "") for it in items]})
    with open(RECENT_PATH, "w", encoding="utf-8") as f:
        json.dump(recent, f, ensure_ascii=False, indent=1)

    def git(*a):
        return subprocess.run(["git", *a], cwd=SCRIPT_DIR,
                              capture_output=True, text=True)

    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email",
        "41898282+github-actions[bot]@users.noreply.github.com")
    git("add", "news_recent.json")
    if git("commit", "-m", f"news {today} 이력 [skip ci]").returncode == 0:
        if git("push").returncode != 0:
            git("pull", "--rebase")
            git("push")


def curate(items, recent):
    key = os.environ["OPENAI_API_KEY"]
    lines = [f"{i}. [{it['source']}] {it['title']} | {it['desc']}"
             for i, it in enumerate(items)]
    body = (USER_TMPL.replace("{recent}", recent_block(recent))
                     .replace("{items}", "\n".join(lines)))
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": OPENAI_MODEL,
              "messages": [{"role": "system", "content": SYS_PROMPT},
                           {"role": "user", "content": body}],
              "response_format": {"type": "json_object"}},
        timeout=180,
    ).json()
    if "choices" not in r:
        raise RuntimeError(f"OpenAI 응답 오류: {r}")
    data = json.loads(r["choices"][0]["message"]["content"])
    out = data.get("items", [])[:N_ITEMS]

    # 고른 후보의 원문을 항목에 붙여 둔다(수치 점검·이력 기록용).
    for it in out:
        i = it.get("id")
        if isinstance(i, int) and 0 <= i < len(items):
            it["_src_title"] = items[i]["title"]
            it["_src_text"] = items[i]["title"] + " " + items[i]["desc"]
            it["link"] = items[i].get("link", "")
    return out


NUM = re.compile(r"\d[\d,\.]*")


def check_numbers(items):
    """요약에 나온 수치가 원문에도 있는지 훑어본다.

    단위를 바꾼 표현(300,000 km → 30만)까지 잡지는 못하므로 막지는 않고 기록만 한다.
    로그에 자주 뜨는 항목이 있으면 그때 프롬프트를 손보면 된다.
    """
    for it in items:
        src = (it.get("_src_text") or "").replace(",", "")
        bad = [n for n in NUM.findall(it.get("summary", ""))
               if len(n.replace(",", "").replace(".", "")) >= 2
               and n.replace(",", "") not in src]
        if bad:
            print(f"  [수치 확인] {it.get('headline','')[:20]} … 원문에 없는 숫자 {bad}")


def fetch_photo(query, dest, used):
    key = os.environ["PEXELS_API_KEY"]

    def search(q):
        return requests.get("https://api.pexels.com/v1/search",
                            headers={"Authorization": key},
                            params={"query": q, "per_page": 15,
                                    "orientation": "portrait", "size": "large"},
                            timeout=30).json().get("photos", [])

    photos = search(query) or search("science") or search("laboratory")
    if not photos:
        raise RuntimeError(f"Pexels 결과 없음: {query}")
    start = datetime.date.today().toordinal() % len(photos)
    pick = None
    for k in range(len(photos)):                 # 같은 게시물 안에서 사진이 겹치지 않게
        cand = photos[(start + k) % len(photos)]
        if cand.get("id") not in used:
            pick = cand
            break
    pick = pick or photos[start]
    used.add(pick.get("id"))
    src = pick["src"]
    url = src.get("large2x") or src.get("large") or src.get("portrait")
    with open(dest, "wb") as f:
        f.write(requests.get(url, timeout=60).content)


def _trim_sentence(text):
    """마지막 문장을 덜어낸다."""
    parts = re.split(r"(?<=[.!?다요])\s+", text.strip())
    return " ".join(parts[:-1]).strip() if len(parts) > 1 else text[:-40].strip()


def build_caption(items):
    today = datetime.date.today()
    nums = "①②③④⑤⑥⑦⑧⑨⑩"
    sums = [it.get("summary", "") for it in items]

    def assemble(sums):
        lines = [f"📰 오늘의 과학뉴스 · {today.month}/{today.day}",
                 "넘겨보고, 자세한 내용은 아래 ↓", ""]
        for i, it in enumerate(items):
            mark = nums[i] if i < len(nums) else f"{i+1}."
            lines.append(f"{mark} {it.get('headline','')}")
            lines.append(sums[i])
            lines.append("")
        lines += ["#과학뉴스 #오늘의과학 #science #고등학생 #라온고 #과학상식 #지식스타그램"]
        return "\n".join(lines)

    cap = assemble(sums)
    while len(cap) > CAP_LIMIT:            # 한도를 넘으면 가장 긴 요약부터 한 문장씩
        j = max(range(len(sums)), key=lambda k: len(sums[k]))
        if len(sums[j]) < 40:
            cap = cap[:CAP_LIMIT]
            break
        sums[j] = _trim_sentence(sums[j])
        cap = assemble(sums)
    return cap


def main():
    cands = news_fetch.fetch(limit_per=10)
    if not cands:
        print("뉴스 수집 실패 — 건너뜀")
        return
    recent = load_recent()
    print(f"후보 {len(cands)}건 → OpenAI가 TOP {N_ITEMS} 선별…")
    items = curate(cands, recent)
    if not items:
        print("선별 결과 없음 — 건너뜀")
        return
    print(f"선별 {len(items)}건")
    check_numbers(items)

    used = set()
    for i, it in enumerate(items):
        photo = os.path.join(SCRIPT_DIR, f"news_photo_{i:02d}.jpg")
        fetch_photo(it.get("photo_query") or "science", photo, used)
        it["photo"] = f"news_photo_{i:02d}.jpg"

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump({"items": items}, f, ensure_ascii=False, indent=2)
    paths = render_news.render(items)

    pairs = [(p, f"news_{i:02d}.jpg") for i, p in enumerate(paths)]
    urls = upload_images(pairs)
    print(f"호스팅 {len(urls)}장")

    caption = build_caption(items)
    print(f"캡션 {len(caption)}자")
    posted = False
    for label in TARGETS:
        try:
            publish_ig.post_carousel(label, urls, caption)
            posted = True
        except Exception as e:
            print(f"[{label}] 캐러셀 게시 실패: {e}")
    if posted:
        try:
            remember(items, datetime.date.today().isoformat())
        except Exception as e:
            print(f"이력 기록 실패(게시는 됨): {e}")

    for label in TARGETS:
        try:
            publish_ig.refresh_token(label)
        except Exception as e:
            print(f"[{label}] 토큰 갱신 스킵: {e}")


if __name__ == "__main__":
    main()

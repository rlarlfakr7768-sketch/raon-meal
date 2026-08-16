"""과학뉴스 수집 — 신뢰도 높은 해외 과학매체 RSS에서 최신 헤드라인을 모은다.
(저작권: 제목/짧은 설명/링크/출처만 수집. 본문 전재 안 함. 요약은 AI가 원작성.)

같은 연구를 여러 매체가 동시에 보도하는 일이 잦아, 제목이 겹치는 후보는 앞선 매체 것만 남긴다.
"""
import re
import requests
import xml.etree.ElementTree as ET

# 순서가 곧 우선순위다(겹치는 기사는 위쪽 매체 것을 남긴다).
FEEDS = [
    ("Nature", "https://www.nature.com/nature.rss"),
    ("Quanta", "https://api.quantamagazine.org/feed/"),
    ("Science News", "https://www.sciencenews.org/feed"),
    ("ScienceDaily", "https://www.sciencedaily.com/rss/top/science.xml"),
    ("Phys.org", "https://phys.org/rss-feed/"),
    ("NASA", "https://www.nasa.gov/news-release/feed/"),
    ("ESA", "https://www.esa.int/rssfeed/Our_Activities/Space_Science"),
]
H = {"User-Agent": "Mozilla/5.0 (raon-edu science digest)"}
ATOM = "{http://www.w3.org/2005/Atom}"

# 기사가 아닌 것들. Nature 피드는 정정문과 서평이, NASA 피드는 사진 소개와 행사 공지가 섞여 온다.
SKIP_PAT = re.compile(
    r"^(author correction|publisher correction|retraction|erratum|correction|"
    r"apod\b|news & views|obituary|editorial expression)", re.I)
SKIP_ANY = re.compile(
    r"(books in brief|briefing chat|daily briefing|podcast|book review)", re.I)
# Nature 설명은 'Nature, Published online: ...; doi:...' 로 시작한다. 알맹이만 남긴다.
BOILER = re.compile(r"^\s*Nature[^;]*;\s*doi:\S+\s*", re.I)

# 제목 비교에서 빼는 흔한 단어
STOP = {"the", "and", "for", "with", "from", "that", "this", "new", "how", "why",
        "what", "into", "study", "researchers", "scientists", "first", "could",
        "may", "can", "than", "more", "have", "has", "are", "was", "were"}


def _clean(s):
    s = re.sub(r"<[^>]+>", "", s or "")
    s = re.sub(r"\s+", " ", s).strip()
    return s[:500]


def _local(tag):
    """{네임스페이스}item 에서 item 만."""
    return tag.rsplit("}", 1)[-1]


def _entries(root):
    """RSS 2.0(item), RSS 1.0/RDF(네임스페이스 붙은 item), Atom(entry)을 모두 훑는다.
    Nature 피드가 RDF라, 네임스페이스를 안 벗기면 조용히 0건이 된다."""
    out = [el for el in root.iter() if _local(el.tag) in ("item", "entry")]
    return out


def _child(el, *names):
    for ch in el:
        if _local(ch.tag) in names:
            if ch.text and ch.text.strip():
                return ch.text
            # Atom 의 link 는 href 속성에 들어 있다
            if ch.get("href"):
                return ch.get("href")
    return ""


def _words(title):
    return {w for w in re.findall(r"[a-z]{4,}", title.lower()) if w not in STOP}


def _is_dup(words, seen_words):
    """제목 단어가 절반 넘게 겹치면 같은 사건으로 본다."""
    for prev in seen_words:
        if not prev or not words:
            continue
        overlap = len(words & prev) / min(len(words), len(prev))
        if overlap >= 0.6:
            return True
    return False


def fetch(limit_per=10):
    items, seen_words = [], []
    for source, url in FEEDS:
        try:
            r = requests.get(url, headers=H, timeout=25)
            root = ET.fromstring(r.content)
            got = 0
            for it in _entries(root):
                if got >= limit_per:
                    break
                title = _clean(_child(it, "title"))
                desc = _clean(_child(it, "description", "summary", "content",
                                     "encoded"))
                link = _clean(_child(it, "link", "guid"))
                if not title or SKIP_PAT.match(title) or SKIP_ANY.search(title):
                    continue
                desc = BOILER.sub("", desc)
                w = _words(title)
                if _is_dup(w, seen_words):
                    continue
                seen_words.append(w)
                items.append({"source": source, "title": title,
                              "desc": desc, "link": link})
                got += 1
        except Exception as e:
            print(f"[feed err] {source}: {str(e)[:120]}")
    return items


if __name__ == "__main__":
    got = fetch(6)
    print(f"후보 {len(got)}건")
    for it in got:
        print(f"[{it['source']}] {it['title'][:70]}")

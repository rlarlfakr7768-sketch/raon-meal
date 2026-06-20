"""
과학뉴스 수집 — 신뢰도 높은 해외 과학매체 RSS에서 최신 헤드라인을 모은다.
(저작권: 제목/짧은 설명/링크/출처만 수집. 본문 전재 안 함. 요약은 AI가 원작성.)
"""
import re
import requests
import xml.etree.ElementTree as ET

FEEDS = [
    ("ScienceDaily", "https://www.sciencedaily.com/rss/top/science.xml"),
    ("Phys.org", "https://phys.org/rss-feed/"),
    ("Nature", "https://www.nature.com/nature.rss"),
]
H = {"User-Agent": "Mozilla/5.0 (raon-edu science digest)"}


def _clean(s):
    s = re.sub(r"<[^>]+>", "", s or "")
    s = re.sub(r"\s+", " ", s).strip()
    return s[:280]


def fetch(limit_per=10):
    items = []
    for source, url in FEEDS:
        try:
            r = requests.get(url, headers=H, timeout=25)
            root = ET.fromstring(r.content)
            for it in root.findall(".//item")[:limit_per]:
                title = _clean(it.findtext("title"))
                desc = _clean(it.findtext("description"))
                link = (it.findtext("link") or "").strip()
                if title:
                    items.append({"source": source, "title": title,
                                  "desc": desc, "link": link})
        except Exception as e:
            print(f"[feed err] {source}: {e}")
    return items


if __name__ == "__main__":
    for it in fetch(3):
        print(f"[{it['source']}] {it['title']}")

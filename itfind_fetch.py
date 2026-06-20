"""
ITFIND 주간기술동향(정보통신기획평가원 IITP 발간) 최신호 수집.
라이선스: 공공누리 제2유형(출처표시 + 비상업적). 본문 전재 안 함 —
목록 페이지의 '초록'만 받아 AI가 학생용으로 원작성 요약한다.
"""
import re
import requests

URL = "https://www.itfind.or.kr/trend/weekly/latestWeekly.do"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

ART = re.compile(
    r'<h6 class="searchresulttitle"><a href="([^"]+)"[^>]*>(.*?)</a></h6>\s*'
    r'<p class="searchresulsentence">(.*?)</p>', re.S)


def _clean(s):
    s = re.sub(r"<[^>]+>", "", s or "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def fetch():
    """(issue, [{title, abstract, link}, ...]) 반환."""
    t = requests.get(URL, headers=H, timeout=30).text
    m = re.search(r"주간기술동향\s*(\d{3,4})\s*호", t)
    issue = m.group(1) if m else ""
    items = []
    seen = set()
    for href, title, abstract in ART.findall(t):
        title = re.sub(r"\s*\[주간기술동향[^\]]*\]", "", _clean(title)).strip()
        abstract = _clean(abstract)
        if title and abstract and title not in seen:
            seen.add(title)
            items.append({"title": title, "abstract": abstract, "link": href.strip()})
    return issue, items


if __name__ == "__main__":
    iss, its = fetch()
    print(f"주간기술동향 {iss}호 · 기사 {len(its)}건")
    for it in its:
        print(f"- {it['title']}\n    {it['abstract'][:80]}…")

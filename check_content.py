"""오늘의 지식 콘텐츠 검사기 — content*.json 전부를 규칙대로 훑는다.

생성기(gen_content.py)가 항목마다 부르고, 사람이 직접 돌려 전수 점검도 한다.

    python check_content.py            # 전체 검사 + 통계
    python check_content.py --quiet    # 오류만

카드가 HTML 이스케이프로 그려지므로 마크다운·수식 기호는 화면에 그대로 노출된다.
그래서 문법 기호는 오류로 잡는다.
"""
import os
import re
import sys
import glob
import json
import unicodedata
from collections import Counter

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 카드 레이아웃이 감당하는 범위. 기존 60일치 실측(최소~최대)에 여유를 조금 붙였다.
LIMITS = {
    "physics": {"title": (4, 20), "body": (65, 135)},
    "math":    {"title": (4, 20), "body": (65, 135)},
    "science": {"title": (4, 20), "body": (65, 135)},
    "study":   {"title": (4, 20), "body": (65, 135)},
    "vocab":   {"word":  (2, 20), "body": (40, 125)},
    "quotes":  {"text":  (8, 52), "author": (2, 24)},
    "quiz":    {"q": (6, 32), "explain": (20, 75), "choice": (1, 22)},
    "cheer":   {"text": (12, 38)},
}

FIELDS = {
    "physics": ("title", "em", "body"),
    "math": ("title", "em", "body"),
    "science": ("title", "em", "body"),
    "study": ("title", "em", "body"),
    "vocab": ("word", "body"),
    "quotes": ("text", "author"),
    "quiz": ("q", "choices", "answer", "explain"),
}

# 화면에 그대로 찍히면 곤란한 것들
BAD_CHARS = {
    "—": "엠대시(줄표)",
    "–": "엔대시",
    "“": "곧은따옴표가 아닌 영문 겹따옴표",
    "”": "영문 겹따옴표",
    "$": "수식 기호",
    "\\": "역슬래시",
    "*": "마크다운 강조",
    "_": "마크다운 강조",
    "#": "마크다운 제목",
    "`": "백틱",
}
MIDDOT = "·"
EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF←-⇿⬀-⯿]"
)
# 가운뎃점이 두 번 이상 이어지면 열거다(A·B·C). '작용·반작용'처럼 굳은 짝은 봐준다.
MIDDOT_LIST = re.compile(r"[가-힣]" + MIDDOT + r"[가-힣]+" + MIDDOT + r"[가-힣]")


def norm(s):
    """중복 비교용 정규화 — 공백과 문장부호를 털어낸다."""
    s = unicodedata.normalize("NFKC", str(s))
    return re.sub(r"[\s,.!?'\"()\[\]{}:;~\-]", "", s)


def norm_loose(s):
    """보기끼리 비교용 — 공백만 턴다(9.8 과 98 을 같게 보면 안 된다)."""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(s)))


def _len_err(cat, field, value, key=None):
    lo, hi = LIMITS[cat][key or field]
    n = len(value)
    if n < lo or n > hi:
        return [f"{field} 길이 {n}자 (허용 {lo}~{hi})"]
    return []


def _text_err(field, value):
    errs = []
    for ch, why in BAD_CHARS.items():
        if ch in value:
            errs.append(f"{field}에 {why} '{ch}'")
    if EMOJI.search(value):
        errs.append(f"{field}에 이모지")
    if MIDDOT_LIST.search(value):
        errs.append(f"{field}에 열거용 가운뎃점")
    if re.search(r"\s{2,}", value):
        errs.append(f"{field}에 연속 공백")
    if value != value.strip():
        errs.append(f"{field} 앞뒤 공백")
    return errs


def validate(cat, item):
    """항목 하나를 검사해 오류 문구 목록을 돌려준다. 빈 목록이면 통과."""
    errs = []

    if cat == "cheer":
        if not isinstance(item, str):
            return ["응원은 문자열이어야 함"]
        return _len_err("cheer", "응원", item, key="text") + _text_err("응원", item)

    if not isinstance(item, dict):
        return ["항목이 객체가 아님"]

    need = FIELDS.get(cat)
    if not need:
        return [f"모르는 카테고리 {cat}"]
    for f in need:
        if f not in item:
            errs.append(f"{f} 없음")
    if errs:
        return errs

    if cat in ("physics", "math", "science", "study"):
        errs += _len_err(cat, "title", item["title"])
        errs += _len_err(cat, "body", item["body"])
        errs += _text_err("title", item["title"]) + _text_err("body", item["body"])
        if len(item.get("em", "")) > 12:
            errs.append(f"em 길이 {len(item['em'])}자 (12자 이내)")
    elif cat == "vocab":
        errs += _len_err(cat, "word", item["word"])
        errs += _len_err(cat, "body", item["body"])
        errs += _text_err("word", item["word"]) + _text_err("body", item["body"])
    elif cat == "quotes":
        errs += _len_err(cat, "text", item["text"])
        errs += _len_err(cat, "author", item["author"])
        errs += _text_err("명언", item["text"])
        if item["author"].strip() in ("", "미상", "작자 미상", "unknown"):
            errs.append("출처 없는 명언은 싣지 않음")
    elif cat == "quiz":
        ch = item["choices"]
        if not isinstance(ch, list) or len(ch) != 3:
            errs.append("보기는 정확히 3개")
        else:
            for c in ch:
                errs += _len_err(cat, "보기", str(c), key="choice")
            if len(set(norm_loose(c) for c in ch)) != 3:
                errs.append("보기가 서로 겹침")
        if not isinstance(item["answer"], int) or not 0 <= item["answer"] <= 2:
            errs.append("정답은 0~2 정수")
        errs += _len_err(cat, "q", item["q"])
        errs += _len_err(cat, "explain", item["explain"])
        errs += _text_err("문제", item["q"]) + _text_err("해설", item["explain"])

    return errs


def key_of(cat, item):
    """중복 판정 기준값."""
    if cat == "cheer":
        return norm(item)
    if cat == "quotes":
        return norm(item["text"])
    if cat == "vocab":
        return norm(item["word"])
    if cat == "quiz":
        return norm(item["q"])
    return norm(item["title"])


def load_all(pattern="content*.json"):
    """카테고리별로 (파일명, 인덱스, 항목) 목록을 모은다."""
    pools = {}
    for path in sorted(glob.glob(os.path.join(SCRIPT_DIR, pattern))):
        name = os.path.basename(path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for cat, items in data.items():
            for i, it in enumerate(items):
                pools.setdefault(cat, []).append((name, i, it))
    return pools


def main():
    quiet = "--quiet" in sys.argv
    pools = load_all()
    if not pools:
        print("content*.json 을 찾지 못했다")
        return 1

    total_err = 0
    for cat in sorted(pools):
        rows = pools[cat]
        seen = {}
        errs = []
        for name, i, it in rows:
            for e in validate(cat, it):
                errs.append(f"  [{name}#{i}] {e}")
            try:
                k = key_of(cat, it)
            except Exception:
                continue
            if k in seen:
                errs.append(f"  [{name}#{i}] 중복 — {seen[k]} 와 같음")
            else:
                seen[k] = f"{name}#{i}"

        extra = ""
        if cat == "quiz":
            dist = Counter(it["answer"] for _, _, it in rows
                           if isinstance(it.get("answer"), int))
            extra = "  정답 분포 " + " ".join(f"{k}번 {dist.get(k, 0)}" for k in (0, 1, 2))
            worst = min(dist.get(k, 0) for k in (0, 1, 2))
            if worst < len(rows) * 0.2:
                errs.append(f"  정답 위치가 한쪽으로 쏠림 {dict(dist)} "
                            "(세 자리가 고르게 나와야 학생이 찍지 못한다)")

        total_err += len(errs)
        if not quiet or errs:
            days = len(rows)
            print(f"{cat:8s} {days:4d}개 ({days}일치){extra}")
            for e in errs:
                print(e)

    print()
    print("검사 통과" if total_err == 0 else f"오류 {total_err}건")
    return 1 if total_err else 0


if __name__ == "__main__":
    sys.exit(main())

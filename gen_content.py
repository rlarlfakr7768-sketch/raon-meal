"""오늘의 지식 콘텐츠 대량 생성 — 카테고리마다 목표 개수를 채워 content3.json 에 쌓는다.

하루에 카테고리당 한 개씩 쓰이므로 '개수 = 일수'다. 목표는 기존 content*.json 을 포함한
총량이다. 기본값 420 = 이미 있는 60일치 + 새로 360일치.
이미 만든 만큼은 건너뛰고 모자란 만큼만 채우므로, 중간에 끊겨도 다시 돌리면 이어진다.

    python gen_content.py                    # 카테고리당 총 420개(=360일치 추가)
    python gen_content.py 120                # 목표를 총 120개로
    python gen_content.py --only=quiz,vocab  # 일부 카테고리만
    python gen_content.py --dry-run          # 세 개만 만들어 화면에 뿌리고 끝

키는 환경변수로 받는다. OPENAI_API_KEY 가 있으면 gpt-5-mini,
DEEPSEEK_API_KEY 만 있으면 deepseek-chat 을 쓴다(같은 형식의 API라 코드는 하나).
검사는 check_content.validate 를 그대로 쓰므로, 검사기를 고치면 생성 기준도 같이 바뀐다.
"""
import os
import sys
import json
import time
import random

import requests

import check_content as chk

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(SCRIPT_DIR, "content3.json")
DEFAULT_TARGET = 420       # 기존 60일치 + 새 360일치
BATCH = 12                 # 한 번에 요청할 항목 수
MAX_ROUNDS = 60            # 카테고리당 요청 횟수 상한(무한루프 방지)

COMMON_RULES = """공통 규칙
- 읽는 사람은 한국 고등학생이다. 존댓말 설명체로 쓰되 교과서처럼 담백하게.
- 사실만 쓴다. 확실하지 않은 수치나 일화는 아예 빼라. 지어내면 안 된다.
- "A가 아니라 B다" 식 대조 문장을 반복해서 쓰지 마라. 한 항목에 많아야 한 번.
- 화면에 그대로 찍히므로 다음은 금지: 이모지, 마크다운(**, #, `), 수식 기호($, \\),
  엠대시(—), 영문 겹따옴표. 열거는 가운뎃점 말고 쉼표로. (작용·반작용처럼 굳은 한 단어는 괜찮다)
- 수식은 말로 풀어 쓴다. 예: "제곱에 비례합니다", "1초에 약 30만 킬로미터".
- 한 항목은 그 자체로 완결되어야 한다. 다른 항목을 가리키는 말("앞에서 본") 금지.
- 항목끼리 소재가 겹치면 안 된다. 아래 '이미 쓴 것'과도 겹치면 안 된다.
"""

SPECS = {
    "physics": {
        "name": "물리상식",
        "shape": '{"title":"14자 이내 제목","em":"제목에서 강조할 짧은 조각(제목 안의 말 그대로)","body":"70~130자 설명"}',
        "extra": ("일상에서 겪는 현상을 물리로 풀어 준다. 역학, 열, 파동과 소리, 빛과 광학, "
                  "전기와 자기, 유체, 천체, 현대물리를 고루 섞어라. 고등학교 교육과정 밖 개념은 "
                  "이름만 빌리지 말고 직관으로 설명하라."),
        "seeds": ["역학과 운동", "열과 에너지", "소리와 파동", "빛과 색", "전기와 자기",
                  "물과 공기의 흐름", "우주와 천체", "현대물리와 원자", "스포츠 속 물리",
                  "교통수단 속 물리", "부엌과 집 안의 물리", "몸에서 일어나는 물리"],
    },
    "math": {
        "name": "수학상식",
        "shape": '{"title":"14자 이내 제목","em":"제목 안의 짧은 조각","body":"70~130자 설명"}',
        "extra": ("계산 요령이 아니라 '왜 그렇게 되는가'를 보여 준다. 수, 도형, 확률과 통계, "
                  "함수, 무한, 수학사, 실생활 셈을 고루 섞어라. 숫자가 나오면 반드시 검산해서 "
                  "맞는 값만 써라."),
        "seeds": ["수와 연산의 성질", "도형과 공간", "확률", "통계와 자료 해석", "함수와 그래프",
                  "무한과 극한", "수학사 속 인물", "암산과 어림", "규칙과 수열", "경우의 수",
                  "일상 속 비율", "증명의 아이디어"],
    },
    "science": {
        "name": "과학상식",
        "shape": '{"title":"14자 이내 제목","em":"제목 안의 짧은 조각","body":"70~130자 설명"}',
        "extra": ("화학, 생명과학, 지구과학, 기술을 다룬다(물리는 다른 항목에서 다루므로 피하라). "
                  "몸, 음식, 날씨, 동식물, 재료, 환경처럼 손에 잡히는 소재로."),
        "seeds": ["몸과 건강", "음식과 요리 속 화학", "날씨와 기후", "동물의 감각", "식물과 광합성",
                  "지구 내부와 지진", "바다와 물", "원소와 물질", "미생물과 면역", "재료와 기술",
                  "환경과 에너지", "우주 탐사"],
    },
    "study": {
        "name": "공부법",
        "shape": '{"title":"14자 이내 제목","em":"제목 안의 짧은 조각","body":"70~130자 설명"}',
        "extra": ("인지심리학에서 근거가 확인된 학습법만 쓴다(인출연습, 분산학습, 교차연습, "
                  "정교화, 자기설명, 수면, 오답 관리 등). 유형별 학습양식처럼 근거가 없는 통념은 "
                  "쓰지 말고, 통념을 다룰 거면 왜 근거가 약한지 알려 주는 쪽으로."),
        "seeds": ["인출연습", "복습 간격", "교차연습", "오답노트", "집중과 방해 요소", "수면과 기억",
                  "노트 필기", "시험 전략", "동기와 습관", "계획 세우기", "이해와 암기",
                  "스스로 설명하기"],
    },
    "vocab": {
        "name": "오늘의 어휘",
        "shape": '{"word":"헷갈리는 말 한 쌍 또는 낱말(16자 이내)","body":"50~120자 설명"}',
        "extra": ("맞춤법, 띄어쓰기, 헷갈리는 낱말 쌍, 한자어의 속뜻, 학술 용어의 어원을 다룬다. "
                  "규범에 맞는 표기를 분명히 알려 주고 짧은 예문을 하나 넣어라. "
                  "국립국어원 규범과 어긋나는 설명은 절대 쓰지 마라."),
        "seeds": ["헷갈리는 표기", "띄어쓰기", "한자어의 속뜻", "과학 용어의 어원", "높임말과 예의",
                  "비슷한 말의 차이", "외래어 표기", "속담과 관용구", "문장부호", "줄임말의 원말",
                  "조사와 어미", "잘못 쓰는 표현"],
    },
    "quotes": {
        "name": "명언",
        "shape": '{"text":"인용문(45자 이내)","author":"말한 사람 또는 출처(고사성어, 속담 등)"}',
        "extra": ("실제로 그 사람이 남긴 말만 쓴다. 출처가 불분명하면 쓰지 마라. "
                  "한국 속담과 사자성어도 좋다(그때 author 는 '속담' 또는 '고사성어'). "
                  "고사성어는 '대기만성: 큰 그릇은 늦게 이루어진다'처럼 콜론으로 뜻을 붙여라. "
                  "학생에게 힘이 되는 배움, 끈기, 호기심에 관한 말로."),
        "seeds": ["배움", "끈기", "호기심", "실패와 재도전", "시간", "과학자의 말", "속담",
                  "고사성어", "용기", "습관", "생각하는 힘", "겸손"],
    },
    "quiz": {
        "name": "퀴즈",
        "shape": ('{"q":"질문(28자 이내)","choices":["보기1","보기2","보기3"],'
                  '"answer":0,"explain":"정답 해설(25~70자)"}'),
        "extra": ("보기는 셋이고 answer 는 정답의 자리 번호(0, 1, 2)다. 정답 자리를 골고루 섞어라. "
                  "오답 보기도 그럴듯해야 한다(자릿수만 바꾼 값, 흔한 오개념). "
                  "수치 문제는 반드시 검산해서 정답이 실제로 맞는지 확인하고, 확신 없으면 다른 문제로 바꿔라. "
                  "물리, 수학, 화학, 생명, 지구과학, 상식을 고루."),
        "seeds": ["물리 수치", "천문 수치", "화학", "생명과학", "지구과학", "수학 계산",
                  "단위와 어림", "과학사", "인체", "기술과 발명", "확률", "일상 속 과학"],
    },
    "cheer": {
        "name": "응원 한 줄",
        "shape": '"응원 문장 한 줄(15~35자)"  (문자열 배열로만)',
        "extra": ("퀴즈 정답 카드 아래에 붙는 짧은 응원이다. 부담을 주는 훈계나 성적 압박은 빼고, "
                  "오늘 하루의 노력을 인정해 주는 담백한 말로. 느낌표 남발 금지."),
        "seeds": ["꾸준함", "오늘 하루", "실수해도 괜찮다", "작은 진전", "쉬어 가기", "질문하기",
                  "비교하지 않기", "집중", "회복", "시작", "마무리", "자기 신뢰"],
    },
}


def api():
    """(엔드포인트, 헤더, 모델) — 있는 키에 맞춰 고른다."""
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return ("https://api.openai.com/v1/chat/completions",
                {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                os.environ.get("GEN_MODEL", "gpt-5-mini"))
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key:
        return ("https://api.deepseek.com/chat/completions",
                {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                os.environ.get("GEN_MODEL", "deepseek-chat"))
    raise SystemExit("OPENAI_API_KEY 또는 DEEPSEEK_API_KEY 가 필요하다")


def ask(prompt, retries=3):
    url, headers, model = api()
    payload = {"model": model,
               "messages": [{"role": "system",
                             "content": "너는 한국 고등학생용 학습 카드를 만드는 편집자다. "
                                        "요청한 JSON만 출력한다."},
                            {"role": "user", "content": prompt}],
               "response_format": {"type": "json_object"}}
    for n in range(retries):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=180).json()
            if "choices" not in r:
                raise RuntimeError(r.get("error", r))
            return json.loads(r["choices"][0]["message"]["content"])
        except Exception as e:
            print(f"    요청 실패({n + 1}/{retries}): {str(e)[:160]}")
            time.sleep(3 * (n + 1))
    return {}


def build_prompt(cat, need, used_titles, seed):
    spec = SPECS[cat]
    used = "\n".join(f"- {t}" for t in used_titles)
    return (f"'{spec['name']}' 카드 {need}개를 만들어라.\n\n"
            f"{COMMON_RULES}\n"
            f"이 카테고리 규칙\n{spec['extra']}\n\n"
            f"이번 묶음은 '{seed}' 쪽 소재를 중심으로 하되, 억지로 끼워 맞추지는 마라.\n\n"
            f"항목 형식: {spec['shape']}\n"
            f'출력: {{"items":[ ... {need}개 ... ]}}\n\n'
            f"이미 쓴 것(제목만, 겹치면 안 됨)\n{used}\n")


def load_pools():
    """content*.json 을 모두 합쳐 카테고리별 목록으로."""
    pools = {}
    for cat, rows in chk.load_all().items():
        pools[cat] = [it for _, _, it in rows]
    return pools


def existing_out():
    if os.path.exists(OUT_PATH):
        with open(OUT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save(out):
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)


def title_of(cat, it):
    try:
        if cat == "cheer":
            return str(it)[:30]
        if cat == "quotes":
            return it["text"][:30]
        if cat == "vocab":
            return it["word"]
        if cat == "quiz":
            return it["q"]
        return it["title"]
    except Exception:
        return "?"


def balance_answers(items, start):
    """퀴즈 정답이 한 자리에 몰리지 않게 보기를 돌린다.

    기존 60개는 3번 자리가 정답인 적이 한 번도 없었다. 학생은 그런 걸 금방 눈치챈다.
    """
    for n, it in enumerate(items):
        want = (start + n) % 3
        cur = it["answer"]
        if cur == want:
            continue
        ch = it["choices"]
        ch[cur], ch[want] = ch[want], ch[cur]
        it["answer"] = want
    return items


def fill(cat, target, pools, out):
    made = out.setdefault(cat, [])
    seen = set()
    for it in pools.get(cat, []) + made:
        try:
            seen.add(chk.key_of(cat, it))
        except Exception:
            pass

    have = len(pools.get(cat, [])) + len(made)
    print(f"\n[{cat}] 현재 {have}개 → 목표 {target}개")
    rounds = 0
    while have < target and rounds < MAX_ROUNDS:
        rounds += 1
        need = min(BATCH, target - have)
        titles = [title_of(cat, it) for it in pools.get(cat, []) + made]
        if len(titles) > 600:                       # 프롬프트가 너무 길어지지 않게
            titles = titles[-400:] + random.sample(titles[:-400], 200)
        seed = SPECS[cat]["seeds"][(rounds - 1) % len(SPECS[cat]["seeds"])]

        data = ask(build_prompt(cat, need, titles, seed))
        items = data.get("items") or []
        if cat == "quiz":
            items = [it for it in items
                     if isinstance(it, dict) and isinstance(it.get("choices"), list)
                     and len(it["choices"]) == 3 and isinstance(it.get("answer"), int)]
            items = balance_answers(items, have)

        ok, bad = 0, 0
        for it in items:
            errs = chk.validate(cat, it)
            if errs:
                bad += 1
                continue
            k = chk.key_of(cat, it)
            if k in seen:
                bad += 1
                continue
            seen.add(k)
            made.append(it)
            ok += 1
        have += ok
        save(out)
        print(f"  {rounds:2d}회차 [{seed}] 채택 {ok} / 버림 {bad} → 누적 {have}")
        if ok == 0 and bad == 0:
            print("  응답이 비어 잠시 쉬었다 간다")
            time.sleep(10)
    if have < target:
        print(f"  ! {cat} 은 {have}개에서 멈췄다(요청 상한 도달). 다시 돌리면 이어진다.")
    return have


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    target = int(args[0]) if args else DEFAULT_TARGET
    dry = "--dry-run" in sys.argv
    only = None
    for a in sys.argv[1:]:
        if a.startswith("--only="):
            only = a.split("=", 1)[1].split(",")

    pools = load_pools()
    out = existing_out()
    if dry:
        cat = (only or ["physics"])[0]
        data = ask(build_prompt(cat, 3, [title_of(cat, it) for it in pools.get(cat, [])],
                                SPECS[cat]["seeds"][0]))
        print(json.dumps(data, ensure_ascii=False, indent=2))
        for it in data.get("items", []):
            print("검사:", chk.validate(cat, it) or "통과")
        return

    # 이미 있는 60일치는 목표에 포함해서 센다(목표 360이면 300개만 더 만든다).
    for cat in SPECS:
        if only and cat not in only:
            continue
        fill(cat, target, pools, out)

    save(out)
    print(f"\n{OUT_PATH} 저장 완료")
    print("전수 검사:")
    os.system(f'"{sys.executable}" "{os.path.join(SCRIPT_DIR, "check_content.py")}"')


if __name__ == "__main__":
    main()

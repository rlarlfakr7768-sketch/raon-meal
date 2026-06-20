"""
공식 Instagram API(Instagram Login, graph.instagram.com)로 게시.
- secrets.json 의 계정별 토큰/user_id 사용.
- 피드: image_url + caption / 스토리: media_type=STORIES.
- 토큰 갱신(refresh) 헬퍼 포함(장기토큰 60일 -> 갱신 시 60일 연장).

사용:
  py publish_ig.py refresh <label>
  py publish_ig.py post <label> <image_url> "<caption>"
  py publish_ig.py story <label> <image_url>
  (label = ha_miltonian | phyedu_net)
"""
import os
import sys
import time
import json

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SECRETS_PATH = os.path.join(SCRIPT_DIR, "secrets.json")
GRAPH = "https://graph.instagram.com"
VERSION = "v21.0"


def load_secrets():
    with open(SECRETS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_secrets(data):
    with open(SECRETS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_account(label):
    s = load_secrets()
    acc = s["accounts"].get(label)
    if not acc or not acc.get("ok"):
        raise SystemExit(f"[중단] secrets.json 에 '{label}' 계정 토큰이 없음")
    return s, acc


def refresh_token(label):
    """장기토큰 갱신(24시간 이상 된 토큰만 가능). 새 토큰을 secrets.json에 저장."""
    s, acc = get_account(label)
    r = requests.get(f"{GRAPH}/refresh_access_token",
                     params={"grant_type": "ig_refresh_token",
                             "access_token": acc["access_token"]},
                     timeout=20).json()
    if "access_token" in r:
        acc["access_token"] = r["access_token"]
        days = round(int(r.get("expires_in", 0)) / 86400, 1)
        save_secrets(s)
        print(f"[{label}] 토큰 갱신 OK — 약 {days}일 연장, 저장 완료")
    else:
        print(f"[{label}] 갱신 응답: {r}")
    return r


def create_container(user_id, token, image_url, caption=None, is_story=False):
    params = {"image_url": image_url, "access_token": token}
    if is_story:
        params["media_type"] = "STORIES"
    elif caption:
        params["caption"] = caption
    r = requests.post(f"{GRAPH}/{VERSION}/{user_id}/media", data=params, timeout=60).json()
    if "id" not in r:
        raise SystemExit(f"[컨테이너 실패] {r}")
    return r["id"]


def publish_container(user_id, token, creation_id):
    r = requests.post(f"{GRAPH}/{VERSION}/{user_id}/media_publish",
                      data={"creation_id": creation_id, "access_token": token},
                      timeout=60).json()
    if "id" not in r:
        raise SystemExit(f"[게시 실패] {r}")
    return r["id"]


def post(label, image_url, caption=None, is_story=False):
    _, acc = get_account(label)
    uid, tok = acc["user_id"], acc["access_token"]
    kind = "스토리" if is_story else "피드"
    print(f"[{label}] {kind} 컨테이너 생성…")
    cid = create_container(uid, tok, image_url, caption, is_story)
    time.sleep(5)  # 처리 대기
    mid = publish_container(uid, tok, cid)
    print(f"[{label}] {kind} 게시 완료 — media id {mid}")
    return mid


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    cmd, label = sys.argv[1], sys.argv[2]
    if cmd == "refresh":
        refresh_token(label)
    elif cmd == "post":
        image_url = sys.argv[3]
        caption = sys.argv[4] if len(sys.argv) > 4 else None
        post(label, image_url, caption, is_story=False)
    elif cmd == "story":
        image_url = sys.argv[3]
        post(label, image_url, None, is_story=True)
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()

"""Fail-closed editorial policy for queued Instagram Reels."""
from __future__ import annotations

import json
import re
from pathlib import Path


POLICY_VERSION = 1
HASHTAG_RE = re.compile(r"(?<!\S)#[A-Za-z0-9_가-힣]+")
GENERIC_TAGS = {
    "ko": {"#과학", "#물리", "#생활과학", "#지구과학", "#요리과학", "#phyedu"},
    "en": {"#science", "#physics", "#everydayscience", "#phyedu"},
}


def _fail(item, message):
    raise RuntimeError(f"Reel content policy rejected {item.get('id', '<unknown>')}: {message}")


def load_baseline(root: Path):
    path = root / "reel_content_policy_baseline.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        raise RuntimeError("Reel content-policy baseline is missing or invalid") from None
    if data.get("version") != POLICY_VERSION or not isinstance(data.get("accounts"), dict):
        raise RuntimeError("Reel content-policy baseline has an unsupported schema")
    return data


def validate_item(item, caption: str, language: str, account: str, baseline: dict):
    policy = item.get("content_policy")
    if not isinstance(policy, dict) or policy.get("version") != POLICY_VERSION:
        _fail(item, "content_policy version 1 is required")

    family = policy.get("topic_family")
    keywords = policy.get("keywords")
    if not isinstance(family, str) or not family.strip():
        _fail(item, "topic_family is required")
    if not isinstance(keywords, list) or not keywords or not all(
            isinstance(word, str) and word.strip() for word in keywords):
        _fail(item, "at least one search keyword is required")

    nonempty_lines = [line.strip() for line in caption.splitlines() if line.strip()]
    first_two = " ".join(nonempty_lines[:2]).casefold()
    if not any(word.casefold() in first_two for word in keywords):
        _fail(item, "a search keyword must appear near the start of the caption")

    tags = HASHTAG_RE.findall(caption)
    expected = policy.get("hashtags")
    if not 4 <= len(tags) <= 5:
        _fail(item, "caption must contain 4 or 5 hashtags")
    folded = [tag.casefold() for tag in tags]
    if len(set(folded)) != len(folded):
        _fail(item, "duplicate hashtags are not allowed")
    if "#shorts" in folded:
        _fail(item, "#shorts is not allowed")
    if expected != tags:
        _fail(item, "caption hashtags must exactly match content_policy.hashtags")
    if not any(tag not in GENERIC_TAGS[language] for tag in folded):
        _fail(item, "at least one topic-specific hashtag is required")

    windows = policy.get("measurement_hours")
    if windows != [24, 72]:
        _fail(item, "24-hour and 72-hour measurement windows are required")

    mode = policy.get("mode")
    if mode == "baseline_asset":
        registered = baseline.get("accounts", {}).get(account, {}).get(item.get("id"))
        if registered != item.get("video_sha256"):
            _fail(item, "baseline asset id/hash is not registered")
    elif mode == "full":
        if policy.get("hook") != "visible_result_first_2s":
            _fail(item, "first two seconds must show the visible result")
        if policy.get("controlled_change") != "second_visible_result":
            _fail(item, "one controlled change and a second visible result are required")
        if not isinstance(policy.get("pair_id"), str) or not policy["pair_id"].strip():
            _fail(item, "a bilingual pair_id is required")
    else:
        _fail(item, "mode must be baseline_asset or full")


def validate_queue(queue: dict, data_dir: Path, language: str, account: str, root: Path):
    baseline = load_baseline(root)
    for item in queue.get("queue", []):
        caption_name = item.get("caption", "")
        caption_path = data_dir / caption_name
        if not caption_name or Path(caption_name).name != caption_name or not caption_path.is_file():
            _fail(item, "caption file is missing")
        validate_item(item, caption_path.read_text(encoding="utf-8").strip(),
                      language, account, baseline)

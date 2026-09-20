import json
import tempfile
import unittest
from pathlib import Path

from reel_content_policy import validate_queue


class ContentPolicyTests(unittest.TestCase):
    def make_case(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        data = root / "shorts"
        data.mkdir()
        (data / "caption.txt").write_text(
            "물방울은 왜 둥글까\n\n설명\n\n#과학 #생활과학 #표면장력 #물방울", encoding="utf-8")
        item = {
            "id": "item-1", "caption": "caption.txt", "video_sha256": "abc",
            "content_policy": {
                "version": 1, "mode": "full", "topic_family": "general_physics",
                "keywords": ["물방울"],
                "hashtags": ["#과학", "#생활과학", "#표면장력", "#물방울"],
                "measurement_hours": [24, 72], "hook": "visible_result_first_2s",
                "controlled_change": "second_visible_result", "pair_id": "round-drops",
            },
        }
        queue = {"queue": [item]}
        (root / "reel_content_policy_baseline.json").write_text(
            json.dumps({"version": 1, "accounts": {}}), encoding="utf-8")
        return temp, root, data, queue, item

    def test_valid_full_policy(self):
        temp, root, data, queue, _ = self.make_case()
        self.addCleanup(temp.cleanup)
        validate_queue(queue, data, "ko", "phyedu_net", root)

    def test_generic_only_tags_fail(self):
        temp, root, data, queue, item = self.make_case()
        self.addCleanup(temp.cleanup)
        (data / "caption.txt").write_text(
            "물방울은 왜 둥글까\n\n설명\n\n#과학 #생활과학 #물리 #PhyEdu", encoding="utf-8")
        item["content_policy"]["hashtags"] = ["#과학", "#생활과학", "#물리", "#PhyEdu"]
        with self.assertRaisesRegex(RuntimeError, "topic-specific"):
            validate_queue(queue, data, "ko", "phyedu_net", root)

    def test_shorts_tag_fails(self):
        temp, root, data, queue, item = self.make_case()
        self.addCleanup(temp.cleanup)
        (data / "caption.txt").write_text(
            "물방울은 왜 둥글까\n\n설명\n\n#과학 #표면장력 #물방울 #shorts", encoding="utf-8")
        item["content_policy"]["hashtags"] = ["#과학", "#표면장력", "#물방울", "#shorts"]
        with self.assertRaisesRegex(RuntimeError, "#shorts"):
            validate_queue(queue, data, "ko", "phyedu_net", root)

    def test_missing_visual_gate_fails(self):
        temp, root, data, queue, item = self.make_case()
        self.addCleanup(temp.cleanup)
        del item["content_policy"]["hook"]
        with self.assertRaisesRegex(RuntimeError, "first two seconds"):
            validate_queue(queue, data, "ko", "phyedu_net", root)

    def test_baseline_requires_exact_hash(self):
        temp, root, data, queue, item = self.make_case()
        self.addCleanup(temp.cleanup)
        item["content_policy"]["mode"] = "baseline_asset"
        (root / "reel_content_policy_baseline.json").write_text(json.dumps({
            "version": 1, "accounts": {"phyedu_net": {"item-1": "different"}}
        }), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "id/hash"):
            validate_queue(queue, data, "ko", "phyedu_net", root)


if __name__ == "__main__":
    unittest.main()

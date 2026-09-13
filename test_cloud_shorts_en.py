"""No-network tests for isolated account, timing and uncertain publication guards."""
import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

import cloud_shorts_en as m


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name)
        self.q = {"account": "phyedu_en", "timezone": "Asia/Seoul",
                  "slots": {"B": "12:00", "A": "18:00"}, "paused": False,
                  "queue": [], "done": []}
        self.at = dt.datetime(2026, 9, 14, 12, 10, tzinfo=m.KST)
        self.args = types.SimpleNamespace(plan=False, check=False, slot="B")
        self.credential = {"username": "phyedu_en", "user_id": "123", "access_token": "TEST_ONLY",
                           "obtained_at": self.at.isoformat()}
        self.patchers = [patch.object(m, "DATA", self.data),
                         patch.object(m, "QUEUE", self.data / "queue.json"),
                         patch.object(m, "LOG", self.data / "UPLOAD.log"),
                         patch.object(m, "now", return_value=self.at)]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in reversed(self.patchers):
            p.stop()
        self.tmp.cleanup()

    def item(self):
        video, caption = self.data / "science-en.mp4", self.data / "science-en.txt"
        video.write_bytes(b"reviewed test video bytes")
        caption.write_text("Everyday science in English.\n", encoding="utf-8")
        return {"id": "science-en-v1", "video": video.name, "caption": caption.name,
                "language": "en", "reviewed": True, "slot": "B",
                "scheduled_at": "2026-09-14T12:00:00+09:00",
                "video_sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
                "caption_sha256": hashlib.sha256(caption.read_bytes()).hexdigest()}

    def test_wrong_queue_account_is_rejected(self):
        self.q["account"] = "phyedu_net"
        m.save_queue(self.q)
        with self.assertRaisesRegex(RuntimeError, "account/timezone"):
            m.load_queue()

    def test_wrong_secret_account_is_rejected(self):
        value = dict(self.credential, username="phyedu_net")
        with patch.dict(os.environ, {m.SECRET_NAME: json.dumps(value)}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "expected account"):
                m.credentials()

    def test_empty_queue_does_not_load_credentials_or_publish(self):
        with patch.object(m, "load_queue", return_value=self.q), \
             patch.object(m, "persist", side_effect=AssertionError("No state commit on empty queue")), \
             patch.object(m, "API", side_effect=AssertionError("No network allowed")), \
             patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}, clear=True):
            self.assertEqual(m.run(self.args), 0)

    def test_plan_is_read_only(self):
        self.args.plan = True
        with patch.object(m, "load_queue", return_value=self.q), \
             patch.object(m, "persist", side_effect=AssertionError("No writes")), \
             patch.object(m, "API", side_effect=AssertionError("No network")):
            self.assertEqual(m.run(self.args), 0)

    def test_checksum_prevents_changed_video(self):
        item = self.item()
        (self.data / item["video"]).write_bytes(b"changed")
        with self.assertRaisesRegex(RuntimeError, "checksum"):
            m.media(item)

    def test_korean_or_unreviewed_asset_is_rejected(self):
        item = self.item()
        for change in ({"language": "ko"}, {"reviewed": False}):
            with self.assertRaisesRegex(RuntimeError, "reviewed English"):
                m.media(dict(item, **change))

    def test_parent_path_is_rejected(self):
        item = self.item()
        item["video"] = "../science-en.mp4"
        with self.assertRaisesRegex(RuntimeError, "Invalid or missing"):
            m.media(item)

    def test_early_wrong_slot_and_same_slot_repeat_do_not_run(self):
        item = self.item()
        self.assertFalse(m.eligible(self.q, item, "A", self.at))
        self.assertFalse(m.eligible(self.q, item, "B", self.at - dt.timedelta(hours=1)))
        self.q["done"].append({"slot": "B", "published_at": self.at.isoformat()})
        self.assertFalse(m.eligible(self.q, item, "B", self.at))

    def test_daily_cap(self):
        self.q["done"] = [{"slot": "A", "published_at": self.at.isoformat()}] * 2
        self.assertFalse(m.eligible(self.q, self.item(), "B", self.at))

    def run_with_api(self, item, api):
        self.q["queue"] = [item]
        return [patch.object(m, "load_queue", return_value=self.q),
                patch.object(m, "API", return_value=api),
                patch.object(m, "credentials", return_value=self.credential),
                patch.dict(os.environ, {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "owner/repo"}, clear=True)]

    def test_uncertain_publication_is_never_retried(self):
        item = dict(self.item(), publish_requested_at=self.at.isoformat())
        api = types.SimpleNamespace(verify=lambda: None, recent=lambda: [])
        ps = self.run_with_api(item, api)
        for p in ps:
            p.start()
        try:
            with patch.object(m, "persist"):
                self.assertEqual(m.run(self.args), 1)
                self.assertTrue(self.q["paused"])
        finally:
            for p in reversed(ps): p.stop()

    def test_live_account_mismatch_stops_before_media_calls(self):
        item = self.item()
        def reject(): raise RuntimeError("LIVE Instagram account does not match")
        api = types.SimpleNamespace(verify=reject)
        ps = self.run_with_api(item, api)
        for p in ps: p.start()
        try:
            with self.assertRaisesRegex(RuntimeError, "LIVE Instagram"):
                m.run(self.args)
        finally:
            for p in reversed(ps): p.stop()

    def test_publication_intent_is_durable_before_publish(self):
        item = self.item()
        recorded = []
        def remember(q, reason): recorded.append((reason, copy.deepcopy(q)))
        def publish(cid):
            self.assertEqual(recorded[-1][0], "publication intent")
            self.assertIn("publish_requested_at", recorded[-1][1]["queue"][0])
            return "mid"
        api = types.SimpleNamespace(verify=lambda: None, recent=lambda: [],
              create=lambda u, c: "cid", ready=lambda c: None,
              publish=publish, media_info=lambda mid: {"id": mid, "caption": "Everyday science in English.",
                  "permalink": "https://www.instagram.com/reel/test/", "timestamp": self.at.isoformat()})
        ps = self.run_with_api(item, api)
        for p in ps: p.start()
        try:
            with patch.object(m, "persist", side_effect=remember), \
                 patch.object(m, "git", return_value=types.SimpleNamespace(stdout="abc123")):
                self.assertEqual(m.run(self.args), 0)
                self.assertEqual(len(self.q["done"]), 1)
                self.assertEqual(self.q["done"][0]["media_id"], "mid")
                self.assertEqual(self.q["queue"], [])
        finally:
            for p in reversed(ps): p.stop()

    def test_failed_durable_intent_prevents_publish(self):
        item = dict(self.item(), creation_id="cid")
        api = types.SimpleNamespace(verify=lambda: None, recent=lambda: [], ready=lambda cid: None,
                                   publish=lambda c: self.fail("publish must not happen"))
        ps = self.run_with_api(item, api)
        for p in ps: p.start()
        try:
            with patch.object(m, "persist", side_effect=RuntimeError("disk or git failure")), \
                 patch.object(m, "git", return_value=types.SimpleNamespace(stdout="abc123")):
                with self.assertRaisesRegex(RuntimeError, "disk or git"):
                    m.run(self.args)
        finally:
            for p in reversed(ps): p.stop()

    def test_known_media_id_reconciles_without_publishing(self):
        item = dict(self.item(), creation_id="cid", media_id="mid",
                    publish_requested_at=self.at.isoformat())
        api = types.SimpleNamespace(verify=lambda: None,
              media_info=lambda mid: {"id": mid, "caption": "Everyday science in English.",
                  "permalink": "https://www.instagram.com/reel/test/", "timestamp": self.at.isoformat()})
        ps = self.run_with_api(item, api)
        for p in ps: p.start()
        try:
            with patch.object(m, "persist"):
                self.assertEqual(m.run(self.args), 0)
                self.assertEqual(self.q["queue"], [])
                self.assertEqual(self.q["done"][0]["media_id"], "mid")
        finally:
            for p in reversed(ps): p.stop()

    def test_duplicate_uses_actual_timestamp_not_reconciliation_date(self):
        item = self.item()
        yesterday = (self.at - dt.timedelta(days=1)).isoformat()
        api = types.SimpleNamespace(verify=lambda: None, recent=lambda: [{
            "id": "oldmid", "caption": "Everyday science in English.",
            "permalink": "https://www.instagram.com/reel/test/", "timestamp": yesterday}])
        ps = self.run_with_api(item, api)
        for p in ps: p.start()
        try:
            with patch.object(m, "persist"):
                self.assertEqual(m.run(self.args), 0)
                self.assertEqual(self.q["done"][0]["published_at"], yesterday)
                self.assertTrue(m.eligible(self.q, self.item(), "B", self.at))
        finally:
            for p in reversed(ps): p.stop()

    def test_different_id_field_is_accepted_only_for_same_account(self):
        api = object.__new__(m.API)
        api.c = self.credential
        api.call = lambda *a, **kw: {"id": "999", "user_id": "123", "username": "phyedu_en"}
        api.verify()
        api.call = lambda *a, **kw: {"id": "999", "user_id": "123", "username": "phyedu_net"}
        with self.assertRaisesRegex(RuntimeError, "LIVE Instagram"):
            api.verify()

    def test_hosting_is_immutable_raw_github_url(self):
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/repo"}, clear=True), \
             patch.object(m, "git", return_value=types.SimpleNamespace(stdout="abc123\n")):
            self.assertEqual(m.host_url(Path("science-en.mp4")),
                             "https://raw.githubusercontent.com/owner/repo/abc123/shorts-en/science-en.mp4")

    def test_known_processing_error_pauses_after_three(self):
        item = dict(self.item(), creation_id="cid", failures=2)
        def ready(cid): raise m.ProcessingError("Known processing error")
        api = types.SimpleNamespace(verify=lambda: None, recent=lambda: [], ready=ready)
        ps = self.run_with_api(item, api)
        for p in ps: p.start()
        try:
            with patch.object(m, "persist"), \
                 patch.object(m, "git", return_value=types.SimpleNamespace(stdout="abc123")):
                self.assertEqual(m.run(self.args), 1)
                self.assertTrue(self.q["paused"])
                self.assertNotIn("creation_id", self.q["queue"][0])
                self.assertNotIn("publish_requested_at", self.q["queue"][0])
        finally:
            for p in reversed(ps): p.stop()


if __name__ == "__main__":
    unittest.main()

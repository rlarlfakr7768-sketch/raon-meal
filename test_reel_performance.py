import datetime as dt
import unittest

from reel_performance import due_samples, sample


class PerformanceTests(unittest.TestCase):
    def setUp(self):
        self.now = dt.datetime(2026, 9, 20, 12, tzinfo=dt.timezone.utc)
        self.item = {
            "id": "r1", "media_id": "123", "published_at": "2026-09-19T11:00:00+00:00",
            "content_policy": {"measurement_hours": [24, 72], "topic_family": "food"},
        }

    def test_24_hour_sample_becomes_due(self):
        due = due_samples([self.item], [], self.now)
        self.assertEqual([(row[0]["id"], row[1]) for row in due], [("r1", 24)])

    def test_existing_sample_is_not_repeated(self):
        existing = [{"item_id": "r1", "window_hours": 24}]
        self.assertEqual(due_samples([self.item], existing, self.now), [])

    def test_stale_window_is_not_backfilled(self):
        old = dict(self.item, published_at="2026-09-17T12:00:00+00:00")
        self.assertEqual(due_samples([old], [], self.now), [(old, 72, 72.0)])
        much_older = dict(self.item, published_at="2026-09-16T12:00:00+00:00")
        self.assertEqual(due_samples([much_older], [], self.now), [])

    def test_rates_are_normalized_by_reach(self):
        row = sample(self.item, 24, 25, {"reach": 500, "shares": 2, "saved": 3}, self.now)
        self.assertEqual(row["shares_per_1000_reach"], 4.0)
        self.assertEqual(row["saves_per_1000_reach"], 6.0)


if __name__ == "__main__":
    unittest.main()

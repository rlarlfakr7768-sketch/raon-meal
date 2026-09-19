import unittest, datetime as dt
from reel_schedule import active_slot, eligible, KST
class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.at=dt.datetime(2026,9,20,12,tzinfo=KST)
        self.q={'slots':{'B':'12:00','A':'18:00'},'done':[]}
        self.item={'slot':'B','scheduled_at':self.at.isoformat()}
    def test_no_early_or_overnight_publication(self):
        for h in (0,8,11):self.assertIsNone(active_slot(self.at.replace(hour=h)))
        self.assertFalse(eligible(self.q,self.item,'B',self.at-dt.timedelta(seconds=1)))
    def test_exact_lunch_and_evening(self):
        self.assertTrue(eligible(self.q,self.item,'B',self.at))
        self.assertTrue(eligible(self.q,dict(self.item,slot='A',scheduled_at=self.at.replace(hour=18).isoformat()),'A',self.at.replace(hour=18)))
    def test_delayed_lunch_cannot_publish_in_evening(self):
        self.assertFalse(eligible(self.q,self.item,'B',self.at.replace(hour=18)))
        self.assertFalse(eligible(self.q,self.item,'A',self.at.replace(hour=18)))
    def test_overdue_item_recovers_at_next_matching_slot(self):
        self.assertTrue(eligible(self.q,self.item,'B',self.at+dt.timedelta(days=1)))
        self.assertFalse(eligible(self.q,self.item,'B',self.at+dt.timedelta(days=1,hours=-1)))
    def test_future_item_never_publishes_early(self):
        self.assertFalse(eligible(self.q,dict(self.item,scheduled_at=(self.at+dt.timedelta(days=1)).isoformat()),'B',self.at))
    def test_repeated_dispatch_cannot_repeat_slot(self):
        for field in ('at','published_at'):
            self.q['done']=[{'slot':'B',field:self.at.isoformat()}]
            self.assertFalse(eligible(self.q,self.item,'B',self.at))
    def test_daily_cap(self):
        self.q['done']=[{'slot':'A','published_at':self.at.isoformat()}]*2
        self.assertFalse(eligible(self.q,self.item,'B',self.at))
    def test_timezone_conversion(self):
        self.assertTrue(eligible(self.q,self.item,'B',self.at.astimezone(dt.timezone.utc)))
    def test_bad_slot_timestamp_rejected(self):
        with self.assertRaises(RuntimeError):eligible(self.q,dict(self.item,scheduled_at=self.at.replace(hour=18).isoformat()),'B',self.at)
        with self.assertRaises(RuntimeError):eligible(self.q,dict(self.item,scheduled_at='2026-09-20T12:00:00'),'B',self.at)
if __name__=='__main__':unittest.main()

from datetime import datetime, timezone
from django.test import SimpleTestCase, RequestFactory
from explorer_core.time_windows import parse_time, daily_intervals, in_intervals
from .comparison import schedule, compare
from .tests import sample
from types import SimpleNamespace


class TimezoneTests(SimpleTestCase):
    def test_same_instant_eastern_central_mountain(self):
        eastern=parse_time('2026-10-09T09:00:00','America/New_York')
        self.assertEqual(eastern,parse_time('2026-10-09T08:00:00','America/Chicago'))
        self.assertEqual(eastern,parse_time('2026-10-09T07:00:00','America/Denver'))
        self.assertEqual(eastern,parse_time('2026-10-09T13:00:00Z'))
        self.assertEqual(parse_time('2026-01-09T09:00:00','America/New_York'),parse_time('2026-01-09T14:00:00Z'))

    def test_dst_nonexistent_and_ambiguous_times_rejected(self):
        for date in ('2026-03-08T02:30:00','2026-11-01T01:30:00'):
            with self.assertRaises(ValueError):parse_time(date,'America/New_York')
        self.assertNotEqual(parse_time('2026-11-01T01:30:00-04:00'),parse_time('2026-11-01T01:30:00-05:00'))

    def test_daily_hours_follow_dst_and_do_not_include_lunch(self):
        start=parse_time('2026-10-30T00:00:00','America/New_York');end=parse_time('2026-11-03T00:00:00','America/New_York')
        intervals=daily_intervals(start,end,'America/New_York','09:00','12:00')
        self.assertEqual(len(intervals),4)
        self.assertEqual(datetime.fromtimestamp(intervals[0][0],timezone.utc).hour,13)
        self.assertEqual(datetime.fromtimestamp(intervals[-1][0],timezone.utc).hour,14)
        self.assertTrue(all(b-a==3*3600 for a,b in intervals))
        starts=[a for a,b in intervals]
        self.assertFalse(in_intervals(parse_time('2026-11-02T13:00:00','America/New_York'),intervals,starts))
        self.assertFalse(in_intervals(intervals[0][1],intervals,starts))

    def test_seven_calendar_days_not_168_hours_at_dst(self):
        request=RequestFactory().get('/',{'local_start':'2026-03-06T00:00','local_end':'2026-03-13T00:00','timezone':'America/Denver'})
        start,end,_,_=schedule(request)
        self.assertEqual(end-start,167*3600)

    def test_comparison_daily_filter_and_bad_schedule(self):
        d=sample();r=SimpleNamespace(payload=d,server_id=d['server_id'],source_bytes=1000,player_uuid=d['player_uuid'],player_label='Test',id='test')
        interval=[(d['start']+10,d['start']+20)]
        result=compare([r],d['start'],d['end'],'demo-world',interval)
        self.assertTrue(all(interval[0][0]<=p['time']<interval[0][1] for person in result['players'] for segment in person['segments'] for p in segment))
        with self.assertRaises(ValueError):daily_intervals(d['start'],d['end'],'America/Denver','16:00','09:00')
        with self.assertRaises(ValueError):parse_time('2026-10-09T09:00','Not/AZone')

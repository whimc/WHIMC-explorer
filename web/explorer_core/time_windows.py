"""Study wall-clock times are resolved centrally, never using the machine timezone."""
from bisect import bisect_right
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def zone(name):
    if not isinstance(name, str) or len(name) > 128:
        raise ValueError('Choose a valid IANA timezone.')
    try:
        return ZoneInfo(name)
    except (ValueError, ZoneInfoNotFoundError):
        raise ValueError('Unknown timezone; use a name such as America/New_York or America/Denver.')


def parse_time(value, timezone_name=None):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        raise ValueError('Enter a valid ISO date and time.')
    if parsed.microsecond:
        raise ValueError('Use whole-second times.')
    if parsed.tzinfo is not None:
        return int(parsed.timestamp())
    if timezone_name is None:
        raise ValueError('Supply an explicit UTC offset/Z or choose a study timezone.')
    tz = zone(timezone_name)
    candidates = set()
    for fold in (0, 1):
        aware = parsed.replace(tzinfo=tz, fold=fold)
        utc = aware.astimezone(timezone.utc)
        if utc.astimezone(tz).replace(tzinfo=None) == parsed:
            candidates.add(int(utc.timestamp()))
    if not candidates:
        raise ValueError('This local time does not exist because of daylight saving. Choose another time.')
    if len(candidates) > 1:
        raise ValueError('This local time occurs twice because of daylight saving. Use explicit UTC offsets or UTC times.')
    return candidates.pop()


def daily_intervals(start, end, timezone_name, daily_start='', daily_end=''):
    tz = zone(timezone_name)
    if not daily_start and not daily_end:
        return [(start, end)]
    import re
    if not all(isinstance(v,str) and re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]',v) for v in (daily_start,daily_end)) or daily_start >= daily_end:
        raise ValueError('Daily times must be HH:MM, with the end later on the same day.')
    date = datetime.fromtimestamp(start,tz).date()
    last = datetime.fromtimestamp(end-1,tz).date()
    if (last-date).days > 367:
        raise ValueError('Daily schedule exceeds one year.')
    intervals = []
    while date <= last:
        a = max(start,parse_time(f'{date}T{daily_start}',timezone_name))
        b = min(end,parse_time(f'{date}T{daily_end}',timezone_name))
        if a < b: intervals.append((a,b))
        date += timedelta(days=1)
    return intervals


def in_intervals(value, intervals, starts):
    index = bisect_right(starts, value)-1
    return index >= 0 and intervals[index][0] <= value < intervals[index][1]

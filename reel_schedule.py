"""Actual KST wall time gates all schedulers, including delayed events."""
import datetime as dt
KST=dt.timezone(dt.timedelta(hours=9))
def active_slot(at):
    hour=at.astimezone(KST).hour
    return 'B' if 12<=hour<18 else 'A' if 18<=hour<24 else None

def eligible(q,item,slot,at):
    at=at.astimezone(KST)
    if slot not in ('A','B') or slot!=active_slot(at) or item.get('slot')!=slot:return False
    scheduled=dt.datetime.fromisoformat(item['scheduled_at'])
    if scheduled.tzinfo is None:raise RuntimeError('Scheduled time must include timezone')
    scheduled=scheduled.astimezone(KST)
    if scheduled.strftime('%H:%M')!=q['slots'][slot] or scheduled.second or scheduled.microsecond:
        raise RuntimeError('Scheduled time does not match its configured slot')
    if at<scheduled:return False
    today=[]
    for row in q['done']:
        stamp=row.get('published_at') or row.get('at')
        if stamp and dt.datetime.fromisoformat(stamp).astimezone(KST).date()==at.date():today.append(row)
    return len(today)<2 and not any(x.get('slot')==slot for x in today)

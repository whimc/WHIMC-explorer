"""Private roster feeds the importer-only wizard; never publish it as static data."""
import json
from uuid import UUID
from django.conf import settings
from .models import SessionBundle


def learner_choices():
    path = settings.DATA_DIR / 'roster' / 'accounts.json'
    if path.exists():
        try:
            if path.stat().st_size > 256 * 1024:
                raise ValueError()
            with path.open(encoding='utf-8') as source:
                raw = json.load(source)['accounts']
            if not isinstance(raw, list) or len(raw) > 500:
                raise ValueError()
            accounts, seen = [], set()
            for item in raw:
                uid = str(UUID(item['uuid']))
                name, role = item['name'], item['role']
                if uid in seen or not isinstance(name, str) or not name.strip() or len(name) > 128 or any(ord(c) < 32 for c in name) or role not in {'participant','operator'}:
                    raise ValueError()
                seen.add(uid)
                accounts.append({'uuid':uid,'name':name,'role':role})
            return sorted(accounts,key=lambda a:(a['role']=='operator',a['name'].casefold())), 'Private account roster loaded.'
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return [], 'The private account roster could not be read. Ask the administrator to validate roster/accounts.json in the private data directory.'
    # Most recent label per UUID; roles are only those explicitly present in a bundle.
    accounts = {}
    for record in SessionBundle.objects.order_by('-start','-id').values('player_uuid','player_label','payload__player_role'):
        uid = str(record['player_uuid'])
        if uid not in accounts:
            accounts[uid] = {'uuid':uid,'name':record['player_label'],'role':record['payload__player_role'] or 'unknown'}
        if len(accounts) >= 500:
            break
    return sorted(accounts.values(),key=lambda a:a['name'].casefold()), 'Using learners from imported sessions. Upload a private roster to preload accounts that have not played yet; unknown roles are not assumed to be participants.'

"""Explicit research roles are independent of Minecraft OP and website login rights."""
from uuid import UUID
from explorer_core.scoring import label


def identify(roster, player_uuid):
    matches = [a for a in roster['accounts'] if UUID(a['uuid']) == UUID(player_uuid)]
    if len(matches) != 1:
        raise ValueError('Player must occur exactly once in the roster')
    account = matches[0]
    if account['role'] not in {'participant', 'operator'}:
        raise ValueError('Roster role must be participant or operator')
    label(account['name'])
    return account


def tag_bundle(data, account):
    if UUID(data['player_uuid']) != UUID(account['uuid']):
        raise ValueError('Roster account does not match the bundle player')
    data['player_role'] = account['role']
    # Compatible with the already-deployed portal: its existing session list
    # displays this label and its existing quality section displays this note.
    role = account['role'].capitalize()
    data['player_label'] = role + ' - ' + data['player_label']
    data.setdefault('warnings', []).append('Account role: ' + role + '; assigned by the study roster, not Minecraft permissions.')
    return data

import argparse
import json
import statistics
from pathlib import Path


def analyze(paths):
    turns = {}
    sessions = {}
    invalid = 0
    active_requests = set()
    ambiguous_sessions = set()
    for path in paths:
        for line in Path(path).read_text().splitlines():
            if 'VOICE_LATENCY ' not in line:
                continue
            try:
                event = json.loads(line.split('VOICE_LATENCY ', 1)[1])
                session = event['client_session_id']
                fields = event['fields']
                name = event['event']
            except (ValueError, KeyError, TypeError):
                invalid += 1
                continue
            if name == 'utterance_endpoint':
                if session in active_requests:
                    ambiguous_sessions.add(session)
                active_requests.add(session)
            elif name in ('generation_done', 'server_error'):
                active_requests.discard(session)
            sessions.setdefault(session, {})[name] = fields
            if event.get('turn_id'):
                turns.setdefault((session, event['turn_id']), {})[name] = fields
    samples = {}
    for (session, _), events in turns.items():
        kind = events.get('thinking', {}).get('kind')
        if kind is None:
            render = events.get('first_pcm_rendered', {})
            kind = ('turn' if render.get('speech_end_to_render_ms') is not None else 'greeting') if render else 'unknown'
        if session in ambiguous_sessions and kind != 'greeting':
            continue
        for name, fields in events.items():
            for key in ('response_ms', 'speech_end_to_render_ms', 'received_to_render_ms', 'max_frame_gap_ms'):
                value = fields.get(key)
                if isinstance(value, (float, int)):
                    samples.setdefault(f'{kind}.{name}.{key}', []).append(value)
    aggregates = {}
    for name, values in samples.items():
        aggregates[name] = {
            'count': len(values), 'min_ms': min(values),
            'median_ms': statistics.median(values), 'max_ms': max(values),
        }
    return {
        'sessions': len(sessions), 'turns': len(turns), 'malformed_events': invalid,
        'measured_turns': sum('first_pcm_rendered' in events for events in turns.values()),
        'aggregates': aggregates,
        'sessions_with_overlapping_requests': len(ambiguous_sessions),
        'exclusion': 'User turn aggregates excluded for sessions with overlapping unresolved utterances; old server lacks client request IDs',
        'turn_samples': [dict(client_session_id=session, turn_id=turn, events=events)
                         for (session, turn), events in turns.items()],
        'boundary': 'first PCM output callback; excludes unknown hardware/acoustic delay',
        'origin': 'greeting: session start; user turn: utterance endpoint',
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('logs', nargs='+')
    args = parser.parse_args()
    print(json.dumps(analyze(args.logs), indent=2))


if __name__ == '__main__':
    main()

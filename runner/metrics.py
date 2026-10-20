"""Metriky z výstupu `claude -p --output-format stream-json --verbose`.

Kromě souhrnu z události `result` počítá to, co je potřeba ke srovnání nástrojů:
vývoj spotřeby po jednotlivých voláních API, počty a objem výsledků nástrojů podle
jména nástroje (hlavní ukazatel pro RTK a Context Mode), objem textu modelu
(Caveman, Ponytail) a stopy aktivace pluginů v hook událostech.
"""
import json
from collections import defaultdict
from pathlib import Path


def _text_len(content) -> int:
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return sum(_text_len(c.get('text', '') if isinstance(c, dict) else c) for c in content)
    return 0


def parse_stream(path: Path) -> dict:
    init, result = None, None
    calls = []                       # usage každé odpovědi API (podle message.id)
    seen_msg = set()
    tool_uses = defaultdict(int)
    tool_result_chars = defaultdict(int)
    tool_id_name = {}
    assistant_text_chars = 0
    thinking_chars = 0
    hook_outputs = []
    rate_limit_events = []
    bash_commands = []
    tool_calls = []                  # jednotlivá volání: jméno, zkrácený vstup, velikost výsledku
    tool_call_idx = {}
    compactions = 0
    parse_errors = 0

    for line in path.read_text(errors='replace').splitlines():
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            parse_errors += 1
            continue
        t = e.get('type')
        if t == 'system' and e.get('subtype') == 'init':
            init = e
        elif t == 'system' and e.get('subtype') == 'hook_response':
            hook_outputs.append({k: e.get(k) for k in ('hook_name', 'hook_event', 'output', 'stdout', 'stderr', 'exit_code')})
        elif t == 'system' and e.get('subtype') == 'compact_boundary':
            compactions += 1
        elif t == 'rate_limit_event':
            rate_limit_events.append(e)
        elif t == 'result':
            result = e
        elif t == 'assistant':
            m = e.get('message', {})
            mid = m.get('id')
            if mid and mid not in seen_msg and m.get('usage'):
                seen_msg.add(mid)
                u = m['usage']
                calls.append({
                    'input': u.get('input_tokens', 0),
                    'cache_read': u.get('cache_read_input_tokens', 0),
                    'cache_write': u.get('cache_creation_input_tokens', 0),
                    'output': u.get('output_tokens', 0),
                    'subagent': bool(e.get('parent_tool_use_id')),
                })
            for c in m.get('content', []) or []:
                ct = c.get('type')
                if ct == 'text':
                    assistant_text_chars += len(c.get('text', ''))
                elif ct == 'thinking':
                    thinking_chars += len(c.get('thinking', ''))
                elif ct == 'tool_use':
                    name = c.get('name', '?')
                    tool_uses[name] += 1
                    tool_id_name[c.get('id')] = name
                    if name == 'Bash':
                        bash_commands.append((c.get('input') or {}).get('command', ''))
                    tool_call_idx[c.get('id')] = len(tool_calls)
                    tool_calls.append({'name': name, 'input': json.dumps(c.get('input') or {}, ensure_ascii=False)[:500],
                                       'result_chars': 0, 'subagent': bool(e.get('parent_tool_use_id'))})
        elif t == 'user':
            for c in (e.get('message', {}).get('content') or []):
                if isinstance(c, dict) and c.get('type') == 'tool_result':
                    name = tool_id_name.get(c.get('tool_use_id'), '?')
                    n = _text_len(c.get('content'))
                    tool_result_chars[name] += n
                    if c.get('tool_use_id') in tool_call_idx:
                        tool_calls[tool_call_idx[c.get('tool_use_id')]]['result_chars'] += n

    return {
        'init': {k: (init or {}).get(k) for k in (
            'model', 'permissionMode', 'claude_code_version', 'apiKeySource', 'per_turn_effort_active',
            'plugins', 'mcp_servers', 'tools', 'skills', 'output_style')},
        'result': {k: (result or {}).get(k) for k in (
            'subtype', 'is_error', 'terminal_reason', 'stop_reason', 'num_turns', 'duration_ms', 'duration_api_ms',
            'total_cost_usd', 'usage', 'modelUsage', 'permission_denials', 'api_error_status', 'subagent_stats',
            'safety_stops', 'result')},
        'api_calls': calls,
        'api_call_count': len(calls),
        'tool_uses': dict(tool_uses),
        'tool_result_chars': dict(tool_result_chars),
        'tool_result_chars_total': sum(tool_result_chars.values()),
        'assistant_text_chars': assistant_text_chars,
        'thinking_chars': thinking_chars,
        'bash_commands': bash_commands,
        'tool_calls': tool_calls,
        'tool_result_chars_max': max((c['result_chars'] for c in tool_calls), default=0),
        'compactions': compactions,
        'hook_outputs': hook_outputs,
        'rate_limit_events': rate_limit_events,
        'parse_errors': parse_errors,
        'has_result': result is not None,
    }


def hook_text(m: dict) -> str:
    return '\n'.join(json.dumps(h, ensure_ascii=False) for h in m['hook_outputs'])

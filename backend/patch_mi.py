"""Replace all signal_confidence usages with _forecast injection."""
import os

BASE = os.path.dirname(__file__)
result_path = os.path.join(BASE, 'patch_mi_result.txt')

def load(rel_path):
    path = os.path.join(BASE, rel_path)
    with open(path, 'rb') as f:
        raw = f.read()
    return raw.replace(b'\r\n', b'\n').replace(b'\r', b'\n').decode('utf-8').split('\n')

def save(rel_path, lines):
    path = os.path.join(BASE, rel_path)
    with open(path, 'w', newline='\n', encoding='utf-8') as f:
        f.write('\n'.join(lines))

def fr_lines(direction, conf, pu, pd, pf, indent='        '):
    """Return the _forecast injection lines as a single string."""
    return (
        f'{indent}from app.ai.prediction.forecasting import ForecastResult\n'
        f'{indent}ctx.metadata["_forecast"] = ForecastResult(\n'
        f'{indent}    direction="{direction}", confidence={conf},\n'
        f'{indent}    prob_up={pu}, prob_down={pd}, prob_flat={pf},\n'
        f'{indent})'
    )

# ── test_6d_integration.py ────────────────────────────────────────────────────
lines = load('tests/phase6/test_6d_integration.py')
# Line 163: signal_confidence=0.85 -> UP BUY
lines[162] = fr_lines('UP', 85.0, 85.0, 8.0, 7.0)
# Line 173: signal_confidence=0.15 -> DOWN SELL
lines[172] = fr_lines('DOWN', 68.0, 12.0, 68.0, 20.0)
save('tests/phase6/test_6d_integration.py', lines)

# ── test_7c_agents.py ─────────────────────────────────────────────────────────
lines = load('tests/phase7/test_7c_agents.py')

# Map: 1-based line number -> (direction, conf, pu, pd, pf)
# Lines that set signal_confidence and what they should become
replacements = {
    674:  ('UP',   80.0, 80.0, 10.0, 10.0),   # test_execute_returns_agent_result trader
    683:  ('UP',   80.0, 80.0, 10.0, 10.0),   # test_execute_without_rag
    693:  ('UP',   80.0, 80.0, 10.0, 10.0),   # test_execute_with_rag
    704:  ('UP',   80.0, 80.0, 10.0, 10.0),   # test_execute_with_empty_rag
    718:  ('FLAT', 50.0, 20.0, 30.0, 50.0),   # test_execute_publishes_to_bus (neutral->HOLD)
    730:  ('UP',   80.0, 80.0, 10.0, 10.0),   # test_execute_no_bus
    739:  ('UP',   85.0, 85.0,  8.0,  7.0),   # test_buy_signal_at_high_confidence
    748:  ('DOWN', 68.0, 12.0, 68.0, 20.0),   # test_sell_signal_at_low_confidence
    757:  ('FLAT', 50.0, 20.0, 30.0, 50.0),   # test_hold_signal_at_neutral_confidence
    766:  ('UP',   80.0, 80.0, 10.0, 10.0),   # test_verify_passes_for_valid_signal
    902:  ('UP',   82.0, 82.0, 10.0,  8.0),   # test_trader_then_analyst_pipeline
    955:  ('UP',   80.0, 80.0, 10.0, 10.0),   # test_rag_context_shared_across_agents
    1035: ('UP',   72.0, 72.0, 15.0, 13.0),   # test_trader_confidence_matches_signal_confidence
    1058: ('UP',   82.0, 82.0, 10.0,  8.0),   # test_full_7c_pipeline_high_confidence
    1102: ('UP',   75.0, 75.0, 12.0, 13.0),   # test_two_contexts_independent (ctx1)
    1127: ('UP',   80.0, 80.0, 10.0, 10.0),   # test_rag_assembly_with_no_market_blocks_graceful
}

# Also fix analyst test_execute_returns_agent_result (line 789 area)
# Find it: it checks confidence == 0.7
for i, line in enumerate(lines, 1):
    if 'assert result.confidence == 0.7' in line and i > 780 and i < 800:
        # The line before should be execute(ctx)
        # We need to inject _forecast before execute
        # Find the ctx line above
        for j in range(i-1, max(0, i-10), -1):
            if 'ctx    = _ctx' in lines[j] or 'ctx = _ctx' in lines[j]:
                # Insert after this line
                indent = '        '
                fr = fr_lines('UP', 70.0, 70.0, 15.0, 15.0, indent)
                lines[j] = lines[j] + '\n' + fr
                break
        # Fix the assertion
        lines[i-1] = lines[i-1].replace('== 0.7', '- 0.7) < 0.001').replace('assert result.confidence', 'assert abs(result.confidence')
        break

for lineno, (direction, conf, pu, pd, pf) in replacements.items():
    idx = lineno - 1
    if idx < len(lines) and 'signal_confidence' in lines[idx]:
        lines[idx] = fr_lines(direction, conf, pu, pd, pf)
    else:
        # Try to find it nearby
        found = False
        for offset in range(-2, 3):
            if 0 <= idx+offset < len(lines) and 'signal_confidence' in lines[idx+offset]:
                lines[idx+offset] = fr_lines(direction, conf, pu, pd, pf)
                found = True
                break

save('tests/phase7/test_7c_agents.py', lines)

with open(result_path, 'w', encoding='utf-8') as r:
    r.write('DONE\n')

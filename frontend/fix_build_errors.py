import re, sys

# ── Fix 1: PositionBanner in StocksPage.tsx ───────────────────
path1 = r'src\components\StocksPage.tsx'
with open(path1, 'r', encoding='utf-8', newline='') as f:
    c1 = f.read()

if 'function PositionBanner' not in c1:
    banner = (
        '\r\n'
        'function PositionBanner({ buyPrice, openedAt, currentPrice }: '
        '{ buyPrice: number; openedAt: number; currentPrice: number }) {\r\n'
        '  const pnl = currentPrice - buyPrice\r\n'
        '  const pnlPct = buyPrice ? (pnl / buyPrice * 100) : 0\r\n'
        '  const positive = pnl >= 0\r\n'
        '  return (\r\n'
        '    <div style={{\r\n'
        '      display: \'flex\', alignItems: \'center\', gap: 12, padding: \'6px 12px\', marginBottom: 8,\r\n'
        '      background: positive ? \'rgba(0,255,153,0.06)\' : \'rgba(255,90,122,0.06)\',\r\n'
        '      border: `1px solid ${positive ? \'rgba(0,255,153,0.25)\' : \'rgba(255,90,122,0.25)\'}`,\r\n'
        '      borderRadius: 2,\r\n'
        '    }}>\r\n'
        '      <span style={{ fontSize: 9, fontFamily: \'Orbitron, sans-serif\', color: \'#2A5A6A\', letterSpacing: \'0.18em\' }}>OPEN POSITION</span>\r\n'
        '      <span style={{ fontSize: 10, fontFamily: \'IBM Plex Mono, monospace\', color: \'#D8FFFF\' }}>\u20b9{buyPrice.toFixed(2)}</span>\r\n'
        '      <span style={{ fontSize: 10, fontFamily: \'IBM Plex Mono, monospace\', color: positive ? \'#00FF99\' : \'#FF5A7A\', fontWeight: 700 }}>\r\n'
        '        {positive ? \'+\' : \'\'}{pnl.toFixed(2)} ({positive ? \'+\' : \'\'}{pnlPct.toFixed(2)}%)\r\n'
        '      </span>\r\n'
        '      <span style={{ fontSize: 9, fontFamily: \'Rajdhani, sans-serif\', color: \'#2A5A6A\' }}>{holdDurationStr(openedAt)}</span>\r\n'
        '    </div>\r\n'
        '  )\r\n'
        '}\r\n'
    )
    marker = "return `${Math.floor(secs / 86400)}d ${Math.floor((secs % 86400) / 3600)}h`"
    idx = c1.find(marker)
    if idx != -1:
        close_idx = c1.find('}', idx)
        if close_idx != -1:
            c1 = c1[:close_idx + 1] + banner + c1[close_idx + 1:]
            with open(path1, 'w', encoding='utf-8', newline='') as f:
                f.write(c1)
            print('Fix 1: PositionBanner inserted')
        else:
            print('Fix 1: closing brace not found')
    else:
        print('Fix 1: marker not found')
else:
    print('Fix 1: already present')

# ── Fix 2: HudPanelManager load type ─────────────────────────
path2 = r'src\components\HudPanelManager.tsx'
with open(path2, 'r', encoding='utf-8', newline='') as f:
    c2 = f.read()

old = 'load: () => Promise<{ default: React.ComponentType<any> } | { [k: string]: React.ComponentType<any> }>'
new = 'load: () => Promise<any>'
if old in c2:
    c2 = c2.replace(old, new)
    with open(path2, 'w', encoding='utf-8', newline='') as f:
        f.write(c2)
    print('Fix 2: HudPanelManager type fixed')
elif new in c2:
    print('Fix 2: already fixed')
else:
    print('Fix 2: pattern not found')

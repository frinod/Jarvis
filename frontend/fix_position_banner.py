import re

path = r'src\components\StocksPage.tsx'

with open(path, 'r', encoding='utf-8', newline='') as f:
    content = f.read()

if 'function PositionBanner' in content:
    print('Already fixed.')
else:
    banner = (
        '\r\n'
        '// -- PositionBanner --\r\n'
        'function PositionBanner({ buyPrice, openedAt, currentPrice }: { buyPrice: number; openedAt: number; currentPrice: number }) {\r\n'
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
        '      <span style={{ fontSize: 10, fontFamily: \'IBM Plex Mono, monospace\', color: \'#D8FFFF\' }}>Avg \u20b9{buyPrice.toFixed(2)}</span>\r\n'
        '      <span style={{ fontSize: 10, fontFamily: \'IBM Plex Mono, monospace\', color: positive ? \'#00FF99\' : \'#FF5A7A\', fontWeight: 700 }}>\r\n'
        '        {positive ? \'+\' : \'\'}{pnl.toFixed(2)} ({positive ? \'+\' : \'\'}{pnlPct.toFixed(2)}%)\r\n'
        '      </span>\r\n'
        '      <span style={{ fontSize: 9, fontFamily: \'Rajdhani, sans-serif\', color: \'#2A5A6A\' }}>{holdDurationStr(openedAt)}</span>\r\n'
        '    </div>\r\n'
        '  )\r\n'
        '}\r\n'
    )

    # Find the end of holdDurationStr by locating its unique last return line
    marker = "return `${Math.floor(secs / 86400)}d ${Math.floor((secs % 86400) / 3600)}h`"
    idx = content.find(marker)
    if idx == -1:
        print('ERROR: marker not found')
    else:
        # Find the closing brace after the marker
        close_idx = content.find('}', idx)
        if close_idx == -1:
            print('ERROR: closing brace not found')
        else:
            insert_at = close_idx + 1
            content = content[:insert_at] + banner + content[insert_at:]
            with open(path, 'w', encoding='utf-8', newline='') as f:
                f.write(content)
            print('PositionBanner inserted at index', insert_at)

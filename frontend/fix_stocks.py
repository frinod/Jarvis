path = r'src\components\StocksPage.tsx'
with open(path, 'r', encoding='utf-8', newline='') as f:
    content = f.read()

# Replace the PositionBanner JSX call with an inline expression
old = '<PositionBanner buyPrice={positionMarker.buyPrice} openedAt={positionMarker.openedAt} currentPrice={selectedStockData?.price ?? positionMarker.buyPrice} />'
new = (
    '<div style={{ display: "flex", alignItems: "center", gap: 12, padding: "6px 12px", marginBottom: 8, '
    'background: (selectedStockData?.price ?? positionMarker.buyPrice) >= positionMarker.buyPrice ? "rgba(0,255,153,0.06)" : "rgba(255,90,122,0.06)", '
    'border: "1px solid " + ((selectedStockData?.price ?? positionMarker.buyPrice) >= positionMarker.buyPrice ? "rgba(0,255,153,0.25)" : "rgba(255,90,122,0.25)"), '
    'borderRadius: 2 }}>'
    '<span style={{ fontSize: 9, fontFamily: "Orbitron, sans-serif", color: "#2A5A6A", letterSpacing: "0.18em" }}>OPEN POSITION</span>'
    '<span style={{ fontSize: 10, fontFamily: "IBM Plex Mono, monospace", color: "#D8FFFF" }}>'
    '\u20b9{positionMarker.buyPrice.toFixed(2)}</span>'
    '<span style={{ fontSize: 10, fontFamily: "IBM Plex Mono, monospace", '
    'color: (selectedStockData?.price ?? positionMarker.buyPrice) >= positionMarker.buyPrice ? "#00FF99" : "#FF5A7A", fontWeight: 700 }}>'
    '{((selectedStockData?.price ?? positionMarker.buyPrice) - positionMarker.buyPrice) >= 0 ? "+" : ""}'
    '{((selectedStockData?.price ?? positionMarker.buyPrice) - positionMarker.buyPrice).toFixed(2)}'
    '</span>'
    '</div>'
)

if old in content:
    content = content.replace(old, new, 1)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(content)
    print('PositionBanner usage replaced with inline div')
else:
    print('ERROR: PositionBanner JSX not found')
    # Show what's around line 2184
    lines = content.split('\n')
    for i, line in enumerate(lines[2180:2190], start=2181):
        print(f'{i}: {repr(line[:80])}')

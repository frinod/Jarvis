/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        jarvis: {
          bg:       '#050816',
          bg2:      '#081328',
          panel:    '#0a1a2e',
          surface:  '#0d2040',
          surface2: '#102448',
          border:   'rgba(0,217,255,0.12)',
          border2:  'rgba(0,217,255,0.22)',
          accent:   '#00D9FF',
          accent2:  '#0066ff',
          accent3:  '#7B5EA7',
          highlight:'#00F5FF',
          text:     '#C8F9FF',
          text2:    '#7ECFDF',
          muted:    '#2A5A6A',
          neon: {
            blue:   '#00D9FF',
            purple: '#7B5EA7',
            green:  '#00FF9C',
            orange: '#FF7B00',
            yellow: '#FFB347',
            red:    '#FF4D6D',
            cyan:   '#00F5FF',
          },
        },
      },
      fontFamily: {
        orbitron: ['Orbitron', 'sans-serif'],
        rajdhani: ['Rajdhani', 'sans-serif'],
        grotesk:  ['Space Grotesk', 'sans-serif'],
        plex:     ['IBM Plex Mono', 'monospace'],
        mono:     ['JetBrains Mono', 'IBM Plex Mono', 'Consolas', 'monospace'],
      },
      boxShadow: {
        'neon-blue':   '0 0 12px rgba(0,217,255,0.55), 0 0 24px rgba(0,217,255,0.28)',
        'neon-green':  '0 0 12px rgba(0,255,156,0.55), 0 0 24px rgba(0,255,156,0.28)',
        'neon-red':    '0 0 12px rgba(255,77,109,0.55), 0 0 24px rgba(255,77,109,0.28)',
        'neon-purple': '0 0 12px rgba(123,94,167,0.55), 0 0 24px rgba(123,94,167,0.28)',
        'panel':       '0 4px 32px rgba(0,0,0,0.7), 0 0 1px rgba(0,217,255,0.12)',
        'hud':         '0 0 60px rgba(0,217,255,0.06), inset 0 0 60px rgba(0,217,255,0.02)',
      },
      animation: {
        'spin-slow':    'spin 24s linear infinite',
        'spin-medium':  'spin 16s linear infinite',
        'spin-reverse': 'spin 18s linear infinite reverse',
        'spin-fast':    'spin 8s linear infinite',
        'pulse-glow':   'pulseDot 2s ease-in-out infinite',
        'hologram':     'hologram 4s ease infinite',
        'border-glow':  'borderGlow 3s ease-in-out infinite',
        'fade-in':      'fadeIn 0.25s ease',
        'scan':         'scanLine 6s linear infinite',
        'radar':        'radarSweep 4s linear infinite',
        'energy-ring':  'energyRing 2.5s ease-out infinite',
        'grid-drift':   'gridDrift 60s linear infinite',
        'target-lock':  'targetLock 0.8s ease-in-out infinite',
      },
      backgroundImage: {
        'grid-pattern': `
          linear-gradient(rgba(0,217,255,0.04) 1px, transparent 1px),
          linear-gradient(90deg, rgba(0,217,255,0.04) 1px, transparent 1px)
        `,
        'radial-glow':  'radial-gradient(ellipse at center, rgba(0,217,255,0.1) 0%, transparent 70%)',
        'hud-gradient': 'linear-gradient(135deg, rgba(10,26,46,0.9) 0%, rgba(8,19,40,0.85) 100%)',
      },
      backgroundSize: {
        'grid': '80px 80px',
      },
    },
  },
  plugins: [],
}

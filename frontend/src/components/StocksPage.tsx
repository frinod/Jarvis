'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { RefreshCw, Search, BarChart2, Wifi, WifiOff, ExternalLink, ChevronRight, TrendingUp, TrendingDown, Minus, MessageSquare, X, Send, Layers, ShoppingCart } from 'lucide-react'
import { useJarvisStore, StockQuote, Candle, StockFundamentals, Financials, ShareholdingData, PeerStock, ScreenerResult, AIAnalysis, ForecastResult, BudgetAdvice, WS_URL, AnalysisSnapshot, API_URL } from '@/store/jarvisStore'

// ── Buy Marker Overlay ────────────────────────────────────────
function holdDurationStr(openedAt: number): string {
  const secs = Math.floor(Date.now() / 1000 - openedAt)
  if (secs < 60) return `${secs}s`
  if (secs < 3600) return `${Math.floor(secs / 60)}m`
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ${Math.floor((secs % 3600) / 60)}m`
  return `${Math.floor(secs / 86400)}d ${Math.floor((secs % 86400) / 3600)}h`
}

// ── Overlay Types + Fetch ─────────────────────────────────────
interface OverlayData {
  ema9: number[]; ema21: number[]; ema50: number[]; ema200: number[]
  bb_upper: number[]; bb_mid: number[]; bb_lower: number[]
  supertrend: number[]; st_direction: number[]
  fibonacci: Record<string, number>
  support: number[]; resistance: number[]; pivot: number
}

async function fetchOverlays(symbol: string, interval: string, range: string): Promise<OverlayData | null> {
  try {
    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'
    const r = await fetch(`${API_URL}/api/stocks/overlays/${symbol}?interval=${interval}&range=${range}`)
    return r.json()
  } catch { return null }
}

// ── Sparkline ─────────────────────────────────────────────────
function Sparkline({ data, positive }: { data: number[]; positive: boolean }) {
  if (!data || data.length < 2) return null
  const w = 56, h = 22
  const min = Math.min(...data), max = Math.max(...data)
  const range = max - min || 1
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * w},${h - ((v - min) / range) * h}`).join(' ')
  return (
    <svg width={w} height={h} className="overflow-visible shrink-0">
      <polyline points={pts} fill="none" stroke={positive ? '#30d158' : '#ff453a'} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  )
}

// ── Price Chart ───────────────────────────────────────────────
function PriceChart({ candles, mode, tf, overlays, activeOverlays, buyMarker }: {
  candles: Candle[]
  mode: 'line' | 'candle'
  tf: string
  overlays?: OverlayData | null
  activeOverlays?: Set<string>
  buyMarker?: { buyPrice: number; openedAt: number } | null
}) {
  if (!candles || candles.length === 0) return (
    <div className="flex items-center justify-center h-[500px] text-jarvis-muted text-sm">No chart data available</div>
  )

  const [tooltip, setTooltip] = useState<{ svgX: number; svgY: number; closeY: number; idx: number } | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)

  // Layout: no internal padding — chart fills the full SVG
  // Y-axis labels rendered as foreignObject outside SVG, or we keep a left pad only for labels
  const W = 1100, H = 420
  const PAD = { top: 12, right: 8, bottom: 36, left: 64 }
  const cw = W - PAD.left - PAD.right
  const ch = H - PAD.top - PAD.bottom

  const closes = candles.map(c => c.c)
  const highs  = candles.map(c => c.h)
  const lows   = candles.map(c => c.l)
  const minP   = Math.min(...lows)
  const maxP   = Math.max(...highs)
  const priceRange = maxP - minP || 1

  const xScale = (i: number) => PAD.left + (i / Math.max(candles.length - 1, 1)) * cw
  const yScale = (v: number) => PAD.top + ch - ((v - minP) / priceRange) * ch

  const positive = closes[closes.length - 1] >= closes[0]
  const linePts  = candles.map((c, i) => `${xScale(i)},${yScale(c.c)}`).join(' ')

  const yTicks = Array.from({ length: 6 }, (_, i) => minP + (priceRange / 5) * i)
  const xStep  = Math.max(1, Math.floor(candles.length / 10))

  const isIntraday = ['1m', '2m', '5m', '15m', '30m'].includes(tf)
  const formatXLabel = (t: number) => {
    const d = new Date(t)
    if (isIntraday) return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Kolkata' })
    if (tf === '1H') return d.toLocaleDateString('en-IN', { month: 'short', day: 'numeric', timeZone: 'Asia/Kolkata' })
    return d.toLocaleDateString('en-IN', { month: 'short', day: 'numeric', year: tf === '1M' ? '2-digit' : undefined, timeZone: 'Asia/Kolkata' })
  }
  const formatTooltipDate = (t: number) => new Date(t).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'Asia/Kolkata' })
  const formatTooltipTime = (t: number) => new Date(t).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Kolkata' })

  const xLabels = candles.map((c, i) => ({ i, label: formatXLabel(c.t) })).filter((_, i) => i % xStep === 0)

  // Use SVG's own coordinate transform — pixel-perfect at any zoom/resolution
  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const svg = svgRef.current
    if (!svg) return
    const pt = svg.createSVGPoint()
    pt.x = e.clientX
    pt.y = e.clientY
    const ctm = svg.getScreenCTM()
    if (!ctm) return
    const svgPt = pt.matrixTransform(ctm.inverse())
    const mx = svgPt.x
    const my = svgPt.y
    if (mx < PAD.left || mx > W - PAD.right || my < PAD.top || my > PAD.top + ch) {
      setTooltip(null)
      return
    }
    const idx = Math.max(0, Math.min(candles.length - 1, Math.round(((mx - PAD.left) / cw) * (candles.length - 1))))
    setTooltip({ svgX: xScale(idx), svgY: my, closeY: yScale(candles[idx].c), idx })
  }

  const tc = tooltip !== null ? candles[tooltip.idx] : null

  return (
    <div className="w-full relative">
      {/* Floating OHLCV tooltip — top-left corner */}
      {tc && tooltip && (
        <div className="absolute top-2 left-16 z-10 glass rounded-lg px-3 py-2 border border-jarvis-border pointer-events-none">
          <p className="text-[10px] text-jarvis-accent font-mono font-bold mb-1">
            {formatTooltipDate(tc.t)} &nbsp; {formatTooltipTime(tc.t)}
          </p>
          <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
            {([['O', tc.o], ['H', tc.h], ['L', tc.l], ['C', tc.c]] as [string, number][]).map(([label, val]) => (
              <div key={label} className="flex items-center gap-1">
                <span className="text-[10px] text-jarvis-muted w-3">{label}</span>
                <span className="text-[11px] font-mono text-jarvis-text">₹{val.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
              </div>
            ))}
          </div>
          <div className="flex items-center gap-1 mt-1">
            <span className="text-[10px] text-jarvis-muted">Vol</span>
            <span className="text-[11px] font-mono text-jarvis-muted">{(tc.v / 1000).toFixed(0)}K</span>
          </div>
        </div>
      )}

      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        className="w-full cursor-crosshair block"
        style={{ height: 420 }}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setTooltip(null)}
      >
        {/* Grid lines */}
        {yTicks.map((v, i) => (
          <g key={i}>
            <line x1={PAD.left} x2={W - PAD.right} y1={yScale(v)} y2={yScale(v)}
              stroke="rgba(6,182,212,0.07)" strokeWidth="1" strokeDasharray="4,4" />
            <text x={PAD.left - 6} y={yScale(v) + 4} textAnchor="end"
              fill="rgba(148,163,184,0.85)" fontSize="11" fontFamily="monospace">
              {v >= 1000 ? (v / 1000).toFixed(1) + 'k' : v.toFixed(0)}
            </text>
          </g>
        ))}
        {xLabels.map(({ i, label }) => (
          <text key={i} x={xScale(i)} y={H - 6} textAnchor="middle"
            fill="rgba(148,163,184,0.85)" fontSize="10" fontFamily="monospace">
            {label}
          </text>
        ))}

        {/* Chart */}
        {mode === 'line' ? (
          <>
            <defs>
              <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={positive ? '#30d158' : '#ff453a'} stopOpacity="0.2" />
                <stop offset="100%" stopColor={positive ? '#30d158' : '#ff453a'} stopOpacity="0" />
              </linearGradient>
            </defs>
            <polygon
              points={`${PAD.left},${PAD.top + ch} ${linePts} ${xScale(candles.length - 1)},${PAD.top + ch}`}
              fill="url(#areaGrad)" />
            <polyline points={linePts} fill="none"
              stroke={positive ? '#30d158' : '#ff453a'} strokeWidth="2"
              strokeLinejoin="round" strokeLinecap="round" />
          </>
        ) : (
          candles.map((c, i) => {
            const x = xScale(i)
            const barW = Math.max(2, cw / candles.length - 1)
            const isUp = c.c >= c.o
            const color = isUp ? '#30d158' : '#ff453a'
            return (
              <g key={i}>
                <line x1={x} x2={x} y1={yScale(c.h)} y2={yScale(c.l)} stroke={color} strokeWidth="1" />
                <rect x={x - barW / 2} y={Math.min(yScale(c.o), yScale(c.c))}
                  width={barW} height={Math.max(1, Math.abs(yScale(c.o) - yScale(c.c)))}
                  fill={color} opacity="0.9" />
              </g>
            )
          })
        )}

        {/* Crosshair */}
        {tooltip && (
          <g pointerEvents="none">
            <line x1={tooltip.svgX} x2={tooltip.svgX} y1={PAD.top} y2={PAD.top + ch}
              stroke="rgba(6,182,212,0.6)" strokeWidth="1" strokeDasharray="4,3" />
            <line x1={PAD.left} x2={W - PAD.right} y1={tooltip.svgY} y2={tooltip.svgY}
              stroke="rgba(6,182,212,0.4)" strokeWidth="1" strokeDasharray="4,3" />
            <circle cx={tooltip.svgX} cy={tooltip.closeY} r="3.5"
              fill="#06b6d4" stroke="rgba(6,182,212,0.35)" strokeWidth="5" />
          </g>
        )}

        {/* Buy Price Marker */}
        {buyMarker && buyMarker.buyPrice >= minP && buyMarker.buyPrice <= maxP && (() => {
          const by = yScale(buyMarker.buyPrice)
          const label = `BUY ₹${buyMarker.buyPrice.toLocaleString('en-IN', { minimumFractionDigits: 2 })}  ⏱ ${holdDurationStr(buyMarker.openedAt)}`
          const labelW = label.length * 6.2 + 12
          return (
            <g pointerEvents="none">
              {/* dashed horizontal line */}
              <line x1={PAD.left} x2={W - PAD.right} y1={by} y2={by}
                stroke="#f59e0b" strokeWidth="1.5" strokeDasharray="6,3" opacity="0.9" />
              {/* left pill label */}
              <rect x={PAD.left} y={by - 10} width={labelW} height={18} rx="4"
                fill="rgba(245,158,11,0.18)" stroke="#f59e0b" strokeWidth="1" opacity="0.95" />
              <text x={PAD.left + 6} y={by + 4} fontSize="10" fontFamily="monospace"
                fill="#f59e0b" fontWeight="bold">
                {label}
              </text>
              {/* right price tag */}
              <rect x={W - PAD.right} y={by - 9} width={52} height={16} rx="3"
                fill="#f59e0b" opacity="0.9" />
              <text x={W - PAD.right + 4} y={by + 3} fontSize="9" fontFamily="monospace"
                fill="#000" fontWeight="bold">
                ₹{buyMarker.buyPrice >= 1000
                  ? (buyMarker.buyPrice / 1000).toFixed(1) + 'k'
                  : buyMarker.buyPrice.toFixed(0)}
              </text>
            </g>
          )
        })()}

        {/* C1.3 EMA lines */}
        {overlays && activeOverlays && (
          <g pointerEvents="none">
            {activeOverlays.has('ema9') && overlays.ema9?.map((v, i) => i === 0 ? null : (
              <line key={i} x1={xScale(i-1)} y1={yScale(overlays.ema9[i-1])} x2={xScale(i)} y2={yScale(v)}
                stroke="#f59e0b" strokeWidth="1" opacity="0.9" />
            ))}
            {activeOverlays.has('ema21') && overlays.ema21?.map((v, i) => i === 0 ? null : (
              <line key={i} x1={xScale(i-1)} y1={yScale(overlays.ema21[i-1])} x2={xScale(i)} y2={yScale(v)}
                stroke="#a78bfa" strokeWidth="1" opacity="0.9" />
            ))}
            {activeOverlays.has('ema50') && overlays.ema50?.map((v, i) => i === 0 ? null : (
              <line key={i} x1={xScale(i-1)} y1={yScale(overlays.ema50[i-1])} x2={xScale(i)} y2={yScale(v)}
                stroke="#06b6d4" strokeWidth="1.5" opacity="0.9" />
            ))}
            {activeOverlays.has('ema200') && overlays.ema200?.map((v, i) => i === 0 ? null : (
              <line key={i} x1={xScale(i-1)} y1={yScale(overlays.ema200[i-1])} x2={xScale(i)} y2={yScale(v)}
                stroke="#f97316" strokeWidth="1.5" opacity="0.9" />
            ))}

            {/* C1.4 Bollinger Bands */}
            {activeOverlays.has('bb') && overlays.bb_upper?.map((v, i) => i === 0 ? null : (
              <g key={i}>
                <line x1={xScale(i-1)} y1={yScale(overlays.bb_upper[i-1])} x2={xScale(i)} y2={yScale(v)}
                  stroke="#64748b" strokeWidth="1" strokeDasharray="3,2" opacity="0.7" />
                <line x1={xScale(i-1)} y1={yScale(overlays.bb_lower[i-1])} x2={xScale(i)} y2={yScale(overlays.bb_lower[i])}
                  stroke="#64748b" strokeWidth="1" strokeDasharray="3,2" opacity="0.7" />
                <line x1={xScale(i-1)} y1={yScale(overlays.bb_mid[i-1])} x2={xScale(i)} y2={yScale(overlays.bb_mid[i])}
                  stroke="#94a3b8" strokeWidth="1" strokeDasharray="2,3" opacity="0.5" />
              </g>
            ))}

            {/* C1.5 Supertrend */}
            {activeOverlays.has('supertrend') && overlays.supertrend?.map((v, i) => i === 0 ? null : (
              <line key={i} x1={xScale(i-1)} y1={yScale(overlays.supertrend[i-1])} x2={xScale(i)} y2={yScale(v)}
                stroke={overlays.st_direction?.[i] === 1 ? '#30d158' : '#ff453a'}
                strokeWidth="2" opacity="0.85" />
            ))}

            {/* C1.6 Support / Resistance horizontal lines */}
            {activeOverlays.has('sr') && overlays.support?.slice(0, 3).map((s, i) => (
              <line key={`s${i}`} x1={PAD.left} x2={W - PAD.right} y1={yScale(s)} y2={yScale(s)}
                stroke="#30d158" strokeWidth="1" strokeDasharray="6,3" opacity="0.6" />
            ))}
            {activeOverlays.has('sr') && overlays.resistance?.slice(0, 3).map((r, i) => (
              <line key={`r${i}`} x1={PAD.left} x2={W - PAD.right} y1={yScale(r)} y2={yScale(r)}
                stroke="#ff453a" strokeWidth="1" strokeDasharray="6,3" opacity="0.6" />
            ))}
            {activeOverlays.has('sr') && overlays.pivot > 0 && (
              <line x1={PAD.left} x2={W - PAD.right} y1={yScale(overlays.pivot)} y2={yScale(overlays.pivot)}
                stroke="#06b6d4" strokeWidth="1" strokeDasharray="4,4" opacity="0.5" />
            )}

            {/* C1.7 Fibonacci levels */}
            {activeOverlays.has('fib') && overlays.fibonacci && Object.entries(overlays.fibonacci).map(([key, val]) => (
              <g key={key}>
                <line x1={PAD.left} x2={W - PAD.right} y1={yScale(val)} y2={yScale(val)}
                  stroke="#fbbf24" strokeWidth="1" strokeDasharray="3,4" opacity="0.5" />
                <text x={W - PAD.right + 2} y={yScale(val) + 3} fontSize="8" fill="#fbbf24" opacity="0.7" fontFamily="monospace">
                  {key}
                </text>
              </g>
            ))}
          </g>
        )}
      </svg>
    </div>
  )
}

// ── Fundamentals Panel ────────────────────────────────────────
function FundamentalsPanel({ data, loading }: { data: StockFundamentals | null; loading: boolean }) {
  if (loading) return (
    <div className="flex items-center justify-center py-8 text-jarvis-muted text-sm">
      <RefreshCw size={14} className="animate-spin mr-2" /> Loading fundamentals...
    </div>
  )
  if (!data || data.error) return null

  const sections = [
    {
      title: 'Valuation',
      rows: [
        ['Market Cap', data.market_cap], ['P/E (TTM)', data.pe_ratio],
        ['Forward P/E', data.forward_pe], ['P/B Ratio', data.pb_ratio],
        ['P/S Ratio', data.ps_ratio], ['PEG Ratio', data.peg_ratio],
        ['EV', data.ev], ['EV/EBITDA', data.ev_ebitda], ['EV/Revenue', data.ev_revenue],
      ],
    },
    {
      title: 'Per Share & Dividends',
      rows: [
        ['EPS (TTM)', data.eps], ['Forward EPS', data.forward_eps],
        ['Book Value', data.book_value], ['Dividend Rate', data.dividend_rate],
        ['Dividend Yield', data.dividend_yield], ['Payout Ratio', data.payout_ratio],
        ['Beta', data.beta], ['Shares Out.', data.shares_outstanding], ['Float', data.float_shares],
      ],
    },
    {
      title: 'Financials',
      rows: [
        ['Revenue', data.revenue], ['Gross Profit', data.gross_profit],
        ['EBITDA', data.ebitda], ['Net Income', data.net_income],
        ['Profit Margin', data.profit_margin], ['Operating Margin', data.operating_margin],
        ['Gross Margin', data.gross_margin], ['Revenue Growth', data.revenue_growth],
        ['Earnings Growth', data.earnings_growth],
      ],
    },
    {
      title: 'Balance Sheet',
      rows: [
        ['Total Cash', data.total_cash], ['Total Debt', data.total_debt],
        ['Debt/Equity', data.debt_to_equity], ['Current Ratio', data.current_ratio],
        ['Quick Ratio', data.quick_ratio], ['ROE', data.roe],
        ['ROA', data.roa], ['Free Cash Flow', data.free_cashflow],
        ['Operating CF', data.operating_cashflow],
      ],
    },
    {
      title: 'Price History',
      rows: [
        ['52W High', data['52w_high']], ['52W Low', data['52w_low']],
        ['50D Avg', data['50d_avg']], ['200D Avg', data['200d_avg']],
        ['Short Ratio', data.short_ratio],
      ],
    },
  ]

  return (
    <div className="mt-6 pt-6 border-t border-jarvis-border">
      {/* Company Info */}
      <div className="mb-5 flex items-start justify-between gap-6">
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <span className="text-xs text-jarvis-muted bg-white/5 px-2 py-0.5 rounded">{data.industry}</span>
            <span className="text-xs text-jarvis-muted bg-white/5 px-2 py-0.5 rounded">{data.sector}</span>
            {data.website !== 'N/A' && (
              <a href={data.website} target="_blank" rel="noopener noreferrer"
                className="text-xs text-jarvis-accent flex items-center gap-1 hover:underline">
                <ExternalLink size={10} /> Website
              </a>
            )}
          </div>
          {data.description !== 'N/A' && (
            <p className="text-xs text-jarvis-muted leading-relaxed">{data.description}</p>
          )}
        </div>
        {data.employees !== 'N/A' && (
          <div className="text-right shrink-0 glass rounded-lg p-3">
            <p className="text-[10px] text-jarvis-muted uppercase tracking-wider">Employees</p>
            <p className="text-sm font-mono text-jarvis-text mt-0.5">{Number(data.employees).toLocaleString('en-IN')}</p>
          </div>
        )}
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 xl:grid-cols-3 2xl:grid-cols-5 gap-4">
        {sections.map((section) => (
          <div key={section.title} className="glass rounded-xl p-4">
            <p className="text-[10px] text-jarvis-accent uppercase tracking-wider mb-3 font-semibold">{section.title}</p>
            <div className="space-y-2">
              {section.rows.map(([label, value]) => (
                <div key={label} className="flex items-center justify-between gap-2">
                  <span className="text-[11px] text-jarvis-muted">{label}</span>
                  <span className="text-[11px] font-mono text-jarvis-text shrink-0">{value ?? 'N/A'}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Financials Panel ─────────────────────────────────────────
function FinancialsPanel({ data, loading }: { data: Financials | null; loading: boolean }) {
  const [period, setPeriod] = useState<'annual' | 'quarterly'>('annual')
  const [sheet, setSheet] = useState<'pl' | 'bs' | 'cf'>('pl')

  if (loading) return (
    <div className="flex items-center justify-center py-12 text-jarvis-muted text-sm">
      <RefreshCw size={14} className="animate-spin mr-2" /> Loading financials...
    </div>
  )
  if (!data || data.error) return (
    <div className="py-8 text-center text-jarvis-muted text-xs">{data?.error || 'No financial data available'}</div>
  )

  const rows = period === 'annual'
    ? (sheet === 'pl' ? data.annual_pl : sheet === 'bs' ? data.annual_bs : data.annual_cf)
    : (sheet === 'pl' ? data.quarterly_pl : sheet === 'bs' ? data.quarterly_bs : data.quarterly_cf)

  const plCols = ['date', 'revenue', 'gross_profit', 'operating_income', 'net_income', 'ebitda', 'interest_expense']
  const bsCols = ['date', 'total_assets', 'total_liabilities', 'total_equity', 'total_debt', 'current_assets', 'current_liabilities', 'cash', 'roce']
  const cfCols = ['date', 'operating_cf', 'investing_cf', 'financing_cf', 'free_cashflow', 'capex']
  const cols = sheet === 'pl' ? plCols : sheet === 'bs' ? bsCols : cfCols

  const labels: Record<string, string> = {
    date: 'Period', revenue: 'Revenue', gross_profit: 'Gross Profit', operating_income: 'Op. Income',
    net_income: 'Net Income', ebitda: 'EBITDA', interest_expense: 'Interest Exp.',
    total_assets: 'Total Assets', total_liabilities: 'Total Liab.', total_equity: 'Equity',
    total_debt: 'Total Debt', current_assets: 'Curr. Assets', current_liabilities: 'Curr. Liab.',
    cash: 'Cash', roce: 'ROCE %',
    operating_cf: 'Operating CF', investing_cf: 'Investing CF', financing_cf: 'Financing CF',
    free_cashflow: 'Free CF', capex: 'CapEx',
  }

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex gap-1">
          {(['annual', 'quarterly'] as const).map(p => (
            <button key={p} onClick={() => setPeriod(p)}
              className={`text-xs px-3 py-1 rounded font-mono transition-all ${
                period === p ? 'bg-jarvis-accent/20 text-jarvis-accent border border-jarvis-accent/30' : 'text-jarvis-muted bg-white/5 hover:text-jarvis-text'
              }`}>
              {p === 'annual' ? 'Annual' : 'Quarterly'}
            </button>
          ))}
        </div>
        <div className="flex gap-1">
          {([['pl', 'P&L'], ['bs', 'Balance Sheet'], ['cf', 'Cash Flow']] as const).map(([k, label]) => (
            <button key={k} onClick={() => setSheet(k)}
              className={`text-xs px-3 py-1 rounded font-mono transition-all ${
                sheet === k ? 'bg-jarvis-accent/20 text-jarvis-accent border border-jarvis-accent/30' : 'text-jarvis-muted bg-white/5 hover:text-jarvis-text'
              }`}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      {rows.length === 0 ? (
        <p className="text-center text-jarvis-muted text-xs py-6">No data for this period</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-jarvis-border">
                {cols.map(c => (
                  <th key={c} className="text-left py-2 px-3 text-[10px] text-jarvis-accent uppercase tracking-wider font-semibold whitespace-nowrap">
                    {labels[c]}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i} className="border-b border-jarvis-border/40 hover:bg-white/[0.02] transition-colors">
                  {cols.map(c => (
                    <td key={c} className={`py-2 px-3 font-mono whitespace-nowrap ${
                      c === 'date' ? 'text-jarvis-muted text-[10px]' :
                      c === 'roce' ? 'text-jarvis-accent' : 'text-jarvis-text'
                    }`}>
                      {(row as unknown as Record<string, string | undefined>)[c] ?? 'N/A'}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Shareholding Panel ───────────────────────────────────────
function ShareholdingPanel({ data, loading }: { data: ShareholdingData | null; loading: boolean }) {
  const [view, setView] = useState<'summary' | 'institutions' | 'funds' | 'insiders'>('summary')

  if (loading) return (
    <div className="flex items-center justify-center py-12 text-jarvis-muted text-sm">
      <RefreshCw size={14} className="animate-spin mr-2" /> Loading shareholding...
    </div>
  )
  if (!data || data.error) return (
    <div className="py-8 text-center text-jarvis-muted text-xs">{data?.error || 'No shareholding data available'}</div>
  )

  const summaryItems = [
    { label: 'Promoters / Insiders', value: data.summary.promoters, color: '#06b6d4' },
    { label: 'FII / Institutions', value: data.summary.fii_institutions, color: '#30d158' },
    { label: 'Public / Others', value: data.summary.public, color: '#ff9f0a' },
  ]

  return (
    <div className="space-y-4">
      {/* Tab switcher */}
      <div className="flex gap-1 flex-wrap">
        {([['summary', 'Summary'], ['institutions', 'Institutions'], ['funds', 'Funds'], ['insiders', 'Insiders']] as const).map(([k, label]) => (
          <button key={k} onClick={() => setView(k)}
            className={`text-xs px-3 py-1 rounded font-mono transition-all ${
              view === k ? 'bg-jarvis-accent/20 text-jarvis-accent border border-jarvis-accent/30' : 'text-jarvis-muted bg-white/5 hover:text-jarvis-text'
            }`}>
            {label}
          </button>
        ))}
      </div>

      {view === 'summary' && (
        <div className="space-y-3">
          {summaryItems.map(({ label, value, color }) => {
            const pct = parseFloat(value) || 0
            return (
              <div key={label}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-jarvis-muted">{label}</span>
                  <span className="font-mono" style={{ color }}>{value}</span>
                </div>
                <div className="h-2 bg-white/5 rounded-full overflow-hidden">
                  <div className="h-full rounded-full transition-all" style={{ width: `${Math.min(pct, 100)}%`, backgroundColor: color }} />
                </div>
              </div>
            )
          })}
        </div>
      )}

      {view === 'institutions' && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className="border-b border-jarvis-border">
              <th className="text-left py-2 px-3 text-[10px] text-jarvis-accent uppercase tracking-wider">Institution</th>
              <th className="text-right py-2 px-3 text-[10px] text-jarvis-accent uppercase tracking-wider">% Held</th>
              <th className="text-right py-2 px-3 text-[10px] text-jarvis-accent uppercase tracking-wider">Shares</th>
            </tr></thead>
            <tbody>
              {data.top_institutions.map((inst, i) => (
                <tr key={i} className="border-b border-jarvis-border/40 hover:bg-white/[0.02]">
                  <td className="py-2 px-3 text-jarvis-text">{inst.name}</td>
                  <td className="py-2 px-3 text-right font-mono text-jarvis-neon-green">{inst.pct_held}%</td>
                  <td className="py-2 px-3 text-right font-mono text-jarvis-muted">{inst.shares}</td>
                </tr>
              ))}
              {data.top_institutions.length === 0 && <tr><td colSpan={3} className="py-6 text-center text-jarvis-muted">No data</td></tr>}
            </tbody>
          </table>
        </div>
      )}

      {view === 'funds' && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className="border-b border-jarvis-border">
              <th className="text-left py-2 px-3 text-[10px] text-jarvis-accent uppercase tracking-wider">Fund</th>
              <th className="text-right py-2 px-3 text-[10px] text-jarvis-accent uppercase tracking-wider">% Held</th>
              <th className="text-right py-2 px-3 text-[10px] text-jarvis-accent uppercase tracking-wider">Shares</th>
            </tr></thead>
            <tbody>
              {data.top_funds.map((f, i) => (
                <tr key={i} className="border-b border-jarvis-border/40 hover:bg-white/[0.02]">
                  <td className="py-2 px-3 text-jarvis-text">{f.name}</td>
                  <td className="py-2 px-3 text-right font-mono text-jarvis-neon-green">{f.pct_held}%</td>
                  <td className="py-2 px-3 text-right font-mono text-jarvis-muted">{f.shares}</td>
                </tr>
              ))}
              {data.top_funds.length === 0 && <tr><td colSpan={3} className="py-6 text-center text-jarvis-muted">No data</td></tr>}
            </tbody>
          </table>
        </div>
      )}

      {view === 'insiders' && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className="border-b border-jarvis-border">
              <th className="text-left py-2 px-3 text-[10px] text-jarvis-accent uppercase tracking-wider">Name</th>
              <th className="text-left py-2 px-3 text-[10px] text-jarvis-accent uppercase tracking-wider">Relation</th>
              <th className="text-right py-2 px-3 text-[10px] text-jarvis-accent uppercase tracking-wider">Shares</th>
            </tr></thead>
            <tbody>
              {data.insiders.map((ins, i) => (
                <tr key={i} className="border-b border-jarvis-border/40 hover:bg-white/[0.02]">
                  <td className="py-2 px-3 text-jarvis-text">{ins.name}</td>
                  <td className="py-2 px-3 text-jarvis-muted">{ins.relation}</td>
                  <td className="py-2 px-3 text-right font-mono text-jarvis-muted">{ins.shares}</td>
                </tr>
              ))}
              {data.insiders.length === 0 && <tr><td colSpan={3} className="py-6 text-center text-jarvis-muted">No data</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Peers Panel ───────────────────────────────────────────────
function PeersPanel({ data, loading, currentSymbol }: { data: PeerStock[]; loading: boolean; currentSymbol: string }) {
  if (loading) return (
    <div className="flex items-center justify-center py-12 text-jarvis-muted text-sm">
      <RefreshCw size={14} className="animate-spin mr-2" /> Loading peers...
    </div>
  )
  if (!data.length) return (
    <div className="py-8 text-center text-jarvis-muted text-xs">No peer data available</div>
  )

  const cols: { key: keyof PeerStock; label: string }[] = [
    { key: 'name', label: 'Company' },
    { key: 'price', label: 'Price' },
    { key: 'market_cap', label: 'Mkt Cap' },
    { key: 'pe_ratio', label: 'P/E' },
    { key: 'pb_ratio', label: 'P/B' },
    { key: 'roe', label: 'ROE' },
    { key: 'roa', label: 'ROA' },
    { key: 'profit_margin', label: 'Net Margin' },
    { key: 'revenue_growth', label: 'Rev Growth' },
    { key: 'debt_to_equity', label: 'D/E' },
    { key: 'eps', label: 'EPS' },
    { key: 'dividend_yield', label: 'Div Yield' },
  ]

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-jarvis-border">
            {cols.map(c => (
              <th key={c.key} className="text-left py-2 px-3 text-[10px] text-jarvis-accent uppercase tracking-wider whitespace-nowrap font-semibold">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((peer, i) => (
            <tr key={i} className={`border-b border-jarvis-border/40 hover:bg-white/[0.02] transition-colors ${
              peer.symbol === currentSymbol ? 'bg-jarvis-accent/5' : ''
            }`}>
              {cols.map(c => (
                <td key={c.key} className={`py-2 px-3 whitespace-nowrap ${
                  c.key === 'name' ? 'text-jarvis-text font-medium' :
                  c.key === 'symbol' ? 'text-jarvis-accent font-mono' :
                  'text-jarvis-muted font-mono'
                }`}>
                  {c.key === 'name'
                    ? <><span className="text-jarvis-accent font-mono mr-1">{peer.symbol}</span>{peer.name}</>
                    : String(peer[c.key] ?? 'N/A')
                  }
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Screener Panel ────────────────────────────────────────────
function ScreenerPanel({ results, loading, onRun }: {
  results: ScreenerResult[]
  loading: boolean
  onRun: (filters: Record<string, string>) => void
}) {
  const [filters, setFilters] = useState<Record<string, string>>({
    min_pe: '', max_pe: '', min_roe: '', max_debt_equity: '',
    min_market_cap: '', min_profit_margin: '', sector: '',
  })

  const sectors = ['', 'IT', 'Banking', 'Energy', 'FMCG', 'Auto', 'Pharma', 'Finance', 'Metal', 'Infra', 'Power', 'Insurance', 'Cement', 'Consumer', 'Healthcare', 'Mining', 'Agro', 'Paints', 'Conglomerate']

  const set = (k: string, v: string) => setFilters(f => ({ ...f, [k]: v }))

  const handleRun = () => {
    const active = Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== ''))
    onRun(active)
  }

  const inputCls = 'bg-white/5 border border-jarvis-border rounded px-2 py-1 text-xs text-jarvis-text font-mono outline-none focus:border-jarvis-accent/50 w-full placeholder-jarvis-muted/50'

  return (
    <div className="space-y-5">
      {/* Filter Form */}
      <div className="glass rounded-xl p-4">
        <p className="text-[10px] text-jarvis-accent uppercase tracking-wider mb-3 font-semibold">Filters</p>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          <div>
            <label className="text-[10px] text-jarvis-muted block mb-1">Min P/E</label>
            <input className={inputCls} placeholder="e.g. 5" value={filters.min_pe} onChange={e => set('min_pe', e.target.value)} />
          </div>
          <div>
            <label className="text-[10px] text-jarvis-muted block mb-1">Max P/E</label>
            <input className={inputCls} placeholder="e.g. 30" value={filters.max_pe} onChange={e => set('max_pe', e.target.value)} />
          </div>
          <div>
            <label className="text-[10px] text-jarvis-muted block mb-1">Min ROE (%)</label>
            <input className={inputCls} placeholder="e.g. 15" value={filters.min_roe} onChange={e => set('min_roe', e.target.value)} />
          </div>
          <div>
            <label className="text-[10px] text-jarvis-muted block mb-1">Max Debt/Equity</label>
            <input className={inputCls} placeholder="e.g. 1" value={filters.max_debt_equity} onChange={e => set('max_debt_equity', e.target.value)} />
          </div>
          <div>
            <label className="text-[10px] text-jarvis-muted block mb-1">Min Profit Margin (%)</label>
            <input className={inputCls} placeholder="e.g. 10" value={filters.min_profit_margin} onChange={e => set('min_profit_margin', e.target.value)} />
          </div>
          <div>
            <label className="text-[10px] text-jarvis-muted block mb-1">Sector</label>
            <select className={inputCls} value={filters.sector} onChange={e => set('sector', e.target.value)}>
              {sectors.map(s => <option key={s} value={s} className="bg-jarvis-bg">{s || 'All Sectors'}</option>)}
            </select>
          </div>
        </div>
        <button onClick={handleRun} disabled={loading}
          className="mt-4 px-5 py-1.5 text-xs font-mono rounded bg-jarvis-accent/20 text-jarvis-accent border border-jarvis-accent/30 hover:bg-jarvis-accent/30 transition-all disabled:opacity-40 flex items-center gap-2">
          {loading ? <><RefreshCw size={11} className="animate-spin" /> Screening...</> : '🔍 Run Screener'}
        </button>
      </div>

      {/* Results */}
      {results.length > 0 && (
        <div className="overflow-x-auto">
          <p className="text-[10px] text-jarvis-muted mb-2">{results.length} stocks matched</p>
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-jarvis-border">
                {['Symbol', 'Name', 'Sector', 'Price', 'Chg%', 'P/E', 'ROE', 'D/E', 'Mkt Cap', 'Net Margin', 'EPS', 'Div Yield', 'P/B'].map(h => (
                  <th key={h} className="text-left py-2 px-3 text-[10px] text-jarvis-accent uppercase tracking-wider whitespace-nowrap font-semibold">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {results.map((r, i) => (
                <tr key={i} className="border-b border-jarvis-border/40 hover:bg-white/[0.02] transition-colors">
                  <td className="py-2 px-3 font-mono text-jarvis-accent">{r.symbol}</td>
                  <td className="py-2 px-3 text-jarvis-text whitespace-nowrap">{r.name}</td>
                  <td className="py-2 px-3 text-jarvis-muted">{r.sector}</td>
                  <td className="py-2 px-3 font-mono text-jarvis-text">₹{r.price?.toLocaleString('en-IN')}</td>
                  <td className={`py-2 px-3 font-mono ${ r.change_pct >= 0 ? 'text-jarvis-neon-green' : 'text-jarvis-neon-red'}`}>
                    {r.change_pct >= 0 ? '+' : ''}{r.change_pct?.toFixed(2)}%
                  </td>
                  <td className="py-2 px-3 font-mono text-jarvis-muted">{r.pe_ratio}</td>
                  <td className="py-2 px-3 font-mono text-jarvis-muted">{r.roe}</td>
                  <td className="py-2 px-3 font-mono text-jarvis-muted">{r.debt_to_equity}</td>
                  <td className="py-2 px-3 font-mono text-jarvis-muted">{r.market_cap}</td>
                  <td className="py-2 px-3 font-mono text-jarvis-muted">{r.profit_margin}</td>
                  <td className="py-2 px-3 font-mono text-jarvis-muted">{r.eps}</td>
                  <td className="py-2 px-3 font-mono text-jarvis-muted">{r.dividend_yield}</td>
                  <td className="py-2 px-3 font-mono text-jarvis-muted">{r.pb_ratio}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Forecast Panel ───────────────────────────────────────────
function ForecastPanel({ data, loading, onRun }: {
  data: ForecastResult | null
  loading: boolean
  onRun: () => void
}) {
  if (loading) return (
    <div className="flex flex-col items-center justify-center py-16 gap-3 text-jarvis-muted">
      <RefreshCw size={20} className="animate-spin text-jarvis-accent" />
      <p className="text-sm">Training XGBoost model on 5-day history...</p>
      <p className="text-xs text-jarvis-muted/60">Building 51 features · Sliding window training · Predicting 30-min direction</p>
    </div>
  )
  if (!data) return (
    <div className="flex flex-col items-center justify-center py-16 gap-4">
      <div className="text-5xl">🔮</div>
      <p className="text-sm text-jarvis-muted">Run 30-minute price forecast using XGBoost + 50 indicators</p>
      <button onClick={onRun} className="px-6 py-2 text-xs font-mono rounded-lg bg-jarvis-accent/20 text-jarvis-accent border border-jarvis-accent/30 hover:bg-jarvis-accent/30 transition-all">
        🚀 Run Forecast
      </button>
    </div>
  )
  if (data.error) return (
    <div className="flex flex-col items-center justify-center py-16 gap-4">
      <p className="text-sm text-jarvis-neon-red">{data.error}</p>
      {data.error === 'model_training_failed' && <p className="text-xs text-jarvis-muted font-mono">pip install xgboost scikit-learn</p>}
      <button onClick={onRun} className="px-4 py-1.5 text-xs font-mono rounded bg-jarvis-accent/20 text-jarvis-accent border border-jarvis-accent/30 hover:bg-jarvis-accent/30 transition-all">Retry</button>
    </div>
  )
  const fc = data.forecast
  const ctx = data.context
  const dirColor = fc.direction === 'UP' ? '#30d158' : fc.direction === 'DOWN' ? '#ff453a' : '#ff9f0a'
  const DirIcon = fc.direction === 'UP' ? TrendingUp : fc.direction === 'DOWN' ? TrendingDown : Minus
  return (
    <div className="space-y-5">
      <div className={`glass rounded-2xl p-5 border ${ fc.direction === 'UP' ? 'border-jarvis-neon-green/30' : fc.direction === 'DOWN' ? 'border-jarvis-neon-red/30' : 'border-yellow-500/30' }`}>
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3 mb-3">
              <DirIcon size={28} style={{ color: dirColor }} />
              <span className="text-3xl font-black font-mono" style={{ color: dirColor }}>{fc.direction}</span>
              <div className="flex flex-col"><span className="text-[10px] text-jarvis-muted">Confidence</span><span className="text-lg font-mono font-bold" style={{ color: dirColor }}>{fc.confidence}%</span></div>
              <div className="flex flex-col"><span className="text-[10px] text-jarvis-muted">Horizon</span><span className="text-xs font-mono text-jarvis-text">{fc.horizon}</span></div>
              <div className="flex flex-col"><span className="text-[10px] text-jarvis-muted">Model</span><span className="text-xs font-mono text-jarvis-accent">{fc.model}</span></div>
            </div>
            <div className="w-64 h-2 bg-white/5 rounded-full overflow-hidden mb-3">
              <div className="h-full rounded-full" style={{ width: `${fc.confidence}%`, backgroundColor: dirColor }} />
            </div>
            <div className="flex gap-4">
              {([['UP', fc.prob_up, '#30d158'], ['DOWN', fc.prob_down, '#ff453a'], ['FLAT', fc.prob_flat, '#ff9f0a']] as [string, number, string][]).map(([label, val, color]) => (
                <div key={label} className="flex flex-col items-center gap-1">
                  <span className="text-[10px] text-jarvis-muted">{label}</span>
                  <div className="w-16 h-1.5 bg-white/5 rounded-full overflow-hidden"><div className="h-full rounded-full" style={{ width: `${val}%`, backgroundColor: color }} /></div>
                  <span className="text-[10px] font-mono" style={{ color }}>{val.toFixed(1)}%</span>
                </div>
              ))}
            </div>
          </div>
          <button onClick={onRun} className="text-jarvis-muted hover:text-jarvis-accent transition-colors"><RefreshCw size={14} /></button>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-3">
        {([['Current', `₹${fc.current_price.toLocaleString('en-IN')}`, '#94a3b8'], ['Est. Target', `₹${fc.estimated_target.toLocaleString('en-IN')}`, dirColor], ['Est. Low', `₹${fc.estimated_low.toLocaleString('en-IN')}`, '#ff453a']] as [string, string, string][]).map(([label, value, color]) => (
          <div key={label} className="glass rounded-xl p-3 text-center">
            <p className="text-[10px] text-jarvis-muted uppercase tracking-wider mb-1">{label}</p>
            <p className="text-sm font-mono font-bold" style={{ color }}>{value}</p>
          </div>
        ))}
      </div>
      <div className="glass rounded-xl p-4">
        <p className="text-[10px] text-jarvis-accent uppercase tracking-wider mb-3 font-semibold">Market Context</p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {([['Trend', ctx.trend?.replace(/_/g, ' ')], ['TA Signal', ctx.overall_signal], ['RSI', ctx.rsi?.toFixed(1)], ['Supertrend', ctx.supertrend], ['Ichimoku', ctx.ichimoku_bias], ['Nearest Res.', ctx.nearest_resistance ? `₹${ctx.nearest_resistance}` : 'N/A'], ['Nearest Sup.', ctx.nearest_support ? `₹${ctx.nearest_support}` : 'N/A'], ['ATR', ctx.atr?.toFixed(2)]] as [string, string | undefined][]).map(([label, value]) => (
            <div key={label} className="text-center">
              <p className="text-[9px] text-jarvis-muted uppercase tracking-wider">{label}</p>
              <p className="text-xs font-mono text-jarvis-text capitalize">{value ?? 'N/A'}</p>
            </div>
          ))}
        </div>
      </div>
      {(data.bos_choch.length > 0 || data.order_blocks.length > 0 || data.fvg.length > 0) && (
        <div className="glass rounded-xl p-4">
          <p className="text-[10px] text-jarvis-accent uppercase tracking-wider mb-3 font-semibold">Smart Money Concepts</p>
          <div className="space-y-2">
            {data.bos_choch.map((e, i) => (
              <div key={i} className="flex items-center gap-3">
                <span className={`text-[10px] px-2 py-0.5 rounded font-mono font-bold shrink-0 ${ e.direction === 'bullish' ? 'bg-jarvis-neon-green/10 text-jarvis-neon-green' : 'bg-jarvis-neon-red/10 text-jarvis-neon-red' }`}>{e.type}</span>
                <span className="text-[11px] text-jarvis-text">{e.desc}</span>
              </div>
            ))}
            {data.order_blocks.map((ob, i) => (
              <div key={i} className="flex items-center gap-3">
                <span className={`text-[10px] px-2 py-0.5 rounded font-mono font-bold shrink-0 ${ ob.type === 'bullish' ? 'bg-jarvis-neon-green/10 text-jarvis-neon-green' : 'bg-jarvis-neon-red/10 text-jarvis-neon-red' }`}>OB</span>
                <span className="text-[11px] text-jarvis-text">{ob.desc}</span>
              </div>
            ))}
            {data.fvg.map((f, i) => (
              <div key={i} className="flex items-center gap-3">
                <span className={`text-[10px] px-2 py-0.5 rounded font-mono font-bold shrink-0 ${ f.type === 'bullish' ? 'bg-jarvis-neon-green/10 text-jarvis-neon-green' : 'bg-jarvis-neon-red/10 text-jarvis-neon-red' }`}>FVG</span>
                <span className="text-[11px] text-jarvis-text">{f.desc}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      {data.signals_summary.length > 0 && (
        <div className="glass rounded-xl p-4">
          <p className="text-[10px] text-jarvis-accent uppercase tracking-wider mb-3 font-semibold">Top Signals Used</p>
          <div className="space-y-2">
            {data.signals_summary.map((s, i) => (
              <div key={i} className="flex items-center gap-3">
                <span className={`text-[10px] px-2 py-0.5 rounded font-mono font-bold shrink-0 ${ s.signal === 'buy' ? 'bg-jarvis-neon-green/10 text-jarvis-neon-green' : s.signal === 'sell' ? 'bg-jarvis-neon-red/10 text-jarvis-neon-red' : 'bg-white/5 text-jarvis-muted' }`}>{s.signal.toUpperCase()}</span>
                <span className="text-[10px] text-jarvis-muted shrink-0 w-24">{s.indicator}</span>
                <span className="text-[11px] text-jarvis-text">{s.reason}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      <p className="text-[10px] text-jarvis-muted/50 text-center">Trained on {data.candles_used} candles · XGBoost classifier · Not financial advice</p>
    </div>
  )
}

// ── Budget Advisor Panel ──────────────────────────────────────
function BudgetAdvisorPanel({ data, loading, onRun }: {
  data: BudgetAdvice | null
  loading: boolean
  onRun: (budget: number, topN: number) => void
}) {
  const [budget, setBudget] = useState('50000')
  const [topN, setTopN] = useState('5')
  const gradeColor = (g: string) => g === 'A+' ? '#30d158' : g === 'A' ? '#06b6d4' : g === 'B' ? '#ff9f0a' : '#ff453a'
  return (
    <div className="space-y-5">
      <div className="glass rounded-xl p-4">
        <p className="text-[10px] text-jarvis-accent uppercase tracking-wider mb-3 font-semibold">Budget Settings</p>
        <div className="flex items-end gap-3 flex-wrap">
          <div>
            <label className="text-[10px] text-jarvis-muted block mb-1">Your Budget (₹)</label>
            <input type="number" value={budget} onChange={e => setBudget(e.target.value)}
              className="bg-white/5 border border-jarvis-border rounded px-3 py-1.5 text-xs text-jarvis-text font-mono outline-none focus:border-jarvis-accent/50 w-36" placeholder="50000" />
          </div>
          <div>
            <label className="text-[10px] text-jarvis-muted block mb-1">Top N Picks</label>
            <select value={topN} onChange={e => setTopN(e.target.value)}
              className="bg-white/5 border border-jarvis-border rounded px-3 py-1.5 text-xs text-jarvis-text font-mono outline-none focus:border-jarvis-accent/50 w-20">
              {[3, 5, 7, 10].map(n => <option key={n} value={n} className="bg-jarvis-bg">{n}</option>)}
            </select>
          </div>
          <button onClick={() => onRun(parseFloat(budget) || 50000, parseInt(topN) || 5)} disabled={loading}
            className="px-5 py-1.5 text-xs font-mono rounded bg-jarvis-accent/20 text-jarvis-accent border border-jarvis-accent/30 hover:bg-jarvis-accent/30 transition-all disabled:opacity-40 flex items-center gap-2">
            {loading ? <><RefreshCw size={11} className="animate-spin" /> Analyzing...</> : '💰 Get Recommendations'}
          </button>
        </div>
      </div>
      {data?.error && <p className="text-center text-jarvis-neon-red text-xs py-4">{data.error}</p>}
      {data && !data.error && (
        <>
          <div className="glass rounded-xl p-4">
            <p className="text-[10px] text-jarvis-accent uppercase tracking-wider mb-3 font-semibold">Summary</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {([['Budget', `₹${data.budget.toLocaleString('en-IN')}`], ['Top Pick', data.summary.top_pick ?? 'N/A'], ['Avg Score', `${data.summary.avg_score}/100`], ['Best Grade', data.summary.best_grade ?? 'N/A'], ['Analyzed', String(data.stocks_analyzed)], ['Affordable', String(data.stocks_affordable)], ['Total Cost', `₹${data.summary.total_if_all_bought?.toLocaleString('en-IN')}`], ['Leftover', `₹${data.summary.leftover_if_all_bought?.toLocaleString('en-IN')}`]] as [string, string][]).map(([label, value]) => (
                <div key={label} className="text-center">
                  <p className="text-[9px] text-jarvis-muted uppercase tracking-wider">{label}</p>
                  <p className="text-xs font-mono text-jarvis-text">{value}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="space-y-3">
            {data.recommendations.map((rec, i) => (
              <div key={rec.symbol} className="glass rounded-xl p-4 border border-jarvis-border hover:border-jarvis-accent/20 transition-all">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span className="text-sm font-mono font-bold text-jarvis-accent">#{i + 1} {rec.symbol}</span>
                      <span className="text-xs text-jarvis-muted">{rec.name}</span>
                      <span className="text-[10px] bg-white/5 text-jarvis-muted px-1.5 py-0.5 rounded">{rec.sector}</span>
                      <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded" style={{ color: gradeColor(rec.grade), backgroundColor: `${gradeColor(rec.grade)}15` }}>{rec.grade}</span>
                      <span className={`text-[10px] px-2 py-0.5 rounded font-mono ${ rec.signal === 'BUY' ? 'bg-jarvis-neon-green/10 text-jarvis-neon-green' : rec.signal === 'SELL' ? 'bg-jarvis-neon-red/10 text-jarvis-neon-red' : 'bg-yellow-500/10 text-yellow-400' }`}>{rec.signal}</span>
                    </div>
                    <div className="flex items-center gap-2 mb-2">
                      <div className="w-32 h-1.5 bg-white/5 rounded-full overflow-hidden"><div className="h-full rounded-full" style={{ width: `${rec.score}%`, backgroundColor: gradeColor(rec.grade) }} /></div>
                      <span className="text-[10px] font-mono text-jarvis-muted">{rec.score}/100</span>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {rec.reasons.map((r, j) => <span key={j} className="text-[10px] bg-white/5 text-jarvis-muted px-2 py-0.5 rounded">{r}</span>)}
                    </div>
                  </div>
                  <div className="shrink-0 text-right">
                    <p className="text-base font-mono font-bold text-jarvis-text">₹{rec.price.toLocaleString('en-IN')}</p>
                    <p className="text-[10px] text-jarvis-muted">Qty: <span className="text-jarvis-accent font-mono font-bold">{rec.qty}</span></p>
                    <p className="text-[10px] text-jarvis-muted">Cost: <span className="font-mono text-jarvis-text">₹{rec.cost.toLocaleString('en-IN')}</span></p>
                    <p className="text-[10px] text-jarvis-muted">Split: <span className="font-mono text-jarvis-accent">{rec.suggested_qty_equal_split}</span></p>
                  </div>
                </div>
                <div className="grid grid-cols-4 gap-2 mt-3 pt-3 border-t border-jarvis-border/40">
                  {([['Stop Loss', `₹${rec.stop_loss}`, '#ff453a'], ['Target 1', `₹${rec.target1}`, '#30d158'], ['Target 2', `₹${rec.target2}`, '#30d158'], ['R:R', `1:${rec.risk_reward}`, '#06b6d4']] as [string, string, string][]).map(([label, value, color]) => (
                    <div key={label} className="text-center">
                      <p className="text-[9px] text-jarvis-muted uppercase tracking-wider">{label}</p>
                      <p className="text-[11px] font-mono" style={{ color }}>{value}</p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
            {data.recommendations.length === 0 && <p className="text-center text-jarvis-muted text-xs py-8">No stocks found within budget or all signals are weak today.</p>}
          </div>
          <p className="text-[10px] text-jarvis-muted/50 text-center">Based on real-time TA scoring · Not financial advice</p>
        </>
      )}
      {!data && !loading && (
        <div className="flex flex-col items-center justify-center py-12 gap-3 text-jarvis-muted">
          <div className="text-4xl">💰</div>
          <p className="text-sm">Enter your budget and get the best Nifty 50 picks for today</p>
        </div>
      )}
    </div>
  )
}

// ── Weekend check (IST) ──────────────────────────────────────
function WeekendBanner() {
  const now = new Date()
  const istDay = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Kolkata' })).getDay()
  if (istDay !== 0 && istDay !== 6) return null
  const dayName = istDay === 0 ? 'Sunday' : 'Saturday'
  const nextOpen = istDay === 6 ? 'Monday' : 'Monday'
  return (
    <div className="flex items-start gap-3 glass rounded-xl px-4 py-3 border border-yellow-500/30 bg-yellow-500/5 mb-1">
      <span className="text-lg">🏖️</span>
      <div>
        <p className="text-xs font-semibold text-yellow-400">Markets are closed — it's {dayName}</p>
        <p className="text-[11px] text-jarvis-muted mt-0.5">
          NSE &amp; BSE are closed on weekends. Analysis below is based on <span className="text-jarvis-accent">Friday's last session</span> data.
          Live trading resumes {nextOpen} at 9:15 AM IST.
        </p>
      </div>
    </div>
  )
}

// ── Alert System ─────────────────────────────────────────────
function useAlerts() {
  const notifPermission = useRef<NotificationPermission>('default')

  useEffect(() => {
    if ('Notification' in window) {
      notifPermission.current = Notification.permission
      if (Notification.permission === 'default') {
        Notification.requestPermission().then(p => { notifPermission.current = p })
      }
    }
  }, [])

  const playSound = (signal: 'BUY' | 'SELL' | 'HOLD') => {
    try {
      const ctx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)()
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.connect(gain)
      gain.connect(ctx.destination)
      osc.frequency.value = signal === 'BUY' ? 880 : signal === 'SELL' ? 440 : 660
      osc.type = signal === 'BUY' ? 'sine' : signal === 'SELL' ? 'sawtooth' : 'triangle'
      gain.gain.setValueAtTime(0.3, ctx.currentTime)
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.6)
      osc.start(ctx.currentTime)
      osc.stop(ctx.currentTime + 0.6)
    } catch {}
  }

  const sendNotification = (symbol: string, prev: string, next: string, confidence: number, price: number) => {
    if (!('Notification' in window) || notifPermission.current !== 'granted') return
    const emoji = next === 'BUY' ? '🟢' : next === 'SELL' ? '🔴' : '🟡'
    new Notification(`${emoji} ${symbol} — Signal Changed!`, {
      body: `${prev} → ${next} | Confidence: ${confidence}% | ₹${price.toLocaleString('en-IN')}`,
      icon: '/favicon.ico',
    })
  }

  return { playSound, sendNotification }
}

// ── Live Monitor Hook ────────────────────────────────────────
function useAnalysisMonitor(
  symbol: string | null,
  monitorOn: boolean,
  intervalMs: number,
  onRefresh: () => void,
) {
  const [countdown, setCountdown] = useState(intervalMs / 1000)

  useEffect(() => {
    if (!monitorOn || !symbol) { setCountdown(intervalMs / 1000); return }
    setCountdown(intervalMs / 1000)
    // countdown ticker
    const ticker = setInterval(() => setCountdown(c => Math.max(0, c - 1)), 1000)
    // actual refresh
    const refresher = setInterval(() => {
      onRefresh()
      setCountdown(intervalMs / 1000)
    }, intervalMs)
    return () => { clearInterval(ticker); clearInterval(refresher) }
  }, [monitorOn, symbol, intervalMs, onRefresh])

  return countdown
}

function AnalysisPanel({ data, loading, onRun, forecast, forecastLoading, onRunForecast, history, symbol }: {
  data: AIAnalysis | null
  loading: boolean
  onRun: () => void
  forecast: ForecastResult | null
  forecastLoading: boolean
  onRunForecast: (horizon: number) => void
  history: AnalysisSnapshot[]
  symbol: string | null
}) {
  const [forecastHorizon, setForecastHorizon] = useState<15 | 30>(30)
  const [monitorOn, setMonitorOn] = useState(false)
  const [refreshInterval, setRefreshInterval] = useState<1 | 5 | 15>(5)
  const [alertsOn, setAlertsOn] = useState(true)
  const { playSound, sendNotification } = useAlerts()
  const openQuickTrade = useJarvisStore(s => s.openQuickTrade)
  const prevSignalRef = useRef<string | null>(null)

  // Fire alert when signal changes
  useEffect(() => {
    if (history.length < 2) { prevSignalRef.current = history[0]?.signal ?? null; return }
    const latest = history[0]
    const prev = history[1]
    if (prev.signal !== latest.signal && prevSignalRef.current !== latest.signal) {
      prevSignalRef.current = latest.signal
      if (alertsOn) {
        playSound(latest.signal)
        sendNotification(symbol ?? '', prev.signal, latest.signal, latest.confidence, latest.price)
      }
    }
  }, [history])

  // IST weekend check — pause monitor on weekends
  const isWeekend = (() => {
    const d = new Date(new Date().toLocaleString('en-US', { timeZone: 'Asia/Kolkata' })).getDay()
    return d === 0 || d === 6
  })()

  const countdown = useAnalysisMonitor(
    symbol,
    monitorOn && !isWeekend,
    refreshInterval * 60 * 1000,
    onRun,
  )

  // detect signal change between last two history entries
  const signalChanged = history.length >= 2 && history[0].signal !== history[1].signal

  if (loading && !data) return (
    <div className="flex flex-col items-center justify-center py-16 gap-3 text-jarvis-muted">
      <RefreshCw size={20} className="animate-spin text-jarvis-accent" />
      <p className="text-sm">AI is analyzing the chart...</p>
      <p className="text-xs text-jarvis-muted/60">Computing indicators · Detecting patterns · Generating insights</p>
    </div>
  )

  if (!data) return (
    <div className="flex flex-col items-center justify-center py-16 gap-4">
      <div className="text-5xl">🤖</div>
      <p className="text-sm text-jarvis-muted">Click to run AI analysis on this stock</p>
      <button onClick={onRun}
        className="px-6 py-2 text-xs font-mono rounded-lg bg-jarvis-accent/20 text-jarvis-accent border border-jarvis-accent/30 hover:bg-jarvis-accent/30 transition-all">
        🔬 Run AI Analysis
      </button>
    </div>
  )

  if (data.error) return (
    <div className="py-8 text-center text-jarvis-muted text-xs">{data.error}</div>
  )

  const ai = data.ai_analysis
  const ta = data.technical
  const signalColor = ai.signal === 'BUY' ? '#30d158' : ai.signal === 'SELL' ? '#ff453a' : '#ff9f0a'
  const signalBg = ai.signal === 'BUY' ? 'bg-jarvis-neon-green/10 border-jarvis-neon-green/30' : ai.signal === 'SELL' ? 'bg-jarvis-neon-red/10 border-jarvis-neon-red/30' : 'bg-yellow-500/10 border-yellow-500/30'

  return (
    <div className="space-y-5">

      <WeekendBanner />

      {/* ── Live Monitor Controls ── */}
      <div className="flex items-center gap-3 flex-wrap glass rounded-xl px-4 py-2.5 border border-jarvis-border">
        <span className="text-[10px] text-jarvis-accent uppercase tracking-wider font-semibold">🔴 Live Monitor</span>
        {/* ON/OFF toggle */}
        <button
          onClick={() => setMonitorOn(v => !v)}
          disabled={isWeekend}
          className={`relative w-10 h-5 rounded-full transition-all shrink-0 ${
            monitorOn && !isWeekend ? 'bg-jarvis-neon-green/70' : 'bg-white/10'
          } disabled:opacity-40`}
        >
          <span className={`absolute top-0.5 w-4 h-4 rounded-full transition-all ${
            monitorOn && !isWeekend ? 'left-5 bg-jarvis-neon-green' : 'left-0.5 bg-jarvis-muted'
          }`} />
        </button>
        {/* Interval selector */}
        <select
          value={refreshInterval}
          onChange={e => setRefreshInterval(Number(e.target.value) as 1 | 5 | 15)}
          className="bg-white/5 border border-jarvis-border rounded px-2 py-0.5 text-[10px] font-mono text-jarvis-accent outline-none focus:border-jarvis-accent/50"
        >
          <option value={1} className="bg-jarvis-bg">Every 1 min</option>
          <option value={5} className="bg-jarvis-bg">Every 5 min</option>
          <option value={15} className="bg-jarvis-bg">Every 15 min</option>
        </select>
        {/* Status */}
        {monitorOn && !isWeekend ? (
          <span className="text-[10px] font-mono text-jarvis-muted flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-jarvis-neon-green animate-pulse inline-block" />
            {loading ? 'Refreshing...' : `Next refresh in ${countdown}s`}
          </span>
        ) : isWeekend ? (
          <span className="text-[10px] text-yellow-400">Paused — market closed</span>
        ) : (
          <span className="text-[10px] text-jarvis-muted">Off — manual mode</span>
        )}
        {/* Signal changed badge */}
        {signalChanged && (
          <span className="ml-auto text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-yellow-500/20 text-yellow-400 animate-pulse">
            ⚡ Signal Changed!
          </span>
        )}
        {/* Alerts toggle */}
        <div className="ml-auto flex items-center gap-1.5">
          <span className="text-[10px] text-jarvis-muted">🔔 Alerts</span>
          <button
            onClick={() => setAlertsOn(v => !v)}
            className={`relative w-8 h-4 rounded-full transition-all ${
              alertsOn ? 'bg-jarvis-accent/70' : 'bg-white/10'
            }`}
          >
            <span className={`absolute top-0.5 w-3 h-3 rounded-full transition-all ${
              alertsOn ? 'left-4 bg-jarvis-accent' : 'left-0.5 bg-jarvis-muted'
            }`} />
          </button>
        </div>
      </div>

      {/* ── Signal History Strip ── */}
      {history.length > 0 && (
        <div className="glass rounded-xl px-4 py-3 border border-jarvis-border">
          <p className="text-[10px] text-jarvis-accent uppercase tracking-wider font-semibold mb-2">📜 Signal History</p>
          <div className="flex gap-2 overflow-x-auto pb-1">
            {history.map((snap, i) => {
              const sc = snap.signal === 'BUY' ? '#30d158' : snap.signal === 'SELL' ? '#ff453a' : '#ff9f0a'
              const isLatest = i === 0
              return (
                <div key={snap.timestamp} className={`shrink-0 glass rounded-lg px-3 py-2 text-center border ${
                  isLatest ? 'border-jarvis-accent/40' : 'border-jarvis-border'
                }`}>
                  <p className="text-[9px] text-jarvis-muted mb-0.5">
                    {new Date(snap.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Kolkata' })}
                  </p>
                  <p className="text-xs font-mono font-bold" style={{ color: sc }}>{snap.signal}</p>
                  <p className="text-[9px] font-mono text-jarvis-muted">{snap.confidence}%</p>
                  <p className="text-[9px] font-mono text-jarvis-muted">₹{snap.price.toLocaleString('en-IN')}</p>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* ── 📊 Today's Signal Card ── */}
      <div className={`glass rounded-2xl p-5 border ${signalBg} transition-all ${
        loading ? 'opacity-60' : ''
      }`}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[10px] text-jarvis-accent uppercase tracking-widest font-semibold mb-2">📊 Today's Signal</p>
            <div className="flex items-center gap-3 mb-2">
              <span className="text-3xl font-black font-mono" style={{ color: signalColor }}>{ai.signal}</span>
              <div className="flex flex-col">
                <span className="text-xs text-jarvis-muted">Confidence</span>
                <span className="text-lg font-mono font-bold" style={{ color: signalColor }}>{ai.confidence}%</span>
              </div>
              <div className="flex flex-col">
                <span className="text-xs text-jarvis-muted">Timeframe</span>
                <span className="text-xs font-mono text-jarvis-text capitalize">{ai.timeframe}</span>
              </div>
              <div className="flex flex-col">
                <span className="text-xs text-jarvis-muted">Source</span>
                <span className="text-xs font-mono text-jarvis-accent">{ai.source === 'ai' ? '🤖 AI' : '📐 Rules'}</span>
              </div>
            </div>
            {/* Confidence bar */}
            <div className="w-64 h-2 bg-white/5 rounded-full overflow-hidden mb-3">
              <div className="h-full rounded-full transition-all" style={{ width: `${ai.confidence}%`, backgroundColor: signalColor }} />
            </div>
            <p className="text-sm text-jarvis-text leading-relaxed max-w-xl">{ai.summary}</p>
          </div>
          <button onClick={onRun} className="shrink-0 text-jarvis-muted hover:text-jarvis-accent transition-colors" title="Re-run analysis">
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      {/* Price Levels */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'Entry', value: ai.entry_price, color: '#06b6d4' },
          { label: 'Stop Loss', value: ai.stop_loss, color: '#ff453a' },
          { label: 'Target 1', value: ai.target1, color: '#30d158' },
          { label: 'Target 2', value: ai.target2, color: '#30d158' },
        ].map(({ label, value, color }) => (
          <div key={label} className="glass rounded-xl p-3 text-center">
            <p className="text-[10px] text-jarvis-muted uppercase tracking-wider mb-1">{label}</p>
            <p className="text-sm font-mono font-bold" style={{ color }}>₹{value?.toLocaleString('en-IN')}</p>
          </div>
        ))}
      </div>

      {/* Paper Trade button — only when signal is BUY or SELL */}
      {ai.signal !== 'HOLD' && (
        <button
          onClick={() => openQuickTrade({
            symbol: symbol?.replace('.NS', '').replace('.BO', '') ?? '',
            side: ai.signal === 'BUY' ? 'BUY' : 'SELL',
            entry: ai.entry_price,
            stop_loss: ai.stop_loss,
            target1: ai.target1,
            signal: ai.signal,
            confidence: ai.confidence,
            source: 'ai_analysis',
          })}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-xs font-mono font-bold transition-all border"
          style={{
            background: ai.signal === 'BUY' ? 'rgba(38,166,154,0.15)' : 'rgba(239,83,80,0.15)',
            color: ai.signal === 'BUY' ? '#26a69a' : '#ef5350',
            borderColor: ai.signal === 'BUY' ? 'rgba(38,166,154,0.3)' : 'rgba(239,83,80,0.3)',
          }}
        >
          <ShoppingCart size={13} />
          Paper Trade this signal — {ai.signal} @ ₹{ai.entry_price?.toLocaleString('en-IN')}
        </button>
      )}

      {/* XGBoost Forecast Section */}
      <div className="border-t border-jarvis-border pt-5">
        <div className="flex items-center justify-between mb-3">
          <p className="text-[10px] text-jarvis-accent uppercase tracking-wider font-semibold">🔮 XGBoost Forecast</p>
          <div className="flex items-center gap-2">
            <select
              value={forecastHorizon}
              onChange={e => {
                const h = Number(e.target.value) as 15 | 30
                setForecastHorizon(h)
                onRunForecast(h)
              }}
              className="bg-white/5 border border-jarvis-border rounded px-2 py-0.5 text-[10px] font-mono text-jarvis-accent outline-none focus:border-jarvis-accent/50 cursor-pointer"
            >
              <option value={15} className="bg-jarvis-bg">15 min</option>
              <option value={30} className="bg-jarvis-bg">30 min</option>
            </select>
            <button onClick={() => onRunForecast(forecastHorizon)} className="text-jarvis-muted hover:text-jarvis-accent transition-colors"><RefreshCw size={13} /></button>
          </div>
        </div>
        {forecastLoading ? (
          <div className="flex items-center gap-3 py-4 text-jarvis-muted">
            <RefreshCw size={14} className="animate-spin text-jarvis-accent" />
            <span className="text-xs">Training XGBoost on 5-day history...</span>
          </div>
        ) : !forecast ? (
          <div className="flex items-center gap-4 py-3">
            <p className="text-xs text-jarvis-muted">Run ML forecast for {forecastHorizon}-min price direction</p>
            <button onClick={() => onRunForecast(forecastHorizon)} className="px-4 py-1.5 text-xs font-mono rounded bg-jarvis-accent/20 text-jarvis-accent border border-jarvis-accent/30 hover:bg-jarvis-accent/30 transition-all shrink-0">
              🚀 Run Forecast
            </button>
          </div>
        ) : forecast.error ? (
          <p className="text-xs text-jarvis-neon-red py-2">{forecast.error} <button onClick={() => onRunForecast(forecastHorizon)} className="ml-2 underline text-jarvis-accent">Retry</button></p>
        ) : (() => {
          const fc = forecast.forecast
          const ctx = forecast.context
          const dirColor = fc.direction === 'UP' ? '#30d158' : fc.direction === 'DOWN' ? '#ff453a' : '#ff9f0a'
          const DirIcon = fc.direction === 'UP' ? TrendingUp : fc.direction === 'DOWN' ? TrendingDown : Minus
          return (
            <div className="space-y-3">
              {/* Direction + Probabilities */}
              <div className={`glass rounded-xl p-4 border ${ fc.direction === 'UP' ? 'border-jarvis-neon-green/30' : fc.direction === 'DOWN' ? 'border-jarvis-neon-red/30' : 'border-yellow-500/30' }`}>
                <div className="flex items-center gap-4 flex-wrap">
                  <div className="flex items-center gap-2">
                    <DirIcon size={22} style={{ color: dirColor }} />
                    <span className="text-2xl font-black font-mono" style={{ color: dirColor }}>{fc.direction}</span>
                  </div>
                  <div className="flex flex-col"><span className="text-[10px] text-jarvis-muted">Confidence</span><span className="text-base font-mono font-bold" style={{ color: dirColor }}>{fc.confidence}%</span></div>
                  <div className="flex flex-col"><span className="text-[10px] text-jarvis-muted">Horizon</span><span className="text-xs font-mono text-jarvis-text">{fc.horizon}</span></div>
                  <div className="flex flex-col"><span className="text-[10px] text-jarvis-muted">Model</span><span className="text-xs font-mono text-jarvis-accent">{fc.model}</span></div>
                  <div className="flex gap-3 ml-auto">
                    {([['UP', fc.prob_up, '#30d158'], ['DOWN', fc.prob_down, '#ff453a'], ['FLAT', fc.prob_flat, '#ff9f0a']] as [string, number, string][]).map(([label, val, color]) => (
                      <div key={label} className="flex flex-col items-center gap-1">
                        <span className="text-[10px] text-jarvis-muted">{label}</span>
                        <div className="w-12 h-1.5 bg-white/5 rounded-full overflow-hidden"><div className="h-full rounded-full" style={{ width: `${val}%`, backgroundColor: color }} /></div>
                        <span className="text-[10px] font-mono" style={{ color }}>{val.toFixed(1)}%</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="w-full h-1.5 bg-white/5 rounded-full overflow-hidden mt-3">
                  <div className="h-full rounded-full" style={{ width: `${fc.confidence}%`, backgroundColor: dirColor }} />
                </div>
              </div>
              {/* Forecast Price Levels */}
              <div className="grid grid-cols-3 gap-3">
                {([['Current', `₹${fc.current_price.toLocaleString('en-IN')}`, '#94a3b8'], ['Est. Target', `₹${fc.estimated_target.toLocaleString('en-IN')}`, dirColor], ['Est. Low', `₹${fc.estimated_low.toLocaleString('en-IN')}`, '#ff453a']] as [string, string, string][]).map(([label, value, color]) => (
                  <div key={label} className="glass rounded-xl p-3 text-center">
                    <p className="text-[10px] text-jarvis-muted uppercase tracking-wider mb-1">{label}</p>
                    <p className="text-sm font-mono font-bold" style={{ color }}>{value}</p>
                  </div>
                ))}
              </div>
              {/* Context Grid */}
              <div className="grid grid-cols-4 gap-2">
                {([['Supertrend', ctx.supertrend], ['Ichimoku', ctx.ichimoku_bias], ['Nearest Res.', ctx.nearest_resistance ? `₹${ctx.nearest_resistance}` : 'N/A'], ['Nearest Sup.', ctx.nearest_support ? `₹${ctx.nearest_support}` : 'N/A']] as [string, string | undefined][]).map(([label, value]) => (
                  <div key={label} className="text-center">
                    <p className="text-[9px] text-jarvis-muted uppercase tracking-wider">{label}</p>
                    <p className="text-xs font-mono text-jarvis-text capitalize">{value ?? 'N/A'}</p>
                  </div>
                ))}
              </div>
              {/* SMC */}
              {(forecast.bos_choch.length > 0 || forecast.order_blocks.length > 0 || forecast.fvg.length > 0) && (
                <div className="space-y-1.5">
                  {[...forecast.bos_choch, ...forecast.order_blocks.map(o => ({ ...o, type: 'OB' })), ...forecast.fvg.map(f => ({ ...f, type: 'FVG' }))].map((e, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <span className={`text-[10px] px-2 py-0.5 rounded font-mono font-bold shrink-0 ${ (e as {direction?:string}).direction === 'bullish' || (e as {type:string}).type === 'bullish' ? 'bg-jarvis-neon-green/10 text-jarvis-neon-green' : 'bg-jarvis-neon-red/10 text-jarvis-neon-red' }`}>{(e as {type:string}).type}</span>
                      <span className="text-[11px] text-jarvis-text">{(e as {desc:string}).desc}</span>
                    </div>
                  ))}
                </div>
              )}
              <p className="text-[10px] text-jarvis-muted/50">Trained on {forecast.candles_used} candles · Not financial advice</p>
            </div>
          )
        })()}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="glass rounded-xl p-3 text-center">
          <p className="text-[10px] text-jarvis-muted uppercase tracking-wider mb-1">Risk / Reward</p>
          <p className="text-sm font-mono font-bold text-jarvis-accent">1 : {ai.risk_reward}</p>
        </div>
        <div className="glass rounded-xl p-3 text-center">
          <p className="text-[10px] text-jarvis-muted uppercase tracking-wider mb-1">Trend</p>
          <p className="text-sm font-mono font-bold text-jarvis-text capitalize">{ta.trend.replace(/_/g, ' ')}</p>
        </div>
      </div>

      {/* Reasoning */}
      <div className="glass rounded-xl p-4">
        <p className="text-[10px] text-jarvis-accent uppercase tracking-wider mb-2 font-semibold">AI Reasoning</p>
        <p className="text-xs text-jarvis-muted leading-relaxed">{ai.reasoning}</p>
      </div>

      {/* Indicator Signals */}
      {ta.signals.length > 0 && (
        <div className="glass rounded-xl p-4">
          <p className="text-[10px] text-jarvis-accent uppercase tracking-wider mb-3 font-semibold">Indicator Signals</p>
          <div className="space-y-2">
            {ta.signals.map((s, i) => (
              <div key={i} className="flex items-center gap-3">
                <span className={`text-[10px] px-2 py-0.5 rounded font-mono font-bold shrink-0 ${
                  s.signal === 'buy' ? 'bg-jarvis-neon-green/10 text-jarvis-neon-green' :
                  s.signal === 'sell' ? 'bg-jarvis-neon-red/10 text-jarvis-neon-red' :
                  s.signal === 'confirm' ? 'bg-jarvis-accent/10 text-jarvis-accent' :
                  'bg-white/5 text-jarvis-muted'
                }`}>{s.signal.toUpperCase()}</span>
                <span className="text-[10px] text-jarvis-muted shrink-0 w-24">{s.indicator}</span>
                <span className="text-[11px] text-jarvis-text">{s.reason}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Patterns */}
      {(ta.candlestick_patterns.length > 0 || ta.chart_patterns.length > 0) && (
        <div className="glass rounded-xl p-4">
          <p className="text-[10px] text-jarvis-accent uppercase tracking-wider mb-3 font-semibold">Patterns Detected</p>
          <div className="space-y-2">
            {[...ta.candlestick_patterns, ...ta.chart_patterns].map((p, i) => (
              <div key={i} className="flex items-center gap-3">
                <span className={`text-[10px] px-2 py-0.5 rounded font-mono shrink-0 ${
                  p.type === 'bullish' ? 'bg-jarvis-neon-green/10 text-jarvis-neon-green' :
                  p.type === 'bearish' ? 'bg-jarvis-neon-red/10 text-jarvis-neon-red' :
                  'bg-white/5 text-jarvis-muted'
                }`}>{p.type.toUpperCase()}</span>
                <span className="text-[11px] text-jarvis-text font-medium shrink-0">{p.pattern}</span>
                <span className="text-[10px] text-jarvis-muted">{p.desc}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Support / Resistance */}
      <div className="glass rounded-xl p-4">
        <p className="text-[10px] text-jarvis-accent uppercase tracking-wider mb-3 font-semibold">Support & Resistance</p>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <p className="text-[10px] text-jarvis-muted mb-1">Resistance</p>
            {ta.support_resistance.resistance?.map((r, i) => (
              <p key={i} className="text-xs font-mono text-jarvis-neon-red">₹{r.toLocaleString('en-IN')}</p>
            ))}
          </div>
          <div className="text-center">
            <p className="text-[10px] text-jarvis-muted mb-1">Pivot</p>
            <p className="text-xs font-mono text-jarvis-accent">₹{ta.support_resistance.pivot?.toLocaleString('en-IN')}</p>
          </div>
          <div>
            <p className="text-[10px] text-jarvis-muted mb-1">Support</p>
            {ta.support_resistance.support?.map((s, i) => (
              <p key={i} className="text-xs font-mono text-jarvis-neon-green">₹{s.toLocaleString('en-IN')}</p>
            ))}
          </div>
        </div>
      </div>

      {/* Risks */}
      <div className="glass rounded-xl p-4">
        <p className="text-[10px] text-jarvis-accent uppercase tracking-wider mb-2 font-semibold">Key Risks</p>
        <ul className="space-y-1">
          {ai.risks.map((r, i) => (
            <li key={i} className="text-xs text-jarvis-muted flex items-start gap-2">
              <span className="text-jarvis-neon-red mt-0.5">⚠</span>{r}
            </li>
          ))}
        </ul>
        {ai.market_context && (
          <p className="text-[11px] text-jarvis-muted mt-3 pt-3 border-t border-jarvis-border">{ai.market_context}</p>
        )}
      </div>

      {/* Key Indicators Grid */}
      <div className="glass rounded-xl p-4">
        <p className="text-[10px] text-jarvis-accent uppercase tracking-wider mb-3 font-semibold">Key Indicators</p>
        <div className="grid grid-cols-3 md:grid-cols-5 gap-3">
          {[
            ['RSI', ta.indicators.rsi],
            ['MACD', ta.indicators.macd],
            ['EMA9', ta.indicators.ema9],
            ['EMA21', ta.indicators.ema21],
            ['EMA50', ta.indicators.ema50],
            ['BB Upper', ta.indicators.bb_upper],
            ['BB Lower', ta.indicators.bb_lower],
            ['ATR', ta.indicators.atr],
            ['Stoch K', ta.indicators.stochastic_k],
            ['VWAP', ta.indicators.vwap],
          ].map(([label, value]) => value != null && (
            <div key={label as string} className="text-center">
              <p className="text-[9px] text-jarvis-muted uppercase tracking-wider">{label}</p>
              <p className="text-xs font-mono text-jarvis-text">{typeof value === 'number' ? value.toFixed(2) : value}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Market Chat Panel ────────────────────────────────────────
function MarketChat({ selectedStock }: { selectedStock: string | null }) {
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')
  const { messages, sendMessage, status } = useJarvisStore()
  const bottomRef = useRef<HTMLDivElement>(null)

  // Only show messages from this chat session (all messages are shared store)
  useEffect(() => {
    if (open) bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, open])

  const handleSend = useCallback(() => {
    if (!input.trim()) return
    sendMessage(input.trim())
    setInput('')
  }, [input, sendMessage])

  const chatMessages = messages.slice(-40) // last 40 messages

  return (
    <>
      {/* Floating toggle button */}
      <button
        onClick={() => setOpen(o => !o)}
        className={`fixed bottom-6 right-6 z-50 flex items-center gap-2 px-4 py-2.5 rounded-full shadow-lg transition-all ${
          open
            ? 'bg-jarvis-accent text-jarvis-bg'
            : 'bg-jarvis-accent/20 text-jarvis-accent border border-jarvis-accent/40 hover:bg-jarvis-accent/30'
        }`}
      >
        {open ? <X size={15} /> : <MessageSquare size={15} />}
        <span className="text-xs font-mono font-bold">{open ? 'Close' : 'AI Chat'}</span>
        {selectedStock && !open && (
          <span className="text-[10px] font-mono bg-jarvis-accent/20 px-1.5 py-0.5 rounded-full">{selectedStock}</span>
        )}
      </button>

      {/* Chat panel */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.97 }}
            transition={{ duration: 0.18 }}
            className="fixed bottom-20 right-6 z-50 w-[380px] h-[520px] glass rounded-2xl border border-jarvis-border flex flex-col shadow-2xl overflow-hidden"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-jarvis-border shrink-0 bg-white/[0.02]">
              <div className="flex items-center gap-2">
                <MessageSquare size={13} className="text-jarvis-accent" />
                <span className="text-xs font-mono font-bold text-jarvis-accent">Market AI</span>
                {selectedStock && (
                  <span className="text-[10px] font-mono bg-jarvis-accent/10 text-jarvis-accent px-2 py-0.5 rounded-full border border-jarvis-accent/20">
                    📈 {selectedStock}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                {status === 'thinking' && (
                  <span className="flex items-center gap-1 text-[10px] text-jarvis-muted">
                    <RefreshCw size={9} className="animate-spin" /> thinking...
                  </span>
                )}
                <button onClick={() => setOpen(false)} className="text-jarvis-muted hover:text-jarvis-text transition-colors">
                  <X size={13} />
                </button>
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-3 space-y-2">
              {chatMessages.length === 0 && (
                <div className="flex flex-col items-center justify-center h-full gap-3 text-jarvis-muted">
                  <MessageSquare size={28} className="text-jarvis-border" />
                  <p className="text-xs text-center">
                    {selectedStock
                      ? `Ask anything about ${selectedStock} — signal, target, RSI, should I buy?`
                      : 'Select a stock or ask any market question'}
                  </p>
                  {selectedStock && (
                    <div className="flex flex-col gap-1.5 w-full px-2">
                      {[
                        `Should I buy ${selectedStock} today?`,
                        `What is the target for ${selectedStock}?`,
                        `What's the RSI for ${selectedStock}?`,
                      ].map(q => (
                        <button key={q} onClick={() => { sendMessage(q) }}
                          className="text-[10px] text-left px-3 py-1.5 rounded-lg bg-white/5 border border-jarvis-border hover:border-jarvis-accent/30 hover:bg-jarvis-accent/5 text-jarvis-muted hover:text-jarvis-text transition-all">
                          {q}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
              {chatMessages.map((msg) => (
                <div key={msg.id} className={`flex ${ msg.role === 'user' ? 'justify-end' : 'justify-start' }`}>
                  <div className={`max-w-[88%] rounded-xl px-3 py-2 text-xs ${
                    msg.role === 'user'
                      ? 'bg-jarvis-accent/15 border border-jarvis-accent/20 text-jarvis-text'
                      : 'bg-white/5 border border-jarvis-border text-jarvis-text'
                  }`}>
                    <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                    <p className="text-[9px] text-jarvis-muted mt-1 opacity-60">
                      {new Date(msg.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false })}
                    </p>
                  </div>
                </div>
              ))}
              {status === 'thinking' && (
                <div className="flex gap-1 px-2 py-1">
                  {[0,1,2].map(i => (
                    <motion.div key={i} className="w-1.5 h-1.5 bg-jarvis-accent rounded-full"
                      animate={{ y: [0, -4, 0] }}
                      transition={{ duration: 0.5, repeat: Infinity, delay: i * 0.12 }} />
                  ))}
                </div>
              )}
              <div ref={bottomRef} />
            </div>

            {/* Input */}
            <div className="p-3 border-t border-jarvis-border shrink-0">
              <div className="flex items-center gap-2 bg-white/5 rounded-lg px-3 py-2 border border-jarvis-border focus-within:border-jarvis-accent/40 transition-colors">
                <input
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSend()}
                  placeholder={selectedStock ? `Ask about ${selectedStock}...` : 'Ask a market question...'}
                  className="flex-1 bg-transparent text-xs text-jarvis-text placeholder-jarvis-muted outline-none"
                />
                <button onClick={handleSend} disabled={!input.trim() || status === 'thinking'}
                  className="p-1.5 rounded bg-jarvis-accent/20 text-jarvis-accent hover:bg-jarvis-accent/30 disabled:opacity-30 transition-all">
                  <Send size={12} />
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}

// ── Live Clock ────────────────────────────────────────────────
function LiveClock() {
  const [time, setTime] = useState('')
  useEffect(() => {
    const tick = () => setTime(new Date().toLocaleTimeString('en-IN', {
      timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
    }))
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [])
  return <span className="text-xs font-mono text-jarvis-muted">🕐 IST {time}</span>
}

// ── Stock List Item ───────────────────────────────────────────
function StockItem({ stock, selected, onClick }: { stock: StockQuote; selected: boolean; onClick: () => void }) {
  const up = stock.change_pct >= 0
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      onClick={onClick}
      className={`flex items-center justify-between px-3 py-2.5 cursor-pointer rounded-lg transition-all border ${
        selected
          ? 'bg-jarvis-accent/10 border-jarvis-accent/30'
          : 'border-transparent hover:bg-white/[0.03] hover:border-jarvis-border'
      }`}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-mono font-bold text-jarvis-accent">{stock.symbol}</span>
          {selected && <ChevronRight size={10} className="text-jarvis-accent" />}
        </div>
        <p className="text-[10px] text-jarvis-muted truncate mt-0.5">{stock.name}</p>
      </div>
      <div className="text-right shrink-0 ml-2">
        <p className="text-xs font-mono text-jarvis-text">₹{stock.price.toLocaleString('en-IN')}</p>
        <span className={`text-[10px] font-mono ${up ? 'text-jarvis-neon-green' : 'text-jarvis-neon-red'}`}>
          {up ? '+' : ''}{stock.change_pct.toFixed(2)}%
        </span>
      </div>
    </motion.div>
  )
}

// ── Main Page ─────────────────────────────────────────────────
export function StocksPage() {
  const {
    stocks, indices, stocksLoading, fetchStocks,
    selectedStock, setSelectedStock, stockChart, chartLoading, fetchChart,
    fundamentals, fundamentalsLoading, fetchFundamentals,
    financials, financialsLoading, fetchFinancials,
    shareholding, shareholdingLoading, fetchShareholding,
    peers, peersLoading, fetchPeers,
    screenerResults, screenerLoading, runScreener,
    analysis, analysisLoading, fetchAnalysis,
    forecast, forecastLoading, fetchForecast,
    budgetAdvice, budgetLoading, fetchRecommendations,
    analysisHistory,
    positionMarker, setPositionMarker,
  } = useJarvisStore()

  const [search, setSearch] = useState('')
  const [sector, setSector] = useState('All')
  const [universe, setUniverse] = useState('nifty50')
  const loadedUniverses = useRef<Set<string>>(new Set())
  const [chartTf, setChartTf] = useState('5m')
  const [chartMode, setChartMode] = useState<'line' | 'candle'>('line')
  const [isLive, setIsLive] = useState(false)
  const [activeTab, setActiveTab] = useState<'overview' | 'analysis' | 'financials' | 'shareholding' | 'peers' | 'screener'>('overview')
  const [overlayData, setOverlayData] = useState<OverlayData | null>(null)
  const [activeOverlays, setActiveOverlays] = useState<Set<string>>(new Set())
  const [overlayLoading, setOverlayLoading] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const chartRefreshRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Standard timeframe → Yahoo Finance valid intervals only
  const TF_MAP: Record<string, { interval: string; range: string; label: string }> = {
    '1m':  { interval: '1m',  range: '1d',  label: '1m'  },
    '2m':  { interval: '2m',  range: '1d',  label: '2m'  },
    '5m':  { interval: '5m',  range: '1d',  label: '5m'  },
    '15m': { interval: '15m', range: '5d',  label: '15m' },
    '30m': { interval: '30m', range: '5d',  label: '30m' },
    '1H':  { interval: '60m', range: '1mo', label: '1H'  },
    '1D':  { interval: '1d',  range: '1y',  label: '1D'  },
    '1W':  { interval: '1wk', range: '5y',  label: '1W'  },
    '1M':  { interval: '1mo', range: 'max', label: '1M'  },
  }

  // WebSocket live stream
  useEffect(() => {
    function connect() {
      const ws = new WebSocket(`${WS_URL}/api/ws/stocks`)
      wsRef.current = ws
      ws.onopen = () => setIsLive(true)
      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data)
          useJarvisStore.setState((s) => {
            // Patch last candle of chart with live price for selected stock
            let stockChart = s.stockChart
            if (stockChart && s.selectedStock) {
              const liveStock = (data.stocks || []).find(
                (st: { symbol: string; price: number; day_high: number; day_low: number }) =>
                  st.symbol === s.selectedStock
              )
              if (liveStock && stockChart.candles.length > 0) {
                const candles = [...stockChart.candles]
                const last = { ...candles[candles.length - 1] }
                last.c = liveStock.price
                last.h = Math.max(last.h, liveStock.price)
                last.l = Math.min(last.l, liveStock.price)
                candles[candles.length - 1] = last
                stockChart = { ...stockChart, candles }
              }
            }
            // Only update stock list if we're on nifty50 universe (WS only streams nifty50)
            // For larger universes, merge by symbol instead of replacing
            const wsStocks: typeof s.stocks = data.stocks || []
            let updatedStocks = s.stocks
            if (wsStocks.length > 0) {
              if (s.stocks.length <= 55) {
                // nifty50 view — safe to replace
                updatedStocks = wsStocks
              } else {
                // larger universe — patch only the stocks that exist in WS update
                const wsMap = new Map(wsStocks.map(st => [st.symbol, st]))
                updatedStocks = s.stocks.map(st => wsMap.get(st.symbol) ?? st)
              }
            }
            return { stocks: updatedStocks, indices: data.indices || s.indices, stocksLoading: false, stockChart }
          })
        } catch {}
      }
      ws.onclose = () => { setIsLive(false); reconnectRef.current = setTimeout(connect, 5000) }
      ws.onerror = () => ws.close()
    }
    connect()
    return () => { wsRef.current?.close(); if (reconnectRef.current) clearTimeout(reconnectRef.current) }
  }, [])

  useEffect(() => {
    if (!loadedUniverses.current.has(universe)) {
      loadedUniverses.current.add(universe)
      fetchStocks(universe)
    }
  }, [fetchStocks, universe])

  // Intraday timeframes that benefit from periodic chart refresh
  const INTRADAY_TFS = new Set(['1m', '2m', '5m', '15m', '30m'])

  useEffect(() => {
    if (chartRefreshRef.current) clearInterval(chartRefreshRef.current)
    if (selectedStock) {
      const tf = TF_MAP[chartTf] || TF_MAP['5m']
      fetchChart(selectedStock, tf.interval, tf.range)
      fetchFundamentals(selectedStock)
      // Auto-refresh chart: 15s for 1m/2m, 30s for 15m/30m intraday
      if (INTRADAY_TFS.has(chartTf)) {
        const refreshMs = (chartTf === '1m' || chartTf === '2m') ? 15000 : 30000
        chartRefreshRef.current = setInterval(() => {
          fetchChart(selectedStock, tf.interval, tf.range)
        }, refreshMs)
      }
    }
    return () => { if (chartRefreshRef.current) clearInterval(chartRefreshRef.current) }
  }, [selectedStock, chartTf, fetchChart, fetchFundamentals])

  const handleTabChange = (tab: typeof activeTab) => {
    setActiveTab(tab)
    if (!selectedStock) return
    if (tab === 'analysis') {
      if (!analysis) fetchAnalysis(selectedStock)
      if (!forecast) fetchForecast(selectedStock, 30)
    }
    if (tab === 'financials' && !financials) fetchFinancials(selectedStock)
    if (tab === 'shareholding' && !shareholding) fetchShareholding(selectedStock)
    if (tab === 'peers' && !peers.length) fetchPeers(selectedStock)
  }

  // Reset tab when stock changes — but keep marker if it matches the new symbol
  useEffect(() => {
    setActiveTab('overview')
    setOverlayData(null)
    setActiveOverlays(new Set())
    // Clear marker if user navigated to a different stock manually
    if (positionMarker && selectedStock && !selectedStock.startsWith(positionMarker.symbol.replace('.NS','').replace('.BO','')))
      setPositionMarker(null)
  }, [selectedStock])

  const toggleOverlay = (key: string) => {
    setActiveOverlays(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else {
        next.add(key)
        if (!overlayData && selectedStock) {
          const tf = TF_MAP[chartTf] || TF_MAP['5m']
          setOverlayLoading(true)
          fetchOverlays(selectedStock, tf.interval, tf.range)
            .then(d => { setOverlayData(d); setOverlayLoading(false) })
            .catch(() => setOverlayLoading(false))
        }
      }
      return next
    })
  }

  const sectors = ['All', ...Array.from(new Set(stocks.map(s => s.sector))).sort()]

  const filtered = stocks.filter(s => {
    const matchSearch = s.symbol.includes(search.toUpperCase()) || s.name.toLowerCase().includes(search.toLowerCase())
    const matchSector = sector === 'All' || s.sector === sector
    return matchSearch && matchSector
  })

  const selectedStockData = stocks.find(s => s.symbol === selectedStock)

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <MarketChat selectedStock={selectedStock} />

      {/* ── Top Bar ── */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-jarvis-border shrink-0">
        <div className="flex items-center gap-3">
          <BarChart2 size={15} className="text-jarvis-accent" />
          <span className="text-sm font-bold text-jarvis-text uppercase tracking-wider">Indian Stock Market</span>
          <span className={`flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full font-mono ${
            isLive ? 'bg-jarvis-neon-green/10 text-jarvis-neon-green' : 'bg-jarvis-muted/10 text-jarvis-muted'
          }`}>
            {isLive ? <Wifi size={9} /> : <WifiOff size={9} />}
            {isLive ? 'LIVE' : 'Connecting...'}
          </span>
        </div>
        <LiveClock />
      </div>

      {/* ── Indices Bar ── */}
      <div className="grid grid-cols-3 gap-3 px-4 py-3 border-b border-jarvis-border shrink-0">
        {indices.slice(0, 3).map((idx) => (
          <div key={idx.symbol} className="glass rounded-xl px-4 py-3 flex items-center justify-between">
            <div>
              <p className="text-[10px] text-jarvis-muted uppercase tracking-wider">{idx.name}</p>
              <p className="text-lg font-mono text-jarvis-text font-bold mt-0.5">{idx.price.toLocaleString('en-IN')}</p>
              <p className={`text-xs font-mono mt-0.5 ${idx.change_pct >= 0 ? 'text-jarvis-neon-green' : 'text-jarvis-neon-red'}`}>
                {idx.change_pct >= 0 ? '+' : ''}{idx.change.toFixed(2)} ({idx.change_pct >= 0 ? '+' : ''}{idx.change_pct.toFixed(2)}%)
              </p>
            </div>
            <Sparkline data={idx.sparkline} positive={idx.change_pct >= 0} />
          </div>
        ))}
      </div>

      {/* ── Main Body: Left List + Right Chart ── */}
      <div className="flex flex-1 overflow-hidden">

        {/* ── Left: Stock List ── */}
        <div className="w-72 shrink-0 flex flex-col border-r border-jarvis-border overflow-hidden">

          {/* Search */}
          <div className="p-3 border-b border-jarvis-border shrink-0">
            <div className="flex items-center gap-2 bg-white/5 border border-jarvis-border rounded-lg px-3 py-2">
              <Search size={13} className="text-jarvis-muted shrink-0" />
              <input
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search stocks..."
                className="bg-transparent text-xs text-jarvis-text placeholder-jarvis-muted outline-none flex-1"
              />
              {search && (
                <button onClick={() => setSearch('')} className="text-jarvis-muted hover:text-jarvis-text">
                  <RefreshCw size={10} />
                </button>
              )}
            </div>
          </div>

          {/* Universe Selector */}
          <div className="px-3 py-2 border-b border-jarvis-border shrink-0 flex gap-1 flex-wrap">
            {([
              ['nifty50',  'N50'],
              ['nifty100', 'N100'],
              ['midcap',   'Mid'],
              ['smallcap', 'Small'],
              ['all',      'All'],
            ] as const).map(([key, label]) => (
              <button key={key} onClick={() => { setUniverse(key); setSector('All') }}
                className={`text-[10px] px-2 py-0.5 rounded font-mono transition-all ${
                  universe === key
                    ? 'bg-jarvis-accent text-jarvis-bg font-bold'
                    : 'text-jarvis-muted hover:text-jarvis-text bg-white/5'
                }`}>
                {label}
              </button>
            ))}
            {stocksLoading && <RefreshCw size={10} className="animate-spin text-jarvis-accent ml-1 self-center" />}
          </div>

          {/* Sector Filter */}
          <div className="px-3 py-2 border-b border-jarvis-border shrink-0 flex gap-1 flex-wrap">
            {sectors.map(s => (
              <button key={s} onClick={() => setSector(s)}
                className={`text-[10px] px-2 py-0.5 rounded transition-all ${
                  sector === s ? 'bg-jarvis-accent/20 text-jarvis-accent' : 'text-jarvis-muted hover:text-jarvis-text bg-white/5'
                }`}>
                {s}
              </button>
            ))}
          </div>

          {/* Count + Refresh */}
          <div className="flex items-center justify-between px-3 py-1.5 shrink-0">
            <span className="text-[10px] text-jarvis-muted">
              {filtered.length} / {stocks.length} stocks
              {universe !== 'nifty50' && (
                <span className="ml-1 text-jarvis-accent font-mono">
                  · {universe === 'nifty100' ? 'Nifty 100' : universe === 'midcap' ? 'Midcap 150' : universe === 'smallcap' ? 'Smallcap 100' : 'All'}
                </span>
              )}
            </span>
            <button onClick={() => fetchStocks(universe)} disabled={stocksLoading}
              className="text-jarvis-muted hover:text-jarvis-accent transition-colors disabled:opacity-40">
              <RefreshCw size={11} className={stocksLoading ? 'animate-spin' : ''} />
            </button>
          </div>

          {/* Scrollable Stock List */}
          <div className="flex-1 overflow-y-auto px-2 pb-2 space-y-0.5">
            {filtered.map(stock => (
              <StockItem
                key={stock.symbol}
                stock={stock}
                selected={selectedStock === stock.symbol}
                onClick={() => setSelectedStock(selectedStock === stock.symbol ? null : stock.symbol)}
              />
            ))}
            {filtered.length === 0 && !stocksLoading && (
              <p className="text-center text-jarvis-muted text-xs py-8">No stocks found</p>
            )}
          </div>
        </div>

        {/* ── Right: Chart + Fundamentals ── */}
        <div className="flex-1 overflow-y-auto">
          <AnimatePresence mode="wait">
            {selectedStock && selectedStockData ? (
              <motion.div
                key={selectedStock}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                className="p-5"
              >
                {/* Stock Header */}
                <div className="mb-5">
                  <div className="flex items-center gap-3 mb-1">
                    <h2 className="text-xl font-bold font-mono text-jarvis-text">{selectedStockData.name}</h2>
                    <span className="text-sm text-jarvis-muted font-mono bg-white/5 px-2 py-0.5 rounded">{selectedStockData.symbol}</span>
                    <span className="text-[10px] text-jarvis-muted bg-white/5 px-2 py-0.5 rounded">{selectedStockData.sector}</span>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-3xl font-mono font-bold text-jarvis-text">
                      ₹{selectedStockData.price.toLocaleString('en-IN')}
                    </span>
                    <span className={`text-base font-mono px-3 py-1 rounded-lg ${
                      selectedStockData.change_pct >= 0
                        ? 'bg-jarvis-neon-green/10 text-jarvis-neon-green'
                        : 'bg-jarvis-neon-red/10 text-jarvis-neon-red'
                    }`}>
                      {selectedStockData.change_pct >= 0 ? '+' : ''}{selectedStockData.change.toFixed(2)} ({selectedStockData.change_pct >= 0 ? '+' : ''}{selectedStockData.change_pct.toFixed(2)}%)
                    </span>
                  </div>
                  <div className="flex items-center gap-4 mt-2 text-xs text-jarvis-muted font-mono">
                    <span>H: ₹{selectedStockData.day_high.toLocaleString('en-IN')}</span>
                    <span>L: ₹{selectedStockData.day_low.toLocaleString('en-IN')}</span>
                    <span>Prev: ₹{selectedStockData.prev_close.toLocaleString('en-IN')}</span>
                    <span>Vol: {(selectedStockData.volume / 1000).toFixed(0)}K</span>
                    <span className={`px-2 py-0.5 rounded text-[10px] ${
                      selectedStockData.market_state === 'REGULAR'
                        ? 'bg-jarvis-neon-green/10 text-jarvis-neon-green'
                        : 'bg-jarvis-muted/10 text-jarvis-muted'
                    }`}>
                      {selectedStockData.market_state}
                    </span>
                  </div>
                </div>

                {/* Tabs */}
                <div className="flex gap-1 border-b border-jarvis-border mb-5">
                  {([
                    ['overview', '📈 Overview'],
                    ['analysis', '🤖 AI Analysis'],
                    ['financials', '📊 Financials'],
                    ['shareholding', '🏦 Shareholding'],
                    ['peers', '👥 Peers'],
                    ['screener', '🔍 Screener'],
                  ] as const).map(([tab, label]) => (
                    <button key={tab} onClick={() => handleTabChange(tab)}
                      className={`text-xs px-4 py-2 font-mono transition-all border-b-2 -mb-px ${
                        activeTab === tab
                          ? 'border-jarvis-accent text-jarvis-accent'
                          : 'border-transparent text-jarvis-muted hover:text-jarvis-text'
                      }`}>
                      {label}
                    </button>
                  ))}
                </div>

                {/* Tab Content */}
                {activeTab === 'overview' && (
                  <>
                    {/* Timeframe + Mode Controls */}
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex gap-1 flex-wrap">
                        {Object.entries(TF_MAP).map(([key, { label }]) => (
                          <button key={key} onClick={() => setChartTf(key)}
                            className={`text-xs px-2.5 py-1 rounded font-mono transition-all ${
                              chartTf === key
                                ? 'bg-jarvis-accent/20 text-jarvis-accent border border-jarvis-accent/30'
                                : 'text-jarvis-muted hover:text-jarvis-text bg-white/5 border border-transparent'
                            }`}>
                            {label}
                          </button>
                        ))}
                      </div>
                      <div className="flex gap-1">
                        {(['line', 'candle'] as const).map(m => (
                          <button key={m} onClick={() => setChartMode(m)}
                            className={`text-xs px-3 py-1 rounded font-mono transition-all ${
                              chartMode === m ? 'bg-jarvis-accent/20 text-jarvis-accent border border-jarvis-accent/30' : 'text-jarvis-muted hover:text-jarvis-text bg-white/5'
                            }`}>
                            {m === 'line' ? '📈 Line' : '🕯 Candle'}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Overlay Toggle Buttons */}
                    <div className="flex items-center gap-1 flex-wrap mb-3">
                      <Layers size={11} className="text-jarvis-muted shrink-0" />
                      {[
                        { key: 'ema9',       label: 'EMA9',   color: '#f59e0b' },
                        { key: 'ema21',      label: 'EMA21',  color: '#a78bfa' },
                        { key: 'ema50',      label: 'EMA50',  color: '#06b6d4' },
                        { key: 'ema200',     label: 'EMA200', color: '#f97316' },
                        { key: 'bb',         label: 'BB',     color: '#64748b' },
                        { key: 'supertrend', label: 'ST',     color: '#30d158' },
                        { key: 'sr',         label: 'S/R',    color: '#ff453a' },
                        { key: 'fib',        label: 'Fib',    color: '#fbbf24' },
                      ].map(({ key, label, color }) => (
                        <button key={key} onClick={() => toggleOverlay(key)}
                          className={`text-[10px] px-2 py-0.5 rounded font-mono transition-all border ${
                            activeOverlays.has(key)
                              ? 'text-jarvis-bg font-bold'
                              : 'bg-white/5 text-jarvis-muted hover:text-jarvis-text border-transparent'
                          }`}
                          style={activeOverlays.has(key) ? { backgroundColor: color, borderColor: color } : {}}>
                          {label}
                        </button>
                      ))}
                      {overlayLoading && <RefreshCw size={10} className="animate-spin text-jarvis-accent ml-1" />}
                    </div>
                    {/* Chart */}
                    <div className="glass rounded-2xl p-5 mb-5">
                      {/* Position marker banner */}
                      {positionMarker && positionMarker.symbol.replace('.NS','').replace('.BO','') === selectedStock?.replace('.NS','').replace('.BO','') && (
                        <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "6px 12px", marginBottom: 8, background: (selectedStockData?.price ?? positionMarker.buyPrice) >= positionMarker.buyPrice ? "rgba(0,255,153,0.06)" : "rgba(255,90,122,0.06)", border: "1px solid " + ((selectedStockData?.price ?? positionMarker.buyPrice) >= positionMarker.buyPrice ? "rgba(0,255,153,0.25)" : "rgba(255,90,122,0.25)"), borderRadius: 2 }}><span style={{ fontSize: 9, fontFamily: "Orbitron, sans-serif", color: "#2A5A6A", letterSpacing: "0.18em" }}>OPEN POSITION</span><span style={{ fontSize: 10, fontFamily: "IBM Plex Mono, monospace", color: "#D8FFFF" }}>₹{positionMarker.buyPrice.toFixed(2)}</span><span style={{ fontSize: 10, fontFamily: "IBM Plex Mono, monospace", color: (selectedStockData?.price ?? positionMarker.buyPrice) >= positionMarker.buyPrice ? "#00FF99" : "#FF5A7A", fontWeight: 700 }}>{((selectedStockData?.price ?? positionMarker.buyPrice) - positionMarker.buyPrice) >= 0 ? "+" : ""}{((selectedStockData?.price ?? positionMarker.buyPrice) - positionMarker.buyPrice).toFixed(2)}</span></div>
                      )}
                      {chartLoading ? (
                        <div className="flex items-center justify-center h-[480px] text-jarvis-muted text-sm">
                          <RefreshCw size={16} className="animate-spin mr-2" /> Loading chart...
                        </div>
                      ) : stockChart ? (
                        <PriceChart
                          candles={stockChart.candles}
                          mode={chartMode}
                          tf={chartTf}
                          overlays={overlayData}
                          activeOverlays={activeOverlays}
                          buyMarker={positionMarker && positionMarker.symbol.replace('.NS','').replace('.BO','') === selectedStock?.replace('.NS','').replace('.BO','') ? positionMarker : null}
                        />
                      ) : (
                        <div className="flex items-center justify-center h-[480px] text-jarvis-muted text-sm">No data</div>
                      )}
                    </div>
                    <FundamentalsPanel data={fundamentals} loading={fundamentalsLoading} />
                  </>
                )}

                {activeTab === 'analysis' && (
                  <div className="glass rounded-2xl p-5">
                    <AnalysisPanel
                      data={analysis}
                      loading={analysisLoading}
                      onRun={() => selectedStock && fetchAnalysis(selectedStock)}
                      forecast={forecast}
                      forecastLoading={forecastLoading}
                      onRunForecast={(h) => selectedStock && fetchForecast(selectedStock, h)}
                      history={analysisHistory}
                      symbol={selectedStock}
                    />
                  </div>
                )}

                {activeTab === 'financials' && (
                  <div className="glass rounded-2xl p-5">
                    <FinancialsPanel data={financials} loading={financialsLoading} />
                  </div>
                )}

                {activeTab === 'shareholding' && (
                  <div className="glass rounded-2xl p-5">
                    <ShareholdingPanel data={shareholding} loading={shareholdingLoading} />
                  </div>
                )}

                {activeTab === 'peers' && (
                  <div className="glass rounded-2xl p-5">
                    <PeersPanel data={peers} loading={peersLoading} currentSymbol={selectedStock ?? ''} />
                  </div>
                )}

                {activeTab === 'screener' && (
                  <div className="glass rounded-2xl p-5">
                    <ScreenerPanel results={screenerResults} loading={screenerLoading} onRun={(f) => runScreener({ ...f, universe })} />
                  </div>
                )}
              </motion.div>
            ) : (
              <motion.div
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex flex-col h-full p-5"
              >
                {/* Screener always accessible */}
                <div className="flex gap-1 border-b border-jarvis-border mb-5">
                  <button
                    onClick={() => handleTabChange('screener')}
                    className={`text-xs px-4 py-2 font-mono transition-all border-b-2 -mb-px ${
                      activeTab === 'screener'
                        ? 'border-jarvis-accent text-jarvis-accent'
                        : 'border-transparent text-jarvis-muted hover:text-jarvis-text'
                    }`}>
                    🔍 Screener
                  </button>
                </div>
                {activeTab === 'screener' ? (
                  <div className="glass rounded-2xl p-5">
                    <ScreenerPanel results={screenerResults} loading={screenerLoading} onRun={(f) => runScreener({ ...f, universe })} />
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center flex-1 text-jarvis-muted gap-3">
                    <BarChart2 size={48} className="text-jarvis-border" />
                    <p className="text-sm">Select a stock from the list to view chart &amp; analysis</p>
                    <p className="text-xs text-jarvis-muted/60">Or use the Screener tab to filter {stocks.length} Nifty 50 stocks</p>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}

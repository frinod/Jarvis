import { create } from 'zustand'

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
  tradeProposal?: TradeProposal | null
}

export interface TradeProposal {
  confirmation_id: string
  symbol: string
  trade_type: string
  qty: number
  price: number
  estimated_cost: number
  signal: string
  confidence: number
  trend: string
  stop_loss: number
  target1: number
  target2: number
  risk_reward: number
}

export interface Task {
  id: string
  title: string
  status: 'pending' | 'running' | 'completed' | 'failed'
}

export interface Agent {
  id: string
  name: string
  status: 'active' | 'idle' | 'error'
  task?: string
}

export interface SystemStats {
  cpu: number
  memory: number
  network: number
  uptime: string
}

export interface LLMInfo {
  provider: string
  model: string
  status: 'connected' | 'disconnected' | 'loading'
  tokensUsed: number
  available: string[]
}

export interface StockQuote {
  symbol: string
  name: string
  sector: string
  price: number
  prev_close: number
  change: number
  change_pct: number
  day_high: number
  day_low: number
  volume: number
  market_state: string
}

export interface IndexQuote {
  name: string
  symbol: string
  price: number
  change: number
  change_pct: number
  sparkline: number[]
}

export interface Candle {
  t: number
  o: number
  h: number
  l: number
  c: number
  v: number
}

export interface StockChart {
  symbol: string
  name: string
  candles: Candle[]
}

export interface StockFundamentals {
  symbol: string
  name: string
  sector: string
  industry: string
  website: string
  description: string
  employees: string
  market_cap: string
  pe_ratio: string
  forward_pe: string
  pb_ratio: string
  ps_ratio: string
  peg_ratio: string
  ev: string
  ev_ebitda: string
  ev_revenue: string
  eps: string
  forward_eps: string
  book_value: string
  dividend_yield: string
  dividend_rate: string
  payout_ratio: string
  '52w_high': string
  '52w_low': string
  '50d_avg': string
  '200d_avg': string
  beta: string
  revenue: string
  gross_profit: string
  ebitda: string
  net_income: string
  profit_margin: string
  operating_margin: string
  gross_margin: string
  revenue_growth: string
  earnings_growth: string
  total_cash: string
  total_debt: string
  debt_to_equity: string
  current_ratio: string
  quick_ratio: string
  roe: string
  roa: string
  free_cashflow: string
  operating_cashflow: string
  shares_outstanding: string
  float_shares: string
  short_ratio: string
  error?: string
}

export interface FinancialRow {
  date: string
  revenue?: string
  gross_profit?: string
  operating_income?: string
  net_income?: string
  ebit?: string
  ebitda?: string
  interest_expense?: string
  total_assets?: string
  total_liabilities?: string
  total_equity?: string
  total_debt?: string
  current_assets?: string
  current_liabilities?: string
  working_capital?: string
  cash?: string
  roce?: string
  operating_cf?: string
  investing_cf?: string
  financing_cf?: string
  free_cashflow?: string
  capex?: string
}

export interface Financials {
  symbol: string
  annual_pl: FinancialRow[]
  quarterly_pl: FinancialRow[]
  annual_bs: FinancialRow[]
  quarterly_bs: FinancialRow[]
  annual_cf: FinancialRow[]
  quarterly_cf: FinancialRow[]
  error?: string
}

export interface ShareholdingData {
  symbol: string
  summary: { promoters: string; fii_institutions: string; public: string }
  top_institutions: { name: string; pct_held: number; shares: string }[]
  top_funds: { name: string; pct_held: number; shares: string }[]
  insiders: { name: string; relation: string; shares: string }[]
  error?: string
}

export interface PeerStock {
  symbol: string
  name: string
  price: string
  market_cap: string
  pe_ratio: string
  pb_ratio: string
  roe: string
  roa: string
  profit_margin: string
  revenue_growth: string
  debt_to_equity: string
  dividend_yield: string
  eps: string
}

export interface ScreenerResult {
  symbol: string
  name: string
  sector: string
  price: number
  change_pct: number
  pe_ratio: string
  roe: string
  debt_to_equity: string
  market_cap: string
  profit_margin: string
  eps: string
  dividend_yield: string
  pb_ratio: string
}

// ── New interfaces ────────────────────────────────────────────

export interface MarketMover {
  symbol: string
  name: string
  sector: string
  price: number
  change: number
  change_pct: number
  volume: number
  turnover?: number
}

export interface SectorHeatmapItem {
  sector: string
  avg_change_pct: number
  stock_count: number
  advancing: number
  declining: number
  top_mover: string | null
  top_mover_pct: number
  stocks: { symbol: string; change_pct: number; price: number }[]
}

export interface DiscoveryStock {
  symbol: string
  name: string
  sector: string
  price: number
  change_pct: number
  score: number
  grade: string
  signal: string
  trend: string
  confidence: number
  stop_loss: number
  target1: number
  target2: number
  risk_reward: number | null
  reasons: string[]
  volume_ratio: number | null
  rsi: number | null
  category: string
}

export interface NewsItem {
  source: string
  title: string
  link: string
  summary: string
  published: string
  sentiment: 'positive' | 'negative' | 'neutral'
  impact: 'high' | 'medium' | 'low'
}

export interface DepthLevel {
  price: number
  qty: number
}

export interface MarketDepth {
  symbol: string
  price: number
  bid: number
  ask: number
  spread: number
  bids: DepthLevel[]
  asks: DepthLevel[]
  note: string
}

export interface IntradaySignal {
  symbol: string
  timeframe: string
  price: number
  action: string
  signal: string
  confidence: number
  entry: number
  stop_loss: number
  target1: number
  target2: number
  risk_reward: number
  trend: string
  momentum: string
  volume_confirmation: boolean
  rsi: number
  nearest_support: number | null
  nearest_resistance: number | null
  updated_at: number
  signals?: { indicator: string; signal: string; strength?: string; value?: number; reason: string }[]
  patterns?: { pattern: string; type: string; desc: string }[]
  error?: string
}

export interface WatchlistItem {
  symbol: string
  name: string
  addedAt: number
  alertAbove?: number
  alertBelow?: number
}

export interface PortfolioHolding {
  symbol: string
  name: string
  qty: number
  avgPrice: number
  addedAt: number
}

export interface AISignal {
  indicator: string
  signal: 'buy' | 'sell' | 'hold' | 'confirm'
  strength: string
  value: number
  reason: string
}

export interface ForecastResult {
  symbol: string
  forecast: {
    direction: 'UP' | 'DOWN' | 'FLAT'
    confidence: number
    prob_up: number
    prob_down: number
    prob_flat: number
    current_price: number
    estimated_target: number
    estimated_low: number
    horizon: string
    model: string
  }
  context: {
    trend: string
    overall_signal: string
    ta_confidence: number
    ta_score: number
    nearest_resistance: number | null
    nearest_support: number | null
    pivot: number | null
    fib_618: number | null
    fib_382: number | null
    atr: number | null
    rsi: number | null
    supertrend: string | null
    ichimoku_bias: string
  }
  signals_summary: { indicator: string; signal: string; reason: string }[]
  order_blocks: { type: string; top: number; bottom: number; desc: string }[]
  fvg: { type: string; top: number; bottom: number; gap_size: number; desc: string }[]
  bos_choch: { type: string; direction: string; level: number; desc: string }[]
  candles_used: number
  model_trained: boolean
  error?: string
}

export interface BudgetRecommendation {
  symbol: string
  name: string
  sector: string
  price: number
  score: number
  grade: string
  qty: number
  cost: number
  leftover: number
  reasons: string[]
  signal: string
  trend: string
  confidence: number
  stop_loss: number
  target1: number
  target2: number
  risk_reward: number
  suggested_qty_equal_split: number
}

export interface BudgetAdvice {
  budget: number
  stocks_analyzed: number
  stocks_affordable: number
  recommendations: BudgetRecommendation[]
  summary: {
    top_pick: string | null
    top_pick_symbol: string | null
    avg_score: number
    total_if_all_bought: number
    leftover_if_all_bought: number
    best_grade: string | null
  }
  error?: string
}

export interface AIAnalysis {
  symbol: string
  name: string
  technical: {
    current_price: number
    trend: string
    overall_signal: string
    confidence: number
    score: number
    stop_loss: number
    target1: number
    target2: number
    risk_reward: number
    indicators: Record<string, number | null>
    signals: AISignal[]
    candlestick_patterns: { pattern: string; type: string; desc: string }[]
    chart_patterns: { pattern: string; type: string; desc: string }[]
    support_resistance: { pivot: number; resistance: number[]; support: number[] }
  }
  ai_analysis: {
    signal: 'BUY' | 'SELL' | 'HOLD'
    confidence: number
    summary: string
    reasoning: string
    entry_price: number
    stop_loss: number
    target1: number
    target2: number
    risk_reward: number
    timeframe: string
    key_levels: { strong_resistance: number; strong_support: number }
    risks: string[]
    market_context: string
    sentiment: string
    source: string
  }
  error?: string
}

export interface AnalysisSnapshot {
  timestamp: number
  signal: 'BUY' | 'SELL' | 'HOLD'
  confidence: number
  price: number
  score: number
  trend: string
}

interface JarvisState {
  status: 'idle' | 'thinking' | 'speaking' | 'listening' | 'executing'
  messages: Message[]
  tasks: Task[]
  agents: Agent[]
  systemStats: SystemStats
  llmInfo: LLMInfo
  llmSwitching: boolean
  voiceActive: boolean
  activeNav: string
  connected: boolean
  // Stocks
  stocks: StockQuote[]
  indices: IndexQuote[]
  stocksLoading: boolean
  selectedStock: string | null
  stockChart: StockChart | null
  chartLoading: boolean
  fundamentals: StockFundamentals | null
  fundamentalsLoading: boolean
  financials: Financials | null
  financialsLoading: boolean
  shareholding: ShareholdingData | null
  shareholdingLoading: boolean
  peers: PeerStock[]
  peersLoading: boolean
  screenerResults: ScreenerResult[]
  screenerLoading: boolean
  analysis: AIAnalysis | null
  analysisLoading: boolean
  // Market Intelligence
  movers: { gainers: MarketMover[]; losers: MarketMover[]; most_active: MarketMover[]; volume_leaders: MarketMover[]; advancing: number; declining: number; unchanged: number } | null
  moversLoading: boolean
  heatmap: SectorHeatmapItem[]
  heatmapLoading: boolean
  discovery: DiscoveryStock[]
  discoveryLoading: boolean
  discoveryCategory: string
  news: NewsItem[]
  newsLoading: boolean
  depth: MarketDepth | null
  depthLoading: boolean
  intradaySignal: IntradaySignal | null
  intradayLoading: boolean
  // Watchlist & Portfolio (persisted in localStorage)
  watchlist: WatchlistItem[]
  portfolio: PortfolioHolding[]
  analysisHistory: AnalysisSnapshot[]
  forecast: ForecastResult | null
  forecastLoading: boolean
  budgetAdvice: BudgetAdvice | null
  budgetLoading: boolean
  calendar: { events: any[]; holidays: any[] } | null
  calendarLoading: boolean
  triggeredAlerts: { symbol: string; price: number; type: string; threshold: number }[]
  // Paper quick-trade
  quickTrade: QuickTradePayload | null
  openQuickTrade: (payload: QuickTradePayload) => void
  closeQuickTrade: () => void
  activePaperPortfolioId: string | null
  setActivePaperPortfolioId: (id: string | null) => void
  // Position marker — shown on stock chart when navigating from a position card
  positionMarker: { symbol: string; buyPrice: number; openedAt: number } | null
  setPositionMarker: (marker: { symbol: string; buyPrice: number; openedAt: number } | null) => void
  // Actions
  sendMessage: (content: string) => Promise<void>
  addSystemMessage: (content: string) => void
  setStatus: (status: JarvisState['status']) => void
  addTask: (task: Task) => void
  setActiveNav: (nav: string) => void
  setVoiceActive: (active: boolean) => void
  fetchStatus: () => Promise<void>
  switchLLMProvider: (name: string) => Promise<void>
  startPolling: () => () => void
  fetchStocks: (universe?: string) => Promise<void>
  fetchChart: (symbol: string, interval?: string, range?: string) => Promise<void>
  setSelectedStock: (symbol: string | null) => void
  fetchFundamentals: (symbol: string) => Promise<void>
  fetchFinancials: (symbol: string) => Promise<void>
  fetchShareholding: (symbol: string) => Promise<void>
  fetchPeers: (symbol: string) => Promise<void>
  runScreener: (filters: Record<string, string>) => Promise<void>
  fetchAnalysis: (symbol: string, interval?: string, range?: string) => Promise<void>
  // Market Intelligence actions
  fetchMovers: (universe?: string) => Promise<void>
  fetchHeatmap: (universe?: string) => Promise<void>
  fetchDiscovery: (category?: string, universe?: string) => Promise<void>
  fetchNews: (symbol?: string) => Promise<void>
  fetchDepth: (symbol: string) => Promise<void>
  fetchIntradaySignal: (symbol: string, timeframe?: string) => Promise<void>
  fetchCalendar: () => Promise<void>
  // Watchlist
  addToWatchlist: (item: WatchlistItem) => void
  removeFromWatchlist: (symbol: string) => void
  setWatchlistAlert: (symbol: string, above?: number, below?: number) => void
  // Portfolio
  addHolding: (holding: PortfolioHolding) => void
  removeHolding: (symbol: string) => void
  updateHolding: (symbol: string, qty: number, avgPrice: number) => void
  clearAnalysisHistory: () => void
  fetchForecast: (symbol: string, horizon?: number) => Promise<void>
  fetchRecommendations: (budget: number, topN?: number) => Promise<void>
  fetchTriggeredAlerts: () => Promise<void>
  dismissTriggeredAlerts: () => void
}

// ── Paper Trading Quick-Trade (shared across all pages) ───────
export interface QuickTradePayload {
  symbol: string
  side: 'BUY' | 'SELL'
  price?: number
  entry?: number
  stop_loss?: number
  target1?: number
  signal?: string
  confidence?: number
  source?: string
}

export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'
export const WS_URL = API_URL.replace('http', 'ws')

// ── Browser TTS helper ────────────────────────────────────────
function speakText(text: string, onStart: () => void, onEnd: () => void) {
  if (typeof window === 'undefined' || !window.speechSynthesis) { onEnd(); return }

  const clean = text
    .replace(/```[\s\S]*?```/g, 'code block omitted')
    .replace(/[*_`#>~|\[\]]/g, '')
    .replace(/\n+/g, ' ')
    .trim()
  const spoken = clean.length > 500 ? clean.slice(0, 497) + '...' : clean
  if (!spoken) { onEnd(); return }

  // Signal speaking immediately — don't wait for onstart (fires late on Chrome)
  onStart()

  const doSpeak = (voices: SpeechSynthesisVoice[]) => {
    const utt = new SpeechSynthesisUtterance(spoken)
    utt.lang = 'en-IN'
    utt.rate = 1.05
    utt.pitch = 0.9
    utt.volume = 1
    const preferred =
      voices.find(v => v.name.toLowerCase().includes('google uk english male')) ||
      voices.find(v => v.name.toLowerCase().includes('david')) ||
      voices.find(v => v.name.toLowerCase().includes('daniel')) ||
      voices.find(v => v.lang === 'en-IN') ||
      voices.find(v => v.lang.startsWith('en-'))
    if (preferred) utt.voice = preferred
    utt.onend = onEnd
    utt.onerror = () => { onEnd() }
    // Cancel any previous speech, then wait 80ms for Chrome to fully clear its queue
    window.speechSynthesis.cancel()
    setTimeout(() => {
      // If cancelled externally during the delay, don't speak
      if (!window.speechSynthesis) return
      if (window.speechSynthesis.paused) window.speechSynthesis.resume()
      window.speechSynthesis.speak(utt)
    }, 80)
  }

  const voices = window.speechSynthesis.getVoices()
  if (voices.length > 0) {
    doSpeak(voices)
  } else {
    window.speechSynthesis.onvoiceschanged = () => {
      window.speechSynthesis.onvoiceschanged = null
      doSpeak(window.speechSynthesis.getVoices())
    }
  }
}

export const useJarvisStore = create<JarvisState>((set, get) => ({
  status: 'idle',
  messages: [],
  tasks: [],
  agents: [],
  systemStats: { cpu: 0, memory: 0, network: 0, uptime: '0s' },
  llmInfo: { provider: '—', model: '—', status: 'disconnected', tokensUsed: 0, available: [] },
  llmSwitching: false,
  voiceActive: false,
  activeNav: 'dashboard',
  connected: false,
  stocks: [],
  indices: [],
  stocksLoading: false,
  selectedStock: null,
  stockChart: null,
  chartLoading: false,
  fundamentals: null,
  fundamentalsLoading: false,
  financials: null,
  financialsLoading: false,
  shareholding: null,
  shareholdingLoading: false,
  peers: [],
  peersLoading: false,
  screenerResults: [],
  screenerLoading: false,
  analysis: null,
  analysisLoading: false,
  movers: null,
  moversLoading: false,
  heatmap: [],
  heatmapLoading: false,
  discovery: [],
  discoveryLoading: false,
  discoveryCategory: 'all',
  news: [],
  newsLoading: false,
  depth: null,
  depthLoading: false,
  intradaySignal: null,
  intradayLoading: false,
  watchlist: typeof window !== 'undefined' ? (() => { try { return JSON.parse(localStorage.getItem('jarvis_watchlist') || '[]') } catch { return [] } })() : [],
  portfolio: typeof window !== 'undefined' ? (() => { try { return JSON.parse(localStorage.getItem('jarvis_portfolio') || '[]') } catch { return [] } })() : [],
  analysisHistory: [],
  forecast: null,
  forecastLoading: false,
  budgetAdvice: null,
  budgetLoading: false,
  calendar: null,
  calendarLoading: false,
  triggeredAlerts: [],
  quickTrade: null,
  activePaperPortfolioId: typeof window !== 'undefined' ? (localStorage.getItem('jarvis_active_pid') ?? null) : null,

  positionMarker: null,
  setPositionMarker: (marker) => set({ positionMarker: marker }),

  openQuickTrade: (payload) => set({ quickTrade: payload }),
  closeQuickTrade: () => set({ quickTrade: null }),
  setActivePaperPortfolioId: (id) => {
    if (typeof window !== 'undefined') {
      if (id) localStorage.setItem('jarvis_active_pid', id)
      else localStorage.removeItem('jarvis_active_pid')
    }
    set({ activePaperPortfolioId: id })
  },

  setStatus: (status) => set({ status }),
  addTask: (task) => set((s) => ({ tasks: [...s.tasks, task] })),
  setActiveNav: (nav) => set({ activeNav: nav }),
  setVoiceActive: (active) => set({ voiceActive: active }),
  setSelectedStock: (symbol) => set({
    selectedStock: symbol,
    fundamentals: null,
    financials: null,
    shareholding: null,
    peers: [],
    analysis: null,
    analysisHistory: [],
    forecast: null,
  }),

  fetchStocks: async (universe = 'nifty50') => {
    set({ stocksLoading: true })
    try {
      const res = await fetch(`${API_URL}/api/stocks?universe=${universe}`)
      const data = await res.json()
      set({ stocks: data.stocks || [], indices: data.indices || [], stocksLoading: false })
    } catch {
      set({ stocksLoading: false })
    }
  },

  fetchChart: async (symbol, interval = '5m', range = '1d') => {
    set({ chartLoading: true, stockChart: null })
    try {
      const res = await fetch(`${API_URL}/api/stocks/chart/${symbol}?interval=${interval}&range=${range}`)
      const data = await res.json()
      set({ stockChart: data, chartLoading: false })
    } catch {
      set({ chartLoading: false })
    }
  },

  fetchFundamentals: async (symbol: string) => {
    set({ fundamentalsLoading: true, fundamentals: null })
    try {
      const res = await fetch(`${API_URL}/api/stocks/fundamentals/${symbol}`)
      const data = await res.json()
      set({ fundamentals: data, fundamentalsLoading: false })
    } catch {
      set({ fundamentalsLoading: false })
    }
  },

  fetchFinancials: async (symbol: string) => {
    set({ financialsLoading: true, financials: null })
    try {
      const res = await fetch(`${API_URL}/api/stocks/financials/${symbol}`)
      const data = await res.json()
      set({ financials: data, financialsLoading: false })
    } catch {
      set({ financialsLoading: false })
    }
  },

  fetchShareholding: async (symbol: string) => {
    set({ shareholdingLoading: true, shareholding: null })
    try {
      const res = await fetch(`${API_URL}/api/stocks/shareholding/${symbol}`)
      const data = await res.json()
      set({ shareholding: data, shareholdingLoading: false })
    } catch {
      set({ shareholdingLoading: false })
    }
  },

  fetchPeers: async (symbol: string) => {
    set({ peersLoading: true, peers: [] })
    try {
      const res = await fetch(`${API_URL}/api/stocks/peers/${symbol}`)
      const data = await res.json()
      set({ peers: data.peers || [], peersLoading: false })
    } catch {
      set({ peersLoading: false })
    }
  },

  runScreener: async (filters: Record<string, string>) => {
    set({ screenerLoading: true, screenerResults: [] })
    try {
      const params = new URLSearchParams(filters).toString()
      const res = await fetch(`${API_URL}/api/stocks/screener?${params}`)
      const data = await res.json()
      set({ screenerResults: data.results || [], screenerLoading: false })
    } catch {
      set({ screenerLoading: false })
    }
  },

  fetchAnalysis: async (symbol: string, interval = '15m', range = '5d') => {
    set({ analysisLoading: true })
    try {
      const res = await fetch(`${API_URL}/api/stocks/analyze/${symbol}?interval=${interval}&range=${range}`)
      const data = await res.json()
      if (!data.error && data.ai_analysis) {
        const snap: AnalysisSnapshot = {
          timestamp: Date.now(),
          signal: data.ai_analysis.signal,
          confidence: data.ai_analysis.confidence,
          price: data.technical?.current_price ?? 0,
          score: data.technical?.score ?? 0,
          trend: data.technical?.trend ?? 'neutral',
        }
        set((s) => ({
          analysis: data,
          analysisLoading: false,
          analysisHistory: [snap, ...s.analysisHistory].slice(0, 10),
        }))
      } else {
        set({ analysis: data, analysisLoading: false })
      }
    } catch {
      set({ analysisLoading: false })
    }
  },

  clearAnalysisHistory: () => set({ analysisHistory: [] }),

  fetchTriggeredAlerts: async () => {
    try {
      const res = await fetch(`${API_URL}/api/alerts/triggered`)
      const data = await res.json()
      if (data.triggered?.length) {
        set((s) => ({ triggeredAlerts: [...s.triggeredAlerts, ...data.triggered].slice(-50) }))
        // Push visual toasts for each alert
        if (typeof window !== 'undefined') {
          import('@/components/NotificationToasts').then(({ pushToast }) => {
            data.triggered.forEach((a: { symbol: string; price: number; type: string; threshold: number }) => {
              pushToast({
                type: a.type === 'above' ? 'buy' : 'sell',
                title: `PRICE ALERT`,
                symbol: a.symbol,
                entry: a.price,
                target: a.threshold,
                body: `${a.symbol} hit ${a.type === 'above' ? 'above' : 'below'} ₹${a.threshold}`,
                modal: 'stocks',
              })
            })
          }).catch(() => {})
        }
        await fetch(`${API_URL}/api/alerts/triggered`, { method: 'DELETE' }).catch(() => {})
      }
    } catch {}
  },

  dismissTriggeredAlerts: () => set({ triggeredAlerts: [] }),

  fetchForecast: async (symbol: string, horizon = 30) => {
    set({ forecastLoading: true, forecast: null })
    try {
      const res = await fetch(`${API_URL}/api/stocks/forecast/${symbol}?horizon=${horizon}`)
      const data = await res.json()
      set({ forecast: data, forecastLoading: false })
    } catch {
      set({ forecastLoading: false })
    }
  },

  fetchRecommendations: async (budget: number, topN = 5) => {
    set({ budgetLoading: true, budgetAdvice: null })
    try {
      const res = await fetch(`${API_URL}/api/stocks/recommend?budget=${budget}&top_n=${topN}`)
      const data = await res.json()
      set({ budgetAdvice: data, budgetLoading: false })
    } catch {
      set({ budgetLoading: false })
    }
  },

  fetchCalendar: async () => {
    set({ calendarLoading: true })
    try {
      const res = await fetch(`${API_URL}/api/market/calendar`)
      const data = await res.json()
      set({ calendar: data, calendarLoading: false })
    } catch {
      set({ calendarLoading: false })
    }
  },

  fetchMovers: async (universe = 'nifty50') => {
    set({ moversLoading: true })
    try {
      const res = await fetch(`${API_URL}/api/market/movers?universe=${universe}`)
      const data = await res.json()
      set({ movers: data, moversLoading: false })
    } catch {
      set({ moversLoading: false })
    }
  },

  fetchHeatmap: async (universe = 'nifty50') => {
    set({ heatmapLoading: true })
    try {
      const res = await fetch(`${API_URL}/api/market/heatmap?universe=${universe}`)
      const data = await res.json()
      set({ heatmap: data.sectors ?? data ?? [], heatmapLoading: false })
    } catch {
      set({ heatmapLoading: false })
    }
  },

  fetchDiscovery: async (category = 'intraday', universe = 'nifty50') => {
    set({ discoveryLoading: true, discoveryCategory: category })
    try {
      const res = await fetch(`${API_URL}/api/market/discovery?category=${category}&universe=${universe}`)
      const data = await res.json()
      set({ discovery: data.recommendations ?? data.stocks ?? [], discoveryLoading: false })
    } catch {
      set({ discoveryLoading: false })
    }
  },

  fetchNews: async (symbol?: string) => {
    set({ newsLoading: true })
    try {
      const url = symbol ? `${API_URL}/api/market/news?symbol=${symbol}` : `${API_URL}/api/market/news`
      const res = await fetch(url)
      const data = await res.json()
      set({ news: data.news ?? data ?? [], newsLoading: false })
    } catch {
      set({ newsLoading: false })
    }
  },

  fetchDepth: async (symbol: string) => {
    set({ depthLoading: true })
    try {
      const res = await fetch(`${API_URL}/api/market/depth/${symbol}`)
      const data = await res.json()
      set({ depth: data, depthLoading: false })
    } catch {
      set({ depthLoading: false })
    }
  },

  fetchIntradaySignal: async (symbol: string, timeframe = '5m') => {
    set({ intradayLoading: true })
    try {
      const res = await fetch(`${API_URL}/api/market/intraday/${symbol}?timeframe=${timeframe}`)
      const data = await res.json()
      set({ intradaySignal: data, intradayLoading: false })
    } catch {
      set({ intradayLoading: false })
    }
  },

  addToWatchlist: (item) => set((s) => {
    const exists = s.watchlist.some(w => w.symbol === item.symbol)
    if (exists) return {}
    const updated = [...s.watchlist, item]
    if (typeof window !== 'undefined') localStorage.setItem('jarvis_watchlist', JSON.stringify(updated))
    return { watchlist: updated }
  }),

  removeFromWatchlist: (symbol) => set((s) => {
    const updated = s.watchlist.filter(w => w.symbol !== symbol)
    if (typeof window !== 'undefined') localStorage.setItem('jarvis_watchlist', JSON.stringify(updated))
    return { watchlist: updated }
  }),

  setWatchlistAlert: (symbol, above, below) => set((s) => {
    const updated = s.watchlist.map(w =>
      w.symbol === symbol ? { ...w, alertAbove: above, alertBelow: below } : w
    )
    if (typeof window !== 'undefined') localStorage.setItem('jarvis_watchlist', JSON.stringify(updated))
    return { watchlist: updated }
  }),

  addHolding: (holding) => set((s) => {
    const updated = [...s.portfolio.filter(h => h.symbol !== holding.symbol), holding]
    if (typeof window !== 'undefined') localStorage.setItem('jarvis_portfolio', JSON.stringify(updated))
    return { portfolio: updated }
  }),

  removeHolding: (symbol) => set((s) => {
    const updated = s.portfolio.filter(h => h.symbol !== symbol)
    if (typeof window !== 'undefined') localStorage.setItem('jarvis_portfolio', JSON.stringify(updated))
    return { portfolio: updated }
  }),

  updateHolding: (symbol, qty, avgPrice) => set((s) => {
    const updated = s.portfolio.map(h => h.symbol === symbol ? { ...h, qty, avgPrice } : h)
    if (typeof window !== 'undefined') localStorage.setItem('jarvis_portfolio', JSON.stringify(updated))
    return { portfolio: updated }
  }),

  fetchStatus: async () => {
    try {
      const res = await fetch(`${API_URL}/api/status`)
      const data = await res.json()

      const agentRoles: string[] = data.agents || []
      const agents: Agent[] = agentRoles.map((role, i) => ({
        id: String(i + 1),
        name: role.charAt(0).toUpperCase() + role.slice(1) + ' Agent',
        status: 'active' as const,
        task: undefined,
      }))

      const llmInfo: LLMInfo = {
        provider: data.llm_provider || '—',
        model: (data.llm_providers_available || []).join(', ') || '—',
        status: data.llm_provider && data.llm_provider !== 'none (fallback mode)' ? 'connected' : 'disconnected',
        tokensUsed: 0,
        available: data.llm_providers_available || [],
      }

      const memData = data.memory || {}
      const tasks: Task[] = [
        { id: 'mem', title: `Memory: ${memData.total || 0} entries`, status: 'completed' as const },
        { id: 'tools', title: `Tools: ${data.tools || 0} loaded`, status: 'completed' as const },
        { id: 'plugins', title: `Plugins: ${(data.plugins || []).length} active`, status: 'completed' as const },
      ]

      const state = data.state || {}
      const uptime = state.session_duration
        ? `${Math.floor(state.session_duration / 60)}m ${Math.floor(state.session_duration % 60)}s`
        : '0s'

      set({
        connected: true, agents, llmInfo, tasks,
        systemStats: {
          cpu: Math.round(state.confidence * 100) || 0,
          memory: memData.total || 0,
          network: state.interaction_count || 0,
          uptime,
        },
      })
    } catch {
      set({ connected: false })
    }
  },

  switchLLMProvider: async (name: string) => {
    set({ llmSwitching: true })
    try {
      const res = await fetch(`${API_URL}/api/llm/provider/${name}`, { method: 'POST' })
      const data = await res.json()
      if (!data.error) {
        set((s) => ({
          llmInfo: { ...s.llmInfo, provider: data.active, available: data.available },
          llmSwitching: false,
        }))
      } else {
        set({ llmSwitching: false })
      }
    } catch {
      set({ llmSwitching: false })
    }
  },

  startPolling: () => {
    get().fetchStatus()
    get().fetchTriggeredAlerts()
    const interval = setInterval(() => {
      get().fetchStatus()
      get().fetchTriggeredAlerts()
    }, 30000)
    return () => clearInterval(interval)
  },

  addSystemMessage: (content: string) => {
    const msg: Message = {
      id: crypto.randomUUID(), role: 'assistant', content, timestamp: Date.now(),
    }
    set((s) => ({ messages: [...s.messages, msg] }))
  },

  sendMessage: async (content: string) => {
    // Cancel any ongoing TTS and hide the overlay immediately
    if (typeof window !== 'undefined') {
      if (window.speechSynthesis?.speaking || window.speechSynthesis?.pending) {
        window.speechSynthesis.cancel()
      }
      // Hide overlay so new response replaces it cleanly
      import('@/components/JarvisOverlay').then(m => m.hideJarvisOverlay()).catch(() => {})
    }

    const userMsg: Message = {
      id: crypto.randomUUID(), role: 'user', content, timestamp: Date.now(),
    }
    set((s) => ({ messages: [...s.messages, userMsg], status: 'thinking' }))
    const selectedStock = get().selectedStock

    try {
      const ws = new WebSocket(`${WS_URL}/api/ws/chat`)
      let fullResponse = ''

      await new Promise<void>((resolve, reject) => {
        const assistantId = crypto.randomUUID()
        const assistantTs = Date.now()
        let assistantAdded = false
        let rafPending = false
        let tradeProposal: TradeProposal | null = null
        let settled = false
        const settle = () => { if (!settled) { settled = true; resolve() } }

        const flushToState = () => {
          rafPending = false
          set((s) => {
            const msgs = [...s.messages]
            const idx = msgs.findIndex(m => m.id === assistantId)
            if (idx !== -1) {
              msgs[idx] = { ...msgs[idx], content: fullResponse }
            } else {
              msgs.push({ id: assistantId, role: 'assistant', content: fullResponse, timestamp: assistantTs })
            }
            return { messages: msgs }
          })
        }

        ws.onopen = () => ws.send(JSON.stringify({ message: content, user_id: 'default', selected_stock: selectedStock }))
        ws.onmessage = (event) => {
          const data = JSON.parse(event.data)
          if (data.type === 'token') {
            fullResponse += data.content
            if (!assistantAdded) {
              assistantAdded = true
              flushToState()
            } else if (!rafPending) {
              rafPending = true
              requestAnimationFrame(flushToState)
            }
          } else if (data.type === 'done') {
            tradeProposal = data.status?.trade_proposal ?? null
            set((s) => {
              const msgs = [...s.messages]
              const idx = msgs.findIndex(m => m.id === assistantId)
              if (idx !== -1) {
                msgs[idx] = { ...msgs[idx], content: fullResponse, ...(tradeProposal ? { tradeProposal } : {}) }
              }
              return { messages: msgs }
            })
            ws.close(); settle()
          }
        }
        ws.onerror = () => { ws.close(); reject(new Error('ws_failed')) }
        ws.onclose = () => settle()
      })

      if (fullResponse) {
        set({ status: 'speaking' })
        // Show visual overlay — import lazily to avoid SSR issues
        if (typeof window !== 'undefined') {
          import('@/components/JarvisOverlay').then(m => m.showJarvisOverlay(fullResponse)).catch(() => {})
        }
        speakText(fullResponse, () => {}, () => set({ status: 'idle' }))
        get().fetchStatus()
        return
      }
    } catch {}

    try {
      const res = await fetch(`${API_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: content, selected_stock: selectedStock }),
      })
      const data = await res.json()
      const reply = data.response
      set((s) => ({
        messages: [...s.messages, { id: crypto.randomUUID(), role: 'assistant', content: reply, timestamp: Date.now() }],
        status: 'idle',
      }))
      set({ status: 'speaking' })
      if (typeof window !== 'undefined') {
        import('@/components/JarvisOverlay').then(m => m.showJarvisOverlay(reply)).catch(() => {})
      }
      speakText(reply, () => {}, () => set({ status: 'idle' }))
      get().fetchStatus()
    } catch {
      set((s) => ({
        messages: [...s.messages, { id: crypto.randomUUID(), role: 'assistant', content: 'Connection error. Backend offline.', timestamp: Date.now() }],
        status: 'idle', connected: false,
      }))
    }
  },
}))

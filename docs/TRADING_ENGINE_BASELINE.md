# Trading Engine Baseline

**Version**: v0.7.1-trading-verified  
**V&V Completed**: 2026-08-07  
**Status**: FROZEN — do not modify trading logic without a new V&V cycle  
**Test Baseline**: 1517/1517 passing

This document is the permanent reference for every formula, assumption, and known
limitation in the Jarvis trading engine. It was produced after the V&V phase
(VV-001 through VV-010) that preceded Phase 7 implementation.

---

## 1. Technical Indicators

### SMA — Simple Moving Average
**File**: `app/api/technical_analysis.py` → `_sma()`  
**Formula**: `SMA(n) = sum(close[i-n+1 .. i]) / n`  
**Window**: configurable (default 20)  
**Implementation**: sliding window sum — O(n) not O(n²)  
**Warm-up**: first valid value at index `n-1`

---

### EMA — Exponential Moving Average
**File**: `_ema()`  
**Formula**: `EMA(i) = close(i) × k + EMA(i-1) × (1-k)`, where `k = 2 / (period+1)`  
**Seed**: SMA of first `period` values  
**Warm-up**: first valid value at index `period-1`  
**Reference**: Wilder / standard EMA definition

---

### RSI — Relative Strength Index
**File**: `_rsi()`  
**Formula**: `RSI = 100 - 100 / (1 + RS)`, where `RS = avg_gain / avg_loss`  
**Smoothing**: Wilder smoothing — `avg_gain = (prev_avg_gain × (n-1) + gain) / n`  
**Period**: 14 (default)  
**Warm-up**: first valid value at index `period` (requires `period+1` closes)  
**Thresholds used in signals**: oversold < 35, overbought > 65

---

### MACD — Moving Average Convergence Divergence
**File**: `_macd()`  
**Formula**:
- MACD line = EMA(12) − EMA(26)
- Signal line = EMA(9) of MACD line
- Histogram = MACD line − Signal line

**Warm-up**: first MACD value at index 25; first signal value 8 bars later  
**Signal threshold**: relative — `current_price × 0.0002` (0.02% of price)

---

### Bollinger Bands
**File**: `_bollinger()`  
**Formula**:
- Middle = SMA(20)
- Upper = Middle + 2 × σ
- Lower = Middle − 2 × σ
- σ = population std dev of closes over the window

**Period**: 20, std_dev multiplier: 2.0  
**Squeeze threshold**: BB width < 2% of middle band

---

### ATR — Average True Range
**File**: `_atr()`  
**Formula**: `TR = max(H-L, |H-prev_C|, |L-prev_C|)`  
**Smoothing**: Wilder smoothing (same as RSI)  
**Seed**: SMA of first `period` TRs  
**Period**: 14 (default)  
**First TR**: `H[0] - L[0]` (no previous close available)

---

### Stochastic Oscillator
**File**: `_stochastic()`  
**Formula**: `%K = (close - lowest_low) / (highest_high - lowest_low) × 100`  
**%D**: SMA(3) of %K  
**Period**: K=14, D=3  
**Edge case**: H == L → %K = 50.0  
**Thresholds**: oversold < 20, overbought > 80

---

### VWAP — Volume Weighted Average Price
**File**: `_vwap()`  
**Formula**: `VWAP = cumsum(TP × volume) / cumsum(volume)`, where `TP = (H+L+C)/3`  
**Reset**: cumulative from start of candle series — **not** reset per trading day  
**Known limitation**: for multi-day feeds this is a rolling VWAP, not a true intraday VWAP.
True intraday VWAP requires session boundary detection. Enhancement deferred to Phase 8.

---

### Williams %R
**File**: `_williams_r()`  
**Formula**: `%R = -100 × (HH - close) / (HH - LL)`  
**Range**: -100 to 0  
**Period**: 14  
**Thresholds**: oversold < -80, overbought > -20  
**Edge case**: HH == LL → -50.0

---

### CCI — Commodity Channel Index
**File**: `_cci()`  
**Formula**: `CCI = (TP - mean_TP) / (0.015 × mean_deviation)`  
**TP**: (H + L + C) / 3  
**Period**: 20  
**Constant**: 0.015 (Lambert's original)  
**Thresholds**: oversold < -100, overbought > +100

---

### MFI — Money Flow Index
**File**: `_mfi()`  
**Formula**: volume-weighted RSI using Typical Price  
**Period**: 14  
**Positive MF**: bars where TP > previous TP  
**Negative MF**: bars where TP < previous TP  
**Thresholds**: oversold < 20, overbought > 80

---

### OBV — On-Balance Volume
**File**: `_obv()`  
**Formula**: cumulative — add volume on up-close, subtract on down-close  
**Seed**: 0.0  
**Signal**: OBV rising vs 5-bar-ago value

---

### Supertrend
**File**: `_supertrend()`  
**Formula**:
- Basic upper band = (H+L)/2 + multiplier × ATR
- Basic lower band = (H+L)/2 − multiplier × ATR
- Final upper band: tightens only (never widens while price is below it)
- Final lower band: rises only (never falls while price is above it)

**Direction**:
- Was bearish (supertrend = upper band): flip to bullish only when `close > upper_band[i-1]`
- Was bullish (supertrend = lower band): flip to bearish only when `close < lower_band[i-1]`

**Parameters**: period=10, multiplier=3.0  
**V&V fix**: direction previously compared against newly-computed band — corrected to use previous bar's band to prevent premature flips

---

### Ichimoku Cloud
**File**: `_ichimoku()`  
**Components**:
- Tenkan-sen (Conversion): (9-period high + 9-period low) / 2
- Kijun-sen (Base): (26-period high + 26-period low) / 2
- Senkou Span A: (Tenkan + Kijun) / 2, plotted 26 periods ahead
- Senkou Span B: (52-period high + 52-period low) / 2, plotted 26 periods ahead
- Chikou Span: current close, plotted 26 periods back

**Look-ahead**: Senkou A/B are written at `i+26` — `last()` retrieves the most recent
populated value which is 26 bars ago. No look-ahead bias. ✅

---

### Parabolic SAR
**File**: `_parabolic_sar()`  
**Formula**: standard Wilder Parabolic SAR  
**AF**: starts at 0.02, increments by 0.02 on each new extreme, max 0.20  
**Reversal**: when price crosses SAR, direction flips and SAR resets to the extreme point  
**SAR constraint**: in uptrend, SAR ≤ min of previous two lows; in downtrend, SAR ≥ max of previous two highs

---

### Fibonacci Retracement
**File**: `_fibonacci()`  
**Levels**: 0%, 23.6%, 38.2%, 50%, 61.8%, 78.6%, 100%  
**Swing**: highest high and lowest low over last 50 bars  
**Direction**: retracement from swing high down to swing low

---

### Pivot Points
**File**: `_pivot_points()`  
**Input**: previous candle's HLC (not current bar)  
**V&V fix**: was using current candle — corrected to `candles[-2]`  
**Types computed**: Standard, Camarilla, Woodie

**Standard**:
- Pivot = (H + L + C) / 3
- R1 = 2P − L, R2 = P + (H−L), R3 = H + 2(P−L)
- S1 = 2P − H, S2 = P − (H−L), S3 = L − 2(H−P)

**Camarilla**:
- R4 = C + range × 1.1/2, R3 = C + range × 1.1/4, etc.

**Woodie**:
- Pivot = (H + L + 2C) / 4

---

### Donchian Channel
**File**: `_donchian()`  
**Formula**: upper = highest high over period; lower = lowest low over period  
**Period**: 20  
**Middle**: (upper + lower) / 2

---

### Keltner Channel
**File**: `_keltner()`  
**Formula**: EMA(20) ± 2 × ATR(20)  
**Squeeze signal**: BB inside Keltner = volatility compression

---

## 2. Candlestick Patterns

**File**: `detect_candlestick_patterns()`  
**Scan window**: last 5 candles (patterns detected at each bar)  
**Minimum candles required**: 3

| Pattern | Type | Minimum Candles | Key Condition |
|---------|------|-----------------|---------------|
| Doji | Neutral | 1 | body/range < 10% |
| Hammer | Bullish | 1 | lower_wick > 2×body, upper_wick < 30% body, bullish |
| Shooting Star | Bearish | 1 | upper_wick > 2×body, lower_wick < 30% body, bearish |
| Bullish Marubozu | Bullish | 1 | bullish, body/range > 90% |
| Bearish Marubozu | Bearish | 1 | bearish, body/range > 90% |
| Bullish Engulfing | Bullish | 2 | prev bearish, current bullish, body > prev body, open < prev close, close > prev open |
| Bearish Engulfing | Bearish | 2 | prev bullish, current bearish, body > prev body, open > prev close, close < prev open |
| Morning Star | Bullish | 3 | bearish + small body + bullish closing above midpoint of candle 1 |
| Evening Star | Bearish | 3 | bullish + small body + bearish closing below midpoint of candle 1 |
| Spinning Top | Neutral | 1 | body/range 10-30%, both wicks > body |
| Bullish Harami | Bullish | 2 | prev bearish large, current bullish small (< 50% prev body), inside prev body |
| Bearish Harami | Bearish | 2 | prev bullish large, current bearish small (< 50% prev body), inside prev body |
| Tweezer Bottom | Bullish | 2 | same low (< 0.1% diff), current bullish, prev bearish |
| Tweezer Top | Bearish | 2 | same high (< 0.1% diff), current bearish, prev bullish |
| Three White Soldiers | Bullish | 3 | 3 consecutive bullish, each close > prev close, each open > prev open, body/range > 60% |
| Three Black Crows | Bearish | 3 | 3 consecutive bearish, each close < prev close, each open < prev open, body/range > 60% |

---

## 3. Smart Money Concepts

**File**: `detect_order_blocks()`, `detect_fvg()`, `detect_bos_choch()`

### Order Blocks
**Definition**: last strong impulse candle (body > 60% of range) before a significant move  
**Bullish OB**: bearish candle where next 2 bars' high exceeds candle high by > 0.3%  
**Bearish OB**: bullish candle where next 2 bars' low falls below candle low by > 0.3%  
**Output**: last 6 most recent blocks  
**No repainting**: detection uses only `candles[i+1..i+2]` which are already closed bars at time of detection. ✅

### Fair Value Gaps (FVG)
**Definition**: 3-candle imbalance — gap between candle[i-1] and candle[i+1]  
**Bullish FVG**: `candle[i+1].low > candle[i-1].high` — unfilled buy imbalance  
**Bearish FVG**: `candle[i+1].high < candle[i-1].low` — unfilled sell imbalance  
**Output**: last 6 most recent gaps  
**No repainting**: all three candles are closed at detection time. ✅

### BOS — Break of Structure
**Definition**: price breaks beyond the last swing high/low in the direction of the existing trend  
**Bullish BOS**: `current > last_swing_high AND last_swing_high > prev_swing_high`  
**Bearish BOS**: `current < last_swing_low AND last_swing_low < prev_swing_low`  
**Swing detection**: local extrema over 3 candles (simple definition)

### CHoCH — Change of Character
**Definition**: price breaks a swing level that contradicts the existing trend — potential reversal  
**Bullish CHoCH**: `current > last_swing_high AND last_swing_high < prev_swing_high` (was making lower highs)  
**Bearish CHoCH**: `current < last_swing_low AND last_swing_low > prev_swing_low` (was making higher lows)  
**Known limitation**: 3-candle swing detection is a simplified definition. More sophisticated implementations use multi-swing structure analysis. Current definition is correct for its stated scope.

---

## 4. Forecasting Pipeline

**File**: `app/api/forecaster.py`

### Label Generation
- Horizon: configurable (default 6 bars = ~30 minutes on 5m data)
- Threshold: ATR-relative — `max(ATR/price × 0.5, 0.002)` — at least 0.2%, at most 0.5 ATR
- Labels: 1 = UP, 0 = DOWN, 2 = FLAT
- **No look-ahead**: features from bar `i`, label from bar `i+horizon`. ✅

### Feature Generation (`build_features()`)
49 features covering:
- Price returns (1, 3, 5, 10 bar)
- Candle structure (high-low ratio, close position)
- Volume (ratio, change)
- Momentum (RSI normalised, MACD, histogram, Stochastic normalised)
- EMA alignment (price vs EMA9/21/50/200, EMA9 vs EMA21, EMA21 vs EMA50)
- VWAP position
- ATR percentage
- Bollinger position and width
- Keltner position
- Donchian position
- Supertrend direction
- Parabolic SAR position
- Ichimoku (price vs Tenkan, Tenkan vs Kijun)
- Fibonacci nearest level distance
- SMC flags (BOS bull/bear, CHoCH bull/bear, near OB, in FVG)
- Candlestick pattern flags (bull count, bear count, neutral, net)
- TA score (normalised)
- Williams %R, CCI, MFI (normalised), OBV trend
- Session time features (progress, is_opening, is_closing)

**V&V fix**: timestamp was in milliseconds, divided as seconds — session features were always wrong. Fixed.

### Training
- Model: XGBoost multi-class softprob (3 classes)
- Class imbalance: sample weights — UP and DOWN upweighted relative to FLAT
- Retrain interval: 4 hours
- Minimum samples: 30

### Confidence Calibration
- If historical accuracy available: `0.4 × model_conf + 0.6 × hist_accuracy`
- If no history: raw model confidence capped at 65%

### Prediction Decision Rule
- UP: `prob_up ≥ 0.45 AND prob_up > prob_flat + 0.05`
- DOWN: `prob_down ≥ 0.45 AND prob_down > prob_flat + 0.05`
- FLAT: otherwise

---

## 5. Risk Engine

**File**: `app/api/technical_analysis.py` → `compute_technical_analysis()`  
**File**: `app/api/auto_trader.py` → `_scan_candidates()`

### ATR-Based Stop Loss and Targets
| Signal | Stop Loss | Target 1 | Target 2 |
|--------|-----------|----------|----------|
| BUY | price − 1.5 × ATR | price + 2.0 × ATR | price + 3.5 × ATR |
| SELL | price + 1.5 × ATR | price − 2.0 × ATR | price − 3.5 × ATR |
| HOLD | price − 1.0 × ATR | price + 1.0 × ATR | price + 2.0 × ATR |

**Risk/Reward**: `|target1 − price| / |price − stop_loss|` — minimum 1.5 required by auto_trader

### Smart Stop Loss (auto_trader)
`smart_sl = min(ATR-based SL, nearest support below price)` — uses the deeper of the two

### Regime-Adaptive Stops
- Normal regime: stop multiplier = 1.5×
- High volatility / reduce_size regime: stop multiplier = 2.0×

### Position Sizing
- Auto-trader: fixed budget per trade (default ₹10,000)
- Backtester: 95% of available cash per trade

---

## 6. Transaction Charges (Indian Market)

**File**: `app/api/paper_trading.py` → `calculate_charges()`

| Charge | Rate | Applied On |
|--------|------|------------|
| Brokerage | 0.03% of value, max ₹20 | Both sides |
| Exchange transaction | 0.00345% | Both sides |
| SEBI charges | 0.0001% | Both sides |
| GST | 18% of (brokerage + exchange) | Both sides |
| Stamp duty | 0.015% | BUY only |
| STT — Intraday | 0.025% | SELL only |
| STT — Delivery | 0.1% | **Both sides** |

**V&V fix**: delivery STT was previously applied on SELL only — corrected to both sides per NSE rules.

---

## 7. Backtesting Assumptions

**File**: `app/api/backtesting.py`

| Assumption | Value |
|------------|-------|
| Execution | Next bar open after signal bar close |
| Slippage | Not modelled (known limitation) |
| Commission | Full Indian market charges via `calculate_charges()` |
| Position sizing | 95% of available cash |
| Warm-up | 30 bars before first signal |
| Data | Daily candles from Yahoo Finance |
| Short selling | Not supported (long-only) |

**V&V fix**: previously executed at signal bar close — corrected to next bar open to eliminate look-ahead bias.

**Known limitation**: slippage is not modelled. Real-world execution will underperform backtest results. Slippage modelling deferred to Phase 8.

---

## 8. Performance Metrics

**File**: `app/api/paper_trading.py`

### Sharpe Ratio
`Sharpe = (avg_daily_return − daily_risk_free) / sample_std_dev × √252`  
Risk-free rate: 6.5% per annum (Indian T-bill proxy)  
**V&V fix**: was using population std dev (÷N) — corrected to sample std dev (÷N-1)

### Annualised Volatility
`Volatility = sample_std_dev(daily_returns) × √252 × 100%`  
**V&V fix**: was using population std dev (÷N) — corrected to sample std dev (÷N-1)

### Maximum Drawdown
`Max DD = max((peak − trough) / peak) × 100%`  
Computed from daily portfolio value snapshots

### Win Rate
`Win Rate = winning_trades / closed_trades × 100%`

### Profit Factor
`Profit Factor = sum(winning PnL) / |sum(losing PnL)|`

---

## 9. Market Regime Detection

**File**: `app/api/market_regime.py`

**Data source**: NIFTY 50 daily candles, 180-day lookback  
**Cache TTL**: 5 minutes

| Regime | Condition |
|--------|-----------|
| strong_bull | Above EMA20/50/200, all aligned, 20d return > 4%, volume expanding |
| weak_bull | Above EMA20/50/200, aligned, but momentum weaker |
| sideways | Above EMA200 but below EMA50, no clear direction |
| high_volatility | ATR% > 1.5× 20-period average ATR% |
| weak_bear | Below EMA20/50/200 |
| strong_bear | Below EMA20/50/200, 20d return < -6% |
| panic | High volatility AND RSI < 30 |
| distribution | Above EMA200, below EMA50, volume expanding, 5d return < -2% |
| accumulation | Above EMA200, below EMA50, volume expanding, 5d return > 1% |

**Signal filter**: BUY suppressed in bear/distribution regimes; SELL suppressed in bull/accumulation regimes  
**Size multiplier**: 0.5× in high_volatility, panic, sideways regimes

---

## 10. V&V Changelog

All 12 fixes applied during V&V phase (VV-001 through VV-010):

| # | File | Severity | Fix |
|---|------|----------|-----|
| 1 | technical_analysis.py | Critical | Supertrend direction compared against new band instead of `upper_band[i-1]` / `lower_band[i-1]` — caused premature trend flips |
| 2 | technical_analysis.py | Medium | Pivot points used current candle HLC — corrected to `candles[-2]` (previous session) |
| 3 | technical_analysis.py | Medium | `find_support_resistance` pivot used current candle HLC — corrected to `candles[-2]` |
| 4 | technical_analysis.py | Low | RSI/EMA/VWAP signal guards used `if rsi:` — corrected to `if rsi is not None:` |
| 5 | forecaster.py | Medium | Timestamp in milliseconds divided as seconds — IST session features always wrong — corrected to `last_ts / 1000` |
| 6 | backtesting.py | Critical | Look-ahead bias — trades executed at signal bar close — corrected to next bar open (`candles[i+1]["o"]`) |
| 7 | paper_trading.py | High | STT delivery applied on SELL only — NSE rules require both BUY and SELL — corrected |
| 8 | paper_trading.py | Medium | Sharpe ratio used population std dev (÷N) — corrected to sample std dev (÷N-1) |
| 9 | paper_trading.py | Medium | Annualised volatility used population std dev (÷N) — corrected to sample std dev (÷N-1) |
| 10 | auto_trader.py | Medium | Scan pipeline missing `clean_candles()` data quality gate — added with quality score ≥ 40 guard |
| 11 | confidence.py | Medium | `PredictionResult.confidence` assumed [0,1] but forecaster returns [0,100] — defensive auto-normalisation added |
| 12 | feature_store.py | Low | `inf`/`NaN` values passed through to model input — non-finite values now skipped |

---

## 11. Known Limitations (Not Bugs)

These are architectural decisions accepted for the current phase. Each is a candidate for Phase 8 enhancement.

| # | Component | Limitation | Phase |
|---|-----------|------------|-------|
| 1 | VWAP | Cumulative from series start, not reset per trading day. Multi-day feeds produce rolling VWAP, not true intraday VWAP | Phase 8 |
| 2 | BOS/CHoCH | 3-candle local extrema definition. More sophisticated SMC uses multi-swing structure | Phase 8 |
| 3 | Backtesting | Slippage not modelled. Real execution will underperform backtest | Phase 8 |
| 4 | Backtesting | Long-only. No short-selling simulation | Phase 8 |
| 5 | Ichimoku | Chikou span plotted as `closes[:-26]` — display only, not used in signal logic | Phase 8 |
| 6 | Forecasting | Walk-forward validation uses same model instance — independent holdout set not implemented | Phase 8 |

---

*This document is the authoritative reference for the Jarvis trading engine as of v0.7.1-trading-verified.*  
*Any modification to trading logic requires a new V&V entry in section 10 and a corresponding test.*

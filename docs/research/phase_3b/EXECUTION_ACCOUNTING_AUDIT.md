# EXECUTION AND RISK ACCOUNTING AUDIT
## Phase 3B Quantitative Architecture Verification

**Repository:** `BTC_ML_System`  
**Branch:** `feat/phase-3b-strategy-evaluation`  
**Execution Engine:** `btc_ml_system.src.research.runner.ResearchSimulationRunner`  
**Scope:** Research Simulation Protocol Audit (Zero Broker Execution)

---

### 1. Executive Summary

Prior to conducting empirical strategy simulations for Phase 3B, a comprehensive quantitative audit of the research execution simulation protocol was conducted. Historical quantitative backtesting platforms frequently exhibit subtle execution and accounting artifacts—such as lookahead bias, unanchored stops, optimistic gap fills, simultaneous stop/target execution, and unrealistic transaction costs—which invalidate research conclusions.

This audit establishes the formal mechanics implemented in `ResearchSimulationRunner` to guarantee institutional-grade execution integrity across US equities and cryptocurrencies.

---

### 2. Audit Verification Matrix

| Audit Item | Implementation Mechanism | Validation Status |
| :--- | :--- | :--- |
| **Completed Candle Rule** | Signals evaluated strictly on bar close $t$ using historical OHLCV features up to $t$. | **VERIFIED** |
| **Next-Bar Open Execution** | Orders generated at close $t$ queue for execution at bar $t+1$ `open`. | **VERIFIED** |
| **Entry Fill Prices** | Simulated fill price incorporates asset-specific slippage: $P_{\text{fill}} = P_{\text{open}} \cdot (1 + \text{slip})$. | **VERIFIED** |
| **Stop Anchoring** | ATR stops and targets anchor to actual fill price: $\text{SL} = P_{\text{fill}} - \Delta_{\text{SL}}$, $\text{TP} = P_{\text{fill}} + \Delta_{\text{TP}}$. | **VERIFIED** |
| **Gap-Through Stops** | If open gaps adverse to stop ($P_{\text{open}} < \text{SL}$), fill occurs at adverse open $P_{\text{open}}$, not optimistic SL. | **VERIFIED** |
| **Intrabar Collision Rule** | When bar $[L, H]$ touches both SL and TP, conservative standard assumes adverse stop hit first (`STOP_LOSS_COLLISION`). | **VERIFIED** |
| **Trailing Stop Lookahead** | Active stop during bar $t$ references high up to bar $t-1$. High of bar $t$ updates stop only for bar $t+1$. | **VERIFIED** |
| **Market Session Filter** | Equities execute strictly during regular US hours (Mon–Fri, 14:00–21:00 UTC). Orders wait during closed sessions. | **VERIFIED** |
| **Continuous Crypto Trading** | Cryptocurrencies (`BTCUSDT`, `ETHUSDT`) execute 24/7/365 without session gating. | **VERIFIED** |
| **Asset Cost Structure** | Equities: 2 bps slip entry, 2 bps slip exit, 0 bps comm (4 bps RT). Crypto: 5 bps slip entry, 5 bps slip exit, 10 bps comm (20 bps RT). | **VERIFIED** |
| **Position Sizing & Risk** | Risk-based sizing capped at $0.5\%$ capital risk per trade, subject to portfolio capital constraints. | **VERIFIED** |

---

### 3. Detailed Audit Findings

#### 3.1 Next-Bar Open Execution and Fill Slippage
Orders are queued at bar close $t$ after indicators and signal filters are fully calculated on closed candles. At bar $t+1$, execution takes place at the bar's `open` price, augmented by asset-specific slippage:
$$P_{\text{fill, entry}} = P_{t+1, \text{open}} \cdot \left(1 + \frac{\text{slip\_bps}}{10000}\right)$$
For long positions, entry slippage penalizes the fill price upward. This eliminates same-bar execution bias and ensures realistic latency modeling.

#### 3.2 Dynamic Stop-Loss & Take-Profit Anchoring
In naive backtesters, stop-loss and take-profit levels are often computed from bar $t$ close ($P_{t, \text{close}} - 2 \cdot \text{ATR}$). However, if the market opens with a gap at $t+1$, referencing $P_{t, \text{close}}$ distorts the actual dollar risk and reward distance.
`ResearchSimulationRunner` measures the nominal risk distance $\Delta_{\text{SL}} = P_{t, \text{close}} - \text{SL}_{\text{nominal}}$ and anchors the active position limits to the actual entry fill price:
$$\text{SL}_{\text{active}} = P_{\text{fill}} - \Delta_{\text{SL}}$$
$$\text{TP}_{\text{active}} = P_{\text{fill}} + \Delta_{\text{TP}}$$
This guarantees that the exact intended ATR risk budget is preserved regardless of opening gap magnitude.

#### 3.3 Conservative Gap-Through-Stop Accounting
When severe overnight or inter-bar gaps occur such that the bar opens below the active stop-loss level ($P_{t, \text{open}} < \text{SL}_{\text{active}}$), filling at $\text{SL}_{\text{active}}$ represents an optimistic, non-executable assumption.
The runner implements conservative gap handling:
$$P_{\text{exit}} = \begin{cases} 
P_{t, \text{open}} & \text{if } P_{t, \text{open}} < \text{SL}_{\text{active}} \\ 
\text{SL}_{\text{active}} & \text{otherwise} 
\end{cases}$$
Following the fill, exit slippage is applied to $P_{\text{exit}}$, ensuring that gap-downs are fully and realistically penalized.

#### 3.4 Intrabar Collision Rule (`STOP_LOSS_COLLISION`)
When high-volatility bars feature large wicks where both the stop-loss threshold ($L_t \le \text{SL}$) and the take-profit threshold ($H_t \ge \text{TP}$) are breached within the same bar, tick-level order of arrival cannot be determined from OHLC data alone.
In compliance with quantitative research standards, the system applies the conservative adverse-move assumption:
- The trade is flagged with exit reason `STOP_LOSS_COLLISION`.
- The stop-loss is assumed to have been triggered first, preventing backtest result fabrication through optimistic target execution.

#### 3.5 Trailing Stop Non-Repainting & Lookahead Elimination
To prevent lookahead within bar $t$:
1. At the start of bar $t$, the active trailing stop is determined solely by the highest high observed up to bar $t-1$:
   $$\text{SL}_t = \max\left(\text{Initial\_SL}, H_{1:t-1}^{\max} \cdot (1 - \text{trail\_pct})\right)$$
2. Exits are evaluated against bar $t$ low ($L_t \le \text{SL}_t$).
3. Only if the position survives bar $t$ without being stopped out is $H_t$ incorporated into $H_{1:t}^{\max}$ to compute $\text{SL}_{t+1}$ for the subsequent bar.

#### 3.6 Equity Market Sessions vs. Continuous Crypto Trading
- **Equities (`AAPL`, `MSFT`, `NVDA`, `TSLA`, `AMZN`):** Trading is strictly gated to US Regular Market Hours (Monday–Friday, 14:00–21:00 UTC). Pending orders queued outside these hours cannot fill and remain pending until market open. Open positions cannot exit during weekend or off-hour candles.
- **Crypto (`BTCUSDT`, `ETHUSDT`):** Trading operates continuously 24 hours a day, 7 days a week, 365 days a year without session gating.

---

### 4. Audit Conclusion

The execution and accounting mechanisms in `ResearchSimulationRunner` satisfy all Phase 3B quantitative requirements. Execution timing, cost models, gap handling, collision rules, and session filters are mathematically robust and free from lookahead bias.

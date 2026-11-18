# BTC-ML SYSTEM V2 — PHASE 1 RISK POLICY REPORT
## Position Sizing Denominators, Aggregate Risk Ceilings & Execution Timing

**Date:** 2026-11-18  
**Author:** Quantitative Risk Engineer & Portfolio Architect  
**Status:** Validated & Configurable  

---

### 1. Executive Summary: Risk Denominator Resolution (RSK-001)

The Phase 0 forensic audit identified a critical ambiguity in position sizing risk calculations:
Does a `"0.5% per-trade risk"` limit apply to:
- **Interpretation A (`component_allocation`):** 0.5% of the capital allocated to that specific asset/sleeve (e.g., 25% of $10,000 = $2,500 sub-capital, yielding $12.50 risk)?
- **Interpretation B (`portfolio_equity`):** 0.5% of the total aggregate portfolio equity ($10,000 total capital, yielding $50.00 risk)?

To resolve this ambiguity without disrupting existing trading behavior or risking unintended leverage, Phase 1 introduces explicit configuration parameter `risk_denominator` with `"component_allocation"` set as the primary default.

---

### 2. Mathematical Formalization & Numerical Sizing Comparison

For a portfolio with initial equity $E = \$10,000$, target per-trade risk $\rho = 0.005$ (0.5%), and an asset with allocation weight $w_i$:

#### Mode A: `component_allocation` (Default)
$$\text{Allocated Sub-Capital } C_i = E \times w_i$$
$$\text{Dollar Risk } R_i = C_i \times \rho = E \times w_i \times \rho$$
$$\text{Position Quantity } Q_i = \frac{R_i}{|P_{\text{entry}} - P_{\text{stop}}|}$$

#### Mode B: `portfolio_equity`
$$\text{Dollar Risk } R_i = E \times \rho$$
$$\text{Position Quantity } Q_i = \frac{R_i}{|P_{\text{entry}} - P_{\text{stop}}|}$$

---

#### Worked Example: Sizing on a $10,000 Portfolio
Assuming entry price $P_{\text{entry}} = \$60,000$ and stop loss $P_{\text{stop}} = \$58,500$ ($\Delta P = \$1,500$):

| Metric | `component_allocation` (Default) | `portfolio_equity` (Alternative) | Ratio |
| :--- | :--- | :--- | :--- |
| **Component Weight ($w_i$)** | 25.0% (BTC) | 25.0% (BTC) | 1.0x |
| **Allocated Capital ($C_i$)** | $2,500.00 | $10,000.00 (Total) | 0.25x |
| **Dollar Risk ($R_i$)** | **$12.50** | **$50.00** | **0.25x** |
| **Stop Distance ($\Delta P$)** | $1,500.00 (2.5%) | $1,500.00 (2.5%) | 1.0x |
| **Calculated Position Qty** | **0.00833 BTC** | **0.03333 BTC** | 0.25x |
| **Total Position Notional Value** | **$500.00** | **$2,000.00** | 0.25x |
| **Position Leverage on Sleeve** | 20.0% of $2,500 sleeve | 80.0% of $2,500 sleeve | 4.0x |
| **Hard Position Cap Check ($2,500)** | PASSED ($500 < $2,500) | PASSED ($2,000 < $2,500) | — |

> [!NOTE]
> The `component_allocation` default preserves the multi-sleeve risk architecture of the V5 portfolio, ensuring that an individual asset class cannot consume disproportionate risk relative to its portfolio allocation weight.

---

### 3. Aggregate Portfolio Risk Controls & Circuit Breakers

The system enforces three hard layers of portfolio-level risk protection regardless of sizing mode:

1. **Maximum Aggregate Open Risk Ceiling (3.0%):**
   $$\sum_{j \in \text{Open Positions}} R_j \le 0.03 \times E_{\text{current}}$$
   On a $10,000 account, total open dollar risk cannot exceed $300.00. Any signal that would push aggregate open risk above $300 is blocked before submission.
2. **Daily Loss Limit Circuit Breaker (2.0%):**
   $$\text{Daily Drawdown } D_{\text{day}} = \frac{E_{\text{day\_start}} - E_{\text{current}}}{E_{\text{day\_start}}} \ge 0.02$$
   If intraday equity drops by 2.0% ($200 on $10,000), all further trade entries across all assets are frozen until the next calendar day.
3. **Maximum Drawdown Circuit Breaker (10.0%):**
   $$\text{Portfolio Drawdown } D_{\text{peak}} = \frac{E_{\text{peak}} - E_{\text{current}}}{E_{\text{peak}}} \ge 0.10$$
   If portfolio drawdown from peak equity reaches 10.0%, all new trade entries are permanently halted until manual review.

---

### 4. Backtest Execution Timing & Gap Slippage (BKT-001 & BKT-002)

To assess the impact of realistic broker fill timing on portfolio performance, a synchronized backtest was executed across all 7 assets comparing legacy `same_bar_close` against remediated `next_bar_open` (with opening gap slippage handling):

| Execution Model | Total Trades | Win Rate | Net Return (%) | Max Drawdown (%) | Profit Factor |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Legacy (`same_bar_close`)** | 661 | 53.25% | **+1.86%** | 4.33% | 1.08 |
| **Remediated (`next_bar_open`)** | 628 | 51.43% | **+0.11%** | 4.78% | 1.00 |
| **Variance / Bias Elimination** | -33 trades | -1.82% | **-1.75%** | +0.45% | -0.08 |

#### Key Risk Insights:
- The legacy `same_bar_close` model assumed orders filled at the exact closing price of the signal candle, introducing lookahead bias.
- The `next_bar_open` model executes orders on the subsequent bar open and incorporates overnight gap slippage on stop losses (if open < stop price).
- This removes artificial optimism, establishing an authentic baseline for strategy optimization in Phase 2.

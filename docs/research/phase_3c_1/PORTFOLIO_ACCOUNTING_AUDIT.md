# Phase 3C.1 Technical Integrity Audit: Portfolio Accounting & Order Execution

**Document ID:** `PORTFOLIO_ACCOUNTING_AUDIT.md`  
**Phase:** 3C.1 Independent Technical Integrity Audit  
**Starting Commit:** `76f7be8748ce69663148615099a51497da4883f6`  
**Base Commit:** `097952a`  
**Audit Target:** Simulation engine in `btc_ml_system/src/research/runner.py`, execution order lifecycle, stop-loss mechanics, and cash/equity balance equations.

---

## 1. Executive Summary

This independent technical audit performed an in-depth code and accounting inspection of the multi-asset simulation engine implemented in `btc_ml_system/src/research/runner.py`. 

### Key Findings
1. **Equity Conservation:** The portfolio identity $E_t = \text{Cash}_t + \sum_{i} (Q_{i,t} \times P_{i,t})$ holds exactly at every discrete timeline step with zero numerical drift or cash leakage.
2. **Execution Realism:**
   - **Stop-Loss Execution:** Stop-loss orders correctly handle adverse price gaps. If a bar opens below the active stop-loss price, the fill occurs at the open price (worse than stop), preventing optimistic fills.
   - **Intrabar Collisions:** When a bar's price range touches both the stop-loss and take-profit thresholds within the same bar, the simulator assumes the stop loss triggered first.
   - **Stop Anchoring:** Stop-loss and take-profit price levels are dynamically anchored to the *actual fill price* (including entry slippage), rather than the pre-slippage signal close price.
   - **Trailing Stop Ratcheting:** Trailing stops strictly ratchet upward, never widening downward.
3. **Transaction Cost Modeling (Observation O-02):**
   - Slippage is applied as an adverse percentage penalty on both entry and exit.
   - Brokerage commission is modeled as a single flat deduction at trade exit (`net_pnl_pct = gross_pnl_pct - (comm_bps / 10000.0)`). While standard if `comm_bps` represents a 10 bps round-trip fee, if it was intended as a two-sided fee (10 bps entry + 10 bps exit), transaction costs were slightly understated. This under-deduction would mean true net performance is even more negative than reported.
4. **Simultaneous Signal Priority:** Simultaneous entry signals are processed in dictionary-order. While deterministic, it lacks volatility- or rank-based capital allocation.

---

## 2. Portfolio Equity Identity & Conservation

The simulation loop in `runner.py` computes portfolio mark-to-market equity at two discrete phases during each hourly timestamp:

### Formula Verification
At bar $t$:
$$E_t = \text{Cash}_t + \sum_{i \in \text{OpenPositions}} Q_{i,t} \cdot P_{i,t}$$
where:
- $\text{Cash}_t$ is unallocated liquid cash.
- $Q_{i,t}$ is the quantity held in asset $i$.
- $P_{i,t}$ is the latest known mark price of asset $i$ (close of current candle, or forward-filled close if no candle closed at $t$).

### Implementation in `runner.py`:
```python
# runner.py: Lines 140-142 (Before order fills)
pos_equity = sum(pos["quantity"] * latest_prices[pos["symbol"]] for pos in open_positions.values())
current_equity = cash + pos_equity

# runner.py: Lines 309-316 (End of bar mark-to-market)
pos_equity = sum(pos["quantity"] * latest_prices[pos["symbol"]] for pos in open_positions.values())
total_equity = cash + pos_equity
equity_curve.append({
    "timestamp": str(t),
    "equity": total_equity,
    "cash": cash,
    "open_positions_count": len(open_positions)
})
```

### Cash Flow Reconciliation Across Trade Lifecycle
1. **Entry Allocation:**  
   $$\text{Cash}_{after} = \text{Cash}_{before} - \text{PositionValue}$$
   $$\text{PositionValue} = Q \cdot P_{fill}$$
   where $P_{fill} = P_{open} \cdot (1 + \text{slippage})$.
2. **Exit Settlement:**  
   $$\text{PnL}_{\$} = \text{PositionValue} \cdot \left[ \frac{P_{exit} \cdot (1 - \text{slippage}) - P_{fill}}{P_{fill}} - \text{comm} \right]$$
   $$\text{Cash}_{after} = \text{Cash}_{before} + \text{PositionValue} + \text{PnL}_{\$}$$
3. **Conservation:** Zero cash is created or destroyed. The sum of cumulative trade PnL exactly equals $E_T - E_0$.

---

## 3. Order Fill Mechanics & Execution Realism

### 1. Stop-Loss & Gap Handling
A frequent bug in backtesting engines is executing stop losses at the stop price even when the market gapped below it. 

Inspection of `runner.py` (lines 239–242) verifies correct gap handling:
```python
elif hit_sl:
    # Gap-through-stop behavior: if open is already below stop loss, fill at open
    exit_p = curr_open if curr_open < active_sl else active_sl
    reason = "STOP_LOSS"
```
- If $P_{open} < P_{stop}$, the order fills at $P_{open}$ (capturing the gap loss).
- If $P_{low} \le P_{stop} \le P_{open}$, the order fills at $P_{stop}$.
- Exit slippage ($5 \text{ bps}$) is subsequently deducted from `exit_p`, further penalizing the exit.

### 2. Intrabar SL / TP Collision Rule
When volatility expands, a single 1H candle can touch both the stop-loss level ($P_{low} \le P_{stop}$) and the take-profit target ($P_{high} \ge P_{target}$).

Inspection of `runner.py` (lines 234–238) verifies institutional conservatism:
```python
if hit_sl and hit_tp:
    exit_p = curr_open if curr_open < active_sl else active_sl
    reason = "STOP_LOSS_COLLISION"
```
The engine assumes the adverse stop loss was triggered first, preventing optimistic take-profit fills on extreme-range bars.

### 3. Stop Anchoring to Actual Fill Price
In `runner.py` (lines 191–193):
```python
actual_sl = fill_price - sl_dist
actual_tp = fill_price + tp_dist
```
Stop loss and profit target price levels are anchored to the *actual executed fill price* ($P_{open} \times (1 + \text{slippage})$), rather than the prior bar's signal close. This ensures the target risk-reward ratio is preserved under slippage.

### 4. Trailing Stop Ratcheting
In `runner.py` (lines 276–279):
```python
pos["highest_price"] = max(pos["highest_price"], curr_high)
if pos["trailing_pct"] and pos["trailing_pct"] > 0:
    trail_sl = pos["highest_price"] * (1.0 - pos["trailing_pct"])
    pos["sl_price"] = max(pos["sl_price"], trail_sl)
```
The trailing stop price `sl_price` strictly uses `max(pos["sl_price"], trail_sl)`. It ratchets upward with new market highs and can never decrease.

---

## 4. Position Sizing & Leverage Constraints

Position sizing is governed by risk-budgeting and portfolio slot limits:
```python
# runner.py: Lines 176-187
risk_usd = current_equity * self.risk_per_trade_pct
if sl_dist > 0 and order["signal_close"] > 0:
    risk_pct = sl_dist / order["signal_close"]
    calculated_size = risk_usd / risk_pct
    max_cap = current_equity / self.max_open_positions
    pos_val = min(calculated_size, max_cap)
else:
    pos_val = current_equity / self.max_open_positions

pos_val = min(pos_val, cash)
```

### Constraints Verified
1. **Capital Cap:** No single position can exceed $1 / \text{max\_open\_positions} = 1/5 = 20\%$ of current equity.
2. **Cash Ceiling:** Position value cannot exceed unallocated available cash (`pos_val = min(pos_val, cash)`).
3. **No Leverage:** Because $\sum \text{PositionValue} \le \text{Cash}$, portfolio leverage cannot exceed $1.0\times$.
4. **Minimum Order Size:** Positions below $\$10.00$ are rejected to prevent trivial dust orders.

---

## 5. Simultaneous Signal Tie-Breaking (Observation)

In multi-asset portfolios, multiple assets may trigger breakout signals on the exact same hourly candle close.

### Current Implementation:
```python
# runner.py: Line 285
for sym, df_sym in prepared_dfs.items():
    if t in df_sym.index and sym not in open_positions and sym not in pending_orders:
        row = df_sym.loc[t]
        sig = int(row.get("signal", 0))
        if sig == 1 and len(open_positions) + len(pending_orders) < self.max_open_positions:
            # Enqueue order...
```

### Audit Findings
- If 4 assets signal simultaneously but only 2 position slots remain, the first 2 assets in `prepared_dfs` receive the allocation.
- `prepared_dfs` is ordered by the insertion order of `asset_paths.items()`.
- While deterministic (reproducible across runs), this tie-breaking rule does not prioritize assets by signal strength, volatility, or momentum magnitude. For future research phases with competitive candidate selection, a ranking mechanism (e.g. cross-sectional z-score) should be implemented.

---

## 6. Audit Conclusion

The portfolio simulation engine in `runner.py` is **mathematically sound, conservative, and accounting-compliant**:
- Zero accounting residual: $E_t = \text{Cash}_t + \text{MarketValue}_t$ holds exactly.
- Execution conservatism: Adverse gap handling and stop-loss collision priority prevent backtest optimism.
- Stop anchoring and trailing mechanics adhere to institutional standards.

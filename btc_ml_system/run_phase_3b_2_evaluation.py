"""
Execution Script for BTC-ML System V2 Phase 3B.2 Research Revalidation.
Reruns all 9 pre-registered strategy variants across the 7 validated assets:
- Equities: AAPL, MSFT, NVDA, TSLA, AMZN (Authentic 1h data from Alpaca v2)
- Crypto: BTCUSDT (4h), ETHUSDT (1h)
Outputs complete JSON results to reports/phase_3b_2_raw_results.json and verifies DuckDB persistence.
"""

import os
import sys
import json
from pathlib import Path

# Ensure package on path
base_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(base_dir))

from btc_ml_system.src.research.evaluator import ResearchEvaluator


def main():
    print("=== STARTING PHASE 3B.2 DATA INTEGRITY REVALIDATION EVALUATION ===")
    auth_data_dir = base_dir.parent / "data" / "authentic_raw"
    evaluator = ResearchEvaluator(data_dir=auth_data_dir)

    results = evaluator.run_all_evaluations(log_to_registry=True)

    out_file = base_dir / "reports" / "phase_3b_2_raw_results.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)

    serializable_results = {
        "candidate_matrix_info": {
            "n_candidates": results["candidate_matrix_info"]["n_candidates"],
            "t_steps": results["candidate_matrix_info"]["t_steps"],
            "is_sufficient_for_pbo": results["candidate_matrix_info"]["is_sufficient_for_pbo"],
            "status": results["candidate_matrix_info"]["status"],
            "candidate_ids": results["candidate_matrix_info"].get("candidate_ids", []),
            "reconciliation_status": results["candidate_matrix_info"].get("reconciliation_status"),
            "max_reconciliation_error": results["candidate_matrix_info"].get("max_reconciliation_error"),
            "zero_stats": results["candidate_matrix_info"].get("zero_stats", {})
        },
        "pbo_result": results["pbo_result"],
        "dsr_result": results["dsr_result"],
        "top_candidate": results["top_candidate"],
        "registered_experiments": results["registered_experiments"],
        "benchmarks": results["benchmarks"],
        "strategy_summary": {},
        "asset_level_summary": results["asset_level_results"]
    }

    for strat_id, s_data in results["strategy_results"].items():
        serializable_results["strategy_summary"][strat_id] = {
            "strategy_id": strat_id,
            "strategy_name": s_data["metadata"].strategy_name,
            "family": s_data["metadata"].family.value,
            "portfolio_metrics": s_data["portfolio_metrics"],
            "regimes": s_data["regimes"],
            "calendar": s_data["calendar"],
            "robustness": s_data["robustness"],
            "experiment_id": s_data["experiment_id"]
        }

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(serializable_results, f, indent=2, default=str)

    print(f"Results successfully saved to {out_file}")
    print(f"Total strategies evaluated: {len(results['strategy_results'])}")
    print(f"Top strategy: {results['top_candidate']}")
    print(f"PBO status: {results['pbo_result'].get('status', 'COMPLETED')} | PBO: {results['pbo_result'].get('pbo')}")
    print(f"DSR: {results['dsr_result'].get('deflated_sharpe_ratio') if results['dsr_result'] else 'N/A'}")
    print(f"Matrix Reconciliation: {results['candidate_matrix_info'].get('reconciliation_status')} (max err: {results['candidate_matrix_info'].get('max_reconciliation_error')})")
    print("=== PHASE 3B.2 EVALUATION COMPLETE ===")


if __name__ == "__main__":
    main()

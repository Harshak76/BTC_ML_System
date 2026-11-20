"""
Execution Script for BTC-ML System V2 Phase 3B Quantitative Strategy Evaluation.
Runs all 9 pre-registered strategy variants across 7 assets:
- Equities: AAPL, MSFT, NVDA, TSLA, AMZN
- Crypto: BTCUSDT, ETHUSDT
Outputs complete JSON results for report authoring and verifies DuckDB persistence.
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
    print("=== STARTING PHASE 3B COMPREHENSIVE STRATEGY EVALUATION ===")
    evaluator = ResearchEvaluator()

    results = evaluator.run_all_evaluations(log_to_registry=True)

    out_file = base_dir / "reports" / "phase_3b_raw_results.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)

    # Convert non-serializable objects (like numpy arrays / metadata)
    serializable_results = {
        "candidate_matrix_info": {
            "n_candidates": results["candidate_matrix_info"]["n_candidates"],
            "t_steps": results["candidate_matrix_info"]["t_steps"],
            "is_sufficient_for_pbo": results["candidate_matrix_info"]["is_sufficient_for_pbo"],
            "status": results["candidate_matrix_info"]["status"],
            "candidate_ids": results["candidate_matrix_info"].get("candidate_ids", [])
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
    print("=== PHASE 3B EVALUATION COMPLETE ===")


if __name__ == "__main__":
    main()

"""
Experiment Tracking & Reproducibility Registry for BTC-ML System V2.
Features:
- Unique UUID generation for each quantitative validation run
- Full parameter, version, dataset, seed, and execution-cost logging
- Persistent serialization to JSON registry and DuckDB
- Resumability: Checks if an experiment configuration was already evaluated
"""

import os
import json
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
import duckdb

logger = logging.getLogger("btc_ml_system.validation.experiment_tracker")


class ExperimentTracker:
    """
    Tracks and registers all quantitative validation experiments for auditability and reproducibility.
    """

    def __init__(self, registry_dir: Optional[str] = None, db_path: Optional[str] = None):
        base_dir = Path(__file__).resolve().parent.parent.parent
        self.registry_dir = Path(registry_dir or (base_dir / "experiments"))
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path or str(base_dir / "data" / "btc_ml_system.duckdb")
        self._init_duckdb_schema()

    def _init_duckdb_schema(self):
        """Initializes experiment_registry table in DuckDB if writable."""
        try:
            con = duckdb.connect(self.db_path)
            con.execute("""
                CREATE TABLE IF NOT EXISTS experiment_registry (
                    experiment_id VARCHAR PRIMARY KEY,
                    created_at TIMESTAMP,
                    strategy_name VARCHAR,
                    strategy_version VARCHAR,
                    asset VARCHAR,
                    timeframe VARCHAR,
                    candidate_configs_count INTEGER,
                    completed_trials INTEGER,
                    random_seed INTEGER,
                    sharpe_ratio DOUBLE,
                    total_return_pct DOUBLE,
                    max_drawdown_pct DOUBLE,
                    pbo DOUBLE,
                    dsr DOUBLE,
                    gate_status VARCHAR,
                    config_json VARCHAR,
                    results_json VARCHAR
                );
            """)
            con.close()
        except Exception as e:
            logger.debug(f"DuckDB experiment table init note (read-only or locked): {e}")

    def create_experiment_id(self) -> str:
        """Generates a unique experiment ID."""
        return f"EXP-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"

    def log_experiment(
        self,
        experiment_id: str,
        strategy_name: str,
        strategy_version: str,
        asset: str,
        timeframe: str,
        parameter_config: Dict[str, Any],
        dataset_info: Dict[str, Any],
        validation_results: Dict[str, Any],
        random_seed: int = 42,
        cost_assumptions: Optional[Dict[str, Any]] = None,
        candidate_count: int = 1,
        completed_trials: int = 1
    ) -> Dict[str, Any]:
        """
        Persists full experiment record to JSON registry and DuckDB.
        """
        record = {
            "experiment_id": experiment_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "strategy_name": strategy_name,
            "strategy_version": strategy_version,
            "asset": asset,
            "timeframe": timeframe,
            "parameter_config": parameter_config,
            "dataset_info": dataset_info,
            "cost_assumptions": cost_assumptions or {"slippage_bps": 5, "commission_bps": 10},
            "candidate_count": candidate_count,
            "completed_trials": completed_trials,
            "random_seed": random_seed,
            "validation_results": validation_results
        }

        # Save to JSON file
        json_path = self.registry_dir / f"{experiment_id}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, default=str)

        # Attempt DuckDB insert
        try:
            metrics = validation_results.get("portfolio_metrics", validation_results.get("metrics", {}))
            pbo_val = validation_results.get("pbo_cscv", {}).get("pbo", None)
            dsr_val = validation_results.get("deflated_sharpe", {}).get("deflated_sharpe_ratio", None)
            gate_stat = validation_results.get("validation_gate", {}).get("overall_status", "PENDING")

            con = duckdb.connect(self.db_path)
            con.execute("""
                INSERT OR REPLACE INTO experiment_registry VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, [
                experiment_id,
                datetime.now(timezone.utc),
                strategy_name,
                strategy_version,
                asset,
                timeframe,
                candidate_count,
                completed_trials,
                random_seed,
                metrics.get("sharpe_ratio"),
                metrics.get("total_return_pct"),
                metrics.get("max_drawdown_pct"),
                pbo_val,
                dsr_val,
                gate_stat,
                json.dumps(parameter_config, default=str),
                json.dumps(validation_results, default=str)
            ])
            con.close()
        except Exception as e:
            logger.debug(f"DuckDB insert note: {e}")

        logger.info(f"Logged experiment {experiment_id} for {strategy_name} ({asset}) to {json_path}")
        return record

    def is_experiment_completed(self, experiment_id: str) -> bool:
        """Checks if an experiment result file exists."""
        json_path = self.registry_dir / f"{experiment_id}.json"
        return json_path.exists()

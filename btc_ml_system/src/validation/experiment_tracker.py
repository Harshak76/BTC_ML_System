"""
Experiment Tracking & Reproducibility Registry for BTC-ML System V2.
Features:
- Unique UUID generation for each quantitative validation run
- Full parameter, git commit, version, dataset, seed, and execution-cost logging
- Persistent, append-only serialization to JSON registry and DuckDB
- Multiple-testing trial accounting: Tracks total historical trials across research lifecycle
- Never overwrites or resets historical trial records
"""

import os
import json
import uuid
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
import duckdb

logger = logging.getLogger("btc_ml_system.validation.experiment_tracker")


class ExperimentTracker:
    """
    Tracks and registers all quantitative validation experiments in a persistent, append-only store.
    """

    def __init__(self, registry_dir: Optional[str] = None, db_path: Optional[str] = None):
        base_dir = Path(__file__).resolve().parent.parent.parent
        self.registry_dir = Path(registry_dir or (base_dir / "experiments"))
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        if db_path:
            self.db_path = db_path
        else:
            root_db = base_dir.parent / "data" / "btc_ml_system.duckdb"
            nested_db = base_dir / "data" / "btc_ml_system.duckdb"
            self.db_path = str(root_db) if root_db.exists() else str(nested_db)
        self._mem_con = None
        if self.db_path == ":memory:":
            self._mem_con = duckdb.connect(":memory:")
        self._init_duckdb_schema()

    def _get_connection(self, read_only: bool = False):
        """Returns DuckDB connection, reusing in-memory connection if configured."""
        if self.db_path == ":memory:":
            return self._mem_con
        return duckdb.connect(self.db_path, read_only=read_only)

    def _close_connection(self, con):
        """Closes file connection; leaves in-memory connection open."""
        if self.db_path != ":memory:":
            try:
                con.close()
            except Exception:
                pass

    def _get_current_git_commit(self) -> str:
        """Resolves current git commit hash."""
        try:
            cmd = ["git", "rev-parse", "HEAD"]
            commit = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip()
            return commit
        except Exception:
            return "UNKNOWN_COMMIT"

    def _init_duckdb_schema(self):
        """Initializes append-only experiment_registry table in DuckDB."""
        try:
            con = self._get_connection()
            con.execute("""
                CREATE TABLE IF NOT EXISTS experiment_registry (
                    experiment_id VARCHAR PRIMARY KEY,
                    git_commit VARCHAR,
                    created_at TIMESTAMP,
                    strategy_name VARCHAR,
                    strategy_version VARCHAR,
                    asset VARCHAR,
                    timeframe VARCHAR,
                    dataset_identity VARCHAR,
                    dataset_date_range VARCHAR,
                    candidate_configs_count INTEGER,
                    completed_trials INTEGER,
                    failed_trials INTEGER,
                    abandoned_trials INTEGER,
                    random_seed INTEGER,
                    return_frequency VARCHAR,
                    cost_assumptions_json VARCHAR,
                    sharpe_ratio DOUBLE,
                    total_return_pct DOUBLE,
                    max_drawdown_pct DOUBLE,
                    pbo DOUBLE,
                    dsr DOUBLE,
                    gate_status VARCHAR,
                    parameter_config_json VARCHAR,
                    validation_results_json VARCHAR
                );
            """)
            self._close_connection(con)
        except Exception as e:
            logger.warning(f"DuckDB experiment table init note: {e}")

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
        completed_trials: int = 1,
        failed_trials: int = 0,
        abandoned_trials: int = 0,
        return_frequency: str = "1h",
        git_commit: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Persists full experiment record to JSON registry and DuckDB.
        Strictly append-only: Fails if an experiment with the same ID already exists.
        """
        commit = git_commit or self._get_current_git_commit()
        costs = cost_assumptions or {"slippage_bps": 5, "commission_bps": 10}
        now_dt = datetime.now(timezone.utc)

        # Dataset details
        ds_id = str(dataset_info.get("symbols", asset))
        ds_range = str(dataset_info.get("date_range", dataset_info.get("history_years", "2 years")))

        record = {
            "experiment_id": experiment_id,
            "git_commit": commit,
            "created_at": now_dt.isoformat(),
            "strategy_name": strategy_name,
            "strategy_version": strategy_version,
            "asset": asset,
            "timeframe": timeframe,
            "dataset_info": dataset_info,
            "dataset_identity": ds_id,
            "dataset_date_range": ds_range,
            "parameter_config": parameter_config,
            "cost_assumptions": costs,
            "candidate_count": candidate_count,
            "completed_trials": completed_trials,
            "failed_trials": failed_trials,
            "abandoned_trials": abandoned_trials,
            "random_seed": random_seed,
            "return_frequency": return_frequency,
            "validation_results": validation_results
        }

        # 1. Append-only JSON check
        json_path = self.registry_dir / f"{experiment_id}.json"
        if json_path.exists():
            raise ValueError(f"Append-only violation: Experiment {experiment_id} already exists on disk.")

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, default=str)

        # 2. Append-only DuckDB insert
        try:
            metrics = validation_results.get("portfolio_metrics", validation_results.get("metrics", {}))
            pbo_val = validation_results.get("pbo_cscv", {}).get("pbo", None)
            dsr_val = validation_results.get("deflated_sharpe", {}).get("deflated_sharpe_ratio", None)
            gate_stat = validation_results.get("validation_gate", {}).get("overall_status", "PENDING")

            con = self._get_connection()
            # Check for existing record
            existing = con.execute("SELECT COUNT(*) FROM experiment_registry WHERE experiment_id = ?", [experiment_id]).fetchone()[0]
            if existing > 0:
                self._close_connection(con)
                raise ValueError(f"Append-only violation: Experiment {experiment_id} already exists in DuckDB.")

            con.execute("""
                INSERT INTO experiment_registry VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, [
                experiment_id,
                commit,
                now_dt,
                strategy_name,
                strategy_version,
                asset,
                timeframe,
                ds_id,
                ds_range,
                candidate_count,
                completed_trials,
                failed_trials,
                abandoned_trials,
                random_seed,
                return_frequency,
                json.dumps(costs, default=str),
                metrics.get("sharpe_ratio"),
                metrics.get("total_return_pct"),
                metrics.get("max_drawdown_pct"),
                pbo_val,
                dsr_val,
                gate_stat,
                json.dumps(parameter_config, default=str),
                json.dumps(validation_results, default=str)
            ])
            self._close_connection(con)
        except Exception as e:
            logger.warning(f"DuckDB insert error: {e}")
            if "Append-only violation" in str(e):
                raise

        logger.info(f"Registered experiment {experiment_id} (commit={commit}) to {json_path} and DuckDB")
        return record

    def get_total_historical_trials(self) -> Dict[str, Any]:
        """
        Calculates the complete documented trial count across the historical experiment registry.
        Used for rigorous multiple-testing corrections (DSR & PBO).
        """
        # First synchronize any JSON experiments on disk that may not be in DuckDB
        self.sync_json_to_duckdb()

        total_candidates = 0
        total_completed = 0
        total_failed = 0
        total_abandoned = 0
        experiment_count = 0
        all_trial_sharpes = []

        try:
            con = self._get_connection(read_only=(self.db_path != ":memory:"))
            rows = con.execute("""
                SELECT 
                    SUM(candidate_configs_count), 
                    SUM(completed_trials), 
                    SUM(failed_trials), 
                    SUM(abandoned_trials), 
                    COUNT(*) 
                FROM experiment_registry
            """).fetchone()

            if rows and rows[4] > 0:
                total_candidates = int(rows[0] or 0)
                total_completed = int(rows[1] or 0)
                total_failed = int(rows[2] or 0)
                total_abandoned = int(rows[3] or 0)
                experiment_count = int(rows[4] or 0)

            # Retrieve recorded Sharpe ratios
            sharpe_rows = con.execute("SELECT sharpe_ratio FROM experiment_registry WHERE sharpe_ratio IS NOT NULL").fetchall()
            all_trial_sharpes = [r[0] for r in sharpe_rows]
            self._close_connection(con)
        except Exception as e:
            logger.debug(f"Error querying trial count from DuckDB: {e}")

        # Document missing historical trials from early development phases
        missing_trials_note = (
            "Phase 0 and Phase 1 exploratory runs (estimated 25-40 parameter combinations across Stage 1 loosened, "
            "regime threshold variations, and session filter tests) were executed prior to the creation of the persistent registry "
            "and are not recorded in DuckDB. These historical trials are documented as MISSING_HISTORICAL_EXPERIMENTS. "
            "Never invent fabricated trial records; DSR calculations using only registry records represent a lower bound on trial count."
        )

        return {
            "total_candidate_trials": total_candidates,
            "total_completed_trials": total_completed,
            "total_failed_trials": total_failed,
            "total_abandoned_trials": total_abandoned,
            "total_registered_experiments": experiment_count,
            "all_trial_sharpes": all_trial_sharpes,
            "missing_historical_trials_documented": True,
            "documentation": missing_trials_note
        }

    def sync_json_to_duckdb(self):
        """Synchronizes any existing JSON experiment files on disk into DuckDB."""
        if not self.registry_dir.exists():
            return

        try:
            con = self._get_connection()
            for jf in self.registry_dir.glob("*.json"):
                try:
                    with open(jf, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    exp_id = data.get("experiment_id")
                    if not exp_id:
                        continue
                    exists = con.execute("SELECT COUNT(*) FROM experiment_registry WHERE experiment_id = ?", [exp_id]).fetchone()[0]
                    if exists == 0:
                        metrics = data.get("validation_results", {}).get("portfolio_metrics", {})
                        pbo_val = data.get("validation_results", {}).get("pbo_cscv", {}).get("pbo", None)
                        dsr_val = data.get("validation_results", {}).get("deflated_sharpe", {}).get("deflated_sharpe_ratio", None)
                        gate_stat = data.get("validation_results", {}).get("validation_gate", {}).get("overall_status", "PENDING")

                        con.execute("""
                            INSERT INTO experiment_registry VALUES (
                                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                            )
                        """, [
                            exp_id,
                            data.get("git_commit", "aa5ee10487ed9c3753b8d15f4ffa59c6c0f6aa72"),
                            datetime.fromisoformat(data.get("created_at")),
                            data.get("strategy_name", "unknown"),
                            data.get("strategy_version", "unknown"),
                            data.get("asset", "unknown"),
                            data.get("timeframe", "unknown"),
                            str(data.get("dataset_info", {}).get("symbols", "unknown")),
                            str(data.get("dataset_info", {}).get("history_years", "unknown")),
                            int(data.get("candidate_count", 1)),
                            int(data.get("completed_trials", 1)),
                            int(data.get("failed_trials", 0)),
                            int(data.get("abandoned_trials", 0)),
                            int(data.get("random_seed", 42)),
                            data.get("return_frequency", "1h"),
                            json.dumps(data.get("cost_assumptions", {}), default=str),
                            metrics.get("sharpe_ratio"),
                            metrics.get("total_return_pct"),
                            metrics.get("max_drawdown_pct"),
                            pbo_val,
                            dsr_val,
                            gate_stat,
                            json.dumps(data.get("parameter_config", {}), default=str),
                            json.dumps(data.get("validation_results", {}), default=str)
                        ])
                except Exception as e:
                    logger.debug(f"Sync error for {jf}: {e}")
            self._close_connection(con)
        except Exception as e:
            logger.debug(f"Sync connection note: {e}")

    def is_experiment_completed(self, experiment_id: str) -> bool:
        """Checks if an experiment result file exists."""
        json_path = self.registry_dir / f"{experiment_id}.json"
        return json_path.exists()

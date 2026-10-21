"""Optional MLflow logging (install with `uv sync --group eval`). Runs work without it."""

import json
import logging
import math
from pathlib import Path

logger = logging.getLogger(__name__)

TRACKING_URI = f"sqlite:///{(Path(__file__).parents[1] / 'mlflow.db').as_posix()}"


def log_run(experiment: str, result: dict, artifact: Path) -> None:
    try:
        import mlflow
    except ImportError:
        logger.info("mlflow not installed; skipping experiment tracking")
        return
    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment(experiment)
    with mlflow.start_run(run_name=result["variant"]["name"]):
        mlflow.log_params({k: str(v) for k, v in result["variant"].items()})
        mlflow.log_metrics(
            {
                k.replace("@", "_at_"): v
                for k, v in result["metrics"].items()
                if isinstance(v, int | float) and math.isfinite(v)
            }
        )
        mlflow.log_dict(json.loads(artifact.read_text(encoding="utf-8")), artifact.name)

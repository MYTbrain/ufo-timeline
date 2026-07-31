"""UFO timeline parsing and mapping pipeline."""

__all__ = ["AppConfig", "load_config", "run_pipeline"]


def __getattr__(name):
    if name in {"AppConfig", "load_config"}:
        from .config import AppConfig, load_config

        return {"AppConfig": AppConfig, "load_config": load_config}[name]
    if name == "run_pipeline":
        from .pipeline import run_pipeline

        return run_pipeline
    raise AttributeError(f"module 'parser' has no attribute {name!r}")

"""FastAPI app serving the local map UI and generated datasets."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from parser import load_config


def create_app() -> FastAPI:
    config_path = os.environ.get("UFO_TIMELINE_CONFIG", "config.example.yaml")
    config = load_config(config_path)

    project_root = Path(__file__).resolve().parent.parent
    static_dir = project_root / "webapp" / "static"
    data_dir = config.map_events_path.parent

    app = FastAPI(title="UFO Timeline Map Tool")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    app.mount("/data", StaticFiles(directory=data_dir), name="data")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/app-config")
    def app_config() -> JSONResponse:
        return JSONResponse(
            {
                "tileUrl": config.web.tile_url,
                "tileAttribution": config.web.tile_attribution,
                "initialCenter": config.web.initial_center,
                "initialZoom": config.web.initial_zoom,
                "mapEventsUrl": "/data/map_events.json",
                "normalizedEventsUrl": "/data/normalized_events.json",
                "unresolvedLocationsUrl": "/data/reports/unresolved_locations.json",
            }
        )

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    return app

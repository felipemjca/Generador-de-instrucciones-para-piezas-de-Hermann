from __future__ import annotations

import os
from pathlib import Path

from flask import Flask

from . import db


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("INSTRUCCIONES_SECRET_KEY", "local-only-change-me"),
        DATABASE=str(Path(app.instance_path) / "app.sqlite3"),
        UPLOAD_FOLDER=str(Path(app.instance_path) / "uploads"),
        OUTPUT_FOLDER=str(Path(app.instance_path) / "outputs"),
        TEMPLATE_XLSX=str(
            Path(app.root_path) / "excel_templates" / "plantilla_definitiva.xlsx"
        ),
        MAX_CONTENT_LENGTH=50 * 1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["OUTPUT_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)

    from .routes import bp

    app.register_blueprint(bp)
    return app

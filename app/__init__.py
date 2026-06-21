from __future__ import annotations

from pathlib import Path

from flask import Flask

from . import db
from .routes import bp


def format_metric(value, unit=""):
    if value is None:
        return "—"
    if unit == "₽":
        formatted = f"{value:,.0f}".replace(",", " ")
        return f"{formatted} ₽"
    if unit == "%":
        return f"{value:.1f}%"
    if float(value).is_integer():
        return f"{int(value)} {unit}".strip()
    return f"{value:,.2f}".replace(",", " ").replace(".", ",") + (f" {unit}" if unit else "")


def create_app():
    base_dir = Path(__file__).resolve().parent.parent
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY="business-analytics-local-secret",
        DATABASE=str(base_dir / "instance" / "business_analytics.sqlite3"),
        DASHBOARD_UPLOAD_FOLDER=str(base_dir / "app" / "uploads" / "dashboards"),
    )

    Path(app.config["DASHBOARD_UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    with app.app_context():
        db.init_db()

    app.register_blueprint(bp)

    @app.context_processor
    def inject_helpers():
        return {"format_metric": format_metric}

    @app.template_filter("dt")
    def format_dt(value):
        if not value:
            return "—"
        return value.replace("T", " ")

    return app

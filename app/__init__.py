from __future__ import annotations

import os
from pathlib import Path

from flask import Flask

from . import db
from .routes import bp


def format_metric(value, unit="", metric_code=None, for_plan=False):
    if value is None:
        return "—"
    if unit == "₽":
        formatted = f"{value:,.0f}".replace(",", " ")
        return f"{formatted} ₽"
    if unit == "%":
        return f"{value:.1f}%"
    if metric_code == "turnover_orders":
        if float(value).is_integer():
            base_value = f"{int(value)}"
        else:
            base_value = f"{value:,.2f}".replace(",", " ").replace(".", ",")
        return base_value if for_plan else f"{base_value} дней"
    if float(value).is_integer():
        return f"{int(value)} {unit}".strip()
    return f"{value:,.2f}".replace(",", " ").replace(".", ",") + (f" {unit}" if unit else "")


def create_app():
    base_dir = Path(__file__).resolve().parent.parent
    data_dir = Path(os.environ.get("BUSINESS_ANALYTICS_DATA_DIR", str(base_dir / "instance")))
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY="business-analytics-local-secret",
        DATABASE=str(data_dir / "business_analytics.sqlite3"),
        DASHBOARD_UPLOAD_FOLDER=str(base_dir / "app" / "uploads" / "dashboards"),
        REPORT_RETENTION_DAYS={
            "daily": 62,
            "weekly": 90,
            "monthly": 180,
        },
        RETENTION_POLICY_START_DATE="2026-06-26",
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

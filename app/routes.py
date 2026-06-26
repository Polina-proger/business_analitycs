from __future__ import annotations

import json
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from functools import wraps
from io import BytesIO
from itertools import zip_longest
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from .catalog import (
    PERIOD_LABELS,
    all_reports,
    all_report_keys,
    build_period_label,
    default_period_bounds,
    get_report_definition,
    get_zone_definition,
    grouped_reports,
    metric_lookup,
)
from .db import get_db
from .excel import create_report_template, parse_report_workbook


bp = Blueprint("main", __name__)
PASSWORD_HASH_METHOD = "pbkdf2:sha256"
LAST_RETENTION_RUN: str | None = None
DASHBOARD_FILTERS_SESSION_KEY = "dashboard_filters"


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("main.login"))
        return view(**kwargs)

    return wrapped_view


def normalize_number(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = (
        str(value)
        .strip()
        .replace(" ", "")
        .replace("\xa0", "")
        .replace(",", ".")
        .replace("%", "")
        .replace("₽", "")
    )
    if text in {"", "-", "—"}:
        return None
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"Некорректное число: {value}") from exc


def build_summary_metrics_payload(report_key: str, source: dict | None = None, imported_rows: list[dict] | None = None) -> list[dict]:
    definition = get_report_definition(report_key)
    imported_map = {row["code"]: row for row in (imported_rows or [])}
    payload = []
    for metric in definition["metrics"]:
        source_row = imported_map.get(metric["code"], {})
        plan_value = source_row.get("plan")
        fact_value = source_row.get("fact")
        comment_value = source_row.get("comment")
        if source is not None:
            plan_value = source.get(f"plan_{metric['code']}", plan_value)
            fact_value = source.get(f"fact_{metric['code']}", fact_value)
            comment_value = source.get(f"comment_{metric['code']}", comment_value)
        payload.append(
            {
                "code": metric["code"],
                "label": metric["label"],
                "unit": metric["unit"],
                "has_plan": metric["has_plan"],
                "direction": metric["direction"],
                "plan": normalize_number(plan_value) if metric["has_plan"] else None,
                "fact": normalize_number(fact_value),
                "comment": str(comment_value).strip() if comment_value else "",
            }
        )
    return payload


def build_article_entries_payload(report_key: str, source: dict | None = None, imported_rows: list[dict] | None = None) -> list[dict]:
    lookup = metric_lookup(report_key)
    entries = []

    if imported_rows is not None:
        iterable = [
            (
                row.get("article_name"),
                row.get("metric_code"),
                row.get("plan"),
                row.get("fact"),
                row.get("comment"),
            )
            for row in imported_rows
        ]
    else:
        iterable = zip_longest(
            source.getlist("article_name[]"),
            source.getlist("article_metric_code[]"),
            source.getlist("article_plan[]"),
            source.getlist("article_fact[]"),
            source.getlist("article_comment[]"),
            fillvalue="",
        )

    for index, (article_name, metric_code, plan_value, fact_value, comment_value) in enumerate(iterable, start=1):
        article_name = str(article_name or "").strip()
        metric_code = str(metric_code or "").strip()
        comment_text = str(comment_value or "").strip()
        has_any_input = any(
            [
                article_name,
                metric_code,
                str(plan_value or "").strip(),
                str(fact_value or "").strip(),
                comment_text,
            ]
        )
        if not has_any_input:
            continue
        # Incomplete article rows are ignored so a partially filled breakdown
        # never blocks saving the main report or Excel import.
        if not article_name or metric_code not in lookup:
            continue
        has_payload = any(
            [
                str(plan_value or "").strip(),
                str(fact_value or "").strip(),
                comment_text,
            ]
        )
        if not has_payload:
            continue
        entries.append(
            {
                "article_name": article_name,
                "metric_code": metric_code,
                "metric_label": lookup[metric_code]["label"],
                "unit": lookup[metric_code]["unit"],
                "has_plan": lookup[metric_code]["has_plan"],
                "direction": lookup[metric_code]["direction"],
                "plan": normalize_number(plan_value) if lookup[metric_code]["has_plan"] else None,
                "fact": normalize_number(fact_value),
                "comment": comment_text,
            }
        )
    return entries


def status_from_achievement(value):
    if value is None:
        return "neutral"
    if value >= 100:
        return "good"
    if value >= 85:
        return "warn"
    return "danger"


def enrich_metrics(metrics: list[dict]) -> list[dict]:
    enriched = []
    for item in metrics:
        plan = item.get("plan")
        fact = item.get("fact")
        direction = item.get("direction", "up")
        achievement = None
        delta = None
        if plan not in (None, 0) and fact is not None:
            achievement = (fact / plan) * 100 if direction == "up" else (plan / fact) * 100 if fact else None
            delta = fact - plan
        enriched.append(
            {
                **item,
                "achievement": achievement,
                "delta": delta,
                "status": status_from_achievement(achievement),
            }
        )
    return enriched


def unpack_report_payload(report_key: str, data_json: str) -> tuple[list[dict], list[dict]]:
    raw = json.loads(data_json)
    if isinstance(raw, list):
        return raw, []
    summary_metrics = raw.get("summary_metrics", [])
    article_entries = raw.get("article_entries", [])
    lookup = metric_lookup(report_key)
    normalized_entries = []
    for entry in article_entries:
        metric_code = entry.get("metric_code")
        metric = lookup.get(metric_code, {})
        normalized_entries.append(
            {
                "article_name": entry.get("article_name", ""),
                "metric_code": metric_code,
                "metric_label": entry.get("metric_label") or metric.get("label", metric_code),
                "unit": entry.get("unit") or metric.get("unit", ""),
                "has_plan": entry.get("has_plan", metric.get("has_plan", False)),
                "direction": entry.get("direction", metric.get("direction", "up")),
                "plan": entry.get("plan"),
                "fact": entry.get("fact"),
                "comment": entry.get("comment", ""),
            }
        )
    return summary_metrics, normalized_entries


def group_article_entries(entries: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for entry in enrich_metrics(entries):
        grouped[entry["article_name"]].append(entry)
    return [{"article_name": name, "entries": values} for name, values in grouped.items()]


def parse_report_dates(period_type: str, report_date_raw: str, start_raw: str | None, end_raw: str | None):
    anchor = datetime.strptime(report_date_raw, "%Y-%m-%d").date()
    if start_raw:
        start = datetime.strptime(start_raw, "%Y-%m-%d").date()
    else:
        start, _ = default_period_bounds(period_type, anchor)
    if end_raw:
        end = datetime.strptime(end_raw, "%Y-%m-%d").date()
    else:
        _, end = default_period_bounds(period_type, anchor)
    return anchor, start, end


def store_report(
    report_key: str,
    period_type: str,
    report_date_raw: str,
    start_raw: str | None,
    end_raw: str | None,
    summary_metrics: list[dict],
    article_entries: list[dict],
    report_id: int | None = None,
) -> int:
    anchor, start, end = parse_report_dates(period_type, report_date_raw, start_raw, end_raw)
    definition = get_report_definition(report_key)
    db = get_db()
    now = datetime.now().isoformat(timespec="seconds")
    payload = json.dumps(
        {"summary_metrics": summary_metrics, "article_entries": article_entries},
        ensure_ascii=False,
    )
    period_label = build_period_label(period_type, start, end)
    if report_id is None:
        cursor = db.execute(
            """
            INSERT INTO reports (
                report_key, report_title, period_type, period_label, report_date,
                period_start, period_end, submitted_by, submitted_by_name,
                submitted_by_position, data_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_key,
                definition["title"],
                period_type,
                period_label,
                anchor.isoformat(),
                start.isoformat(),
                end.isoformat(),
                g.user["id"],
                g.user["full_name"],
                g.user_scope["zone_label"],
                payload,
                now,
                now,
            ),
        )
        db.commit()
        return cursor.lastrowid
    db.execute(
        """
        UPDATE reports
        SET period_type = ?, period_label = ?, report_date = ?, period_start = ?, period_end = ?,
            data_json = ?, updated_at = ?, submitted_by_name = ?, submitted_by_position = ?
        WHERE id = ?
        """,
        (
            period_type,
            period_label,
            anchor.isoformat(),
            start.isoformat(),
            end.isoformat(),
            payload,
            now,
            g.user["full_name"],
            g.user_scope["zone_label"],
            report_id,
        ),
    )
    db.commit()
    return report_id


def sync_article_catalog(article_entries: list[dict]) -> None:
    if not article_entries:
        return
    db = get_db()
    now = datetime.now().isoformat(timespec="seconds")
    for entry in article_entries:
        article_name = entry["article_name"].strip()
        if not article_name:
            continue
        db.execute(
            """
            INSERT OR IGNORE INTO article_catalog (article_name, created_at)
            VALUES (?, ?)
            """,
            (article_name, now),
        )
    db.commit()


def article_catalog_names(limit: int = 500) -> list[str]:
    rows = get_db().execute(
        """
        SELECT article_name
        FROM article_catalog
        ORDER BY article_name COLLATE NOCASE ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [row["article_name"] for row in rows]


def row_to_report(row) -> dict:
    report = dict(row)
    summary_metrics, article_entries = unpack_report_payload(report["report_key"], report["data_json"])
    report["summary_metrics"] = enrich_metrics(summary_metrics)
    report["article_entries"] = enrich_metrics(article_entries)
    report["article_groups"] = group_article_entries(article_entries)
    report["definition"] = get_report_definition(report["report_key"])
    return report


def grouped_report_rows(limit_per_group: int = 12) -> dict[str, list[dict]]:
    db = get_db()
    rows = db.execute(
        """
        SELECT *
        FROM reports
        ORDER BY report_date DESC, updated_at DESC
        """
    ).fetchall()
    grouped = defaultdict(list)
    for row in rows:
        if len(grouped[row["report_key"]]) < limit_per_group:
            grouped[row["report_key"]].append(row_to_report(row))
    return grouped


def latest_reports(limit: int = 5) -> list[dict]:
    rows = get_db().execute(
        """
        SELECT *
        FROM reports
        ORDER BY report_date DESC, updated_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [row_to_report(row) for row in rows]


def current_period_snapshots(period_type: str) -> tuple[dict[str, dict], str]:
    today = date.today()
    period_start, period_end = default_period_bounds(period_type, today)
    label = build_period_label(period_type, period_start, period_end)
    db = get_db()
    snapshots: dict[str, dict] = {}
    for report_key, _definition in all_reports():
        row = db.execute(
            """
            SELECT *
            FROM reports
            WHERE report_key = ? AND period_type = ? AND period_start = ? AND period_end = ?
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (report_key, period_type, period_start.isoformat(), period_end.isoformat()),
        ).fetchone()
        if row is not None:
            snapshots[report_key] = row_to_report(row)
    return snapshots, label


def build_week_options(count: int = 11) -> list[dict]:
    today = date.today()
    current_week_start, _ = default_period_bounds("weekly", today)
    options = []
    for index in range(count):
        week_start = current_week_start - timedelta(days=7 * index)
        week_end = week_start + timedelta(days=6)
        options.append(
            {
                "value": week_start.isoformat(),
                "label": f"{week_start.strftime('%d.%m')} - {week_end.strftime('%d.%m')}",
                "start": week_start,
                "end": week_end,
            }
        )
    return options


def build_month_options(count: int = 12) -> list[dict]:
    today = date.today()
    month_start = today.replace(day=1)
    options = []
    current = month_start
    for _index in range(count):
        if current.month == 12:
            next_month = current.replace(year=current.year + 1, month=1, day=1)
        else:
            next_month = current.replace(month=current.month + 1, day=1)
        options.append(
            {
                "value": current.isoformat(),
                "label": current.strftime("%m.%y"),
                "start": current,
                "end": next_month - timedelta(days=1),
            }
        )
        if current.month == 1:
            current = current.replace(year=current.year - 1, month=12, day=1)
        else:
            current = current.replace(month=current.month - 1, day=1)
    return options


def snapshots_for_period(period_type: str, period_start: date, period_end: date) -> dict[str, dict]:
    db = get_db()
    snapshots: dict[str, dict] = {}
    for report_key, _definition in all_reports():
        row = db.execute(
            """
            SELECT *
            FROM reports
            WHERE report_key = ? AND period_type = ? AND period_start = ? AND period_end = ?
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (report_key, period_type, period_start.isoformat(), period_end.isoformat()),
        ).fetchone()
        if row is not None:
            snapshots[report_key] = row_to_report(row)
    return snapshots


def resolve_dashboard_period_selection(args) -> dict:
    saved = stored_dashboard_filters()
    selected_period = args.get("period") or saved.get("period") or "weekly"
    if selected_period not in PERIOD_LABELS:
        selected_period = "weekly"

    day_value = args.get("day_date") or saved.get("day_date") or date.today().isoformat()
    try:
        day_date = datetime.strptime(day_value, "%Y-%m-%d").date()
    except ValueError:
        day_date = date.today()
        day_value = day_date.isoformat()

    week_options = build_week_options()
    default_week_value = week_options[1]["value"] if len(week_options) > 1 else week_options[0]["value"]
    selected_week_value = args.get("week_start") or saved.get("week_start") or default_week_value
    selected_week = next((item for item in week_options if item["value"] == selected_week_value), None)
    if selected_week is None:
        selected_week = next(item for item in week_options if item["value"] == default_week_value)
        selected_week_value = selected_week["value"]

    month_options = build_month_options()
    default_month_value = month_options[0]["value"]
    selected_month_value = args.get("month_start") or saved.get("month_start") or default_month_value
    selected_month = next((item for item in month_options if item["value"] == selected_month_value), None)
    if selected_month is None:
        selected_month = next(item for item in month_options if item["value"] == default_month_value)
        selected_month_value = selected_month["value"]

    if selected_period == "daily":
        period_start = period_end = day_date
        current_label = day_date.strftime("%d.%m.%Y")
    elif selected_period == "weekly":
        period_start = selected_week["start"]
        period_end = selected_week["end"]
        current_label = selected_week["label"]
    else:
        period_start = selected_month["start"]
        period_end = selected_month["end"]
        current_label = selected_month["label"]

    return {
        "selected_period": selected_period,
        "current_label": current_label,
        "period_start": period_start,
        "period_end": period_end,
        "day_value": day_value,
        "week_value": selected_week_value,
        "month_value": selected_month_value,
        "week_options": week_options,
        "month_options": month_options,
        "period_urls": {
            "daily": url_for("main.dashboard", period="daily", day_date=day_value),
            "weekly": url_for("main.dashboard", period="weekly", week_start=selected_week_value),
            "monthly": url_for("main.dashboard", period="monthly", month_start=selected_month_value),
        },
    }


def load_report_or_404(report_id: int) -> dict:
    row = get_db().execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    if row is None:
        abort(404)
    return row_to_report(row)


def ensure_report_access(report: dict) -> None:
    if report["submitted_by"] != g.user["id"] and not g.user["is_admin"]:
        abort(403)


def load_dashboard_or_404(dashboard_id: int):
    row = get_db().execute("SELECT * FROM dashboards WHERE id = ?", (dashboard_id,)).fetchone()
    if row is None:
        abort(404)
    return row


def ensure_dashboard_access(dashboard) -> None:
    if dashboard["uploaded_by"] != g.user["id"] and not g.user["is_admin"]:
        abort(403)


def dashboard_period_name(dashboard) -> str:
    title = dashboard["title"] or ""
    parts = [part.strip() for part in title.split("·", 1)]
    if len(parts) == 2:
        return parts[1]
    return title


def build_user_scope(user) -> dict:
    if user is None:
        return {
            "zone_key": None,
            "zone_label": "",
            "report_keys": [],
            "can_submit_reports": False,
            "can_view_dashboards": False,
            "can_upload_dashboards": False,
        }

    if user["is_admin"]:
        return {
            "zone_key": "admin",
            "zone_label": "Администратор",
            "report_keys": all_report_keys(),
            "can_submit_reports": True,
            "can_view_dashboards": True,
            "can_upload_dashboards": True,
        }

    zone_key = user["position"] if get_zone_definition(user["position"]) else "management"
    zone = get_zone_definition(zone_key)
    return {
        "zone_key": zone_key,
        "zone_label": zone["label"],
        "report_keys": zone["report_keys"],
        "can_submit_reports": zone["can_submit_reports"],
        "can_view_dashboards": zone["can_view_dashboards"],
        "can_upload_dashboards": zone["can_upload_dashboards"],
    }


def visible_report_groups() -> dict[str, list[tuple[str, dict]]]:
    allowed = set(g.user_scope["report_keys"])
    groups: dict[str, list[tuple[str, dict]]] = {}
    for group_name, reports in grouped_reports().items():
        filtered = [(report_key, definition) for report_key, definition in reports if report_key in allowed]
        if filtered:
            groups[group_name] = filtered
    return groups


def visible_report_keys() -> set[str]:
    return set(g.user_scope["report_keys"])


def can_view_report_key(report_key: str) -> bool:
    return report_key in visible_report_keys()


def can_submit_report_key(report_key: str) -> bool:
    return g.user_scope["can_submit_reports"] and report_key in visible_report_keys()


def settings_actions_for_report(report_key: str, snapshot: dict | None = None) -> list[dict]:
    actions = []
    if snapshot is not None:
        actions.append({"label": "Открыть", "url": url_for("main.report_detail", report_id=snapshot["id"]), "kind": "secondary"})
        actions.append({"label": "История", "url": f"{dashboard_url_with_state()}#{report_key}", "kind": "ghost"})
        if snapshot["submitted_by"] == g.user["id"] or g.user["is_admin"]:
            actions.append({"label": "Изменить", "url": url_for("main.edit_report", report_id=snapshot["id"]), "kind": "ghost"})
    else:
        actions.append({"label": "История", "url": f"{dashboard_url_with_state()}#{report_key}", "kind": "ghost"})
    if can_submit_report_key(report_key):
        actions.append({"label": "Заполнить", "url": url_for("main.report_form", report_key=report_key), "kind": "primary"})
    return actions


def stored_dashboard_filters() -> dict:
    saved = session.get(DASHBOARD_FILTERS_SESSION_KEY, {})
    if not isinstance(saved, dict):
        return {}
    return {
        "period": saved.get("period"),
        "day_date": saved.get("day_date"),
        "week_start": saved.get("week_start"),
        "month_start": saved.get("month_start"),
    }


def remember_dashboard_filters(selection: dict) -> None:
    session[DASHBOARD_FILTERS_SESSION_KEY] = {
        "period": selection["selected_period"],
        "day_date": selection["day_value"],
        "week_start": selection["week_value"],
        "month_start": selection["month_value"],
    }


def dashboard_url_with_state(**overrides) -> str:
    params = {key: value for key, value in stored_dashboard_filters().items() if value}
    params.update({key: value for key, value in overrides.items() if value is not None})
    return url_for("main.dashboard", **params)


def purge_expired_data() -> None:
    retention_by_period = current_app.config.get(
        "REPORT_RETENTION_DAYS",
        {"daily": 62, "weekly": 90, "monthly": 180},
    )
    policy_start_date = current_app.config.get("RETENTION_POLICY_START_DATE", "2026-06-26")
    db = get_db()

    for period_type, retention_days in retention_by_period.items():
        cutoff = date.today() - timedelta(days=int(retention_days))

        old_dashboards = db.execute(
            """
            SELECT id, filename
            FROM dashboards
            WHERE period_type = ?
              AND substr(created_at, 1, 10) >= ?
              AND substr(created_at, 1, 10) < ?
            """,
            (period_type, policy_start_date, cutoff.isoformat()),
        ).fetchall()
        for row in old_dashboards:
            file_path = Path(current_app.config["DASHBOARD_UPLOAD_FOLDER"]) / row["filename"]
            if file_path.exists():
                file_path.unlink()
        if old_dashboards:
            db.executemany("DELETE FROM dashboards WHERE id = ?", [(row["id"],) for row in old_dashboards])

        db.execute(
            """
            DELETE FROM reports
            WHERE period_type = ?
              AND substr(created_at, 1, 10) >= ?
              AND period_end < ?
            """,
            (period_type, policy_start_date, cutoff.isoformat()),
        )
    db.commit()


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
        g.user_scope = build_user_scope(None)
    else:
        g.user = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        g.user_scope = build_user_scope(g.user)


@bp.app_context_processor
def inject_navigation_helpers():
    return {"dashboard_url": dashboard_url_with_state}


@bp.before_app_request
def apply_retention_policy():
    global LAST_RETENTION_RUN
    today_key = date.today().isoformat()
    if LAST_RETENTION_RUN == today_key:
        return
    purge_expired_data()
    LAST_RETENTION_RUN = today_key


@bp.route("/")
def index():
    if g.user is None:
        return redirect(url_for("main.login"))
    return redirect(url_for("main.dashboard"))


@bp.route("/register", methods=("GET", "POST"))
def register():
    return redirect(url_for("main.login"))


@bp.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        login_value = request.form["full_name"].strip()
        password = request.form["password"]
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE lower(full_name) = lower(?)",
            (login_value,),
        ).fetchone()
        if user is None:
            user = db.execute(
                "SELECT * FROM users WHERE lower(email) = lower(?)",
                (login_value,),
            ).fetchone()
        error = None
        if user is None or not check_password_hash(user["password_hash"], password):
            error = "Неверное имя или пароль."
        if error is None:
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("main.dashboard"))
        flash(error, "error")
    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.login"))


@bp.route("/dashboard")
@login_required
def dashboard():
    selection = resolve_dashboard_period_selection(request.args)
    remember_dashboard_filters(selection)
    snapshots = snapshots_for_period(
        selection["selected_period"],
        selection["period_start"],
        selection["period_end"],
    )
    filtered_snapshots = {report_key: report for report_key, report in snapshots.items() if can_view_report_key(report_key)}
    grouped_rows = grouped_report_rows()
    filtered_grouped_rows = {report_key: reports for report_key, reports in grouped_rows.items() if can_view_report_key(report_key)}
    return render_template(
        "dashboard.html",
        report_groups=visible_report_groups(),
        period_labels=PERIOD_LABELS,
        snapshots=filtered_snapshots,
        grouped_rows=filtered_grouped_rows,
        **selection,
    )


@bp.route("/reports")
@login_required
def reports_archive():
    return redirect(url_for("main.dashboard"))


@bp.route("/reports/<report_key>/new", methods=("GET", "POST"))
@login_required
def report_form(report_key: str):
    if report_key not in dict(all_reports()):
        abort(404)
    if not can_submit_report_key(report_key):
        abort(403)
    definition = get_report_definition(report_key)
    if request.method == "POST":
        period_type = request.form["period_type"]
        try:
            summary_metrics = build_summary_metrics_payload(report_key, source=request.form)
            article_entries = build_article_entries_payload(report_key, source=request.form)
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("main.report_form", report_key=report_key))
        report_id = store_report(
            report_key,
            period_type,
            request.form["report_date"],
            request.form.get("period_start"),
            request.form.get("period_end"),
            summary_metrics,
            article_entries,
        )
        sync_article_catalog(article_entries)
        flash("Отчет сохранен.", "success")
        return redirect(url_for("main.report_detail", report_id=report_id))
    today = date.today().isoformat()
    return render_template(
        "report_form.html",
        definition=definition,
        report_key=report_key,
        period_labels=PERIOD_LABELS,
        today=today,
        report=None,
        report_values={},
        article_entries=[{}],
        article_names=article_catalog_names(),
    )


@bp.route("/reports/<int:report_id>")
@login_required
def report_detail(report_id: int):
    report = load_report_or_404(report_id)
    if not can_view_report_key(report["report_key"]):
        abort(403)
    return render_template("report_detail.html", report=report)


@bp.route("/reports/<int:report_id>/edit", methods=("GET", "POST"))
@login_required
def edit_report(report_id: int):
    report = load_report_or_404(report_id)
    if not can_view_report_key(report["report_key"]):
        abort(403)
    ensure_report_access(report)
    if request.method == "POST":
        try:
            summary_metrics = build_summary_metrics_payload(report["report_key"], source=request.form)
            article_entries = build_article_entries_payload(report["report_key"], source=request.form)
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("main.edit_report", report_id=report_id))
        store_report(
            report["report_key"],
            request.form["period_type"],
            request.form["report_date"],
            request.form.get("period_start"),
            request.form.get("period_end"),
            summary_metrics,
            article_entries,
            report_id=report_id,
        )
        sync_article_catalog(article_entries)
        flash("Отчет обновлен.", "success")
        return redirect(url_for("main.report_detail", report_id=report_id))
    return render_template(
        "report_form.html",
        definition=report["definition"],
        report_key=report["report_key"],
        period_labels=PERIOD_LABELS,
        today=report["report_date"],
        report=report,
        report_values={item["code"]: item for item in report["summary_metrics"]},
        article_entries=report["article_entries"] or [{}],
        article_names=article_catalog_names(),
    )


@bp.route("/reports/<int:report_id>/delete", methods=("POST",))
@login_required
def delete_report(report_id: int):
    report = load_report_or_404(report_id)
    if not can_view_report_key(report["report_key"]):
        abort(403)
    db = get_db()
    db.execute("DELETE FROM reports WHERE id = ?", (report_id,))
    db.commit()
    flash("Отчет удален.", "success")
    next_url = request.form.get("next") or dashboard_url_with_state()
    return redirect(next_url)


@bp.route("/reports/<report_key>/template/<period_type>")
@login_required
def download_template(report_key: str, period_type: str):
    if report_key not in dict(all_reports()) or period_type not in PERIOD_LABELS:
        abort(404)
    if not can_submit_report_key(report_key):
        abort(403)
    definition = get_report_definition(report_key)
    file_bytes = create_report_template(report_key, definition, period_type)
    filename = f"{report_key}-{period_type}-template.xlsx"
    return send_file(
        BytesIO(file_bytes),
        download_name=filename,
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.route("/reports/<report_key>/import", methods=("POST",))
@login_required
def import_report(report_key: str):
    if report_key not in dict(all_reports()):
        abort(404)
    if not can_submit_report_key(report_key):
        abort(403)
    report_id = request.form.get("report_id", type=int)
    if report_id is not None:
        existing_report = load_report_or_404(report_id)
        if existing_report["report_key"] != report_key:
            abort(400)
        ensure_report_access(existing_report)
    upload = request.files.get("report_file")
    period_type = request.form["period_type"]
    report_date = request.form["report_date"]
    if upload is None or upload.filename == "":
        flash("Сначала выберите Excel-файл шаблона.", "error")
        return redirect(url_for("main.report_form", report_key=report_key))
    try:
        imported_data = parse_report_workbook(upload)
    finally:
        upload.close()
    try:
        summary_metrics = build_summary_metrics_payload(report_key, imported_rows=imported_data["summary_metrics"])
        article_entries = build_article_entries_payload(report_key, imported_rows=imported_data["article_entries"])
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("main.report_form", report_key=report_key))
    report_id = store_report(
        report_key,
        period_type,
        report_date,
        request.form.get("period_start"),
        request.form.get("period_end"),
        summary_metrics,
        article_entries,
        report_id=report_id,
    )
    sync_article_catalog(article_entries)
    flash("Excel-файл обработан. В базе сохранены только значения отчета, сам файл не хранится.", "success")
    return redirect(url_for("main.report_detail", report_id=report_id))


@bp.route("/dashboards", methods=("GET", "POST"))
@login_required
def dashboards():
    if not g.user_scope["can_view_dashboards"]:
        abort(403)
    db = get_db()
    if request.method == "POST":
        if not g.user_scope["can_upload_dashboards"]:
            abort(403)
        period_type = request.form["period_type"]
        period_name = request.form["period_name"].strip()
        html_file = request.files.get("dashboard_file")
        error = None
        if period_type not in {"weekly", "monthly"} or not period_name:
            error = "Заполните тип и период дашборда."
        if html_file is None or html_file.filename == "":
            error = "Выберите HTML-файл."
        elif not html_file.filename.lower().endswith(".html"):
            error = "Поддерживаются только файлы .html."
        if error is None:
            title = f"{period_type.capitalize()} · {period_name}"
            safe_name = secure_filename(html_file.filename)
            unique_name = f"{uuid.uuid4().hex}-{safe_name}"
            target = Path(current_app.config["DASHBOARD_UPLOAD_FOLDER"]) / unique_name
            html_file.save(target)
            db.execute(
                """
                INSERT INTO dashboards (title, platform, period_type, filename, original_name, uploaded_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    title,
                    "HTML",
                    period_type,
                    unique_name,
                    html_file.filename,
                    g.user["id"],
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            db.commit()
            flash("HTML-дашборд загружен.", "success")
            return redirect(url_for("main.dashboards"))
        flash(error, "error")
    rows = db.execute(
        """
        SELECT dashboards.*, users.full_name AS uploader_name
        FROM dashboards
        LEFT JOIN users ON users.id = dashboards.uploaded_by
        ORDER BY created_at DESC
        """
    ).fetchall()
    selected_type = request.args.get("type", "weekly")
    if selected_type not in {"weekly", "monthly"}:
        selected_type = "weekly"
    selected_dashboard_id = request.args.get("selected_dashboard_id", type=int)
    dashboards_by_type = {
        "weekly": [row for row in rows if row["period_type"] == "weekly"],
        "monthly": [row for row in rows if row["period_type"] == "monthly"],
    }
    selected_dashboard = None
    if selected_dashboard_id is not None:
        for row in rows:
            if row["id"] == selected_dashboard_id:
                selected_dashboard = row
                break
    return render_template(
        "dashboards.html",
        dashboards=rows,
        recent_dashboards=rows[:5],
        dashboards_by_type=dashboards_by_type,
        selected_type=selected_type,
        selected_dashboard=selected_dashboard,
    )


@bp.route("/dashboards/<int:dashboard_id>")
@login_required
def dashboard_view(dashboard_id: int):
    if not g.user_scope["can_view_dashboards"]:
        abort(403)
    row = load_dashboard_or_404(dashboard_id)
    return render_template("dashboard_view.html", dashboard=row)


@bp.route("/dashboards/<int:dashboard_id>/edit", methods=("GET", "POST"))
@login_required
def dashboard_edit(dashboard_id: int):
    if not g.user_scope["can_upload_dashboards"]:
        abort(403)
    dashboard = load_dashboard_or_404(dashboard_id)
    ensure_dashboard_access(dashboard)
    if request.method == "POST":
        period_type = request.form["period_type"]
        period_name = request.form["period_name"].strip()
        html_file = request.files.get("dashboard_file")
        error = None
        if period_type not in {"weekly", "monthly"} or not period_name:
            error = "Заполните тип и период дашборда."
        if html_file is None or html_file.filename == "":
            error = "Выберите новый HTML-файл."
        elif not html_file.filename.lower().endswith(".html"):
            error = "Поддерживаются только файлы .html."
        if error is None:
            title = f"{period_type.capitalize()} · {period_name}"
            safe_name = secure_filename(html_file.filename)
            unique_name = f"{uuid.uuid4().hex}-{safe_name}"
            target = Path(current_app.config["DASHBOARD_UPLOAD_FOLDER"]) / unique_name
            html_file.save(target)
            old_path = Path(current_app.config["DASHBOARD_UPLOAD_FOLDER"]) / dashboard["filename"]
            if old_path.exists():
                old_path.unlink()
            db = get_db()
            db.execute(
                """
                UPDATE dashboards
                SET title = ?, period_type = ?, filename = ?, original_name = ?
                WHERE id = ?
                """,
                (title, period_type, unique_name, html_file.filename, dashboard_id),
            )
            db.commit()
            flash("HTML-дашборд обновлен.", "success")
            return redirect(url_for("main.dashboard_view", dashboard_id=dashboard_id))
        flash(error, "error")
    return render_template(
        "dashboard_edit.html",
        dashboard=dashboard,
        period_name=dashboard_period_name(dashboard),
    )


@bp.route("/dashboards/<int:dashboard_id>/delete", methods=("POST",))
@login_required
def dashboard_delete(dashboard_id: int):
    if not g.user_scope["can_upload_dashboards"]:
        abort(403)
    dashboard = load_dashboard_or_404(dashboard_id)
    ensure_dashboard_access(dashboard)
    file_path = Path(current_app.config["DASHBOARD_UPLOAD_FOLDER"]) / dashboard["filename"]
    if file_path.exists():
        file_path.unlink()
    db = get_db()
    db.execute("DELETE FROM dashboards WHERE id = ?", (dashboard_id,))
    db.commit()
    flash("HTML-дашборд удален.", "success")
    next_url = request.form.get("next") or url_for("main.dashboards")
    return redirect(next_url)


@bp.route("/dashboards/files/<path:filename>")
@login_required
def dashboard_file(filename: str):
    if not g.user_scope["can_view_dashboards"]:
        abort(403)
    return send_from_directory(current_app.config["DASHBOARD_UPLOAD_FOLDER"], filename)

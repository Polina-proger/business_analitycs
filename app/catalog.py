from __future__ import annotations

from datetime import date, timedelta


REPORT_DEFINITIONS = {
    "ozon": {
        "title": "Ozon",
        "group": "Маркетплейсы",
        "description": "Продажи, маржа, ROI, ДРР, ABC-зоны и оборачиваемость по Ozon.",
        "metrics": [
            {"code": "sales_rub", "label": "Продажи", "unit": "₽", "has_plan": True, "direction": "up"},
            {"code": "margin_rub", "label": "Маржа", "unit": "₽", "has_plan": True, "direction": "up"},
            {"code": "margin_pct", "label": "Маржа", "unit": "%", "has_plan": True, "direction": "up"},
            {"code": "roi_pct", "label": "ROI", "unit": "%", "has_plan": True, "direction": "up"},
            {"code": "drr_pct", "label": "ДРР", "unit": "%", "has_plan": True, "direction": "down"},
            {"code": "abc_red_sku", "label": "SKU в красной зоне", "unit": "шт", "has_plan": False, "direction": "down"},
            {"code": "abc_yellow_sku", "label": "SKU в желтой зоне", "unit": "шт", "has_plan": False, "direction": "down"},
            {"code": "abc_work_sku", "label": "SKU в рабочей зоне", "unit": "шт", "has_plan": False, "direction": "up"},
            {"code": "turnover_orders", "label": "Оборачиваемость в заказах", "unit": "заказов", "has_plan": True, "direction": "up"},
        ],
    },
    "wb": {
        "title": "WB",
        "group": "Маркетплейсы",
        "description": "Продажи, маржа, ROI, ДРР, ABC-зоны и оборачиваемость по Wildberries.",
        "metrics": [
            {"code": "sales_rub", "label": "Продажи", "unit": "₽", "has_plan": True, "direction": "up"},
            {"code": "margin_rub", "label": "Маржа", "unit": "₽", "has_plan": True, "direction": "up"},
            {"code": "margin_pct", "label": "Маржа", "unit": "%", "has_plan": True, "direction": "up"},
            {"code": "roi_pct", "label": "ROI", "unit": "%", "has_plan": True, "direction": "up"},
            {"code": "drr_pct", "label": "ДРР", "unit": "%", "has_plan": True, "direction": "down"},
            {"code": "abc_red_sku", "label": "SKU в красной зоне", "unit": "шт", "has_plan": False, "direction": "down"},
            {"code": "abc_yellow_sku", "label": "SKU в желтой зоне", "unit": "шт", "has_plan": False, "direction": "down"},
            {"code": "abc_work_sku", "label": "SKU в рабочей зоне", "unit": "шт", "has_plan": False, "direction": "up"},
            {"code": "turnover_orders", "label": "Оборачиваемость в заказах", "unit": "заказов", "has_plan": True, "direction": "up"},
        ],
    },
    "finance": {
        "title": "Финансы",
        "group": "Финансы",
        "description": "ДДС, маржа, прибыль, ROI, ROS, баланс и оборачиваемость по себестоимости.",
        "metrics": [
            {"code": "cash_on_accounts_rub", "label": "Деньги на счетах", "unit": "₽", "has_plan": False, "direction": "up"},
            {"code": "cash_flow_rub", "label": "ДДС", "unit": "₽", "has_plan": True, "direction": "up"},
            {"code": "company_margin_rub", "label": "Маржа по компании", "unit": "₽", "has_plan": True, "direction": "up"},
            {"code": "company_margin_pct", "label": "Маржа по компании", "unit": "%", "has_plan": True, "direction": "up"},
            {"code": "company_profit_rub", "label": "Прибыль по компании", "unit": "₽", "has_plan": True, "direction": "up"},
            {"code": "company_profit_pct", "label": "Прибыль по компании", "unit": "%", "has_plan": True, "direction": "up"},
            {"code": "roi_pct", "label": "ROI", "unit": "%", "has_plan": True, "direction": "up"},
            {"code": "ros_pct", "label": "ROS", "unit": "%", "has_plan": True, "direction": "up"},
            {"code": "balance_rub", "label": "Баланс", "unit": "₽", "has_plan": False, "direction": "up"},
            {"code": "cogs_turnover", "label": "Оборачиваемость по себестоимости", "unit": "дн", "has_plan": True, "direction": "down"},
        ],
    },
    "procurement": {
        "title": "Закупки",
        "group": "Операции",
        "description": "Себестоимость, долги поставщикам и оборачиваемость закупочной партии.",
        "metrics": [
            {"code": "cost_price_rub", "label": "Себестоимость", "unit": "₽", "has_plan": True, "direction": "down"},
            {"code": "supplier_debt_rub", "label": "Долги перед поставщиками", "unit": "₽", "has_plan": True, "direction": "up"},
            {"code": "purchase_batch_turnover", "label": "Оборачиваемость закупочной партии", "unit": "дн", "has_plan": True, "direction": "down"},
        ],
    },
    "logistics": {
        "title": "Логистика",
        "group": "Операции",
        "description": "Операционная оборачиваемость поставок и стоимость отгрузки единицы товара.",
        "metrics": [
            {"code": "ozon_acceptance_turnover", "label": "Оборачиваемость Ozon: от заявки до приемки", "unit": "дн", "has_plan": True, "direction": "down"},
            {"code": "wb_acceptance_turnover", "label": "Оборачиваемость WB: от заявки до приемки", "unit": "дн", "has_plan": True, "direction": "down"},
            {"code": "shipping_cost_per_unit", "label": "Стоимость отгрузки ед. товара", "unit": "₽", "has_plan": True, "direction": "down"},
        ],
    },
}

RESPONSIBILITY_ZONES = {
    "ozon": {
        "label": "Ozon",
        "report_keys": ["ozon"],
        "can_submit_reports": True,
        "can_view_dashboards": False,
        "can_upload_dashboards": False,
    },
    "wb": {
        "label": "WB",
        "report_keys": ["wb"],
        "can_submit_reports": True,
        "can_view_dashboards": False,
        "can_upload_dashboards": False,
    },
    "finance": {
        "label": "Финансы",
        "report_keys": ["finance"],
        "can_submit_reports": True,
        "can_view_dashboards": False,
        "can_upload_dashboards": False,
    },
    "procurement": {
        "label": "Закупки",
        "report_keys": ["procurement"],
        "can_submit_reports": True,
        "can_view_dashboards": False,
        "can_upload_dashboards": False,
    },
    "logistics": {
        "label": "Логистика",
        "report_keys": ["logistics"],
        "can_submit_reports": True,
        "can_view_dashboards": False,
        "can_upload_dashboards": False,
    },
    "management": {
        "label": "Управление",
        "report_keys": list(REPORT_DEFINITIONS.keys()),
        "can_submit_reports": False,
        "can_view_dashboards": True,
        "can_upload_dashboards": False,
    },
}

PERIOD_LABELS = {
    "daily": "День",
    "weekly": "Неделя",
    "monthly": "Месяц",
}


def get_report_definition(report_key: str) -> dict:
    return REPORT_DEFINITIONS[report_key]


def all_reports() -> list[tuple[str, dict]]:
    return list(REPORT_DEFINITIONS.items())


def grouped_reports() -> dict[str, list[tuple[str, dict]]]:
    groups: dict[str, list[tuple[str, dict]]] = {}
    for report_key, definition in REPORT_DEFINITIONS.items():
        groups.setdefault(definition["group"], []).append((report_key, definition))
    return groups


def all_report_keys() -> list[str]:
    return list(REPORT_DEFINITIONS.keys())


def responsibility_zones() -> dict[str, dict]:
    return RESPONSIBILITY_ZONES


def get_zone_definition(zone_key: str) -> dict | None:
    return RESPONSIBILITY_ZONES.get(zone_key)


def default_period_bounds(period_type: str, anchor: date) -> tuple[date, date]:
    if period_type == "daily":
        return anchor, anchor
    if period_type == "weekly":
        start = anchor - timedelta(days=anchor.weekday())
        return start, start + timedelta(days=6)
    start = anchor.replace(day=1)
    if start.month == 12:
        next_month = start.replace(year=start.year + 1, month=1, day=1)
    else:
        next_month = start.replace(month=start.month + 1, day=1)
    return start, next_month - timedelta(days=1)


def build_period_label(period_type: str, start: date, end: date) -> str:
    if period_type == "daily":
        return start.strftime("%d.%m.%Y")
    if period_type == "weekly":
        return f"{start.strftime('%d.%m')} - {end.strftime('%d.%m.%Y')}"
    return start.strftime("%m.%Y")


def metric_lookup(report_key: str) -> dict[str, dict]:
    definition = get_report_definition(report_key)
    return {metric["code"]: metric for metric in definition["metrics"]}

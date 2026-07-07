const root = document.body;
const storageKey = "business-analytics-theme";

function applyTheme(theme) {
    root.setAttribute("data-theme", theme);
    const button = document.querySelector("[data-theme-toggle]");
    if (button) {
        button.setAttribute(
            "title",
            theme === "dark" ? "Переключить на светлую тему" : "Переключить на темную тему"
        );
    }
}

const savedTheme = localStorage.getItem(storageKey) || "light";
applyTheme(savedTheme);

document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-theme-toggle]");
    if (!button) {
        return;
    }
    const current = root.getAttribute("data-theme") || "light";
    const next = current === "dark" ? "light" : "dark";
    localStorage.setItem(storageKey, next);
    applyTheme(next);
});

function updateDashboardTitlePreview() {
    const typeField = document.querySelector("[data-dashboard-period-type]");
    const periodField = document.querySelector("[data-dashboard-period-name]");
    const preview = document.querySelector("[data-dashboard-title-preview]");
    if (!typeField || !periodField || !preview) {
        return;
    }
    const typeLabel = typeField.value === "monthly" ? "Monthly" : "Weekly";
    const periodLabel = periodField.value.trim() || "08.06-14.06";
    preview.textContent = `${typeLabel} · ${periodLabel}`;
}

document.addEventListener("input", (event) => {
    if (event.target.matches("[data-dashboard-period-name], [data-dashboard-period-type]")) {
        updateDashboardTitlePreview();
    }
});

document.addEventListener("change", (event) => {
    if (event.target.matches("[data-dashboard-period-name], [data-dashboard-period-type]")) {
        updateDashboardTitlePreview();
    }
});

updateDashboardTitlePreview();

function formatDateInputValue(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}

function buildPeriodBounds(periodType, reportDateValue) {
    if (!periodType || !reportDateValue) {
        return null;
    }
    const [year, month, day] = reportDateValue.split("-").map(Number);
    if (!year || !month || !day) {
        return null;
    }
    const anchor = new Date(year, month - 1, day);
    if (Number.isNaN(anchor.getTime())) {
        return null;
    }
    let start;
    let end;
    if (periodType === "daily") {
        start = new Date(anchor);
        end = new Date(anchor);
    } else if (periodType === "weekly") {
        const weekday = (anchor.getDay() + 6) % 7;
        start = new Date(anchor);
        start.setDate(anchor.getDate() - weekday);
        end = new Date(start);
        end.setDate(start.getDate() + 6);
    } else {
        start = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
        end = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0);
    }
    return {
        start: formatDateInputValue(start),
        end: formatDateInputValue(end),
    };
}

function bindPeriodAutoFill() {
    const forms = new Map();
    document.querySelectorAll("[data-period-form]").forEach((element) => {
        const formKey = element.getAttribute("data-period-form");
        if (!forms.has(formKey)) {
            forms.set(formKey, {});
        }
        const registry = forms.get(formKey);
        if (element.matches("[data-period-type]")) {
            registry.typeField = element;
        } else if (element.matches("[data-report-date]")) {
            registry.reportDateField = element;
        } else if (element.matches("[data-period-start]")) {
            registry.startField = element;
        } else if (element.matches("[data-period-end]")) {
            registry.endField = element;
        }
    });

    function syncFormBounds(registry) {
        if (!registry?.typeField || !registry?.reportDateField || !registry?.startField || !registry?.endField) {
            return;
        }
        const bounds = buildPeriodBounds(registry.typeField.value, registry.reportDateField.value);
        if (!bounds) {
            return;
        }
        registry.startField.value = bounds.start;
        registry.endField.value = bounds.end;
    }

    forms.forEach((registry) => {
        syncFormBounds(registry);
        [registry.typeField, registry.reportDateField].forEach((field) => {
            if (!field) {
                return;
            }
            field.addEventListener("change", () => syncFormBounds(registry));
            field.addEventListener("input", () => syncFormBounds(registry));
        });
    });
}

bindPeriodAutoFill();

function formatDateDisplay(value) {
    if (!value) {
        return "—";
    }
    const [year, month, day] = value.split("-").map(Number);
    if (!year || !month || !day) {
        return value;
    }
    return `${String(day).padStart(2, "0")}.${String(month).padStart(2, "0")}.${year}`;
}

function getPeriodTypeText(periodType) {
    const labels = {
        daily: {
            action: "день",
            title: "День",
        },
        weekly: {
            action: "неделю",
            title: "Неделя",
        },
        monthly: {
            action: "месяц",
            title: "Месяц",
        },
    };
    return labels[periodType] || {
        action: "период",
        title: "Период",
    };
}

function buildPeriodDisplay(periodType, reportDateValue, startValue, endValue) {
    const bounds = buildPeriodBounds(periodType, reportDateValue);
    const start = startValue || bounds?.start || "";
    const end = endValue || bounds?.end || "";
    if (periodType === "daily") {
        return formatDateDisplay(reportDateValue || start);
    }
    return `${formatDateDisplay(start)} - ${formatDateDisplay(end)}`;
}

function bindReportConfirmation() {
    const overlay = document.querySelector("[data-report-confirm]");
    if (!overlay) {
        return;
    }

    const messageNode = overlay.querySelector("[data-confirm-message]");
    const periodTypeNode = overlay.querySelector("[data-confirm-period-type]");
    const periodRangeNode = overlay.querySelector("[data-confirm-period-range]");
    const submitButton = overlay.querySelector("[data-confirm-submit]");
    const closeButtons = overlay.querySelectorAll("[data-confirm-close]");

    let pendingForm = null;

    function closeDialog() {
        overlay.hidden = true;
        document.body.classList.remove("dialog-open");
        pendingForm = null;
    }

    function openDialog(form) {
        const periodType = form.querySelector("[data-period-type]")?.value || "";
        const reportDate = form.querySelector("[data-report-date]")?.value || "";
        const periodStart = form.querySelector("[data-period-start]")?.value || "";
        const periodEnd = form.querySelector("[data-period-end]")?.value || "";
        const action = form.dataset.confirmAction || "Сохранить";
        const labels = getPeriodTypeText(periodType);

        pendingForm = form;
        messageNode.textContent = `${action} отчет за ${labels.action}`;
        periodTypeNode.textContent = labels.title;
        periodRangeNode.textContent = buildPeriodDisplay(periodType, reportDate, periodStart, periodEnd);
        submitButton.textContent = action;
        overlay.hidden = false;
        document.body.classList.add("dialog-open");
    }

    function tryOpenDialog(form, event = null) {
        if (!form) {
            return;
        }
        if (form.dataset.confirmedSubmit === "true") {
            return;
        }
        if (typeof form.reportValidity === "function" && !form.reportValidity()) {
            return;
        }
        if (event) {
            event.preventDefault();
        }
        openDialog(form);
    }

    document.querySelectorAll("[data-report-submit-form]").forEach((form) => {
        form.addEventListener("submit", (event) => {
            if (form.dataset.confirmedSubmit === "true") {
                delete form.dataset.confirmedSubmit;
                return;
            }
            tryOpenDialog(form, event);
        });
    });

    document.addEventListener("click", (event) => {
        const submitButton = event.target.closest(
            "[data-report-submit-form] button[type='submit'], [data-report-submit-form] input[type='submit']"
        );
        if (!submitButton) {
            return;
        }
        const form = submitButton.closest("[data-report-submit-form]");
        tryOpenDialog(form, event);
    });

    submitButton?.addEventListener("click", () => {
        if (!pendingForm) {
            closeDialog();
            return;
        }
        pendingForm.dataset.confirmedSubmit = "true";
        closeDialog();
        HTMLFormElement.prototype.submit.call(pendingForm);
    });

    closeButtons.forEach((button) => {
        button.addEventListener("click", closeDialog);
    });

    overlay.addEventListener("click", (event) => {
        if (event.target === overlay) {
            closeDialog();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !overlay.hidden) {
            closeDialog();
        }
    });
}

bindReportConfirmation();

function bindArticleRows() {
    const container = document.querySelector("[data-article-rows]");
    const template = document.getElementById("article-row-template");
    if (!container || !template) {
        return;
    }

    document.addEventListener("click", (event) => {
        const addButton = event.target.closest("[data-add-article-row]");
        if (addButton) {
            const clone = template.content.cloneNode(true);
            container.appendChild(clone);
            return;
        }

        const removeButton = event.target.closest("[data-remove-article-row]");
        if (!removeButton) {
            return;
        }
        const rows = container.querySelectorAll("[data-article-row]");
        if (rows.length <= 1) {
            const inputs = rows[0].querySelectorAll("input, select");
            inputs.forEach((input) => {
                if (input.tagName === "SELECT") {
                    input.selectedIndex = 0;
                } else {
                    input.value = "";
                }
            });
            return;
        }
        removeButton.closest("[data-article-row]")?.remove();
    });
}

bindArticleRows();

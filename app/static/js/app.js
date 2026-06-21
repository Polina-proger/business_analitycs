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

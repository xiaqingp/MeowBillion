import { state } from './state.js';

export function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(Math.abs(amount)).replace('$', '');
}

export function getRulesForCategory(cat) {
    if (!state.categoriesConfig || !state.categoriesConfig.rules) return [];
    const lowerCat = (cat || "").toLowerCase();
    for (const [key, val] of Object.entries(state.categoriesConfig.rules)) {
        if (key.toLowerCase() === lowerCat) {
            return val;
        }
    }
    return [];
}

export function enableResizableColumns() {
    const table = document.querySelector("#view-transactions .data-table");
    if (!table) return;

    table.style.tableLayout = "fixed";

    const cols = table.querySelectorAll("thead th");
    
    let savedWidths = {};
    try {
        const stored = localStorage.getItem("transaction_col_widths");
        if (stored) {
            savedWidths = JSON.parse(stored);
        }
    } catch (e) {
        console.error("Error reading column widths from localStorage:", e);
    }

    cols.forEach((th, idx) => {
        const colKey = `col_${idx}`;
        if (savedWidths[colKey]) {
            th.style.width = savedWidths[colKey];
        }

        if (th.querySelector(".col-resizer")) return;

        th.style.position = "relative";
        
        const resizer = document.createElement("div");
        resizer.className = "col-resizer";
        resizer.style.position = "absolute";
        resizer.style.top = "0";
        resizer.style.right = "0";
        resizer.style.width = "8px";
        resizer.style.height = "100%";
        resizer.style.cursor = "col-resize";
        resizer.style.userSelect = "none";
        resizer.style.zIndex = "10";
        
        resizer.addEventListener("mouseenter", () => {
            resizer.style.borderRight = "3px solid var(--color-primary)";
        });
        resizer.addEventListener("mouseleave", () => {
            resizer.style.borderRight = "none";
        });

        resizer.addEventListener("mousedown", (e) => {
            e.preventDefault();
            const startX = e.pageX;
            const startWidth = th.offsetWidth;
            
            resizer.style.borderRight = "3px solid var(--color-primary)";

            const onMouseMove = (moveEvent) => {
                const deltaX = moveEvent.pageX - startX;
                const newWidth = Math.max(40, startWidth + deltaX);
                th.style.width = `${newWidth}px`;
            };

            const onMouseUp = () => {
                document.removeEventListener("mousemove", onMouseMove);
                document.removeEventListener("mouseup", onMouseUp);
                resizer.style.borderRight = "none";
                
                const currentWidths = {};
                cols.forEach((header, index) => {
                    currentWidths[`col_${index}`] = `${header.offsetWidth}px`;
                });
                localStorage.setItem("transaction_col_widths", JSON.stringify(currentWidths));
            };

            document.addEventListener("mousemove", onMouseMove);
            document.addEventListener("mouseup", onMouseUp);
        });

        th.appendChild(resizer);
    });
}

export function initCustomMultiselects(triggerFilterUpdate) {
    document.querySelectorAll(".custom-multiselect").forEach(container => {
        const btn = container.querySelector(".multiselect-btn");
        const dropdown = container.querySelector(".multiselect-dropdown");
        if (!btn || !dropdown) return;

        btn.onclick = (e) => {
            e.stopPropagation();
            document.querySelectorAll(".multiselect-dropdown").forEach(d => {
                if (d !== dropdown) d.classList.remove("open");
            });
            dropdown.classList.toggle("open");
        };

        const selectAllLink = dropdown.querySelector(".select-all");
        if (selectAllLink) {
            selectAllLink.onclick = (e) => {
                e.stopPropagation();
                dropdown.querySelectorAll(".multiselect-options input[type='checkbox']").forEach(cb => {
                    cb.checked = true;
                });
                updateButtonText(container);
                triggerFilterUpdate();
            };
        }

        const clearAllLink = dropdown.querySelector(".clear-all");
        if (clearAllLink) {
            clearAllLink.onclick = (e) => {
                e.stopPropagation();
                dropdown.querySelectorAll(".multiselect-options input[type='checkbox']").forEach(cb => {
                    cb.checked = false;
                });
                updateButtonText(container);
                triggerFilterUpdate();
            };
        }

        const searchInput = dropdown.querySelector(".dropdown-search-input");
        if (searchInput) {
            searchInput.onclick = (e) => e.stopPropagation();
            searchInput.oninput = () => {
                const term = searchInput.value.toLowerCase().trim();
                dropdown.querySelectorAll(".multiselect-options label").forEach(lbl => {
                    const text = lbl.textContent.toLowerCase();
                    lbl.style.display = text.includes(term) ? "flex" : "none";
                });
            };
        }

        dropdown.querySelectorAll(".multiselect-options input[type='checkbox']").forEach(cb => {
            cb.onchange = () => {
                updateButtonText(container);
                triggerFilterUpdate();
            };
        });

        updateButtonText(container);
    });

    document.addEventListener("click", () => {
        document.querySelectorAll(".multiselect-dropdown").forEach(d => {
            d.classList.remove("open");
        });
    });

    document.querySelectorAll(".multiselect-dropdown").forEach(d => {
        d.onclick = (e) => e.stopPropagation();
    });
}

export function populateCategoryMultiselectOptions(categories, triggerFilterUpdate) {
    const list = document.getElementById("category-options-list");
    if (!list) return;

    list.innerHTML = "";
    (categories || []).slice().sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" })).forEach(cat => {
        const lbl = document.createElement("label");
        lbl.style.display = "flex";
        lbl.style.alignItems = "center";
        lbl.style.gap = "8px";
        lbl.style.padding = "6px 8px";
        lbl.style.fontSize = "12.5px";
        lbl.style.borderRadius = "4px";
        lbl.style.cursor = "pointer";
        
        lbl.innerHTML = `<input type="checkbox" value="${cat}" checked> ${cat}`;
        
        const cb = lbl.querySelector("input");
        cb.onchange = () => {
            updateButtonText(document.getElementById("filter-category-container"));
            triggerFilterUpdate();
        };

        list.appendChild(lbl);
    });

    updateButtonText(document.getElementById("filter-category-container"));
}

export function populateStatusMultiselectOptions(statuses, triggerFilterUpdate) {
    const list = document.getElementById("reviewed-options-list");
    if (!list) return;

    list.innerHTML = "";
    (statuses || []).forEach(status => {
        const lbl = document.createElement("label");
        lbl.style.display = "flex";
        lbl.style.alignItems = "center";
        lbl.style.gap = "8px";
        lbl.style.padding = "6px 8px";
        lbl.style.fontSize = "12.5px";
        lbl.style.borderRadius = "4px";
        lbl.style.cursor = "pointer";

        const countText = typeof status.count === "number" ? ` (${status.count})` : "";
        lbl.innerHTML = `<input type="checkbox" value="${status.value}" checked> ${status.label}${countText}`;

        const cb = lbl.querySelector("input");
        cb.onchange = () => {
            updateButtonText(document.getElementById("filter-reviewed-container"));
            triggerFilterUpdate();
        };

        list.appendChild(lbl);
    });

    updateButtonText(document.getElementById("filter-reviewed-container"));
}

export function getMultiselectValues(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return "all";

    const checkboxes = container.querySelectorAll(".multiselect-options input[type='checkbox']");
    const checked = Array.from(checkboxes).filter(cb => cb.checked).map(cb => cb.value);

    if (checked.length === 0) return "none";
    if (checked.length === checkboxes.length) return "all";
    return checked.join(",");
}

function updateButtonText(container) {
    if (!container) return;
    const btnSpan = container.querySelector(".multiselect-btn span");
    const checkboxes = container.querySelectorAll(".multiselect-options input[type='checkbox']");
    const checked = Array.from(checkboxes).filter(cb => cb.checked);
    const checkedCount = checked.length;
    const totalCount = checkboxes.length;

    let text = "All";
    if (container.id === "filter-direction-container") {
        if (checkedCount === totalCount) text = "All flows";
        else if (checkedCount === 0) text = "No flows";
        else text = checked.map(cb => cb.parentNode.textContent.trim().split(" ")[0]).join(", ");
    } else if (container.id === "filter-category-container") {
        if (checkedCount === totalCount) text = "All categories";
        else if (checkedCount === 0) text = "No categories";
        else {
            const labels = checked.map(cb => cb.value);
            text = labels.length <= 2 ? labels.join(", ") : `${checkedCount} categories`;
        }
    } else if (container.id === "filter-reviewed-container") {
        if (checkedCount === totalCount) text = "All statuses";
        else if (checkedCount === 0) text = "No statuses";
        else {
            const labels = checked.map(cb => cb.parentNode.textContent.trim().replace(/\s+\(\d+\)$/, ""));
            text = labels.length <= 2 ? labels.join(", ") : `${checkedCount} statuses`;
        }
    }

    if (btnSpan) btnSpan.textContent = text;
}


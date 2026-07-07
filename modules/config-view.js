import { state } from './state.js';
import { saveCategoriesConfigApi } from './api.js';
import { getRulesForCategory } from './utils.js';
import { renderTransactionsList } from './transaction-renderer.js';

let categoryAutosaveTimer = null;
let categorySaveRequestId = 0;
let categoryAutosaveStatus = "idle";

function sortedCategories() {
    return (state.categoriesConfig.categories || []).slice().sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));
}

function setCategoryAutosaveStatus(status) {
    categoryAutosaveStatus = status;
    const el = document.getElementById("category-autosave-status");
    if (!el) return;

    el.classList.remove("saving", "saved", "failed");
    if (status === "idle") {
        el.textContent = "";
    } else if (status === "saving") {
        el.classList.add("saving");
        el.textContent = "Saving...";
    } else if (status === "saved") {
        el.classList.add("saved");
        el.textContent = "Saved";
    } else if (status === "failed") {
        el.classList.add("failed");
        el.innerHTML = `Save failed · <button type="button" id="category-autosave-retry">Retry</button>`;
        document.getElementById("category-autosave-retry")?.addEventListener("click", autosaveCategoriesNow);
    }
}

function scheduleCategoriesAutosave() {
    clearTimeout(categoryAutosaveTimer);
    setCategoryAutosaveStatus("saving");
    categoryAutosaveTimer = setTimeout(autosaveCategoriesNow, 500);
}

async function autosaveCategoriesNow() {
    const requestId = ++categorySaveRequestId;
    try {
        setCategoryAutosaveStatus("saving");
        const result = await saveCategoriesConfig({ silent: true });
        if (requestId !== categorySaveRequestId) return;
        setCategoryAutosaveStatus(result?.status === "success" ? "saved" : "failed");
        if (result?.status === "success") {
            window.dispatchEvent(new CustomEvent("categories-config-saved", { detail: { categoriesConfig: state.categoriesConfig } }));
        }
    } catch (err) {
        if (requestId !== categorySaveRequestId) return;
        console.error("Category autosave failed:", err);
        setCategoryAutosaveStatus("failed");
    }
}

function makeConfigRow(label, iconName, onClick) {
    const row = document.createElement("div");
    row.style.display = "flex";
    row.style.justifyContent = "space-between";
    row.style.alignItems = "center";
    row.style.padding = "8px 12px";
    row.style.backgroundColor = "var(--bg-main)";
    row.style.borderRadius = "6px";
    row.style.border = "1px solid var(--border-color)";
    row.style.fontSize = "13px";

    const text = document.createElement("span");
    text.style.fontWeight = "600";
    text.style.color = "var(--text-primary)";
    text.textContent = label;

    const button = document.createElement("button");
    button.className = "btn-action-inline";
    button.style.color = "var(--color-danger)";
    button.style.borderColor = "var(--color-danger)";
    button.style.height = "24px";
    button.style.padding = "0 6px";
    button.innerHTML = `<i data-lucide="${iconName}" style="width:12px;height:12px;"></i>`;
    button.addEventListener("click", onClick);

    row.append(text, button);
    return row;
}

export function renderCategoryConfigView() {
    const typesListContainer = document.getElementById("config-categories-list");
    if (typesListContainer) {
        typesListContainer.innerHTML = "";
        sortedCategories().forEach(cat => {
            typesListContainer.appendChild(makeConfigRow(cat, "trash-2", event => deleteCategory(cat, event)));
        });
    }

    const ruleCatSelect = document.getElementById("config-rule-category-select");
    if (ruleCatSelect) {
        const currentSelected = ruleCatSelect.value;
        ruleCatSelect.innerHTML = '<option value="">Select a category...</option>';
        sortedCategories().forEach(cat => {
            const opt = document.createElement("option");
            opt.value = cat;
            opt.textContent = cat;
            if (cat === currentSelected) opt.selected = true;
            ruleCatSelect.appendChild(opt);
        });
        onConfigRuleCategoryChange();
    }
    setCategoryAutosaveStatus(categoryAutosaveStatus);
    lucide.createIcons();
}

export function onConfigRuleCategoryChange() {
    const select = document.getElementById("config-rule-category-select");
    const container = document.getElementById("config-subcategories-container");
    const subList = document.getElementById("config-subcategories-list");
    if (!select || !container || !subList) return;

    const cat = select.value;
    if (!cat) {
        container.style.display = "none";
        return;
    }

    container.style.display = "block";
    subList.innerHTML = "";

    const subcats = getRulesForCategory(cat);
    if (subcats.length === 0) {
        const empty = document.createElement("span");
        empty.style.color = "var(--text-muted)";
        empty.style.fontSize = "12px";
        empty.textContent = "No subcategories configured for this category.";
        subList.appendChild(empty);
        return;
    }

    subcats.forEach(sub => {
        subList.appendChild(makeConfigRow(sub, "x", event => deleteSubcategory(sub, event)));
    });
    lucide.createIcons();
}

export function addNewCategory() {
    const input = document.getElementById("new-category-input");
    if (!input) return;

    const catName = input.value.trim();
    if (!catName) {
        alert("Enter a category name.");
        return;
    }

    if ((state.categoriesConfig.categories || []).includes(catName)) {
        alert("This category already exists.");
        return;
    }

    state.categoriesConfig.categories.push(catName);
    state.categoriesConfig.categories = sortedCategories();
    input.value = "";
    renderCategoryConfigView();
    scheduleCategoriesAutosave();
}

export function deleteCategory(cat, event) {
    if (event) event.stopPropagation();

    if (!confirm(`Delete category "${cat}"?\n\nThis removes the category from the configuration and also removes its subcategory rules. Existing transactions are not deleted.`)) {
        return;
    }

    state.categoriesConfig.categories = (state.categoriesConfig.categories || []).filter(c => c !== cat);
    if (state.categoriesConfig.rules?.[cat]) {
        delete state.categoriesConfig.rules[cat];
    }

    const select = document.getElementById("config-rule-category-select");
    if (select && select.value === cat) {
        select.value = "";
    }

    renderCategoryConfigView();
    scheduleCategoriesAutosave();
}

export function addNewSubcategory() {
    const select = document.getElementById("config-rule-category-select");
    const input = document.getElementById("new-subcategory-input");
    if (!select || !input) return;

    const cat = select.value;
    const subName = input.value.trim();
    if (!cat) {
        alert("Select a category first.");
        return;
    }
    if (!subName) {
        alert("Enter a subcategory name.");
        return;
    }

    if (!state.categoriesConfig.rules[cat]) {
        state.categoriesConfig.rules[cat] = [];
    }

    if (state.categoriesConfig.rules[cat].includes(subName)) {
        alert("This subcategory already exists for the selected category.");
        return;
    }

    state.categoriesConfig.rules[cat].push(subName);
    input.value = "";
    onConfigRuleCategoryChange();
    scheduleCategoriesAutosave();
}

export function deleteSubcategory(sub, event) {
    if (event) event.stopPropagation();

    const select = document.getElementById("config-rule-category-select");
    if (!select) return;

    const cat = select.value;
    if (!cat || !state.categoriesConfig.rules[cat]) return;

    state.categoriesConfig.rules[cat] = state.categoriesConfig.rules[cat].filter(s => s !== sub);
    onConfigRuleCategoryChange();
    scheduleCategoriesAutosave();
}

export async function saveCategoriesConfig(options = {}) {
    const silent = typeof options === "object" ? Boolean(options.silent) : false;
    const buttonId = typeof options === "string" ? options : "";
    const saveBtn = buttonId ? document.getElementById(buttonId) : null;
    const saveLabel = buttonId === "btn-save-subcategories-config" ? "Save subcategories" : "Save categories";
    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i data-lucide="loader-2" class="spin" style="width:14px;height:14px;"></i> Saving...';
        lucide.createIcons();
    }

    try {
        const data = await saveCategoriesConfigApi(state.categoriesConfig);
        if (data.status === "success") {
            const { updateCategoryFilterOptions } = await import('../app.js');
            updateCategoryFilterOptions();
            renderTransactionsList();
        } else if (!silent) {
            alert("Save failed: " + data.error);
        } else {
            return data;
        }
        return data;
    } catch (err) {
        console.error("Save config error:", err);
        if (!silent) alert("Save failed: " + err.message);
        return { status: "error", error: err.message };
    } finally {
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.innerHTML = `<i data-lucide="save" style="width:14px;height:14px;"></i> ${saveLabel}`;
            lucide.createIcons();
        }
    }
}

import { state } from './state.js';
import { updateTransactionReview, updateTransactionAssignmentApi, unconfirmTransaction, deleteTransactionApi } from './api.js';
import { formatCurrency, getRulesForCategory } from './utils.js';
import { loadMergeCandidates } from './merge-service.js';

const ASSIGNMENT_TYPES = {
    travel: "travel",
    rentals: "rental_property"
};

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

function assignmentKind(type) {
    return ASSIGNMENT_TYPES[String(type || "").trim().toLowerCase()] || "";
}

function renderGroupedOptions(items, selectedId, labelFn) {
    return items.map(item => {
        const id = item.id || "";
        return `<option value="${escapeHtml(id)}" ${id === selectedId ? "selected" : ""}>${escapeHtml(labelFn(item))}</option>`;
    }).join("");
}

function renderTripSelect(t, disabled, autoSave) {
    const selectedId = t.TripID || "";
    const txYear = String((t.Date || "").slice(0, 4));
    const trips = state.trips || [];
    const sameYear = trips.filter(trip => String(trip.year || "") === txYear && (trip.status || "active") !== "archived");
    const other = trips.filter(trip => String(trip.year || "") !== txYear && (trip.status || "active") !== "archived");
    const currentArchived = trips.filter(trip => trip.id === selectedId && (trip.status || "active") === "archived");
    let options = '<option value="">Unassigned</option>';
    if (sameYear.length) {
        options += `<optgroup label="Suggested">${renderGroupedOptions(sameYear, selectedId, trip => `${trip.year || ""} ${trip.name}`.trim())}</optgroup>`;
    }
    if (other.length) {
        options += `<optgroup label="Other">${renderGroupedOptions(other, selectedId, trip => `${trip.year || ""} ${trip.name}`.trim())}</optgroup>`;
    }
    if (currentArchived.length) {
        options += `<optgroup label="Archived">${renderGroupedOptions(currentArchived, selectedId, trip => `${trip.year || ""} ${trip.name}`.trim())}</optgroup>`;
    }
    return `
        <select class="table-select assignment-select" id="assignment-select-${t.TransactionID}" data-kind="trip" data-autosave="${autoSave ? "1" : "0"}" ${disabled ? "disabled" : ""} onchange="onAssignmentChange('${t.TransactionID}')" onclick="event.stopPropagation()">
            ${options}
        </select>
    `;
}

function renderRentalPropertySelect(t, disabled, autoSave) {
    const selectedId = t.RentalPropertyID || "";
    const properties = state.rentalProperties || [];
    const active = properties.filter(prop => Number(prop.active) !== 0);
    const currentInactive = properties.filter(prop => prop.id === selectedId && Number(prop.active) === 0);
    let options = '<option value="">Unassigned</option>';
    if (active.length) {
        options += renderGroupedOptions(active, selectedId, prop => prop.name);
    }
    if (currentInactive.length) {
        options += `<optgroup label="Inactive">${renderGroupedOptions(currentInactive, selectedId, prop => prop.name)}</optgroup>`;
    }
    return `
        <select class="table-select assignment-select" id="assignment-select-${t.TransactionID}" data-kind="rental_property" data-autosave="${autoSave ? "1" : "0"}" ${disabled ? "disabled" : ""} onchange="onAssignmentChange('${t.TransactionID}')" onclick="event.stopPropagation()">
            ${options}
        </select>
    `;
}

function renderAssignmentSelect(t, selectedType = t.Type) {
    const kind = assignmentKind(selectedType);
    const isPending = t.Pending === 1;
    const autoSave = kind && kind === assignmentKind(t.Type);
    if (kind === "travel") return renderTripSelect(t, isPending, autoSave);
    if (kind === "rental_property") return renderRentalPropertySelect(t, isPending, autoSave);
    return `<span class="text-muted">-</span>`;
}

export function renderTransactionsList() {
    const tbody = document.getElementById("tx-tbody");
    if (!tbody) return;
    
    // 1. Build category options for creator dropdown
    let creatorCatOptionsHtml = "";
    if (state.categoriesConfig && state.categoriesConfig.categories) {
        state.categoriesConfig.categories.slice().sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" })).forEach(cat => {
            const isSelected = cat === 'Other' ? 'selected' : '';
            creatorCatOptionsHtml += `<option value="${cat}" ${isSelected}>${cat}</option>`;
        });
    }

    const creatorHtml = `
        <tr class="create-trigger-row" id="create-trigger-row" onclick="event.stopPropagation()">
            <td colspan="9">
                <div class="create-trigger-btn" onclick="toggleCreatePanel(true)">
                    <i data-lucide="plus-circle" style="width:14px;height:14px;margin-right:6px;vertical-align:middle;"></i>
                    Create manual transaction / quick templates
                </div>
            </td>
        </tr>
        <tr class="create-form-row" id="create-form-row" style="display:none;" onclick="event.stopPropagation()">
            <td><input type="date" id="create-tx-date" class="table-input" style="width:100%;"></td>
            <td style="text-align:center;"><span style="font-size:12px;color:var(--text-muted);font-weight:700;">Legacy</span></td>
            <td><input type="text" id="create-tx-merchant" class="table-input" placeholder="Merchant / description..." style="width:100%;"></td>
            <td>
                <div style="display:flex;align-items:center;gap:4px;">
                    <select id="create-tx-dir" class="table-select" style="padding:0 4px;width:50px;height:36px;border-radius:6px;" onchange="updateCreateSplitPreview()">
                        <option value="outflow">-</option>
                        <option value="inflow">+</option>
                    </select>
                    <input type="number" step="0.01" min="0" id="create-tx-amount" class="table-input" placeholder="Amount..." style="width:100%;" oninput="updateCreateSplitPreview()">
                </div>
            </td>
            <td>
                <select class="table-select" id="create-tx-type" style="width:100%;" onchange="onCreateCategoryChange(false)">
                    ${creatorCatOptionsHtml}
                </select>
            </td>
            <td><select id="create-tx-subtype" class="table-select" style="width:100%;"></select></td>
            <td><span class="text-muted">-</span></td>
            <td><input type="text" id="create-tx-note" class="table-input" placeholder="Note..." style="width:100%;"></td>
            <td style="text-align:center;">
                <div style="display:flex;gap:4px;justify-content:center;">
                    <button class="btn-action-inline btn-confirm-inline" style="background-color:var(--color-success-glow);color:var(--color-success);border-color:var(--color-success);" onclick="submitCreateManual(event)">
                        <i data-lucide="save" style="width:12px;height:12px;"></i> Save
                    </button>
                    <button class="btn-action-inline" style="border-color:var(--text-muted);color:var(--text-muted);" onclick="toggleCreatePanel(false, event)">
                        <i data-lucide="x" style="width:12px;height:12px;"></i>
                    </button>
                </div>
            </td>
        </tr>
        <tr class="create-form-row" id="create-details-row" style="display:none;" onclick="event.stopPropagation()">
            <td colspan="9">
                <div class="review-panel" style="padding: 14px; background-color: var(--bg-main); border-radius: 8px; border: 1px solid var(--border-color);">
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin-bottom: 14px;">
                        <div style="display:flex; flex-direction:column; gap:4px;">
                            <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">Split mode</label>
                            <select class="filter-select" id="create-tx-isb" style="width:100%; height:36px; padding:0 8px; border-radius:6px; background-color:var(--bg-card); color:var(--text-primary); border:1px solid var(--border-color);" onchange="onCreateIsBChange()">
                                <option value="n" selected>Paid by me</option>
                                <option value="y">Split</option>
                                <option value="b">Paid by partner</option>
                            </select>
                        </div>
                        <div style="display:flex; flex-direction:column; gap:4px;">
                            <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">My share ratio</label>
                            <input type="number" step="0.01" min="0" max="1" class="filter-select" id="create-tx-ratio" value="1.0" style="width:100%; height:36px; padding:0 8px; border-radius:6px; background-color:var(--bg-card); color:var(--text-primary); border:1px solid var(--border-color);" disabled oninput="updateCreateSplitPreview()">
                        </div>
                        <div style="display:flex; flex-direction:column; gap:4px;">
                            <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">Reimbursement</label>
                            <input type="number" step="0.01" class="filter-select" id="create-tx-mown" value="0.0" style="width:100%; height:36px; padding:0 8px; border-radius:6px; background-color:var(--bg-card); color:var(--text-primary); border:1px solid var(--border-color);" oninput="updateCreateSplitPreview()">
                        </div>
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div id="create-split-preview" style="font-size:13px; color:var(--text-secondary);"></div>
                        <div style="display:flex;gap:8px;align-items:center;">
                            <span style="font-size:11px;color:var(--text-muted);font-weight:700;text-transform:uppercase;">Quick templates:</span>
                            <button class="btn-quick-create" onclick="applyQuickTemplate('taobao', event)">
                                <i data-lucide="shopping-bag" style="width:12px;height:12px;color:var(--color-warning);"></i> Taobao (-$218.40)
                            </button>
                            <button class="btn-quick-create" onclick="applyQuickTemplate('bpay', event)">
                                <i data-lucide="arrow-down-left" style="width:12px;height:12px;color:var(--color-primary);"></i> Bpay (+$218.40)
                            </button>
                            <button class="btn-quick-create" onclick="applyQuickTemplate('mom', event)">
                                <i data-lucide="heart" style="width:12px;height:12px;color:#ef4444;"></i> Mom transfer (-$500)
                            </button>
                        </div>
                    </div>
                </div>
            </td>
        </tr>
    `;
    tbody.innerHTML = creatorHtml;
    
    if (state.transactions.length === 0) {
        const trEmpty = document.createElement("tr");
        trEmpty.innerHTML = `
            <td colspan="9" style="text-align:center; padding: 40px 20px; color: var(--text-muted);">
                <i data-lucide="inbox" style="width:32px; height:32px; margin-bottom:12px; opacity:0.5;"></i>
                <p style="font-size:14px; font-weight:600;">No matching transactions</p>
                <p style="font-size:12px; margin-top:4px;">Try adjusting filters, or sync the latest bank transactions.</p>
            </td>
        `;
        tbody.appendChild(trEmpty);
        lucide.createIcons();
        updatePaginationUI();
        return;
    }

    state.transactions.forEach(t => {
        const tr = document.createElement("tr");
        tr.className = "tx-row";
        tr.id = `row-${t.TransactionID}`;

        // --- Col 1: Posted date ---
        const dateText = t.Date || t.AuthorizedDate || "";

        // --- Col 2: Account icon based on AccountType ---
        let iconName = "landmark";
        if (t.AccountType === "credit") iconName = "credit-card";
        else if (t.AccountType === "depository") iconName = "wallet";
        else if (t.AccountType === "loan") iconName = "home";
        else if (t.AccountType === "investment") iconName = "trending-up";

        let accountCellHtml;
        if (t.AccountName === 'Legacy') {
            accountCellHtml = `<div class="account-icon-container" title="Legacy manual entry"><i data-lucide="edit-3" style="width:14px;height:14px;"></i></div>`;
        } else {
            const tooltipText = t.InstitutionName ? `${t.InstitutionName} - ${t.AccountName}` : (t.AccountName || 'Unknown account');
            accountCellHtml = `<div class="account-icon-container" title="${tooltipText}"><i data-lucide="${iconName}" style="width:14px;height:14px;"></i></div>`;
        }

        // --- Col 3: Merchant ---
        const merchantHtml = `<span class="merchant-cell" title="${t.Merchant}">${t.Merchant}</span>`;

        // --- Col 4: Amount ---
        const isOut = t.Direction === "outflow";
        const dirPrefix = isOut ? '-' : '+';
        const dirClass = isOut ? 'amount-expense' : 'amount-income';

        // --- Col 5: Type select ---
        const isPending = t.Pending === 1;
        const isConfirmed = t.Reviewed === 1;
        const disabledAttr = (isConfirmed || isPending) ? 'disabled' : '';

        let catOptionsHtml = "";
        state.categoriesConfig.categories.slice().sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" })).forEach(cat => {
            const isSelected = cat.toLowerCase() === (t.Type || '').toLowerCase() ? 'selected' : '';
            catOptionsHtml += `<option value="${cat}" ${isSelected}>${cat}</option>`;
        });

        const typeSelectHtml = `
            <select class="table-select" id="type-select-${t.TransactionID}" ${disabledAttr} onchange="onRowCategoryChange('${t.TransactionID}')" onclick="event.stopPropagation()">
                ${catOptionsHtml}
            </select>
        `;

        // --- Col 6: SubType select (rule-based) ---
        const subtypeSelectHtml = `
            <select class="table-select" id="subtype-input-${t.TransactionID}" ${disabledAttr} onclick="event.stopPropagation()">
            </select>
        `;

        // --- Col 7: Note ---
        const assignmentCellHtml = `<div id="assignment-cell-${t.TransactionID}">${renderAssignmentSelect(t)}</div>`;

        const noteInputHtml = `
            <input type="text" class="table-input" id="note-input-${t.TransactionID}" value="${escapeHtml(t.Note)}" ${disabledAttr} placeholder="Note..." onclick="event.stopPropagation()">
        `;

        // --- Col 8: Action button with Legacy-specific styles ---
        let actionButtonHtml = "";
        if (isPending) {
            actionButtonHtml = `<button class="btn-action-inline" disabled style="background-color: var(--color-warning-glow, #fffbeb); color: var(--color-warning, #d97706); border-color: var(--color-warning, #d97706); cursor: not-allowed; opacity: 0.9;"><i data-lucide="clock" style="width:12px;height:12px;"></i> Pending</button>`;
        } else if (t.Reviewed === 0) {
            actionButtonHtml = `<button class="btn-action-inline btn-confirm-inline" onclick="toggleTransactionConfirm('${t.TransactionID}', event)"><i data-lucide="check-circle" style="width:12px;height:12px;"></i> Review</button>`;
        } else {
            if (t.Type === "Internal Transfer") {
                actionButtonHtml = `<button class="btn-action-inline btn-reviewed-inline" style="background-color: #ecfdf5; color: #10b981; border-color: #10b981;" onclick="toggleTransactionConfirm('${t.TransactionID}', event)"><i data-lucide="check" style="width:12px;height:12px;"></i> Transfer</button>`;
            } else if (t.ImportedFromLegacy === 1 && t.LegacyMatched === 1) {
                actionButtonHtml = `<button class="btn-action-inline btn-reviewed-inline" style="background-color: var(--color-primary-glow, #eff6ff); color: var(--color-primary, #3b82f6); border-color: var(--color-primary, #3b82f6);" onclick="toggleTransactionConfirm('${t.TransactionID}', event)"><i data-lucide="link" style="width:12px;height:12px;"></i> Legacy matched</button>`;
            } else if (t.ImportedFromLegacy === 1 && t.LegacyMatched === 0) {
                actionButtonHtml = `<button class="btn-action-inline btn-reviewed-inline" style="background-color: #faf5ff; color: #a855f7; border-color: #a855f7;" onclick="toggleTransactionConfirm('${t.TransactionID}', event)"><i data-lucide="archive" style="width:12px;height:12px;"></i> Legacy imported</button>`;
            } else if (t.ImportedFromLegacy === 0 && t.AccountName === 'Legacy') {
                actionButtonHtml = `<button class="btn-action-inline btn-reviewed-inline" style="background-color: #f0fdfa; color: #0d9488; border-color: #0d9488;" onclick="toggleTransactionConfirm('${t.TransactionID}', event)"><i data-lucide="edit-3" style="width:12px;height:12px;"></i> Manual</button>`;
            } else {
                actionButtonHtml = `<button class="btn-action-inline btn-reviewed-inline" onclick="toggleTransactionConfirm('${t.TransactionID}', event)"><i data-lucide="check" style="width:12px;height:12px;"></i> Reviewed</button>`;
            }
        }

        // --- Assemble row matching the table header ---
        tr.innerHTML = `
            <td><strong>${dateText}</strong></td>
            <td style="text-align: center;">${accountCellHtml}</td>
            <td>${merchantHtml}</td>
            <td class="${dirClass}" style="text-align: right; font-weight: 700;">${dirPrefix}${formatCurrency(t.Amount)}</td>
            <td>${typeSelectHtml}</td>
            <td>${subtypeSelectHtml}</td>
            <td>${assignmentCellHtml}</td>
            <td>${noteInputHtml}</td>
            <td style="text-align: center;" onclick="event.stopPropagation()">${actionButtonHtml}</td>
        `;
        tbody.appendChild(tr);

        // --- Detail collapsible row ---
        const detailTr = document.createElement("tr");
        detailTr.className = "detail-row";
        detailTr.id = `detail-${t.TransactionID}`;
        detailTr.style.display = "none";

        let locationText = "N/A";
        try {
            const loc = JSON.parse(t.Location || "{}");
            const parts = [loc.city, loc.region, loc.country].filter(Boolean);
            if (parts.length > 0) locationText = parts.join(", ");
        } catch (e) {}

        let plaidCategoriesText = "N/A";
        try {
            const cats = JSON.parse(t.Categories || "[]");
            if (cats && cats.length > 0) plaidCategoriesText = cats.join(" ➔ ");
        } catch(e) {}

        // Status badge for detail metadata row (inline styles matching original)
        let statusBadgeHtml = "";
        if (isPending) {
            statusBadgeHtml = `<span style="background-color: var(--color-warning-glow, #fffbeb); color: var(--color-warning, #d97706); font-size:10px; font-weight:700; padding:2px 6px; border-radius:4px; text-transform:uppercase;">Pending</span>`;
        } else if (t.Reviewed === 0) {
            statusBadgeHtml = `<span style="background-color: var(--color-warning-glow, #fffbeb); color: var(--color-warning, #d97706); font-size:10px; font-weight:700; padding:2px 6px; border-radius:4px; text-transform:uppercase;">Needs review</span>`;
        } else if (t.ImportedFromLegacy === 1 && t.LegacyMatched === 1) {
            statusBadgeHtml = `<span style="background-color: var(--color-primary-glow, #eff6ff); color: var(--color-primary, #3b82f6); font-size:10px; font-weight:700; padding:2px 6px; border-radius:4px; text-transform:uppercase;">Legacy matched</span>`;
        } else if (t.ImportedFromLegacy === 1 && t.LegacyMatched === 0) {
            statusBadgeHtml = `<span style="background-color: #faf5ff; color: #a855f7; font-size:10px; font-weight:700; padding:2px 6px; border-radius:4px; text-transform:uppercase;">Legacy imported</span>`;
        } else if (t.AccountName === 'Legacy') {
            statusBadgeHtml = `<span style="background-color: #f0fdfa; color: #0d9488; font-size:10px; font-weight:700; padding:2px 6px; border-radius:4px; text-transform:uppercase;">Manual</span>`;
        } else {
            statusBadgeHtml = `<span style="background-color: var(--color-success-glow, #ecfdf5); color: var(--color-success, #10b981); font-size:10px; font-weight:700; padding:2px 6px; border-radius:4px; text-transform:uppercase;">Reviewed</span>`;
        }
        const settlementBadgeHtml = t.Pending === 1
            ? `<span style="background-color: var(--color-warning-glow, #fffbeb); color: var(--color-warning, #d97706); font-size:10px; font-weight:700; padding:2px 6px; border-radius:4px; text-transform:uppercase;">Pending</span>`
            : `<span style="background-color: var(--color-success-glow, #ecfdf5); color: var(--color-success, #10b981); font-size:10px; font-weight:700; padding:2px 6px; border-radius:4px; text-transform:uppercase;">Posted</span>`;

        let transferMatchHtml = "";
        if (!isPending && t.Type === "Internal Transfer" && t.TransferCandidate && t.Reviewed === 0) {
            transferMatchHtml = `
            <div style="padding: 10px 14px; background-color: #fffbeb; color: #d97706; border: 1px solid #fcd34d; border-radius: 8px; font-size: 13px; display: flex; align-items: center; gap: 8px; margin-bottom: 4px;" onclick="event.stopPropagation()">
                <i data-lucide="info" style="width:16px; height:16px; flex-shrink:0;"></i>
                <div>
                    <strong>Possible transfer detected.</strong> Matches <strong>${t.TransferCandidate.AccountName}</strong> / <strong>${t.TransferCandidate.Merchant}</strong> (${t.TransferCandidate.Direction === 'inflow' ? '+' : '-'}$${t.TransferCandidate.Amount}).
                </div>
                <button class="btn btn-primary" style="margin-left: auto; height: 28px; padding: 0 10px; font-size: 11px; background-color: #d97706; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: 700;" onclick="window.confirmInternalTransfer('${t.TransactionID}', '${t.TransferCandidate.TransactionID}', event)">Confirm as transfer</button>
            </div>
            `;
        }

        detailTr.innerHTML = `
            <td colspan="9">
                <div class="detail-container" style="display:flex; flex-direction:column; gap:16px;">
                    <!-- Primary Metadata Row -->
                    <div style="display: flex; gap: 24px; font-size:12px; color:var(--text-muted); border-bottom: 1px solid var(--border-color); padding-bottom: 8px; flex-wrap: wrap;">
                        <span><strong>Review:</strong> ${statusBadgeHtml}</span>
                        <span><strong>Settlement:</strong> ${settlementBadgeHtml}</span>
                        <span><strong>Date:</strong> ${t.Date}</span>
                        <span><strong>Authorized:</strong> ${t.AuthorizedDate || 'N/A'}</span>
                        <span><strong>Plaid categories:</strong> ${plaidCategoriesText}</span>
                        <span><strong>Channel:</strong> <span style="text-transform: capitalize;">${t.PaymentChannel || 'N/A'}</span></span>
                        <span><strong>Location:</strong> ${locationText}</span>
                        <span><strong>Account:</strong> ${t.AccountName || 'N/A'}</span>
                        <span style="margin-left: auto;"><strong>Transaction ID:</strong> <span style="font-family:monospace;font-size:11px;">${t.TransactionID}</span></span>
                    </div>
                    
                    ${transferMatchHtml}
                    
                    <!-- Review Split Form -->
                    <div class="review-panel" style="padding: 14px; background-color: var(--bg-main); border-radius: 8px; border: 1px solid var(--border-color);">
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin-bottom: 14px;">
                            <div style="display:flex; flex-direction:column; gap:4px;" onclick="event.stopPropagation()">
                                <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">Split mode</label>
                                <select class="filter-select" id="isb-select-${t.TransactionID}" style="width: 100%; height: 36px; padding: 0 8px; border-radius: 6px; background-color: var(--bg-card); color: var(--text-primary); border: 1px solid var(--border-color);" ${disabledAttr} onchange="updateSplitPreview('${t.TransactionID}', ${t.Amount}, '${t.Direction}')">
                                    <option value="n" ${t.IsB === 'n' ? 'selected' : ''}>Paid by me</option>
                                    <option value="y" ${t.IsB === 'y' ? 'selected' : ''}>Split</option>
                                    <option value="b" ${t.IsB === 'b' ? 'selected' : ''}>Paid by partner</option>
                                </select>
                            </div>
                            <div style="display:flex; flex-direction:column; gap:4px;" onclick="event.stopPropagation()">
                                <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">My share ratio</label>
                                <input type="number" step="0.01" min="0" max="1" class="filter-select" id="ratio-input-${t.TransactionID}" value="${t.Ratio}" style="width: 100%; height: 36px; padding: 0 8px; border-radius: 6px; background-color: var(--bg-card); color: var(--text-primary); border: 1px solid var(--border-color);" ${t.IsB !== 'y' || isConfirmed || isPending ? 'disabled' : ''} oninput="updateSplitPreview('${t.TransactionID}', ${t.Amount}, '${t.Direction}')">
                            </div>
                            <div style="display:flex; flex-direction:column; gap:4px;" onclick="event.stopPropagation()">
                                <label style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">Reimbursement</label>
                                <input type="number" step="0.01" class="filter-select" id="mown-input-${t.TransactionID}" value="${t.Mown}" style="width: 100%; height: 36px; padding: 0 8px; border-radius: 6px; background-color: var(--bg-card); color: var(--text-primary); border: 1px solid var(--border-color);" ${disabledAttr} oninput="updateSplitPreview('${t.TransactionID}', ${t.Amount}, '${t.Direction}')">
                            </div>
                        </div>
                        
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div id="preview-${t.TransactionID}" style="font-size:13px; color:var(--text-secondary);"></div>
                            <div>
                                <button class="btn" ${isPending ? 'disabled' : ''} style="height: 36px; padding: 0 16px; border-radius: 6px; font-weight: 700; cursor: ${isPending ? 'not-allowed' : 'pointer'}; display: inline-flex; align-items: center; gap: 6px; background-color: var(--bg-main); border: 1px solid var(--color-danger, #ef4444); color: var(--color-danger, #ef4444); transition: var(--transition-smooth); opacity: ${isPending ? '0.5' : '1'};" onclick="${isPending ? 'event.stopPropagation()' : `deleteTransaction('${t.TransactionID}', event)`}">
                                    <i data-lucide="trash-2" style="width: 14px; height: 14px;"></i> Delete transaction
                                </button>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Manual Merge Section for Legacy transactions -->
                    ${t.AccountName === 'Legacy' ? `
                    <div class="manual-merge-section" style="padding: 14px; background-color: var(--bg-main); border-radius: 8px; border: 1px solid var(--border-color); display: flex; flex-direction: column; gap: 10px;">
                        <h4 style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; margin:0;">Merge with Plaid transaction</h4>
                        <p class="text-xs" style="color:var(--text-secondary); margin:0;">If this historical transaction has been pulled from Plaid, enter a Plaid transaction ID or choose a suggested match below.</p>
                        <div style="display: flex; gap: 8px; align-items: center;" onclick="event.stopPropagation()">
                            <input type="text" id="manual-plaid-id-${t.TransactionID}" class="table-input" placeholder="Target Plaid transaction ID..." style="max-width: 320px; font-family: monospace; font-size: 11px;">
                            <button class="btn btn-primary" style="height:32px; padding:0 12px; font-size:12px; background-color:var(--color-primary); color:white; border:none; border-radius:6px; cursor:pointer;" onclick="executePreciseMerge('${t.TransactionID}', event)">Merge by ID</button>
                        </div>
                        <div style="border-top: 1px dashed var(--border-color); margin: 4px 0;"></div>
                        <div id="merge-candidates-${t.TransactionID}" style="font-size:12px;">
                            <span style="color:var(--text-muted);">Loading possible Plaid matches...</span>
                        </div>
                    </div>
                    ` : ''}
                </div>
            </td>
        `;
        tbody.appendChild(detailTr);

        // Initialize subtype options and split preview
        onRowCategoryChange(t.TransactionID, true, t.SubType);
        updateSplitPreview(t.TransactionID, t.Amount, t.Direction);

        // Toggle detail on row click
        tr.onclick = () => {
            const isCollapsed = detailTr.style.display === "none";
            detailTr.style.display = isCollapsed ? "table-row" : "none";
            if (isCollapsed && t.AccountName === 'Legacy') {
                loadMergeCandidates(t.TransactionID);
            }
        };
    });

    lucide.createIcons();
    updatePaginationUI();
}

function updatePaginationUI() {
    const firstBtn = document.getElementById("tx-first-btn");
    const prevBtn = document.getElementById("tx-prev-btn");
    const nextBtn = document.getElementById("tx-next-btn");
    const lastBtn = document.getElementById("tx-last-btn");
    const pageInfo = document.getElementById("tx-page-info");

    const isFirst = state.currentPage <= 1;
    const isLast = state.currentPage >= state.totalPages;

    if (firstBtn) firstBtn.disabled = isFirst;
    if (prevBtn) prevBtn.disabled = isFirst;
    if (nextBtn) nextBtn.disabled = isLast;
    if (lastBtn) lastBtn.disabled = isLast;
    if (pageInfo) pageInfo.textContent = `Page ${state.currentPage} of ${state.totalPages}`;
}

export function onRowCategoryChange(txId, isInitial = false, savedSubtype = "") {
    const select = document.getElementById(`type-select-${txId}`);
    const subSelect = document.getElementById(`subtype-input-${txId}`);
    if (!select || !subSelect) return;
    
    const cat = select.value;
    const subcats = getRulesForCategory(cat);
    const isConfirmed = select.disabled;
    
    if (subcats.length === 0) {
        subSelect.disabled = true;
        subSelect.innerHTML = '<option value="">No subcategory</option>';
        subSelect.value = "";
    } else {
        subSelect.disabled = isConfirmed;
        let optionsHtml = '<option value="">Select subcategory...</option>';
        subcats.forEach(sub => {
            optionsHtml += `<option value="${sub}">${sub}</option>`;
        });
        if (savedSubtype && !subcats.includes(savedSubtype)) {
            optionsHtml += `<option value="${savedSubtype}">${savedSubtype}</option>`;
        }
        subSelect.innerHTML = optionsHtml;
        if (isInitial && savedSubtype) {
            subSelect.value = savedSubtype;
        } else if (!isInitial) {
            subSelect.value = "";
        }
    }

    const tx = state.transactions.find(t => t.TransactionID === txId);
    const assignmentCell = document.getElementById(`assignment-cell-${txId}`);
    if (tx && assignmentCell) {
        assignmentCell.innerHTML = renderAssignmentSelect(tx, cat);
    }
}

export async function onAssignmentChange(txId) {
    const select = document.getElementById(`assignment-select-${txId}`);
    if (!select || select.dataset.autosave !== "1") return;

    const value = select.value || "";
    const kind = select.dataset.kind || "";
    const tripId = kind === "trip" ? value : "";
    const rentalPropertyId = kind === "rental_property" ? value : "";
    try {
        const res = await updateTransactionAssignmentApi(txId, tripId, rentalPropertyId);
        if (res.status !== "success") {
            alert("Failed to save assignment: " + res.error);
            const { loadData } = await import('../app.js');
            await loadData({ preserveScroll: true });
            return;
        }
        const tx = state.transactions.find(t => t.TransactionID === txId);
        if (tx) {
            tx.TripID = tripId;
            tx.RentalPropertyID = rentalPropertyId;
        }
    } catch (err) {
        alert("Assignment update failed: " + err.message);
    }
}

export function updateSplitPreview(txId, amount, direction) {
    const isBSelect = document.getElementById(`isb-select-${txId}`);
    const ratioInput = document.getElementById(`ratio-input-${txId}`);
    const mownInput = document.getElementById(`mown-input-${txId}`);
    const previewSpan = document.getElementById(`preview-${txId}`);
    
    if (!isBSelect || !ratioInput || !previewSpan) return;
    
    const isB = isBSelect.value;
    const ratio = parseFloat(ratioInput.value) || 0.0;
    
    // Enable/disable ratio input based on isb
    if (isB === 'y') {
        ratioInput.removeAttribute('disabled');
    } else {
        ratioInput.setAttribute('disabled', 'true');
        if (isB === 'n') ratioInput.value = "1.0";
        else if (isB === 'b') ratioInput.value = "0.0";
    }
    
    const parsedAmount = Math.abs(parseFloat(amount) || 0.0);
    const mown = parseFloat(mownInput?.value) || 0.0;
    let ipay = 0.0;
    let bpay = 0.0;
    
    if (direction === 'inflow') {
        ipay = parsedAmount;
        bpay = 0.0;
    } else {
        if (isB === 'y') {
            ipay = parsedAmount * ratio;
            bpay = parsedAmount * (1.0 - ratio);
        } else if (isB === 'b') {
            ipay = 0.0;
            bpay = parsedAmount;
        } else {
            ipay = parsedAmount;
            bpay = 0.0;
        }
    }
    
    previewSpan.innerHTML = `
        <span>Mine: <strong style="color:var(--color-danger);">-$${ipay.toFixed(2)}</strong></span>
        <span style="margin-left:12px;">Partner share: <strong style="color:var(--text-muted);">-$${bpay.toFixed(2)}</strong></span>
        <span style="margin-left:12px;color:var(--color-primary);">Reimbursement: <strong>$${mown.toFixed(2)}</strong></span>
    `;
}

export async function submitTransactionReview(txId, event) {
    if (event) event.stopPropagation();
    
    const type = document.getElementById(`type-select-${txId}`)?.value;
    const subtype = (document.getElementById(`subtype-input-${txId}`)?.value || '').trim();
    const note = (document.getElementById(`note-input-${txId}`)?.value || '').trim();
    const isB = document.getElementById(`isb-select-${txId}`)?.value || 'n';
    const ratio = parseFloat(document.getElementById(`ratio-input-${txId}`)?.value) || 1.0;
    const mown = parseFloat(document.getElementById(`mown-input-${txId}`)?.value) || 0.0;
    const assignmentSelect = document.getElementById(`assignment-select-${txId}`);
    const assignmentKindValue = assignmentSelect?.dataset.kind || "";
    const assignmentValue = assignmentSelect?.value || "";
    const tripId = assignmentKindValue === "trip" ? assignmentValue : "";
    const rentalPropertyId = assignmentKindValue === "rental_property" ? assignmentValue : "";
    
    try {
        const res = await updateTransactionReview(txId, type, isB, ratio, mown, note, subtype, tripId, rentalPropertyId);
        if (res.status === "success") {
            const { loadData } = await import('../app.js');
            await loadData({ preserveScroll: true });
        } else {
            alert("Failed to save review: " + res.error);
        }
    } catch (err) {
        alert("Review update failed: " + err.message);
    }
}

export async function toggleTransactionConfirm(txId, event) {
    if (event) event.stopPropagation();
    
    // Find the transaction to check current state
    const tx = state.transactions.find(t => t.TransactionID === txId);
    if (!tx) return;
    
    if (tx.Reviewed === 1) {
        // Currently confirmed → unconfirm
        try {
            const res = await unconfirmTransaction(txId);
            if (res.status === "success") {
                const { loadData } = await import('../app.js');
                await loadData({ preserveScroll: true });
            } else {
                alert("Failed to reset review status: " + res.error);
            }
        } catch (err) {
            alert("Failed to reset review: " + err.message);
        }
    } else {
        // Currently unconfirmed → confirm
        await submitTransactionReview(txId);
    }
}

export async function deleteTransaction(txId, event) {
    if (event) event.stopPropagation();
    
    if (!confirm("Delete this transaction?\n\nThis cannot be undone. If this transaction came from Plaid, it may reappear after the next sync.")) {
        return;
    }
    
    try {
        const res = await deleteTransactionApi(txId);
        if (res.status === "success") {
            const { loadData } = await import('../app.js');
            await loadData({ preserveScroll: true });
        } else {
            alert("Delete failed: " + res.error);
        }
    } catch (err) {
        alert("Delete error: " + err.message);
    }
}


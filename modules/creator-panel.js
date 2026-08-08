import { state } from './state.js';
import { checkDuplicateApi, createManualTransactionApi } from './api.js';
import { getRulesForCategory } from './utils.js';

export function applyQuickTemplate(name, event) {
    if (event) event.stopPropagation();
    
    const dateInput = document.getElementById("create-tx-date");
    const merchantInput = document.getElementById("create-tx-merchant");
    const dirInput = document.getElementById("create-tx-dir");
    const amountInput = document.getElementById("create-tx-amount");
    const typeInput = document.getElementById("create-tx-type");
    const noteInput = document.getElementById("create-tx-note");
    const subtypeInput = document.getElementById("create-tx-subtype");
    
    const isbSelect = document.getElementById("create-tx-isb");
    const ratioInput = document.getElementById("create-tx-ratio");
    const mownInput = document.getElementById("create-tx-mown");
    
    dateInput.value = new Date().toISOString().substring(0, 10);
    
    if (name === "taobao") {
        merchantInput.value = "Taobao";
        dirInput.value = "outflow";
        amountInput.value = "218.40";
        typeInput.value = "Shopping";
        onCreateCategoryChange(true);
        subtypeInput.value = "";
        noteInput.value = "damn";
        isbSelect.value = "n";
        mownInput.value = "0.0";
    } else if (name === "bpay") {
        merchantInput.value = "bpay";
        dirInput.value = "inflow";
        amountInput.value = "218.40";
        typeInput.value = "Income";
        onCreateCategoryChange(true);
        subtypeInput.value = "";
        noteInput.value = "note";
        isbSelect.value = "n";
        mownInput.value = "0.0";
    } else if (name === "mom") {
        merchantInput.value = "Mom Retire";
        dirInput.value = "outflow";
        amountInput.value = "500.00";
        typeInput.value = "Mom";
        onCreateCategoryChange(true);
        subtypeInput.value = "";
        noteInput.value = "Retire";
        isbSelect.value = "n";
        mownInput.value = "150.00";
    }
    
    onCreateIsBChange();
}

export function toggleCreatePanel(open, event) {
    if (event) event.stopPropagation();
    
    const triggerRow = document.getElementById("create-trigger-row");
    const formRow = document.getElementById("create-form-row");
    const detailsRow = document.getElementById("create-details-row");
    
    if (!triggerRow || !formRow || !detailsRow) return;
    
    if (open) {
        const dateInput = document.getElementById("create-tx-date");
        if (dateInput && !dateInput.value) {
            dateInput.value = new Date().toISOString().substring(0, 10);
        }
        
        triggerRow.style.display = "none";
        formRow.style.display = "table-row";
        detailsRow.style.display = "table-row";
        
        // Reset defaults
        document.getElementById("create-tx-merchant").value = "";
        document.getElementById("create-tx-amount").value = "";
        document.getElementById("create-tx-type").value = "Other";
        onCreateCategoryChange(true);
        document.getElementById("create-tx-subtype").value = "";
        document.getElementById("create-tx-note").value = "";
        document.getElementById("create-tx-isb").value = "n";
        document.getElementById("create-tx-ratio").value = "1.0";
        document.getElementById("create-tx-ratio").disabled = true;
        document.getElementById("create-tx-mown").value = "0.0";
        document.getElementById("create-tx-reimbursement").checked = false;
        
        updateCreateSplitPreview();
        lucide.createIcons();
    } else {
        triggerRow.style.display = "table-row";
        formRow.style.display = "none";
        detailsRow.style.display = "none";
    }
}

export function onCreateIsBChange() {
    const isbSelect = document.getElementById("create-tx-isb");
    const ratioInput = document.getElementById("create-tx-ratio");
    
    if (!isbSelect || !ratioInput) return;
    
    if (isbSelect.value === 'y') {
        ratioInput.disabled = false;
        ratioInput.value = "0.5";
    } else {
        ratioInput.disabled = true;
        ratioInput.value = "1.0";
    }
    updateCreateSplitPreview();
}

export function updateCreateSplitPreview() {
    const amountVal = parseFloat(document.getElementById("create-tx-amount").value) || 0.0;
    const direction = document.getElementById("create-tx-dir").value;
    const isb = document.getElementById("create-tx-isb").value;
    const ratioVal = parseFloat(document.getElementById("create-tx-ratio").value) || 1.0;
    const mownVal = parseFloat(document.getElementById("create-tx-mown").value) || 0.0;
    
    const previewContainer = document.getElementById("create-split-preview");
    if (!previewContainer) return;
    
    if (direction === 'inflow') {
        previewContainer.innerHTML = `<span style="color: var(--color-success); font-weight:700;">+ $${amountVal.toFixed(2)} (Income)</span>`;
        return;
    }
    
    let ipay = 0.0;
    let bpay = 0.0;
    
    if (isb === 'y') {
        ipay = -amountVal * ratioVal;
        bpay = -amountVal * (1.0 - ratioVal);
    } else if (isb === 'b') {
        ipay = 0.0;
        bpay = -amountVal;
    } else {
        ipay = -amountVal;
        bpay = 0.0;
    }
    
    previewContainer.innerHTML = `
            <span style="font-weight:700;">Mine (ipay): <span style="color:var(--color-danger);">$${Math.abs(ipay).toFixed(2)}</span></span>
            <span style="margin-left:12px;font-weight:700;">Partner share (bpay): <span style="color:var(--text-muted);">$${Math.abs(bpay).toFixed(2)}</span></span>
            <span style="margin-left:12px;font-weight:700;color:var(--color-primary);">Reimbursement (mown): $${mownVal.toFixed(2)}</span>
    `;
}

export async function submitCreateManual(event) {
    if (event) event.stopPropagation();
    
    const date = document.getElementById("create-tx-date").value;
    const merchant = document.getElementById("create-tx-merchant").value.trim();
    const direction = document.getElementById("create-tx-dir").value;
    const amountVal = parseFloat(document.getElementById("create-tx-amount").value);
    const type = document.getElementById("create-tx-type").value;
    const subtype = document.getElementById("create-tx-subtype").value.trim();
    const note = document.getElementById("create-tx-note").value.trim();
    const isB = document.getElementById("create-tx-isb").value;
    const ratio = parseFloat(document.getElementById("create-tx-ratio").value) || 1.0;
    const mown = parseFloat(document.getElementById("create-tx-mown").value) || 0.0;
    const isReimbursement = document.getElementById("create-tx-reimbursement").checked;
    
    if (!merchant || isNaN(amountVal) || amountVal <= 0) {
        alert("Enter a valid merchant and amount.");
        return;
    }
    
    // Check duplicate
    try {
        const dupRes = await checkDuplicateApi(merchant, date);
        if (dupRes.exists) {
            if (!confirm(`Possible duplicate: ${dupRes.count} transaction(s) for "${merchant}" already exist in ${date.substring(0, 7)}.\n\nCreate this transaction anyway?`)) {
                return;
            }
        }
    } catch(err) {
        console.error("Duplicate checking error:", err);
    }
    
    try {
        const res = await createManualTransactionApi({
            date,
            merchant,
            direction,
            amount: amountVal,
            type,
            subtype,
            note,
            is_b: isB,
            ratio,
            mown,
            is_reimbursement: isReimbursement,
            reviewed: 1
        });
        
        if (res.status === "success") {
            alert("Manual transaction saved.");
            toggleCreatePanel(false);
            const { loadData } = await import('../app.js');
            await loadData();
        } else {
            alert("Save failed: " + res.error);
        }
    } catch (err) {
        alert("Manual transaction save failed: " + err.message);
    }
}

export function onCreateCategoryChange(isInitial = false) {
    const select = document.getElementById("create-tx-type");
    const subSelect = document.getElementById("create-tx-subtype");
    if (!select || !subSelect) return;
    
    const cat = select.value;
    const subcats = getRulesForCategory(cat);
    
    if (subcats.length === 0) {
        subSelect.disabled = true;
        subSelect.innerHTML = '<option value="">No subcategory</option>';
        subSelect.value = "";
    } else {
        subSelect.disabled = false;
        let optionsHtml = '<option value="">Select subcategory...</option>';
        subcats.forEach(sub => {
            optionsHtml += `<option value="${sub}">${sub}</option>`;
        });
        subSelect.innerHTML = optionsHtml;
        subSelect.value = "";
    }
}

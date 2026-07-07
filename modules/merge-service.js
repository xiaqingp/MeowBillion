import { fetchMergeCandidates, mergeTransactionsApi } from './api.js';
import { formatCurrency } from './utils.js';

export async function loadMergeCandidates(legacyId) {
    const container = document.getElementById(`merge-candidates-${legacyId}`);
    if (!container) return;

    try {
        const candidates = await fetchMergeCandidates(legacyId);
        if (candidates.error) {
            container.innerHTML = `<span class="text-danger">Failed to load candidates: ${candidates.error}</span>`;
            return;
        }
        if (candidates.length === 0) {
            container.innerHTML = `<span style="color:var(--text-muted); font-size:11px;">No nearby unreviewed Plaid candidates within 15 days.</span>`;
            return;
        }

        let html = `<ul style="list-style:none; padding:0; display:flex; flex-direction:column; gap:8px; margin: 8px 0 0 0;">`;
        candidates.forEach(c => {
            const statusTag = c.reviewed === 1
                ? '<span style="background-color: var(--color-success-glow); color: var(--color-success); font-size:9px; padding:2px 4px; border-radius:4px; font-weight:700;">Reviewed</span>'
                : '<span style="background-color: var(--color-warning-glow); color: var(--color-warning); font-size:9px; padding:2px 4px; border-radius:4px; font-weight:700;">Needs review</span>';
            const diffDaysText = c.date_diff === 0 ? "Same day" : `${c.date_diff} days apart`;

            html += `
                <li style="display:flex; justify-content:space-between; align-items:center; background-color:var(--bg-card); padding:8px 12px; border-radius:6px; border:1px solid var(--border-color);" onclick="event.stopPropagation()">
                    <span style="color: var(--text-primary);">
                        <strong>${c.date}</strong> - <span style="color:var(--text-secondary);">${c.merchant}</span> (${c.account_name})
                        <strong class="${c.direction === 'outflow' ? 'amount-expense' : 'amount-income'}" style="margin-left:8px;">
                            ${c.direction === 'outflow' ? '-' : '+'}${formatCurrency(c.amount)}
                        </strong>
                        <span style="margin-left:12px; font-size:11px; color: var(--text-muted);">${diffDaysText}</span>
                        <span style="margin-left:8px;">${statusTag}</span>
                    </span>
                    <button class="btn btn-primary" style="height:26px; padding:0 8px; font-size:11px; background-color:var(--color-primary); color:white; border:none; border-radius:4px; cursor:pointer;" onclick="executeManualMerge('${legacyId}', '${c.transaction_id}', event)">
                        Merge
                    </button>
                </li>
            `;
        });
        html += `</ul>`;
        container.innerHTML = html;
    } catch (err) {
        container.innerHTML = `<span class="text-danger">Candidate request failed: ${err.message}</span>`;
    }
}

export async function executeManualMerge(legacyId, plaidId, event) {
    if (event) event.stopPropagation();

    if (!confirm("Merge this Legacy transaction into the selected Plaid transaction?\n\nThis will copy the historical category, split, and note onto the Plaid transaction, then delete this Legacy transaction.")) {
        return;
    }

    try {
        const res = await mergeTransactionsApi(legacyId, plaidId);
        if (res.status === "success") {
            alert("Merge complete.");
            const { loadData } = await import('../app.js');
            await loadData();
        } else {
            alert("Merge failed: " + res.error);
        }
    } catch (err) {
        console.error("Merge error:", err);
        alert("Unable to submit merge request: " + err.message);
    }
}

export async function executePreciseMerge(legacyId, event) {
    if (event) event.stopPropagation();

    const plaidIdInput = document.getElementById(`manual-plaid-id-${legacyId}`);
    if (!plaidIdInput) return;

    const plaidId = plaidIdInput.value.trim();
    if (!plaidId) {
        alert("Enter a target Plaid transaction ID.");
        return;
    }

    if (!confirm(`Merge this Legacy transaction into Plaid transaction ID [${plaidId}]?\n\nThis will copy the historical category, split, and note onto the Plaid transaction, then delete this Legacy transaction.`)) {
        return;
    }

    try {
        const res = await mergeTransactionsApi(legacyId, plaidId);
        if (res.status === "success") {
            alert("Merge complete.");
            const { loadData } = await import('../app.js');
            await loadData();
        } else {
            alert("Merge failed: " + res.error);
        }
    } catch (err) {
        console.error("Merge error:", err);
        alert("Unable to submit merge request: " + err.message);
    }
}

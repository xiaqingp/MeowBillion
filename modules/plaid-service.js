import { 
    createLinkTokenApi, 
    exchangePublicTokenApi, 
    fetchAccountsApi, 
    syncTransactionsApi, 
    disconnectAccountsApi 
} from './api.js';
import { formatCurrency } from './utils.js';

export async function loadAccounts() {
    try {
        const accounts = await fetchAccountsApi();
        renderAccountsList(accounts);
    } catch (err) {
        console.error("Failed to load bank accounts:", err);
    }
}

export function renderAccountsList(accounts) {
    const listContainer = document.getElementById("accounts-list");
    if (!listContainer) return;

    listContainer.innerHTML = "";

    if (accounts.length === 0) {
        listContainer.innerHTML = `
            <div style="text-align:center; padding: 20px; color: var(--text-muted);">
                <i data-lucide="info" style="width:24px; height:24px; margin-bottom:8px; opacity:0.5;"></i>
                <p style="font-size:12px;">No linked bank accounts yet.<br>Use Plaid Settings to link a bank.</p>
            </div>
        `;
        lucide.createIcons();
        return;
    }

    accounts.forEach(acc => {
        const item = document.createElement("div");
        item.className = "bank-item";

        const isVirtual = acc.is_virtual === true;
        const isCredit = acc.type === "credit";
        const available = acc.balance_available != null ? acc.balance_available : 0.0;
        const current = acc.balance_current != null ? acc.balance_current : 0.0;

        let bal = 0.0;
        if (isVirtual) {
            bal = current;
        } else if (isCredit) {
            bal = -current;
        } else {
            bal = acc.balance_available != null ? available : current;
        }

        const balClass = bal < 0 ? 'balance-negative' : '';
        const symbol = bal < 0 ? '-' : '';

        item.innerHTML = `
            <div style="display:flex; flex-direction:column; gap:4px; max-width: 60%;">
                <span class="bank-name">${acc.name}</span>
                <span class="account-type">${acc.official_name || acc.subtype}</span>
            </div>
            <div class="bank-balance ${balClass}">
                ${symbol}$${formatCurrency(bal)}
            </div>
        `;
        listContainer.appendChild(item);
    });
    lucide.createIcons();
}

export async function syncPlaidTransactions() {
    const syncBtn = document.getElementById("settings-sync-btn") || document.getElementById("btn-sync");
    if (syncBtn) {
        syncBtn.disabled = true;
        syncBtn.innerHTML = '<i data-lucide="loader-2" class="spin" style="width:14px;height:14px;"></i> Syncing...';
        lucide.createIcons();
    }

    try {
        const res = await syncTransactionsApi();
        if (res.status === "success") {
            alert(`Sync complete. Imported ${res.new_transactions_count} new transactions.`);
            const { loadData } = await import('../app.js');
            await loadData({ refreshOverview: true });
        } else if (res.status === "partial_success") {
            alert(`Sync partially completed. Imported ${res.new_transactions_count || 0} new transactions. ${(res.failed_items || []).length} institution needs attention.`);
            const { loadData } = await import('../app.js');
            await loadData({ refreshOverview: true });
        } else if (res.status === "failed") {
            alert(`Sync failed. ${(res.failed_items || []).length} institutions need attention.`);
        } else {
            alert("Sync failed: " + res.error);
        }
    } catch (err) {
        alert("Sync failed: " + err.message);
    } finally {
        if (syncBtn) {
            syncBtn.disabled = false;
            syncBtn.innerHTML = '<i data-lucide="refresh-cw" style="width:14px;height:14px;"></i> Sync now';
            lucide.createIcons();
        }
    }
}

export async function handleDisconnect() {
    if (!confirm("Disconnect all linked institutions?\n\nThis stops future automatic syncs but keeps all local transaction history and classifications. This cannot be undone from the app.")) {
        return;
    }

    try {
        const res = await disconnectAccountsApi();
        if (res.status === "success") {
            alert("All Plaid connections were disconnected. Local transaction history was kept.");
            const { loadData } = await import('../app.js');
            await loadData();
        } else {
            alert("Disconnect failed: " + res.error);
        }
    } catch (err) {
        alert("Disconnect failed: " + err.message);
    }
}

export async function linkNewBank() {
    try {
        const data = await createLinkTokenApi();
        if (data.error) {
            alert("Unable to create a Plaid Link token: " + data.error);
            return;
        }

        const handler = Plaid.create({
            token: data.link_token,
            onSuccess: async (public_token) => {
                try {
                    const res = await exchangePublicTokenApi(public_token);
                    if (res.status === "success") {
                        alert("Bank linked successfully. Syncing transactions...");
                        await syncPlaidTransactions();
                    } else {
                        alert("Token exchange failed: " + res.error);
                    }
                } catch (err) {
                    alert("Token exchange failed: " + err.message);
                }
            },
            onExit: (err) => {
                if (err != null) {
                    console.error("Plaid Link Exit Error:", err);
                }
            }
        });

        handler.open();
    } catch (err) {
        alert("Unable to start Plaid Link: " + err.message);
    }
}

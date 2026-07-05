export async function fetchCredentialsStatus() {
    const res = await fetch("/api/credentials_status");
    return await res.json();
}

export async function fetchTransactions(page, limit, filters) {
    const queryParams = new URLSearchParams({
        page,
        limit,
        query: filters.search || "",
        direction: filters.direction || "all",
        category: filters.category || "all",
        reviewed_filter: filters.reviewed || "unreviewed",
        start_date: filters.startDate || "",
        end_date: filters.endDate || "",
        account: filters.account || "all",
        amount: filters.amount || ""
    });
    const res = await fetch(`/api/transactions?${queryParams}`);
    return await res.json();
}

export async function fetchTransactionFilterOptionsApi() {
    const res = await fetch("/api/transaction_filter_options");
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    return await res.json();
}

export async function fetchMonthlyAnalysisApi() {
    const res = await fetch("/api/monthly_analysis");
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    return await res.json();
}

export async function fetchTravelAnalysisApi() {
    const res = await fetch("/api/travel_analysis");
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    return await res.json();
}

export async function fetchRentalAnalysisApi() {
    const res = await fetch("/api/rental_analysis");
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    return await res.json();
}

export async function updateTransactionReview(txId, type, isB, ratio, mown, note, subtype) {
    const res = await fetch("/api/update_transaction", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            transaction_id: txId,
            type,
            is_b: isB,
            ratio,
            mown,
            note,
            subtype
        })
    });
    return await res.json();
}

export async function unconfirmTransaction(txId) {
    const res = await fetch("/api/unconfirm_transaction", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transaction_id: txId })
    });
    return await res.json();
}

export async function deleteTransactionApi(txId) {
    const res = await fetch("/api/delete_transaction", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transaction_id: txId })
    });
    return await res.json();
}

export async function fetchMergeCandidates(legacyId) {
    const res = await fetch(`/api/merge_candidates?legacy_id=${legacyId}`);
    return await res.json();
}

export async function mergeTransactionsApi(legacyId, plaidId) {
    const res = await fetch("/api/merge_transactions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ legacy_id: legacyId, plaid_id: plaidId })
    });
    return await res.json();
}

export async function createManualTransactionApi(data) {
    const res = await fetch("/api/create_manual_transaction", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
    });
    return await res.json();
}

export async function fetchCategoriesConfig() {
    const res = await fetch("/api/config/categories");
    return await res.json();
}

export async function saveCategoriesConfigApi(config) {
    const res = await fetch("/api/config/categories", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config)
    });
    return await res.json();
}

export async function checkDuplicateApi(merchant, date) {
    const res = await fetch(`/api/check_duplicate?merchant=${encodeURIComponent(merchant)}&date=${date}`);
    return await res.json();
}

export async function disconnectAccountsApi() {
    const res = await fetch("/api/disconnect", { method: "POST" });
    return await res.json();
}

export async function createLinkTokenApi() {
    const res = await fetch("/api/create_link_token", { method: "POST" });
    return await res.json();
}

export async function exchangePublicTokenApi(publicToken) {
    const res = await fetch("/api/exchange_public_token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ public_token: publicToken })
    });
    return await res.json();
}

export async function fetchAccountsApi() {
    const res = await fetch("/api/accounts");
    return await res.json();
}

export async function syncTransactionsApi() {
    const res = await fetch("/api/sync_transactions", { method: "POST" });
    return await res.json();
}

export async function confirmTransferApi(txId1, txId2) {
    const res = await fetch("/api/confirm_transfer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tx_id_1: txId1, tx_id_2: txId2 })
    });
    return await res.json();
}

export async function fetchBalanceHistoryApi() {
    const res = await fetch("/api/balance_history");
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    return await res.json();
}

export async function fetchAllocationHistoryApi() {
    const res = await fetch("/api/allocation_history");
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    return await res.json();
}

export async function fetchConnectionsApi() {
    const res = await fetch("/api/connections");
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    return await res.json();
}

export async function disconnectItemApi(itemId) {
    const res = await fetch("/api/disconnect_item", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ item_id: itemId })
    });
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    return await res.json();
}

export async function fetchPortfolioAllocationApi() {
    const res = await fetch("/api/portfolio_allocation");
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    return await res.json();
}

export async function fetchPortfolioAllocationDetailsApi(params = {}) {
    const query = new URLSearchParams();
    if (params.item_id) query.set("item_id", params.item_id);
    if (params.institution) query.set("institution", params.institution);
    const suffix = query.toString() ? `?${query.toString()}` : "";
    const res = await fetch(`/api/portfolio_allocation_details${suffix}`);
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    return await res.json();
}

export async function fetchAllocationAccountsApi() {
    const res = await fetch("/api/allocation_accounts");
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    return await res.json();
}

export async function saveAllocationOverrideApi(accountId, percentages, clear = false) {
    const res = await fetch("/api/allocation_overrides", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ account_id: accountId, percentages, clear })
    });
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    return await res.json();
}

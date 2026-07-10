import { state } from './modules/state.js';
import { 
    fetchCredentialsStatus, 
    fetchTransactions, 
    fetchAccountsApi, 
    fetchCategoriesConfig,
    confirmTransferApi,
    fetchBalanceHistoryApi,
    fetchAllocationHistoryApi,
    fetchConnectionsApi,
    disconnectItemApi,
    fetchPortfolioAllocationApi,
    fetchPortfolioAllocationDetailsApi,
    fetchAllocationAccountsApi,
    fetchAccountBalanceHistoryApi,
    saveAllocationOverrideApi,
    fetchTransactionFilterOptionsApi,
    fetchMonthlyAnalysisApi,
    fetchTravelAnalysisApi,
    fetchRentalAnalysisApi,
    fetchAuthStatusApi,
    loginApi,
    signupApi,
    logoutApi,
    fetchPlaidCredentialsApi,
    savePlaidCredentialsApi,
    fetchSyncScheduleApi,
    saveSyncScheduleApi,
    fetchTripsApi,
    createTripApi,
    updateTripApi,
    deleteTripApi,
    fetchRentalPropertiesApi,
    createRentalPropertyApi,
    updateRentalPropertyApi,
    deleteRentalPropertyApi,
    fetchRentalPropertyRulesApi,
    createRentalPropertyRuleApi,
    updateRentalPropertyRuleApi,
    deleteRentalPropertyRuleApi,
    applyRentalPropertyRulesApi
} from './modules/api.js';
import { 
    loadAccounts, 
    syncPlaidTransactions, 
    handleDisconnect, 
    linkNewBank,
    renderAccountsList
} from './modules/plaid-service.js';
import { 
    renderCategoryConfigView, 
    addNewCategory, 
    deleteCategory, 
    onConfigRuleCategoryChange, 
    addNewSubcategory, 
    deleteSubcategory, 
    saveCategoriesConfig 
} from './modules/config-view.js';
import { 
    loadMergeCandidates, 
    executeManualMerge, 
    executePreciseMerge 
} from './modules/merge-service.js';
import { 
    applyQuickTemplate, 
    toggleCreatePanel, 
    onCreateIsBChange, 
    updateCreateSplitPreview, 
    submitCreateManual, 
    onCreateCategoryChange 
} from './modules/creator-panel.js';
import { 
    renderTransactionsList, 
    updateSplitPreview, 
    submitTransactionReview, 
    toggleTransactionConfirm, 
    deleteTransaction, 
    onRowCategoryChange,
    onAssignmentChange
} from './modules/transaction-renderer.js';
import { 
    formatCurrency, 
    enableResizableColumns,
    initCustomMultiselects,
    populateCategoryMultiselectOptions,
    populateStatusMultiselectOptions,
    getMultiselectValues
} from './modules/utils.js';

// DOM READY Check
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => initApp());
} else {
    initApp();
}

window.addEventListener("categories-config-saved", () => {
    updateCategoryFilterOptions();
});

async function safeFetch(promise, fallbackValue) {
    try {
        return await promise;
    } catch (e) {
        console.warn("Safe fetch failed:", e);
        return fallbackValue;
    }
}

function debounce(fn, delay = 300) {
    let timer = null;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), delay);
    };
}

function getScrollSnapshot(selector) {
    const selected = selector ? document.querySelector(selector) : null;
    const el = selected || document.querySelector(".main-content") || document.scrollingElement || document.documentElement;
    const isWindowScroll = el === document.scrollingElement || el === document.documentElement || el === document.body;
    return {
        el,
        isWindowScroll,
        top: isWindowScroll ? window.scrollY : el.scrollTop,
        left: isWindowScroll ? window.scrollX : el.scrollLeft
    };
}

function restoreScrollSnapshot(snapshot) {
    if (!snapshot?.el) return;
    requestAnimationFrame(() => {
        if (snapshot.isWindowScroll) {
            window.scrollTo({ top: snapshot.top, left: snapshot.left, behavior: "auto" });
        } else {
            snapshot.el.scrollTop = snapshot.top;
            snapshot.el.scrollLeft = snapshot.left;
        }
    });
}

function normalizeCategoryConfig(config) {
    const normalized = config || { categories: [], rules: {} };
    normalized.categories = (normalized.categories || []).slice().sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));
    return normalized;
}

async function initApp() {
    const tStart = performance.now();
    lucide.createIcons();

    const auth = await fetchAuthStatusApi();
    if (!auth.authenticated) {
        showAuthScreen(auth);
        return;
    }
    showApp(auth.user);

    // 1. Setup static UI events and elements early so page is instantly responsive
    setupRouting();
    setupFilters();
    setupSidebarCollapser();

    // Show initial loading spinner in table
    const tbody = document.getElementById("tx-tbody");
    if (tbody) {
        tbody.innerHTML = `
            <tr>
                <td colspan="9" style="text-align:center; padding: 48px; color: var(--text-muted);">
                    <i data-lucide="loader-2" class="spin" style="width:24px; height:24px; margin-bottom:8px; display:inline-block;"></i>
                    <div>Loading transactions...</div>
                </td>
            </tr>
        `;
        lucide.createIcons();
    }

    try {
        // 2. Fetch all configuration and transactions data in parallel to avoid sequential round-trips
        const [config, txData, accounts, plaidStatus, connections, trips, rentalProperties] = await Promise.all([
            safeFetch(fetchCategoriesConfig(), { categories: [], rules: {} }),
            safeFetch(fetchTransactions(state.currentPage, state.limit, state.currentFilters), { transactions: [], total_pages: 1, page: 1, total_count: 0 }),
            safeFetch(fetchAccountsApi(), []),
            safeFetch(fetchCredentialsStatus(), { has_credentials: false, env: 'N/A', last_sync_time: 'N/A' }),
            safeFetch(fetchConnectionsApi(), []),
            safeFetch(fetchTripsApi(), []),
            safeFetch(fetchRentalPropertiesApi(), [])
        ]);

        // 3. Save loaded states
        state.categoriesConfig = normalizeCategoryConfig(config);
        state.transactions = txData.transactions || [];
        state.totalPages = txData.total_pages || 1;
        state.currentPage = txData.page || 1;
        state.totalCount = txData.total_count || 0;
        state.accounts = accounts || [];
        state.trips = trips || [];
        state.rentalProperties = rentalProperties || [];

        // 4. Update dropdown filter categories
        await updateCategoryFilterOptions();
        await updateTransactionFilterOptions();

        // 5. Render dashboard and tables
        renderDashboard(state.accounts);
        initializeNetWorthRangeControl();
        initializeResponsiveChartResizing();
        renderBalanceTrendChart();
        renderAssetAllocationChart();
        renderInstitutionAllocationDetails();
        renderMonthlyAnalysis();
        renderTripManager();
        renderRentalManager();
        await renderRentalRuleManager();
        renderTravelAnalysis();
        renderRentalAnalysis();
        renderTransactionsList();
        renderAccountsList(state.accounts);
        renderPlaidConnections(state.accounts, connections);
        renderCategoryConfigView();
        enableResizableColumns();

        // 6. Bind Plaid configuration elements using pre-fetched status
        await checkPlaidConfiguration(plaidStatus);

        const duration = performance.now() - tStart;
        console.log(`[Performance] initApp completed in ${duration.toFixed(1)}ms`);
        const badge = document.getElementById("load-time-badge");
        if (badge) {
            badge.textContent = `(Loaded in ${duration.toFixed(0)}ms)`;
        }

    } catch (err) {
        console.error("Initialization error:", err);
    }
}

function showApp(user) {
    const authScreen = document.getElementById("auth-screen");
    const appContainer = document.querySelector(".app-container");
    if (authScreen) authScreen.style.display = "none";
    if (appContainer) appContainer.style.display = "flex";
    const nameEl = document.getElementById("sidebar-user-name");
    if (nameEl) nameEl.textContent = user?.display_name || user?.email || "MeowBillion";
    const signoutBtn = document.getElementById("signout-btn");
    if (signoutBtn) {
        signoutBtn.onclick = async () => {
            await logoutApi();
            window.location.reload();
        };
    }
}

function showAuthScreen(auth) {
    const authScreen = document.getElementById("auth-screen");
    const appContainer = document.querySelector(".app-container");
    if (authScreen) authScreen.style.display = "flex";
    if (appContainer) appContainer.style.display = "none";

    let mode = auth.setup_required ? "setup" : "login";
    const title = document.getElementById("auth-title");
    const copy = document.getElementById("auth-copy");
    const nameInput = document.getElementById("auth-name");
    const emailInput = document.getElementById("auth-email");
    const passwordInput = document.getElementById("auth-password");
    const errorEl = document.getElementById("auth-error");
    const submitBtn = document.getElementById("auth-submit-btn");
    const switchBtn = document.getElementById("auth-switch-btn");

    function setMode(nextMode) {
        mode = nextMode;
        const isSetup = mode === "setup";
        const isSignup = mode === "signup";
        if (title) title.textContent = isSetup ? "Set up MeowBillion" : (isSignup ? "Create account" : "Sign in");
        if (copy) copy.textContent = isSetup ? "Create the first admin account and claim existing data." : (isSignup ? "Start with your own empty workspace." : "Use your personal workspace.");
        if (nameInput) nameInput.style.display = isSetup || isSignup ? "block" : "none";
        if (submitBtn) submitBtn.textContent = isSetup ? "Create admin account" : (isSignup ? "Create account" : "Sign in");
        if (switchBtn) {
            switchBtn.style.display = auth.setup_required || !auth.allow_signups ? "none" : "block";
            switchBtn.textContent = isSignup ? "Back to sign in" : "Create account";
        }
        if (errorEl) errorEl.style.display = "none";
    }

    setMode(mode);
    if (switchBtn) {
        switchBtn.onclick = () => setMode(mode === "signup" ? "login" : "signup");
    }
    if (submitBtn) {
        submitBtn.onclick = async () => {
            const email = emailInput?.value || "";
            const password = passwordInput?.value || "";
            const name = nameInput?.value || "";
            const res = mode === "login"
                ? await loginApi(email, password)
                : await signupApi(name, email, password, mode === "setup");
            if (res.error) {
                if (errorEl) {
                    errorEl.textContent = res.error;
                    errorEl.style.display = "block";
                }
                return;
            }
            window.location.reload();
        };
    }
    lucide.createIcons();
}

export async function loadCategoriesConfig() {
    try {
        state.categoriesConfig = normalizeCategoryConfig(await fetchCategoriesConfig());
    } catch (err) {
        console.error("Failed to load categories config:", err);
    }
}

export async function loadData(options = {}) {
    const tStart = performance.now();
    const scrollSnapshot = options.preserveScroll ? getScrollSnapshot(options.scrollTargetSelector) : null;
    const tbody = document.getElementById("tx-tbody");
    if (tbody) {
        tbody.innerHTML = `
            <tr>
                <td colspan="9" style="text-align:center; padding: 48px; color: var(--text-muted);">
                    <i data-lucide="loader-2" class="spin" style="width:24px; height:24px; margin-bottom:8px; display:inline-block;"></i>
                    <div>Loading transactions...</div>
                </td>
            </tr>
        `;
        lucide.createIcons();
    }
    
    try {
        // Fetch paginated transactions, accounts, Plaid status, and active connections concurrently
        const [txData, accounts, plaidStatus, connections, trips, rentalProperties] = await Promise.all([
            safeFetch(fetchTransactions(state.currentPage, state.limit, state.currentFilters), { transactions: [], total_pages: 1, page: 1, total_count: 0 }),
            safeFetch(fetchAccountsApi(), []),
            safeFetch(fetchCredentialsStatus(), { has_credentials: false, env: 'N/A', last_sync_time: 'N/A' }),
            safeFetch(fetchConnectionsApi(), []),
            safeFetch(fetchTripsApi(), []),
            safeFetch(fetchRentalPropertiesApi(), [])
        ]);
        
        state.transactions = txData.transactions || [];
        state.totalPages = txData.total_pages || 1;
        state.currentPage = txData.page || 1;
        state.totalCount = txData.total_count || 0;
        state.accounts = accounts;
        state.trips = trips || [];
        state.rentalProperties = rentalProperties || [];
        
        renderDashboard(accounts);
        initializeNetWorthRangeControl();
        renderBalanceTrendChart();
        renderAssetAllocationChart();
        renderInstitutionAllocationDetails();
        renderMonthlyAnalysis();
        renderTripManager();
        renderRentalManager();
        await renderRentalRuleManager();
        renderTravelAnalysis();
        renderRentalAnalysis();
        renderTransactionsList();
        renderAccountsList(accounts);
        renderPlaidConnections(accounts, connections);
        renderCategoryConfigView();
        enableResizableColumns();
        
        await checkPlaidConfiguration(plaidStatus);

        const duration = performance.now() - tStart;
        console.log(`[Performance] loadData completed in ${duration.toFixed(1)}ms`);
        const badge = document.getElementById("load-time-badge");
        if (badge) {
            badge.textContent = `(Loaded in ${duration.toFixed(0)}ms)`;
        }
    } catch (err) {
        console.error("Error loading data from backend:", err);
    } finally {
        if (options.preserveScroll) {
            restoreScrollSnapshot(scrollSnapshot);
        }
    }
}

function setupRouting() {
    const navBtns = document.querySelectorAll(".nav-btn");
    navBtns.forEach(btn => {
        btn.addEventListener("click", (e) => {
            const target = e.currentTarget.getAttribute("data-view");
            if (target === "see-all") return;
            window.location.hash = target;
        });
    });

    window.addEventListener("hashchange", () => {
        const view = window.location.hash.substring(1) || "dashboard";
        switchView(view);
    });

    // Handle initial route
    const initialView = window.location.hash.substring(1) || "dashboard";
    switchView(initialView);
}

function switchView(viewName) {
    document.querySelectorAll(".sidebar .nav-btn").forEach(btn => {
        if (btn.getAttribute("data-view") === viewName) {
            btn.classList.add("active");
        } else {
            btn.classList.remove("active");
        }
    });

    document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
    const activeView = document.getElementById(`view-${viewName}`);
    if (activeView) activeView.classList.add("active");

    const headers = {
        dashboard: { t: "Overview", d: "Track net worth, allocation, and synced account activity." },
        "monthly-analysis": { t: "Spending", d: "Monthly and yearly income, expenses, and category trends." },
        transactions: { t: "Transactions", d: "Review, search, and classify synced transactions." },
        "travel-analysis": { t: "Travel", d: "Trips, travel categories, and monthly travel spending." },
        "rental-analysis": { t: "Rentals", d: "Property-level rental transactions and category summaries." },
        settings: { t: "Plaid", d: "Manage linked institutions and Plaid connection health." },
        "category-config": { t: "Categories", d: "Manage transaction categories, subcategories, and mapping rules." }
    };

    if (headers[viewName]) {
        document.getElementById("view-title").textContent = headers[viewName].t;
        document.getElementById("view-description").textContent = headers[viewName].d;
    }
    
    if (viewName === "category-config") {
        renderCategoryConfigView();
    }
}

async function checkPlaidConfiguration(preFetchedStatus = null) {
    const credStatus = document.getElementById("settings-cred-status");
    const envStatus = document.getElementById("settings-env-status");
    const syncTimeEl = document.getElementById("settings-last-sync-time");
    const linkBtn = document.getElementById("settings-link-btn");
    const syncBtn = document.getElementById("settings-sync-btn");
    const disconnectBtn = document.getElementById("settings-disconnect-btn");
    const clientIdInput = document.getElementById("plaid-client-id-input");
    const secretInput = document.getElementById("plaid-secret-input");
    const envSelect = document.getElementById("plaid-env-select");
    const saveCredentialsBtn = document.getElementById("settings-save-plaid-credentials-btn");
    const dailySyncTimeInput = document.getElementById("settings-daily-sync-time");
    const saveSyncScheduleBtn = document.getElementById("settings-save-sync-schedule-btn");
    const syncScheduleNote = document.getElementById("settings-sync-schedule-note");

    if (!credStatus || !envStatus || !linkBtn || !syncBtn || !disconnectBtn) return;

    try {
        const [status, plaidCreds, syncSchedule] = await Promise.all([
            preFetchedStatus ? Promise.resolve(preFetchedStatus) : fetchCredentialsStatus(),
            fetchPlaidCredentialsApi(),
            fetchSyncScheduleApi()
        ]);
        if (clientIdInput) clientIdInput.value = plaidCreds.client_id || "";
        if (secretInput) secretInput.placeholder = plaidCreds.has_credentials ? "Plaid Secret saved" : "Plaid Secret";
        if (envSelect) envSelect.value = plaidCreds.environment || status.env || "development";
        if (dailySyncTimeInput) {
            dailySyncTimeInput.value = syncSchedule.daily_sync_time || "16:00";
            dailySyncTimeInput.disabled = !syncSchedule.can_edit;
        }
        if (saveSyncScheduleBtn) saveSyncScheduleBtn.disabled = !syncSchedule.can_edit;
        if (syncScheduleNote) {
            syncScheduleNote.textContent = syncSchedule.can_edit
                ? "All active users sync at this local server time. Changes apply within 30 seconds."
                : "All active users sync at this local server time. Only an administrator can change it.";
        }
        if (status.has_credentials) {
            credStatus.textContent = "Configured";
            credStatus.style.color = "var(--color-success)";
            envStatus.textContent = (status.env || "N/A").toUpperCase();
            envStatus.style.color = "var(--color-primary)";
            if (syncTimeEl) {
                syncTimeEl.textContent = status.last_sync_time || "N/A";
                syncTimeEl.style.color = status.last_sync_time && status.last_sync_time !== "N/A" ? "var(--color-success)" : "var(--text-muted)";
            }

            linkBtn.removeAttribute("disabled");
            syncBtn.removeAttribute("disabled");
            disconnectBtn.removeAttribute("disabled");
        } else {
            credStatus.textContent = "Missing user credentials";
            credStatus.style.color = "var(--color-danger)";
            envStatus.textContent = "N/A";
            if (syncTimeEl) syncTimeEl.textContent = "N/A";
            linkBtn.setAttribute("disabled", "true");
            syncBtn.setAttribute("disabled", "true");
            disconnectBtn.setAttribute("disabled", "true");
        }
    } catch (err) {
        credStatus.textContent = "Server unavailable";
        credStatus.style.color = "var(--color-danger)";
    }

    // Bind event handlers
    linkBtn.onclick = () => linkNewBank();
    syncBtn.onclick = () => syncPlaidTransactions();
    disconnectBtn.onclick = () => handleDisconnect();
    if (saveCredentialsBtn) {
        saveCredentialsBtn.onclick = async () => {
            const payload = {
                client_id: clientIdInput?.value || "",
                secret: secretInput?.value || "",
                environment: envSelect?.value || "development"
            };
            saveCredentialsBtn.disabled = true;
            try {
                const res = await savePlaidCredentialsApi(payload);
                if (res.error) {
                    alert("Unable to save Plaid credentials: " + res.error);
                    return;
                }
                if (secretInput) secretInput.value = "";
                await checkPlaidConfiguration();
                alert("Plaid credentials saved.");
            } finally {
                saveCredentialsBtn.disabled = false;
            }
        };
    }
    if (saveSyncScheduleBtn) {
        saveSyncScheduleBtn.onclick = async () => {
            saveSyncScheduleBtn.disabled = true;
            try {
                const res = await saveSyncScheduleApi(dailySyncTimeInput?.value || "");
                if (res.error) {
                    alert("Unable to save daily sync time: " + res.error);
                    return;
                }
                await checkPlaidConfiguration();
                alert(`Daily auto-sync updated to ${res.daily_sync_time}.`);
            } finally {
                saveSyncScheduleBtn.disabled = false;
            }
        };
    }
}

async function renderDashboard(accounts) {
    const cashBalEl = document.getElementById("dash-cash-balance");
    if (cashBalEl) {
        try {
            const allocationPayload = await fetchAllocationAccountsCached();
            const totals = allocationPayload?.totals || {};
            const assetTotal = ["Cash", "Stock", "Bond", "Real Estate"]
                .reduce((sum, key) => sum + Number(totals[key] || 0), 0);
            const liabilities = accounts
                .filter(acc => acc.type === "credit" && !acc.is_virtual)
                .reduce((sum, acc) => sum + Number(acc.balance_current || 0), 0);
            cashBalEl.textContent = formatCurrency(assetTotal - liabilities);
        } catch (err) {
            console.warn("Unable to load net worth total:", err);
            const assetAccounts = accounts.filter(a => !a.is_virtual && (a.type === "depository" || a.type === "investment"));
            const netBalance = assetAccounts.reduce((sum, a) => sum + (a.balance_current || 0), 0);
            cashBalEl.textContent = formatCurrency(netBalance);
        }
    }

    const now = new Date();
    const currentYear = now.getFullYear();
    const currentMonth = String(now.getMonth() + 1).padStart(2, '0');
    const monthPrefix = `${currentYear}-${currentMonth}`;

    const monthIncEl = document.getElementById("dash-month-income");
    const monthExpEl = document.getElementById("dash-month-expense");
    try {
        const data = await fetchMonthlyAnalysisApi();
        const currentMonthRow = (data.months || []).find(row => row.month === monthPrefix);
        if (monthIncEl) monthIncEl.textContent = formatCurrency(currentMonthRow?.income || 0);
        if (monthExpEl) monthExpEl.textContent = formatCurrency(currentMonthRow?.expense || 0);
    } catch (err) {
        console.warn("Unable to load dashboard monthly totals:", err);
        if (monthIncEl) monthIncEl.textContent = formatCurrency(0);
        if (monthExpEl) monthExpEl.textContent = formatCurrency(0);
    }
}

function guessBankName(accList) {
    // 1. Scan across ALL accounts in this connection for known keywords
    for (const acc of accList) {
        const official = (acc.official_name || "").toLowerCase();
        const name = (acc.name || "").toLowerCase();
        
        if (official.includes("discover") || name.includes("discover")) {
            return "Discover";
        }
        if (official.includes("citi") || name.includes("citi") || 
            official.includes("costco anywhere") || name.includes("costco anywhere")) {
            return "Citi";
        }
        if (official.includes("wealthfront") || name.includes("wealthfront") || 
            official.includes("individual cash") || name.includes("individual cash")) {
            return "Wealthfront";
        }
        if (official.includes("chase") || name.includes("chase") || 
            official.includes("jpmorgan") || name.includes("jpmorgan")) {
            return "Chase";
        }
        if (official.includes("capital one") || name.includes("capital one") || 
            official.includes("capitalone") || name.includes("capitalone")) {
            return "Capital One";
        }
        if (official.includes("america") || name.includes("america") || 
            official.includes("bofa") || name.includes("bofa") ||
            official.includes("customized cash") || official.includes("relationship banking") ||
            official.includes("advantage savings") || name.includes("advantage savings") ||
            official.includes("southern california visa") || name.includes("southern california visa")) {
            return "Bank of America";
        }
        if (official.includes("american express") || name.includes("american express") || 
            official.includes("amex") || name.includes("amex")) {
            return "American Express";
        }
    }
    
    // 2. Fallback to parsing the first account
    const firstAcc = accList[0] || {};
    const words = (firstAcc.official_name || firstAcc.name || "Bank Link").split(" ");
    for (const w of words) {
        const clean = w.replace(/[^a-zA-Z]/g, "").toLowerCase();
        if (clean && !["customized", "individual", "advantage", "university", "relationship", "adv", "online", "savings", "checking"].includes(clean)) {
            return w;
        }
    }
    return words[0] || "Bank Link";
}

function escapeJsString(value) {
    return String(value ?? "")
        .replaceAll("\\", "\\\\")
        .replaceAll("'", "\\'")
        .replaceAll("\n", " ")
        .replaceAll("\r", " ");
}

function plaidWarningMessage(connInfo) {
    const raw = String(connInfo?.error_message || "");
    if (connInfo?.status === "error_consent" || raw.includes("ADDITIONAL_CONSENT_REQUIRED")) {
        if (!connInfo?.has_investments) return "";
        return "Plaid says this investment connection has not granted Investments access. Repair the connection to grant the investments product.";
    }
    if (connInfo?.status === "error_login" || raw.includes("ITEM_LOGIN_REQUIRED")) {
        return "Plaid says this bank login needs to be refreshed before sync can continue.";
    }
    const match = raw.match(/"error_message"\s*:\s*"([^"]+)"/);
    if (match?.[1]) return match[1];
    return raw.trim();
}

function renderPlaidWarningIcon(message) {
    if (!message) return "";
    return `<span class="settings-warning-icon" title="${escapeHtml(message)}"><i data-lucide="circle-alert"></i></span>`;
}

export async function reconnectItem(itemId) {
    return repairConnection(itemId);
}

export async function repairConnection(itemId) {
    try {
        const res = await fetch("/api/create_link_token", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ item_id: itemId })
        });
        const data = await res.json();
        if (data.error) {
            alert("Unable to create an update-mode Link token: " + data.error);
            return;
        }
        
        const handler = Plaid.create({
            token: data.link_token,
            onSuccess: async () => {
                alert("Connection repaired. Syncing latest data...");
                await syncPlaidTransactions();
                await loadData({ preserveScroll: true });
            },
            onExit: (err, metadata) => {
                if (err != null) {
                    console.error("Plaid Update Mode Exit Error:", err);
                }
            }
        });
        handler.open();
    } catch (e) {
        alert("Unable to start repair: " + e.message);
    }
}

export async function disconnectItem(itemId, bankName) {
    if (!confirm(`Disconnect [${bankName}]?\n\nThis stops future sync for this institution but keeps all synced transaction history and classifications. This cannot be undone from the app.`)) {
        return;
    }
    
    try {
        const res = await disconnectItemApi(itemId);
        if (res.status === "success") {
            alert(`[${bankName}] was disconnected. Local transaction history was kept.`);
            await loadData();
        } else {
            alert("Disconnect failed: " + res.error);
        }
    } catch (e) {
        alert("Disconnect failed: " + e.message);
    }
}

export async function deleteCachedAccounts(itemId, bankName) {
    if (!confirm(`Clear local cache for [${bankName}]?\n\nWarning: this deletes local accounts, synced transactions, and reconciliation records for this institution. Use this only after replacing a duplicate connection. Legacy imported transactions are not affected.`)) {
        return;
    }
    
    try {
        const res = await fetch("/api/delete_cached_accounts", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ item_id: itemId })
        });
        const data = await res.json();
        if (data.status === "success") {
            alert(`[${bankName}] local cached accounts and transactions were cleared.`);
            await loadData();
        } else {
            alert("Cache cleanup failed: " + data.error);
        }
    } catch (e) {
        alert("Cache cleanup failed: " + e.message);
    }
}

export async function replaceItemWithNewLink(oldItemId, bankName) {
    if (!confirm(`Replace connection?\n\nThis creates a new Plaid connection. Account IDs and transaction IDs may change, and duplicate accounts may appear if cleanup fails.\n\nUse this only if Repair connection does not work.\n\nInstitution: ${bankName}`)) {
        return;
    }

    try {
        const tokenRes = await fetch("/api/create_link_token", { method: "POST" });
        const tokenData = await tokenRes.json();
        if (tokenData.error) {
            alert("Unable to create a replacement Link token: " + tokenData.error);
            return;
        }

        const handler = Plaid.create({
            token: tokenData.link_token,
            onSuccess: async (public_token, metadata) => {
                try {
                    alert("New Plaid connection created. Exchanging token and syncing accounts...");

                    const exchangeRes = await fetch("/api/exchange_public_token", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ public_token })
                    });
                    const exchangeData = await exchangeRes.json();
                    if (exchangeData.status !== "success") {
                        alert("Token exchange failed: " + (exchangeData.error || "Unknown error"));
                        return;
                    }

                    const syncRes = await fetch("/api/sync_transactions", { method: "POST" });
                    const syncData = await syncRes.json();
                    if (syncData.status !== "success") {
                        alert("New institution was linked, but sync failed: " + (syncData.error || "Unknown error"));
                        await loadData();
                        return;
                    }

                    const finalizeRes = await fetch("/api/finalize_replacement", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            old_item_id: oldItemId,
                            new_item_id: exchangeData.item_id
                        })
                    });
                    const finalizeData = await finalizeRes.json();
                    if (finalizeData.status !== "success") {
                        alert("New accounts synced, but old-cache cleanup failed: " + (finalizeData.error || "Unknown error"));
                        await loadData();
                        return;
                    }

                    alert(`[${bankName}] replacement complete. New transactions synced: ${syncData.new_transactions_count || 0}`);
                    await loadData();
                } catch (innerErr) {
                    alert("Replacement failed: " + innerErr.message);
                    await loadData();
                }
            },
            onExit: (err, metadata) => {
                if (err != null) {
                    console.error("Plaid replacement Link Exit Error:", err);
                }
            }
        });
        handler.open();
    } catch (e) {
        alert("Unable to start replacement: " + e.message);
    }
}

function getConnectionUiState(connInfo, accList = [], isDisconnected = false) {
    const status = isDisconnected ? "disconnected" : (connInfo?.status || "disconnected");
    const rawErrorCode = String(connInfo?.error_code || "");
    const rawErrorMessage = String(connInfo?.error_message || "");
    const holdingsStatus = connInfo?.holdings_sync_status || null;
    const hasInvestments = Boolean(connInfo?.has_investments) || accList.some(acc => acc.type === "investment");
    const hasLoginError = status === "error_login" || rawErrorCode === "ITEM_LOGIN_REQUIRED" || rawErrorMessage.includes("ITEM_LOGIN_REQUIRED");
    const hasConsentError = hasInvestments && (status === "error_consent" || rawErrorCode === "ADDITIONAL_CONSENT_REQUIRED" || rawErrorMessage.includes("ADDITIONAL_CONSENT_REQUIRED"));
    const hasGenericError = status === "error";
    const holdingsNeedsRepair = hasInvestments && ["auth_required", "consent_required", "error_consent", "error_login", "failed"].includes(holdingsStatus);
    const holdingsPending = hasInvestments && ["pending", "syncing"].includes(holdingsStatus);
    const holdingsLimited = hasInvestments && ["no_holdings", "product_not_supported", "not_supported"].includes(holdingsStatus);

    if (status === "disconnected") {
        return {
            state: "disconnected",
            label: "Disconnected",
            message: "This connection no longer syncs. Cached local data may remain.",
            primaryAction: "clear_cache",
            primaryLabel: "Clear cache",
            moreItems: ["view_cached_data"]
        };
    }
    if (hasLoginError || hasConsentError || hasGenericError || holdingsNeedsRepair) {
        return {
            state: "needs_repair",
            label: "Needs attention",
            message: "This connection needs repair before it can fully sync.",
            primaryAction: "repair",
            primaryLabel: "Repair connection",
            moreItems: ["view_error_details", "disconnect", "replace_connection"]
        };
    }
    if (holdingsPending) {
        return {
            state: "syncing_or_pending",
            label: "Holdings syncing",
            message: "Plaid is still preparing investment holdings.",
            primaryAction: "sync",
            primaryLabel: "Sync now",
            moreItems: ["view_details", "disconnect", "replace_connection"]
        };
    }
    if (holdingsLimited) {
        return {
            state: "limited_support",
            label: holdingsStatus === "no_holdings" ? "No holdings" : "Limited support",
            message: "Investment holdings are not available for this connection.",
            primaryAction: "sync",
            primaryLabel: "Sync now",
            moreItems: ["view_details", "disconnect", "replace_connection"]
        };
    }
    if (hasInvestments && holdingsStatus === "synced") {
        return {
            state: "connected",
            label: "Investments synced",
            message: "Transactions, accounts, and investment holdings are syncing normally.",
            primaryAction: "sync",
            primaryLabel: "Sync now",
            moreItems: ["view_details", "disconnect", "replace_connection"]
        };
    }
    return {
        state: "connected",
        label: "Connected",
        message: "Transactions and accounts are syncing normally.",
        primaryAction: "sync",
        primaryLabel: "Sync now",
        moreItems: ["view_details", "disconnect", "replace_connection"]
    };
}

function connectionTooltip(uiState, connInfo, accList, itemId, isDisconnected) {
    const lines = [`UI status: ${uiState.label}`];
    if (connInfo?.status) lines.push(`Plaid status: ${connInfo.status}`);
    if (connInfo?.error_code) lines.push(`Plaid error code: ${connInfo.error_code}`);
    if (connInfo?.error_message) lines.push(`Plaid error message: ${String(connInfo.error_message).slice(0, 260)}`);
    if (connInfo?.holdings_sync_status) lines.push(`Holdings status: ${connInfo.holdings_sync_status}`);
    if (connInfo?.last_sync_attempt_at) lines.push(`Last sync attempt: ${connInfo.last_sync_attempt_at}`);
    if (connInfo?.last_success_at) lines.push(`Last successful sync: ${connInfo.last_success_at}`);
    if (isDisconnected) {
        lines.push(`Cached accounts: ${connInfo?.cached_accounts_count ?? accList.length}`);
        if (connInfo?.cached_transactions_count != null) lines.push(`Cached transactions: ${connInfo.cached_transactions_count}`);
    }
    if (itemId) lines.push(`${isDisconnected ? "Old item ID" : "Item ID"}: ${itemId}`);
    return lines.join("\n");
}

function showConnectionDetails(kind, itemId) {
    const payload = window.__connectionDetails?.[itemId];
    if (!payload) return;
    const { uiState, connInfo, accList, bankName, isDisconnected } = payload;
    const investmentCount = connInfo.cached_investment_accounts_count ?? accList.filter(acc => acc.type === "investment").length;
    const accountCount = connInfo.cached_accounts_count ?? accList.length;
    const lines = [
        `Institution: ${bankName}`,
        `UI status: ${uiState.label}`,
        `Plaid status: ${connInfo.status || (isDisconnected ? "disconnected / no active Plaid token" : "unknown")}`,
        `${isDisconnected ? "Old item ID" : "Item ID"}: ${itemId}`,
        `Account count: ${accountCount}`,
        `Investment account count: ${investmentCount}`
    ];
    if (connInfo.holdings_sync_status) lines.push(`Holdings status: ${connInfo.holdings_sync_status}`);
    if (connInfo.last_sync_attempt_at) lines.push(`Last sync attempt: ${connInfo.last_sync_attempt_at}`);
    if (connInfo.last_success_at) lines.push(`Last successful sync: ${connInfo.last_success_at}`);
    if (connInfo.last_cursor_available != null) lines.push(`Last cursor available: ${connInfo.last_cursor_available ? "yes" : "no"}`);
    if (connInfo.error_code) lines.push(`Plaid error code: ${connInfo.error_code}`);
    if (connInfo.error_message) lines.push(`Plaid error message: ${connInfo.error_message}`);
    if (kind === "error") lines.push("Suggested action: Repair connection");
    if (kind === "cache") {
        if (connInfo.cached_transactions_count != null) lines.push(`Cached transactions: ${connInfo.cached_transactions_count}`);
        if (connInfo.cached_reviewed_transactions_count != null) lines.push(`Reviewed transactions: ${connInfo.cached_reviewed_transactions_count}`);
        if (connInfo.first_transaction_date) lines.push(`First transaction date: ${connInfo.first_transaction_date}`);
        if (connInfo.last_transaction_date) lines.push(`Last transaction date: ${connInfo.last_transaction_date}`);
        lines.push("Cached transactions remain in local history until cache is cleared.");
    }
    alert(lines.join("\n"));
}

function renderConnectionMoreMenu(items, itemId, bankNameArg) {
    const labels = {
        view_details: "View details",
        view_error_details: "View error details",
        view_cached_data: "View cached data",
        disconnect: "Disconnect...",
        replace_connection: "Replace connection..."
    };
    const actions = {
        view_details: `showConnectionDetails('details', '${itemId}')`,
        view_error_details: `showConnectionDetails('error', '${itemId}')`,
        view_cached_data: `showConnectionDetails('cache', '${itemId}')`,
        disconnect: `disconnectItem('${itemId}', '${bankNameArg}')`,
        replace_connection: `replaceItemWithNewLink('${itemId}', '${bankNameArg}')`
    };
    return `
        <details class="settings-more-menu">
            <summary class="pagination-btn settings-card-action" title="More actions">
                <i data-lucide="more-horizontal"></i>
            </summary>
            <div class="settings-more-list">
                ${items.map(item => `<button type="button" onclick="${actions[item]}">${labels[item]}</button>`).join("")}
            </div>
        </details>
    `;
}

function renderPlaidConnections(accounts, connections = []) {
    const card = document.getElementById("settings-connections-card");
    const container = document.getElementById("settings-connections-container");

    if (!card || !container) return;

    const plaidAccounts = accounts.filter(acc => acc.account_id !== "Legacy");

    if (plaidAccounts.length === 0 && connections.length === 0) {
        card.style.display = "block";
        container.innerHTML = `
            <div class="settings-empty-link">
                <i data-lucide="link"></i>
                <div>
                    <strong>No banks linked yet</strong>
                    <p>Connect a bank with Plaid to start syncing this workspace.</p>
                </div>
                <button class="sync-btn settings-card-action is-primary" onclick="linkNewBank()">
                    <i data-lucide="link"></i> Link bank
                </button>
            </div>
        `;
        lucide.createIcons();
        return;
    }

    card.style.display = "block";
    container.innerHTML = "";
    window.__connectionDetails = {};

    const groups = {};
    plaidAccounts.forEach(acc => {
        const itemId = acc.item_id || "unknown";
        if (!groups[itemId]) {
            groups[itemId] = [];
        }
        groups[itemId].push(acc);
    });

    const connMap = {};
    connections.forEach(c => {
        connMap[c.item_id] = c;
    });

    const allItemIds = new Set([...Object.keys(groups), ...Object.keys(connMap)]);

    let connIndex = 1;
    for (const itemId of allItemIds) {
        if (itemId === "unknown") continue;

        const accList = groups[itemId] || [];
        const isDisconnected = !connMap[itemId] || Boolean(connMap[itemId]?.is_cached_only);
        const connInfo = connMap[itemId] || { status: 'disconnected', institution_name: 'Bank Link' };

        const connCard = document.createElement("div");
        connCard.className = "settings-connection-card";
        if (isDisconnected) {
            connCard.classList.add("is-disconnected");
        }

        const bankName = connInfo.institution_name && connInfo.institution_name !== "Bank Link" 
            ? connInfo.institution_name 
            : (accList.length > 0 ? (accList[0].institution_name || guessBankName(accList)) : "Bank Link");
        const bankNameArg = escapeJsString(bankName);
        const uiState = getConnectionUiState(connInfo, accList, isDisconnected);
        window.__connectionDetails[itemId] = { uiState, connInfo, accList, bankName, isDisconnected };
        const badgeClass = uiState.state === "needs_repair" ? "is-danger"
            : uiState.state === "syncing_or_pending" ? "is-pending"
            : uiState.state === "limited_support" || uiState.state === "disconnected" ? "is-muted"
            : "is-success";
        const statusBadgeHtml = `<span class="settings-status-badge ${badgeClass}">${escapeHtml(uiState.label)}</span>`;
        const infoTooltip = escapeHtml(connectionTooltip(uiState, connInfo, accList, itemId, isDisconnected)).replaceAll("\n", "&#10;");
        const infoIconHtml = `<span class="connection-info-icon" tabindex="0" title="${infoTooltip}">i</span>`;
        const warningIconHtml = renderPlaidWarningIcon(plaidWarningMessage(connInfo));
        const noteHtml = `<div class="settings-connection-note ${uiState.state === "needs_repair" ? "is-danger" : "is-info"}"><i data-lucide="info"></i><span>${escapeHtml(uiState.message)}</span></div>`;
        const primaryAction = uiState.primaryAction === "repair"
            ? `repairConnection('${itemId}')`
            : uiState.primaryAction === "clear_cache"
                ? `deleteCachedAccounts('${itemId}', '${bankNameArg}')`
                : `syncPlaidTransactions()`;
        const primaryIcon = uiState.primaryAction === "repair" ? "wrench"
            : uiState.primaryAction === "clear_cache" ? "trash-2"
            : "refresh-cw";
        const primaryClass = uiState.primaryAction === "clear_cache" ? "is-danger" : "is-primary";
        const buttonHtml = `
            <button class="pagination-btn settings-card-action ${primaryClass}" onclick="${primaryAction}">
                <i data-lucide="${primaryIcon}"></i> ${escapeHtml(uiState.primaryLabel)}
            </button>
            ${renderConnectionMoreMenu(uiState.moreItems, itemId, bankNameArg)}
        `;

        let html = `
            <div class="settings-connection-header">
                <div class="settings-connection-title">
                    <i data-lucide="landmark"></i>
                    <span>${escapeHtml(bankName)} #${connIndex}</span>
                    ${statusBadgeHtml}
                    ${infoIconHtml}
                    ${warningIconHtml}
                </div>
                <span class="settings-connection-id">ID: ${escapeHtml(itemId.substring(0, 8))}...</span>
            </div>
            <div class="settings-account-list">
        `;

        if (accList.length === 0) {
            html += `<div class="settings-empty-accounts">No synced accounts yet. Run Sync now after linking.</div>`;
        } else {
            accList.forEach(acc => {
                const isCredit = acc.type === "credit";
                const val = acc.balance_current || 0;
                const displayVal = isCredit ? -val : val;
                const prefix = displayVal < 0 ? "-" : "";
                html += `
                    <div class="settings-account-row">
                        <div>
                            <span>${escapeHtml(acc.name)}</span>
                            <small>${escapeHtml(acc.subtype || acc.type || "account")}</small>
                        </div>
                        <strong>${prefix}${formatCurrency(displayVal)}</strong>
                    </div>
                `;
            });
        }

        html += `
            </div>
            ${noteHtml}
            <div class="settings-card-actions">
                ${buttonHtml}
            </div>
        `;
        connCard.innerHTML = html;
        container.appendChild(connCard);
        connIndex++;
    }

    lucide.createIcons();
}

window.reconnectItem = reconnectItem;
window.repairConnection = repairConnection;
window.disconnectItem = disconnectItem;
window.deleteCachedAccounts = deleteCachedAccounts;
window.showConnectionDetails = showConnectionDetails;
window.syncPlaidTransactions = syncPlaidTransactions;

let netWorthChartInstance = null;
let allocationTrendChartInstance = null;
let netWorthTrendRange = "1M";
let netWorthTrendHistory = [];
let netWorthTrendHistoryPromise = null;
let allocationAccountsCache = null;
let allocationAccountsPromise = null;
let expandedAllocationAccountId = "";
let accountBalanceHistoryRange = "1M";
const accountBalanceHistoryCache = {};
const accountBalanceChartInstances = {};

async function fetchAllocationHistoryCached(force = false) {
    if (force) {
        netWorthTrendHistory = [];
        netWorthTrendHistoryPromise = null;
    }
    if (netWorthTrendHistory.length) return netWorthTrendHistory;
    if (!netWorthTrendHistoryPromise) {
        netWorthTrendHistoryPromise = fetchAllocationHistoryApi()
            .then(payload => {
                netWorthTrendHistory = payload.history || [];
                return netWorthTrendHistory;
            })
            .finally(() => {
                netWorthTrendHistoryPromise = null;
            });
    }
    return await netWorthTrendHistoryPromise;
}

async function fetchAllocationAccountsCached(force = false) {
    if (force) {
        allocationAccountsCache = null;
        allocationAccountsPromise = null;
    }
    if (allocationAccountsCache) return allocationAccountsCache;
    if (!allocationAccountsPromise) {
        allocationAccountsPromise = fetchAllocationAccountsApi()
            .then(payload => {
                allocationAccountsCache = payload || {};
                return allocationAccountsCache;
            })
            .finally(() => {
                allocationAccountsPromise = null;
            });
    }
    return await allocationAccountsPromise;
}

function filterTrendHistoryByRange(historyData, rangeKey) {
    if (!historyData.length || rangeKey === "ALL") return historyData;
    const lastTimestamp = Math.max(...historyData.map(row => new Date(`${row.date}T00:00:00`).getTime()));
    const rangeDays = {
        "1M": 30,
        "3M": 90,
        "1Y": 365,
        "5Y": 365 * 5
    };
    const days = rangeDays[rangeKey];
    if (!days) return historyData;
    const cutoffTime = lastTimestamp - days * 24 * 60 * 60 * 1000;
    const filtered = historyData.filter(row => new Date(`${row.date}T00:00:00`).getTime() >= cutoffTime);
    const prior = [...historyData]
        .reverse()
        .find(row => new Date(`${row.date}T00:00:00`).getTime() < cutoffTime);
    return prior && filtered.length < 2 ? [prior, ...filtered] : filtered;
}

export async function renderBalanceTrendChart() {
    const netWorthCanvas = document.getElementById("balanceTrendChart");
    const allocationCanvas = document.getElementById("allocationTrendChart");
    if (!netWorthCanvas && !allocationCanvas) return;

    try {
        if (!netWorthTrendHistory.length) await fetchAllocationHistoryCached();
        const historyData = filterTrendHistoryByRange(netWorthTrendHistory, netWorthTrendRange);
        const dateFormatter = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "2-digit" });
        const currencyFormatter = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
        const netWorthConfig = [
            { key: "Net Worth", label: "Net Worth", color: "#10b981", fill: true, width: 3 }
        ];
        const allocationConfig = [
            { key: "Cash", label: "Cash", color: "#3b82f6" },
            { key: "Stock", label: "Stock", color: "#22c55e" },
            { key: "Bond", label: "Bond", color: "#f59e0b" },
            { key: "Real Estate", label: "Real Estate", color: "#8b5cf6" }
        ];
        const makeDatasets = (trendConfig) => trendConfig.map(cfg => ({
            label: cfg.label,
            data: historyData.map(row => ({
                x: new Date(`${row.date}T00:00:00`).getTime(),
                y: row[cfg.key] || 0,
                date: row.date
            })),
            allocationColor: cfg.color,
            borderColor: cfg.color,
            backgroundColor: cfg.fill ? "rgba(16, 185, 129, 0.08)" : "transparent",
            fill: !!cfg.fill,
            tension: 0.3,
            borderWidth: cfg.width || 2,
            pointRadius: cfg.key === "Net Worth" ? 1.5 : 1,
            pointHoverRadius: cfg.key === "Net Worth" ? 4 : 3,
            pointHitRadius: 8,
            pointBackgroundColor: cfg.color
        }));

        const buildTrendChart = (canvas, datasets) => new Chart(canvas.getContext('2d'), {
            type: 'line',
            data: {
                datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                parsing: false,
                interaction: {
                    mode: 'nearest',
                    axis: 'xy',
                    intersect: false
                },
                onHover: (event, elements, chart) => {
                    const activeDatasetIndex = elements.length ? elements[0].datasetIndex : null;
                    chart.data.datasets.forEach((dataset, index) => {
                        const color = dataset.allocationColor;
                        const isActive = activeDatasetIndex === null || activeDatasetIndex === index;
                        dataset.borderColor = isActive ? color : `${color}45`;
                        dataset.pointBackgroundColor = isActive ? color : `${color}45`;
                        dataset.borderWidth = isActive
                            ? (dataset.label === "Net Worth" ? 4 : 3)
                            : 1;
                    });
                    chart.update('none');
                },
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            color: '#e2e8f0',
                            font: { family: 'Inter' }
                        }
                    },
                    tooltip: {
                        mode: 'nearest',
                        intersect: false,
                        callbacks: {
                            title: function(context) {
                                const raw = context[0]?.raw;
                                return raw?.date || "";
                            },
                            label: function(context) {
                                const label = context.dataset.label || "";
                                return `${label}: ${currencyFormatter.format(context.parsed.y || 0)}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'linear',
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: {
                            color: '#94a3b8',
                            maxTicksLimit: 7,
                            callback: function(value) {
                                return dateFormatter.format(new Date(value));
                            }
                        }
                    },
                    y: {
                        type: 'linear',
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: {
                            color: '#94a3b8',
                            maxTicksLimit: 6,
                            callback: function(value) {
                                return currencyFormatter.format(value);
                            }
                        }
                    }
                }
            }
        });

        if (netWorthCanvas) {
            if (netWorthChartInstance) netWorthChartInstance.destroy();
            netWorthChartInstance = buildTrendChart(netWorthCanvas, makeDatasets(netWorthConfig));
        }
        if (allocationCanvas) {
            if (allocationTrendChartInstance) allocationTrendChartInstance.destroy();
            allocationTrendChartInstance = buildTrendChart(allocationCanvas, makeDatasets(allocationConfig));
        }
    } catch (e) {
        console.error("Error rendering balance trend chart:", e);
    }
}

function initializeNetWorthRangeControl() {
    const controls = document.querySelectorAll(".trend-range-control");
    controls.forEach(control => {
        control.querySelectorAll(".chart-range-btn").forEach(btn => {
            btn.classList.toggle("active", btn.dataset.range === netWorthTrendRange);
        });
        if (control.dataset.bound === "true") return;
        control.dataset.bound = "true";
        control.addEventListener("click", async (event) => {
            const button = event.target.closest(".chart-range-btn");
            if (!button) return;
            netWorthTrendRange = button.dataset.range || "ALL";
            controls.forEach(group => {
                group.querySelectorAll(".chart-range-btn").forEach(btn => {
                    btn.classList.toggle("active", btn.dataset.range === netWorthTrendRange);
                });
            });
            await renderBalanceTrendChart();
        });
    });
}

let allocationChartInstance = null;
let monthlyAnalysisChartInstance = null;
let yearlyAnalysisChartInstance = null;
let travelMonthlyChartInstance = null;
let transactionFilterOptionsLoaded = false;
let monthlyCashFlowRange = "1Y";
let responsiveChartResizeBound = false;
let travelTripsByKey = {};
let rentalPropertiesByKey = {};

function stableReportKey(prefix, id, fallbackParts = []) {
    if (id) return `${prefix}:${id}`;
    return `${prefix}:unassigned:${fallbackParts.map(part => String(part ?? "")).join(":")}`;
}

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function formatPercent(value) {
    return `${((value || 0) * 100).toFixed(1)}%`;
}

function filterMonthlyRowsByRange(rows, rangeKey) {
    if (!rows.length || rangeKey === "ALL") return rows;
    const monthCount = {
        "3M": 3,
        "6M": 6,
        "1Y": 12,
        "5Y": 60
    }[rangeKey] || 12;
    return rows.slice(-monthCount);
}

function resizeChartIfReady(chart) {
    if (!chart) return;
    requestAnimationFrame(() => {
        try {
            chart.resize();
            chart.update('none');
        } catch (e) {
            console.warn("Chart resize failed:", e);
        }
    });
}

function resizeDashboardCharts() {
    resizeChartIfReady(netWorthChartInstance);
    resizeChartIfReady(allocationTrendChartInstance);
    resizeChartIfReady(allocationChartInstance);
}

function initializeResponsiveChartResizing() {
    if (responsiveChartResizeBound) return;
    responsiveChartResizeBound = true;

    let resizeTimer = null;
    const scheduleResize = () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(resizeDashboardCharts, 80);
    };

    window.addEventListener("resize", scheduleResize);
    if (!("ResizeObserver" in window)) return;

    const observer = new ResizeObserver(scheduleResize);
    ["balanceTrendChart", "allocationTrendChart", "assetAllocationChart"].forEach(id => {
        const canvas = document.getElementById(id);
        const parent = canvas?.parentElement;
        if (parent) observer.observe(parent);
    });
}

function bindMonthlyCashFlowRangeControl() {
    const control = document.getElementById("monthly-cash-flow-range-control");
    if (!control || control.dataset.bound === "true") return;
    control.dataset.bound = "true";
    control.addEventListener("click", async (event) => {
        const button = event.target.closest(".chart-range-btn");
        if (!button) return;
        monthlyCashFlowRange = button.dataset.range || "1Y";
        control.querySelectorAll(".chart-range-btn").forEach(btn => {
            btn.classList.toggle("active", btn === button);
        });
        await renderMonthlyAnalysis();
    });
}

export async function renderAssetAllocationChart() {
    const canvas = document.getElementById("assetAllocationChart");
    if (!canvas) return;

    try {
        const data = (await fetchAllocationAccountsCached()).totals || {};
        
        const labels = [];
        const values = [];
        const colors = [];
        
        const categoryConfig = [
            { key: "Cash", label: "Cash", color: "#3b82f6" },
            { key: "Stock", label: "Stock", color: "#10b981" },
            { key: "Bond", label: "Bond", color: "#f59e0b" },
            { key: "Real Estate", label: "Real Estate", color: "#8b5cf6" }
        ];
        
        categoryConfig.forEach(cat => {
            const val = data[cat.key] || 0.0;
            if (val > 0) {
                labels.push(cat.label);
                values.push(val);
                colors.push(cat.color);
            }
        });

        const summary = document.getElementById("portfolio-allocation-summary");
        if (summary) {
            summary.innerHTML = categoryConfig.map(cat => `
                <div>
                    <span>${cat.label}</span>
                    <strong>$${formatCurrency(data[cat.key] || 0)}</strong>
                </div>
            `).join("");
        }
        
        if (allocationChartInstance) {
            allocationChartInstance.destroy();
        }
        
        const ctx = canvas.getContext('2d');
        allocationChartInstance = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: values,
                    backgroundColor: colors,
                    borderWidth: 1,
                    borderColor: 'rgba(255, 255, 255, 0.1)'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: '#e2e8f0',
                            font: { family: 'Inter', size: 10 },
                            boxWidth: 12
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const val = context.parsed;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((val / total) * 100).toFixed(1);
                                const formattedVal = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val);
                                return ` ${context.label}: ${formattedVal} (${percentage}%)`;
                            }
                        }
                    }
                },
                cutout: '65%'
            }
        });
    } catch (e) {
        console.error("Error rendering asset allocation chart:", e);
    }
}

export async function renderMonthlyAnalysis() {
    const canvas = document.getElementById("monthlyAnalysisChart");
    const yearlyCanvas = document.getElementById("yearlyAnalysisChart");
    const tbody = document.getElementById("monthly-analysis-tbody");
    if (!canvas || !tbody) return;

    try {
        bindMonthlyCashFlowRangeControl();
        const data = await fetchMonthlyAnalysisApi();
        const months = data.months || [];
        const monthlyChartRows = filterMonthlyRowsByRange(months, monthlyCashFlowRange);
        const yearly = data.yearly || [];
        const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

        tbody.innerHTML = months.slice().reverse().map(row => `
            <tr>
                <td>${escapeHtml(row.month)}</td>
                <td>${money.format(row.income || 0)}</td>
                <td>${money.format(row.expense || 0)}</td>
                <td>${money.format(row.expense_ex_mortgage || 0)}</td>
                <td class="${(row.net_savings || 0) >= 0 ? 'amount-income' : 'amount-expense'}">${money.format(row.net_savings || 0)}</td>
                <td>${formatPercent(row.savings_rate || 0)}</td>
            </tr>
        `).join("");

        const categoryHead = document.getElementById("monthly-category-thead");
        const categoryBody = document.getElementById("monthly-category-tbody");
        const categoryOrder = data.category_order || [];
        const categoryMatrix = data.category_matrix || [];
        if (categoryHead && categoryBody) {
            categoryHead.innerHTML = `
                <tr>
                    <th>Month</th>
                    ${categoryOrder.map(category => `<th>${escapeHtml(category)}</th>`).join("")}
                </tr>
            `;
            categoryBody.innerHTML = categoryMatrix.slice().reverse().map(row => `
                <tr>
                    <td>${escapeHtml(row.month)}</td>
                    ${categoryOrder.map(category => {
                        const amount = (row.categories || {})[category] || 0;
                        return `<td>${amount ? money.format(amount) : ""}</td>`;
                    }).join("")}
                </tr>
            `).join("");
        }

        const yearlyBody = document.getElementById("yearly-analysis-tbody");
        if (yearlyBody) {
            yearlyBody.innerHTML = yearly.slice().reverse().map(row => `
                <tr>
                    <td>${escapeHtml(row.year)}</td>
                    <td>${money.format(row.income || 0)}</td>
                    <td>${money.format(row.expense || 0)}</td>
                    <td>${money.format(row.expense_ex_mortgage || 0)}</td>
                    <td class="${(row.net_savings || 0) >= 0 ? 'amount-income' : 'amount-expense'}">${money.format(row.net_savings || 0)}</td>
                    <td>${formatPercent(row.savings_rate || 0)}</td>
                </tr>
            `).join("");
        }

        const yearlyCategoryHead = document.getElementById("yearly-category-thead");
        const yearlyCategoryBody = document.getElementById("yearly-category-tbody");
        const yearlyCategoryOrder = data.yearly_category_order || [];
        const yearlyCategoryMatrix = data.yearly_category_matrix || [];
        if (yearlyCategoryHead && yearlyCategoryBody) {
            yearlyCategoryHead.innerHTML = `
                <tr>
                    <th>Year</th>
                    ${yearlyCategoryOrder.map(category => `<th>${escapeHtml(category)}</th>`).join("")}
                </tr>
            `;
            yearlyCategoryBody.innerHTML = yearlyCategoryMatrix.slice().reverse().map(row => `
                <tr>
                    <td>${escapeHtml(row.year)}</td>
                    ${yearlyCategoryOrder.map(category => {
                        const amount = (row.categories || {})[category] || 0;
                        return `<td>${amount ? money.format(amount) : ""}</td>`;
                    }).join("")}
                </tr>
            `).join("");
        }

        if (monthlyAnalysisChartInstance) monthlyAnalysisChartInstance.destroy();
        monthlyAnalysisChartInstance = new Chart(canvas.getContext("2d"), {
            type: "bar",
            data: {
                labels: monthlyChartRows.map(row => row.month),
                datasets: [
                    { label: "Income", data: monthlyChartRows.map(row => row.income || 0), backgroundColor: "#10b981" },
                    { label: "Expense", data: monthlyChartRows.map(row => row.expense || 0), backgroundColor: "#ef4444" },
                    { label: "Net", data: monthlyChartRows.map(row => row.net_savings || 0), type: "line", borderColor: "#3b82f6", backgroundColor: "transparent", tension: 0.25 }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { labels: { color: "#e2e8f0" } } },
                scales: {
                    x: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(255,255,255,0.05)" } },
                    y: { ticks: { color: "#94a3b8", callback: value => money.format(value) }, grid: { color: "rgba(255,255,255,0.05)" } }
                }
            }
        });

        if (yearlyCanvas) {
            if (yearlyAnalysisChartInstance) yearlyAnalysisChartInstance.destroy();
            yearlyAnalysisChartInstance = new Chart(yearlyCanvas.getContext("2d"), {
                type: "bar",
                data: {
                    labels: yearly.map(row => row.year),
                    datasets: [
                        { label: "Income", data: yearly.map(row => row.income || 0), backgroundColor: "#10b981" },
                        { label: "Expense", data: yearly.map(row => row.expense || 0), backgroundColor: "#ef4444" },
                        { label: "Net", data: yearly.map(row => row.net_savings || 0), type: "line", borderColor: "#3b82f6", backgroundColor: "transparent", tension: 0.25 }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { labels: { color: "#e2e8f0" } } },
                    scales: {
                        x: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(255,255,255,0.05)" } },
                        y: { ticks: { color: "#94a3b8", callback: value => money.format(value) }, grid: { color: "rgba(255,255,255,0.05)" } }
                    }
                }
            });
        }
    } catch (e) {
        console.error("Error rendering monthly analysis:", e);
    }
}

async function refreshContextMetadata() {
    const [trips, rentalProperties] = await Promise.all([
        safeFetch(fetchTripsApi(), []),
        safeFetch(fetchRentalPropertiesApi(), [])
    ]);
    state.trips = trips || [];
    state.rentalProperties = rentalProperties || [];
}

function renderTripManager() {
    const container = document.getElementById("trip-manager-container");
    if (!container) return;
    const trips = (state.trips || []).slice().sort((a, b) => String(b.year || "").localeCompare(String(a.year || "")) || String(a.name || "").localeCompare(String(b.name || "")));
    const row = (trip = {}, key = "new") => `
        <tr>
            <td><input id="trip-year-${key}" class="table-input" type="number" value="${escapeHtml(trip.year || "")}" placeholder="Year"></td>
            <td><input id="trip-name-${key}" class="table-input" value="${escapeHtml(trip.name || "")}" placeholder="Trip name"></td>
            <td><input id="trip-destination-${key}" class="table-input" value="${escapeHtml(trip.destination || "")}" placeholder="Destination"></td>
            <td>
                <select id="trip-status-${key}" class="table-select">
                    <option value="active" ${(trip.status || "active") === "active" ? "selected" : ""}>Active</option>
                    <option value="archived" ${trip.status === "archived" ? "selected" : ""}>Archived</option>
                </select>
            </td>
            <td><input id="trip-notes-${key}" class="table-input" value="${escapeHtml(trip.notes || "")}" placeholder="Notes"></td>
            <td class="metadata-table-actions">
                <button class="sync-btn" onclick="saveTripRow('${escapeHtml(trip.id || "")}', '${key}', event)">Save</button>
                ${trip.id ? `<button class="pagination-btn" onclick="archiveTripRow('${escapeHtml(trip.id)}', event)">Archive</button>` : ""}
            </td>
        </tr>
    `;
    container.innerHTML = `
        <div class="analysis-table-wrap">
            <table class="analysis-table">
                <thead><tr><th>Year</th><th>Trip</th><th>Destination</th><th>Status</th><th>Notes</th><th>Actions</th></tr></thead>
                <tbody>${row({}, "new")}${trips.map(trip => row(trip, trip.id)).join("")}</tbody>
            </table>
        </div>
    `;
}

export function selectTripManagerItem() {}

export function fillTripManagerForm() {}

export async function saveTripRow(id, key, event) {
    if (event) event.preventDefault();
    const payload = {
        name: document.getElementById(`trip-name-${key}`)?.value || "",
        year: document.getElementById(`trip-year-${key}`)?.value || "",
        destination: document.getElementById(`trip-destination-${key}`)?.value || "",
        status: document.getElementById(`trip-status-${key}`)?.value || "active",
        notes: document.getElementById(`trip-notes-${key}`)?.value || ""
    };
    if (!payload.name.trim()) return alert("Trip name is required.");
    const res = id ? await updateTripApi(id, payload) : await createTripApi(payload);
    if (res.error) return alert(res.error);
    await refreshContextMetadata();
    renderTripManager();
    renderTravelAnalysis();
    renderTransactionsList();
}

export async function saveTripManagerForm(event) {
    return saveTripRow("", "new", event);
}

export async function archiveTripRow(id, event) {
    if (event) event.preventDefault();
    if (!id) return;
    const res = await deleteTripApi(id);
    if (res.error) return alert(res.error);
    await refreshContextMetadata();
    renderTripManager();
    renderTravelAnalysis();
    renderTransactionsList();
}

export async function archiveTripManagerSelection(event) {
    if (event) event.preventDefault();
}

function renderRentalManager() {
    const container = document.getElementById("rental-manager-container");
    if (!container) return;
    const properties = (state.rentalProperties || []).slice().sort((a, b) => Number(b.active || 0) - Number(a.active || 0) || String(a.name || "").localeCompare(String(b.name || "")));
    const row = (prop = {}, key = "new") => `
        <tr>
            <td><input id="rental-name-${key}" class="table-input" value="${escapeHtml(prop.name || "")}" placeholder="Property"></td>
            <td><input id="rental-address-${key}" class="table-input" value="${escapeHtml(prop.address || "")}" placeholder="Address"></td>
            <td><input id="rental-city-${key}" class="table-input" value="${escapeHtml(prop.city || "")}" placeholder="City"></td>
            <td><input id="rental-state-${key}" class="table-input" value="${escapeHtml(prop.state || "")}" placeholder="State"></td>
            <td>
                <select id="rental-active-${key}" class="table-select">
                    <option value="1" ${Number(prop.active ?? 1) === 1 ? "selected" : ""}>Active</option>
                    <option value="0" ${Number(prop.active ?? 1) === 0 ? "selected" : ""}>Inactive</option>
                </select>
            </td>
            <td><input id="rental-notes-${key}" class="table-input" value="${escapeHtml(prop.notes || "")}" placeholder="Notes"></td>
            <td class="metadata-table-actions">
                <button class="sync-btn" onclick="saveRentalRow('${escapeHtml(prop.id || "")}', '${key}', event)">Save</button>
                ${prop.id ? `<button class="pagination-btn" onclick="archiveRentalRow('${escapeHtml(prop.id)}', event)">Archive</button>` : ""}
            </td>
        </tr>
    `;
    container.innerHTML = `
        <div class="analysis-table-wrap">
            <table class="analysis-table">
                <thead><tr><th>Property</th><th>Address</th><th>City</th><th>State</th><th>Status</th><th>Notes</th><th>Actions</th></tr></thead>
                <tbody>${row({}, "new")}${properties.map(prop => row(prop, prop.id)).join("")}</tbody>
            </table>
        </div>
    `;
}

export function selectRentalManagerItem() {}

export function fillRentalManagerForm() {}

export async function saveRentalRow(id, key, event) {
    if (event) event.preventDefault();
    const payload = {
        name: document.getElementById(`rental-name-${key}`)?.value || "",
        address: document.getElementById(`rental-address-${key}`)?.value || "",
        city: document.getElementById(`rental-city-${key}`)?.value || "",
        state: document.getElementById(`rental-state-${key}`)?.value || "",
        active: Number(document.getElementById(`rental-active-${key}`)?.value || 1),
        notes: document.getElementById(`rental-notes-${key}`)?.value || ""
    };
    if (!payload.name.trim()) return alert("Property name is required.");
    const res = id ? await updateRentalPropertyApi(id, payload) : await createRentalPropertyApi(payload);
    if (res.error) return alert(res.error);
    await refreshContextMetadata();
    renderRentalManager();
    await renderRentalRuleManager();
    renderRentalAnalysis();
    renderTransactionsList();
}

export async function saveRentalManagerForm(event) {
    return saveRentalRow("", "new", event);
}

export async function archiveRentalRow(id, event) {
    if (event) event.preventDefault();
    if (!id) return;
    const res = await deleteRentalPropertyApi(id);
    if (res.error) return alert(res.error);
    await refreshContextMetadata();
    renderRentalManager();
    await renderRentalRuleManager();
    renderRentalAnalysis();
    renderTransactionsList();
}

export async function archiveRentalManagerSelection(event) {
    if (event) event.preventDefault();
}

export async function renderRentalRuleManager() {
    const container = document.getElementById("rental-rule-manager-container");
    if (!container) return;
    const properties = state.rentalProperties || [];
    const previousPropertyId = container.dataset.propertyId || "";
    const propertyId = document.getElementById("rental-rule-property-select")?.value || previousPropertyId || properties[0]?.id || "";
    container.dataset.propertyId = propertyId;
    if (!propertyId) {
        container.innerHTML = `<div class="allocation-empty">Create or select a rental property first.</div>`;
        return;
    }
    const rules = await safeFetch(fetchRentalPropertyRulesApi(propertyId), []);
    const row = (rule = {}, key = "new") => `
        <tr>
            <td><input id="rental-rule-name-${key}" class="table-input" value="${escapeHtml(rule.name || "")}" placeholder="Rule"></td>
            <td><input id="rental-rule-merchant-${key}" class="table-input" value="${escapeHtml(rule.merchant_contains || "")}" placeholder="Merchant"></td>
            <td><input id="rental-rule-account-${key}" class="table-input" value="${escapeHtml(rule.account_name_contains || "")}" placeholder="Account"></td>
            <td>
                <select id="rental-rule-direction-${key}" class="table-select">
                    <option value="" ${!rule.direction ? "selected" : ""}>Any</option>
                    <option value="outflow" ${rule.direction === "outflow" ? "selected" : ""}>Outflow</option>
                    <option value="inflow" ${rule.direction === "inflow" ? "selected" : ""}>Inflow</option>
                </select>
            </td>
            <td><input id="rental-rule-min-${key}" class="table-input" type="number" step="0.01" value="${escapeHtml(rule.amount_min ?? "")}" placeholder="Min"></td>
            <td><input id="rental-rule-max-${key}" class="table-input" type="number" step="0.01" value="${escapeHtml(rule.amount_max ?? "")}" placeholder="Max"></td>
            <td><input id="rental-rule-subtype-${key}" class="table-input" value="${escapeHtml(rule.default_subtype || "")}" placeholder="Subtype"></td>
            <td>
                <select id="rental-rule-enabled-${key}" class="table-select">
                    <option value="1" ${Number(rule.enabled ?? 1) === 1 ? "selected" : ""}>Enabled</option>
                    <option value="0" ${Number(rule.enabled ?? 1) === 0 ? "selected" : ""}>Disabled</option>
                </select>
            </td>
            <td class="metadata-table-actions">
                <button class="sync-btn" onclick="saveRentalRuleRow('${escapeHtml(rule.id || "")}', '${key}', event)">Save</button>
                ${rule.id ? `<button class="pagination-btn" onclick="deleteRentalRule('${escapeHtml(rule.id)}', event)">Delete</button>` : ""}
            </td>
        </tr>
    `;
    container.innerHTML = `
        <div class="metadata-rule-toolbar">
            <select id="rental-rule-property-select" class="table-select" onchange="renderRentalRuleManager()">
                ${properties.map(prop => `<option value="${escapeHtml(prop.id)}" ${prop.id === propertyId ? "selected" : ""}>${escapeHtml(prop.name || "Property")}</option>`).join("")}
            </select>
            <button class="pagination-btn" onclick="applyRentalRules(event)">Apply to unreviewed</button>
        </div>
        <div class="analysis-table-wrap mt-4">
            <table class="analysis-table">
                <thead><tr><th>Name</th><th>Merchant</th><th>Account</th><th>Direction</th><th>Min</th><th>Max</th><th>Subtype</th><th>Status</th><th>Actions</th></tr></thead>
                <tbody>${row({}, "new")}${rules.map(rule => row(rule, rule.id)).join("")}</tbody>
            </table>
        </div>
    `;
    container.dataset.rules = JSON.stringify(rules);
}

export function fillRentalRuleForm() {}

export function clearRentalRuleForm(event) {
    if (event) event.preventDefault();
}

export async function saveRentalRuleRow(ruleId, key, event) {
    if (event) event.preventDefault();
    const propertyId = document.getElementById("rental-rule-property-select")?.value || document.getElementById("rental-rule-manager-container")?.dataset.propertyId || "";
    if (!propertyId) return alert("Select a rental property first.");
    const payload = {
        rental_property_id: propertyId,
        name: document.getElementById(`rental-rule-name-${key}`)?.value || "",
        merchant_contains: document.getElementById(`rental-rule-merchant-${key}`)?.value || "",
        account_name_contains: document.getElementById(`rental-rule-account-${key}`)?.value || "",
        direction: document.getElementById(`rental-rule-direction-${key}`)?.value || "",
        amount_min: document.getElementById(`rental-rule-min-${key}`)?.value || "",
        amount_max: document.getElementById(`rental-rule-max-${key}`)?.value || "",
        default_subtype: document.getElementById(`rental-rule-subtype-${key}`)?.value || "",
        enabled: Number(document.getElementById(`rental-rule-enabled-${key}`)?.value || 1)
    };
    const res = ruleId ? await updateRentalPropertyRuleApi(ruleId, payload) : await createRentalPropertyRuleApi(payload);
    if (res.error) return alert(res.error);
    await renderRentalRuleManager();
}

export async function saveRentalRuleForm(event) {
    return saveRentalRuleRow("", "new", event);
}

export async function deleteRentalRule(ruleId, event) {
    if (event) event.stopPropagation();
    const res = await deleteRentalPropertyRuleApi(ruleId);
    if (res.error) return alert(res.error);
    await renderRentalRuleManager();
}

export async function applyRentalRules(event) {
    if (event) event.preventDefault();
    const propertyId = document.getElementById("rental-rule-property-select")?.value || document.getElementById("rental-rule-manager-container")?.dataset.propertyId || "";
    const res = await applyRentalPropertyRulesApi({ rental_property_id: propertyId });
    if (res.error) return alert(res.error);
    alert(`Updated ${res.updated_count || 0} transaction(s).`);
    await loadData({ preserveScroll: true });
}

export async function renderTravelAnalysis() {
    const tripsHead = document.getElementById("travel-trips-thead");
    const tripsBody = document.getElementById("travel-trips-tbody");
    if (!tripsHead || !tripsBody) return;

    try {
        const data = await fetchTravelAnalysisApi();
        const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
        const categories = data.category_order || [];
        travelTripsByKey = {};
        tripsHead.innerHTML = `
            <tr>
                <th>Trip</th>
                <th>Total Spend</th>
                ${categories.map(category => `<th>${escapeHtml(category)}</th>`).join("")}
            </tr>
        `;

        const rows = [];
        (data.years || []).forEach(group => {
            rows.push(`
                <tr class="travel-year-row">
                    <td>${escapeHtml(group.year)}</td>
                    <td></td>
                    ${categories.map(() => `<td></td>`).join("")}
                </tr>
            `);
            (group.trips || []).forEach(trip => {
                const tripKey = stableReportKey("trip", trip.trip_id, [trip.year, trip.trip]);
                travelTripsByKey[tripKey] = trip;
                rows.push(`
                    <tr class="travel-trip-row" data-trip-key="${escapeHtml(tripKey)}">
                        <td>
                            <div class="allocation-primary">${escapeHtml(trip.trip)}</div>
                            <div class="allocation-secondary">${escapeHtml(trip.last_date || "")}</div>
                        </td>
                        <td>${money.format(trip.total || 0)}</td>
                        ${categories.map(category => {
                            const amount = (trip.categories || {})[category] || 0;
                            return `<td>${amount ? money.format(amount) : ""}</td>`;
                        }).join("")}
                    </tr>
                `);
            });
        });
        tripsBody.innerHTML = rows.join("") || `
            <tr>
                <td colspan="${categories.length + 2}" class="allocation-empty">No travel spending found.</td>
            </tr>
        `;
        tripsBody.querySelectorAll(".travel-trip-row").forEach(row => {
            row.addEventListener("click", () => {
                tripsBody.querySelectorAll(".travel-trip-row").forEach(item => item.classList.toggle("selected", item === row));
                renderTravelTripTransactions(row.dataset.tripKey);
            });
        });

        const firstTripRow = tripsBody.querySelector(".travel-trip-row");
        if (firstTripRow) {
            firstTripRow.classList.add("selected");
            renderTravelTripTransactions(firstTripRow.dataset.tripKey);
        } else {
            renderTravelTripTransactions("");
        }
    } catch (e) {
        console.error("Error rendering travel analysis:", e);
    }
}

function renderTravelAccountIcon(tx) {
    let iconName = "landmark";
    if (tx.account_type === "credit") iconName = "credit-card";
    else if (tx.account_type === "depository") iconName = "wallet";
    else if (tx.account_type === "loan") iconName = "home";
    else if (tx.account_type === "investment") iconName = "trending-up";

    if (tx.account_name === "Legacy" || tx.account_name_raw === "Legacy") {
        return `<div class="account-icon-container" title="Legacy manual entry"><i data-lucide="edit-3" style="width:14px;height:14px;"></i></div>`;
    }

    const accountName = tx.account_name || tx.account_name_raw || "Unknown account";
    const tooltipText = tx.institution_name ? `${tx.institution_name} - ${accountName}` : accountName;
    return `<div class="account-icon-container" title="${escapeHtml(tooltipText)}"><i data-lucide="${iconName}" style="width:14px;height:14px;"></i></div>`;
}

function renderTravelTripTransactions(tripKey) {
    const title = document.getElementById("travel-transactions-title");
    const tbody = document.getElementById("travel-transactions-tbody");
    if (!tbody) return;

    const trip = travelTripsByKey[tripKey];
    const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });
    if (!trip) {
        if (title) title.textContent = "Trip Transactions";
        tbody.innerHTML = `<tr><td colspan="6" class="allocation-empty">Select a trip to view transactions.</td></tr>`;
        return;
    }

    if (title) title.textContent = `${trip.year} ${trip.trip} Transactions`;
    tbody.innerHTML = (trip.transactions || []).map(tx => `
        <tr>
            <td>${escapeHtml(tx.date || "")}</td>
            <td class="travel-account-cell">${renderTravelAccountIcon(tx)}</td>
            <td>${escapeHtml(tx.merchant || "")}</td>
            <td>${escapeHtml(tx.category || "Unclassified")}</td>
            <td>${money.format(tx.amount || 0)}</td>
            <td>${escapeHtml(tx.note || "")}</td>
        </tr>
    `).join("") || `<tr><td colspan="6" class="allocation-empty">No transactions found for this trip.</td></tr>`;
    lucide.createIcons();
}

export async function renderRentalAnalysis() {
    const propertiesHead = document.getElementById("rental-properties-thead");
    const propertiesBody = document.getElementById("rental-properties-tbody");
    if (!propertiesHead || !propertiesBody) return;

    try {
        const data = await fetchRentalAnalysisApi();
        const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
        const categories = data.category_order || [];
        rentalPropertiesByKey = {};

        propertiesHead.innerHTML = `
            <tr>
                <th>Property</th>
                <th>Net</th>
                <th>Income</th>
                <th>Expense</th>
                ${categories.map(category => `<th>${escapeHtml(category)}</th>`).join("")}
            </tr>
        `;

        propertiesBody.innerHTML = (data.properties || []).map(property => {
            const key = stableReportKey("property", property.property_id, [property.property]);
            rentalPropertiesByKey[key] = property;
            return `
                <tr class="rental-property-row" data-property-key="${escapeHtml(key)}">
                    <td>
                        <div class="allocation-primary">${escapeHtml(property.property || "Unassigned")}</div>
                        <div class="allocation-secondary">${escapeHtml(property.last_date || "")} · ${property.count || 0} transactions</div>
                    </td>
                    <td class="${(property.total || 0) >= 0 ? 'amount-income' : 'amount-expense'}">${money.format(property.total || 0)}</td>
                    <td class="amount-income">${money.format(property.income || 0)}</td>
                    <td class="amount-expense">${money.format(property.expense || 0)}</td>
                    ${categories.map(category => {
                        const amount = (property.categories || {})[category] || 0;
                        const className = amount >= 0 ? "amount-income" : "amount-expense";
                        return `<td class="${amount ? className : ""}">${amount ? money.format(amount) : ""}</td>`;
                    }).join("")}
                </tr>
            `;
        }).join("") || `
            <tr>
                <td colspan="${categories.length + 4}" class="allocation-empty">No rental transactions found.</td>
            </tr>
        `;

        propertiesBody.querySelectorAll(".rental-property-row").forEach(row => {
            row.addEventListener("click", () => {
                propertiesBody.querySelectorAll(".rental-property-row").forEach(item => item.classList.toggle("selected", item === row));
                renderRentalPropertyDetails(row.dataset.propertyKey, categories);
            });
        });

        const firstPropertyRow = propertiesBody.querySelector(".rental-property-row");
        if (firstPropertyRow) {
            firstPropertyRow.classList.add("selected");
            renderRentalPropertyDetails(firstPropertyRow.dataset.propertyKey, categories);
        } else {
            renderRentalPropertyDetails("", categories);
        }
    } catch (e) {
        console.error("Error rendering rental analysis:", e);
    }
}

function renderRentalMatrixTable(head, body, label, rows, categories) {
    const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
    if (!head || !body) return;

    head.innerHTML = `
        <tr>
            <th>${escapeHtml(label)}</th>
            <th>Net</th>
            ${categories.map(category => `<th>${escapeHtml(category)}</th>`).join("")}
        </tr>
    `;
    body.innerHTML = (rows || []).slice().reverse().map(row => `
        <tr>
            <td>${escapeHtml(row.month || row.year || "")}</td>
            <td class="${(row.total || 0) >= 0 ? 'amount-income' : 'amount-expense'}">${money.format(row.total || 0)}</td>
            ${categories.map(category => {
                const amount = (row.categories || {})[category] || 0;
                const className = amount >= 0 ? "amount-income" : "amount-expense";
                return `<td class="${amount ? className : ""}">${amount ? money.format(amount) : ""}</td>`;
            }).join("")}
        </tr>
    `).join("") || `<tr><td colspan="${categories.length + 2}" class="allocation-empty">No summary data found.</td></tr>`;
}

function renderRentalPropertyDetails(propertyKey, categories) {
    const title = document.getElementById("rental-transactions-title");
    const summaryTitle = document.getElementById("rental-summary-title");
    const tbody = document.getElementById("rental-transactions-tbody");
    const monthlyHead = document.getElementById("rental-monthly-thead");
    const monthlyBody = document.getElementById("rental-monthly-tbody");
    const yearlyHead = document.getElementById("rental-yearly-thead");
    const yearlyBody = document.getElementById("rental-yearly-tbody");
    if (!tbody) return;

    const property = rentalPropertiesByKey[propertyKey];
    const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });
    if (!property) {
        if (title) title.textContent = "Rental Transactions";
        if (summaryTitle) summaryTitle.textContent = "Rental Summary";
        tbody.innerHTML = `<tr><td colspan="5" class="allocation-empty">Select a property to view transactions.</td></tr>`;
        renderRentalMatrixTable(monthlyHead, monthlyBody, "Month", [], categories || []);
        renderRentalMatrixTable(yearlyHead, yearlyBody, "Year", [], categories || []);
        return;
    }

    if (title) title.textContent = `${property.property} Transactions`;
    if (summaryTitle) summaryTitle.textContent = `${property.property} Summary`;
    tbody.innerHTML = (property.transactions || []).map(tx => {
        const amount = tx.amount || 0;
        return `
            <tr>
                <td>${escapeHtml(tx.date || "")}</td>
                <td class="travel-account-cell">${renderTravelAccountIcon(tx)}</td>
                <td>${escapeHtml(tx.merchant || "")}</td>
                <td>${escapeHtml(tx.category || "Unclassified")}</td>
                <td class="${amount >= 0 ? 'amount-income' : 'amount-expense'}">${money.format(amount)}</td>
            </tr>
        `;
    }).join("") || `<tr><td colspan="5" class="allocation-empty">No transactions found for this property.</td></tr>`;

    renderRentalMatrixTable(monthlyHead, monthlyBody, "Month", property.monthly_matrix || [], categories || []);
    renderRentalMatrixTable(yearlyHead, yearlyBody, "Year", property.yearly_matrix || [], categories || []);
    lucide.createIcons();
}

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function renderBucketCells(categories) {
    const buckets = categories || {};
    return ["Cash", "Stock", "Bond", "Real Estate"].map(key => {
        const val = buckets[key] || 0;
        return `<td class="allocation-bucket-cell">$${formatCurrency(val)}</td>`;
    }).join("");
}

function allocationDomId(accountId) {
    return String(accountId || "").replace(/[^a-zA-Z0-9_-]/g, "_");
}

export async function toggleAccountBalanceHistory(accountId, event) {
    if (event) event.stopPropagation();
    if (expandedAllocationAccountId === accountId) {
        expandedAllocationAccountId = "";
        Object.values(accountBalanceChartInstances).forEach(chart => chart?.destroy?.());
        Object.keys(accountBalanceChartInstances).forEach(key => delete accountBalanceChartInstances[key]);
        await renderInstitutionAllocationDetails();
        return;
    }
    expandedAllocationAccountId = accountId;
    accountBalanceHistoryRange = "1M";
    await renderInstitutionAllocationDetails();
}

export async function setAccountBalanceHistoryRange(accountId, rangeKey, event) {
    if (event) event.stopPropagation();
    accountBalanceHistoryRange = rangeKey || "1M";
    await renderExpandedAccountBalanceHistory(accountId, true);
}

async function fetchAccountBalanceHistoryCached(accountId, rangeKey, force = false) {
    const cacheKey = `${accountId}::${rangeKey}`;
    if (!force && accountBalanceHistoryCache[cacheKey]) return accountBalanceHistoryCache[cacheKey];
    const payload = await fetchAccountBalanceHistoryApi(accountId, rangeKey);
    accountBalanceHistoryCache[cacheKey] = payload;
    return payload;
}

async function renderExpandedAccountBalanceHistory(accountId, force = false) {
    const safeId = allocationDomId(accountId);
    const canvas = document.getElementById(`account-balance-chart-${safeId}`);
    const status = document.getElementById(`account-balance-status-${safeId}`);
    const rangeWrap = document.getElementById(`account-balance-ranges-${safeId}`);
    if (!canvas) return;
    if (status) status.textContent = "Loading balance history...";

    try {
        const payload = await fetchAccountBalanceHistoryCached(accountId, accountBalanceHistoryRange, force);
        const history = payload.history || [];
        if (rangeWrap) {
            rangeWrap.querySelectorAll("button[data-range]").forEach(btn => {
                btn.classList.toggle("active", btn.dataset.range === accountBalanceHistoryRange);
            });
        }
        if (accountBalanceChartInstances[accountId]) {
            accountBalanceChartInstances[accountId].destroy();
            delete accountBalanceChartInstances[accountId];
        }
        if (!history.length) {
            if (status) status.textContent = "No balance history yet.";
            return;
        }
        if (status) {
            const first = history[0]?.date || "";
            const last = history[history.length - 1]?.date || "";
            status.textContent = `${history.length} points${first && last ? ` · ${first} to ${last}` : ""}`;
        }
        const currencyFormatter = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
        accountBalanceChartInstances[accountId] = new Chart(canvas.getContext("2d"), {
            type: "line",
            data: {
                datasets: [{
                    label: "Balance",
                    data: history.map(row => ({
                        x: new Date(`${row.date}T00:00:00`).getTime(),
                        y: row.balance || 0
                    })),
                    borderColor: "#3b82f6",
                    backgroundColor: "rgba(59, 130, 246, 0.12)",
                    borderWidth: 2,
                    pointRadius: history.length > 45 ? 0 : 2,
                    pointHoverRadius: 4,
                    tension: 0.25,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title: items => {
                                const value = items[0]?.parsed?.x;
                                return value ? new Date(value).toLocaleDateString() : "";
                            },
                            label: item => currencyFormatter.format(item.parsed.y || 0)
                        }
                    }
                },
                scales: {
                    x: {
                        type: "linear",
                        ticks: {
                            color: "#94a3b8",
                            callback: value => new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric" }),
                            maxTicksLimit: 6
                        },
                        grid: { color: "rgba(148, 163, 184, 0.12)" }
                    },
                    y: {
                        ticks: { color: "#94a3b8", callback: value => currencyFormatter.format(value) },
                        grid: { color: "rgba(148, 163, 184, 0.12)" }
                    }
                }
            }
        });
    } catch (e) {
        console.error("Error rendering account balance history:", e);
        if (status) status.textContent = "Unable to load balance history.";
    }
}

export async function renderInstitutionAllocationDetails() {
    const container = document.getElementById("institution-allocation-container");
    if (!container) return;

    Object.values(accountBalanceChartInstances).forEach(chart => chart?.destroy?.());
    Object.keys(accountBalanceChartInstances).forEach(key => delete accountBalanceChartInstances[key]);

    container.innerHTML = `
        <div class="allocation-empty">
            <i data-lucide="loader-2" class="spin"></i>
            <span>Loading account allocation...</span>
        </div>
    `;
    lucide.createIcons();

    try {
        const data = await fetchAllocationAccountsCached();
        const accounts = data.accounts || [];
        const totals = data.totals || {};

        if (accounts.length === 0) {
            container.innerHTML = `
                <div class="allocation-empty">
                    <i data-lucide="info"></i>
                    <span>No allocatable accounts found.</span>
                </div>
            `;
            lucide.createIcons();
            return;
        }

        const sourceLabels = {
            holdings: "Holdings",
            manual_override: "Manual",
            cash_default: "Cash default",
            needs_allocation: "Needs allocation",
            limited_support: "Limited support",
            default_cash: "Cash default",
            manual: "Manual",
            manual_asset: "Manual asset",
            auto: "Auto"
        };

        const groupedAccounts = accounts.reduce((groups, acc) => {
            const key = acc.institution_name || "Unknown";
            if (!groups[key]) groups[key] = [];
            groups[key].push(acc);
            return groups;
        }, {});

        const accountRows = Object.keys(groupedAccounts).sort().map(institutionName => {
            const group = groupedAccounts[institutionName];
            const groupTotal = group.reduce((sum, acc) => sum + (acc.balance_current || 0), 0);
            const bankRow = `
            <tr class="allocation-bank-row">
                <td colspan="9">
                    <div class="allocation-bank-name">${escapeHtml(institutionName)}</div>
                    <div class="allocation-bank-total">$${formatCurrency(groupTotal)}</div>
                </td>
            </tr>`;
            const rows = group.map(acc => {
                const pct = acc.percentages || {};
                const id = escapeHtml(acc.account_id);
                const safeDomId = allocationDomId(acc.account_id);
                const manualDisabled = acc.source === "manual_asset" ? "disabled" : "";
                const source = acc.source || "auto";
                const sourceClass = `allocation-source-${escapeHtml(source)}`;
                const warning = acc.allocation_warning ? ` title="${escapeHtml(acc.allocation_warning)}"` : "";
                const isExpanded = expandedAllocationAccountId === acc.account_id;
                const historyButtons = ["1M", "3M", "1Y", "5Y", "ALL"].map(range => `
                    <button class="pagination-btn account-balance-range-btn ${range === accountBalanceHistoryRange ? "active" : ""}" data-range="${range}" onclick="setAccountBalanceHistoryRange('${id}', '${range}', event)">${range === "ALL" ? "All" : range}</button>
                `).join("");
                const accountRow = `
            <tr class="account-allocation-row">
                <td class="allocation-account-cell">
                    <div class="allocation-primary">${escapeHtml(acc.name || "Account")}</div>
                    <div class="allocation-secondary">${escapeHtml([acc.type, acc.subtype].filter(Boolean).join(" / "))}</div>
                </td>
                <td class="allocation-source-cell"><span class="allocation-source ${sourceClass}"${warning}>${escapeHtml(sourceLabels[source] || source || "Auto")}</span></td>
                <td class="allocation-balance-cell">$${formatCurrency(acc.balance_current || 0)}</td>
                ${renderBucketCells(acc.categories)}
                <td class="allocation-percent-cell allocation-manual-cell">
                    <div class="allocation-percent-grid" data-account-id="${id}">
                        ${["Cash", "Stock", "Bond", "Real Estate"].map(key => `
                            <label>
                                <span>${key}</span>
                                <input class="manual-allocation-input" type="number" min="0" max="100" step="1" value="${(pct[key] || 0).toFixed(0)}" data-category="${key}" ${manualDisabled}>
                            </label>
                        `).join("")}
                    </div>
                </td>
                <td class="allocation-action-cell">
                    <div class="allocation-actions">
                        <button class="pagination-btn allocation-save-btn" onclick="saveAllocationOverride('${id}', event)" ${manualDisabled}>Save</button>
                        <button class="pagination-btn allocation-auto-btn" onclick="clearAllocationOverride('${id}', event)" ${manualDisabled}>Auto</button>
                        <button class="pagination-btn allocation-history-btn" onclick="toggleAccountBalanceHistory('${id}', event)" title="Balance history">
                            <i data-lucide="${isExpanded ? "chevron-up" : "line-chart"}"></i>
                        </button>
                    </div>
                </td>
            </tr>`;
                const detailRow = isExpanded ? `
            <tr class="account-balance-detail-row">
                <td colspan="9">
                    <div class="account-balance-detail">
                        <div class="account-balance-detail-header">
                            <div>
                                <div class="allocation-primary">Balance History</div>
                                <div class="allocation-secondary" id="account-balance-status-${safeDomId}">Loading balance history...</div>
                            </div>
                            <div class="account-balance-range-controls" id="account-balance-ranges-${safeDomId}">
                                ${historyButtons}
                            </div>
                        </div>
                        <div class="account-balance-chart-wrap">
                            <canvas id="account-balance-chart-${safeDomId}"></canvas>
                        </div>
                    </div>
                </td>
            </tr>` : "";
                return accountRow + detailRow;
            }).join("");
            return bankRow + rows;
        }).join("");

        container.innerHTML = `
            <div class="allocation-summary-row">
                <div>
                    <div class="allocation-primary">Account Allocation</div>
                    <div class="allocation-secondary">Grouped by bank. Manual percentages override automatic holdings; accounts without holdings default to Cash.</div>
                </div>
                <div class="allocation-total">$${formatCurrency(Object.values(totals).reduce((sum, val) => sum + (val || 0), 0))}</div>
            </div>
            <div class="allocation-table-wrap">
                <table class="allocation-table allocation-account-table">
                    <thead>
                        <tr>
                            <th>Account</th>
                            <th>Source</th>
                            <th>Balance</th>
                            <th>Cash</th>
                            <th>Stock</th>
                            <th>Bond</th>
                            <th>Real Estate</th>
                            <th>Manual %</th>
                            <th></th>
                        </tr>
                    </thead>
                    <tbody>${accountRows}</tbody>
                </table>
            </div>
        `;
        if (expandedAllocationAccountId) {
            await renderExpandedAccountBalanceHistory(expandedAllocationAccountId);
        }
    } catch (e) {
        console.error("Error rendering institution allocation details:", e);
        container.innerHTML = `
            <div class="allocation-empty allocation-error">
                <i data-lucide="alert-circle"></i>
                <span>Unable to load account allocation.</span>
            </div>
        `;
    }

    lucide.createIcons();
}

function readAllocationPercentages(accountId) {
    const grid = document.querySelector(`.allocation-percent-grid[data-account-id="${CSS.escape(accountId)}"]`);
    const percentages = {};
    if (!grid) return percentages;
    grid.querySelectorAll("input[data-category]").forEach(input => {
        percentages[input.getAttribute("data-category")] = parseFloat(input.value) || 0;
    });
    return percentages;
}

export async function saveAllocationOverride(accountId, event) {
    if (event) event.stopPropagation();
    try {
        await saveAllocationOverrideApi(accountId, readAllocationPercentages(accountId), false);
        await Promise.all([
            fetchAllocationHistoryCached(true),
            fetchAllocationAccountsCached(true)
        ]);
        await renderBalanceTrendChart();
        await renderAssetAllocationChart();
        await renderInstitutionAllocationDetails();
    } catch (e) {
        alert("Failed to save allocation override: " + e.message);
    }
}

export async function clearAllocationOverride(accountId, event) {
    if (event) event.stopPropagation();
    try {
        await saveAllocationOverrideApi(accountId, {}, true);
        await Promise.all([
            fetchAllocationHistoryCached(true),
            fetchAllocationAccountsCached(true)
        ]);
        await renderBalanceTrendChart();
        await renderAssetAllocationChart();
        await renderInstitutionAllocationDetails();
    } catch (e) {
        alert("Failed to clear allocation override: " + e.message);
    }
}

export function triggerFilterUpdate() {
    const searchInput = document.getElementById("tx-search-input");
    const startDateInput = document.getElementById("tx-start-date");
    const endDateInput = document.getElementById("tx-end-date");
    const accountSelect = document.getElementById("tx-account-filter");
    const assignmentSelect = document.getElementById("tx-assignment-filter");
    const amountInput = document.getElementById("tx-amount-filter");
    state.currentFilters.search = searchInput ? searchInput.value.trim() : "";
    state.currentFilters.direction = getMultiselectValues("filter-direction-container");
    state.currentFilters.category = getMultiselectValues("filter-category-container");
    state.currentFilters.reviewed = getMultiselectValues("filter-reviewed-container");
    state.currentFilters.startDate = startDateInput ? startDateInput.value : "";
    state.currentFilters.endDate = endDateInput ? endDateInput.value : "";
    state.currentFilters.account = accountSelect ? accountSelect.value : "all";
    state.currentFilters.assignment = assignmentSelect ? assignmentSelect.value : "all";
    state.currentFilters.amount = amountInput ? amountInput.value.trim() : "";
    
    state.currentPage = 1;
    loadData();
}

function getMonthDateRange(monthValue) {
    if (!monthValue) return { start: "", end: "" };
    const [year, month] = monthValue.split("-").map(Number);
    if (!year || !month) return { start: "", end: "" };
    const start = `${year}-${String(month).padStart(2, "0")}-01`;
    const lastDay = new Date(year, month, 0).getDate();
    const end = `${year}-${String(month).padStart(2, "0")}-${String(lastDay).padStart(2, "0")}`;
    return { start, end };
}

function syncMonthFilterFromDates() {
    const monthInput = document.getElementById("tx-month-filter");
    const startDateInput = document.getElementById("tx-start-date");
    const endDateInput = document.getElementById("tx-end-date");
    if (!monthInput || !startDateInput || !endDateInput || !monthInput.value) return;

    const { start, end } = getMonthDateRange(monthInput.value);
    if (startDateInput.value !== start || endDateInput.value !== end) {
        monthInput.value = "";
    }
}

export async function updateCategoryFilterOptions() {
    try {
        const categories = state.categoriesConfig.categories;
        populateCategoryMultiselectOptions(categories, triggerFilterUpdate);
    } catch (e) {
        console.error("Error setting category filter options:", e);
    }
}

export async function updateTransactionFilterOptions() {
    if (transactionFilterOptionsLoaded) return;
    try {
        const options = await fetchTransactionFilterOptionsApi();
        const accountSelect = document.getElementById("tx-account-filter");
        const assignmentSelect = document.getElementById("tx-assignment-filter");
        const monthInput = document.getElementById("tx-month-filter");
        const startDateInput = document.getElementById("tx-start-date");
        const endDateInput = document.getElementById("tx-end-date");
        if (monthInput && options.min_date) monthInput.min = options.min_date.slice(0, 7);
        if (monthInput && options.max_date) monthInput.max = options.max_date.slice(0, 7);
        if (startDateInput && options.min_date) startDateInput.min = options.min_date;
        if (startDateInput && options.max_date) startDateInput.max = options.max_date;
        if (endDateInput && options.min_date) endDateInput.min = options.min_date;
        if (endDateInput && options.max_date) endDateInput.max = options.max_date;
        if (accountSelect) {
            accountSelect.innerHTML = `<option value="all">All accounts</option>`;
            (options.accounts || []).forEach(acc => {
                const label = [acc.institution_name, acc.account_name].filter(Boolean).join(" / ") || acc.account_id;
                const opt = document.createElement("option");
                opt.value = acc.account_id;
                opt.textContent = `${label} (${acc.tx_count})`;
                accountSelect.appendChild(opt);
            });
        }
        if (assignmentSelect) {
            assignmentSelect.innerHTML = `<option value="all">All trips/properties</option>`;
            const addGroup = (label, items, prefix) => {
                if (!items?.length) return;
                const group = document.createElement("optgroup");
                group.label = label;
                items.forEach(item => {
                    const opt = document.createElement("option");
                    opt.value = `${prefix}:${item.id}`;
                    opt.textContent = `${item.label} (${item.tx_count})`;
                    group.appendChild(opt);
                });
                assignmentSelect.appendChild(group);
            };
            addGroup("Trips", options.trips || [], "trip");
            addGroup("Rental properties", options.rental_properties || [], "rental");
        }
        populateStatusMultiselectOptions(options.statuses || [], triggerFilterUpdate);
        transactionFilterOptionsLoaded = true;
    } catch (e) {
        console.error("Error setting transaction filter options:", e);
    }
}

function setupFilters() {
    const searchInput = document.getElementById("tx-search-input");
    const debouncedFilterUpdate = debounce(triggerFilterUpdate, 300);
    if (searchInput) searchInput.oninput = debouncedFilterUpdate;
    const monthInput = document.getElementById("tx-month-filter");
    const startDateInput = document.getElementById("tx-start-date");
    const endDateInput = document.getElementById("tx-end-date");
    const accountSelect = document.getElementById("tx-account-filter");
    const assignmentSelect = document.getElementById("tx-assignment-filter");
    const amountInput = document.getElementById("tx-amount-filter");
    if (monthInput) {
        monthInput.onchange = () => {
            const { start, end } = getMonthDateRange(monthInput.value);
            if (startDateInput) startDateInput.value = start;
            if (endDateInput) endDateInput.value = end;
            triggerFilterUpdate();
        };
    }
    if (startDateInput) {
        startDateInput.onchange = () => {
            syncMonthFilterFromDates();
            triggerFilterUpdate();
        };
    }
    if (endDateInput) {
        endDateInput.onchange = () => {
            syncMonthFilterFromDates();
            triggerFilterUpdate();
        };
    }
    if (accountSelect) accountSelect.onchange = triggerFilterUpdate;
    if (assignmentSelect) assignmentSelect.onchange = triggerFilterUpdate;
    if (amountInput) amountInput.oninput = debouncedFilterUpdate;
    
    initCustomMultiselects(triggerFilterUpdate);
    
    const firstBtn = document.getElementById("tx-first-btn");
    const prevBtn = document.getElementById("tx-prev-btn");
    const nextBtn = document.getElementById("tx-next-btn");
    const lastBtn = document.getElementById("tx-last-btn");
    
    if (firstBtn) {
        firstBtn.onclick = () => {
            if (state.currentPage > 1) {
                state.currentPage = 1;
                loadData();
            }
        };
    }
    
    if (prevBtn) {
        prevBtn.onclick = () => {
            if (state.currentPage > 1) {
                state.currentPage--;
                loadData();
            }
        };
    }
    
    if (nextBtn) {
        nextBtn.onclick = () => {
            if (state.currentPage < state.totalPages) {
                state.currentPage++;
                loadData();
            }
        };
    }
    
    if (lastBtn) {
        lastBtn.onclick = () => {
            if (state.currentPage < state.totalPages) {
                state.currentPage = state.totalPages;
                loadData();
            }
        };
    }
}

function setupSidebarCollapser() {
    const sidebarToggleBtn = document.getElementById("sidebar-toggle-btn");
    const sidebar = document.querySelector(".sidebar");
    
    if (sidebarToggleBtn && sidebar) {
        const isTabletWidth = window.matchMedia("(max-width: 1180px)").matches;
        if (isTabletWidth) {
            sidebar.classList.remove("collapsed");
            localStorage.removeItem("sidebar-collapsed");
        }

        sidebarToggleBtn.onclick = (e) => {
            if (e) e.stopPropagation();
            sidebar.classList.toggle("collapsed");
            const isCollapsed = sidebar.classList.contains("collapsed");
            
            const icon = sidebarToggleBtn.querySelector("i");
            if (icon) {
                icon.setAttribute("data-lucide", isCollapsed ? "chevron-right" : "chevron-left");
                lucide.createIcons();
            }
            
            localStorage.setItem("sidebar-collapsed", isCollapsed ? "1" : "0");
        };
        
        if (!isTabletWidth && localStorage.getItem("sidebar-collapsed") === "1") {
            sidebar.classList.add("collapsed");
            const icon = sidebarToggleBtn.querySelector("i");
            if (icon) {
                icon.setAttribute("data-lucide", "chevron-right");
                lucide.createIcons();
            }
        }
    }
}

// Expose review functions to global window context for inline HTML attributes
window.updateSplitPreview = updateSplitPreview;
window.submitTransactionReview = submitTransactionReview;
window.toggleTransactionConfirm = toggleTransactionConfirm;
window.deleteTransaction = deleteTransaction;
window.executeManualMerge = executeManualMerge;
window.executePreciseMerge = executePreciseMerge;
window.setupSidebarCollapser = setupSidebarCollapser;
window.toggleCreatePanel = toggleCreatePanel;
window.onCreateIsBChange = onCreateIsBChange;
window.updateCreateSplitPreview = updateCreateSplitPreview;
window.applyQuickTemplate = applyQuickTemplate;
window.submitCreateManual = submitCreateManual;
window.renderCategoryConfigView = renderCategoryConfigView;
window.addNewCategory = addNewCategory;
window.deleteCategory = deleteCategory;
window.onConfigRuleCategoryChange = onConfigRuleCategoryChange;
window.addNewSubcategory = addNewSubcategory;
window.deleteSubcategory = deleteSubcategory;
window.onRowCategoryChange = onRowCategoryChange;
window.onAssignmentChange = onAssignmentChange;
window.onCreateCategoryChange = onCreateCategoryChange;
window.saveCategoriesConfig = saveCategoriesConfig;
window.renderBalanceTrendChart = renderBalanceTrendChart;
window.renderAssetAllocationChart = renderAssetAllocationChart;
window.saveAllocationOverride = saveAllocationOverride;
window.clearAllocationOverride = clearAllocationOverride;
window.toggleAccountBalanceHistory = toggleAccountBalanceHistory;
window.setAccountBalanceHistoryRange = setAccountBalanceHistoryRange;
window.fillTripManagerForm = fillTripManagerForm;
window.selectTripManagerItem = selectTripManagerItem;
window.saveTripRow = saveTripRow;
window.archiveTripRow = archiveTripRow;
window.saveTripManagerForm = saveTripManagerForm;
window.archiveTripManagerSelection = archiveTripManagerSelection;
window.fillRentalManagerForm = fillRentalManagerForm;
window.selectRentalManagerItem = selectRentalManagerItem;
window.saveRentalRow = saveRentalRow;
window.archiveRentalRow = archiveRentalRow;
window.saveRentalManagerForm = saveRentalManagerForm;
window.archiveRentalManagerSelection = archiveRentalManagerSelection;
window.renderRentalRuleManager = renderRentalRuleManager;
window.fillRentalRuleForm = fillRentalRuleForm;
window.clearRentalRuleForm = clearRentalRuleForm;
window.saveRentalRuleRow = saveRentalRuleRow;
window.saveRentalRuleForm = saveRentalRuleForm;
window.deleteRentalRule = deleteRentalRule;
window.applyRentalRules = applyRentalRules;
window.loadData = loadData;
window.linkNewBank = linkNewBank;
window.replaceItemWithNewLink = replaceItemWithNewLink;

window.confirmInternalTransfer = async function(txId1, txId2, event) {
    if (event) event.stopPropagation();
    if (!confirm("Confirm these two transactions as an internal transfer?\n\nBoth transactions will be categorized as Internal Transfer and marked reviewed.")) return;
    try {
        const res = await confirmTransferApi(txId1, txId2);
        if (res.status === "success") {
            alert("Internal transfer confirmed.");
            await loadData();
        } else {
            alert("Confirmation failed: " + res.error);
        }
    } catch (err) {
        alert("Error: " + err.message);
    }
};


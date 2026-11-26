import * as SecureStore from "expo-secure-store";
import * as LocalAuthentication from "expo-local-authentication";
import Constants from "expo-constants";
import { StatusBar } from "expo-status-bar";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  AppState,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import {
  ArrowLeft,
  ChartNoAxesCombined,
  HandCoins,
  House,
  Landmark,
  Plane,
  ReceiptText,
  RefreshCw,
  Settings,
  TrendingDown,
  TrendingUp,
  Warehouse,
} from "lucide-react-native";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";

import { ApiError, createApiClient } from "./src/api/client";
import { checkBackendConnection, RequestTimeoutError } from "./src/api/connection";
import { plaidSyncMessage, type PlaidSyncResult } from "./src/api/plaidSync";
import { loginMobile } from "./src/auth/login";
import { createSessionStore, MobileSession } from "./src/auth/session";
import { MeowBillionMark } from "./src/components/MeowBillionMark";
import {
  AllocationDonut,
  RangeControl,
  TrendChart,
} from "./src/components/DashboardCharts";
import {
  createApiEndpointStore,
  DEFAULT_API_ENDPOINT,
  normalizeApiEndpoint,
} from "./src/config/apiEndpoint";
import {
  NetWorthDriversSheet,
  type NetWorthDriverSelection,
  type NetWorthDrivers,
} from "./src/dashboard/NetWorthDriversSheet";
import {
  Allocation,
  AssetBucket,
  buildDashboard,
  filterAllocationGroupsByBucket,
  filterHistoryByRange,
  HistoryPoint,
  TrendRange,
} from "./src/dashboard/model";
import {
  buildTransactionQuery,
  buildTransactionReviewPayload,
} from "./src/transactions/api";
import { TransactionsScreen as M3TransactionsScreen } from "./src/transactions/TransactionsScreen";
import { SpendingScreen } from "./src/spending/SpendingScreen";
import { AccountDetailSheet } from "./src/accounts/AccountDetailSheet";
import { RentalsScreen, TravelScreen } from "./src/context/ContextScreens";

const sessionStore = createSessionStore(SecureStore);
const apiEndpointStore = createApiEndpointStore(SecureStore);
const APP_VERSION = Constants.expoConfig?.version || "1.0.0";
const APP_UPDATED_AT =
  typeof Constants.expoConfig?.extra?.buildTime === "string"
    ? Constants.expoConfig.extra.buildTime
    : undefined;
const APP_LOCK_KEY = "meowbillion.mobile.app-lock";
const tabs = [
  { key: "home", label: "Home", icon: House },
  { key: "transactions", label: "Transactions", icon: ReceiptText },
  { key: "spending", label: "Spending", icon: ChartNoAxesCombined },
  { key: "travel", label: "Travel", icon: Plane },
  { key: "rentals", label: "Rentals", icon: Warehouse },
] as const;
type TabKey = (typeof tabs)[number]["key"];
type Account = {
  account_id: string;
  name: string;
  type: string;
  balance_current: number | null;
  institution_name?: string;
  is_virtual?: boolean;
};
type Dashboard = Pick<ReturnType<typeof buildDashboard>, "netWorth" | "portfolio" | "allocationGroups"> & {
  monthlyIncome: number | null;
  monthlyExpense: number | null;
  unreviewedCount: number | null;
  reimbursementOutstanding: number | null;
};
type OverviewAnalysis = Parameters<typeof buildDashboard>[0]["analysis"];
type DashboardHistory = { points: HistoryPoint[]; unavailable: boolean };
type ApiClient = ReturnType<typeof createApiClient>;
type Transaction = {
  TransactionID: string;
  Date: string;
  Merchant: string;
  Amount: number;
  Direction: string;
  AccountName: string;
  Type?: string;
  IsB?: string;
  Ratio?: number;
  Mown?: number;
  IsReimbursement?: number;
  Note?: string;
  SubType?: string;
  Pending?: number;
  Reviewed?: number;
};

function formatMoney(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(value);
}
function errorMessage(error: unknown) {
  if (error instanceof ApiError && error.status === 401)
    return "Your session expired. Please sign in again.";
  if (error instanceof Error && /network request failed/i.test(error.message))
    return "Unable to reach the MeowBillion server. Check the address and network connection.";
  return error instanceof Error
    ? error.message
    : "Unable to reach the MeowBillion server.";
}

export default function App() {
  const [session, setSession] = useState<MobileSession | null>(null);
  const [booting, setBooting] = useState(true);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [history, setHistory] = useState<DashboardHistory | null>(null);
  const [lastSync, setLastSync] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<TabKey>("home");
  const [moreOpen, setMoreOpen] = useState(false);
  const [apiEndpoint, setApiEndpoint] = useState(DEFAULT_API_ENDPOINT);
  const [appLockEnabled, setAppLockEnabled] = useState(false);
  const [locked, setLocked] = useState(false);
  const authenticationInFlight = useRef(false);
  const overviewRequest = useRef(0);
  const sessionVersion = useRef(0);
  const syncingRef = useRef(false);
  const signOut = useCallback(async () => {
    sessionVersion.current += 1;
    overviewRequest.current += 1;
    setSession(null);
    setDashboard(null);
    setHistory(null);
    setLastSync(null);
    setSyncMessage("");
    setLoading(false);
    setError(null);
    setTab("home");
    setMoreOpen(false);
    await sessionStore.clear();
  }, []);
  const api = useMemo(
    () => {
      const version = sessionVersion.current;
      return createApiClient({
        baseUrl: apiEndpoint,
        getToken: async () => session?.accessToken || null,
        onUnauthorized: () => {
          if (version === sessionVersion.current) return signOut();
        },
      });
    },
    [apiEndpoint, session?.accessToken, signOut],
  );
  const saveApiEndpoint = useCallback(
    async (value: string) => {
      const endpoint = await apiEndpointStore.save(value);
      if (endpoint !== apiEndpoint) {
        await signOut();
        setApiEndpoint(endpoint);
      }
      return endpoint;
    },
    [apiEndpoint, signOut],
  );
  const loadDashboard = useCallback(async () => {
    if (!session) return;
    const request = ++overviewRequest.current;
    const isCurrent = () => request === overviewRequest.current;
    const read = { retry: true };
    let allocation: Allocation | undefined;
    let analysis: OverviewAnalysis | undefined;
    let unreviewedCount: number | null = null;
    let reimbursementOutstanding: number | null = null;
    const publish = () => {
      if (!allocation || !isCurrent()) return;
      const summary = buildDashboard({
        allocation,
        analysis: analysis ?? {},
        unreviewedCount: unreviewedCount ?? 0,
        reimbursementOutstanding: reimbursementOutstanding ?? 0,
        history: [],
      });
      setDashboard({
        ...summary,
        monthlyIncome: analysis ? summary.monthlyIncome : null,
        monthlyExpense: analysis ? summary.monthlyExpense : null,
        unreviewedCount,
        reimbursementOutstanding,
      });
    };
    function loadMetric<T>(path: string, receive: (value: T) => void) {
      void api.get<T>(path, read).then((value) => {
        if (!isCurrent()) return;
        receive(value);
        publish();
      }).catch(() => {});
    }

    setLoading(true);
    setError(null);
    const allocationRequest = api.get<Allocation>("/api/allocation_accounts", read);
    loadMetric<OverviewAnalysis>("/api/monthly_analysis", (value) => { analysis = value; });
    loadMetric<{ total_count?: number }>("/api/transactions?reviewed_filter=unreviewed&page=1&limit=1",
      (value) => { unreviewedCount = Number(value.total_count ?? 0); });
    loadMetric<{ to_be_reimbursed?: number }>("/api/reimbursement_summary",
      (value) => { reimbursementOutstanding = Number(value.to_be_reimbursed ?? 0); });
    void api.get<{ history?: HistoryPoint[] }>("/api/allocation_history", read)
      .then(({ history: points }) => {
        if (isCurrent()) setHistory({ points: points || [], unavailable: false });
      })
      .catch(() => {
        if (isCurrent()) setHistory((current) => current ?? { points: [], unavailable: true });
      });
    void api.get<{ last_success_at?: string; last_sync_time?: string }>("/api/credentials_status", read)
      .then((status) => {
        if (isCurrent()) {
          const time = status.last_success_at || status.last_sync_time;
          setLastSync(time && time !== "N/A" ? `Last sync: ${time}` : "Not synced yet");
        }
      })
      .catch(() => {
        if (isCurrent()) setLastSync((current) => current ?? "Sync status unavailable");
      });
    try {
      allocation = await allocationRequest;
      if (!allocation) throw new Error("Current Net Worth is unavailable");
      publish();
    } catch (requestError) {
      if (isCurrent()) setError(errorMessage(requestError));
    } finally {
      if (isCurrent()) setLoading(false);
    }
  }, [api, session]);

  const syncPlaid = useCallback(async () => {
    if (syncingRef.current) return;
    const version = sessionVersion.current;
    syncingRef.current = true;
    setSyncing(true);
    setSyncMessage("");
    try {
      const result = await api.post<PlaidSyncResult>("/api/sync_transactions", undefined, { timeoutMs: 180_000 });
      if (version !== sessionVersion.current) return;
      setSyncMessage(plaidSyncMessage(result));
      if (result.status !== "failed") void loadDashboard();
    } catch (syncError) {
      if (version === sessionVersion.current) {
        setSyncMessage(syncError instanceof RequestTimeoutError ||
          (syncError instanceof TypeError && /network request failed|failed to fetch/i.test(syncError.message))
          ? "Sync status is unknown. The server may still be syncing. Check the last sync time before trying again."
          : errorMessage(syncError));
      }
    } finally {
      syncingRef.current = false;
      setSyncing(false);
    }
  }, [api, loadDashboard]);

  const unlock = useCallback(async () => {
    if (authenticationInFlight.current || AppState.currentState !== "active")
      return false;
    authenticationInFlight.current = true;
    try {
      const supported =
        (await LocalAuthentication.hasHardwareAsync()) &&
        (await LocalAuthentication.isEnrolledAsync());
      if (!supported) {
        await SecureStore.setItemAsync(APP_LOCK_KEY, "0");
        setAppLockEnabled(false);
        setLocked(false);
        return false;
      }
      const result = await LocalAuthentication.authenticateAsync({
        promptMessage: "Unlock MeowBillion",
        cancelLabel: "Cancel",
      });
      if (result.success) setLocked(false);
      return result.success;
    } catch {
      await SecureStore.setItemAsync(APP_LOCK_KEY, "0");
      setAppLockEnabled(false);
      setLocked(false);
      return false;
    } finally {
      authenticationInFlight.current = false;
    }
  }, []);
  const updateAppLock = useCallback(
    async (enabled: boolean) => {
      if (enabled && !(await unlock())) return false;
      await SecureStore.setItemAsync(APP_LOCK_KEY, enabled ? "1" : "0");
      setAppLockEnabled(enabled);
      setLocked(false);
      return true;
    },
    [unlock],
  );
  useEffect(() => {
    Promise.all([
      apiEndpointStore.load(),
      sessionStore.load(),
      SecureStore.getItemAsync(APP_LOCK_KEY),
    ]).then(([endpoint, storedSession, lockSetting]) => {
      setApiEndpoint(endpoint);
      setSession(storedSession);
      setAppLockEnabled(lockSetting === "1");
      setLocked(Boolean(storedSession && lockSetting === "1"));
      setBooting(false);
    });
  }, []);
  useEffect(() => {
    const subscription = AppState.addEventListener("change", (state) => {
      if (state === "background" && appLockEnabled && session) setLocked(true);
    });
    return () => subscription.remove();
  }, [appLockEnabled, session]);
  useEffect(() => {
    if (!locked || !session || AppState.currentState !== "active") return;
    const timer = setTimeout(() => void unlock(), 300);
    return () => clearTimeout(timer);
  }, [locked, session, unlock]);
  useEffect(() => {
    if (session) void loadDashboard();
  }, [session, loadDashboard]);
  if (booting)
    return (
      <SafeAreaProvider>
        <LoadingScreen label="Restoring session" />
      </SafeAreaProvider>
    );
  if (!session)
    return (
      <SafeAreaProvider>
        <LoginScreen
          apiEndpoint={apiEndpoint}
          onEndpointSaved={saveApiEndpoint}
          onSession={setSession}
        />
      </SafeAreaProvider>
    );

  return (
    <SafeAreaProvider>
      <SafeAreaView edges={["top", "left", "right"]} style={styles.safeArea}>
        <StatusBar style="dark" />
        {tab === "home" && !moreOpen ? (
          <HomeScreen
            api={api}
            dashboard={dashboard}
            error={error}
            history={history}
            lastSync={lastSync}
            loading={loading}
            onMore={() => setMoreOpen(true)}
            onRefresh={loadDashboard}
            onSync={syncPlaid}
            onTransactions={() => setTab("transactions")}
            syncing={syncing}
            syncMessage={syncMessage}
            displayName={session.user.displayName}
          />
        ) : null}
        {tab === "home" && moreOpen ? (
          <MoreScreen
            api={api}
            apiEndpoint={apiEndpoint}
            appLockEnabled={appLockEnabled}
            onClose={() => setMoreOpen(false)}
            onEndpointSaved={saveApiEndpoint}
            onSetAppLock={updateAppLock}
            onSignOut={signOut}
          />
        ) : null}
        {tab === "transactions" ? (
          <M3TransactionsScreen
            api={api}
            errorMessage={errorMessage}
            formatMoney={formatMoney}
          />
        ) : null}
        {tab === "spending" ? (
          <SpendingScreen
            api={api}
            errorMessage={errorMessage}
            formatMoney={formatMoney}
          />
        ) : null}
        {tab === "travel" ? (
          <TravelScreen
            api={api}
            errorMessage={errorMessage}
            formatMoney={formatMoney}
          />
        ) : null}
        {tab === "rentals" ? (
          <RentalsScreen
            api={api}
            errorMessage={errorMessage}
            formatMoney={formatMoney}
          />
        ) : null}
        {tab !== "home" &&
        tab !== "transactions" &&
        tab !== "spending" &&
        tab !== "travel" &&
        tab !== "rentals" ? (
          <PlaceholderScreen
            tab={tabs.find((item) => item.key === tab)?.label || ""}
            onBackHome={() => setTab("home")}
          />
        ) : null}
        <SafeAreaView edges={["bottom"]} style={styles.tabSafe}>
          <View style={styles.tabBarFlow}>
            {tabs.map((item) => {
              const Icon = item.icon;
              const active = tab === item.key && !moreOpen;
              return (
                <Pressable
                  key={item.key}
                  onPress={() => {
                    setMoreOpen(false);
                    setTab(item.key);
                  }}
                  style={styles.tabButton}
                >
                  <Icon
                    color={active ? "#0ABAB5" : "#8d96a7"}
                    size={22}
                    strokeWidth={active ? 2.5 : 2}
                  />
                  <Text style={[styles.tabLabel, active && styles.tabActive]}>
                    {item.label}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </SafeAreaView>
        {locked ? <AppLockScreen onUnlock={unlock} /> : null}
      </SafeAreaView>
    </SafeAreaProvider>
  );
}

function LoginScreen({
  apiEndpoint,
  onEndpointSaved,
  onSession,
}: {
  apiEndpoint: string;
  onEndpointSaved: (value: string) => Promise<string>;
  onSession: (session: MobileSession) => void;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [endpointInput, setEndpointInput] = useState(apiEndpoint);
  const [submitting, setSubmitting] = useState(false);
  const [testingConnection, setTestingConnection] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<{
    ok: boolean;
    message: string;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => setEndpointInput(apiEndpoint), [apiEndpoint]);
  async function submit() {
    setSubmitting(true);
    setError(null);
    try {
      const endpoint = await onEndpointSaved(endpointInput);
      const nextSession = await loginMobile(endpoint, email, password);
      await sessionStore.save(nextSession);
      onSession(nextSession);
    } catch (loginError) {
      setError(errorMessage(loginError));
    } finally {
      setSubmitting(false);
    }
  }
  async function testConnection() {
    setTestingConnection(true);
    setConnectionStatus(null);
    try {
      setConnectionStatus(
        await checkBackendConnection(normalizeApiEndpoint(endpointInput)),
      );
    } catch (connectionError) {
      setConnectionStatus({
        ok: false,
        message: errorMessage(connectionError),
      });
    } finally {
      setTestingConnection(false);
    }
  }
  return (
    <SafeAreaView style={styles.loginScreen}>
      <StatusBar style="dark" />
      <View style={styles.brandWrap}>
        <MeowBillionMark size={58} />
        <Text style={styles.loginTitle}>MeowBillion</Text>
        <Text style={styles.loginSubtitle}>
          Household finance, in one place.
        </Text>
      </View>
      <View style={styles.loginForm}>
        <Field label="Server address">
          <TextInput
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="url"
            onChangeText={setEndpointInput}
            placeholder={DEFAULT_API_ENDPOINT}
            style={styles.input}
            value={endpointInput}
          />
        </Field>
        <Pressable
          disabled={testingConnection || !endpointInput}
          onPress={testConnection}
          style={[
            styles.outlineButton,
            (testingConnection || !endpointInput) && styles.disabledButton,
          ]}
        >
          {testingConnection ? (
            <ActivityIndicator color="#0ABAB5" />
          ) : (
            <Text style={styles.outlineButtonText}>Test connection</Text>
          )}
        </Pressable>
        {connectionStatus ? (
          <Text
            style={
              connectionStatus.ok ? styles.connectionSuccess : styles.errorText
            }
          >
            {connectionStatus.message}
          </Text>
        ) : null}
        <Field label="Email">
          <TextInput
            autoCapitalize="none"
            autoComplete="email"
            keyboardType="email-address"
            onChangeText={setEmail}
            placeholder="name@example.com"
            style={styles.input}
            value={email}
          />
        </Field>
        <Field label="Password">
          <TextInput
            autoComplete="password"
            onChangeText={setPassword}
            placeholder="Enter your password"
            secureTextEntry
            style={styles.input}
            value={password}
          />
        </Field>
        {error ? <Text style={styles.errorText}>{error}</Text> : null}
        <Pressable
          disabled={submitting || !email || !password}
          onPress={submit}
          style={[
            styles.primaryButton,
            (!email || !password || submitting) && styles.disabledButton,
          ]}
        >
          {submitting ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.primaryButtonText}>Sign in</Text>
          )}
        </Pressable>
        <Text style={styles.apiHint}>
          Use your household server IP address or private HTTPS address.
        </Text>
      </View>
    </SafeAreaView>
  );
}

function MoreScreen({
  api,
  apiEndpoint,
  appLockEnabled,
  onClose,
  onEndpointSaved,
  onSetAppLock,
  onSignOut,
}: {
  api: ApiClient;
  apiEndpoint: string;
  appLockEnabled: boolean;
  onClose: () => void;
  onEndpointSaved: (value: string) => Promise<string>;
  onSetAppLock(enabled: boolean): Promise<boolean>;
  onSignOut: () => Promise<void>;
}) {
  const [endpointInput, setEndpointInput] = useState(apiEndpoint);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [securityOpen, setSecurityOpen] = useState(false);
  async function save() {
    setSaving(true);
    setError(null);
    try {
      await onEndpointSaved(endpointInput);
    } catch (saveError) {
      setError(errorMessage(saveError));
    } finally {
      setSaving(false);
    }
  }
  if (securityOpen)
    return <SecurityScreen api={api} onBack={() => setSecurityOpen(false)} />;
  return (
    <ScrollView contentContainerStyle={styles.settingsScreen}>
      <View style={styles.settingsTop}>
        <Text style={styles.settingsTitle}>More</Text>
        <Pressable
          accessibilityLabel="Back to Home"
          onPress={onClose}
          style={styles.settingsClose}
        >
          <ArrowLeft color="#066F6C" size={22} />
        </Pressable>
      </View>
      <Pressable
        onPress={() => void onSetAppLock(!appLockEnabled)}
        style={styles.settingRow}
      >
        <View>
          <Text style={styles.appInfoTitle}>App Lock</Text>
          <Text style={styles.settingsDescription}>
            {appLockEnabled ? "On" : "Off"}
          </Text>
        </View>
        <Text style={styles.appInfoValue}>
          {appLockEnabled ? "Disable" : "Enable"}
        </Text>
      </Pressable>
      <Pressable
        onPress={() => setSecurityOpen(true)}
        style={styles.settingRow}
      >
        <View>
          <Text style={styles.appInfoTitle}>Security</Text>
          <Text style={styles.settingsDescription}>
            Manage signed-in devices
          </Text>
        </View>
        <Text style={styles.appInfoValue}>Open</Text>
      </Pressable>
      <Text style={styles.settingsDescription}>
        Changing the server address signs you out before using the new address.
      </Text>
      <Field label="Server address">
        <TextInput
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
          onChangeText={setEndpointInput}
          placeholder={DEFAULT_API_ENDPOINT}
          style={styles.input}
          value={endpointInput}
        />
      </Field>
      {error ? <Text style={styles.errorText}>{error}</Text> : null}
      <Pressable
        disabled={saving || endpointInput === apiEndpoint}
        onPress={save}
        style={[
          styles.primaryButton,
          (saving || endpointInput === apiEndpoint) && styles.disabledButton,
        ]}
      >
        {saving ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.primaryButtonText}>Save and sign in again</Text>
        )}
      </Pressable>
      <Pressable onPress={onSignOut} style={styles.dangerButton}>
        <Text style={styles.dangerButtonText}>Sign out</Text>
      </Pressable>
      <View style={styles.appInfo}>
        <Text style={styles.appInfoTitle}>App</Text>
        <View style={styles.appInfoRow}>
          <Text style={styles.appInfoLabel}>Version</Text>
          <Text style={styles.appInfoValue}>{APP_VERSION}</Text>
        </View>
      </View>
    </ScrollView>
  );
}

function SecurityScreen({ api, onBack }: { api: ApiClient; onBack(): void }) {
  const [sessions, setSessions] = useState<
    Array<{
      id: string;
      device_name: string;
      last_used_at: string;
      created_at: string;
    }>
  >([]);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try {
      setSessions(
        (
          await api.get<{
            sessions: Array<{
              id: string;
              device_name: string;
              last_used_at: string;
              created_at: string;
            }>;
          }>("/api/auth/mobile/sessions")
        ).sessions,
      );
      setError("");
    } catch (e) {
      setError(errorMessage(e));
    }
  }, [api]);
  useEffect(() => {
    void load();
  }, [load]);
  return (
    <ScrollView contentContainerStyle={styles.settingsScreen}>
      <View style={styles.settingsTop}>
        <Text style={styles.settingsTitle}>Security</Text>
        <Pressable onPress={onBack} style={styles.settingsClose}>
          <ArrowLeft color="#066F6C" size={22} />
        </Pressable>
      </View>
      {error ? <Text style={styles.errorText}>{error}</Text> : null}
      <Pressable
        onPress={async () => {
          await api.post("/api/auth/mobile/sessions/revoke_others");
          await load();
        }}
        style={styles.outlineButton}
      >
        <Text style={styles.outlineButtonText}>Sign out other devices</Text>
      </Pressable>
      {sessions.map((item) => (
        <View key={item.id} style={styles.settingRow}>
          <View style={{ flex: 1 }}>
            <Text style={styles.appInfoTitle}>{item.device_name}</Text>
            <Text style={styles.settingsDescription}>
              Last used: {item.last_used_at}
            </Text>
          </View>
          <Pressable
            onPress={async () => {
              await api.delete(`/api/auth/mobile/sessions/${item.id}`);
              await load();
            }}
          >
            <Text style={styles.dangerButtonText}>Revoke</Text>
          </Pressable>
        </View>
      ))}
    </ScrollView>
  );
}
function AppLockScreen({ onUnlock }: { onUnlock(): Promise<boolean> }) {
  return (
    <Pressable onPress={() => void onUnlock()} style={styles.lock}>
      <MeowBillionMark size={76} />
    </Pressable>
  );
}

function TransactionsScreen({ api }: { api: ApiClient }) {
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [reviewedFilter, setReviewedFilter] = useState("unreviewed");
  const [data, setData] = useState<{
    transactions: Transaction[];
    total_count: number;
    total_pages: number;
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [selected, setSelected] = useState<Transaction | null>(null);
  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(
        await api.get(
          buildTransactionQuery({ page, limit: 20, query, reviewedFilter }),
        ),
      );
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setLoading(false);
    }
  }, [api, page, query, reviewedFilter]);
  useEffect(() => {
    void load();
  }, [load]);
  async function confirm(transaction: Transaction) {
    setConfirming(transaction.TransactionID);
    try {
      await api.post(
        "/api/update_transaction",
        buildTransactionReviewPayload(transaction),
      );
      await load();
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setConfirming(null);
    }
  }
  function changeFilter(next: string) {
    setPage(1);
    setReviewedFilter(next);
  }
  return (
    <View style={styles.transactionsScreen}>
      <View style={styles.transactionsHeader}>
        <Text style={styles.transactionsTitle}>Transactions</Text>
        <Text style={styles.transactionsCount}>
          {data ? `${data.total_count} total` : ""}
        </Text>
      </View>
      <TextInput
        autoCapitalize="none"
        onChangeText={(value) => {
          setPage(1);
          setQuery(value);
        }}
        placeholder="Search transactions"
        style={styles.transactionSearch}
        value={query}
      />
      <View style={styles.filterRow}>
        {[
          ["unreviewed", "Needs review"],
          ["reviewed", "Reviewed"],
          ["all", "All"],
        ].map(([key, label]) => (
          <Pressable
            key={key}
            onPress={() => changeFilter(key)}
            style={[
              styles.filterButton,
              reviewedFilter === key && styles.filterButtonActive,
            ]}
          >
            <Text
              style={[
                styles.filterText,
                reviewedFilter === key && styles.filterTextActive,
              ]}
            >
              {label}
            </Text>
          </Pressable>
        ))}
      </View>
      {error ? (
        <View style={styles.errorCard}>
          <Text style={styles.errorText}>{error}</Text>
          <Pressable onPress={load}>
            <Text style={styles.retry}>Retry</Text>
          </Pressable>
        </View>
      ) : null}
      {loading && !data ? <LoadingScreen label="Loading transactions" /> : null}
      <ScrollView contentContainerStyle={styles.transactionsList}>
        {data?.transactions.length ? (
          data.transactions.map((transaction) => (
            <Pressable
              key={transaction.TransactionID}
              onPress={() => setSelected(transaction)}
              style={styles.transactionRow}
            >
              <View style={styles.transactionDetails}>
                <Text numberOfLines={1} style={styles.transactionMerchant}>
                  {transaction.Merchant || "Transaction"}
                </Text>
                <Text style={styles.transactionInfo}>
                  {transaction.Date} / {transaction.AccountName}
                </Text>
                <Text style={styles.transactionInfo}>
                  {transaction.Pending
                    ? "Pending"
                    : transaction.Type || "Uncategorized"}
                </Text>
              </View>
              <View style={styles.transactionActions}>
                <Text
                  style={[
                    styles.transactionAmount,
                    transaction.Direction === "inflow"
                      ? styles.green
                      : styles.rose,
                  ]}
                >
                  {transaction.Direction === "inflow" ? "+" : "-"}
                  {formatMoney(Math.abs(Number(transaction.Amount || 0)))}
                </Text>
                {reviewedFilter === "unreviewed" && !transaction.Pending ? (
                  <Pressable
                    disabled={confirming === transaction.TransactionID}
                    onPress={() => confirm(transaction)}
                    style={[
                      styles.confirmButton,
                      confirming === transaction.TransactionID &&
                        styles.disabledButton,
                    ]}
                  >
                    <Text style={styles.confirmButtonText}>
                      {confirming === transaction.TransactionID
                        ? "Saving"
                        : "Confirm"}
                    </Text>
                  </Pressable>
                ) : null}
              </View>
            </Pressable>
          ))
        ) : !loading ? (
          <Empty text="No transactions match these filters." />
        ) : null}
        <View style={styles.pagination}>
          <Pressable
            disabled={page <= 1 || loading}
            onPress={() => setPage((value) => value - 1)}
            style={[
              styles.paginationButton,
              (page <= 1 || loading) && styles.disabledButton,
            ]}
          >
            <Text style={styles.outlineButtonText}>Previous</Text>
          </Pressable>
          <Text style={styles.pageText}>
            Page {page} of {data?.total_pages || 1}
          </Text>
          <Pressable
            disabled={loading || page >= (data?.total_pages || 1)}
            onPress={() => setPage((value) => value + 1)}
            style={[
              styles.paginationButton,
              (loading || page >= (data?.total_pages || 1)) &&
                styles.disabledButton,
            ]}
          >
            <Text style={styles.outlineButtonText}>Next</Text>
          </Pressable>
        </View>
      </ScrollView>
      {selected ? (
        <TransactionEditor
          api={api}
          onClose={() => setSelected(null)}
          onSaved={async () => {
            setSelected(null);
            await load();
          }}
          transaction={selected}
        />
      ) : null}
    </View>
  );
}

function TransactionEditor({
  api,
  transaction,
  onClose,
  onSaved,
}: {
  api: ApiClient;
  transaction: Transaction;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [type, setType] = useState(transaction.Type || "Other");
  const [note, setNote] = useState(transaction.Note || "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function save() {
    setSaving(true);
    setError(null);
    try {
      await api.post("/api/update_transaction", {
        ...buildTransactionReviewPayload(transaction),
        type,
        note,
      });
      await onSaved();
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setSaving(false);
    }
  }
  async function unconfirm() {
    setSaving(true);
    setError(null);
    try {
      await api.post("/api/unconfirm_transaction", {
        transaction_id: transaction.TransactionID,
      });
      await onSaved();
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setSaving(false);
    }
  }
  return (
    <View style={styles.editor}>
      <View style={styles.editorHeader}>
        <Text style={styles.editorTitle}>
          {transaction.Merchant || "Transaction"}
        </Text>
        <Pressable onPress={onClose}>
          <Text style={styles.retry}>Close</Text>
        </Pressable>
      </View>
      <Text style={styles.transactionInfo}>
        {transaction.Date} / {transaction.AccountName}
      </Text>
      <Text style={styles.editorAmount}>
        {formatMoney(Math.abs(Number(transaction.Amount || 0)))}
      </Text>
      {transaction.Pending ? (
        <Text style={styles.pendingWarning}>
          Pending transactions cannot be changed until posted.
        </Text>
      ) : (
        <>
          <Field label="Category">
            <TextInput
              onChangeText={setType}
              style={styles.input}
              value={type}
            />
          </Field>
          <Field label="Note">
            <TextInput
              multiline
              onChangeText={setNote}
              style={[styles.input, styles.noteInput]}
              value={note}
            />
          </Field>
          {error ? <Text style={styles.errorText}>{error}</Text> : null}
          <Pressable
            disabled={saving}
            onPress={save}
            style={[styles.primaryButton, saving && styles.disabledButton]}
          >
            <Text style={styles.primaryButtonText}>
              {saving ? "Saving" : "Save and confirm"}
            </Text>
          </Pressable>
          {transaction.Reviewed ? (
            <Pressable
              disabled={saving}
              onPress={unconfirm}
              style={styles.outlineButton}
            >
              <Text style={styles.outlineButtonText}>Undo confirmation</Text>
            </Pressable>
          ) : null}
        </>
      )}
    </View>
  );
}

function HomeScreen({
  api,
  dashboard,
  error,
  history,
  lastSync,
  loading,
  onMore,
  onRefresh,
  onSync,
  onTransactions,
  displayName,
  syncing,
  syncMessage,
}: {
  api: ApiClient;
  dashboard: Dashboard | null;
  error: string | null;
  history: DashboardHistory | null;
  lastSync: string | null;
  loading: boolean;
  onMore: () => void;
  onRefresh: () => Promise<void>;
  onSync: () => Promise<void>;
  onTransactions: () => void;
  displayName: string;
  syncing: boolean;
  syncMessage: string;
}) {
  const [netWorthRange, setNetWorthRange] = useState<TrendRange>("1M");
  const [allocationRange, setAllocationRange] = useState<TrendRange>("1M");
  const [selectedBucket, setSelectedBucket] = useState<AssetBucket | "All">(
    "All",
  );
  const [selectedAccount, setSelectedAccount] = useState<Account | null>(null);
  const [driverSelection, setDriverSelection] = useState<NetWorthDriverSelection | null>(null);
  const driverCache = useRef(new Map<string, NetWorthDrivers>());
  useEffect(() => {
    driverCache.current.clear();
  }, [history, dashboard?.netWorth]);
  const openNetWorthDrivers = useCallback(async (point: HistoryPoint) => {
    const date = point.date;
    const netWorth = Number(point["Net Worth"] || 0);
    const cached = driverCache.current.get(date);
    if (cached) {
      setDriverSelection({ date, netWorth, loading: false, data: cached });
      return;
    }
    setDriverSelection({ date, netWorth, loading: true });
    try {
      const data = await api.get<NetWorthDrivers>(`/api/net_worth_drivers?date=${encodeURIComponent(date)}`);
      driverCache.current.set(date, data);
      setDriverSelection((current) => current?.date === date
        ? { date, netWorth, loading: false, data }
        : current);
    } catch (requestError) {
      setDriverSelection((current) => current?.date === date
        ? { date, netWorth, loading: false, error: errorMessage(requestError) }
        : current);
    }
  }, [api]);
  const allocationGroups = dashboard
    ? filterAllocationGroupsByBucket(dashboard.allocationGroups, selectedBucket)
    : [];
  return (
    <>
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={loading}
            onRefresh={onRefresh}
            tintColor="#0ABAB5"
          />
        }
      >
        <View style={styles.header}>
          <Text style={styles.greeting}>Billionaire, {displayName}</Text>
          <Pressable
            accessibilityLabel="More settings"
            onPress={onMore}
            style={styles.homeMore}
          >
            <Settings color="#066F6C" size={22} />
          </Pressable>
        </View>
        <View style={styles.syncCard}>
          <Pressable
            accessibilityRole="button"
            accessibilityState={{ busy: syncing, disabled: syncing }}
            disabled={syncing}
            onPress={() => Alert.alert("Sync Plaid?", "Fetch the latest balances and transactions for your linked accounts.", [
              { text: "Cancel", style: "cancel" },
              { text: "Sync now", onPress: onSync },
            ])}
            style={styles.settingRow}
          >
            <View>
              <Text style={styles.appInfoTitle}>{syncing ? "Syncing Plaid…" : "Sync Plaid"}</Text>
              {lastSync ? <Text style={styles.settingsDescription}>{lastSync}</Text> : null}
            </View>
            {syncing ? <ActivityIndicator color="#078F8B" /> : <RefreshCw color="#078F8B" size={20} />}
          </Pressable>
          {syncMessage ? <Text accessibilityLiveRegion="polite" style={styles.settingsDescription}>{syncMessage}</Text> : null}
        </View>
        {loading && !dashboard ? (
          <LoadingScreen label="Loading your overview" />
        ) : null}
        {error ? (
          <View style={styles.errorCard}>
            <Text style={styles.errorText}>{error}</Text>
            <Pressable onPress={onRefresh}>
              <Text style={styles.retry}>Retry</Text>
            </Pressable>
          </View>
        ) : null}
        {dashboard ? (
          <>
            <View style={styles.netWorth}>
              <View style={styles.kpiHeader}>
                <Text style={styles.netWorthLabel}>Net Worth</Text>
                <View style={[styles.kpiIcon, styles.netWorthIcon]}>
                  <Landmark color="#0ABAB5" size={20} />
                </View>
              </View>
              <Text style={styles.netWorthValue}>
                {formatMoney(dashboard.netWorth)}
              </Text>
            </View>
            <View style={styles.metricRow}>
              <Metric
                label="This Month Inflow"
                icon={<TrendingUp color="#159f72" size={18} />}
                value={dashboard.monthlyIncome}
                tone="green"
              />
              <Metric
                label="This Month Outflow"
                icon={<TrendingDown color="#dc607a" size={18} />}
                value={dashboard.monthlyExpense}
                tone="rose"
              />
            </View>
            <View style={styles.metricRow}>
              <Metric
                label="To Be Reimbursed"
                icon={<HandCoins color="#c58a28" size={18} />}
                value={dashboard.reimbursementOutstanding}
                tone="amber"
              />
            </View>
            <Pressable onPress={onTransactions} style={styles.pendingEntry}>
              <View>
                <Text style={styles.pendingTitle}>Pending transactions</Text>
                <Text style={styles.pendingHint}>
                  Review them in Transactions
                </Text>
              </View>
              <Text style={styles.pendingCount}>
                {dashboard.unreviewedCount ?? "—"}
              </Text>
            </Pressable>
            <ChartCard
              title="Net Worth Trend"
              control={
                <RangeControl
                  active={netWorthRange}
                  onChange={setNetWorthRange}
                />
              }
            >
              {!history ? <ActivityIndicator color="#078F8B" /> : history.unavailable ? (
                <PanelUnavailable />
              ) : (
                <TrendChart
                  formatMoney={formatMoney}
                  history={filterHistoryByRange(
                    history.points,
                    netWorthRange,
                  )}
                  range={netWorthRange}
                  series={["Net Worth"]}
                  onPointPress={openNetWorthDrivers}
                />
              )}
            </ChartCard>
            <ChartCard
              title="Allocation Trend"
              control={
                <RangeControl
                  active={allocationRange}
                  onChange={setAllocationRange}
                />
              }
            >
              {!history ? <ActivityIndicator color="#078F8B" /> : history.unavailable ? (
                <PanelUnavailable />
              ) : (
                <TrendChart
                  formatMoney={formatMoney}
                  history={filterHistoryByRange(
                    history.points,
                    allocationRange,
                  )}
                  range={allocationRange}
                  series={["Cash", "Stock", "Bond", "Real Estate"]}
                />
              )}
            </ChartCard>
            <ChartCard title="Portfolio Allocation">
              <AllocationDonut
                formatMoney={formatMoney}
                onSelect={setSelectedBucket}
                rows={dashboard.portfolio}
                selectedKey={selectedBucket}
              />
            </ChartCard>
            <Text style={styles.sectionTitle}>
              Accounts{selectedBucket === "All" ? "" : `: ${selectedBucket}`}
            </Text>
            {allocationGroups.length ? (
              allocationGroups.map((group) => (
                <View key={group.institution} style={styles.institution}>
                  <View style={styles.institutionHeader}>
                    <Text style={styles.institutionName}>
                      {group.institution}
                    </Text>
                    <Text style={styles.institutionTotal}>
                      {formatMoney(group.total)}
                    </Text>
                  </View>
                  {group.accounts.map((account) => (
                    <Pressable
                      key={account.account_id}
                      onPress={() => setSelectedAccount(account as Account)}
                      style={styles.account}
                    >
                      <View style={styles.accountInfo}>
                        <Text style={styles.accountName}>{account.name}</Text>
                        <Text style={styles.accountMeta}>
                          {sourceLabel(account.source)} /{" "}
                          {account.type || "Account"}
                        </Text>
                      </View>
                      <Text style={styles.accountAmount}>
                        {formatMoney(
                          selectedBucket === "All"
                            ? Number(account.balance_current || 0)
                            : Number(account.categories?.[selectedBucket] || 0),
                        )}
                      </Text>
                    </Pressable>
                  ))}
                </View>
              ))
            ) : (
              <Empty text="No accounts match this allocation." />
            )}
          </>
        ) : null}
      </ScrollView>
      {selectedAccount ? (
        <AccountDetailSheet
          key={selectedAccount.account_id}
          account={selectedAccount}
          api={api}
          errorMessage={errorMessage}
          formatMoney={formatMoney}
          onClose={() => setSelectedAccount(null)}
        />
      ) : null}
      <NetWorthDriversSheet
        formatMoney={formatMoney}
        onClose={() => setDriverSelection(null)}
        selection={driverSelection}
      />
    </>
  );
}

function ChartCard({
  title,
  control,
  children,
}: {
  title: string;
  control?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <View style={styles.chartCard}>
      <View style={styles.chartHeader}>
        <Text style={styles.chartTitle}>{title}</Text>
        {control}
      </View>
      {children}
    </View>
  );
}
function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <View>
      <Text style={styles.fieldLabel}>{label}</Text>
      {children}
    </View>
  );
}
function Metric({
  label,
  icon,
  value,
  tone,
}: {
  label: string;
  icon: React.ReactNode;
  value: number | null;
  tone: "green" | "rose" | "amber";
}) {
  return (
    <View
      style={[
        styles.metric,
        tone === "green"
          ? styles.inflowMetric
          : tone === "amber"
            ? styles.reimbursementMetric
            : styles.outflowMetric,
      ]}
    >
      <View style={styles.metricHeader}>
        <Text style={styles.metricLabel}>{label}</Text>
        <View
          style={[
            styles.kpiIcon,
            tone === "green"
              ? styles.inflowIcon
              : tone === "amber"
                ? styles.reimbursementIcon
                : styles.outflowIcon,
          ]}
        >
          {icon}
        </View>
      </View>
      <Text
        style={[
          styles.metricValue,
          tone === "green"
            ? styles.green
            : tone === "amber"
              ? styles.amber
              : styles.rose,
        ]}
      >
        {value === null ? "—" : formatMoney(value)}
      </Text>
    </View>
  );
}
function Empty({ text }: { text: string }) {
  return (
    <View style={styles.empty}>
      <Text style={styles.emptyText}>{text}</Text>
    </View>
  );
}
function PanelUnavailable() {
  return (
    <View style={styles.panelUnavailable}>
      <Text style={styles.emptyText}>
        This chart is temporarily unavailable.
      </Text>
    </View>
  );
}
function LoadingScreen({ label }: { label: string }) {
  return (
    <View style={styles.loading}>
      <ActivityIndicator color="#0ABAB5" />
      <Text style={styles.loadingText}>{label}</Text>
    </View>
  );
}
function PlaceholderScreen({
  tab,
  onBackHome,
}: {
  tab: string;
  onBackHome: () => void;
}) {
  return (
    <View style={styles.placeholder}>
      <Text style={styles.placeholderTitle}>{tab}</Text>
      <Text style={styles.placeholderText}>
        This section will be connected in a later milestone.
      </Text>
      <Pressable onPress={onBackHome} style={styles.outlineButton}>
        <Text style={styles.outlineButtonText}>Back to Home</Text>
      </Pressable>
    </View>
  );
}
function sourceLabel(source?: string) {
  return (
    (
      {
        holdings: "Holdings",
        manual_override: "Manual",
        cash_default: "Cash default",
        needs_allocation: "Needs allocation",
        manual_asset: "Manual asset",
      } as Record<string, string>
    )[source || ""] || "Auto"
  );
}

const styles = StyleSheet.create({
  syncCard: { marginBottom: 12 },
  tabSafe: {
    backgroundColor: "#fff",
    bottom: 0,
    left: 0,
    position: "absolute",
    right: 0,
  },
  tabBarFlow: {
    alignItems: "flex-start",
    backgroundColor: "#fff",
    borderColor: "#e6eaf2",
    borderTopWidth: 1,
    flexDirection: "row",
    height: 74,
    paddingBottom: 8,
    paddingTop: 8,
  },
  appInfo: {
    borderTopColor: "#dfe4ed",
    borderTopWidth: 1,
    marginTop: 32,
    paddingTop: 18,
  },
  appInfoTitle: { color: "#263047", fontSize: 14, fontWeight: "700" },
  appInfoRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 12,
  },
  appInfoLabel: { color: "#7a8499", fontSize: 12 },
  appInfoValue: { color: "#263047", fontSize: 12, fontWeight: "600" },
  settingRow: {
    alignItems: "flex-start",
    borderBottomColor: "#dfe4ed",
    borderBottomWidth: 1,
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 16,
  },
  lock: {
    alignItems: "center",
    backgroundColor: "#f4f6fb",
    bottom: 0,
    justifyContent: "center",
    left: 0,
    padding: 28,
    position: "absolute",
    right: 0,
    top: 0,
  },
  lockTitle: {
    color: "#182033",
    fontSize: 22,
    fontWeight: "700",
    marginTop: 20,
  },
  editor: {
    backgroundColor: "#fff",
    borderColor: "#d9dfeb",
    borderRadius: 8,
    borderWidth: 1,
    bottom: 82,
    left: 12,
    padding: 16,
    position: "absolute",
    right: 12,
  },
  editorHeader: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  editorTitle: { color: "#182033", flex: 1, fontSize: 16, fontWeight: "700" },
  editorAmount: {
    color: "#263047",
    fontSize: 18,
    fontWeight: "700",
    marginTop: 8,
  },
  noteInput: { height: 78, paddingTop: 10, textAlignVertical: "top" },
  pendingWarning: {
    color: "#a83f58",
    fontSize: 13,
    lineHeight: 18,
    marginTop: 16,
  },
  transactionsScreen: { flex: 1, padding: 20, paddingBottom: 75 },
  transactionsHeader: {
    alignItems: "baseline",
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 20,
  },
  transactionsTitle: { color: "#182033", fontSize: 24, fontWeight: "700" },
  transactionsCount: { color: "#7a8499", fontSize: 12 },
  transactionSearch: {
    backgroundColor: "#fff",
    borderColor: "#e1e6ef",
    borderRadius: 8,
    borderWidth: 1,
    color: "#182033",
    height: 44,
    marginTop: 16,
    paddingHorizontal: 12,
  },
  filterRow: { flexDirection: "row", gap: 7, marginTop: 10 },
  filterButton: {
    borderColor: "#d9dfeb",
    borderRadius: 6,
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 7,
  },
  filterButtonActive: { backgroundColor: "#E8F9F8", borderColor: "#0ABAB5" },
  filterText: { color: "#657087", fontSize: 11, fontWeight: "600" },
  filterTextActive: { color: "#066F6C" },
  transactionsList: { paddingBottom: 30, paddingTop: 12 },
  transactionRow: {
    alignItems: "center",
    backgroundColor: "#fff",
    borderColor: "#e6eaf2",
    borderRadius: 8,
    borderWidth: 1,
    flexDirection: "row",
    marginBottom: 8,
    padding: 12,
  },
  transactionDetails: { flex: 1, minWidth: 0 },
  transactionMerchant: { color: "#263047", fontSize: 14, fontWeight: "700" },
  transactionInfo: { color: "#8992a4", fontSize: 11, marginTop: 3 },
  transactionActions: { alignItems: "flex-end", marginLeft: 8 },
  transactionAmount: { fontSize: 12, fontWeight: "700" },
  confirmButton: {
    backgroundColor: "#0ABAB5",
    borderRadius: 5,
    marginTop: 8,
    paddingHorizontal: 9,
    paddingVertical: 5,
  },
  confirmButtonText: { color: "#fff", fontSize: 11, fontWeight: "700" },
  pagination: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 8,
  },
  paginationButton: {
    borderColor: "#0ABAB5",
    borderRadius: 6,
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 8,
  },
  pageText: { color: "#657087", fontSize: 11 },
  safeArea: { flex: 1, backgroundColor: "#f4f6fb" },
  content: { padding: 20, paddingBottom: 116 },
  loginScreen: {
    flex: 1,
    backgroundColor: "#f4f6fb",
    justifyContent: "center",
    padding: 28,
  },
  brandWrap: { alignItems: "center" },
  loginTitle: {
    color: "#182033",
    fontSize: 30,
    fontWeight: "700",
    marginTop: 14,
  },
  loginSubtitle: { color: "#7a8499", fontSize: 14, marginTop: 8 },
  loginForm: { marginTop: 36 },
  fieldLabel: {
    color: "#4c566b",
    fontSize: 13,
    fontWeight: "600",
    marginBottom: 7,
    marginTop: 14,
  },
  input: {
    backgroundColor: "#fff",
    borderColor: "#e1e6ef",
    borderRadius: 8,
    borderWidth: 1,
    color: "#182033",
    fontSize: 16,
    height: 48,
    paddingHorizontal: 13,
  },
  primaryButton: {
    alignItems: "center",
    backgroundColor: "#0ABAB5",
    borderRadius: 8,
    height: 48,
    justifyContent: "center",
    marginTop: 26,
  },
  outlineButton: {
    alignItems: "center",
    borderColor: "#0ABAB5",
    borderRadius: 8,
    borderWidth: 1,
    height: 42,
    justifyContent: "center",
    marginTop: 8,
  },
  dangerButton: {
    alignItems: "center",
    borderColor: "#dc607a",
    borderRadius: 8,
    borderWidth: 1,
    height: 44,
    justifyContent: "center",
    marginTop: 26,
  },
  primaryButtonText: { color: "#fff", fontSize: 15, fontWeight: "700" },
  outlineButtonText: { color: "#0ABAB5", fontSize: 13, fontWeight: "700" },
  dangerButtonText: { color: "#b73e59", fontSize: 14, fontWeight: "700" },
  disabledButton: { opacity: 0.45 },
  apiHint: {
    color: "#919aad",
    fontSize: 11,
    marginTop: 16,
    textAlign: "left",
  },
  connectionSuccess: { color: "#16815e", fontSize: 12, marginTop: 8 },
  settingsScreen: {
    backgroundColor: "#f4f6fb",
    flexGrow: 1,
    padding: 24,
    paddingBottom: 100,
    paddingTop: 40,
  },
  settingsTop: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  settingsTitle: { color: "#182033", fontSize: 24, fontWeight: "700" },
  settingsClose: {
    alignItems: "center",
    borderColor: "#d9dfeb",
    borderRadius: 7,
    borderWidth: 1,
    height: 44,
    justifyContent: "center",
    width: 44,
  },
  settingsDescription: {
    color: "#7a8499",
    fontSize: 13,
    lineHeight: 19,
    marginTop: 8,
  },
  header: {
    alignItems: "flex-start",
    justifyContent: "center",
    marginBottom: 22,
    paddingTop: 26,
    position: "relative",
  },
  homeMore: {
    alignItems: "center",
    borderColor: "#d9dfeb",
    borderRadius: 7,
    borderWidth: 1,
    height: 44,
    justifyContent: "center",
    position: "absolute",
    right: 0,
    top: 16,
    width: 44,
  },
  greeting: {
    color: "#182033",
    fontSize: 24,
    fontWeight: "700",
    textAlign: "left",
  },
  netWorth: {
    backgroundColor: "#fff",
    borderColor: "#e6eaf2",
    borderLeftColor: "#0ABAB5",
    borderLeftWidth: 4,
    borderRadius: 8,
    borderWidth: 1,
    padding: 18,
  },
  kpiHeader: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  kpiIcon: {
    alignItems: "center",
    borderRadius: 7,
    height: 32,
    justifyContent: "center",
    width: 32,
  },
  netWorthIcon: { backgroundColor: "#E8F9F8" },
  inflowIcon: { backgroundColor: "#e8f8f2" },
  outflowIcon: { backgroundColor: "#fff0f3" },
  reimbursementIcon: { backgroundColor: "#fff6e8" },
  netWorthLabel: { color: "#687893", fontSize: 13, fontWeight: "600" },
  netWorthValue: {
    color: "#182033",
    fontSize: 28,
    fontWeight: "700",
    marginTop: 6,
  },
  sectionTitle: {
    color: "#182033",
    fontSize: 16,
    fontWeight: "700",
    marginBottom: 10,
    marginTop: 24,
  },
  metricRow: { flexDirection: "row", gap: 10, marginTop: 12 },
  metric: {
    backgroundColor: "#fff",
    borderColor: "#e6eaf2",
    borderRadius: 8,
    borderLeftWidth: 4,
    borderWidth: 1,
    flex: 1,
    padding: 14,
  },
  inflowMetric: { borderLeftColor: "#10b981" },
  outflowMetric: { borderLeftColor: "#f43f5e" },
  reimbursementMetric: { borderLeftColor: "#c58a28" },
  metricLabel: { color: "#687893", flex: 1, fontSize: 12, fontWeight: "600" },
  metricHeader: { alignItems: "center", flexDirection: "row", gap: 5 },
  metricValue: { fontSize: 18, fontWeight: "700", marginTop: 8 },
  green: { color: "#159f72" },
  rose: { color: "#dc607a" },
  amber: { color: "#a86f13" },
  pendingEntry: {
    alignItems: "center",
    backgroundColor: "#fff",
    borderColor: "#e6eaf2",
    borderRadius: 8,
    borderWidth: 1,
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 18,
    padding: 15,
  },
  pendingTitle: { color: "#182033", fontSize: 15, fontWeight: "700" },
  pendingHint: { color: "#8992a4", fontSize: 11, marginTop: 3 },
  pendingCount: { color: "#0ABAB5", fontSize: 25, fontWeight: "700" },
  chartCard: {
    backgroundColor: "#fff",
    borderColor: "#e6eaf2",
    borderRadius: 8,
    borderWidth: 1,
    marginTop: 18,
    padding: 14,
  },
  chartHeader: {
    alignItems: "flex-start",
    flexDirection: "row",
    gap: 8,
    justifyContent: "space-between",
    marginBottom: 12,
  },
  chartTitle: {
    color: "#182033",
    flexShrink: 1,
    fontSize: 15,
    fontWeight: "700",
    paddingTop: 5,
  },
  institution: {
    backgroundColor: "#fff",
    borderColor: "#e6eaf2",
    borderRadius: 8,
    borderWidth: 1,
    marginBottom: 10,
  },
  institutionHeader: {
    alignItems: "center",
    borderBottomColor: "#edf0f5",
    borderBottomWidth: 1,
    flexDirection: "row",
    justifyContent: "space-between",
    padding: 12,
  },
  institutionName: { color: "#263047", fontSize: 13, fontWeight: "700" },
  institutionTotal: { color: "#263047", fontSize: 12, fontWeight: "700" },
  account: { alignItems: "center", flexDirection: "row", padding: 12 },
  accountInfo: { flex: 1 },
  accountName: { color: "#263047", fontSize: 13, fontWeight: "600" },
  accountMeta: { color: "#8992a4", fontSize: 11, marginTop: 3 },
  accountAmount: { color: "#263047", fontSize: 12, fontWeight: "700" },
  empty: {
    alignItems: "center",
    backgroundColor: "#fff",
    borderColor: "#e6eaf2",
    borderRadius: 8,
    borderWidth: 1,
    padding: 18,
  },
  panelUnavailable: {
    alignItems: "center",
    justifyContent: "center",
    minHeight: 146,
  },
  emptyText: { color: "#8992a4", fontSize: 12 },
  errorCard: {
    alignItems: "center",
    backgroundColor: "#fff2f4",
    borderColor: "#f2c8d1",
    borderRadius: 8,
    borderWidth: 1,
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: 14,
    padding: 12,
  },
  errorText: { color: "#a83f58", flex: 1, fontSize: 12, marginTop: 8 },
  retry: { color: "#0ABAB5", fontSize: 12, fontWeight: "700", marginLeft: 12 },
  loading: {
    alignItems: "center",
    gap: 10,
    justifyContent: "center",
    minHeight: 150,
  },
  loadingText: { color: "#7a8499", fontSize: 13 },
  tabBar: {
    alignItems: "center",
    backgroundColor: "#fff",
    borderColor: "#e6eaf2",
    borderTopWidth: 1,
    bottom: 0,
    flexDirection: "row",
    height: 74,
    left: 0,
    paddingBottom: 8,
    paddingTop: 8,
    position: "absolute",
    right: 0,
  },
  tabButton: {
    alignItems: "center",
    flex: 1,
    gap: 4,
    minHeight: 54,
    justifyContent: "center",
  },
  tabLabel: { color: "#8d96a7", fontSize: 10, fontWeight: "600" },
  tabActive: { color: "#0ABAB5" },
  placeholder: {
    alignItems: "center",
    flex: 1,
    justifyContent: "center",
    padding: 30,
  },
  placeholderTitle: { color: "#182033", fontSize: 25, fontWeight: "700" },
  placeholderText: {
    color: "#7a8499",
    fontSize: 14,
    lineHeight: 21,
    marginTop: 10,
    textAlign: "center",
  },
});

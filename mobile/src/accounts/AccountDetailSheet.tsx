import { useEffect, useState } from 'react';
import { ActivityIndicator, Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import { X } from 'lucide-react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { RangeControl, TrendChart } from '../components/DashboardCharts';
import { TrendRange } from '../dashboard/model';

type Api = { get<T>(path: string, options?: { retry?: boolean }): Promise<T> };
type Account = { account_id: string; name: string; institution_name?: string; balance_current?: number | null };
type Payload = { account: Account; history: Array<{ date: string; balance: number }> };
type HistoryResult = { range: TrendRange } & ({ data: Payload } | { error: string });

export function AccountDetailSheet({ account, api, formatMoney, errorMessage, onClose }: {
  account: Account;
  api: Api;
  formatMoney(value: number): string;
  errorMessage(error: unknown): string;
  onClose(): void;
}) {
  const [range, setRange] = useState<TrendRange>('1M');
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<HistoryResult>();
  const accountId = account.account_id;

  useEffect(() => {
    let active = true;
    const query = `account_id=${encodeURIComponent(accountId)}&range=${range}`;
    void api.get<Payload>(`/api/account_balance_history?${query}`, { retry: true })
      .then((data) => { if (active) setResult({ range, data }); })
      .catch((error) => { if (active) setResult({ range, error: errorMessage(error) }); });
    return () => { active = false; };
  }, [accountId, api, attempt, errorMessage, range]);

  const current = result?.range === range ? result : undefined;
  const data = current && 'data' in current ? current.data : undefined;
  const error = current && 'error' in current ? current.error : undefined;
  const history = data?.history.map((point) => ({ date: point.date, 'Net Worth': point.balance })) ?? [];
  const balance = data?.account.balance_current ?? account.balance_current;

  return (
    <Modal animationType="slide" onRequestClose={onClose} transparent visible>
      <View style={styles.scrim}>
        <SafeAreaView edges={['top', 'bottom']} style={styles.safe}>
          <View style={styles.sheet}>
            <View style={styles.header}>
              <View style={styles.account}>
                <Text numberOfLines={1} style={styles.title}>{account.name}</Text>
                <Text style={styles.muted}>{account.institution_name || 'Account'}</Text>
              </View>
              <Pressable accessibilityLabel="Close account history" accessibilityRole="button" onPress={onClose} style={styles.close}>
                <X color="#066F6C" size={22} />
              </Pressable>
            </View>
            <Text style={styles.balance}>{balance == null ? '—' : formatMoney(balance)}</Text>
            <View style={styles.ranges}>
              <RangeControl active={range} onChange={(next) => {
                if (next === range) return;
                setResult(undefined);
                setRange(next);
              }} />
            </View>
            {!current ? (
              <View style={styles.loading}>
                <ActivityIndicator color="#0ABAB5" />
                <Text style={styles.muted}>Loading account history…</Text>
              </View>
            ) : null}
            {error !== undefined ? (
              <Pressable accessibilityRole="button" onPress={() => {
                setResult(undefined);
                setAttempt((value) => value + 1);
              }} style={styles.error}>
                <Text style={styles.errorText}>{error} Tap to retry.</Text>
              </Pressable>
            ) : null}
            {data ? (
              <>
                {history.length > 1 ? <Text style={styles.muted}>Tap or drag the chart to see a past balance.</Text> : null}
                <TrendChart directTouch displayNames={{ 'Net Worth': 'Balance' }} formatMoney={formatMoney} history={history} range={range} series={['Net Worth']} />
              </>
            ) : null}
          </View>
        </SafeAreaView>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  scrim: { backgroundColor: 'rgba(20,25,35,.45)', flex: 1 },
  safe: { flex: 1, justifyContent: 'flex-end' },
  sheet: { backgroundColor: '#f7f8fb', borderTopLeftRadius: 14, borderTopRightRadius: 14, minHeight: '55%', padding: 18, paddingBottom: 34 },
  header: { alignItems: 'center', flexDirection: 'row', gap: 10, justifyContent: 'space-between' },
  account: { flex: 1 },
  title: { color: '#182033', fontSize: 20, fontWeight: '700' },
  muted: { color: '#687488', fontSize: 12, marginTop: 3 },
  close: { alignItems: 'center', borderColor: '#d9dfeb', borderRadius: 7, borderWidth: 1, height: 44, justifyContent: 'center', width: 44 },
  balance: { color: '#263047', fontSize: 28, fontWeight: '700', marginTop: 18 },
  ranges: { marginVertical: 16 },
  loading: { alignItems: 'center', gap: 8, justifyContent: 'center', minHeight: 180 },
  error: { backgroundColor: '#fff2f4', borderRadius: 7, padding: 10 },
  errorText: { color: '#a83f58', fontSize: 12 },
});

import { ActivityIndicator, Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import { TrendingDown, TrendingUp, X } from 'lucide-react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

export type NetWorthDriverItem = {
  account_id: string;
  name: string;
  institution_name?: string;
  contribution: number;
  newly_included?: boolean;
};

export type NetWorthDrivers = {
  date: string;
  previous_date: string;
  net_worth: number;
  net_worth_change: number;
  change_pct: number | null;
  coverage_pct: number;
  unattributed_change: number;
  top_up: NetWorthDriverItem[];
  top_down: NetWorthDriverItem[];
};

export type NetWorthDriverSelection = {
  date: string;
  netWorth: number;
  loading: boolean;
  data?: NetWorthDrivers;
  error?: string;
};

function signedMoney(value: number, formatMoney: (value: number) => string) {
  const amount = Number(value || 0);
  return `${amount > 0 ? '+' : amount < 0 ? '-' : ''}${formatMoney(Math.abs(amount))}`;
}

function DriverRows({ rows, direction, formatMoney }: {
  rows: NetWorthDriverItem[];
  direction: 'up' | 'down';
  formatMoney: (value: number) => string;
}) {
  if (!rows.length) return <Text style={styles.empty}>No {direction === 'up' ? 'positive' : 'negative'} movers</Text>;
  const Icon = direction === 'up' ? TrendingUp : TrendingDown;
  return (
    <View>
      {rows.map((row) => (
        <View key={row.account_id} style={styles.driverRow}>
          <Icon color={direction === 'up' ? '#4A9B78' : '#f43f5e'} size={16} />
          <View style={styles.driverIdentity}>
            <Text numberOfLines={1} style={styles.driverName}>{row.name}</Text>
            <Text numberOfLines={1} style={styles.driverMeta}>
              {[row.institution_name, row.newly_included ? 'Newly included' : ''].filter(Boolean).join(' | ')}
            </Text>
          </View>
          <Text style={[styles.driverAmount, direction === 'up' ? styles.up : styles.down]}>
            {signedMoney(row.contribution, formatMoney)}
          </Text>
        </View>
      ))}
    </View>
  );
}

export function NetWorthDriversSheet({ selection, formatMoney, onClose }: {
  selection: NetWorthDriverSelection | null;
  formatMoney: (value: number) => string;
  onClose: () => void;
}) {
  if (!selection) return null;
  const data = selection.data;
  return (
    <Modal animationType="slide" onRequestClose={onClose} transparent visible>
      <Pressable onPress={onClose} style={styles.scrim}>
        <SafeAreaView edges={['bottom']} style={styles.safeArea}>
          <Pressable onPress={(event) => event.stopPropagation()} style={styles.sheet}>
            <View style={styles.header}>
              <View>
                <Text style={styles.title}>Net Worth Drivers</Text>
                <Text style={styles.date}>{data?.date || selection.date}</Text>
              </View>
              <Pressable accessibilityLabel="Close Net Worth drivers" onPress={onClose} style={styles.closeButton}>
                <X color="#066F6C" size={21} />
              </Pressable>
            </View>

            <View style={styles.summaryRow}>
              <View>
                <Text style={styles.summaryLabel}>Net Worth</Text>
                <Text style={styles.summaryValue}>{formatMoney(data?.net_worth ?? selection.netWorth)}</Text>
              </View>
              {data ? (
                <View style={styles.summaryRight}>
                  <Text style={styles.summaryLabel}>Change since {data.previous_date}</Text>
                  <Text style={data.net_worth_change >= 0 ? styles.up : styles.down}>
                    {signedMoney(data.net_worth_change, formatMoney)}
                    {data.change_pct == null ? '' : ` (${data.change_pct >= 0 ? '+' : ''}${data.change_pct.toFixed(2)}%)`}
                  </Text>
                </View>
              ) : null}
            </View>

            {selection.loading ? (
              <View style={styles.loading}>
                <ActivityIndicator color="#0ABAB5" />
                <Text style={styles.muted}>Loading account drivers...</Text>
              </View>
            ) : null}
            {selection.error ? <Text style={styles.error}>{selection.error}</Text> : null}
            {data ? (
              <>
                <Text style={styles.sectionTitle}>Top moves up</Text>
                <DriverRows direction="up" formatMoney={formatMoney} rows={data.top_up || []} />
                <Text style={styles.sectionTitle}>Top moves down</Text>
                <DriverRows direction="down" formatMoney={formatMoney} rows={data.top_down || []} />
                <View style={styles.reconciliation}>
                  <Text style={styles.muted}>Explained {Number(data.coverage_pct || 0).toFixed(1)}%</Text>
                  <Text style={styles.muted}>Unattributed {signedMoney(data.unattributed_change, formatMoney)}</Text>
                </View>
              </>
            ) : null}
          </Pressable>
        </SafeAreaView>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  scrim: { backgroundColor: 'rgba(23, 38, 45, 0.38)', flex: 1, justifyContent: 'flex-end' },
  safeArea: { justifyContent: 'flex-end' },
  sheet: { backgroundColor: '#fff', borderTopLeftRadius: 12, borderTopRightRadius: 12, padding: 18, paddingBottom: 24 },
  header: { alignItems: 'center', flexDirection: 'row', justifyContent: 'space-between' },
  title: { color: '#17262d', fontSize: 18, fontWeight: '700' },
  date: { color: '#697a82', fontSize: 11, marginTop: 3 },
  closeButton: { alignItems: 'center', borderColor: '#dce5e7', borderRadius: 7, borderWidth: 1, height: 40, justifyContent: 'center', width: 40 },
  summaryRow: { alignItems: 'flex-end', borderBottomColor: '#dce5e7', borderBottomWidth: 1, flexDirection: 'row', justifyContent: 'space-between', marginTop: 16, paddingBottom: 12 },
  summaryRight: { alignItems: 'flex-end', flexShrink: 1, marginLeft: 12 },
  summaryLabel: { color: '#697a82', fontSize: 10 },
  summaryValue: { color: '#17262d', fontSize: 20, fontWeight: '700', marginTop: 2 },
  loading: { alignItems: 'center', gap: 8, minHeight: 120, justifyContent: 'center' },
  muted: { color: '#697a82', fontSize: 11 },
  error: { color: '#a83f58', fontSize: 12, paddingVertical: 24, textAlign: 'center' },
  sectionTitle: { color: '#52666f', fontSize: 10, fontWeight: '700', marginBottom: 5, marginTop: 14, textTransform: 'uppercase' },
  empty: { color: '#8992a4', fontSize: 11, paddingVertical: 7 },
  driverRow: { alignItems: 'center', flexDirection: 'row', minHeight: 38 },
  driverIdentity: { flex: 1, marginHorizontal: 8, minWidth: 0 },
  driverName: { color: '#17262d', fontSize: 12, fontWeight: '700' },
  driverMeta: { color: '#697a82', fontSize: 9, marginTop: 2 },
  driverAmount: { fontSize: 12, fontWeight: '700', fontVariant: ['tabular-nums'] },
  up: { color: '#4A9B78', fontWeight: '700' },
  down: { color: '#f43f5e', fontWeight: '700' },
  reconciliation: { borderTopColor: '#dce5e7', borderTopWidth: 1, flexDirection: 'row', justifyContent: 'space-between', marginTop: 12, paddingTop: 10 },
});

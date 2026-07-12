import { useCallback, useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { TrendChart } from '../components/DashboardCharts';
import { categoryMatrixRows, spendingHistory, yearlyCashFlow } from './model';

type Api = { get<T>(path: string): Promise<T> };
type Monthly = { month: string; income: number; expense: number; expense_ex_mortgage?: number; net_savings?: number; savings_rate?: number };
type Yearly = { year: string; income: number; expense: number; expense_ex_mortgage?: number; net_savings?: number; savings_rate?: number };
type MatrixRow = { month?: string; year?: string; categories: Record<string, number> };
type Analysis = {
  months: Monthly[];
  yearly: Yearly[];
  category_order: string[];
  category_matrix: MatrixRow[];
  yearly_category_order: string[];
  yearly_category_matrix: MatrixRow[];
};
type TableRow = { label: string; values: string[] };

const RANGE_VALUES = ['3M', '6M', '1Y', '5Y', 'ALL'] as const;
type SpendingRange = (typeof RANGE_VALUES)[number];

export function SpendingScreen({ api, formatMoney, errorMessage }: { api: Api; formatMoney(value: number): string; errorMessage(error: unknown): string }) {
  const [data, setData] = useState<Analysis>();
  const [range, setRange] = useState<SpendingRange>('1Y');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => { setLoading(true); setError(''); try { setData(await api.get<Analysis>('/api/monthly_analysis')); } catch (requestError) { setError(errorMessage(requestError)); } finally { setLoading(false); } }, [api, errorMessage]);
  useEffect(() => { void load(); }, [load]);
  const monthly = data?.months || [];
  const visible = useMemo(() => filterMonths(monthly, range), [monthly, range]);
  const monthlySummary = monthly.slice().reverse().map((row) => summaryRow(row.month, row, formatMoney));
  const yearlySummary = (data?.yearly || []).slice().reverse().map((row) => summaryRow(row.year, row, formatMoney));
  const monthlyCategories = categoryMatrixRows(data?.category_order || [], data?.category_matrix || []).slice().reverse();
  const yearlyCategories = categoryMatrixRows(data?.yearly_category_order || [], data?.yearly_category_matrix || []).slice().reverse();

  return <ScrollView contentContainerStyle={s.screen}>
    <View style={s.header}><Text style={s.title}>Spending</Text><Text style={s.muted}>Monthly and yearly cash flow</Text></View>
    {loading ? <ActivityIndicator color="#6268dc" style={s.loader} /> : null}
    {error ? <Pressable onPress={load} style={s.error}><Text style={s.errorText}>{error} Tap to retry.</Text></Pressable> : null}
    {data ? <>
      <Panel title="Monthly Cash Flow" control={<RangePicker range={range} onChange={setRange} />}>
        <TrendChart barSeries={['Income', 'Expense']} displayNames={{ Income: 'Income', Expense: 'Expense', Net: 'Net' }} formatMoney={formatMoney} history={spendingHistory(visible)} range={range} series={['Income', 'Expense', 'Net']} />
      </Panel>
      <Panel title="Monthly Summary"><SummaryTable rows={monthlySummary} /></Panel>
      <Panel title="Monthly Category Spending"><CategoryTable categories={data.category_order || []} rows={monthlyCategories} formatMoney={formatMoney} /></Panel>
      <Panel title="Yearly Cash Flow"><TrendChart barSeries={['Income', 'Expense']} displayNames={{ Income: 'Income', Expense: 'Expense', Net: 'Net' }} formatMoney={formatMoney} history={yearlyCashFlow(data.yearly || [])} range="ALL" series={['Income', 'Expense', 'Net']} /></Panel>
      <Panel title="Yearly Summary"><SummaryTable rows={yearlySummary} /></Panel>
      <Panel title="Yearly Category Spending"><CategoryTable categories={data.yearly_category_order || []} rows={yearlyCategories} formatMoney={formatMoney} /></Panel>
    </> : null}
  </ScrollView>;
}

function filterMonths(rows: Monthly[], range: SpendingRange) {
  if (range === 'ALL') return rows;
  const length = { '3M': 3, '6M': 6, '1Y': 12, '5Y': 60 }[range];
  return rows.slice(-length);
}

function summaryRow(label: string, row: Omit<Monthly, 'month'> | Omit<Yearly, 'year'>, formatMoney: (value: number) => string): TableRow {
  const income = Number(row.income || 0); const expense = Number(row.expense || 0); const net = Number(row.net_savings ?? income - expense);
  return { label, values: [formatMoney(income), formatMoney(expense), formatMoney(Number(row.expense_ex_mortgage || 0)), formatMoney(net), formatPercent(Number(row.savings_rate ?? (income ? net / income : 0)))] };
}

function formatPercent(value: number) { return new Intl.NumberFormat('en-US', { style: 'percent', maximumFractionDigits: 1 }).format(value); }
function Panel({ title, control, children }: { title: string; control?: React.ReactNode; children: React.ReactNode }) { return <View style={s.panel}><View style={s.panelHeader}><Text style={s.panelTitle}>{title}</Text>{control}</View>{children}</View>; }
function RangePicker({ range, onChange }: { range: SpendingRange; onChange(value: SpendingRange): void }) { return <View style={s.rangeRow}>{RANGE_VALUES.map((value) => <Pressable key={value} onPress={() => onChange(value)} style={[s.range, range === value && s.rangeActive]}><Text style={[s.rangeText, range === value && s.rangeTextActive]}>{value === 'ALL' ? 'All' : value}</Text></Pressable>)}</View>; }
function SummaryTable({ rows }: { rows: TableRow[] }) { return <HorizontalTable columns={['Income', 'Expense', 'Expense excl. mortgage', 'Net', 'Savings rate']} rows={rows} />; }
function CategoryTable({ categories, rows, formatMoney }: { categories: string[]; rows: Array<{ label: string; values: number[] }>; formatMoney(value: number): string }) { return <HorizontalTable columns={categories} rows={rows.map((row) => ({ label: row.label, values: row.values.map((value) => value ? formatMoney(value) : '') }))} />; }
function HorizontalTable({ columns, rows }: { columns: string[]; rows: TableRow[] }) {
  if (!rows.length) return <Text style={s.empty}>No data is available.</Text>;
  return <ScrollView nestedScrollEnabled showsVerticalScrollIndicator style={s.tableViewport}><ScrollView horizontal showsHorizontalScrollIndicator><View><View style={[s.tableRow, s.tableHead]}><Cell value="Period" header />{columns.map((column) => <Cell header key={column} value={column} />)}</View>{rows.map((row) => <View key={row.label} style={s.tableRow}><Cell value={row.label} />{row.values.map((value, index) => <Cell key={`${row.label}-${columns[index]}`} value={value} />)}</View>)}</View></ScrollView></ScrollView>;
}
function Cell({ value, header = false }: { value: string; header?: boolean }) { return <Text numberOfLines={2} style={[s.cell, header && s.headerCell]}>{value}</Text>; }

const s = StyleSheet.create({ screen: { padding: 18, paddingBottom: 130 }, header: { marginTop: 8 }, title: { color: '#182033', fontSize: 23, fontWeight: '700' }, muted: { color: '#8992a4', fontSize: 11, marginTop: 3 }, loader: { marginTop: 70 }, error: { backgroundColor: '#fff2f4', borderRadius: 7, marginTop: 16, padding: 10 }, errorText: { color: '#a83f58', fontSize: 12 }, panel: { backgroundColor: '#fff', borderColor: '#e6eaf2', borderRadius: 8, borderWidth: 1, marginTop: 14, padding: 14 }, panelHeader: { alignItems: 'flex-start', flexDirection: 'row', gap: 8, justifyContent: 'space-between', marginBottom: 12 }, panelTitle: { color: '#182033', flex: 1, fontSize: 15, fontWeight: '700' }, rangeRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 4, justifyContent: 'flex-end' }, range: { borderColor: '#d9dfeb', borderRadius: 5, borderWidth: 1, paddingHorizontal: 7, paddingVertical: 5 }, rangeActive: { backgroundColor: '#eef0ff', borderColor: '#6268dc' }, rangeText: { color: '#657087', fontSize: 10, fontWeight: '700' }, rangeTextActive: { color: '#4d53b7' }, tableViewport: { maxHeight: 320 }, tableRow: { alignItems: 'stretch', borderBottomColor: '#edf0f5', borderBottomWidth: 1, flexDirection: 'row', minHeight: 46 }, tableHead: { backgroundColor: '#f6f7fb' }, cell: { color: '#263047', fontSize: 11, paddingHorizontal: 8, paddingVertical: 9, width: 118 }, headerCell: { color: '#657087', fontWeight: '700' }, empty: { color: '#8992a4', fontSize: 12, paddingVertical: 12 } });

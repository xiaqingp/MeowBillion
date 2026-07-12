export const ASSET_BUCKETS = ['Cash', 'Stock', 'Bond', 'Real Estate'] as const;
export type AssetBucket = (typeof ASSET_BUCKETS)[number];
export type TrendRange = '1M' | '3M' | '6M' | '1Y' | '5Y' | 'ALL';

type Account = {
  account_id: string;
  name: string;
  type: string;
  balance_current: number | null;
  is_virtual?: boolean;
};

export type AllocationAccount = {
  account_id: string;
  institution_name?: string;
  name: string;
  type?: string;
  subtype?: string;
  balance_current?: number | null;
  source?: string;
  categories?: Partial<Record<AssetBucket, number>>;
};

export type Allocation = {
  totals?: Partial<Record<AssetBucket, number>>;
  accounts?: AllocationAccount[];
};

type MonthlyAnalysis = {
  recent_months?: Array<{ month: string; income: number; expense: number }>;
};

export type HistoryPoint = { date: string; 'Net Worth': number } & Partial<Record<AssetBucket, number>>;

const RANGE_DAYS: Partial<Record<TrendRange, number>> = { '1M': 30, '3M': 90, '6M': 180, '1Y': 365, '5Y': 365 * 5 };

export function buildDashboard({
  accounts,
  allocation,
  analysis,
  unreviewedCount,
  history,
  historyUnavailable = false,
}: {
  accounts: Account[];
  allocation: Allocation;
  analysis: MonthlyAnalysis;
  unreviewedCount: number;
  history: HistoryPoint[];
  historyUnavailable?: boolean;
}) {
  const assetTotal = ASSET_BUCKETS.reduce((total, bucket) => total + Number(allocation.totals?.[bucket] || 0), 0);
  const liabilities = accounts
    .filter((account) => account.type === 'credit' && !account.is_virtual)
    .reduce((total, account) => total + Number(account.balance_current || 0), 0);
  const latestMonth = analysis.recent_months?.at(-1);

  return {
    netWorth: assetTotal - liabilities,
    monthlyIncome: latestMonth?.income || 0,
    monthlyExpense: latestMonth?.expense || 0,
    unreviewedCount,
    history,
    historyUnavailable,
    portfolio: buildPortfolioRows(allocation),
    allocationGroups: groupAllocationAccounts(allocation),
  };
}

export function filterHistoryByRange(history: HistoryPoint[], range: TrendRange) {
  if (range === 'ALL' || history.length === 0) return history;
  const latest = new Date(`${history.at(-1)?.date}T00:00:00`).getTime();
  const cutoff = latest - (RANGE_DAYS[range] || 0) * 24 * 60 * 60 * 1000;
  const visible = history.filter((point) => new Date(`${point.date}T00:00:00`).getTime() >= cutoff);
  const prior = [...history].reverse().find((point) => new Date(`${point.date}T00:00:00`).getTime() < cutoff);
  return prior && visible.length < 2 ? [prior, ...visible] : visible;
}

export function buildPortfolioRows(allocation: Allocation) {
  const total = ASSET_BUCKETS.reduce((sum, bucket) => sum + Number(allocation.totals?.[bucket] || 0), 0);
  return ASSET_BUCKETS.map((key) => {
    const value = Number(allocation.totals?.[key] || 0);
    return { key, value, percentage: total ? Math.round((value / total) * 1000) / 10 : 0 };
  });
}

export function groupAllocationAccounts(allocation: Allocation) {
  const byInstitution = new Map<string, AllocationAccount[]>();
  for (const account of allocation.accounts || []) {
    const institution = account.institution_name || 'Unknown';
    byInstitution.set(institution, [...(byInstitution.get(institution) || []), account]);
  }
  return [...byInstitution.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([institution, accounts]) => ({
      institution,
      total: accounts.reduce((sum, account) => sum + Number(account.balance_current || 0), 0),
      accounts,
    }));
}

export type AllocationGroup = ReturnType<typeof groupAllocationAccounts>[number];

export function filterAllocationGroupsByBucket(groups: AllocationGroup[], bucket: AssetBucket | 'All') {
  if (bucket === 'All') return groups;
  return groups.map((group) => {
    const accounts = group.accounts.filter((account) => Number(account.categories?.[bucket] || 0) !== 0);
    return { institution: group.institution, accounts, total: accounts.reduce((sum, account) => sum + Number(account.categories?.[bucket] || 0), 0) };
  }).filter((group) => group.accounts.length > 0);
}

export function nearestPointIndex(locationX: number, width: number, pointCount: number) {
  if (pointCount <= 1 || width <= 0) return 0;
  return Math.max(0, Math.min(pointCount - 1, Math.round((locationX / width) * (pointCount - 1))));
}

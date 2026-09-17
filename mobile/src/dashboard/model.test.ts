import assert from 'node:assert/strict';
import test from 'node:test';

import { buildDashboard, buildPortfolioRows, chartPointPositions, filterAllocationGroupsByBucket, filterHistoryByRange, groupAllocationAccounts, nearestPointIndex } from './model';

test('uses the backend net worth without recalculating it from frontend totals', () => {
  const dashboard = buildDashboard({
    allocation: { net_worth: 2250, totals: { Cash: 1, Stock: 2, Bond: 3, 'Real Estate': 4 } },
    analysis: {
      recent_months: [
        { month: '2026-06', income: 5000, expense: 2000 },
        { month: '2026-07', income: 6000, expense: 1800 },
      ],
    },
    unreviewedCount: 17,
    reimbursementOutstanding: 325,
    history: [],
    historyUnavailable: true,
  });

  assert.equal(dashboard.netWorth, 2250);
  assert.equal(dashboard.monthlyIncome, 6000);
  assert.equal(dashboard.monthlyExpense, 1800);
  assert.equal(dashboard.unreviewedCount, 17);
  assert.equal(dashboard.reimbursementOutstanding, 325);
  assert.equal(dashboard.historyUnavailable, true);
});

test('keeps the preceding history point when filtering a dashboard range', () => {
  const history = [
    { date: '2026-04-01', 'Net Worth': 100, Cash: 10, Stock: 90, Bond: 0, 'Real Estate': 0 },
    { date: '2026-06-01', 'Net Worth': 120, Cash: 20, Stock: 100, Bond: 0, 'Real Estate': 0 },
    { date: '2026-07-10', 'Net Worth': 140, Cash: 30, Stock: 110, Bond: 0, 'Real Estate': 0 },
  ];

  assert.deepEqual(
    filterHistoryByRange(history, '1M').map((point) => point.date),
    ['2026-06-01', '2026-07-10'],
  );
});

test('builds portfolio rows from the allocation endpoint totals', () => {
  assert.deepEqual(buildPortfolioRows({ totals: { Cash: 100, Stock: 300, Bond: 100, 'Real Estate': 500 } }), [
    { key: 'Cash', value: 100, percentage: 10 },
    { key: 'Stock', value: 300, percentage: 30 },
    { key: 'Bond', value: 100, percentage: 10 },
    { key: 'Real Estate', value: 500, percentage: 50 },
  ]);
});

test('groups allocation accounts by institution without changing backend bucket values', () => {
  const groups = groupAllocationAccounts({
    accounts: [
      { account_id: 'a', institution_name: 'Bank A', name: 'Checking', type: 'depository', balance_current: 100, source: 'cash_default', categories: { Cash: 100 } },
      { account_id: 'b', institution_name: 'Bank A', name: 'Brokerage', type: 'investment', balance_current: 200, source: 'holdings', categories: { Stock: 200 } },
    ],
  });

  assert.equal(groups[0]?.institution, 'Bank A');
  assert.equal(groups[0]?.total, 300);
  assert.equal(groups[0]?.accounts[1]?.categories?.Stock, 200);
});

test('selects the closest chart point for a horizontal touch location', () => {
  const positions = chartPointPositions(['2026-01-01', '2026-02-01', '2026-03-01', '2026-04-01']);
  assert.equal(nearestPointIndex(0, 300, positions), 0);
  assert.equal(nearestPointIndex(149, 300, positions), 1);
  assert.equal(nearestPointIndex(300, 300, positions), 3);
});

test('uses the plotted inset to make the rightmost chart point easier to select', () => {
  const positions = chartPointPositions(Array.from({ length: 30 }, (_, index) => `2026-07-${String(index + 1).padStart(2, '0')}`));
  assert.equal(nearestPointIndex(290, 300, positions, 10), 29);
  assert.equal(nearestPointIndex(10, 300, positions, 10), 0);
});

test('spaces and selects sparse chart history by time instead of point count', () => {
  const positions = chartPointPositions(['2025-01-01', '2025-01-02', '2026-01-01']);
  assert.equal(positions[0], 0);
  assert.ok(positions[1]! < 0.01);
  assert.equal(positions[2], 1);
  assert.equal(nearestPointIndex(150, 300, positions), 1);
  assert.equal(nearestPointIndex(299, 300, positions), 2);
});

test('filters allocation groups and totals by a selected asset bucket', () => {
  const groups = groupAllocationAccounts({ accounts: [
    { account_id: 'a', institution_name: 'Bank A', name: 'Cash', balance_current: 100, categories: { Cash: 100 } },
    { account_id: 'b', institution_name: 'Bank A', name: 'Stock', balance_current: 200, categories: { Stock: 200 } },
  ] });
  const filtered = filterAllocationGroupsByBucket(groups, 'Stock');
  assert.equal(filtered[0]?.accounts.length, 1);
  assert.equal(filtered[0]?.accounts[0]?.name, 'Stock');
  assert.equal(filtered[0]?.total, 200);
});

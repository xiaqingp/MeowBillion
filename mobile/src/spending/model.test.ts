import assert from 'node:assert/strict';
import test from 'node:test';

import { categoryMatrixRows, spendingHistory, yearlyCashFlow } from './model';

test('maps monthly analysis rows to chart-ready cash-flow history including net', () => {
  assert.deepEqual(spendingHistory([{ month: '2026-07', income: 5000, expense: 3200 }]), [
    { date: '2026-07-01', Income: 5000, Expense: 3200, Net: 1800 },
  ]);
});

test('keeps every configured monthly category in the matrix', () => {
  assert.deepEqual(categoryMatrixRows(['Housing', 'Dining'], [{ month: '2026-07', categories: { Housing: 140 } }]), [
    { label: '2026-07', values: [140, 0] },
  ]);
});

test('maps yearly cash flow with income expense and net', () => {
  assert.deepEqual(yearlyCashFlow([{ year: '2026', income: 60000, expense: 38000, net_savings: 22000 }]), [
    { date: '2026-01-01', Income: 60000, Expense: 38000, Net: 22000 },
  ]);
});

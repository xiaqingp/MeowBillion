import assert from 'node:assert/strict';
import test from 'node:test';

import { monthBounds } from './dateFilters';

test('monthBounds returns the complete selected month in local calendar time', () => {
  assert.deepEqual(monthBounds(new Date(2026, 1, 10)), {
    startDate: '2026-02-01',
    endDate: '2026-02-28',
  });
});

test('monthBounds handles December without crossing into the wrong year', () => {
  assert.deepEqual(monthBounds(new Date(2026, 11, 5)), {
    startDate: '2026-12-01',
    endDate: '2026-12-31',
  });
});

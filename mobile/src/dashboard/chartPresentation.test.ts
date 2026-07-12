import assert from 'node:assert/strict';
import test from 'node:test';

import { chartAxisLabels, selectedChartPointIndex, shouldCaptureChartPan } from './chartPresentation';

test('uses day labels with a separate year label for a one-month chart', () => {
  assert.deepEqual(chartAxisLabels('2026-07-01', '2026-07-31', '1M'), {
    first: 'Jul 1', last: 'Jul 31', year: '2026',
  });
});

test('uses years for an all-history chart', () => {
  assert.deepEqual(chartAxisLabels('2022-02-01', '2026-07-10', 'ALL'), {
    first: '2022', last: '2026', year: '2022 - 2026',
  });
});

test('captures intentional horizontal chart drags but leaves vertical scrolling alone', () => {
  assert.equal(shouldCaptureChartPan(18, 4), true);
  assert.equal(shouldCaptureChartPan(4, 18), false);
  assert.equal(shouldCaptureChartPan(4, 3), false);
});

test('selects the final valid point after an async history or range change', () => {
  assert.equal(selectedChartPointIndex(0), 0);
  assert.equal(selectedChartPointIndex(2), 1);
  assert.equal(selectedChartPointIndex(18), 17);
});

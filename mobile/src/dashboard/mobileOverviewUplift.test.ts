import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import test from 'node:test';

const root = join(__dirname, '..', '..');

test('mobile overview uses the balanced Tiffany chart palette', () => {
  const charts = readFileSync(join(root, 'src', 'components', 'DashboardCharts.tsx'), 'utf8');
  const app = readFileSync(join(root, 'App.tsx'), 'utf8');

  for (const color of ['#078F8B', '#238F9D', '#4A9B78', '#C89A43', '#8875A8']) {
    assert.ok(charts.includes(color));
  }
  assert.ok(app.includes('#0ABAB5'));
  assert.ok(app.includes('#066F6C'));
  assert.ok(app.includes('#E8F9F8'));
  assert.ok(!app.includes('#6268dc'));
});

test('net worth chart keeps compact selection and opens full drivers on press', () => {
  const charts = readFileSync(join(root, 'src', 'components', 'DashboardCharts.tsx'), 'utf8');
  const app = readFileSync(join(root, 'App.tsx'), 'utf8');

  assert.ok(charts.includes('onPointPress'));
  assert.ok(app.includes('/api/net_worth_drivers?date='));
  assert.ok(app.includes('NetWorthDriversSheet'));
  assert.ok(app.includes('onPointPress={openNetWorthDrivers}'));
});

test('account history captures direct touches so dragging selects chart points', () => {
  const charts = readFileSync(join(root, 'src', 'components', 'DashboardCharts.tsx'), 'utf8');
  const accountSheet = readFileSync(join(root, 'src', 'accounts', 'AccountDetailSheet.tsx'), 'utf8');

  assert.ok(accountSheet.includes('<TrendChart directTouch'));
  assert.match(charts, /\{directTouch \? \(\s*<View\b[\s\S]*?onStartShouldSetResponder=\{\(\) => true\}[\s\S]*?onResponderGrant=\{selectFromTouch\}[\s\S]*?onResponderMove=\{selectFromTouch\}/);
  assert.match(charts, /selectIndex\(nativeEvent\.locationX\)/);
  assert.ok(charts.includes('history.length === 0'));
});

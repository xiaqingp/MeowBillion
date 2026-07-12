import { TrendRange } from './model';

function asDate(value: string) {
  return new Date(`${value}T00:00:00`);
}

function format(value: string, options: Intl.DateTimeFormatOptions) {
  return new Intl.DateTimeFormat('en-US', options).format(asDate(value));
}

export function chartAxisLabels(firstDate: string, lastDate: string, range: TrendRange) {
  const firstYear = asDate(firstDate).getFullYear();
  const lastYear = asDate(lastDate).getFullYear();
  if (range === 'ALL') return { first: String(firstYear), last: String(lastYear), year: firstYear === lastYear ? String(firstYear) : `${firstYear} - ${lastYear}` };
  if (range === '1M') return { first: format(firstDate, { month: 'short', day: 'numeric' }), last: format(lastDate, { month: 'short', day: 'numeric' }), year: firstYear === lastYear ? String(firstYear) : `${firstYear} - ${lastYear}` };
  return { first: format(firstDate, { month: 'short', year: 'numeric' }), last: format(lastDate, { month: 'short', year: 'numeric' }), year: firstYear === lastYear ? String(firstYear) : `${firstYear} - ${lastYear}` };
}

export function fullChartDateLabel(value: string) {
  return format(value, { month: 'short', day: 'numeric', year: 'numeric' });
}

export function shouldCaptureChartPan(deltaX: number, deltaY: number) {
  return Math.abs(deltaX) > 8 && Math.abs(deltaX) > Math.abs(deltaY);
}

export function selectedChartPointIndex(length: number) {
  return Math.max(0, length - 1);
}

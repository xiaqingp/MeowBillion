import { useEffect, useRef, useState } from 'react';
import { LayoutChangeEvent, Pressable, StyleSheet, Text, View } from 'react-native';
import Svg, { Circle, Line, Polyline, Rect, Text as SvgText } from 'react-native-svg';

import { AssetBucket, HistoryPoint, nearestPointIndex, TrendRange } from '../dashboard/model';
import { chartAxisLabels, fullChartDateLabel, selectedChartPointIndex, shouldCaptureChartPan } from '../dashboard/chartPresentation';

const COLORS = {
  'Net Worth': '#078F8B',
  Cash: '#238F9D',
  Stock: '#4A9B78',
  Bond: '#C89A43',
  'Real Estate': '#8875A8',
  Income: '#10b981',
  Expense: '#f43f5e',
  Net: '#078F8B',
} as const;

type TrendSeries = keyof typeof COLORS;
type TrendDatum = { date: string } & Partial<Record<TrendSeries, number>>;

export function RangeControl({ active, onChange }: { active: TrendRange; onChange: (range: TrendRange) => void }) {
  return (
    <View style={styles.ranges}>
      {(['1M', '3M', '1Y', '5Y', 'ALL'] as TrendRange[]).map((range) => (
        <Pressable key={range} onPress={() => onChange(range)} style={[styles.range, active === range && styles.rangeActive]}>
          <Text style={[styles.rangeText, active === range && styles.rangeTextActive]}>{range === 'ALL' ? 'All' : range}</Text>
        </Pressable>
      ))}
    </View>
  );
}

export function TrendChart({
  history,
  range,
  series,
  formatMoney,
  displayNames,
  directTouch = false,
  barSeries = [],
  onPointPress,
}: {
  history: TrendDatum[];
  range: TrendRange;
  series: TrendSeries[];
  formatMoney: (value: number) => string;
  displayNames?: Partial<Record<TrendSeries, string>>;
  directTouch?: boolean;
  barSeries?: TrendSeries[];
  onPointPress?: (point: HistoryPoint) => void;
}) {
  const [width, setWidth] = useState(0);
  const [active, setActive] = useState(selectedChartPointIndex(history.length));
  const dragStart = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => setActive(selectedChartPointIndex(history.length)), [history.length, history.at(-1)?.date]);

  if (history.length < 2) {
    return <View style={styles.chartEmpty}><Text style={styles.chartEmptyText}>Not enough history yet.</Text></View>;
  }

  const values = history.flatMap((point) => series.map((key) => Number(point[key] || 0)));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const domainMin = barSeries.length ? Math.min(0, min) : min;
  const domainMax = barSeries.length ? Math.max(0, max) : max;
  const chartWidth = 320;
  const chartHeight = 132;
  const padding = 10;
  const x = (index: number) => padding + (index / (history.length - 1)) * (chartWidth - padding * 2);
  const y = (value: number) => chartHeight - padding - (domainMax === domainMin ? 0.5 : (value - domainMin) / (domainMax - domainMin)) * (chartHeight - padding * 2);
  const points = (key: TrendSeries) => history.map((point, index) => `${x(index)},${y(Number(point[key] || 0))}`).join(' ');
  const lineSeries = series.filter((key) => !barSeries.includes(key));
  const barWidth = Math.max(3, Math.min(12, (chartWidth - padding * 2) / history.length / Math.max(barSeries.length + 1, 2)));
  const activeIndex = Math.min(Math.max(active, 0), history.length - 1);
  const point = history[activeIndex]!;
  const labels = chartAxisLabels(history[0].date, history.at(-1)!.date, range);
  const selectIndex = (locationX: number) => {
    const index = nearestPointIndex(locationX, width, history.length);
    setActive(index);
    return index;
  };
  const shouldClaim = (event: any) => {
    const start = dragStart.current;
    return !!start && shouldCaptureChartPan(event.nativeEvent.pageX - start.x, event.nativeEvent.pageY - start.y);
  };
  const responder = {
    onStartShouldSetResponder: () => directTouch,
    onMoveShouldSetResponder: shouldClaim,
    onMoveShouldSetResponderCapture: shouldClaim,
    onResponderGrant: (event: any) => selectIndex(event.nativeEvent.locationX),
    onResponderMove: (event: any) => selectIndex(event.nativeEvent.locationX),
    onResponderRelease: (event: any) => selectIndex(event.nativeEvent.locationX),
    onResponderTerminationRequest: () => false,
    onTouchStart: (event: any) => {
      dragStart.current = { x: event.nativeEvent.pageX, y: event.nativeEvent.pageY };
    },
  };

  return (
    <View>
      <View style={styles.tooltip}>
        <Text style={styles.tooltipDate}>{fullChartDateLabel(point.date)}</Text>
        {series.map((key) => (
          <Text key={key} style={styles.tooltipValue}>{displayNames?.[key] || key}: {formatMoney(Number(point[key] || 0))}</Text>
        ))}
      </View>
      <Pressable
        onLayout={(event: LayoutChangeEvent) => setWidth(event.nativeEvent.layout.width)}
        onPress={onPointPress ? (event) => onPointPress(history[selectIndex(event.nativeEvent.locationX)] as HistoryPoint) : undefined}
        {...responder}
      >
        <Svg height={chartHeight} pointerEvents="none" preserveAspectRatio="none" viewBox={`0 0 ${chartWidth} ${chartHeight}`} width="100%">
          {barSeries.flatMap((key, barIndex) => history.map((item, index) => {
            const value = Number(item[key] || 0);
            const baseline = y(0);
            const valueY = y(value);
            return (
              <Rect
                fill={COLORS[key]}
                height={Math.abs(baseline - valueY)}
                key={`${key}-${item.date}`}
                opacity="0.78"
                rx="1"
                width={barWidth}
                x={x(index) + (barIndex - (barSeries.length - 1) / 2) * barWidth}
                y={Math.min(baseline, valueY)}
              />
            );
          }))}
          {lineSeries.map((key) => (
            <Polyline fill="none" key={key} points={points(key)} stroke={COLORS[key]} strokeLinecap="round" strokeLinejoin="round" strokeWidth={key === 'Net Worth' || key === 'Net' ? 3 : 2} />
          ))}
          <Line stroke="#9aa4b6" strokeDasharray="3 3" strokeWidth="1" x1={x(activeIndex)} x2={x(activeIndex)} y1="0" y2={chartHeight} />
          {lineSeries.map((key) => (
            <Circle cx={x(activeIndex)} cy={y(Number(point[key] || 0))} fill="#fff" key={key} r="4" stroke={COLORS[key]} strokeWidth="2" />
          ))}
        </Svg>
      </Pressable>
      <View style={styles.axis}>
        <Text style={styles.axisText}>{labels.first}</Text>
        <Text style={styles.axisYear}>{labels.year}</Text>
        <Text style={styles.axisText}>{labels.last}</Text>
      </View>
      <View style={styles.legend}>
        {series.map((key) => (
          <View key={key} style={styles.legendItem}>
            <View style={[styles.legendDot, { backgroundColor: COLORS[key] }]} />
            <Text style={styles.legendText}>{displayNames?.[key] || key}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

export function AllocationDonut({ rows, selectedKey, onSelect, formatMoney }: {
  rows: Array<{ key: AssetBucket; value: number; percentage: number }>;
  selectedKey: AssetBucket | 'All';
  onSelect: (key: AssetBucket | 'All') => void;
  formatMoney: (value: number) => string;
}) {
  const total = rows.reduce((sum, row) => sum + row.value, 0);
  if (!total) return <View style={styles.chartEmpty}><Text style={styles.chartEmptyText}>No allocatable assets yet.</Text></View>;
  const selected = selectedKey === 'All' ? { key: 'All', value: total, percentage: 100 } : rows.find((row) => row.key === selectedKey)!;
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;
  return (
    <View style={styles.donutLayout}>
      <Svg height={138} viewBox="0 0 138 138" width={138}>
        {rows.map((row) => {
          const dash = row.value / total * circumference;
          const node = <Circle cx="69" cy="69" fill="none" key={row.key} r={radius} stroke={COLORS[row.key]} strokeDasharray={`${dash} ${circumference - dash}`} strokeDashoffset={-offset} strokeOpacity={selectedKey === 'All' || selectedKey === row.key ? 1 : 0.25} strokeWidth={selectedKey === row.key ? 23 : 18} transform="rotate(-90 69 69)" onPress={() => onSelect(selectedKey === row.key ? 'All' : row.key)} />;
          offset += dash;
          return node;
        })}
        <Circle cx="69" cy="69" fill="#fff" r="35" />
        <SvgText fill="#263047" fontSize="10" fontWeight="700" textAnchor="middle" x="69" y="65">{selected.key}</SvgText>
        <SvgText fill="#263047" fontSize="11" fontWeight="700" textAnchor="middle" x="69" y="80">{formatMoney(selected.value)}</SvgText>
      </Svg>
      <View style={styles.donutRows}>
        <Pressable onPress={() => onSelect('All')} style={[styles.donutRow, selectedKey === 'All' && styles.rowActive]}>
          <Text style={styles.donutLabel}>All assets</Text><Text style={styles.donutValue}>{formatMoney(total)}</Text>
        </Pressable>
        {rows.map((row) => (
          <Pressable key={row.key} onPress={() => onSelect(selectedKey === row.key ? 'All' : row.key)} style={[styles.donutRow, selectedKey === row.key && styles.rowActive]}>
            <View style={[styles.legendDot, { backgroundColor: COLORS[row.key] }]} />
            <Text style={styles.donutLabel}>{row.key}</Text>
            <Text style={styles.donutValue}>{formatMoney(row.value)} ({row.percentage}%)</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  ranges: { flexDirection: 'row', gap: 4, flexWrap: 'wrap' },
  range: { borderColor: '#dce5e7', borderRadius: 4, borderWidth: 1, minWidth: 34, paddingHorizontal: 7, paddingVertical: 5 },
  rangeActive: { backgroundColor: '#E8F9F8', borderColor: '#0ABAB5' },
  rangeText: { color: '#697a82', fontSize: 11, fontWeight: '600', textAlign: 'center' },
  rangeTextActive: { color: '#066F6C' },
  chartEmpty: { alignItems: 'center', justifyContent: 'center', minHeight: 146 },
  chartEmptyText: { color: '#8992a4', fontSize: 12 },
  tooltip: { alignItems: 'center', backgroundColor: '#f4f7f8', borderRadius: 6, marginBottom: 8, padding: 7 },
  tooltipDate: { color: '#17262d', fontSize: 12, fontWeight: '700' },
  tooltipValue: { color: '#52666f', fontSize: 11, marginTop: 2 },
  axis: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 3 },
  axisText: { color: '#8992a4', fontSize: 10 },
  axisYear: { color: '#52666f', fontSize: 10, fontWeight: '700' },
  legend: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginTop: 8 },
  legendItem: { alignItems: 'center', flexDirection: 'row', gap: 4 },
  legendDot: { borderRadius: 4, height: 8, width: 8 },
  legendText: { color: '#52666f', fontSize: 11 },
  donutLayout: { alignItems: 'center', gap: 14 },
  donutRows: { alignSelf: 'stretch', gap: 5 },
  donutRow: { alignItems: 'center', borderRadius: 5, flexDirection: 'row', padding: 5 },
  rowActive: { backgroundColor: '#E8F9F8' },
  donutLabel: { color: '#52666f', flex: 1, fontSize: 12, marginLeft: 7 },
  donutValue: { color: '#17262d', fontSize: 12, fontWeight: '700' },
});

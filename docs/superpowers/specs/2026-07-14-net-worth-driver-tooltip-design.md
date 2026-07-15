# Net Worth Driver Tooltip Design

## Status

- Product: MeowBillion Overview
- Direction: Approved on 2026-07-14
- Scope: Explain each Net Worth Trend point with the largest account-level positive and negative contributions

## Goal

Let a user understand why Net Worth changed between two recorded snapshots without adding another permanent dashboard panel. The explanation appears inside an expanded Net Worth Trend tooltip only when the user inspects a point.

## Interaction

- Desktop: hovering a Net Worth point opens the driver tooltip.
- iPad/touch: tapping a point pins the tooltip; tapping elsewhere closes it.
- The existing time-range controls remain unchanged.
- The latest visible point is prepared asynchronously after the chart renders, but driver loading never blocks the chart or Overview first paint.
- Previously loaded dates are cached in memory for the current page session.

## Tooltip Layout

The existing canvas tooltip becomes an external HTML tooltip constrained to the chart/viewport edges.

```text
Jul 14, 2026
Net Worth                         $7,238,412
Change since Jul 13        +$12,438  +0.18%

TOP MOVES UP
Individual - TOD                    +$8,420
Meta Platform                       +$3,210
BOA Checking                          +$810

TOP MOVES DOWN
Morgan Stanley                     -$1,420
Citi Credit Card                     -$390
Cash Management                      -$120

Explained 97.4% | Unattributed +$318
```

Presentation rules:

- Maximum three positive and three negative contributors.
- Account name is primary; institution/source is muted secondary text when space allows.
- Long names truncate visually and retain the full value in `title`.
- Positive contribution uses the coordinated Stock/success green; negative contribution uses semantic danger red.
- Tiffany is reserved for the selected point, tooltip border, and loading indicator.
- Missing positive or negative rows show a compact neutral empty state.
- While a date is loading, the date, Net Worth, and total change remain visible with one `Loading account drivers...` line.

## Comparison Semantics

- `selected_date` is the hovered/tapped Net Worth snapshot date.
- `previous_date` is the immediately preceding Net Worth snapshot date, not necessarily the prior calendar day.
- The UI says `Change since <previous date>` so sparse monthly Legacy history is not mislabeled as a daily change.
- Multiple syncs on the same date already collapse to the final value because account history uses one row per account/date.

## Contribution Calculation

The explanation includes every item that contributes to Net Worth:

- Plaid deposit and investment accounts.
- Manual assets represented by `account_value_estimates` / manual history.
- Credit/liability accounts with reversed Net Worth impact.

For each item, obtain the latest value on or before `selected_date` and the latest value on or before `previous_date`:

- Asset contribution: `selected_value - previous_value`.
- Liability contribution: `previous_value - selected_value`.
- A newly represented asset has a zero prior value and is labeled `Newly included`.

Rank positive contributions descending and negative contributions ascending. Zero-change items are omitted.

## Reconciliation

- `net_worth_change` comes from the existing allocation history series.
- `explained_change` is the sum of all available account/manual-asset contributions, not only the displayed top six.
- `unattributed_change = net_worth_change - explained_change`.
- `change_pct = net_worth_change / abs(previous_net_worth) * 100`; it is `null` when the previous Net Worth is zero.
- `coverage_pct = clamp((1 - abs(unattributed_change) / abs(net_worth_change)) * 100, 0, 100)`.
- When the Net Worth change rounds to zero cents, coverage is `100` if the residual also rounds to zero cents and `0` otherwise.
- Legacy aggregate snapshots without account-level history may have a material unattributed amount. The UI displays it instead of inventing account attribution.
- Minor currency rounding residuals under `$0.01` display as zero.

## API

Add a user-scoped endpoint:

`GET /api/net_worth_drivers?date=YYYY-MM-DD`

Response:

```json
{
  "date": "2026-07-14",
  "previous_date": "2026-07-13",
  "net_worth": 7238412.0,
  "previous_net_worth": 7225974.0,
  "net_worth_change": 12438.0,
  "change_pct": 0.1721,
  "explained_change": 12120.0,
  "unattributed_change": 318.0,
  "coverage_pct": 97.4,
  "top_up": [
    {
      "account_id": "acc_1",
      "name": "Individual - TOD",
      "institution_name": "Fidelity",
      "source": "plaid",
      "previous_balance": 2234000.0,
      "current_balance": 2242420.0,
      "contribution": 8420.0,
      "newly_included": false
    }
  ],
  "top_down": []
}
```

Validation and behavior:

- Require authenticated `current_user_id()` scope on every query.
- Return `400` for a missing/invalid date.
- Return `404` if the requested date is not a Net Worth snapshot or has no previous snapshot.
- Do not return all account histories or access tokens.

## Frontend Data Flow

1. Render Net Worth Trend immediately from `/api/allocation_history` as today.
2. Asynchronously request drivers for the latest visible point and cache by date.
3. On hover/tap, render the external tooltip from cache.
4. For an uncached date, render the loading row, request that date once, then refresh the tooltip only if the same point remains active.
5. Clear the driver cache after sync or allocation/manual-asset changes, alongside the existing allocation-history cache.

This date-on-demand contract keeps the default Overview payload small and avoids sending years of account attribution during initial load.

## Files Expected to Change

- `routes_plaid.py`: driver calculation and endpoint.
- `modules/api.js`: date-specific driver request.
- `app.js`: cache, external tooltip, hover/tap pinning, and cache invalidation.
- `styles.css`: external tooltip styling and responsive constraints.
- `tests/test_net_worth_drivers.py`: calculation, liability, manual asset, residual, and user-scope tests.
- A focused frontend static regression test for tooltip wiring.

## Responsive and Accessibility

- Tooltip width is capped around `420px` and uses a single-column list so six rows remain readable without fragile side-by-side columns.
- At narrow widths it uses `min(420px, calc(100vw - 24px))` and remains inside the viewport.
- Touch pinning prevents the tooltip from disappearing before it can be read.
- Positive/negative rows use arrows and signed amounts in addition to color.
- Account names and monetary values never overlap; values use tabular numerals.

## Verification

- Backend tests prove asset, liability, manual-asset, Legacy residual, missing-date, and user-isolation behavior.
- Frontend test proves external tooltip wiring, six-row limit, touch pinning, and cache invalidation hooks.
- JavaScript syntax checks pass.
- Full unittest suite passes.
- Desktop and iPad visual checks cover edge positioning, long account names, loading, empty-side, positive day, negative day, and Legacy residual states.

## Acceptance Criteria

1. Hovering a Net Worth point on desktop shows Top 3 Up and Top 3 Down inside its tooltip.
2. Tapping a point on iPad pins the same tooltip and tapping elsewhere closes it.
3. The tooltip shows current Net Worth, total change, percentage, selected date, and actual previous snapshot date.
4. Assets, liabilities, and manual assets use correct Net Worth contribution signs.
5. Displayed movers plus the reconciliation values explain the total change without hiding unsupported Legacy residuals.
6. Tooltip driver loading and errors do not block or break the Net Worth chart.
7. Existing Overview time ranges and chart behavior remain intact.

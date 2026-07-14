# Tiffany Balanced Theme Design

## Status

- Product: MeowBillion web app
- Direction: Approved in visual mockup review on 2026-07-13
- Scope: Visual theme only; no data, API, navigation, or workflow changes

## Goal

Make the web interface feel intentionally connected to the Tiffany MeowBillion logo without turning the entire application teal. Tiffany identifies the brand and interactive state. Financial and operational meaning continues to use distinct semantic colors.

## Color System

### Brand and surfaces

| Role | Color | Usage |
| --- | --- | --- |
| Tiffany primary | `#0ABAB5` | Primary actions, active navigation indicator, focus rings, selected controls |
| Tiffany deep | `#078F8B` | Hover/pressed states and accessible text accents |
| Tiffany ink | `#066F6C` | Text on pale Tiffany backgrounds |
| Tiffany wash | `#E8F9F8` | Active navigation fill, selected rows, subtle badges |
| Page background | `#F4F7F8` | Main application background |
| Surface | `#FFFFFF` | Cards, tables, controls, sidebar |
| Border | `#DCE5E7` | Dividers, input borders, card borders |
| Primary text | `#17262D` | Headings and body text |
| Muted text | `#697A82` | Metadata and supporting labels |

The existing Indigo primary and purple brand gradient are removed from brand surfaces. Tiffany is not used as a blanket section background.

### Allocation palette

| Category | Color | Design intent |
| --- | --- | --- |
| Cash | `#238F9D` | Ocean teal, related to Tiffany but darker and bluer |
| Stock | `#4A9B78` | Calm sage green that still communicates growth |
| Bond | `#C89A43` | Muted gold, distinct from warning orange |
| Real Estate | `#8875A8` | Soft violet counterpoint with matching visual weight |

All four allocation colors use calmer saturation and similar perceived weight. They remain distinguishable in lines, donut segments, legends, and compact account-allocation bars.

### Semantic colors

Success/income, danger/expense, warning, pending, and informational states retain independent semantic colors. Brand Tiffany must not replace error red, warning amber, or income green. UI states must also include text, icon, or label cues so color is not the only signal.

## Component Changes

- Sidebar: Tiffany wash for the active item, deep Tiffany text, and a Tiffany left indicator. Inactive items remain neutral.
- Brand: solid dark text replaces the Indigo-to-purple wordmark gradient. The existing Tiffany logo and white cat outline remain unchanged.
- Buttons: primary buttons use Tiffany; secondary buttons remain white/neutral; destructive buttons remain red.
- Forms: focus border/ring and selected states use Tiffany. Error and warning states retain their semantic colors.
- Tabs and segmented controls: active option uses a neutral surface with Tiffany text/indicator rather than a large teal fill.
- Links and compact actions: use Tiffany deep for sufficient contrast on white.
- Net Worth chart: Tiffany deep is the single primary series color.
- Allocation charts: use the approved four-color allocation palette consistently across trend lines, donut charts, legends, and account rows.
- Tables and cards: use cool white/gray surfaces and restrained borders. No layout or density change is included.

## Implementation Shape

- Update the existing CSS variables in `styles.css` and replace remaining brand-specific Indigo/purple literals in components touched by the theme.
- Define one small shared chart color map in `app.js` for brand and allocation series so Overview charts cannot drift from each other.
- Keep status colors in `modules/transaction-renderer.js` semantic. Only primary-brand fallbacks are updated where needed.
- Do not add a theming dependency, design-system framework, dark mode, or user-selectable themes.

## Responsive Behavior

The theme does not alter breakpoints or layout. Active navigation, focus states, chart legends, and account-allocation bars must remain legible in desktop, iPad-width, and compact-sidebar modes.

## Verification

- Add a focused static regression test that asserts the approved CSS tokens and chart allocation colors.
- Run JavaScript syntax validation for changed frontend files.
- Run the existing unit suite because shared CSS/HTML selectors and brand tests may be affected.
- Visually check Overview, Spending, Transactions, Travel, Rentals, Categories, and Plaid at desktop and iPad widths.
- Verify primary, hover, focus, warning, danger, pending, and reviewed states are still distinguishable.
- Confirm no Indigo/purple brand gradient remains while Real Estate retains its approved soft violet data color.

## Acceptance Criteria

1. The Tiffany logo, active navigation, primary actions, focus states, and selected controls read as one brand system.
2. The page remains predominantly white and cool gray rather than Tiffany-filled.
3. Cash, Stock, Bond, and Real Estate use the approved coordinated palette everywhere on Overview.
4. Financial and operational semantic colors remain meaningful and are not replaced by Tiffany.
5. No data behavior, chart values, layout structure, or API behavior changes.
6. Desktop and iPad layouts retain their current spacing and readability.

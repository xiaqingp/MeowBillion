export type MonthlyRow = { month: string; income: number; expense: number; net_savings?: number };
export type CashFlowRow = { year: string; income: number; expense: number; net_savings?: number };
export type CategoryMatrixRow = { month?: string; year?: string; categories: Record<string, number> };

export function spendingHistory(rows: MonthlyRow[]) {
  return rows.map((row) => ({ date: `${row.month}-01`, Income: Number(row.income || 0), Expense: Number(row.expense || 0), Net: Number(row.net_savings ?? Number(row.income || 0) - Number(row.expense || 0)) }));
}

export function yearlyCashFlow(rows: CashFlowRow[]) {
  return rows.map((row) => ({ date: `${row.year}-01-01`, Income: Number(row.income || 0), Expense: Number(row.expense || 0), Net: Number(row.net_savings ?? Number(row.income || 0) - Number(row.expense || 0)) }));
}

export function categoryMatrixRows(categories: string[], rows: CategoryMatrixRow[]) {
  return rows.map((row) => ({ label: row.month || row.year || '', values: categories.map((category) => Number(row.categories[category] || 0)) }));
}

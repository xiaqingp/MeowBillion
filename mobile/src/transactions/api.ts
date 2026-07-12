export type TransactionFilters = {
  page: number;
  limit: number;
  query?: string;
  reviewedFilter?: string;
  account?: string;
  direction?: string;
  category?: string;
  subtype?: string;
  startDate?: string;
  endDate?: string;
  assignment?: string;
};
export type TransactionRow = {
  TransactionID: string;
  Type?: string;
  IsB?: string;
  Ratio?: number;
  Mown?: number;
  Note?: string;
  SubType?: string;
};

export function buildTransactionQuery(filters: TransactionFilters) {
  const query = new URLSearchParams({
    page: String(filters.page),
    limit: String(filters.limit),
  });
  if (filters.query) query.set("query", filters.query);
  if (filters.reviewedFilter)
    query.set("reviewed_filter", filters.reviewedFilter);
  if (filters.account && filters.account !== "all")
    query.set("account", filters.account);
  if (filters.direction && filters.direction !== "all")
    query.set("direction", filters.direction);
  if (filters.category && filters.category !== "all")
    query.set("category", filters.category);
  if (filters.subtype && filters.subtype !== "all")
    query.set("subtype", filters.subtype);
  if (filters.startDate) query.set("start_date", filters.startDate);
  if (filters.endDate) query.set("end_date", filters.endDate);
  if (filters.assignment && filters.assignment !== "all")
    query.set(
      "assignment",
      filters.assignment.replace(/^property:/, "rental:"),
    );
  return `/api/transactions?${query}`;
}

export function buildTransactionReviewPayload(transaction: TransactionRow) {
  return {
    transaction_id: transaction.TransactionID,
    type: transaction.Type || "Other",
    is_b: transaction.IsB || "n",
    ratio: transaction.Ratio ?? 1,
    mown: transaction.Mown ?? 0,
    note: transaction.Note || "",
    subtype: transaction.SubType || "",
  };
}

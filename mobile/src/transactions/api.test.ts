import assert from "node:assert/strict";
import test from "node:test";

import { buildTransactionQuery, buildTransactionReviewPayload } from "./api";

test("serializes transaction pagination and filters for the existing backend", () => {
  assert.equal(
    buildTransactionQuery({
      page: 2,
      limit: 20,
      query: "market",
      reviewedFilter: "unreviewed",
      account: "acc_1",
      direction: "outflow",
      category: "Food",
      subtype: "Restaurant",
      startDate: "2026-01-01",
      endDate: "2026-01-31",
      assignment: "trip:7",
    }),
    "/api/transactions?page=2&limit=20&query=market&reviewed_filter=unreviewed&account=acc_1&direction=outflow&category=Food&subtype=Restaurant&start_date=2026-01-01&end_date=2026-01-31&assignment=trip%3A7",
  );
});

test("creates the existing update_transaction payload from a transaction row", () => {
  assert.deepEqual(
    buildTransactionReviewPayload({
      TransactionID: "tx-1",
      Type: "Groceries",
      IsB: "n",
      Ratio: 1,
      Mown: 0,
      IsReimbursement: 1,
      Note: "weekly",
      SubType: "Food",
    }),
    {
      transaction_id: "tx-1",
      type: "Groceries",
      is_b: "n",
      ratio: 1,
      mown: 0,
      is_reimbursement: true,
      note: "weekly",
      subtype: "Food",
    },
  );
});

test("maps the mobile property assignment label to the backend rental filter", () => {
  assert.equal(
    buildTransactionQuery({ page: 1, limit: 50, assignment: "property:9" }),
    "/api/transactions?page=1&limit=50&assignment=rental%3A9",
  );
});

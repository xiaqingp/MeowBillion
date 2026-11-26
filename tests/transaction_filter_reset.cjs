const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "..", "app.js"), "utf8");
const start = source.indexOf("function resetTransactionFilters()");
assert.ok(start >= 0, "Reset handler must exist");
const end = source.indexOf("\nfunction ", start + 1);
const handler = source.slice(start, end < 0 ? source.length : end);
const selectIds = [
    "tx-account-filter", "tx-assignment-filter", "tx-subcategory-filter",
    "tx-reimbursement-filter",
];
const inputIds = [
    "tx-search-input", "tx-month-filter", "tx-start-date", "tx-end-date",
    "tx-amount-filter",
];
const elements = Object.fromEntries(
    [...selectIds, ...inputIds].map(id => [id, { value: "previous selection" }])
);
let refreshes = 0;
const context = vm.createContext({
    document: {
        getElementById: id => elements[id] || null,
        querySelectorAll: () => [],
    },
    setMultiselectValues: () => {},
    triggerFilterUpdate: () => { refreshes++; },
});
vm.runInContext(handler + "\nresetTransactionFilters();", context, { timeout: 1000 });
for (const id of selectIds) assert.equal(elements[id].value, "all", `${id} must reset`);
for (const id of inputIds) assert.equal(elements[id].value, "", `${id} must clear`);
assert.equal(refreshes, 1, "Reset must refresh the transaction filters once");

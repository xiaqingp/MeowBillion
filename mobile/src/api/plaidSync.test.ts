import assert from 'node:assert/strict';
import test from 'node:test';

import { plaidSyncMessage } from './plaidSync';

test('reports partial sync results using failed institutions and institutional warnings', () => {
  assert.equal(plaidSyncMessage({
    status: 'partial_success',
    new_transactions_count: 1,
    succeeded_items: [{ institution_name: 'Bank A', warnings: [{}] }],
    failed_items: [{ institution_name: 'Bank B' }],
  }), 'Plaid sync finished with issues. 1 new transaction. Failed: Bank B. Warnings: Bank A.');
});

test('reports successful, failed, and unlinked syncs separately', () => {
  assert.equal(plaidSyncMessage({ status: 'success', new_transactions_count: 2 }), 'Plaid sync complete. 2 new transactions.');
  assert.equal(plaidSyncMessage({ status: 'success', succeeded_items: [] }), 'No Plaid accounts are linked.');
  assert.equal(plaidSyncMessage({ status: 'failed', failed_items: [{ institution_name: 'Bank A' }] }), 'Plaid sync failed. Failed: Bank A.');
});

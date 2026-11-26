type SyncedInstitution = { institution_name: string; warnings?: unknown[] };

export type PlaidSyncResult = {
  status: 'success' | 'partial_success' | 'failed';
  new_transactions_count?: number;
  succeeded_items?: SyncedInstitution[];
  failed_items?: SyncedInstitution[];
};

export function plaidSyncMessage(result: PlaidSyncResult) {
  const count = result.new_transactions_count ?? 0;
  const imported = `${count} new ${count === 1 ? 'transaction' : 'transactions'}.`;
  const failed = result.failed_items?.map((item) => item.institution_name).filter(Boolean).join(', ');
  const warned = result.succeeded_items?.filter((item) => item.warnings?.length)
    .map((item) => item.institution_name).filter(Boolean).join(', ');
  const details = [failed && `Failed: ${failed}.`, warned && `Warnings: ${warned}.`].filter(Boolean).join(' ');

  if (result.status === 'failed') return `Plaid sync failed.${details ? ` ${details}` : ''}`;
  if (result.status === 'partial_success') return `Plaid sync finished with issues. ${imported}${details ? ` ${details}` : ''}`;
  if (result.succeeded_items?.length === 0) return 'No Plaid accounts are linked.';
  return `Plaid sync complete. ${imported}`;
}

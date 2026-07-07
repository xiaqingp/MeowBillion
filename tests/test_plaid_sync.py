import unittest

from routes_plaid import summarize_sync_results


class PlaidSyncSummaryTests(unittest.TestCase):
    def test_success_when_all_items_succeed(self):
        self.assertEqual(summarize_sync_results([{"item_id": "a"}], []), "success")

    def test_partial_success_when_some_items_fail(self):
        self.assertEqual(summarize_sync_results([{"item_id": "a"}], [{"item_id": "b"}]), "partial_success")

    def test_failed_when_all_items_fail(self):
        self.assertEqual(summarize_sync_results([], [{"item_id": "b"}]), "failed")

    def test_success_when_no_items(self):
        self.assertEqual(summarize_sync_results([], []), "success")


if __name__ == "__main__":
    unittest.main()

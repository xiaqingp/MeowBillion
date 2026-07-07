import unittest

from routes_plaid import classify_security_bucket, normalize_account_asset_buckets


class AllocationClassificationTests(unittest.TestCase):
    def test_brokered_cd_is_bond_even_when_name_contains_cash(self):
        security = {
            "type": "other",
            "ticker_symbol": "LIVE.OAK.BKG.CO.NC.CD.3.90000",
            "name": "LIVE OAK BKG CO NC CD 3.90000 03/31/2027 - INTEREST (Cash)",
        }

        self.assertEqual(classify_security_bucket(security), "Bond")

    def test_checking_without_holdings_is_cash_default(self):
        account = {"type": "depository", "subtype": "checking", "balance_current": 100, "categories": {}}

        normalize_account_asset_buckets(account)

        self.assertEqual(account["categories"]["Cash"], 100)
        self.assertEqual(account["allocation_source"], "cash_default")

    def test_cash_management_without_holdings_needs_allocation(self):
        account = {"type": "depository", "subtype": "cash management", "name": "CMA-Edge", "balance_current": 100, "categories": {}}

        normalize_account_asset_buckets(account)

        self.assertEqual(sum(account["categories"].values()), 0)
        self.assertEqual(account["allocation_source"], "needs_allocation")

    def test_investment_without_holdings_needs_allocation(self):
        account = {"type": "investment", "subtype": "brokerage", "balance_current": 100, "categories": {}}

        normalize_account_asset_buckets(account)

        self.assertEqual(sum(account["categories"].values()), 0)
        self.assertEqual(account["allocation_source"], "needs_allocation")

    def test_holdings_source_when_buckets_exist(self):
        account = {"type": "investment", "subtype": "brokerage", "balance_current": 100, "categories": {"Bond": 60, "Cash": 40}}

        normalize_account_asset_buckets(account)

        self.assertEqual(account["allocation_source"], "holdings")
        self.assertEqual(account["categories"]["Bond"], 60)


if __name__ == "__main__":
    unittest.main()

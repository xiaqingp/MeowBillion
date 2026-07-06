import unittest

from routes_plaid import classify_security_bucket


class AllocationClassificationTests(unittest.TestCase):
    def test_brokered_cd_is_bond_even_when_name_contains_cash(self):
        security = {
            "type": "other",
            "ticker_symbol": "LIVE.OAK.BKG.CO.NC.CD.3.90000",
            "name": "LIVE OAK BKG CO NC CD 3.90000 03/31/2027 - INTEREST (Cash)",
        }

        self.assertEqual(classify_security_bucket(security), "Bond")


if __name__ == "__main__":
    unittest.main()

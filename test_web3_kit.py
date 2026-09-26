import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from web3_kit import address_book, event_index, gas_ledger, netflow, nonce_gaps, supply_check


ADDR = "0x" + "a" * 40


class Web3KitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "input"

    def test_gas_cost_uses_exact_units(self):
        self.path.write_text("date,gas_used,gas_price_gwei\n2026-10-01,21000,10\n")
        self.assertEqual(gas_ledger(self.path), {"2026-10": "0.00021"})

    def test_nonce_report_finds_gap_and_duplicate(self):
        self.path.write_text(f"chain_id,address,nonce\n1,{ADDR},1\n1,{ADDR},3\n1,{ADDR},3\n")
        result = next(iter(nonce_gaps(self.path).values()))
        self.assertEqual(result, {"missing_between_observed": [2], "duplicates": [3]})

    def test_supply_cap_flags_excess(self):
        self.path.write_text("date,amount\n2026-10-01,60\n2026-10-02,50\n")
        self.assertEqual(len(supply_check(self.path, Decimal("100"))["over_cap_events"]), 1)

    def test_event_index(self):
        self.path.write_text('{"abi":[{"type":"event","name":"Moved","inputs":'
                             '[{"name":"to","type":"address","indexed":true}]}]}')
        self.assertEqual(event_index(self.path)[0]["indexed"], ["to"])

    def test_address_book_detects_case_insensitive_duplicate(self):
        self.path.write_text(f"chain_id,address,label\n1,{ADDR},A\n1,{ADDR.upper().replace('0X','0x')},B\n")
        self.assertEqual(len(address_book(self.path)), 1)

    def test_netflow_is_per_token(self):
        self.path.write_text("token,direction,amount\nUSDC,in,2.5\nUSDC,out,1\nETH,in,3\n")
        self.assertEqual(netflow(self.path), {"ETH": "3", "USDC": "1.5"})


if __name__ == "__main__":
    unittest.main()

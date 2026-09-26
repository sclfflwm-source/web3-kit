import tempfile
import unittest
from pathlib import Path

from abi_guard import canonical_type, compare, load_abi, render_markdown


class AbiGuardTests(unittest.TestCase):
    def test_tuple_signature_and_integer_alias(self):
        parameter = {"type": "tuple[]", "components": [
            {"type": "uint"}, {"type": "tuple[2]", "components": [{"type": "address"}]},
        ]}
        self.assertEqual(canonical_type(parameter), "(uint256,(address)[2])[]")

    def test_removed_and_changed_entries(self):
        old = [
            {"type": "function", "name": "balance", "inputs": [],
             "outputs": [{"type": "uint256"}], "stateMutability": "view"},
            {"type": "event", "name": "Moved", "inputs": [
                {"type": "address", "indexed": True}]},
        ]
        new = [
            {"type": "function", "name": "balance", "inputs": [],
             "outputs": [{"type": "int256"}], "stateMutability": "view"},
            {"type": "function", "name": "pause", "inputs": []},
            {"type": "event", "name": "Moved", "inputs": [
                {"type": "address", "indexed": False}]},
        ]
        changes = compare(old, new)
        self.assertEqual([item["severity"] for item in changes],
                         ["review", "breaking", "breaking"])
        self.assertIn("pause()", render_markdown(changes))

    def test_signature_change_is_removal_and_addition(self):
        old = [{"type": "function", "name": "send", "inputs": [{"type": "uint"}]}]
        new = [{"type": "function", "name": "send", "inputs": [{"type": "address"}]}]
        changes = compare(old, new)
        self.assertEqual({item["change"] for item in changes}, {"removed", "added"})

    def test_artifact_format_and_invalid_input(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "artifact.json"
            path.write_text('{"abi": [{"type": "receive", "stateMutability": "payable"}]}')
            self.assertEqual(len(load_abi(path)), 1)
            path.write_text('{"abi": {}}')
            with self.assertRaisesRegex(ValueError, "expected an ABI array"):
                load_abi(path)


if __name__ == "__main__":
    unittest.main()

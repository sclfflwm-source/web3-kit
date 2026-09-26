# Web3 Kit

**Seven offline checks for EVM developers and analysts.** Web3 Kit reads data you provide and prints reports. It does not connect wallets, sign transactions, query RPC nodes, or make investment recommendations.

| Command | Input | Output |
| --- | --- | --- |
| `gas-ledger` | CSV: `date,gas_used,gas_price_gwei` | ETH fees by month. |
| `nonce-gaps` | CSV: `chain_id,address,nonce` | Gaps and duplicates between observed nonces. |
| `supply-check` | CSV: `date,amount` plus `--cap` | Cumulative scheduled unlocks above a cap. |
| `event-index` | Solidity ABI JSON | Event signatures and indexed fields. |
| `address-book` | CSV: `chain_id,address,label` | Invalid or duplicate EVM addresses. |
| `netflow` | CSV: `token,direction,amount` | Net token amounts by symbol. |
| `abi_guard.py` | Two Solidity ABI JSON files | Markdown or JSON interface change report. |

## Quick start

```sh
python3 web3_kit.py gas-ledger examples/gas.csv
python3 web3_kit.py nonce-gaps examples/nonces.csv
python3 web3_kit.py supply-check examples/unlocks.csv --cap 1000000
python3 web3_kit.py event-index examples/token.abi.json
python3 web3_kit.py address-book examples/addresses.csv
python3 web3_kit.py netflow examples/flows.csv
python3 abi_guard.py examples/abi-baseline.json examples/abi-candidate.json
```

Amounts use Python `Decimal` to avoid floating-point rounding. Gas cost is `gas_used × gas_price_gwei ÷ 1,000,000,000` ETH, based on [Ethereum's gas units](https://ethereum.org/developers/docs/gas/). `supply-check` compares **supplied schedule totals** with the supplied cap; it does not infer actual circulating supply. `address-book` checks syntax, not EIP-55 checksum or whether an address is deployed.

`nonce-gaps` only reports missing values between the lowest and highest nonces in the input, so it cannot prove that a transaction is missing on-chain. `event-index` uses ABI declarations and does not calculate topic hashes. Solidity defines event ABI fields in its [ABI specification](https://docs.soliditylang.org/en/latest/abi-spec.html).

`abi_guard.py` is a separate CI-friendly script. It flags removed ABI entries, changed function outputs, and changed event indexing as breaking; additions and mutability changes are reported for review. It does not inspect storage layout, bytecode, proxy safety, or contract behavior.

## Tests and exit codes

```sh
python3 -m unittest -v
```

Exit code `0` means a report was produced without validation findings, `1` means `address-book` or `supply-check` found issues, and `2` means invalid input. All commands use the Python standard library.

## License

MIT; see [LICENSE](LICENSE).

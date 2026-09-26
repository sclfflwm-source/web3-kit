#!/usr/bin/env python3
"""Six offline reports for EVM development data."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path


ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}\Z")


def rows(path: Path, required: set[str]) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"{path}: missing columns {sorted(required - set(reader.fieldnames or []))}")
        result = list(reader)
        if any(None in row or any(value is None for value in row.values()) for row in result):
            raise ValueError(f"{path}: inconsistent CSV row")
        return result


def number(value: str, line: int, label: str) -> Decimal:
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"line {line}: invalid {label}") from exc
    if not result.is_finite() or result < 0:
        raise ValueError(f"line {line}: {label} must be finite and nonnegative")
    return result


def gas_ledger(path: Path) -> dict[str, str]:
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for line, row in enumerate(rows(path, {"date", "gas_used", "gas_price_gwei"}), 2):
        month = date.fromisoformat(row["date"]).strftime("%Y-%m")
        gas = number(row["gas_used"], line, "gas_used")
        price = number(row["gas_price_gwei"], line, "gas_price_gwei")
        totals[month] += gas * price / Decimal(10**9)
    return {key: str(totals[key]) for key in sorted(totals)}


def nonce_gaps(path: Path) -> dict[str, dict[str, list[int]]]:
    groups: dict[str, list[int]] = defaultdict(list)
    for line, row in enumerate(rows(path, {"chain_id", "address", "nonce"}), 2):
        if not ADDRESS.fullmatch(row["address"]):
            raise ValueError(f"line {line}: invalid EVM address")
        try:
            nonce = int(row["nonce"])
        except ValueError as exc:
            raise ValueError(f"line {line}: invalid nonce") from exc
        if nonce < 0:
            raise ValueError(f"line {line}: nonce must be nonnegative")
        groups[f"{row['chain_id']}:{row['address'].lower()}"].append(nonce)
    result = {}
    for key, values in sorted(groups.items()):
        observed = set(values)
        result[key] = {"missing_between_observed": [n for n in range(min(values), max(values) + 1)
                                                    if n not in observed],
                       "duplicates": sorted({n for n in values if values.count(n) > 1})}
    return result


def supply_check(path: Path, cap: Decimal) -> dict:
    cumulative = Decimal(0)
    over = []
    for line, row in enumerate(sorted(rows(path, {"date", "amount"}), key=lambda item: item["date"]), 2):
        event_date = date.fromisoformat(row["date"])
        cumulative += number(row["amount"], line, "amount")
        if cumulative > cap:
            over.append({"date": event_date.isoformat(), "cumulative": str(cumulative)})
    return {"cap": str(cap), "scheduled": str(cumulative), "over_cap_events": over}


def event_index(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("abi")
    if not isinstance(data, list):
        raise ValueError("expected ABI array or artifact with abi array")
    result = []
    for entry in data:
        if entry.get("type") != "event":
            continue
        params = entry.get("inputs", [])
        signature = entry["name"] + "(" + ",".join(param["type"] for param in params) + ")"
        result.append({"signature": signature, "indexed": [param.get("name", "") for param in params
                                                        if param.get("indexed", False)],
                       "anonymous": bool(entry.get("anonymous", False))})
    return sorted(result, key=lambda item: item["signature"])


def address_book(path: Path) -> list[str]:
    seen = set()
    issues = []
    for line, row in enumerate(rows(path, {"chain_id", "address", "label"}), 2):
        if not ADDRESS.fullmatch(row["address"]):
            issues.append(f"line {line}: invalid address syntax")
            continue
        key = (row["chain_id"], row["address"].lower())
        if key in seen:
            issues.append(f"line {line}: duplicate address on chain {row['chain_id']}")
        seen.add(key)
    return issues


def netflow(path: Path) -> dict[str, str]:
    balances: dict[str, Decimal] = defaultdict(Decimal)
    for line, row in enumerate(rows(path, {"token", "direction", "amount"}), 2):
        if row["direction"] not in {"in", "out"}:
            raise ValueError(f"line {line}: direction must be in or out")
        amount = number(row["amount"], line, "amount")
        balances[row["token"]] += amount if row["direction"] == "in" else -amount
    return {token: str(balances[token]) for token in sorted(balances)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("gas-ledger", "nonce-gaps", "event-index", "address-book", "netflow"):
        commands.add_parser(name).add_argument("path", type=Path)
    supply = commands.add_parser("supply-check")
    supply.add_argument("path", type=Path)
    supply.add_argument("--cap", type=Decimal, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "gas-ledger":
            result = gas_ledger(args.path)
        elif args.command == "nonce-gaps":
            result = nonce_gaps(args.path)
        elif args.command == "supply-check":
            if not args.cap.is_finite() or args.cap < 0:
                raise ValueError("cap must be finite and nonnegative")
            result = supply_check(args.path, args.cap)
        elif args.command == "event-index":
            result = event_index(args.path)
        elif args.command == "address-book":
            result = address_book(args.path)
        else:
            result = netflow(args.path)
    except (OSError, UnicodeError, ValueError, InvalidOperation, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return int(bool(result) if args.command == "address-book" else
               bool(result["over_cap_events"]) if args.command == "supply-check" else False)


if __name__ == "__main__":
    raise SystemExit(main())

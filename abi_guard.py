#!/usr/bin/env python3
"""Compare two Solidity JSON ABIs and report interface changes."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ALIASES = {"uint": "uint256", "int": "int256", "fixed": "fixed128x18", "ufixed": "ufixed128x18"}
TUPLE = re.compile(r"^tuple((?:\[[0-9]*\])*)$")
KINDS = {"function", "event", "error", "constructor", "fallback", "receive"}


def canonical_type(parameter: dict) -> str:
    if not isinstance(parameter, dict):
        raise ValueError("parameter must be an object")
    value = parameter.get("type")
    if not isinstance(value, str) or not value:
        raise ValueError("parameter has no type")
    match = TUPLE.fullmatch(value)
    if match:
        components = parameter.get("components")
        if not isinstance(components, list):
            raise ValueError("tuple parameter has no components")
        return "(" + ",".join(canonical_type(item) for item in components) + ")" + match.group(1)
    base, *suffix = re.split(r"(?=\[)", value, maxsplit=1)
    return ALIASES.get(base, base) + (suffix[0] if suffix else "")


def types(parameters: object) -> tuple[str, ...]:
    if not isinstance(parameters, list) or not all(isinstance(item, dict) for item in parameters):
        raise ValueError("inputs or outputs must be a list of objects")
    return tuple(canonical_type(item) for item in parameters)


def load_abi(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path}: cannot read JSON: {exc}") from exc
    if isinstance(data, dict):
        data = data.get("abi")
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise ValueError(f"{path}: expected an ABI array or an artifact with an abi array")
    return data


def indexed_flags(entry: dict) -> tuple[bool, ...]:
    return tuple(bool(item.get("indexed", False)) for item in entry.get("inputs", []))


def describe(entry: dict) -> tuple[tuple[str, str], dict]:
    kind = entry.get("type", "function")
    if not isinstance(kind, str) or kind not in KINDS:
        raise ValueError(f"unsupported ABI entry type: {kind!r}")
    name = entry.get("name", "")
    if kind in {"function", "event", "error"} and (not isinstance(name, str) or not name):
        raise ValueError(f"{kind} has no name")
    inputs = types(entry.get("inputs", []))
    signature = f"{name}({','.join(inputs)})" if name else kind
    properties: dict[str, object] = {}
    if kind == "function":
        properties["outputs"] = types(entry.get("outputs", []))
        properties["stateMutability"] = entry.get("stateMutability", "nonpayable")
    elif kind == "event":
        properties["indexed"] = indexed_flags(entry)
        properties["anonymous"] = bool(entry.get("anonymous", False))
    elif kind in {"constructor", "fallback", "receive"}:
        properties["stateMutability"] = entry.get("stateMutability", "nonpayable")
        if kind == "constructor":
            signature = f"constructor({','.join(inputs)})"
    return (kind, signature), properties


def index(abi: list[dict]) -> dict[tuple[str, str], dict]:
    result = {}
    for entry in abi:
        key, properties = describe(entry)
        if key in result and result[key] != properties:
            raise ValueError(f"conflicting duplicate ABI entry: {key[0]} {key[1]}")
        result[key] = properties
    return result


def compare(old: list[dict], new: list[dict]) -> list[dict[str, str]]:
    before, after = index(old), index(new)
    changes = []
    for kind, signature in sorted(before.keys() - after.keys()):
        changes.append({"severity": "breaking", "kind": kind, "signature": signature,
                        "change": "removed"})
    for kind, signature in sorted(after.keys() - before.keys()):
        changes.append({"severity": "review", "kind": kind, "signature": signature,
                        "change": "added"})
    for kind, signature in sorted(before.keys() & after.keys()):
        for property_name in sorted(before[(kind, signature)].keys() | after[(kind, signature)].keys()):
            previous = before[(kind, signature)].get(property_name)
            current = after[(kind, signature)].get(property_name)
            if previous != current:
                severity = "breaking" if property_name in {"outputs", "indexed", "anonymous"} else "review"
                changes.append({"severity": severity, "kind": kind, "signature": signature,
                                "change": f"{property_name}: {previous} -> {current}"})
    return changes


def render_markdown(changes: list[dict[str, str]]) -> str:
    lines = ["# ABI change report", "", f"{len(changes)} change(s) found.", ""]
    if changes:
        lines.extend(["| Severity | Kind | Signature | Change |", "| --- | --- | --- | --- |"])
        for item in changes:
            safe = [str(item[key]).replace("|", "\\|") for key in ("severity", "kind", "signature", "change")]
            lines.append("| " + " | ".join(safe) + " |")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("old", type=Path, help="baseline ABI JSON or compiler artifact")
    parser.add_argument("new", type=Path, help="candidate ABI JSON or compiler artifact")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--fail-on", choices=("breaking", "any"), default="breaking")
    args = parser.parse_args(argv)
    try:
        changes = compare(load_abi(args.old), load_abi(args.new))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(changes, indent=2) if args.format == "json" else render_markdown(changes))
    return int(any(item["severity"] == "breaking" for item in changes)
               if args.fail_on == "breaking" else bool(changes))


if __name__ == "__main__":
    raise SystemExit(main())

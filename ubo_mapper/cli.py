"""Command line entry point: python -m ubo_mapper 00445790 --depth 4"""
from __future__ import annotations

import argparse
import os
import sys

from .analysis import build_ownership
from .client import CompaniesHouseClient, CompaniesHouseError
from .demo import DemoProvider
from .report import to_json, to_markdown


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="OwnnTrak by OSH Ventures: trace company ownership using public Companies House data.")
    parser.add_argument("company_number", help="Companies House number, or DEMO0001 / DEMO0010 with --demo")
    parser.add_argument("--depth", type=int, default=5, help="ownership levels to follow (default 5)")
    parser.add_argument("--include-ceased", action="store_true", help="also show ceased PSCs")
    parser.add_argument("--demo", action="store_true", help="use the built in fictional data, no API key needed")
    parser.add_argument("--format", choices=["md", "json"], default="md")
    args = parser.parse_args(argv)

    if args.demo:
        provider, source = DemoProvider(), "Fictional demo data"
    else:
        key = os.environ.get("COMPANIES_HOUSE_API_KEY")
        if not key:
            print("Set COMPANIES_HOUSE_API_KEY first, or use --demo.", file=sys.stderr)
            return 2
        provider, source = CompaniesHouseClient(key), "Companies House API"

    try:
        result = build_ownership(
            provider, args.company_number, max_depth=args.depth,
            include_ceased=args.include_ceased, source=source,
        )
    except CompaniesHouseError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(to_json(result) if args.format == "json" else to_markdown(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())

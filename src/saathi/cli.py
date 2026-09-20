"""Terminal interface. `python -m saathi.cli` (chat) or `--demo` (no LLM needed)."""
from __future__ import annotations

import argparse
import json

from .engine import Profile, find_schemes

DEMO = {"age": 34, "gender": "female", "occupation": "farmer", "owns_land": True,
        "is_bpl": True, "has_bank_account": True, "annual_family_income": 120000}


def main() -> None:
    ap = argparse.ArgumentParser(description="Sarkari Saathi")
    ap.add_argument("--demo", action="store_true", help="run a sample profile through the rules engine (no LLM)")
    args = ap.parse_args()
    if args.demo:
        print(json.dumps(find_schemes(Profile.from_dict(DEMO)), indent=2, ensure_ascii=False))
        return

    from .agent import build_agent

    agent = build_agent()
    print("Sarkari Saathi - tell me about yourself (Ctrl+C to quit).")
    try:
        while True:
            text = input("\nYou: ").strip()
            if text:
                print(f"\nSaathi: {agent(text)}")
    except (KeyboardInterrupt, EOFError):
        print("\nBye!")


if __name__ == "__main__":
    main()

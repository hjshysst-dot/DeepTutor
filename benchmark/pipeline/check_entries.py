#!/usr/bin/env python3
"""
Check entry health across all KBs in the bench_pipeline output.

Usage:
    python3 -m benchmark.pipeline.check_entries
    python3 -m benchmark.pipeline.check_entries --output-root benchmark/data/bench_pipeline
    python3 -m benchmark.pipeline.check_entries --kb-names kb1,kb2
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = _THIS_FILE.parents[2]

DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "benchmark" / "data" / "bench_pipeline"

ANSI_GREEN = "\033[92m"
ANSI_YELLOW = "\033[93m"
ANSI_RED = "\033[91m"
ANSI_DIM = "\033[2m"
ANSI_BOLD = "\033[1m"
ANSI_RESET = "\033[0m"


def _count_jsonl(path: Path) -> int:
    count = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                count += 1
    return count


def _check_entry_quality(entry: dict) -> list[str]:
    """Return list of warnings for a single entry."""
    warnings = []
    if not entry.get("gaps"):
        warnings.append("no gaps")
    if not entry.get("task"):
        warnings.append("no task")
    task = entry.get("task", {})
    if not task.get("target_gaps"):
        warnings.append("task has no target_gaps")
    if not task.get("title") and not task.get("description"):
        warnings.append("task has no title/description")
    profile = entry.get("profile", {})
    if not profile.get("profile_id"):
        warnings.append("no profile_id in entry")
    return warnings


def main() -> None:
    parser = argparse.ArgumentParser(description="Check entry health")
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help=f"Pipeline output root (default: {DEFAULT_OUTPUT_ROOT})",
    )
    parser.add_argument(
        "--kb-names",
        default=None,
        help="Comma-separated KB names to check (default: all)",
    )
    args = parser.parse_args()

    output_root = Path(args.output_root)
    if not output_root.is_absolute():
        output_root = (PROJECT_ROOT / output_root).resolve()
    entries_root = output_root / "entries"

    if not entries_root.exists():
        print(f"{ANSI_RED}Entries root not found: {entries_root}{ANSI_RESET}")
        sys.exit(1)

    if args.kb_names:
        kb_names = sorted(set(n.strip() for n in args.kb_names.split(",") if n.strip()))
    else:
        kb_names = sorted(
            d.name
            for d in entries_root.iterdir()
            if d.is_dir()
        )

    if not kb_names:
        print(f"{ANSI_RED}No KBs found in {entries_root}{ANSI_RESET}")
        sys.exit(1)

    total_kbs = len(kb_names)
    total_profiles = 0
    total_entries = 0
    total_warnings = 0

    ok_profiles: list[str] = []
    warn_profiles: list[str] = []
    empty_profiles: list[str] = []
    missing_profiles: list[str] = []

    print(f"\n{ANSI_BOLD}Entry Health Check{ANSI_RESET}")
    print(f"Root: {entries_root}")
    print(f"KBs:  {total_kbs}\n")
    print("=" * 80)

    for kb_name in kb_names:
        kb_dir = entries_root / kb_name
        if not kb_dir.exists():
            print(f"\n{ANSI_RED}✗ {kb_name}{ANSI_RESET}  — directory not found")
            continue

        scope_path = kb_dir / "knowledge_scope.json"
        profiles_path = kb_dir / "profiles.json"
        has_scope = scope_path.exists()
        has_profiles_json = profiles_path.exists()

        scope_info = ""
        if has_scope:
            try:
                with open(scope_path, encoding="utf-8") as f:
                    scope = json.load(f)
                topic = scope.get("topic", scope.get("title", "?"))
                n_concepts = len(scope.get("concepts", []))
                scope_info = f"  scope: {topic} ({n_concepts} concepts)"
            except Exception:
                scope_info = f"  {ANSI_YELLOW}scope: parse error{ANSI_RESET}"

        profiles_root = kb_dir / "profiles"
        if not profiles_root.exists():
            print(f"\n{ANSI_RED}✗ {kb_name}{ANSI_RESET}  — no profiles/ directory")
            if scope_info:
                print(f"  {ANSI_DIM}{scope_info}{ANSI_RESET}")
            print(f"  {ANSI_DIM}knowledge_scope.json: {'✓' if has_scope else '✗'}{ANSI_RESET}")
            print(f"  {ANSI_DIM}profiles.json: {'✓' if has_profiles_json else '✗'}{ANSI_RESET}")
            continue

        profile_dirs = sorted(p for p in profiles_root.iterdir() if p.is_dir())
        kb_entries_count = 0
        kb_profile_details: list[str] = []

        for profile_dir in profile_dirs:
            total_profiles += 1
            profile_id = profile_dir.name
            full_id = f"{kb_name}/{profile_id}"
            entries_jsonl = profile_dir / "entries.jsonl"
            profile_json = profile_dir / "profile.json"

            if not entries_jsonl.exists():
                missing_profiles.append(full_id)
                kb_profile_details.append(
                    f"    {ANSI_RED}✗{ANSI_RESET} {profile_id}  "
                    f"{ANSI_RED}entries.jsonl missing{ANSI_RESET}"
                )
                continue

            n_entries = _count_jsonl(entries_jsonl)
            if n_entries == 0:
                empty_profiles.append(full_id)
                kb_profile_details.append(
                    f"    {ANSI_RED}✗{ANSI_RESET} {profile_id}  "
                    f"{ANSI_RED}0 entries{ANSI_RESET}"
                )
                continue

            entry_warnings: list[str] = []
            try:
                with open(entries_jsonl, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        entry = json.loads(line)
                        ws = _check_entry_quality(entry)
                        entry_warnings.extend(
                            f"{entry.get('entry_id', '?')}: {w}" for w in ws
                        )
            except Exception as e:
                entry_warnings.append(f"parse error: {e}")

            total_entries += n_entries
            kb_entries_count += n_entries

            has_profile_json = profile_json.exists()

            if entry_warnings:
                total_warnings += len(entry_warnings)
                warn_profiles.append(full_id)
                icon = f"{ANSI_YELLOW}⚠{ANSI_RESET}"
                detail = (
                    f"    {icon} {profile_id}  "
                    f"{n_entries} entries  "
                    f"{ANSI_YELLOW}{len(entry_warnings)} warnings{ANSI_RESET}  "
                    f"profile.json:{'✓' if has_profile_json else '✗'}"
                )
                kb_profile_details.append(detail)
                for w in entry_warnings[:5]:
                    kb_profile_details.append(f"      {ANSI_DIM}└ {w}{ANSI_RESET}")
                if len(entry_warnings) > 5:
                    kb_profile_details.append(
                        f"      {ANSI_DIM}└ ...and {len(entry_warnings) - 5} more{ANSI_RESET}"
                    )
            else:
                ok_profiles.append(full_id)
                detail = (
                    f"    {ANSI_GREEN}✓{ANSI_RESET} {profile_id}  "
                    f"{n_entries} entries  "
                    f"profile.json:{'✓' if has_profile_json else '✗'}"
                )
                kb_profile_details.append(detail)

        status_icon = ANSI_GREEN + "✓" + ANSI_RESET
        if any(full.startswith(kb_name + "/") for full in empty_profiles + missing_profiles):
            status_icon = ANSI_RED + "✗" + ANSI_RESET
        elif any(full.startswith(kb_name + "/") for full in warn_profiles):
            status_icon = ANSI_YELLOW + "⚠" + ANSI_RESET

        print(
            f"\n{status_icon} {ANSI_BOLD}{kb_name}{ANSI_RESET}  "
            f"{len(profile_dirs)} profiles  {kb_entries_count} entries"
        )
        if scope_info:
            print(f"  {ANSI_DIM}{scope_info}{ANSI_RESET}")
        for line in kb_profile_details:
            print(line)

    # Summary
    print("\n" + "=" * 80)
    print(f"\n{ANSI_BOLD}Summary{ANSI_RESET}")
    print(f"  KBs:       {total_kbs}")
    print(f"  Profiles:  {total_profiles}")
    print(f"  Entries:   {total_entries}")
    print(f"  Warnings:  {total_warnings}")

    print(f"\n  {ANSI_GREEN}OK{ANSI_RESET}:      {len(ok_profiles)}")
    if ok_profiles:
        for p in ok_profiles:
            print(f"    {ANSI_DIM}{p}{ANSI_RESET}")

    print(f"  {ANSI_YELLOW}WARN{ANSI_RESET}:    {len(warn_profiles)}")
    if warn_profiles:
        for p in warn_profiles:
            print(f"    {ANSI_DIM}{p}{ANSI_RESET}")

    print(f"  {ANSI_RED}EMPTY{ANSI_RESET}:   {len(empty_profiles)}")
    if empty_profiles:
        for p in empty_profiles:
            print(f"    {ANSI_DIM}{p}{ANSI_RESET}")

    print(f"  {ANSI_RED}MISSING{ANSI_RESET}: {len(missing_profiles)}")
    if missing_profiles:
        for p in missing_profiles:
            print(f"    {ANSI_DIM}{p}{ANSI_RESET}")

    print()

    if empty_profiles or missing_profiles:
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# Reconciliation script for ARIA credential state
# W1.5.B - Aligns providers_state.enc.yaml key IDs with api-keys.enc.yaml
#
# Usage:
#   python scripts/reconcile_state.py --dry-run  # Preview changes
#   python scripts/reconcile_state.py             # Apply changes
#
# This script is idempotent and safe to re-run.
#
# Per Context7 SOPS docs, we use `sops set` to modify individual values
# in already-encrypted files: sops set <file> <jsonpath> <value>

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aria.config import get_config
from aria.credentials.sops import SopsAdapter


def load_key_ids(sops: SopsAdapter, api_keys_path: Path) -> dict[str, list[str]]:
    """Load all key IDs from api-keys.enc.yaml (source of truth)."""
    if not api_keys_path.exists():
        return {}

    try:
        data = sops.decrypt(api_keys_path)
    except Exception as e:
        print(f"ERROR: Failed to decrypt {api_keys_path}: {e}")
        return {}

    provider_key_ids: dict[str, list[str]] = {}

    # Handle both legacy list format and canonical format
    providers = data.get("providers", {}) or {}
    for provider, config in providers.items():
        if provider == "version" or not isinstance(config, dict):
            # Legacy list format: providers.tavily = [{id, key, ...}, ...]
            if isinstance(config, list):
                key_ids = []
                for item in config:
                    if isinstance(item, dict):
                        key_id = item.get("id") or item.get("key_id")
                        if key_id:
                            key_ids.append(str(key_id))
                if key_ids:
                    provider_key_ids[provider] = key_ids
            continue

        # Canonical format: providers.tavily = {keys: [{key_id, ...}, ...]}
        keys_list = config.get("keys", [])
        if isinstance(keys_list, list):
            key_ids = []
            for item in keys_list:
                if isinstance(item, dict):
                    key_id = item.get("key_id") or item.get("id")
                    if key_id:
                        key_ids.append(str(key_id))
            if key_ids:
                provider_key_ids[provider] = key_ids

    return provider_key_ids


def load_runtime_state(sops: SopsAdapter, state_path: Path) -> dict | None:
    """Load current runtime state."""
    if not state_path.exists():
        return None

    try:
        return sops.decrypt(state_path)
    except Exception as e:
        print(f"ERROR: Failed to decrypt {state_path}: {e}")
        return None


def reconcile(
    sops: SopsAdapter,
    state_path: Path,
    api_keys_source: dict[str, list[str]],
    dry_run: bool = False,
) -> dict[str, list[str]]:
    """Reconcile providers_state with api-keys source of truth.

    Returns dict of changes made: {provider: [list of key_id changes]}
    """
    changes: dict[str, list[str]] = {}
    state = load_runtime_state(sops, state_path)

    if state is None:
        print("ERROR: Could not load runtime state")
        return changes

    providers = state.get("providers", {})
    for provider, provider_config in providers.items():
        if not isinstance(provider_config, dict):
            continue

        # Get current key IDs in runtime state
        current_keys = provider_config.get("keys", [])
        if isinstance(current_keys, list):
            current_keys = {
                str(k.get("key_id") or k.get("id") or ""): k
                for k in current_keys
                if isinstance(k, dict) and (k.get("key_id") or k.get("id"))
            }

        if not current_keys:
            continue

        # Get expected key IDs from source of truth
        expected_key_ids = api_keys_source.get(provider, [])

        # Check for placeholder/missing keys
        found_issues = []

        for key_id in current_keys.keys():
            # Check if key_id exists in source of truth
            if key_id not in expected_key_ids:
                found_issues.append(key_id)

        if found_issues:
            changes[provider] = found_issues
            if dry_run:
                print(f"  [DRY-RUN] Would fix keys in '{provider}': {found_issues}")
                print(f"           Expected key IDs: {expected_key_ids}")
            else:
                print(f"  [APPLY] Fixing keys in '{provider}': {found_issues}")

    return changes


def apply_fixes(
    state_path: Path,
    api_keys_source: dict[str, list[str]],
    changes: dict[str, list[str]],
    age_key_file: Path,
) -> bool:
    """Apply fixes using sops set command for proper in-place re-encryption.

    Per Context7 SOPS docs:
    - `sops set <file> '<jsonpath>' '<value>'` modifies encrypted files
    - Works with already-encrypted files without needing to re-encrypt the whole file
    """
    # Find sops binary - prefer explicit path, fallback to which
    sops_cmd = shutil.which("sops") or "/home/fulvio/.local/bin/sops"
    env = {"SOPS_AGE_KEY_FILE": str(age_key_file)}

    for provider, issue_keys in changes.items():
        expected_key_ids = api_keys_source.get(provider, [])
        if not expected_key_ids:
            continue

        # Get current keys from the state to know the mapping
        state = load_runtime_state(SopsAdapter(age_key_file), state_path)
        if state is None:
            print(f"  ERROR: Could not load state for {provider}")
            continue

        provider_config = state.get("providers", {}).get(provider, {})
        current_keys = provider_config.get("keys", [])

        if not isinstance(current_keys, list):
            current_keys = []
            for k, v in provider_config.get("keys", {}).items():
                v["key_id"] = k
                current_keys.append(v)

        # Update each key_id
        for i, expected_key_id in enumerate(expected_key_ids):
            if i < len(current_keys):
                # Build the JSON path for this key
                jsonpath = f'["providers"]["{provider}"]["keys"][{i}]["key_id"]'
                value = f'"{expected_key_id}"'

                result = subprocess.run(
                    [sops_cmd, "set", str(state_path), jsonpath, value],
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=30,
                )
                if result.returncode != 0:
                    print(f"  ERROR: sops set failed for {provider}[{i}]: {result.stderr}")
                    return False

                print(f"    Updated {provider} key[{i}] -> {expected_key_id}")

    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reconcile ARIA credential runtime state with api-keys source of truth"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("ARIA Credential State Reconciliation Tool")
    print("=" * 60)
    print()

    # Load config
    config = get_config()

    # Initialize SOPS adapter
    sops = SopsAdapter(config.sops.age_key_file)

    # Paths
    api_keys_path = config.paths.credentials / "secrets" / "api-keys.enc.yaml"
    state_path = config.paths.runtime / "credentials" / "providers_state.enc.yaml"

    print(f"API keys source: {api_keys_path}")
    print(f"Runtime state:    {state_path}")
    print()

    # Load source of truth
    print("Loading key IDs from api-keys.enc.yaml...")
    api_keys_source = load_key_ids(sops, api_keys_path)
    for provider, key_ids in api_keys_source.items():
        print(f"  {provider}: {len(key_ids)} keys")
        for kid in key_ids:
            print(f"    - {kid}")
    print()

    if not api_keys_source:
        print("ERROR: No keys found in api-keys.enc.yaml")
        return 1

    # Reconcile
    print("Checking runtime state...")
    changes = reconcile(sops, state_path, api_keys_source, dry_run=args.dry_run)

    if not changes:
        print("No discrepancies found. State is aligned.")
        return 0

    if args.dry_run:
        print()
        print(f"Found {len(changes)} provider(s) with discrepancies.")
        print("Run without --dry-run to apply fixes.")
        return 0

    # Apply changes
    print()
    print("Applying fixes to runtime state via sops set...")

    if not apply_fixes(state_path, api_keys_source, changes, config.sops.age_key_file):
        print("ERROR: Failed to apply fixes")
        return 1

    print()
    print("Reconciliation complete.")
    print()
    print("IMPORTANT: If the scheduler or gateway services are running,")
    print("restart them to pick up the new credential state:")
    print("  systemctl --user restart aria-scheduler.service aria-gateway.service")

    return 0


if __name__ == "__main__":
    sys.exit(main())

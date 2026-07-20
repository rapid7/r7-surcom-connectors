#!/usr/bin/env python3

"""Build refdocs JSON files from source OpenAPI YAML files.

This script normalizes source OpenAPI YAML documents by recursively:
- removing all "additionalProperties" keys
- rewriting "oneOf" to "anyOf"

It then writes JSON versions with matching basenames.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


def normalize_openapi_tree(node: Any) -> Any:
    """Normalize a JSON-like OpenAPI tree for connector use.

    - Remove all "additionalProperties" keys.
    - Rewrite "oneOf" keys to "anyOf" (or merge into existing "anyOf").
    """
    if isinstance(node, dict):
        node.pop("additionalProperties", None)

        # Convert oneOf -> anyOf without dropping alternatives.
        # Coerce both sides to lists so scalar/object forms are preserved too.
        if "oneOf" in node:
            one_of_value = node.pop("oneOf")
            any_of_list = node.get("anyOf", [])
            if not isinstance(any_of_list, list):
                any_of_list = [any_of_list]

            if isinstance(one_of_value, list):
                any_of_list.extend(one_of_value)
            else:
                any_of_list.append(one_of_value)

            node["anyOf"] = any_of_list

        for value in node.values():
            normalize_openapi_tree(value)
        return node

    if isinstance(node, list):
        for item in node:
            normalize_openapi_tree(item)

    return node


def main() -> None:
    # Resolve script directory so this works from any current working directory.
    script_dir = Path(__file__).resolve().parent

    source_files = [
        "swagger-clustermgmt-v4.1-all.yaml",
        "swagger-networking-v4.1-all.yaml",
        "swagger-vmm-v4.1-all.yaml",
    ]

    for source_name in source_files:
        source_path = script_dir / source_name
        target_path = source_path.with_suffix(".json")

        with source_path.open("r", encoding="utf-8") as source_file:
            document = yaml.safe_load(source_file)

        # Mutate in place to keep memory use lower for large specs.
        normalize_openapi_tree(document)

        with target_path.open("w", encoding="utf-8") as target_file:
            json.dump(document, target_file, indent=2)
            target_file.write("\n")

        print(f"Wrote {target_path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Script to extract only the required endpoints from the Nautobot OpenAPI spec.
This creates a smaller openapi file that fits within the 4MB limit.
"""

import json
import re

# Required endpoints based on fn_import_all.py ENDPOINT_TYPES and helper endpoints
REQUIRED_PATHS = [
    # Main import types
    "/cloud/cloud-accounts/",
    "/cloud/cloud-services/",
    "/virtualization/clusters/",
    "/dcim/locations/",
    "/ipam/ip-addresses/",
    "/ipam/prefixes/",
    "/tenancy/tenants/",
    "/virtualization/virtual-machines/",
    "/ipam/vlans/",
    "/dcim/controller-managed-device-groups/",
    "/dcim/software-versions/",
    "/extras/tags/",
    "/dcim/devices/",
    # Helper endpoints (used for lookups)
    "/dcim/device-types/",
    "/dcim/manufacturers/",
    "/extras/statuses/",
    "/dcim/platforms/",
    "/dcim/racks/",
]


def find_schema_refs(obj, refs=None):
    """Recursively find all $ref references to schemas in an object."""
    if refs is None:
        refs = set()

    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "$ref" and isinstance(value, str):
                # Extract schema name from #/components/schemas/SchemaName
                match = re.match(r"#/components/schemas/(.+)", value)
                if match:
                    refs.add(match.group(1))
            else:
                find_schema_refs(value, refs)
    elif isinstance(obj, list):
        for item in obj:
            find_schema_refs(item, refs)

    return refs


def resolve_schema_dependencies(schemas, schema_names):
    """Recursively resolve all schema dependencies."""
    all_schemas = set(schema_names)
    to_process = list(schema_names)

    while to_process:
        schema_name = to_process.pop()
        if schema_name in schemas:
            refs = find_schema_refs(schemas[schema_name])
            for ref in refs:
                if ref not in all_schemas and ref in schemas:
                    all_schemas.add(ref)
                    to_process.append(ref)

    return all_schemas


def extract_openapi(input_file, output_file):
    """Extract only required paths and their schemas from the OpenAPI spec."""
    print(f"Loading {input_file}...")
    with open(input_file, 'r') as f:
        spec = json.load(f)

    # Filter paths to only include required ones
    filtered_paths = {}
    for path, path_item in spec.get("paths", {}).items():
        # Include exact matches or paths with {id} suffix
        base_path = path.rstrip("/").rsplit("/{id}", 1)[0] + "/"
        if path in REQUIRED_PATHS or base_path in REQUIRED_PATHS:
            # Only include GET operations (list and retrieve)
            filtered_item = {}
            if "get" in path_item:
                filtered_item["get"] = path_item["get"]
            if filtered_item:
                filtered_paths[path] = filtered_item

    print(f"Filtered to {len(filtered_paths)} paths from {len(spec.get('paths', {}))} total")

    # Find all schema references in the filtered paths
    schema_refs = find_schema_refs(filtered_paths)
    print(f"Found {len(schema_refs)} direct schema references")

    # Resolve all schema dependencies
    all_schemas = spec.get("components", {}).get("schemas", {})
    required_schemas = resolve_schema_dependencies(all_schemas, schema_refs)
    print(f"Total schemas needed (including dependencies): {len(required_schemas)}")

    # Build the filtered spec, removing "required" field from schemas
    filtered_schemas = {}
    for name, schema in all_schemas.items():
        if name in required_schemas:
            schema_copy = dict(schema)
            schema_copy.pop("required", None)
            filtered_schemas[name] = schema_copy

    filtered_spec = {
        "openapi": spec.get("openapi", "3.0.3"),
        "info": spec.get("info", {}),
        "paths": filtered_paths,
        "components": {
            "schemas": filtered_schemas
        }
    }

    # Copy security schemes if present
    if "securitySchemes" in spec.get("components", {}):
        filtered_spec["components"]["securitySchemes"] = spec["components"]["securitySchemes"]

    # Add servers if present
    if "servers" in spec:
        filtered_spec["servers"] = spec["servers"]

    # Write the filtered spec
    print(f"Writing {output_file}...")
    with open(output_file, 'w') as f:
        json.dump(filtered_spec, f, indent=2)

    # Report file sizes
    import os
    input_size = os.path.getsize(input_file)
    output_size = os.path.getsize(output_file)
    print(f"Original size: {input_size:,} bytes ({input_size/1024/1024:.2f} MB)")
    print(f"Filtered size: {output_size:,} bytes ({output_size/1024/1024:.2f} MB)")
    print(f"Reduction: {(1 - output_size/input_size)*100:.1f}%")


if __name__ == "__main__":
    extract_openapi("openapi.json", "openapi_filtered.json")

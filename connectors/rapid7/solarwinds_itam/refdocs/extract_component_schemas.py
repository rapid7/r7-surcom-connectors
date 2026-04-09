"""
Extract component schemas from the SolarWinds ITAM OpenAPI spec.

The original SolarWinds Service Desk OpenAPI spec defines entity schemas inline
within endpoint responses (no components/schemas section). This script extracts
those schemas and adds them under components/schemas so they can be referenced
by Surface Command type definitions using $ref.

Usage:
    cd connectors/rapid7/solarwinds_itam
    python3 refdocs/extract_component_schemas.py
"""
import json
import copy
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(SCRIPT_DIR, 'resolved_schema.json')

with open(SCHEMA_PATH) as f:
    schema = json.load(f)

# Map: component schema name -> (API path, entity wrapper key in response)
ENTITY_MAP = {
    'User': ('/users/{id}', 'user'),
    'Group': ('/groups/{id}', 'group'),
    'Site': ('/sites/{id}', 'site'),
    'Department': ('/departments/{id}', 'department'),
    'Hardware': ('/hardwares/{id}', 'hardware'),
    'Mobile': ('/mobiles/{id}', 'mobile'),
    'Software': ('/softwares/{id}', 'software'),
}

# Extract schemas from path responses into components/schemas
components_schemas = {}

for name, (path, key) in ENTITY_MAP.items():
    path_val = schema['paths'].get(path, {})
    get_op = path_val.get('get', {})
    responses = get_op.get('responses', {})
    resp_200 = responses.get('200', {})
    content = resp_200.get('content', {})

    json_content = content.get('application/json', {})
    response_schema = json_content.get('schema', {})
    entity_schema = response_schema.get('properties', {}).get(key, {})

    if entity_schema and 'properties' in entity_schema:
        components_schemas[name] = copy.deepcopy(entity_schema)
        print(f"Extracted '{name}' from {path} -> {len(entity_schema['properties'])} properties")
    else:
        print(f"WARNING: Could not extract '{name}' from {path}")

# Add components/schemas to the spec
if 'components' not in schema:
    schema['components'] = {}
schema['components']['schemas'] = components_schemas

# Write back
with open(SCHEMA_PATH, 'w') as f:
    json.dump(schema, f, indent=2)

print(f"\nDone. Added {len(components_schemas)} schemas to components/schemas")
print("Schema names:", list(components_schemas.keys()))

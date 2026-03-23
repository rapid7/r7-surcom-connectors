# Nautobot OpenAPI Schemas

This directory contains the OpenAPI (Swagger) JSON schemas used by the Nautobot connector.

All schema files are stored in the `refdocs` directory.

## How to Update

1. From your Nautobot instance, export or download the latest OpenAPI JSON schema for the Nautobot API (for example, via the API documentation endpoint).
2. Save the full, unfiltered schema JSON into the `refdocs` directory (for example as `openapi.json`, if not already present), replacing the existing file as needed.
3. Create or update `openapi_filtered.json` by starting from the full Nautobot OpenAPI JSON and removing endpoints, components, or other sections that are not required for this connector so that the resulting file remains within the Surface Command request size limits.
4. Use your preferred OpenAPI editing tool or the `extract_openapi.py` script to generate `openapi_filtered.json`, ensuring it remains valid JSON and a valid OpenAPI document.
5. Commit the updated schema files in the `refdocs` directory to keep the Nautobot connector schemas up to date.

## Surface Command Load Support

The full Nautobot OpenAPI schema can exceed the maximum request body size supported by Surface Command (for example: `Maximum request body size 4194304 exceeded, actual body size 4265252`).

To work around this limitation, the Nautobot connector uses a reduced schema file, `openapi_filtered.json`. This file must:

- Be derived from the latest full Nautobot OpenAPI schema.
- Contain only the endpoints and definitions required by this connector.
- Remain within the Surface Command maximum request body size.

Whenever the Nautobot API schema changes, regenerate `openapi_filtered.json` from the latest full schema following the steps above, then commit the updated file.
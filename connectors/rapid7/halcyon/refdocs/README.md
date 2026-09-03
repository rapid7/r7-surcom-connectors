# Halcyon OpenAPI Schemas

This repository contains the OpenAPI 3.1.0 specification for the Halcyon APIs.

All schema files are stored in the `refdocs` directory.

### Schemas

1. **Halcyon API**
   - **URL:** [Halcyon API Docs](https://api.halcyon.ai/docs/index.html)
   - **File:** `refdocs/halcyon_openapi.json`
   - Contains definitions and endpoints for all Halcyon platform resources (assets, deployment groups, policy groups, tenants, and more).
   - **Usage on Surface Command**
        ```bash
        stype refs new halcyon https://api.halcyon.ai /refdocs/halcyon_openapi.json
        ```

## How to Update
1. Download the latest OpenAPI JSON schema from https://api.halcyon.ai/docs/index.html (click "Download OpenAPI specification").
2. Replace `refdocs/halcyon_openapi.json` with the downloaded file.
3. Commit the changes to keep the schemas up-to-date.

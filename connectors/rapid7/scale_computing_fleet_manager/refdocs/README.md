# Scale Computing Fleet Manager OpenAPI Schemas

This directory contains the OpenAPI JSON schema used by the Scale Computing Fleet Manager connector.

## Schemas

1. **Fleet Manager API**
   - **URL:** [Fleet Manager OpenAPI Specification](https://api.scalecomputing.com/api/v2/openapi.json)
   - **File:** `refdocs/openapi.json`
   - Contains the component schemas for `ClusterDto` and `VmDto` referenced by this connector.

## How to Update

1. Download the latest OpenAPI JSON schema from `https://api.scalecomputing.com/api/v2/openapi.json`.
2. Extract only the component schemas required by this connector (`ClusterDto`, `VmDto`, `UpdatesAvailableOptionDto`, `UpdateStatusDto`, `PageMetaDto`, `PageDto`, `BadRequestException`) to keep the file small.
3. Replace `refdocs/openapi.json` with the filtered schema and commit the updated file.

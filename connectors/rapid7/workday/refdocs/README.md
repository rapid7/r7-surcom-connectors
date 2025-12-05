# Workday OpenAPI Schemas

This repository contains the latest OpenAPI (Swagger) JSON schemas for Workday APIs.

All schema files are stored in the `refdocs` directory.

### Schemas

1. **Supervisory Organizations API**  
   - **URL:** [Supervisory Organizations API](https://community.workday.com/sites/default/files/file-hosting/restapi/#common/v1/supervisoryOrganizations)  
   - **File:** `refdocs/supervisory_organization_schema.json`  
   - Contains definitions and endpoints for managing supervisory organizations.
   - **Usage on Surface command**
        ```bash
        stype refs new workday https://community.workday.com/sites/default/files/file-hosting/restapi /refdocs/supervisory_organization_schema.json
        ```

## How to Update
1. Download the latest OpenAPI JSON schema from the respective Workday documentation URL.  
2. Replace the corresponding JSON file in the `refdocs` directory.  
3. Commit the changes to keep the schemas up-to-date.

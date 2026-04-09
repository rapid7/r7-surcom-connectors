### SolarWinds ITAM (Service Desk) API Reference Schema

The `resolved_schema.json` file contains the OpenAPI 3.0.1 specification for the SolarWinds Service Desk (Samanage) API.

#### API Endpoints by Region

- **US:** `https://api.samanage.com`
- **EU:** `https://apieu.samanage.com`
- **APJ:** `https://apiau.samanage.com`


#### How to Update

- The SolarWinds Service Desk API swagger is not available on the public internet.
- To update, obtain the latest OpenAPI specification from an authenticated SolarWinds ITAM instance and replace `resolved_schema.json`.
- After replacing, re-run `extract_component_schemas.py` to regenerate the `components/schemas` section.
- Note: The file is a fully resolved schema (all `$ref` entries expanded inline).

#### API Documentation

- [SolarWinds Service Desk API Documentation](https://documentation.solarwinds.com/en/success_center/)

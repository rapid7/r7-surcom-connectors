---
applyTo: "connectors/**"
---

# Copilot PR Review Instructions

These instructions define review criteria for Surface Command connector PRs. Apply them when reviewing changes to any file within a connector directory (`connectors/<tier>/<connector_name>/`).

Rules are organized by file. When reviewing a diff, apply the rules for each changed file. The "General" section applies across all files.

---

## General

### Naming and Spelling
- Product names must be capitalized **exactly as the vendor specifies**: "SolarWinds" not "Solarwinds", "AppCheck" not "Appcheck", "IPv4" not "Ipv4", "IP" not "Ip".
- Use US English spelling throughout (e.g., "organization" not "organisation").
- Type names must be PascalCased consistently (e.g., `EzoAssetSonarAsset`, not `EzoAssetsonarAsset`).
- Type names should be **singular** (e.g., `Docusnap365Account` not `Docusnap365Accounts`) because each record represents one entity.
- Fix all spelling errors in comments, docstrings, descriptions, sample data, and property titles — they are visible to users.

### Cross-File Consistency
- Type names must be identical across `connector.spec.yaml`, type YAML files (`x-samos-type-name`), `sc_types.py`, sample data filenames, and log messages.
- Setting names referenced in `docs/INSTRUCTIONS.md` must match the `title` values in `connector.spec.yaml` exactly.
- Function parameter order in Python code must match the parameter order declared in `connector.spec.yaml`.
- Generated files (`sc_types.py`, `sc_settings.py`) must be regenerated after any spec change, using `surcom connector codegen`.

---

## connector.spec.yaml

### Metadata
- `notice` must be exactly: `Copyright © 2026 Rapid7. All rights reserved.` (using the current year)
- For connectors in the `connectors/rapid7/` path: `author` must be exactly: `Rapid7`
- New connectors must append `(Beta)` to the `name` field and use version `0.1.0`
- Every PR that changes a connector must increment the version number. MAJOR versions (e.g., 1.2.0 → 2.0.0) indicate breaking changes to types or settings. MINOR versions (e.g., 1.2.0 → 1.3.0) indicate new features or bug fixes. PATCH versions must not be used — the build system applies a patch version automatically.
- Version numbers must only increment. Never downgrade a major version.
- The `current_changes` field must describe only the changes in the current PR — not the full release history. The SDK handles cumulative changelogs.
- When updating a `current_changes` entry, do not include internal-only changes (e.g., refdoc updates) that are not visible to users.

### Functions
- Import function `title` must be a **noun phrase** describing the data imported (e.g., "Darktrace Devices and Subnets"), not a verb phrase.  Recommended max 50 characters.
- Import function `description` must match the title and be clear and concise (e.g., "Import Agents from Delinea Privilege Manager").
- Import function descriptions must match what is actually implemented — do not describe capabilities that are not built.
- Import functions must be declared with signature: `def import_foo(user_log: Logger, settings: Settings)`

### Dependencies
- If a type references types from another connector (e.g., CWE types), declare the dependency in `depends-on`.

### Settings
- Setting `title` and `description` must use the **exact terminology** from the vendor's documentation (e.g., if Datto calls it "API Secret Key", use that — not "Secret" or "Password").
- Use title case for setting titles (e.g., `Server URL`, `API Key`, `Client Secret`).
- Use `example:` (singular), never `examples:` — the OpenAPI/YAML schema uses singular `example`.
- Put example values only in the `example` property — do not embed examples in the `description` field.
- Do not use `<` and `>` angle brackets in `example` values — they can break when rendered in HTML.
- Do not provide `example` values for password/secret fields.
- Secret credentials (API keys, tokens, passwords, private keys) must be marked with `format: password`.
- Non-secret identifiers (API key IDs, client IDs, app IDs, scopes) should NOT use `format: password`.
- Required settings must not be `nullable`.
- Setting descriptions must explain what value is expected, not just name the field.
- `lookback_days` defaults must be integers, not booleans.
- Verify that `enum` values cover all expected options and are sourced from the vendor's API documentation.
- If the connector includes a setting for SSL/TLS verification: it must default to `true` and use the standard title and description: `title: Verify TLS?`, `description: If enabled, verify the server's identity`.
- Order settings logically: connection URL first, then required credentials, then optional settings (verify TLS, page size, filters). Optional settings should appear after required ones so they display last in the UI.
- For published connectors, changing default values for existing settings can break installations. Add new settings with backward-compatible defaults instead.

### Categories
- At least one category must be specified.
- Categories must accurately match the product's functionality (e.g., Mimecast → `phishing`, not just `security_operations`).

The available categories are:

```json
[
  { "id": "endpoint_detection_response", "displayName": "Endpoint Detection & Response", "examples": "Cybereason, CrowdStrike Falcon, Microsoft Defender for Endpoint, SentinelOne, Carbon Black" },
  { "id": "vulnerability_management", "displayName": "Vulnerability Management", "examples": "Tenable.io, Qualys VMDR, Rapid7 InsightVM, SCADAfence, Nozomi" },
  { "id": "asset_management", "displayName": "Asset Management", "examples": "SCADAfence, LANsweeper, ServiceNow ITAM, KACE SMA, SnipeIT" },
  { "id": "external_attack_surface", "displayName": "External Attack Surface", "examples": "Microsoft Defender EASM, Shodan, SecurityScorecard, Cloudflare, Hardenize" },
  { "id": "network_firewall", "displayName": "Network & Firewall", "examples": "Infoblox NIOS, Netbox, Zscaler, Darktrace" },
  { "id": "application_development", "displayName": "Application Development & Security", "examples": "GitHub, Snyk, Semgrep, Sonarqube, Jira" },
  { "id": "database", "displayName": "Database", "examples": "Snowflake, Microsoft SQL Server, PostgreSQL, Amazon S3" },
  { "id": "security_operations", "displayName": "Security Operations", "examples": "Incydr, XSOAR, SolarWinds Orion, Nexthink, Splunk, Devo SIEM, Exabeam" },
  { "id": "endpoint_management", "displayName": "Endpoint Management", "examples": "Microsoft Intune, Jamf, Kaseya VSA, NinjaOne, baramundi" },
  { "id": "phishing", "displayName": "Phishing", "examples": "KnowBe4, Proofpoint TAP" },
  { "id": "iam", "displayName": "Identity & Access Management", "examples": "CyberArk PAM, PingOne, Entra ID, Okta, Cisco Duo" },
  { "id": "cloud_service_provider", "displayName": "Cloud Provider / Infrastructure", "examples": "AWS, Azure Compute, VMWare" },
  { "id": "cloud_security", "displayName": "Cloud Security", "examples": "Orca, Wiz, Trend CloudOne, Cisco Umbrella, Aqua CSPM" },
  { "id": "case_management", "displayName": "Case Management", "examples": "Jira, ServiceNow, Freshservice" },
  { "id": "ticketing", "displayName": "Ticketing", "examples": "Jira, ServiceNow, Freshservice, Ivanti Neurons ITSM" },
  { "id": "alerting_and_notifications", "displayName": "Alerting & Notifications" },
  { "id": "threat_intel", "displayName": "Threat Intelligence", "examples": "HaveIBeenPwned, Recorded Future, Proofpoint TAP" },
  { "id": "collaboration", "displayName": "Collaboration", "examples": "Slack, Google Drive, Microsoft Teams" }
]
```

### Types List
- All type names in `types` and `return_types` must **exactly match** the `x-samos-type-name` in the corresponding YAML files — including casing.
- Commented-out types in `types`/`return_types` must not have corresponding imports or generated classes that are still active.

---

## docs/INSTRUCTIONS.md

### Format
- Every paragraph must be indented by exactly **2 spaces** (not 4) for correct rendering in the Surface Command UI.
- Structure must follow: `# __Description__`, `# __Overview__`, `# __Documentation__` sections.
- Overview should contain two sentences: one describing the product ("X is...") and one describing the connector ("This connector...").
- Descriptions should be professional and factual — avoid marketing language.
- Use correct Markdown syntax: `##` for sections, `###` for subsections, consistent list markers (`*` or `-`), and proper image syntax `![Alt text](./docs/image.png)`. Verify all links resolve correctly.

### Content Accuracy
- INSTRUCTIONS.md must accurately describe **only the settings and data types that are actually implemented**. Do not describe features that are not yet built.
- Do not just list settings — describe the **steps to obtain** each credential (API key generation, token creation, etc.).
- Reference the vendor's documentation for credential generation with direct links.
- Specify the minimum required permissions or roles needed for API access.
- When connectors support multiple deployment modes (e.g., cloud vs. on-prem), clearly describe the configuration differences for each.
- All settings exposed in `connector.spec.yaml` must be documented — do not omit optional settings like `verify_tls`, `page_limit`, etc.

### Security
- Do not include personal email addresses or real names in screenshots or documentation.
- If the connector API requires an allowlisted IP range for access, link to the Rapid7 documentation: `https://docs.rapid7.com/surface-command/allowlist-surface-command-ips/`

---

## Python Code (functions/)

### HTTP Session Usage
- Use `HttpSession` for all HTTP requests — never use `requests.get()` or `requests.post()` directly.
- `HttpSession` provides built-in timeout and retry logic. If you must override the defaults, provide a `Retry` or timeout as parameters to its constructor — do not override per-request.
- Initialize the HTTP session **once** (typically in `__init__`), not per-request.
- Set authentication, TLS verification, and common headers once on the session object, not on every request. Use `self.session.headers.update({...})` for headers, `self.session.auth` for auth, and `self.session.verify` for TLS.
- Do not implement custom rate-limiting or retry logic — the `HttpSession` handles 429/retry automatically. Do not add redundant 429/5xx handling unless you need custom behavior.
- Use `furl` for URL construction when building query parameters, to handle encoding correctly.
- Do not set `Content-Type` manually when using `json=` parameter — it is set automatically by the requests library.

### Error Handling

**HTTP response validation:**
- Call `raise_for_status()` after every HTTP call. Do not assume all HTTP errors are authentication failures — use `raise_for_status()` rather than `if status_code != 200: raise Exception("Invalid credentials")`.
- Do not wrap `raise_for_status()` in try/except just to re-raise — this hides the stack trace and line number. Let exceptions propagate naturally.
- Call `raise_for_status()` **before** `.json()` — if the request failed, calling `.json()` on an error response may raise a different, unhelpful exception.

**JSON parsing safety:**
- Check `Content-Type` before calling `.json()` when connecting to user-provided URLs — an incorrect URL may return HTML instead of JSON. Log the actual response body (first 500 chars) when a non-JSON response is received.

**Exception handling patterns:**
- Catch specific exceptions — never catch bare `Exception`. Catch `requests.exceptions.JSONDecodeError`, `KeyError`, etc.
- When catching exceptions, re-raise them (don't swallow) — otherwise failures result in partial data with no error indication.
- Do not add speculative error handling for errors you have never observed — trust the framework's built-in handling.

**Input and parameter validation:**
- Validate required credentials with `or`, not `and`: `if not client_id or not client_secret` triggers if ANY is missing; `if not client_id and not client_secret` only triggers if ALL are missing.
- For required fields (keys, IDs), either assume they exist or raise a clear exception — don't silently skip with a None check.
- Don't include `None` values in API query parameters — many APIs will serialize `None` as the literal string "None", causing errors. Only include parameters when they have actual values.

**Import resilience:**
- During import, log and continue on non-fatal errors for individual records — do not stop an entire import because one record failed.

### Test Function
- `test_connection` must test **all endpoints** that the import function uses, not just the authentication endpoint.
- Test function must be declared with signature: `def test(user_log: Logger, **settings: Settings)` (note `**`)
- Test functions must fail correctly with wrong credentials, invalid URLs, and missing required settings.
- Do not assume API responses are non-empty (e.g., `applications[0]` will raise `IndexError` if the list is empty).
- The test function must return an error result (not success) when validation fails.
- If some optional features require additional permissions, report success with a message about limitations rather than failing entirely. But if a missing permission will cause import failure, the test must fail.
- The test function must NOT paginate — make minimal API calls to verify connectivity and permissions.

### Import Functions (Python)
- Import functions must use **generators** (yield) — do not accumulate large data structures in memory, which risks OOM errors.
- Do not build complete lists and then iterate — yield items as they are received. Do not make unnecessary intermediate copies (e.g., `list(items)` doubles memory).
- Use the `@paged_function` decorator for pagination when provided by the framework, rather than implementing manual pagination loops.
- Pagination parameters must increment correctly (e.g., `start += len(results)`, not `start += 1`).
- Page sizes should match API maximums — do not use tiny page sizes (e.g., 1 or 3) that cause excessive API calls. Use large page sizes (1000–5000) when the API supports it. Reference the vendor API docs for maximum page size.
- Deduplicate records within each page before yielding — the platform does global deduplication, but reducing duplicates early improves performance.
- Comments documenting API-specific limits (max page sizes, endpoint behaviors) should include a reference to the vendor documentation.
- Assign `response.json()` to a variable — do not call it multiple times on the same response (each call re-parses the full body).

---

## Sample Data

- Sample data files must **exactly match** the type name casing (e.g., `BeyondTrustEPMComputer.json`, not `BeyondtrustEPMComputer.json`).
- Sample data must be derived from **actual API responses** — never generated from scratch.
- Sample data must validate against the type schema — run `surcom connector validate` to verify.
- Sample data for related types must be referentially consistent — IDs referenced across types should actually match.
- Include enough records (preferably ~100 per type) and ensure they relate correctly across types so references and graph views work.
- **No real customer data — EVER**. Do not include real customer names, email addresses, employee names, hostnames, account IDs, or identifiers that could identify a specific organization.
- Use RFC-reserved safe values for anonymization:
  - Email domains: `example.com`, `example.org`, `example.net`
  - IPv4: `192.0.2.x`, `198.51.100.x`, `203.0.113.x` (RFC 5737)
  - IPv6: `2001:db8::` prefix (RFC 3849)
  - Domain names: `example.com`, `example.org` (RFC 2606)
  - Person names: clearly fictitious (`Jane Doe`, `John Smith`)
- Do not include company-internal or proprietary URLs that would be visible in the public repo.
- Watch for overcorrelation: if multiple sample records share the same serial number, MAC address, or hostname, they will merge into a single entity during import. Ensure distinct correlation key values across records.
- Do not include records where all values are placeholder strings like `"string"` — sample data should look realistic.
- Sample data must include records that exercise derived properties — if a derived property transforms data, the sample should demonstrate that transformation.
- Use `x_` prefix for Python-generated properties added to a vendor's return type. Do not use `x_` on properties in entirely custom types.

---

## build_configs.yaml

- All connectors must be listed in this file.
- Connectors must be listed in **alphabetical order**.
- Preserve the trailing comment: `# PLEASE KEEP THE LIST OF CONNECTORS IN ALPHABETICAL ORDER`.
- Do not skip or disable build validations.
- Minimize formatting changes to this file to avoid merge conflicts.

---

## Reviewer Checks

Verify that the PR author has completed these steps:
- `surcom connector validate` passes (not flake8 alone).
- All import function code paths are tested — not just the happy path.

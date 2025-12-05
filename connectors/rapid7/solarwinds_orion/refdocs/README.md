### To Copy the Latest Swagger JSON
- Go to the connector refdocs
- Run the below curl command to download the latest Swagger JSON. Please always ensure you have the latest version.
```bash
curl "https://solarwinds.github.io/OrionSDK/2024.4/swagger.json" | jq . > swagger.json
```
- Note: `refdocs/swagger.json` file 'Orion.Nodes' definition `CMTS` property type is overwritten to `json`, because to handle the Nodes response `CMTS` property value can be object or string
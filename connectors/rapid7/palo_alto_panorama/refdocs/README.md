### PAN-OS REST API OpenAPI schema

`openapi_panos_10_1.json` is the OpenAPI spec embedded in the PAN-OS REST API reference page
(`https://<firewall>/restapi-doc/`) of a PAN-OS 10.1 firewall.

To refresh it, extract the object passed to `Redoc.init(...)` on that page and save it as JSON:

```bash
curl -sk "https://firewall.example.com/restapi-doc/" | python3 -c "
import sys, json
h = sys.stdin.read()
spec, _ = json.JSONDecoder().raw_decode(h[h.index('Redoc.init(') + 11:])
json.dump(spec, open('openapi_panos_10_1.json', 'w'), indent=2)"
```

Then apply these changes, which Surface Command schema validation requires:

- Every `oneOf` is replaced with `anyOf`. The vendor `oneOf` branches (for example the `tcp` and
  `udp` branches of a service `protocol`, or the modes of a zone `network`) have no `required`
  properties, so a valid entry matches every branch and fails "valid to one and only one schema".
- `objects-address-groups` > `dynamic` > `filter` is given `"type": "string"`. The vendor schema
  has no type for it, which Surface Command treats as an object.

```bash
python3 -c "
import json
p = 'openapi_panos_10_1.json'
spec = json.load(open(p))
def fix(n):
    if isinstance(n, dict):
        if 'oneOf' in n: n['anyOf'] = n.pop('oneOf')
        [fix(v) for v in n.values()]
    elif isinstance(n, list):
        [fix(v) for v in n]
fix(spec)
spec['components']['schemas']['objects-address-groups']['properties']['dynamic']['properties']['filter']['type'] = 'string'
json.dump(spec, open(p, 'w'), indent=2)"
```

# __Description__

  Connector for Surface Command that imports Demo Device and User data

# __Overview__

  This is a demo Connector that uses a MockServer https://www.mock-server.com/ started with the surcom-sdk to get example User and Device data

  It is to be used as a reference when developing Connectors with Rapid7 Surface Command

# __Documentation__

  ## __Setup__

  The [MockServer](https://www.mock-server.com/) is started with the surcom-sdk and serves static Expectations.

  To start it, ensure the [surcom-sdk is configured](https://docs.rapid7.com/surface-command/build-custom-connectors/) and that Docker is installed and running, then run the following command:

  ```
  surcom mockserver load-tutorial
  ```

  This will load the MockServer with Expectations that return example User and Device data.

  The endpoints that this Connector uses are:

  * `/api/permissions` - returns Permission data
  * `/api/users` - returns User data
  * `/api/devices` - returns Device data

  ### The Base URL

  The MockServer is started in a Docker container on port 1080, so the base `URL` for this Connector is `http://host.docker.internal:1080`

  ### The API Key

  For this MockServer tutorial, the `API Key` is: `surcom-demo-connector-api-key`

  ### TLS verification (`verify_tls`)

  The `verify_tls` setting controls whether the connector verifies SSL/TLS certificates when connecting to the target API.

  For this MockServer tutorial:

  * The MockServer runs over plain HTTP on `http://host.docker.internal:1080`, so TLS is not used.
  * You can leave `verify_tls` set to its default value; it will not affect the tutorial when using the HTTP MockServer URL.

  When you later point this connector at a real HTTPS endpoint, you should normally leave `verify_tls` enabled so that invalid certificates are rejected.

  ### Pagination (`page_limit` and `total_pages`)

  The connector uses simple pagination settings to control how many results are requested from the MockServer:

  * `page_limit` – the maximum number of records requested per page from the API. Valid options are 2, 4 and 6. The default value is 6.
  * `total_pages` – the maximum number of pages the connector will request before stopping. If the connector reaches this page limit, it will stop paginating and return the results it has collected so far. The default value is 2.

  ### Filter Device Types

  The `filter_device_types` setting allows you to specify a list of device types to filter the imported devices by. Only devices with types in this list will be imported. If the list is empty, all devices will be imported. This is an optional setting, so can be left blank if you want to import all device types.

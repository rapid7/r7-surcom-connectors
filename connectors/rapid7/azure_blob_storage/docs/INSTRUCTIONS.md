# __Description__

  Connector for Azure Blob Storage.

# __Overview__

  Azure Blob Storage is Microsoft's cloud object storage service for storing unstructured data such as documents, images, logs, and JSON exports.

  This connector reads JSON blobs from Azure Blob Storage and imports them into the Rapid7 Platform as records of a Surface Command type configured at runtime.

# __Documentation__

  To configure this connector you must provide a **Storage Account URL**, **Tenant ID**, **Client ID**, and **Client Secret** for a Microsoft Entra ID service principal that has read access to the storage account.

  | Setting | Description | Example |
  |---|---|---|
  | `storage_account_url` | Full blob service endpoint of your Azure Storage account. | `https://mystorageacct.blob.core.windows.net` |
  | `tenant_id` | Microsoft Entra ID directory (tenant) ID. | `11111111-2222-3333-4444-555555555555` |
  | `client_id` | Application (client) ID of the Entra ID app registration. | `aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee` |
  | `client_secret` | Client secret value for the app registration. | `Abc8Q~...` |

  ## __Storage Account URL__

  The blob service endpoint follows the format `https://<account-name>.blob.core.windows.net`.

  To find it in the [Azure portal](https://portal.azure.com):

  1. Navigate to your **Storage account**.
  2. In the left menu, go to **Settings** → **Endpoints**.
  3. Copy the **Blob service** URL (e.g. `https://mystorageacct.blob.core.windows.net`).
  4. Use that exact value — no trailing slash, no container name appended.

  ## __Tenant ID__

  1. Open the [Microsoft Entra admin center](https://entra.microsoft.com).
  2. Browse to **Identity** → **Overview**.
  3. Copy the **Tenant ID** value shown on the Overview page.

  > The same value appears in the [Azure portal](https://portal.azure.com) under **Microsoft Entra ID** → **Overview** → **Tenant ID**, and on any App Registration **Overview** page as **Directory (tenant) ID**.

  ## __Create an App Registration (Client ID and Client Secret)__

  1. In the [Microsoft Entra admin center](https://entra.microsoft.com), browse to **Identity** → **Applications** → **App registrations** and click **+ New registration**.
  2. Enter a descriptive name (e.g. `surface-command-blob-reader`).
  3. Under **Supported account types**, select **Single tenant only** (accounts in your organizational directory only).
  4. Leave **Redirect URI** blank and click **Register**.
  5. On the **Overview** page of the new registration, copy **Application (client) ID** — use this as `client_id`.
  6. In the left menu, open **Certificates & secrets** → **Client secrets** → **+ New client secret**.
  7. Enter a description and choose an expiry that fits your rotation policy (maximum 24 months), then click **Add**.
  8. **Immediately** copy the secret **Value** — it is shown only once. Use it as `client_secret`.

  > **Security:** never commit the client secret to source control or share it over unencrypted channels. Rotate it immediately if exposed.

  ## __Grant the App Access to the Storage Account__

  1. In the [Azure portal](https://portal.azure.com), navigate to your **Storage account**.
  2. Open **Access Control (IAM)** and click **+ Add** → **Add role assignment**.
  3. On the **Role** tab, search for and select **Storage Blob Data Reader**, then click **Next**.
  4. On the **Members** tab, set **Assign access to** → *User, group, or service principal*, click **+ Select members**, search for the app registration created above, select it, and click **Select**.
  5. Click **Review + assign** to complete the role assignment.

  > **Note:** To limit access to a single container only, perform the same steps on the container's **Access Control (IAM)** blade instead of the storage account level. When import configurations have been saved, Test Connection verifies container-level blob-listing access for the first configured container. Without saved configurations it falls back to a storage-account-level listing, which will fail if the role is scoped to a single container even though import itself would succeed. Role assignments may take a few minutes to propagate.

  ## __Import Configurations__

  After the connection test passes, create one **Azure Blob Storage Import Configuration** record in Surface Command for each set of blobs you want to import.

  | Property | Required | Description |
  |---|---|---|
  | `container_name` | Yes | Name of the Azure Blob Storage container to import blobs from. |
  | `blob_prefix` | No | Prefix to filter blobs within the container (e.g. `reports/2026/`). Leave blank to process all blobs in the container. |
  | `import_as_type` | Yes | The Surface Command type to import the JSON records as. Must be a type defined by another installed connector (e.g. `Machine`). |

  Only blobs whose names end in `.json` are processed. Each blob must contain either a single JSON object or a JSON array of objects — each object becomes one record of `import_as_type`, and must conform to its schema.


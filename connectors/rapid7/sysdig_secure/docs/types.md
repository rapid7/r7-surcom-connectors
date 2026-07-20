# Sysdig Secure Connector — Type Relationships

```mermaid
erDiagram
    SysdigSecureAwsAccount {
        string id PK
        string name
        datetime lastModified
    }

    SysdigSecureKubeCluster {
        string name PK
        string platform
        string type
        datetime lastModified
    }

    SysdigSecureKubeWorkload {
        string name PK
        string namespaceName
        string type
        string clusterName FK
        string platform
        boolean isExposed
    }

    SysdigSecureKubeNode {
        string name PK
        string clusterName FK
        string operatingSystem
        string osImage
        string platform
        boolean isMaster
    }

    SysdigSecureHost {
        string name PK
        string hostname
        string type
        string platform
        string operatingSystem
        boolean isExposed
    }

    SysdigSecureImage {
        string imageId PK
        string imageReference
        string repository
        string tag
        string platform
        string architecture
    }

    SysdigSecureVulnerability {
        string name PK
        string severity
        number cvssScore
        boolean hasExploit
        boolean hasFix
        number epssScore
    }

    SysdigSecureFinding {
        string x_id PK
        string x_vulnerabilityName FK
        string x_assetName FK
        string x_assetType
    }
    SysdigSecureAwsAccount }o--|| SysdigSecureHost : "accountId → id"
    SysdigSecureKubeWorkload }o--|| SysdigSecureKubeCluster : "clusterName → name"
    SysdigSecureKubeNode }o--|| SysdigSecureKubeCluster : "clusterName → name"
    SysdigSecureFinding }o--|| SysdigSecureVulnerability : "x_vulnerabilityName → name"
    SysdigSecureFinding }o--o| SysdigSecureHost : "x_assetName → name"
    SysdigSecureFinding }o--o| SysdigSecureKubeNode : "x_assetName → name"
    SysdigSecureFinding }o--o| SysdigSecureImage : "x_assetName → imageId"
    SysdigSecureFinding }o--o| SysdigSecureKubeWorkload : "x_assetName → d_id"
```

## Inheritance

| Type | Extends |
|------|---------|
| SysdigSecureAwsAccount | CloudAccount |
| SysdigSecureKubeCluster | System |
| SysdigSecureKubeWorkload | System |
| SysdigSecureKubeNode | Machine |
| SysdigSecureHost | Machine |
| SysdigSecureImage | Template, core.cloud-component, core.managed.asset |
| SysdigSecureVulnerability | Exposure |
| SysdigSecureFinding | Finding |

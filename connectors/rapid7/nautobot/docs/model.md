# Nautobot Connector Data Model

This document describes the entity-relationship model for the Nautobot connector types.

## Entity-Relationship Diagram

```mermaid
erDiagram
    NautobotTenant {
        string id PK
        string name
        string description
        integer device_count
        integer ipaddress_count
        integer prefix_count
        integer virtualmachine_count
        integer vlan_count
        integer cluster_count
    }

    NautobotLocation {
        string id PK
        string name
        string description
        string physical_address
        string facility
        number latitude
        number longitude
        integer device_count
        integer virtual_machine_count
        integer prefix_count
        integer vlan_count
    }

    NautobotCluster {
        string id PK
        string name
        string comments
        integer device_count
        integer virtualmachine_count
        datetime created
        datetime last_updated
    }

    NautobotDevice {
        string id PK
        string name
        string serial
        string asset_tag
        string comments
        datetime created
        datetime last_updated
    }

    NautobotVirtualMachine {
        string id PK
        string name
        integer vcpus
        integer memory
        integer disk
        string comments
        datetime created
        datetime last_updated
    }

    NautobotDeviceGroup {
        string id PK
        string name
        string description
        integer weight
        datetime created
        datetime last_updated
    }

    NautobotIPAddress {
        string id PK
        string address
        string host
        string dns_name
        integer ip_version
        integer mask_length
        string description
        datetime created
        datetime last_updated
    }

    NautobotPrefix {
        string id PK
        string prefix
        string network
        string broadcast
        integer prefix_length
        integer ip_version
        string description
        datetime created
        datetime last_updated
    }

    NautobotVLAN {
        string id PK
        integer vid
        string name
        string description
        integer prefix_count
        datetime created
        datetime last_updated
    }

    NautobotSoftwareVersion {
        string id PK
        string version
        string alias
        date release_date
        date end_of_support_date
        boolean long_term_support
        boolean pre_release
        datetime created
        datetime last_updated
    }

    NautobotCloudAccount {
        string id PK
        string name
        string account_number
        string description
        datetime created
        datetime last_updated
    }

    NautobotCloudService {
        string id PK
        string name
        string description
        datetime created
        datetime last_updated
    }

    NautobotTag {
        string id PK
        string name
        string color
        string description
        integer tagged_items
        datetime created
        datetime last_updated
    }

    NautobotEnumOperationalStatus {
        string id PK
        string value
        string map_to
    }

    %% Tenant Relationships
    NautobotDevice }o--o| NautobotTenant : "belongs to"
    NautobotVirtualMachine }o--o| NautobotTenant : "belongs to"
    NautobotCluster }o--o| NautobotTenant : "belongs to"
    NautobotLocation }o--o| NautobotTenant : "belongs to"
    NautobotIPAddress }o--o| NautobotTenant : "belongs to"
    NautobotPrefix }o--o| NautobotTenant : "belongs to"
    NautobotVLAN }o--o| NautobotTenant : "belongs to"
    NautobotDeviceGroup }o--o| NautobotTenant : "belongs to"

    %% Location Relationships
    NautobotDevice }o--o| NautobotLocation : "located at"
    NautobotCluster }o--o| NautobotLocation : "located at"
    NautobotLocation }o--o| NautobotLocation : "parent"

    %% Cluster & VM Relationships
    NautobotVirtualMachine }o--o| NautobotCluster : "runs on"

    %% Device Group Relationships
    NautobotDevice }o--o| NautobotDeviceGroup : "member of"
    NautobotDeviceGroup }o--o| NautobotDeviceGroup : "parent"

    %% IP Address Relationships
    NautobotDevice }o--o| NautobotIPAddress : "primary IPv4"
    NautobotDevice }o--o| NautobotIPAddress : "primary IPv6"
    NautobotVirtualMachine }o--o| NautobotIPAddress : "primary IPv4"
    NautobotVirtualMachine }o--o| NautobotIPAddress : "primary IPv6"
    NautobotIPAddress }o--o| NautobotPrefix : "belongs to"

    %% Network Relationships
    NautobotPrefix }o--o| NautobotPrefix : "parent"
    NautobotPrefix }o--o| NautobotVLAN : "assigned to"

    %% Software Version Relationships
    NautobotDevice }o--o| NautobotSoftwareVersion : "runs"
    NautobotVirtualMachine }o--o| NautobotSoftwareVersion : "runs"

    %% Cloud Relationships
    NautobotCloudService }o--|| NautobotCloudAccount : "belongs to"

    %% Tag Relationships (many-to-many via derived properties)
    NautobotDevice }o--o{ NautobotTag : "tagged with"
    NautobotVirtualMachine }o--o{ NautobotTag : "tagged with"
    NautobotCluster }o--o{ NautobotTag : "tagged with"
    NautobotIPAddress }o--o{ NautobotTag : "tagged with"
    NautobotPrefix }o--o{ NautobotTag : "tagged with"
    NautobotVLAN }o--o{ NautobotTag : "tagged with"
    NautobotDeviceGroup }o--o{ NautobotTag : "tagged with"
    NautobotCloudAccount }o--o{ NautobotTag : "tagged with"

    %% Status Enum Relationships
    NautobotDevice }o--o| NautobotEnumOperationalStatus : "status"
    NautobotVirtualMachine }o--o| NautobotEnumOperationalStatus : "status"
    NautobotIPAddress }o--o| NautobotEnumOperationalStatus : "status"
    NautobotPrefix }o--o| NautobotEnumOperationalStatus : "status"
```

## Type Descriptions

| Type | Description | Extends |
|------|-------------|---------|
| **NautobotTenant** | Organizational tenant representing customers, business units, or departments | Organization |
| **NautobotLocation** | Physical or logical location (sites, buildings, data centers) with hierarchical support | Location |
| **NautobotCluster** | Virtualization or compute cluster (VMware, Hyper-V, etc.) | System |
| **NautobotDevice** | Physical network device (servers, switches, routers, infrastructure hardware) | Machine |
| **NautobotVirtualMachine** | Virtual machine running on a cluster | Machine |
| **NautobotDeviceGroup** | Controller-managed device group | core.component-group |
| **NautobotIPAddress** | IP address assignment (IPv4/IPv6) with DNS names and interface assignments | IpAddress |
| **NautobotPrefix** | Network prefix (subnet) in CIDR notation | Network |
| **NautobotVLAN** | Virtual LAN configuration for network segmentation | Network |
| **NautobotSoftwareVersion** | Software/firmware version definition for network devices | Software |
| **NautobotCloudAccount** | Cloud provider account (AWS, Azure, GCP) | CloudAccount |
| **NautobotCloudService** | Cloud service resource (RDS, S3, Lambda, etc.) | core.named-object |
| **NautobotTag** | Tag for categorizing and organizing resources | SourceTag |
| **NautobotEnumOperationalStatus** | Operational status enumeration values | EnumOperationalStatus |

## Key Relationships

### Ownership & Organization
- **Tenant** owns Devices, VMs, Clusters, Locations, IP Addresses, Prefixes, VLANs, and Device Groups

### Location Hierarchy
- **Locations** can have parent-child relationships (e.g., Building → Floor → Room)
- **Devices** and **Clusters** are assigned to Locations

### Compute Infrastructure
- **Virtual Machines** run on **Clusters**
- **Devices** can be members of **Device Groups**
- **Device Groups** support hierarchical parent relationships

### Network Infrastructure
- **IP Addresses** belong to **Prefixes** (subnets)
- **Prefixes** can have parent-child relationships for subnet hierarchies
- **Prefixes** can be assigned to **VLANs**
- **Devices** and **VMs** have primary IPv4 and IPv6 addresses

### Software
- **Devices** and **Virtual Machines** can reference a **Software Version**

### Cloud Resources
- **Cloud Services** belong to **Cloud Accounts**

### Tagging
- Most types support tagging via **NautobotTag** for organization and filtering

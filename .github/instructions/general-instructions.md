
# Download and Install the Agent Skills

Use the `surcom-sdk` that is available on PyPI to download the skills to your agent:

```bash
pip install r7-surcom-sdk
surcom config install-skills -y
```

# Surface Command SDK
The Surface Command Software Development Kit (SDK), is hosted on [PyPI](https://pypi.org/project/r7-surcom-sdk/) and provides a `surcom` CLI with tools to:

- develop and install Connectors
- develop and install Types
- interact with Surface Command Data
- download the Data Model
- download Agent Skills

## Configuration
- Follow our guide at https://docs.rapid7.com/surface-command/build-custom-connectors/#install-and-configure-the-sdk to set up the SDK and configure it

## Required Agent Skills

- sc-surcom-sdk

⚠️ **BEFORE ANSWERING QUESTIONS ABOUT THE SURFACE COMMAND SDK** make sure all the required skills are available!

# Surface Command Data Model and Type System

The Surface Command data model is a graph of strongly-typed entities and their relationships. The type system that defines these entities and their interconnections is dynamic and extensible. Surface Command uses OpenAPI to describe each entity type's schema, including its relationships to other types.

When data is imported by a connector, each entity is validated against the schema for the corresponding source type.

The type system includes unified types that support common, consistent behavior. Users can write queries using unified types for a generic, standardized view of the data or use source types to query specific properties. Unified types also enable correlation, which groups multiple source entities that represent the same physical object.

A **type definition** describes the schema for an entity in Surface Command. Each type definition includes properties, relationships to other types, and metadata that defines how the type behaves within Surface Command.

Type definitions are normally created by connector developers to define the schema for the data they are importing. However, they can also be created independently of connectors to extend the data model.

The `sc-type-system` agent skill provides detailed information about the Surface Command data model, including how to define types, properties, and relationships.

## Required Agent Skills

- sc-surcom-sdk
- sc-type-system

⚠️ **BEFORE ANSWERING QUESTIONS ABOUT THE DATA MODEL** make sure all the required skills are available!

# Surface Command Connectors
Connectors are the means by which data is imported into Surface Command. They are responsible for connecting to data sources, extracting data, and transforming it into the Surface Command data model. Connectors can be developed using the `surcom-sdk`

## Required Agent Skills

- sc-surcom-sdk
- sc-type-system
- sc-connectors

⚠️ **BEFORE ANSWERING QUESTIONS ABOUT TYPE DEFINITIONS** make sure all the required skills are available!

# Surface Command Cypher Queries
Surface Command uses Cypher as the query language for interacting with the data model. Cypher is a powerful and expressive language that allows users to query the graph data in Surface Command.

To generate cypher queries when downloading the model the surcom-sdk generates a duckdb database of our model that can be used to run more complex queries and leverage the power of duckdb for data analysis. To download the model and create this index, run the command:

```bash
surcom model download --all --index
```

## Required Agent Skills

- sc-surcom-sdk
- sc-type-system
- sc-cypher-queries

⚠️ **BEFORE ANSWERING QUESTIONS ABOUT CYPHER QUERIES** make sure all the required skills are available!
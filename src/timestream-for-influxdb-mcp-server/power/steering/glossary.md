# Glossary

Key terms and concepts for working with Amazon Timestream for InfluxDB.

---

## InfluxDB Core Concepts

| Term | Definition |
|------|-----------|
| **Measurement** | The top-level grouping of data in InfluxDB, analogous to a table in relational databases. Each measurement contains tags, fields, and timestamps. |
| **Tag** | An indexed key-value pair used for metadata. Tags are strings and are optimized for grouping and filtering queries. Do not use tags for high-cardinality values that change frequently. |
| **Field** | A key-value pair that stores the actual data values (metrics). Fields are not indexed and can be integers, floats, strings, or booleans. |
| **Timestamp** | The time associated with a data point. Every point in InfluxDB has a timestamp. If omitted during write, the server assigns the current time. |
| **Point** | A single data record consisting of a measurement name, tag set, field set, and timestamp. A point is uniquely identified by its measurement, tag set, and timestamp. |
| **Series** | A unique combination of measurement and tag set. Each distinct tag set within a measurement creates a new series. |
| **Cardinality** | The total number of unique series in a database. High cardinality (millions of series) can degrade performance. |

---

## InfluxDB 2 Concepts

| Term | Definition |
|------|-----------|
| **Bucket** | A named storage location in InfluxDB 2 that holds time-series data. Buckets have a retention policy that defines how long data is kept. Analogous to a database + retention policy in InfluxDB 1.x. |
| **Organization** | A workspace for a group of users in InfluxDB 2. Buckets belong to organizations. |
| **Flux** | The functional query and scripting language for InfluxDB 2. Flux supports data transformations, aggregations, joins, and alerting. Not supported in InfluxDB 3. |
| **InfluxQL** | A SQL-like query language supported in both InfluxDB 2 and 3. In InfluxDB 2, it is a legacy alternative to Flux. |
| **Token** | An authentication credential in InfluxDB 2. Types include operator tokens (full access), all-access tokens, and read/write tokens scoped to specific buckets. |
| **Operator Token** | A special token created during initial setup that grants full administrative access. Required for creating new organizations. |
| **Task** | A scheduled Flux script in InfluxDB 2 that runs at defined intervals for downsampling, alerting, or data processing. |
| **DBRP Mapping** | Database and Retention Policy mapping that allows InfluxQL queries to target InfluxDB 2 buckets using the legacy database/retention-policy naming convention. |

---

## InfluxDB 3 Concepts

| Term | Definition |
|------|-----------|
| **Database** | The primary storage container in InfluxDB 3, replacing the bucket concept from InfluxDB 2. Databases hold tables (measurements). |
| **Table** | A structured collection of data in InfluxDB 3, equivalent to a measurement. Tables have defined columns for tags, fields, and time. |
| **SQL** | The primary query language in InfluxDB 3. Standard SQL is supported for querying time-series data. |
| **InfluxQL** | Also supported in InfluxDB 3 as an alternative query language alongside SQL. |
| **Core** | The open-source, single-node edition of InfluxDB 3. Has limitations on database count, table count, and column count compared to Enterprise. |
| **Enterprise** | The commercial, multi-node edition of InfluxDB 3 with higher limits and additional features like clustering. |
| **Last Value Cache (LVC)** | An InfluxDB 3 feature that caches the most recent value for specified columns, enabling fast lookups of current state without scanning historical data. |
| **Distinct Value Cache (DVC)** | An InfluxDB 3 feature that maintains a cache of distinct values for specified columns, useful for fast enumeration of tag values. |

---

## Amazon Timestream for InfluxDB Concepts

| Term | Definition |
|------|-----------|
| **DB Instance** | A managed InfluxDB 2 deployment in Amazon Timestream for InfluxDB. Supports standalone and Multi-AZ deployment types. |
| **DB Cluster** | A managed InfluxDB deployment (v2 or v3) in Amazon Timestream for InfluxDB that can span multiple instances for high availability. |
| **DB Parameter Group** | A collection of engine configuration parameters that can be applied to DB instances or clusters. Used to tune InfluxDB behavior. |
| **DB Instance Type** | The compute class (e.g., db.influx.medium, db.influx.xlarge) that determines CPU and memory for the InfluxDB deployment. |
| **DB Storage Type** | The storage class for the InfluxDB deployment. Options include InfluxIOIncludedT1 and InfluxIOIncludedT2. |
| **Deployment Type** | Specifies whether a DB instance runs as a standalone instance or with a Multi-AZ standby for high availability. |
| **Failover Mode** | For clusters, specifies the behavior when the primary node fails. Options include automatic failover. |
| **Allocated Storage** | The amount of storage (in GiB) provisioned for the DB instance or cluster. |
| **Endpoint** | The DNS hostname used to connect to the InfluxDB instance or cluster. Provided after deployment. |

---

## Line Protocol Concepts

| Term | Definition |
|------|-----------|
| **Line Protocol** | InfluxDB's text-based format for writing data. Format: `measurement,tag_key=tag_val field_key=field_val timestamp`. |
| **Write Precision** | The timestamp precision used when writing data. Options: nanoseconds (ns), microseconds (us), milliseconds (ms), seconds (s). Default is ns. |
| **Batch Write** | Writing multiple data points in a single API call for improved throughput. Recommended for high-ingest workloads. |

---

## Query Language Summary

| Language | InfluxDB 2 | InfluxDB 3 | Notes |
|----------|:----------:|:----------:|-------|
| Flux | Supported (primary) | Not supported | Functional scripting language |
| InfluxQL | Supported (legacy) | Supported | SQL-like, works across versions |
| SQL | Not supported | Supported (primary) | Standard SQL for InfluxDB 3 |

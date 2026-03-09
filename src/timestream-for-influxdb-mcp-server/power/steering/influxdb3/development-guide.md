# InfluxDB 3 Development Guide

## Overview

InfluxDB 3 is a columnar time-series database built on Apache Arrow and Parquet. It uses SQL as its primary query language and supports InfluxQL for compatibility. Data is organized into Databases and Tables.

Amazon Timestream for InfluxDB 3 is available as managed DB clusters. Use the `awslabs.timestream-for-influxdb-mcp-server` for cluster management and the `influxdb3` MCP server for data operations.

---

## Rules

- MUST NOT attempt Flux queries — Flux is not supported in InfluxDB 3
- SHOULD use SQL as the primary query language
- MAY use InfluxQL for compatibility with existing queries
- MUST use the `influxdb3` MCP server for data operations (read/write/schema)
- MUST use the `awslabs.timestream-for-influxdb-mcp-server` for AWS resource management (clusters, instances, parameter groups)
- SHOULD remind users of Core vs Enterprise limits when relevant
- MAY use the v2-compatible write endpoint (`/api/v2/write`) when migrating existing v2 write workloads — this avoids rewriting write code during migration

---

## Best Practices

- SHOULD design schemas with low-cardinality tags for optimal query performance
- SHOULD use SQL for new query development — it is the primary and most capable language in v3
- SHOULD batch writes using line protocol for high-throughput ingestion
- SHOULD use Last Value Cache (LVC) for dashboards that display current state
- SHOULD use Distinct Value Cache (DVC) for fast enumeration of tag values
- MUST be aware of Core limits: 5 databases, 500 tables per DB, 250 columns per table
- SHOULD prefer `INTERVAL` syntax for time ranges in SQL: `WHERE time >= now() - INTERVAL '1 hour'`

---

## Tool Examples

### Cluster Management (awslabs MCP server)

#### Create a cluster
```json
{
  "name": "my-influxdb3-cluster",
  "db_instance_type": "db.influx.xlarge",
  "password": "securePassword123",
  "allocated_storage_gb": 100,
  "vpc_security_group_ids": ["sg-0123456789abcdef0"],
  "vpc_subnet_ids": ["subnet-abc123", "subnet-def456"],
  "publicly_accessible": true,
  "tool_write_mode": true
}
```

#### List clusters
No parameters required. Use `ListDbClusters`.

#### Check cluster status
```json
{
  "db_cluster_id": "cluster-abc123"
}
```

### Data Operations (influxdb3 MCP server)

Refer to the influxdb3 MCP server documentation for tool-specific parameters. Common operations include:

#### Write data
Write using line protocol format:
```
cpu,host=server01,region=us-east usage=0.64,idle=0.36 1622505600000000000
```

#### Query with SQL
```sql
SELECT host, AVG(usage) as avg_usage
FROM cpu
WHERE time >= now() - INTERVAL '1 hour'
GROUP BY host
ORDER BY avg_usage DESC
```

#### Query with InfluxQL
```sql
SELECT MEAN("usage")
FROM "cpu"
WHERE time > now() - 1h
GROUP BY "host"
```

### Schema Operations

#### Create a database
Use the influxdb3 MCP server's database creation tool.

#### List tables
Use the influxdb3 MCP server's schema inspection tools to view tables and columns.

---

## Workflow Examples

### IoT Sensor Monitoring Setup
1. Create a DB cluster using `CreateDbCluster` with appropriate instance type
2. Wait for cluster status to become `AVAILABLE` using `GetDbCluster`
3. Create a database for sensor data using the influxdb3 MCP server
4. Write sensor data using line protocol:
   ```
   sensor,device_id=d001,location=factory1 temperature=23.5,humidity=45.2
   sensor,device_id=d002,location=factory1 temperature=24.1,humidity=44.8
   ```
5. Query with SQL:
   ```sql
   SELECT device_id, location,
          AVG(temperature) as avg_temp,
          MAX(humidity) as max_humidity
   FROM sensor
   WHERE time >= now() - INTERVAL '24 hours'
   GROUP BY device_id, location
   ```

### DevOps Metrics Dashboard
1. Write system metrics:
   ```
   system,host=web01 cpu=0.72,memory=68.5,disk_pct=45.2
   system,host=web02 cpu=0.45,memory=72.1,disk_pct=38.7
   ```
2. Set up Last Value Cache for current state:
   - Cache the latest `cpu`, `memory`, `disk_pct` per `host`
3. Query current state (fast via LVC):
   ```sql
   SELECT host, cpu, memory, disk_pct
   FROM system
   WHERE time >= now() - INTERVAL '5 minutes'
   ```

---

## Core vs Enterprise Limits

| Resource | Core | Enterprise |
|----------|------|-----------|
| Databases | 5 | 500+ |
| Tables per database | 500 | 500+ |
| Columns per table | 250 | 500+ |
| Last Value Caches | Limited | Higher limits |
| Distinct Value Caches | Limited | Higher limits |

- SHOULD warn users when approaching Core limits
- SHOULD recommend Enterprise for production workloads with many databases or high-cardinality schemas

---

## Limitations

- Flux is NOT supported — all Flux queries must be rewritten as SQL or InfluxQL
- Core has significant restrictions compared to Enterprise (see limits table above)
- No built-in task engine — scheduled processing must be handled externally
- No built-in UI for dashboarding — use Grafana or similar tools
- Deletes of individual records are limited — design retention policies carefully

---

## Schema Design & Data Modelling

### Tag vs Field Decision Guide

| Put in Tags (indexed) | Put in Fields (not indexed) |
|----------------------|---------------------------|
| Host names, regions, environments | CPU %, memory %, latency values |
| Device IDs (if bounded set) | Temperature, humidity readings |
| Status categories (ok, warning, critical) | Request counts, byte counts |
| Application names, service names | Duration, response time |
| Sensor types, metric types | Status messages (strings) |

**Key rules:**
- MUST use tags for values used in `WHERE` and `GROUP BY` clauses
- MUST use fields for numeric measurements and high-cardinality strings
- MUST NOT use tags for: UUIDs, session IDs, IP addresses, user IDs, timestamps, request IDs
- SHOULD keep total unique tag combinations (series) under 1 million per database for optimal performance

### Naming Conventions

- SHOULD use snake_case for measurement/table names: `cpu_usage`, `http_requests`
- SHOULD use snake_case for tag and field keys: `device_id`, `avg_latency_ms`
- MUST NOT use reserved SQL keywords as table or column names (e.g., `time`, `select`, `from`, `table`)
  - If unavoidable, quote them: `"time"`, `"select"`
- MUST NOT use special characters in tag/field keys: avoid `.`, `/`, `(`, `)`, `{`, `}`
- SHOULD include units in field names for clarity: `temperature_celsius`, `latency_ms`, `disk_pct`
- SHOULD use consistent naming across related tables

### Series Cardinality Audit Workflow

When a user asks "which tags are blowing up series count?" or performance is degrading:

**For InfluxDB 3 (SQL):**
1. Count distinct values per tag column:
   ```sql
   SELECT COUNT(DISTINCT host) as host_count,
          COUNT(DISTINCT region) as region_count,
          COUNT(DISTINCT device_id) as device_count
   FROM my_table
   WHERE time >= now() - INTERVAL '24 hours'
   ```
2. Identify the high-cardinality culprit — any tag with thousands+ of distinct values
3. Estimate total series: multiply distinct counts of all tags together
4. Recommend fixes:
   - Move high-cardinality tags to fields
   - Consolidate related tags (e.g., `city` + `state` → `region`)
   - Split into separate tables if tag sets serve different query patterns

**For InfluxDB 2 (Flux):**
1. Count distinct tag values:
   ```flux
   import "influxdata/influxdb/schema"
   schema.tagValues(bucket: "my-bucket", tag: "device_id", start: -24h)
     |> count()
   ```
2. List all tag keys:
   ```flux
   import "influxdata/influxdb/schema"
   schema.tagKeys(bucket: "my-bucket", start: -24h)
   ```
3. For each tag with high distinct count, recommend moving to a field

**Common redesign patterns:**
- `device_id` with 100K+ values → keep as tag only if you always filter by it; otherwise move to field
- `request_id` or `trace_id` → ALWAYS a field, never a tag
- `ip_address` → field (high cardinality)
- `user_id` → field unless bounded set (e.g., internal users only)

---

## Ad-Hoc Data Export

For scenarios like "export the last 7 days of tenant=acme data for incident analysis":

### InfluxDB 3 — SQL Export
```sql
SELECT *
FROM events
WHERE tenant = 'acme'
  AND time >= now() - INTERVAL '7 days'
ORDER BY time ASC
```
Use the influxdb3 MCP server's query tool with CSV output format for export.

### Filtered Export to Line Protocol
1. Query the data with filters
2. Convert results to line protocol format
3. Write to a new database/bucket or save as file

### Time-Scoped Export for Large Datasets
For large exports, batch by day:
```sql
SELECT * FROM events
WHERE tenant = 'acme'
  AND time >= TIMESTAMP '2025-03-01T00:00:00Z'
  AND time < TIMESTAMP '2025-03-02T00:00:00Z'
ORDER BY time ASC
```
Repeat for each day in the range.

---

## Troubleshooting

See [troubleshooting.md](./troubleshooting.md).

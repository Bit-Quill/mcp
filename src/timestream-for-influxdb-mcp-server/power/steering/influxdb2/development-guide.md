# InfluxDB 2 Development Guide

## Overview

InfluxDB 2 is a time-series database that uses Flux as its primary query language and InfluxQL as a legacy alternative. Data is organized into Organizations → Buckets → Measurements. Amazon Timestream for InfluxDB provides managed InfluxDB 2 instances.

Use the `awslabs.timestream-for-influxdb-mcp-server` for both AWS resource management and InfluxDB 2 data operations (queries, writes, bucket/org management).

---

## Rules

- MUST NOT attempt SQL queries — SQL is not supported in InfluxDB 2
- SHOULD use Flux as the primary query language
- MAY use InfluxQL for simpler queries or cross-version compatibility
- SHOULD remind users to use operator tokens when creating new organizations
- MUST set `tool_write_mode: true` for any create, update, or delete operations

---

## Best Practices

- SHOULD design schemas with low-cardinality tags — avoid using unique IDs or timestamps as tag values
- SHOULD set appropriate retention policies on buckets to manage storage costs
- SHOULD use operator tokens only for administrative operations (creating orgs, managing tokens)
- SHOULD use scoped read/write tokens for application access
- SHOULD batch writes for better throughput — use `InfluxDBWriteLP` for bulk line protocol writes
- SHOULD use `InfluxDBWritePoints` for structured writes with explicit measurement, tags, and fields
- MUST verify the organization name matches an existing org before writing or querying

---

## Tool Examples

### Queries

#### Query with Flux using InfluxDBQuery
```json
{
  "query": "from(bucket: \"sensors\") |> range(start: -1h) |> filter(fn: (r) => r._measurement == \"temperature\") |> group(columns: [\"location\"]) |> mean()"
}
```

#### Query last 24 hours of data
```json
{
  "query": "from(bucket: \"metrics\") |> range(start: -24h) |> filter(fn: (r) => r._measurement == \"cpu\") |> filter(fn: (r) => r._field == \"usage\") |> aggregateWindow(every: 15m, fn: mean)"
}
```

### Writes

#### Write structured points using InfluxDBWritePoints
```json
{
  "bucket": "sensors",
  "points": [
    {
      "measurement": "temperature",
      "tags": {"location": "office", "floor": "2"},
      "fields": {"value": 23.5},
      "time": "2025-06-01T12:00:00Z"
    },
    {
      "measurement": "humidity",
      "tags": {"location": "office", "floor": "2"},
      "fields": {"value": 45.0},
      "time": "2025-06-01T12:00:00Z"
    }
  ],
  "tool_write_mode": true
}
```

#### Write line protocol using InfluxDBWriteLP
```json
{
  "bucket": "sensors",
  "data_line_protocol": "temperature,location=office,floor=2 value=23.5 1622505600000000000\nhumidity,location=office,floor=2 value=45.0 1622505600000000000",
  "time_precision": "ns",
  "tool_write_mode": true
}
```

### Schema Operations

#### List all buckets
```json
{}
```
Use `InfluxDBListBuckets` — no parameters required (uses env vars for connection).

#### Create a bucket with 30-day retention
```json
{
  "bucket_name": "metrics",
  "retention_seconds": 2592000,
  "description": "System metrics with 30-day retention",
  "tool_write_mode": true
}
```

#### Create a bucket with infinite retention
```json
{
  "bucket_name": "audit-logs",
  "retention_seconds": 0,
  "description": "Audit logs with no expiration",
  "tool_write_mode": true
}
```

#### List organizations
```json
{}
```
Use `InfluxDBListOrgs` — no parameters required.

#### Create an organization
```json
{
  "org_name": "engineering",
  "tool_write_mode": true
}
```
Note: Requires an operator token.

---

## Workflow Examples

### IoT Sensor Monitoring Setup
1. Create a DB instance using `CreateDbInstance` with appropriate instance type
2. Wait for instance status to become `AVAILABLE` using `GetDbInstance`
3. Create a bucket for sensor data using `InfluxDBCreateBucket`:
   ```json
   {"bucket_name": "iot-sensors", "retention_seconds": 7776000, "tool_write_mode": true}
   ```
4. Write sensor data using `InfluxDBWritePoints`:
   ```json
   {
     "bucket": "iot-sensors",
     "points": [
       {"measurement": "sensor", "tags": {"device_id": "d001", "location": "factory1"}, "fields": {"temperature": 23.5, "humidity": 45.2}},
       {"measurement": "sensor", "tags": {"device_id": "d002", "location": "factory1"}, "fields": {"temperature": 24.1, "humidity": 44.8}}
     ],
     "tool_write_mode": true
   }
   ```
5. Query with Flux using `InfluxDBQuery`:
   ```json
   {
     "query": "from(bucket: \"iot-sensors\") |> range(start: -24h) |> filter(fn: (r) => r._measurement == \"sensor\") |> filter(fn: (r) => r._field == \"temperature\") |> group(columns: [\"device_id\", \"location\"]) |> mean()"
   }
   ```

### Instance Management Workflow
1. List all instances: `ListDbInstances`
2. Check instance details: `GetDbInstance` with the instance identifier
3. Filter by status: `LsInstancesByStatus` with `status: "AVAILABLE"`
4. Update instance type: `UpdateDbInstance` with new `db_instance_type` and `tool_write_mode: true`
5. Monitor tags: `ListTagsForResource` with the instance ARN

---

## Limitations

- SQL is NOT supported — use Flux or InfluxQL
- No columnar storage — uses TSM (Time-Structured Merge Tree) engine
- High cardinality (millions of unique series) can degrade query performance
- Bucket retention is the only built-in data lifecycle mechanism
- InfluxQL has limited functionality compared to Flux (no joins, limited transformations)

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
- MUST use tags for values used in `filter()` and `group()` operations
- MUST use fields for numeric measurements and high-cardinality strings
- MUST NOT use tags for: UUIDs, session IDs, IP addresses, user IDs, timestamps, request IDs
- SHOULD keep total unique tag combinations (series) under 1 million per bucket for optimal performance

### Naming Conventions

- SHOULD use snake_case for measurement names: `cpu_usage`, `http_requests`
- SHOULD use snake_case for tag and field keys: `device_id`, `avg_latency_ms`
- MUST NOT use `_` prefix for custom tag/field keys — `_measurement`, `_field`, `_value`, `_time` are reserved
- MUST NOT use special characters in tag/field keys: avoid `.`, `/`, `(`, `)`, `{`, `}`
- SHOULD include units in field names for clarity: `temperature_celsius`, `latency_ms`, `disk_pct`
- SHOULD use consistent naming across related measurements

### Series Cardinality Audit Workflow

When a user asks "which tags are blowing up series count?" or performance is degrading:

1. List all tag keys in a bucket:
   ```flux
   import "influxdata/influxdb/schema"
   schema.tagKeys(bucket: "my-bucket", start: -24h)
   ```

2. Count distinct values for each suspect tag:
   ```flux
   import "influxdata/influxdb/schema"
   schema.tagValues(bucket: "my-bucket", tag: "device_id", start: -24h)
     |> count()
   ```

3. Identify the high-cardinality culprit — any tag with thousands+ of distinct values

4. Estimate total series: multiply distinct counts of all tags together

5. Recommend fixes:
   - Move high-cardinality tags to fields
   - Consolidate related tags (e.g., `city` + `state` → `region`)
   - Split into separate measurements if tag sets serve different query patterns

**Common redesign patterns:**
- `device_id` with 100K+ values → keep as tag only if you always filter by it; otherwise move to field
- `request_id` or `trace_id` → ALWAYS a field, never a tag
- `ip_address` → field (high cardinality)
- `user_id` → field unless bounded set (e.g., internal users only)

---

## Ad-Hoc Data Export

For scenarios like "export the last 7 days of tenant=acme data for incident analysis":

### Flux Export
```flux
from(bucket: "app-data")
  |> range(start: -7d)
  |> filter(fn: (r) => r.tenant == "acme")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
```
Use `InfluxDBQuery` to run the query and retrieve results as JSON.

### Time-Scoped Export for Large Datasets
For large exports, batch by day:
```flux
from(bucket: "app-data")
  |> range(start: 2025-03-01T00:00:00Z, stop: 2025-03-02T00:00:00Z)
  |> filter(fn: (r) => r.tenant == "acme")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
```
Repeat for each day in the range.

### Export to Line Protocol
1. Query the data with filters using Flux
2. Convert the JSON results back to line protocol format
3. Write to a different bucket or save as file for analysis

---

## Troubleshooting

See [troubleshooting.md](./troubleshooting.md).

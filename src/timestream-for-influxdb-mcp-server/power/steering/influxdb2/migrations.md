# Migrations to Timestream for InfluxDB

This guide covers migration paths to Amazon Timestream for InfluxDB (InfluxDB 2).

---

## Rules

- MUST back up source data before starting any migration
- SHOULD perform a test migration with a subset of data before migrating production workloads
- MUST NOT delete source data until the migration is verified
- SHOULD plan for downtime or dual-write during migration

---

## Migration Paths

### 1. Timestream for InfluxDB (2) → Timestream for InfluxDB 3

**Scenario:** Upgrading from a managed InfluxDB 2 instance to a managed InfluxDB 3 cluster.

**Steps:**
1. Create a Timestream for InfluxDB 3 cluster using `CreateDbCluster`
2. Wait for the cluster to reach `AVAILABLE` status
3. Export data from InfluxDB 2 using Flux queries:
   ```flux
   from(bucket: "source-bucket")
     |> range(start: 2020-01-01T00:00:00Z)
     |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
   ```
4. Convert exported data to line protocol format
5. Write data to the InfluxDB 3 cluster using line protocol
6. Rewrite Flux queries as SQL or InfluxQL (see conversion table below)
7. Verify data integrity by comparing row counts and sample queries
8. Update application connection strings and auth tokens

**Key considerations:**
- Flux is NOT supported in InfluxDB 3 — all Flux queries must be rewritten
- InfluxQL queries are portable and can be used in both versions
- InfluxDB 3 exposes v2-compatible write endpoints (`/api/v2/write`), so existing v2 write workloads can target a v3 cluster without code changes — only the endpoint URL and token need updating
- The v2 query compatibility endpoint does NOT support Flux — queries must be rewritten as SQL or InfluxQL
- Bucket → Database naming: plan your database naming convention
- Measurement → Table: names carry over automatically on write
- Organization concept does not exist in InfluxDB 3
- Authentication tokens must be recreated (different token system)
- Default port changes from 8086 to 8181

### 2. InfluxDB OSS → Timestream for InfluxDB (2)

**Scenario:** Moving from a self-managed InfluxDB 2 OSS instance to a managed Timestream for InfluxDB instance.

**Steps:**
1. Create a Timestream for InfluxDB instance using `CreateDbInstance`:
   ```json
   {
     "db_instance_name": "my-influxdb",
     "db_instance_type": "db.influx.large",
     "password": "securePassword123",
     "allocated_storage_gb": 50,
     "vpc_security_group_ids": ["sg-0123456789abcdef0"],
     "vpc_subnet_ids": ["subnet-abc123", "subnet-def456"],
     "organization": "my-org",
     "bucket": "default",
     "tool_write_mode": true
   }
   ```
2. Wait for instance status to become `AVAILABLE` using `GetDbInstance`
3. Create matching buckets on the target using `InfluxDBCreateBucket`
4. Export data from the source OSS instance using Flux or the InfluxDB backup CLI:
   ```bash
   influx backup /path/to/backup --host http://source:8086 --token <source-token>
   ```
   Note: `influx backup` works against the source OSS instance, not the managed Timestream target. AWS also provides a dedicated [InfluxDB migration script](https://docs.aws.amazon.com/timestream/latest/developerguide/timestream-for-influx-getting-started-migrating-data-prepare.html) as an alternative.
5. For Flux-based export, query each bucket and write to the target:
   ```flux
   from(bucket: "source-bucket")
     |> range(start: 2020-01-01T00:00:00Z)
   ```
6. Write exported data to the target using `InfluxDBWriteLP` or `InfluxDBWritePoints`
7. Verify data integrity
8. Update application connection strings to the new endpoint

**Key considerations:**
- The managed instance uses HTTPS — update connection URLs accordingly
- Security groups must allow inbound traffic on port 8086
- Operator token is created during instance setup — save it securely
- Existing Flux queries and tasks should work without modification
- InfluxDB tasks must be recreated on the managed instance

---

## Data Export Strategies

### Flux-Based Export
Best for selective data migration:
```flux
from(bucket: "source")
  |> range(start: 2024-01-01T00:00:00Z, stop: 2024-02-01T00:00:00Z)
  |> filter(fn: (r) => r._measurement == "temperature")
```

### Time-Range Batching
For large datasets, export in time-range batches:
1. Query data in daily or weekly chunks using `range(start: ..., stop: ...)`
2. Convert to line protocol format
3. Write each chunk to the target using `InfluxDBWriteLP`
4. Verify each chunk before proceeding

### Dual-Write Strategy
For zero-downtime migration:
1. Configure applications to write to both source and target simultaneously
2. Backfill historical data from source to target
3. Verify data consistency
4. Switch reads to the target
5. Stop writes to the source

---

## Flux → SQL Conversion Reference

When migrating from InfluxDB 2 to InfluxDB 3, Flux queries must be rewritten. Common conversions:

| Flux | SQL (InfluxDB 3) |
|------|-------------------|
| `from(bucket: "b") \|> range(start: -1h)` | `SELECT * FROM table WHERE time >= now() - INTERVAL '1 hour'` |
| `\|> filter(fn: (r) => r._measurement == "m")` | `FROM m` (measurement becomes table name) |
| `\|> filter(fn: (r) => r._field == "f")` | `SELECT f FROM ...` |
| `\|> filter(fn: (r) => r.tag == "val")` | `WHERE tag = 'val'` |
| `\|> mean()` | `SELECT AVG(field) ...` |
| `\|> aggregateWindow(every: 5m, fn: mean)` | `SELECT DATE_BIN(INTERVAL '5 minutes', time, TIMESTAMP '1970-01-01T00:00:00Z'), AVG(field) ... GROUP BY 1` |
| `\|> last()` | `ORDER BY time DESC LIMIT 1` |
| `\|> group(columns: ["tag"])` | `GROUP BY tag` |
| `\|> pivot(...)` | Fields are already columns in InfluxDB 3 |
| `\|> limit(n: 100)` | `LIMIT 100` |

---

## Post-Migration Checklist

- [ ] All buckets/databases created on target
- [ ] Data written and row counts verified
- [ ] Sample queries return expected results on target
- [ ] Authentication tokens created and tested
- [ ] Application connection strings updated
- [ ] Flux queries rewritten (if migrating to v3)
- [ ] Retention policies configured on target
- [ ] Monitoring and alerting configured
- [ ] Source data retained until migration is fully verified

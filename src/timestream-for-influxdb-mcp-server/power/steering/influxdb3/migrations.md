# Migrations to Timestream for InfluxDB 3

This guide covers migration paths to Amazon Timestream for InfluxDB 3.

---

## Rules

- MUST back up source data before starting any migration
- SHOULD perform a test migration with a subset of data before migrating production workloads
- MUST rewrite Flux queries as SQL or InfluxQL when migrating from InfluxDB 2
- SHOULD plan for downtime or dual-write during migration
- MUST NOT delete source data until the migration is verified

---

## Migration Paths

### 1. InfluxDB OSS (Core) → Timestream for InfluxDB 3

**Scenario:** Moving from a self-managed InfluxDB 3 Core instance to a managed Timestream for InfluxDB 3 cluster.

**Steps:**
1. Create a Timestream for InfluxDB 3 cluster using `CreateDbCluster`
2. Wait for the cluster to reach `AVAILABLE` status
3. Create matching databases on the target cluster
4. Export data from the source using the InfluxDB 3 CLI:
   ```bash
   influxdb3 query --database <db_name> "SELECT * FROM <table>" --format csv > export.csv
   ```
5. Convert exported data to line protocol format
6. Write data to the target using line protocol
7. Verify data integrity by comparing row counts and sample queries
8. Update application connection strings to point to the new endpoint

**Considerations:**
- Last Value Caches and Distinct Value Caches must be recreated on the target
- Database tokens must be recreated on the target
- Schema (tables, columns) will be recreated automatically on first write

### 2. InfluxDB 3 Core → InfluxDB 3 Enterprise

**Scenario:** Upgrading from Core to Enterprise for higher limits and clustering.

**Steps:**
1. Deploy an Enterprise cluster using `CreateDbCluster`
2. Export data from Core using the InfluxDB 3 CLI or query API
3. Write data to the Enterprise cluster
4. Recreate databases, tokens, caches, and any configuration
5. Verify data and update connection strings

**Considerations:**
- Enterprise supports higher limits (500+ databases, 500+ columns per table)
- No query language changes needed — both use SQL and InfluxQL
- Plan for the transition window where both instances are running

### 3. InfluxDB Cloud → Timestream for InfluxDB 3

**Scenario:** Moving from InfluxDB Cloud (managed by InfluxData) to Amazon Timestream for InfluxDB 3.

**Steps:**
1. Create a Timestream for InfluxDB 3 cluster using `CreateDbCluster`
2. Export data from InfluxDB Cloud:
   - Use the InfluxDB Cloud API or CLI to query and export data
   - Export in CSV or line protocol format
3. Create matching databases on the target
4. Write exported data to the target using line protocol
5. Recreate tokens and any caches
6. Verify data integrity
7. Update application endpoints

**Considerations:**
- InfluxDB Cloud may have features not available in self-managed InfluxDB 3 (e.g., managed alerting)
- Ensure the Timestream cluster has sufficient storage for the migrated data
- Network latency may differ — test query performance after migration

---

## Data Export Strategies

### Line Protocol Export
Best for preserving the exact data format:
```bash
influxdb3 query --database <db> "SELECT * FROM <table> WHERE time >= TIMESTAMP '2025-01-01T00:00:00Z'" --format csv
```
Then convert CSV rows to line protocol format for writing.

### Time-Range Batching
For large datasets, export in time-range batches to avoid memory issues:
1. Query data in daily or hourly chunks
2. Write each chunk to the target
3. Verify each chunk before proceeding

### Dual-Write Strategy
For zero-downtime migration:
1. Configure applications to write to both source and target simultaneously
2. Backfill historical data from source to target
3. Verify data consistency
4. Switch reads to the target
5. Stop writes to the source

---

## Query Migration

### Flux → SQL Conversion Examples

| Flux | SQL Equivalent |
|------|---------------|
| `from(bucket: "b") \|> range(start: -1h)` | `SELECT * FROM table WHERE time >= now() - INTERVAL '1 hour'` |
| `\|> filter(fn: (r) => r._field == "temp")` | `SELECT temp FROM table ...` |
| `\|> mean()` | `SELECT AVG(temp) FROM table ...` |
| `\|> group(columns: ["host"])` | `... GROUP BY host` |
| `\|> aggregateWindow(every: 5m, fn: mean)` | `SELECT DATE_BIN(INTERVAL '5 minutes', time, TIMESTAMP '1970-01-01T00:00:00Z'), AVG(temp) ... GROUP BY 1` |
| `\|> last()` | `SELECT * FROM table ORDER BY time DESC LIMIT 1` |
| `\|> pivot(...)` | Fields are already columns in InfluxDB 3 — no pivot needed |

---

## Post-Migration Checklist

- [ ] All databases created on target
- [ ] Data written and row counts verified
- [ ] Sample queries return expected results
- [ ] Authentication tokens created
- [ ] Last Value Caches recreated (if used)
- [ ] Distinct Value Caches recreated (if used)
- [ ] Application connection strings updated
- [ ] Monitoring and alerting configured for the new cluster
- [ ] Source data retained until migration is fully verified

# InfluxDB 3 Query Guide

InfluxDB 3 supports SQL (primary) and InfluxQL for querying time-series data. Flux is NOT supported.

---

## Rules

- MUST NOT use Flux queries — they will fail on InfluxDB 3
- SHOULD prefer SQL for new queries — it is the primary query language
- MAY use InfluxQL for compatibility with existing queries or cross-version portability
- SHOULD use parameterized queries when incorporating user input to prevent injection

---

## SQL Query Examples

### Basic Queries

#### Select all data from a table (last hour)
```sql
SELECT *
FROM temperature
WHERE time >= now() - INTERVAL '1 hour'
ORDER BY time DESC
```

#### Select specific columns
```sql
SELECT time, location, value
FROM temperature
WHERE time >= now() - INTERVAL '24 hours'
ORDER BY time DESC
```

#### Filter by tag value
```sql
SELECT time, value
FROM temperature
WHERE location = 'office'
  AND time >= now() - INTERVAL '1 hour'
ORDER BY time DESC
```

#### Limit results
```sql
SELECT time, location, value
FROM temperature
WHERE time >= now() - INTERVAL '1 hour'
ORDER BY time DESC
LIMIT 100
```

### Aggregation Queries

#### Average by group
```sql
SELECT location, AVG(value) as avg_temp
FROM temperature
WHERE time >= now() - INTERVAL '24 hours'
GROUP BY location
ORDER BY avg_temp DESC
```

#### Min, Max, Count
```sql
SELECT location,
       MIN(value) as min_temp,
       MAX(value) as max_temp,
       COUNT(*) as readings
FROM temperature
WHERE time >= now() - INTERVAL '24 hours'
GROUP BY location
```

#### Time-bucketed aggregation
```sql
SELECT DATE_BIN(INTERVAL '15 minutes', time, TIMESTAMP '1970-01-01T00:00:00Z') as bucket,
       location,
       AVG(value) as avg_temp,
       COUNT(*) as count
FROM temperature
WHERE time >= now() - INTERVAL '6 hours'
GROUP BY bucket, location
ORDER BY bucket DESC
```

#### Percentiles
```sql
SELECT location,
       APPROX_PERCENTILE_CONT(value, 0.50) as p50,
       APPROX_PERCENTILE_CONT(value, 0.95) as p95,
       APPROX_PERCENTILE_CONT(value, 0.99) as p99
FROM response_time
WHERE time >= now() - INTERVAL '1 hour'
GROUP BY location
```

### Advanced Queries

#### Subquery — latest reading per device
```sql
SELECT *
FROM (
  SELECT *,
         ROW_NUMBER() OVER (PARTITION BY device_id ORDER BY time DESC) as rn
  FROM sensor_data
  WHERE time >= now() - INTERVAL '1 hour'
)
WHERE rn = 1
```

#### Join two tables
```sql
SELECT a.time, a.host, a.cpu_usage, b.memory_usage
FROM cpu a
JOIN memory b ON a.host = b.host AND a.time = b.time
WHERE a.time >= now() - INTERVAL '1 hour'
```

#### CASE expressions
```sql
SELECT time, host, cpu_usage,
  CASE
    WHEN cpu_usage > 90 THEN 'critical'
    WHEN cpu_usage > 70 THEN 'warning'
    ELSE 'normal'
  END as status
FROM cpu
WHERE time >= now() - INTERVAL '1 hour'
```

---

## InfluxQL Query Examples

### Basic Queries

#### Select all fields from a measurement
```sql
SELECT *
FROM "temperature"
WHERE time > now() - 1h
```

#### Filter by tag
```sql
SELECT "value"
FROM "temperature"
WHERE "location" = 'office'
  AND time > now() - 1h
```

### Aggregation Queries

#### Mean grouped by tag
```sql
SELECT MEAN("value")
FROM "temperature"
WHERE time > now() - 24h
GROUP BY "location"
```

#### Time-bucketed aggregation
```sql
SELECT MEAN("value"), MAX("value"), MIN("value")
FROM "temperature"
WHERE time > now() - 6h
GROUP BY time(15m), "location"
```

#### Count and sum
```sql
SELECT COUNT("value"), SUM("value")
FROM "requests"
WHERE time > now() - 1h
GROUP BY "endpoint"
```

#### Last value per group
```sql
SELECT LAST("value")
FROM "temperature"
GROUP BY "location"
```

---

## Time Range Syntax

### SQL
| Expression | Meaning |
|-----------|---------|
| `now() - INTERVAL '1 hour'` | Last hour |
| `now() - INTERVAL '24 hours'` | Last 24 hours |
| `now() - INTERVAL '7 days'` | Last 7 days |
| `now() - INTERVAL '30 days'` | Last 30 days |
| `'2025-01-01T00:00:00Z'` | Specific timestamp |

### InfluxQL
| Expression | Meaning |
|-----------|---------|
| `now() - 1h` | Last hour |
| `now() - 24h` | Last 24 hours |
| `now() - 7d` | Last 7 days |
| `now() - 30d` | Last 30 days |

---

## Common SQL Functions

| Function | Description | Example |
|----------|-------------|---------|
| `AVG(col)` | Average value | `AVG(temperature)` |
| `MIN(col)` | Minimum value | `MIN(temperature)` |
| `MAX(col)` | Maximum value | `MAX(temperature)` |
| `SUM(col)` | Sum of values | `SUM(bytes_sent)` |
| `COUNT(*)` | Count of rows | `COUNT(*)` |
| `DATE_BIN(interval, time, origin)` | Bucket timestamps | `DATE_BIN(INTERVAL '5 minutes', time, TIMESTAMP '1970-01-01T00:00:00Z')` |
| `APPROX_PERCENTILE_CONT(col, p)` | Approximate percentile | `APPROX_PERCENTILE_CONT(latency, 0.99)` |
| `ROW_NUMBER() OVER (...)` | Window function | `ROW_NUMBER() OVER (PARTITION BY host ORDER BY time DESC)` |

---

## Generating Queries from English (Text-to-SQL)

When a user describes what they want in plain English, follow this pattern:

### Pattern: Identify → Map → Build

1. **Identify** the table, columns, filters, time range, and aggregation from the request
2. **Map** to SQL clauses: time range → `WHERE time >=`, filters → `WHERE col = 'val'`, aggregation → `AVG()`/`SUM()`/etc., grouping → `GROUP BY`, sorting → `ORDER BY`
3. **Build** the query following standard SQL order: `SELECT` → `FROM` → `WHERE` → `GROUP BY` → `ORDER BY` → `LIMIT`

### Examples

**"Show me the average temperature per location for the last 24 hours"**
```sql
SELECT location, AVG(value) as avg_temp
FROM temperature
WHERE time >= now() - INTERVAL '24 hours'
GROUP BY location
ORDER BY avg_temp DESC
```

**"What was the peak CPU usage on server web01 in the last hour?"**
```sql
SELECT MAX(cpu_usage) as peak_cpu
FROM system
WHERE host = 'web01'
  AND time >= now() - INTERVAL '1 hour'
```

**"Give me 5-minute averages of memory usage grouped by host for the last 6 hours"**
```sql
SELECT DATE_BIN(INTERVAL '5 minutes', time, TIMESTAMP '1970-01-01T00:00:00Z') as bucket,
       host,
       AVG(memory_pct) as avg_memory
FROM system
WHERE time >= now() - INTERVAL '6 hours'
GROUP BY bucket, host
ORDER BY bucket DESC
```

**"Which hosts had CPU above 90% in the last hour?"**
```sql
SELECT host, MAX(cpu_usage) as max_cpu
FROM system
WHERE cpu_usage > 90
  AND time >= now() - INTERVAL '1 hour'
GROUP BY host
ORDER BY max_cpu DESC
```

**"Show me the 95th percentile response time per endpoint for today"**
```sql
SELECT endpoint,
       APPROX_PERCENTILE_CONT(response_time_ms, 0.95) as p95
FROM http_requests
WHERE time >= now() - INTERVAL '24 hours'
GROUP BY endpoint
ORDER BY p95 DESC
```

---

## Query Optimization

When a user says "this query is slow", follow this checklist:

### Optimization Checklist

1. **Narrow the time range** — `INTERVAL '1 hour'` is much faster than `INTERVAL '30 days'`
2. **Add `WHERE` filters** — filter by tags/columns to reduce scan scope
3. **Use `DATE_BIN` for aggregation** — avoid returning millions of raw rows
4. **Add `LIMIT`** — cap result size
5. **Select only needed columns** — avoid `SELECT *` on large tables
6. **Use Last Value Cache** — for current-state queries, LVC avoids scanning historical data

### Slow Query → Optimized Query Example

**Slow:**
```sql
SELECT * FROM system
WHERE time >= now() - INTERVAL '30 days'
```

**Optimized:**
```sql
SELECT DATE_BIN(INTERVAL '1 hour', time, TIMESTAMP '1970-01-01T00:00:00Z') as bucket,
       host,
       AVG(cpu_usage) as avg_cpu,
       MAX(memory_pct) as max_memory
FROM system
WHERE time >= now() - INTERVAL '30 days'
  AND host = 'web01'
GROUP BY bucket, host
ORDER BY bucket DESC
LIMIT 1000
```

### Schema Changes to Improve Performance

If queries are consistently slow even after optimization:
- Move high-cardinality tags to fields (reduces series count)
- Split wide tables into focused ones (e.g., `system` → `cpu`, `memory`, `disk`)
- Use Last Value Cache for frequently-queried current-state data
- Use Distinct Value Cache for tag enumeration queries
- Consider separate databases with different retention for hot vs. cold data
- For InfluxDB 3 Core: ensure you're not hitting the 250 column limit per table

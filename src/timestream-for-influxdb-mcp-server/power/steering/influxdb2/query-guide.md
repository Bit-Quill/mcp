# InfluxDB 2 Query Guide

InfluxDB 2 supports Flux (primary) and InfluxQL (legacy) for querying time-series data. SQL is NOT supported.

---

## Rules

- MUST NOT use SQL queries — they will fail on InfluxDB 2
- SHOULD prefer Flux for new queries — it is the primary and most capable language
- MAY use InfluxQL for simpler queries or cross-version compatibility
- SHOULD use the `InfluxDBQuery` tool which accepts Flux queries

---

## Flux Query Examples

### Basic Queries

#### Select all data from a bucket (last hour)
```flux
from(bucket: "sensors")
  |> range(start: -1h)
```

#### Filter by measurement
```flux
from(bucket: "sensors")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "temperature")
```

#### Filter by measurement and field
```flux
from(bucket: "sensors")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "temperature")
  |> filter(fn: (r) => r._field == "value")
```

#### Filter by tag value
```flux
from(bucket: "sensors")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "temperature")
  |> filter(fn: (r) => r.location == "office")
```

#### Limit results
```flux
from(bucket: "sensors")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "temperature")
  |> limit(n: 100)
```

### Aggregation Queries

#### Mean by group
```flux
from(bucket: "sensors")
  |> range(start: -24h)
  |> filter(fn: (r) => r._measurement == "temperature")
  |> filter(fn: (r) => r._field == "value")
  |> group(columns: ["location"])
  |> mean()
```

#### Windowed aggregation (15-minute averages)
```flux
from(bucket: "sensors")
  |> range(start: -6h)
  |> filter(fn: (r) => r._measurement == "temperature")
  |> filter(fn: (r) => r._field == "value")
  |> aggregateWindow(every: 15m, fn: mean, createEmpty: false)
```

#### Min, Max, Count
```flux
from(bucket: "sensors")
  |> range(start: -24h)
  |> filter(fn: (r) => r._measurement == "temperature")
  |> filter(fn: (r) => r._field == "value")
  |> group(columns: ["location"])
  |> reduce(
    fn: (r, accumulator) => ({
      min: if r._value < accumulator.min then r._value else accumulator.min,
      max: if r._value > accumulator.max then r._value else accumulator.max,
      count: accumulator.count + 1
    }),
    identity: {min: 999999.0, max: -999999.0, count: 0}
  )
```

#### Last value per group
```flux
from(bucket: "sensors")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "temperature")
  |> filter(fn: (r) => r._field == "value")
  |> group(columns: ["location"])
  |> last()
```

### Advanced Queries

#### Pivot fields into columns
```flux
from(bucket: "sensors")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "sensor")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
```

#### Join two measurements
```flux
cpu = from(bucket: "metrics")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "cpu")
  |> filter(fn: (r) => r._field == "usage")

memory = from(bucket: "metrics")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "memory")
  |> filter(fn: (r) => r._field == "usage")

join(tables: {cpu: cpu, memory: memory}, on: ["_time", "host"])
```

#### Map and transform values
```flux
from(bucket: "sensors")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "temperature")
  |> filter(fn: (r) => r._field == "value")
  |> map(fn: (r) => ({r with _value: (r._value * 9.0 / 5.0) + 32.0}))
```

#### Conditional filtering with multiple tags
```flux
from(bucket: "sensors")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "temperature")
  |> filter(fn: (r) => r.location == "office" or r.location == "warehouse")
  |> filter(fn: (r) => r._field == "value")
  |> filter(fn: (r) => r._value > 25.0)
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

## Flux Time Range Syntax

| Expression | Meaning |
|-----------|---------|
| `-1h` | Last hour |
| `-24h` | Last 24 hours |
| `-7d` | Last 7 days |
| `-30d` | Last 30 days |
| `-1mo` | Last month |
| `2025-01-01T00:00:00Z` | Specific timestamp |

Flux also supports absolute time ranges:
```flux
from(bucket: "sensors")
  |> range(start: 2025-01-01T00:00:00Z, stop: 2025-01-02T00:00:00Z)
```

---

## Common Flux Functions

| Function | Description | Example |
|----------|-------------|---------|
| `filter()` | Filter rows by condition | `filter(fn: (r) => r._field == "value")` |
| `range()` | Set time range | `range(start: -1h)` |
| `mean()` | Average of values | `mean()` |
| `min()` | Minimum value | `min()` |
| `max()` | Maximum value | `max()` |
| `sum()` | Sum of values | `sum()` |
| `count()` | Count of rows | `count()` |
| `last()` | Most recent value | `last()` |
| `first()` | Earliest value | `first()` |
| `aggregateWindow()` | Time-bucketed aggregation | `aggregateWindow(every: 5m, fn: mean)` |
| `group()` | Group by columns | `group(columns: ["location"])` |
| `pivot()` | Pivot fields to columns | `pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")` |
| `map()` | Transform values | `map(fn: (r) => ({r with _value: r._value * 2.0}))` |
| `limit()` | Limit result count | `limit(n: 100)` |
| `sort()` | Sort results | `sort(columns: ["_time"], desc: true)` |
| `join()` | Join two tables | `join(tables: {a: a, b: b}, on: ["_time"])` |

---

## Using InfluxDBQuery Tool

The `InfluxDBQuery` tool accepts Flux queries. Example tool call:

```json
{
  "query": "from(bucket: \"sensors\") |> range(start: -1h) |> filter(fn: (r) => r._measurement == \"temperature\") |> filter(fn: (r) => r._field == \"value\") |> group(columns: [\"location\"]) |> mean()"
}
```

The tool returns results in JSON format with measurement, field, value, time, and tags for each record.

---

## Generating Queries from English (Text-to-Flux)

When a user describes what they want in plain English, follow this pattern:

### Pattern: Identify → Map → Build

1. **Identify** the bucket, measurement, field, tags, time range, and aggregation from the request
2. **Map** to Flux functions: time range → `range()`, filters → `filter()`, aggregation → `mean()`/`sum()`/etc., grouping → `group()`
3. **Build** the query following the optimal order: `range` → `filter` → `aggregate` → `group` → `limit`

### Examples

**"Show me the average temperature per location for the last 24 hours"**
- Bucket: (ask user or use default)
- Measurement: `temperature`
- Field: `value`
- Time range: `-24h`
- Aggregation: `mean()`
- Group by: `location`

```flux
from(bucket: "sensors")
  |> range(start: -24h)
  |> filter(fn: (r) => r._measurement == "temperature")
  |> filter(fn: (r) => r._field == "value")
  |> group(columns: ["location"])
  |> mean()
```

**"What was the peak CPU usage on server web01 in the last hour?"**
```flux
from(bucket: "metrics")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "cpu")
  |> filter(fn: (r) => r._field == "usage")
  |> filter(fn: (r) => r.host == "web01")
  |> max()
```

**"Give me 5-minute averages of memory usage grouped by host for the last 6 hours"**
```flux
from(bucket: "metrics")
  |> range(start: -6h)
  |> filter(fn: (r) => r._measurement == "memory")
  |> filter(fn: (r) => r._field == "usage")
  |> aggregateWindow(every: 5m, fn: mean, createEmpty: false)
  |> group(columns: ["host"])
```

---

## Query Optimization

When a user says "this query is slow", follow this checklist:

### Optimization Checklist

1. **Narrow the time range** — `range(start: -1h)` is much faster than `range(start: -30d)`
2. **Filter measurement first** — always add `filter(fn: (r) => r._measurement == "...")` early
3. **Filter field next** — add `filter(fn: (r) => r._field == "...")` before aggregation
4. **Use `aggregateWindow()` instead of returning raw data** — downsample before returning
5. **Add `limit()`** — cap result size to prevent returning millions of rows
6. **Avoid `pivot()` on large datasets** — pivot is expensive; filter first, then pivot

### Slow Query → Optimized Query Example

**Slow:**
```flux
from(bucket: "metrics")
  |> range(start: -30d)
  |> mean()
```

**Optimized:**
```flux
from(bucket: "metrics")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "cpu")
  |> filter(fn: (r) => r._field == "usage")
  |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
  |> group(columns: ["host"])
  |> limit(n: 1000)
```

### Schema Changes to Improve Performance

If queries are consistently slow even after optimization:
- Move high-cardinality tags to fields (reduces series count)
- Split wide measurements into focused ones (e.g., `system` → `cpu`, `memory`, `disk`)
- Create separate buckets with shorter retention for hot data vs. cold data
- Use downsampling tasks to pre-aggregate data into summary buckets

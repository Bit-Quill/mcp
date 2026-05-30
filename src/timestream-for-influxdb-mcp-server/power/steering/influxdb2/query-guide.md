# InfluxDB 2 Query Guide

V2 supports two query languages:
- **Flux** — primary language, functional pipeline style, full-featured
- **InfluxQL** — SQL-like, available via V1 compatibility endpoint, limited vs Flux

## Flux Query Endpoint

```
POST /api/v2/query?orgID=<org-id>
Authorization: Token <token>
Content-Type: application/vnd.flux
Accept: application/csv
```

Raw body: '<flux script>'

- `Accept: application/csv` is required — Flux always returns CSV. Omitting it causes a 400.
- `type: "flux"` is required.
- Use org ID (not name) in the `orgID` query param.
- Include the header `Accept-Encoding: gzip` for responses over 1.4 KB. Using compression saves network bandwidth but increases server-side load.

For example:
```shell
curl \
  --request POST \
  http://localhost:8086/api/v2/query?orgID=ORG_ID
  \
  --header 'Authorization: Token API_TOKEN
' \
  --header 'Accept: application/csv' \
  --header 'Content-type: application/vnd.flux' \
  --data 'from(bucket:"BUCKET_NAME
")
        |> range(start: -12h)
        |> filter(fn: (r) => r._measurement == "example-measurement")
        |> aggregateWindow(every: 1h, fn: mean)'
```

## Flux Patterns

### Basic filter

```flux
from(bucket: "my-bucket")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "cpu" and r._field == "usage_idle")
```

`range()` is always required — Flux will not scan without a time bound.

`range()` can be relative to the current time, such as `range(start: -1h, stop: -10m)` or absolute, such as `range(start: 2026-01-01T00:00:00Z, stop: 2026-01-01T12:00:00Z)`.

### Aggregation over time windows

```flux
from(bucket: "my-bucket")
  |> range(start: -24h)
  |> filter(fn: (r) => r._measurement == "cpu" and r._field == "usage_idle")
  |> aggregateWindow(every: 5m, fn: mean, createEmpty: false)
```

`createEmpty: false` prevents null rows for windows with no data.

### Multiple fields with pivot

Flux returns one row per field by default. Use `pivot` to get all fields as columns:

```flux
from(bucket: "my-bucket")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "cpu")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
```

### Filter by tag value

```flux
from(bucket: "my-bucket")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "cpu" and r.host == "server01")
```

Tag filters go in the same `filter()` call as measurement/field filters.

### Top N values

```flux
from(bucket: "my-bucket")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "cpu" and r._field == "usage_idle")
  |> top(n: 5, columns: ["_value"])
```

### Last value per tag group

```flux
from(bucket: "my-bucket")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "cpu" and r._field == "usage_idle")
  |> last()
```

### Downsampling with aggregateWindow + write to another bucket

```flux
from(bucket: "raw")
  |> range(start: -task.every)
  |> filter(fn: (r) => r._measurement == "cpu")
  |> aggregateWindow(every: 5m, fn: mean, createEmpty: false)
  |> to(bucket: "downsampled", org: "my-org")
```

Used in scheduled tasks (see Tasks section below).

### Math between fields

```flux
from(bucket: "my-bucket")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "cpu")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> map(fn: (r) => ({ r with usage_total: r.usage_user + r.usage_system }))
```

## InfluxQL Query Endpoint

```
GET /query?db=<bucket-name>&q=<InfluxQL>&epoch=<s|ms|ns>
Authorization: Token <token>
```

Or via POST with form encoding:
```
POST /query
Authorization: Token <token>
Content-Type: application/x-www-form-urlencoded

db=<bucket-name>&q=<InfluxQL>
```

- `db` maps to the bucket name (not ID)
- `epoch` sets timestamp format in results (optional)

### InfluxQL Patterns

**Basic select:**
```sql
SELECT * FROM cpu WHERE time > now() - 1h
```

**Aggregation with time grouping:**
```sql
SELECT mean(usage_idle), max(usage_system)
FROM cpu
WHERE time > now() - 24h
GROUP BY time(5m), host
```

**Filter by tag:**
```sql
SELECT mean(usage_idle) FROM cpu
WHERE host = 'server01' AND time > now() - 1h
GROUP BY time(5m)
```

**Show measurements and tag keys:**
```sql
SHOW MEASUREMENTS
SHOW TAG KEYS FROM cpu
SHOW TAG VALUES FROM cpu WITH KEY = "host"
SHOW FIELD KEYS FROM cpu
```

**Limitations vs Flux:** InfluxQL cannot join across measurements, has no `pivot`, no custom functions, and limited math operations. Use Flux for anything beyond basic aggregations.

## Scheduled Tasks (Flux)

Tasks run Flux scripts on a schedule — used for downsampling, alerting, and data transformation.

```bash
# Create a task
curl -X POST "https://<endpoint>:8086/api/v2/tasks" \
  -H "Authorization: Token <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "orgID": "<org-id>",
    "name": "downsample-cpu",
    "every": "1h",
    "flux": "option task = {name: \"downsample-cpu\", every: 1h}\nfrom(bucket: \"raw\") |> range(start: -task.every) |> filter(fn: (r) => r._measurement == \"cpu\") |> aggregateWindow(every: 5m, fn: mean, createEmpty: false) |> to(bucket: \"downsampled\")"
  }'

# List tasks
curl "https://<endpoint>:8086/api/v2/tasks?orgID=<org-id>" \
  -H "Authorization: Token <token>"

# Manually trigger a task run
curl -X POST "https://<endpoint>:8086/api/v2/tasks/<taskID>/runs" \
  -H "Authorization: Token <token>"

# Check run history
curl "https://<endpoint>:8086/api/v2/tasks/<taskID>/runs" \
  -H "Authorization: Token <token>"
```

Task `status`: `active` (runs on schedule) | `inactive` (paused). Use `PATCH /api/v2/tasks/<taskID>` with `{"status": "inactive"}` to pause.

## Query Performance

- Always use `range()` with the narrowest time window needed — full scans are expensive
- Filter on tags (indexed) before fields (not indexed) in `filter()` calls
- Use `aggregateWindow` instead of `window` + `reduce` for standard aggregations — it's optimized
- For "current state" queries (latest value per series), use `last()` after a short range rather than scanning all time
- Tune `query-concurrency` and `query-max-memory-bytes` in the parameter group for high-concurrency workloads
- If queries timeout, increase `http-read-timeout` in the parameter group

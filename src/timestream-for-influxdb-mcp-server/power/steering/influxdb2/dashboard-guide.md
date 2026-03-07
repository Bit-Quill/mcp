# Grafana Dashboards for InfluxDB 2

This guide covers creating Grafana dashboards and visualizations for InfluxDB 2 data.

---

## Rules

- SHOULD use the Grafana InfluxDB data source with "Flux" or "InfluxQL" query type
- MUST NOT configure Grafana with SQL query type for InfluxDB 2
- SHOULD use `aggregateWindow()` in Flux queries for time-series panels to control data density
- SHOULD use `last()` for single-stat and gauge panels showing current state

---

## Data Source Configuration

### Grafana InfluxDB Data Source (Flux)

| Setting | Value |
|---------|-------|
| Query Language | Flux |
| URL | `https://your-influxdb2-endpoint:8086` |
| Organization | Your organization name |
| Token | Your InfluxDB 2 token |
| Default Bucket | Your default bucket name |

### Grafana InfluxDB Data Source (InfluxQL)

| Setting | Value |
|---------|-------|
| Query Language | InfluxQL |
| URL | `https://your-influxdb2-endpoint:8086` |
| Database | Your bucket name (via DBRP mapping) |
| HTTP Header: Authorization | `Token <your-token>` |

Note: InfluxQL queries against InfluxDB 2 require a DBRP (Database Retention Policy) mapping to map the bucket to a database/retention-policy pair.

---

## Panel Examples

### Time-Series Panel — CPU Usage Over Time

**Flux:**
```flux
from(bucket: "metrics")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "cpu")
  |> filter(fn: (r) => r._field == "usage")
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
  |> yield(name: "mean")
```

**InfluxQL:**
```sql
SELECT MEAN("usage")
FROM "cpu"
WHERE $timeFilter
GROUP BY time($__interval), "host"
```

### Gauge Panel — Current Temperature

**Flux:**
```flux
from(bucket: "sensors")
  |> range(start: -5m)
  |> filter(fn: (r) => r._measurement == "temperature")
  |> filter(fn: (r) => r._field == "value")
  |> filter(fn: (r) => r.location == "server-room")
  |> last()
```

**InfluxQL:**
```sql
SELECT LAST("value")
FROM "temperature"
WHERE "location" = 'server-room'
  AND $timeFilter
```

### Table Panel — Top Hosts by CPU

**Flux:**
```flux
from(bucket: "metrics")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "cpu")
  |> filter(fn: (r) => r._field == "usage")
  |> group(columns: ["host"])
  |> mean()
  |> sort(columns: ["_value"], desc: true)
  |> limit(n: 20)
```

### Bar Chart — Requests by Endpoint

**Flux:**
```flux
from(bucket: "metrics")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "http_requests")
  |> filter(fn: (r) => r._field == "count")
  |> sum()
  |> group(columns: ["endpoint"])
  |> sort(columns: ["_value"], desc: true)
  |> limit(n: 10)
```

### Stat Panel — Total Events

**Flux:**
```flux
from(bucket: "events")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "events")
  |> count()
```

---

## Grafana Variables

Use Grafana template variables for dynamic dashboards.

### Bucket selector variable (Flux)
```flux
buckets()
  |> filter(fn: (r) => not r.name =~ /^_/)
  |> rename(columns: {name: "_value"})
  |> keep(columns: ["_value"])
```

### Tag value selector variable (Flux)
```flux
import "influxdata/influxdb/schema"
schema.tagValues(bucket: "sensors", tag: "location", start: -24h)
```

### Measurement selector variable (Flux)
```flux
import "influxdata/influxdb/schema"
schema.measurements(bucket: "sensors", start: -24h)
```

Use variables in Flux queries:
```flux
from(bucket: v.bucket)
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "temperature")
  |> filter(fn: (r) => r.location == "${location}")
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
```

---

## Dashboard Design Best Practices

- SHOULD use `v.windowPeriod` in `aggregateWindow()` for time-series panels to auto-adjust resolution
- SHOULD use `v.timeRangeStart` and `v.timeRangeStop` instead of hardcoded time ranges
- SHOULD set appropriate refresh intervals (e.g., 30s for real-time, 5m for historical)
- SHOULD use Grafana alerting rules on critical metrics
- SHOULD group related panels into rows
- SHOULD use `createEmpty: false` in `aggregateWindow()` to avoid gaps in sparse data
- SHOULD use `pivot()` when you need multiple fields as separate columns in a table panel:
  ```flux
  from(bucket: "sensors")
    |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
    |> filter(fn: (r) => r._measurement == "sensor")
    |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  ```

---

## Grafana Dashboard JSON Template — System Monitoring

A minimal dashboard structure for system metrics:

```json
{
  "title": "System Monitoring",
  "panels": [
    {
      "title": "CPU Usage",
      "type": "timeseries",
      "targets": [
        {
          "query": "from(bucket: \"metrics\") |> range(start: v.timeRangeStart, stop: v.timeRangeStop) |> filter(fn: (r) => r._measurement == \"cpu\") |> filter(fn: (r) => r._field == \"usage\") |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)",
          "language": "flux"
        }
      ]
    },
    {
      "title": "Memory Usage",
      "type": "timeseries",
      "targets": [
        {
          "query": "from(bucket: \"metrics\") |> range(start: v.timeRangeStart, stop: v.timeRangeStop) |> filter(fn: (r) => r._measurement == \"memory\") |> filter(fn: (r) => r._field == \"usage\") |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)",
          "language": "flux"
        }
      ]
    },
    {
      "title": "Current CPU by Host",
      "type": "gauge",
      "targets": [
        {
          "query": "from(bucket: \"metrics\") |> range(start: -5m) |> filter(fn: (r) => r._measurement == \"cpu\") |> filter(fn: (r) => r._field == \"usage\") |> last() |> group(columns: [\"host\"])",
          "language": "flux"
        }
      ]
    }
  ]
}
```

# Grafana Dashboards for InfluxDB 3

This guide covers creating Grafana dashboards and visualizations for InfluxDB 3 data.

---

## Rules

- SHOULD use the Grafana InfluxDB data source with the "InfluxQL" or "SQL" query type
- MUST NOT configure Grafana with Flux query type for InfluxDB 3
- SHOULD use time-bucketed aggregations for time-series panels to avoid returning too many raw data points
- SHOULD use Last Value Cache queries for single-stat and gauge panels showing current state

---

## Data Source Configuration

### Grafana InfluxDB Data Source (InfluxQL)

| Setting | Value |
|---------|-------|
| Query Language | InfluxQL |
| URL | `https://your-influxdb3-endpoint:8181` |
| Database | Your database name |
| HTTP Header: Authorization | `Bearer <your-token>` |

### Grafana InfluxDB Data Source (SQL)

Grafana's official InfluxDB data source natively supports SQL as a query language for InfluxDB 3.x. No separate Flight SQL plugin is needed.

| Setting | Value |
|---------|-------|
| Query Language | SQL |
| URL | `https://your-influxdb3-endpoint:8181` |
| Database | Your database name |
| Token | Your InfluxDB 3 token |

---

## Panel Examples

### Time-Series Panel — CPU Usage Over Time

**InfluxQL:**
```sql
SELECT MEAN("cpu_usage")
FROM "system"
WHERE $timeFilter
GROUP BY time($__interval), "host"
```

**SQL:**
```sql
SELECT DATE_BIN(INTERVAL '1 minute', time, TIMESTAMP '1970-01-01T00:00:00Z') as time,
       host,
       AVG(cpu_usage) as cpu_usage
FROM system
WHERE time >= $__timeFrom AND time <= $__timeTo
GROUP BY 1, host
ORDER BY 1
```

### Gauge Panel — Current Temperature

**InfluxQL:**
```sql
SELECT LAST("value")
FROM "temperature"
WHERE "location" = 'server-room'
  AND $timeFilter
```

**SQL:**
```sql
SELECT value
FROM temperature
WHERE location = 'server-room'
ORDER BY time DESC
LIMIT 1
```

### Table Panel — Top Hosts by CPU

**SQL:**
```sql
SELECT host,
       AVG(cpu_usage) as avg_cpu,
       MAX(cpu_usage) as max_cpu,
       COUNT(*) as samples
FROM system
WHERE time >= $__timeFrom AND time <= $__timeTo
GROUP BY host
ORDER BY avg_cpu DESC
LIMIT 20
```

### Bar Chart — Requests by Endpoint

**SQL:**
```sql
SELECT endpoint, COUNT(*) as request_count
FROM http_requests
WHERE time >= $__timeFrom AND time <= $__timeTo
GROUP BY endpoint
ORDER BY request_count DESC
LIMIT 10
```

### Stat Panel — Total Events

**SQL:**
```sql
SELECT COUNT(*) as total_events
FROM events
WHERE time >= $__timeFrom AND time <= $__timeTo
```

---

## Grafana Variables

Use Grafana template variables for dynamic dashboards:

### Host selector variable (SQL)
```sql
SELECT DISTINCT host FROM system WHERE time >= now() - INTERVAL '1 hour'
```

### Location selector variable (SQL)
```sql
SELECT DISTINCT location FROM temperature WHERE time >= now() - INTERVAL '1 hour'
```

### Host selector variable (InfluxQL)
```sql
SHOW TAG VALUES FROM "system" WITH KEY = "host"
```

Use variables in InfluxQL queries with `$variable_name` syntax:
```sql
SELECT MEAN("cpu_usage")
FROM "system"
WHERE "host" =~ /^$host$/
  AND $timeFilter
GROUP BY time($__interval)
```

---

## Dashboard Design Best Practices

- SHOULD use `$__interval` or `DATE_BIN` for time-series panels to auto-adjust resolution based on the time range
- SHOULD set appropriate refresh intervals (e.g., 30s for real-time monitoring, 5m for historical analysis)
- SHOULD use Grafana alerting rules on critical metrics rather than polling dashboards manually
- SHOULD group related panels into rows (e.g., "CPU Metrics", "Memory Metrics", "Disk Metrics")
- SHOULD use `LIMIT` in table panels to avoid loading excessive data
- SHOULD use Stat or Gauge panels with `LAST()` or `ORDER BY time DESC LIMIT 1` for current-value displays

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
          "rawSql": "SELECT DATE_BIN(INTERVAL '1 minute', time, TIMESTAMP '1970-01-01T00:00:00Z') as time, host, AVG(cpu_usage) as cpu FROM system WHERE time >= $__timeFrom AND time <= $__timeTo GROUP BY 1, host ORDER BY 1",
          "format": "time_series"
        }
      ]
    },
    {
      "title": "Memory Usage",
      "type": "timeseries",
      "targets": [
        {
          "rawSql": "SELECT DATE_BIN(INTERVAL '1 minute', time, TIMESTAMP '1970-01-01T00:00:00Z') as time, host, AVG(memory_pct) as memory FROM system WHERE time >= $__timeFrom AND time <= $__timeTo GROUP BY 1, host ORDER BY 1",
          "format": "time_series"
        }
      ]
    },
    {
      "title": "Current CPU by Host",
      "type": "gauge",
      "targets": [
        {
          "rawSql": "SELECT host, cpu_usage FROM system ORDER BY time DESC LIMIT 10",
          "format": "table"
        }
      ]
    }
  ]
}
```

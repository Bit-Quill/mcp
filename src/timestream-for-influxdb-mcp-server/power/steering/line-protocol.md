# Line Protocol

InfluxDB Line Protocol is the text-based format for writing time-series data to InfluxDB. It is supported in both InfluxDB 2 and InfluxDB 3.

---

## Rules

- MUST follow the exact syntax: `measurement,tag_key=tag_val field_key=field_val timestamp`
- MUST have at least one field per line — lines with only tags and no fields are invalid
- MUST NOT put spaces between the measurement and tag set (comma-separated, no spaces)
- MUST separate the tag set from the field set with a single space
- MUST separate the field set from the timestamp with a single space
- SHOULD omit the timestamp to let the server assign the current time
- MUST NOT use double quotes around tag values — tag values are always unquoted strings
- MUST use double quotes around string field values
- MUST NOT use quotes around numeric or boolean field values
- SHOULD batch writes for better throughput (hundreds to thousands of lines per request)

---

## Syntax

```
<measurement>[,<tag_key>=<tag_value>[,<tag_key>=<tag_value>...]] <field_key>=<field_value>[,<field_key>=<field_value>...] [<timestamp>]
```

### Components

| Component | Required | Description | Example |
|-----------|:--------:|-------------|---------|
| Measurement | Yes | The name of the measurement (like a table name) | `cpu_usage` |
| Tag Set | No | Comma-separated key=value pairs for indexed metadata | `host=server01,region=us-east` |
| Field Set | Yes | Comma-separated key=value pairs for data values | `value=0.64,count=10i` |
| Timestamp | No | Unix timestamp in the specified precision | `1622505600000000000` |

---

## Data Types in Fields

| Type | Syntax | Example |
|------|--------|---------|
| Float | Plain number or with decimal | `value=82.5` |
| Integer | Number with `i` suffix | `count=10i` |
| Unsigned Integer | Number with `u` suffix | `count=10u` |
| String | Double-quoted value | `status="active"` |
| Boolean | `t`/`f`, `true`/`false`, `T`/`F`, `TRUE`/`FALSE` | `active=true` |

---

## Examples

### Single point
```
temperature,location=office,floor=2 value=23.5 1622505600000000000
```

### Multiple fields
```
system,host=server01 cpu=0.64,memory=72.5,disk_used=45i 1622505600000000000
```

### String field value
```
events,source=app message="User logged in",level="info" 1622505600000000000
```

### No timestamp (server assigns current time)
```
temperature,location=office value=23.5
```

### Batch write (multiple lines)
```
temperature,location=office value=23.5 1622505600000000000
temperature,location=warehouse value=18.2 1622505600000000000
humidity,location=office value=45.0 1622505600000000000
humidity,location=warehouse value=62.3 1622505600000000000
```

---

## Converting Sample Metrics to Line Protocol

When a user provides raw metrics or sample data, follow this process to convert them to well-structured line protocol.

### Step 1: Identify the measurement name
Choose a descriptive name for what is being measured (e.g., `http_requests`, `cpu_usage`, `sensor_reading`).

### Step 2: Separate tags from fields
- Tags = metadata used for grouping/filtering (low cardinality): host, region, environment, device_id, endpoint
- Fields = actual metric values (numbers, strings that change): value, count, latency, temperature, status message

### Step 3: Apply tag vs field rules
- MUST use tags for: identifiers that repeat across many points and are used in WHERE/GROUP BY
- MUST use fields for: numeric measurements, values that change frequently, high-cardinality strings
- MUST NOT use tags for: unique IDs (UUIDs), timestamps, IP addresses, user IDs, session IDs

### Example: Raw metrics → Line Protocol

**User provides:**
> "Here are sample metrics from our web servers:
> - server web01 in us-east, CPU 72%, memory 68.5%, 1250 requests, avg latency 45ms
> - server web02 in us-west, CPU 45%, memory 72.1%, 890 requests, avg latency 62ms"

**Analysis:**
- Measurement: `server_metrics`
- Tags (low cardinality, used for filtering): `host`, `region`
- Fields (numeric values): `cpu`, `memory`, `requests`, `avg_latency_ms`

**Converted line protocol:**
```
server_metrics,host=web01,region=us-east cpu=72.0,memory=68.5,requests=1250i,avg_latency_ms=45i
server_metrics,host=web02,region=us-west cpu=45.0,memory=72.1,requests=890i,avg_latency_ms=62i
```

### Example: IoT sensor data → Line Protocol

**User provides:**
> "Temperature readings: device ABC123 at building-A floor 3 reads 23.5°C and 45% humidity.
> Device DEF456 at building-B floor 1 reads 19.2°C and 62% humidity."

**Analysis:**
- Measurement: `environment`
- Tags: `device_id`, `building`, `floor` (all low cardinality, used for filtering)
- Fields: `temperature`, `humidity` (numeric values)

**Converted line protocol:**
```
environment,device_id=ABC123,building=building-A,floor=3 temperature=23.5,humidity=45.0
environment,device_id=DEF456,building=building-B,floor=1 temperature=19.2,humidity=62.0
```

### Example: Application events → Line Protocol

**User provides:**
> "Log events: user login from IP 10.0.1.5 took 230ms, status success.
> User signup from IP 10.0.2.8 took 1500ms, status success."

**Analysis:**
- Measurement: `app_events`
- Tags: `event_type` (low cardinality: login, signup, logout)
- Fields: `duration_ms` (numeric), `status` (string field), `ip` (string field — high cardinality, NOT a tag)

**Converted line protocol:**
```
app_events,event_type=login duration_ms=230i,status="success",ip="10.0.1.5"
app_events,event_type=signup duration_ms=1500i,status="success",ip="10.0.2.8"
```

Note: `ip` is a field (not a tag) because IP addresses are high-cardinality and would create too many series.

---

## Using Line Protocol with MCP Tools

### InfluxDB 2 — InfluxDBWriteLP tool
```json
{
  "bucket": "sensors",
  "data_line_protocol": "temperature,location=office value=23.5\nhumidity,location=office value=45.0",
  "time_precision": "ns",
  "tool_write_mode": true
}
```

### InfluxDB 2 — InfluxDBWritePoints tool (structured)
```json
{
  "bucket": "sensors",
  "points": [
    {
      "measurement": "temperature",
      "tags": {"location": "office"},
      "fields": {"value": 23.5},
      "time": "2025-06-01T00:00:00Z"
    }
  ],
  "tool_write_mode": true
}
```

---

## Best Practices

- SHOULD sort tags alphabetically by key for consistent series creation and better write performance
- SHOULD keep tag cardinality under control — avoid using unique IDs or timestamps as tag values
- SHOULD use meaningful measurement names that describe the data (e.g., `cpu_usage` not `data`)
- SHOULD batch 1,000–5,000 lines per write request for optimal throughput
- SHOULD use the appropriate write precision — avoid nanosecond precision if seconds suffice
- MUST escape special characters in measurement names, tag keys, tag values, and field keys:
  - Commas: `\,`
  - Spaces: `\ `
  - Equals signs (in tag/field keys): `\=`
- MUST NOT escape special characters in string field values (only `"` and `\` need escaping inside double quotes)

---

## Common Mistakes

| Mistake | Problem | Fix |
|---------|---------|-----|
| `temp, location=office value=23.5` | Space before tag set | Remove space: `temp,location=office value=23.5` |
| `temp,location="office" value=23.5` | Quoted tag value | Remove quotes: `temp,location=office value=23.5` |
| `temp,location=office value="23.5"` | String instead of float | Remove quotes for numeric: `temp,location=office value=23.5` |
| `temp,location=office` | No field set | Add at least one field: `temp,location=office value=23.5` |
| `temp,location=office, floor=2 value=23.5` | Space in tag set | Remove space: `temp,location=office,floor=2 value=23.5` |
| `temp value=23.5 value=24.0` | Duplicate field key | Use unique field keys per line |

---

## Write Precision Options

| Precision | Value | Example Timestamp |
|-----------|-------|-------------------|
| Nanoseconds | `ns` (default) | `1622505600000000000` |
| Microseconds | `us` | `1622505600000000` |
| Milliseconds | `ms` | `1622505600000` |
| Seconds | `s` | `1622505600` |

SHOULD match the precision parameter to the actual timestamp precision in your data. Mismatched precision causes incorrect time values.

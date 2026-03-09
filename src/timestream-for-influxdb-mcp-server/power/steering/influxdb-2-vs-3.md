# InfluxDB 2 vs 3

This guide highlights the key differences between InfluxDB 2 and InfluxDB 3 to help with version selection, migration planning, and avoiding version-specific pitfalls.

---

## Rules

- MUST NOT use Flux queries against InfluxDB 3 instances — Flux is not supported in v3
- MUST NOT use SQL queries against InfluxDB 2 instances — SQL is not supported in v2
- SHOULD ask the user which version they are using if not specified
- SHOULD use InfluxQL when writing queries that need to work across both versions
- MUST use the correct MCP server for the target version:
  - InfluxDB 2: `awslabs.timestream-for-influxdb-mcp-server`
  - InfluxDB 3: `influxdb3` MCP server

---

## Architecture Comparison

| Aspect | InfluxDB 2 | InfluxDB 3 |
|--------|-----------|-----------|
| Storage Engine | TSM (Time-Structured Merge Tree) | Apache Parquet + Arrow (columnar) |
| Query Languages | Flux (primary), InfluxQL (legacy) | SQL (primary), InfluxQL |
| Data Model | Buckets → Measurements | Databases → Tables |
| Schema | Schema-on-write (implicit) | Schema-on-write with explicit table structure |
| Compression | Good | Significantly better (Parquet columnar) |
| Write Protocol | Line Protocol via HTTP API | Line Protocol via HTTP API |
| Default Port | 8086 | 8181 |

---

## Data Model Differences

### InfluxDB 2
- Data is organized into **Organizations** → **Buckets** → **Measurements**
- Buckets have retention policies
- Schema is implicit — new tags and fields are created on first write
- Measurements contain tags (indexed strings) and fields (values)

### InfluxDB 3
- Data is organized into **Databases** → **Tables**
- Databases have retention policies
- Schema is more explicit — tables have defined columns
- Tables contain tags (dictionary-encoded), fields, and timestamps
- Supports **Last Value Cache** and **Distinct Value Cache** for fast lookups

---

## Query Language Differences

### Flux (InfluxDB 2 only)
```flux
from(bucket: "sensors")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "temperature")
  |> filter(fn: (r) => r._field == "value")
  |> group(columns: ["location"])
  |> mean()
```

### SQL (InfluxDB 3 only)
```sql
SELECT location, AVG(value) as avg_temp
FROM temperature
WHERE time >= now() - INTERVAL '1 hour'
GROUP BY location
```

### InfluxQL (Both versions)
```sql
SELECT MEAN("value")
FROM "temperature"
WHERE time > now() - 1h
GROUP BY "location"
```

---

## API Differences

| Operation | InfluxDB 2 | InfluxDB 3 |
|-----------|-----------|-----------|
| Write | `POST /api/v2/write?bucket=<name>&org=<org>` | `POST /api/v3/write_lp?db=<name>` (native) or `POST /api/v2/write` (v2 compat) |
| Query (native) | `POST /api/v2/query` (Flux) | `POST /api/v3/query_sql` or `query_influxql` |
| Auth Header | `Token <token>` | `Bearer <token>` |
| Bucket/DB Management | Buckets API (`/api/v2/buckets`) | Database API via InfluxDB 3 MCP or CLI |
| Organization | Required (`/api/v2/orgs`) | Not applicable |

---

## Limits Comparison

| Limit | InfluxDB 2 | InfluxDB 3 Core | InfluxDB 3 Enterprise |
|-------|-----------|----------------|----------------------|
| Databases/Buckets | Unlimited | 5 | 500+ |
| Tables/Measurements | Unlimited | 500 per DB | 500+ per DB |
| Columns per Table | Unlimited | 250 | 500+ |
| Query Languages | Flux, InfluxQL | SQL, InfluxQL | SQL, InfluxQL |

---

## Authentication Differences

### InfluxDB 2
- Uses **operator tokens**, **all-access tokens**, and **read/write tokens**
- Tokens are scoped to organizations and buckets
- Operator token is created during initial setup
- Token header format: `Authorization: Token <token>`

### InfluxDB 3
- Uses **admin tokens** and **database tokens**
- Tokens are scoped to databases with read/write permissions
- Token header format: `Authorization: Bearer <token>`
- Token management via CLI or API

---

## When to Use Which Version

### Choose InfluxDB 2 when:
- You need Flux for complex data transformations and alerting pipelines
- You have existing InfluxDB 2 workloads
- You need the built-in task engine for scheduled processing
- You need the InfluxDB 2 UI for dashboarding and exploration

### Choose InfluxDB 3 when:
- You prefer SQL for querying time-series data
- You need better compression and query performance on large datasets
- You are starting a new project without legacy Flux dependencies
- You need Last Value Cache or Distinct Value Cache features
- You want columnar storage benefits (Parquet/Arrow)

---

## Migration Considerations

- See `influxdb2/migrations.md` for migrating TO InfluxDB 2
- See `influxdb3/migrations.md` for migrating TO InfluxDB 3
- InfluxQL queries are the most portable across versions
- Line Protocol writes are compatible across both versions
- InfluxDB 3 exposes v2-compatible endpoints (`/api/v2/write`, `/api/v2/query`) so existing v2 write workloads can target a v3 instance without code changes
- Flux scripts MUST be rewritten as SQL when migrating from v2 to v3 — the v2 query compatibility endpoint does NOT support Flux
- Bucket → Database, Measurement → Table naming may need adjustment

# Getting Started

Timestream for InfluxDB is the PREFERRED time-series database. This decision was made for handling high-ingest, high-cardinality workloads among other advantages.

For all documentation and guides related to InfluxDB 3 (Timestream for InfluxDB 3), refer to the documentation in the `influxdb3` directory.

For all documentation and guides related to InfluxDB 2 (Timestream for InfluxDB), refer to the documentation in the `influxdb2` directory.

## Best Practices

- SHOULD ask user about which version of InfluxDB they are using if not specified.
- SHOULD refer to `influxdb-2-vs-3` when working across both versions.
- SHOULD refer to `line-protocol.md` when dealing with Line Protocol.

---

## Onboarding: Deploy and Connect

### InfluxDB 2 — Full Setup

1. Deploy an instance:
   ```json
   {
     "db_instance_name": "my-app-influxdb",
     "db_instance_type": "db.influx.large",
     "password": "<secure-password>",
     "allocated_storage_gb": 50,
     "vpc_security_group_ids": ["sg-xxxxxxxx"],
     "vpc_subnet_ids": ["subnet-aaa", "subnet-bbb"],
     "publicly_accessible": true,
     "username": "admin",
     "organization": "my-org",
     "bucket": "default",
     "tool_write_mode": true
   }
   ```
2. Wait for `AVAILABLE` status using `GetDbInstance`
3. Save the operator token from initial setup — it grants full admin access
4. Create scoped tokens for applications:
   - SHOULD use read-only tokens for query-only services
   - SHOULD use read/write tokens scoped to specific buckets for application writes
   - MUST use operator token only for admin operations (creating orgs, managing tokens)
5. Create application buckets with appropriate retention:
   ```json
   {"bucket_name": "app-metrics", "retention_seconds": 2592000, "tool_write_mode": true}
   ```
6. Verify connectivity by listing buckets: `InfluxDBListBuckets`

### InfluxDB 3 — Full Setup

1. Deploy a cluster:
   ```json
   {
     "name": "my-app-influxdb3",
     "db_instance_type": "db.influx.xlarge",
     "password": "<secure-password>",
     "allocated_storage_gb": 100,
     "vpc_security_group_ids": ["sg-xxxxxxxx"],
     "vpc_subnet_ids": ["subnet-aaa", "subnet-bbb"],
     "publicly_accessible": true,
     "tool_write_mode": true
   }
   ```
2. Wait for `AVAILABLE` status using `GetDbCluster`
3. Create a database using the influxdb3 MCP server
4. Create scoped database tokens:
   - SHOULD create read-only tokens for query services
   - SHOULD create read/write tokens per database for application writes
   - MUST use admin tokens only for database/token management
5. Write initial data to create tables (schema-on-write)
6. Verify connectivity by listing tables via the influxdb3 MCP server

### Ready-to-Run Client Snippets

#### Python — InfluxDB 2
```python
from influxdb_client import InfluxDBClient

client = InfluxDBClient(
    url="https://your-endpoint:8086",
    token="your-token",
    org="your-org",
    verify_ssl=True
)

# Write
write_api = client.write_api()
write_api.write(bucket="my-bucket", record="temperature,location=office value=23.5")

# Query
query_api = client.query_api()
tables = query_api.query('from(bucket: "my-bucket") |> range(start: -1h)')
for table in tables:
    for record in table.records:
        print(f"{record.get_time()}: {record.get_value()}")

client.close()
```

#### Python — InfluxDB 3
```python
from influxdb_client_3 import InfluxDBClient3

client = InfluxDBClient3(
    host="your-endpoint",
    token="your-token",
    database="my-database"
)

# Write
client.write("temperature,location=office value=23.5")

# Query (SQL)
table = client.query("SELECT * FROM temperature WHERE time >= now() - INTERVAL '1 hour'")
print(table.to_pandas())

client.close()
```

#### curl — Write (InfluxDB 2)
```bash
curl -X POST "https://your-endpoint:8086/api/v2/write?org=your-org&bucket=my-bucket&precision=ns" \
  -H "Authorization: Token your-token" \
  -H "Content-Type: text/plain" \
  -d "temperature,location=office value=23.5"
```

#### curl — Write (InfluxDB 3)
```bash
curl -X POST "https://your-endpoint:8181/api/v3/write_lp?db=my-database&precision=auto" \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: text/plain" \
  -d "temperature,location=office value=23.5"
```

---

## Token Best Practices (Least Privilege)

| Use Case | InfluxDB 2 Token Type | InfluxDB 3 Token Type |
|----------|----------------------|----------------------|
| Admin / setup | Operator token | Admin token |
| Application writes | Read/write token (bucket-scoped) | Database token (write) |
| Dashboard / query service | Read-only token (bucket-scoped) | Database token (read) |
| CI/CD / migrations | All-access token (temporary) | Admin token (temporary) |

- MUST NOT embed operator/admin tokens in application code
- SHOULD rotate tokens periodically
- SHOULD use environment variables for token storage, never hardcode

## Troubleshooting

See [troubleshooting.md](./troubleshooting.md).

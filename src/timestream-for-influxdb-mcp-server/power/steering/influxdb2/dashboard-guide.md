# Grafana Dashboards for InfluxDB 2

How to visualize **Timestream for InfluxDB v2** data in Grafana.

## Data source
Grafana ships a built-in **InfluxDB** data source plugin. Add it via **Connections → Data sources → InfluxDB**. The plugin supports three query languages; for v2 use **Flux** (primary) or **InfluxQL**.

### Connection settings
- **URL:** `https://<INSTANCE_ENDPOINT>:8086` (v2 default port).
- **Network reachability:** the Grafana server must reach the instance. For private instances, run Grafana inside the VPC or front the endpoint with a bastion/port-forward (see `influxdb2/onboarding.md`).

### Flux (recommended for v2)
Set **Query language: Flux**, then provide:
- **Organization:** your InfluxDB org name.
- **Token:** a data-plane token with read access (retrieve from InfluxDB UI — see `influxdb2/onboarding.md`).
- **Default Bucket:** optional.

Example panel query:
```flux
from(bucket: "my-bucket")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "cpu" and r._field == "usage")
```
`v.timeRangeStart`/`v.timeRangeStop` bind the panel to Grafana's time picker; `v.windowPeriod` is the auto-interval for `aggregateWindow`.

### InfluxQL (alternative)
Set **Query language: InfluxQL**. InfluxQL needs a **DBRP mapping** (database/retention-policy → bucket) on the instance; without it queries return no databases. Configure **Database**, and use **Token** auth (header `Authorization: Token <token>`). Use Flux instead, unless you need InfluxQL compatibility.

Example panel query:
```sql
SELECT mean("usage") FROM "my-bucket"."cpu" WHERE $timeFilter GROUP BY time($__interval) fill(null)
```
In Grafana, the `$timeFilter` macro expands to the panel's time range (the InfluxQL equivalent of Flux's `v.timeRangeStart`/`v.timeRangeStop`), and `$__interval` is the auto-interval for the `GROUP BY time(...)` bucket. For raw rows without aggregation, use `SELECT "usage" FROM "cpu" WHERE $timeFilter`.

## Building dashboards
- Use the visual query builder or raw editor in the panel. **Time series** and **Stat** panels cover most metrics; **Table** for raw rows.
- Use **template variables** (e.g. a query variable over tag values) for reusable, filterable dashboards.
- Grafana **alerting** and **annotations** both work against this data source.

## Monitoring the database itself
To dashboard the health of the Timestream for InfluxDB instance (CPU, memory, write throughput, query latency), use the AWS sample in **awslabs/amazon-timestream-tools** → [`integrations/influxdb_metrics_dashboard`](https://github.com/awslabs/amazon-timestream-tools/tree/mainline/integrations/influxdb_metrics_dashboard). It is a CDK app that deploys a Telegraf collector to scrape the instance `/metrics` endpoint into CloudWatch and ships a pre-built Grafana dashboard. CloudWatch metrics (`CPUUtilization`, `MemoryUtilization`, etc.) can also be charted directly via Grafana's CloudWatch data source.

## See also
- Ingestion via Telegraf: [`integrations/telegraf`](https://github.com/awslabs/amazon-timestream-tools/tree/mainline/integrations/telegraf)
- [Grafana InfluxDB data source docs](https://grafana.com/docs/grafana/latest/datasources/influxdb/)

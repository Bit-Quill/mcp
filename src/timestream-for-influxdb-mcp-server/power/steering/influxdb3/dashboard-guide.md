# Grafana Dashboards for InfluxDB 3

How to visualize **Timestream for InfluxDB v3** data in Grafana.

## Data source
Use Grafana's built-in [**InfluxDB** data source plugin](https://grafana.com/docs/grafana/latest/datasources/influxdb/) (Grafana 11+ recommended for full v3 support). Add it via **Connections → Data sources → InfluxDB**. For v3 the query language is **SQL** (primary) or **InfluxQL**. **Flux is not supported in v3** — do not select it.

### Connection settings
- **URL:** `https://<CLUSTER_ENDPOINT>:8181` (v3 default port).
- **Query language: SQL** (or InfluxQL).
- **Database:** your v3 database name (replaces v2's org/bucket).
- **Token:** a data-plane token with read access; v3 uses the `Bearer` prefix (retrieve from Secrets Manager — see `influxdb3/onboarding.md`).
- **Network reachability:** Grafana must reach the cluster. Private clusters need in-VPC Grafana or a bastion port-forward; the reader endpoint is used when the cluster has query-only nodes (Enterprise).

### SQL example
```sql
SELECT date_bin('$__interval', time) AS time, mean(usage) AS usage
FROM cpu
WHERE $__timeFilter(time)
GROUP BY 1 ORDER BY 1
```
`$__timeFilter(time)` and `$__interval` are Grafana macros that bind to the panel time range and auto-interval.

### InfluxQL (alternative)
Set **Query language: InfluxQL** to reuse legacy v1-style queries against v3's compatibility endpoint. Use SQL for new dashboards — it is the native, best-supported path.

### Arrow Flight SQL (optional)
v3's native high-performance protocol is Arrow Flight SQL. The community **FlightSQL** Grafana data source plugin can connect over gRPC for lower-latency querying, but the built-in InfluxDB data source (SQL) is the simplest and recommended starting point.

## Building dashboards
- **Time series** and **Stat** panels for metrics; **Table** for raw rows. Use the SQL builder or raw editor.
- Use **template variables** (e.g. `SELECT DISTINCT host FROM cpu`) for filterable dashboards — the v3 Distinct Value Cache makes these fast.
- Grafana **alerting** and **annotations** work against the data source.

## Monitoring the cluster itself
To dashboard cluster health (CPU, memory, write throughput, query latency), use the AWS sample in **awslabs/amazon-timestream-tools** → [`integrations/influxdb_metrics_dashboard`](https://github.com/awslabs/amazon-timestream-tools/tree/mainline/integrations/influxdb_metrics_dashboard): a CDK app that deploys a Telegraf collector scraping the cluster `/metrics` endpoint into CloudWatch with a pre-built Grafana dashboard. v3's processing engine also includes a System Metrics plugin, and CloudWatch metrics can be charted directly via Grafana's CloudWatch data source.

## See also
- Ingestion via Telegraf: [`integrations/telegraf`](https://github.com/awslabs/amazon-timestream-tools/tree/mainline/integrations/telegraf)
- [Grafana InfluxDB data source docs](https://grafana.com/docs/grafana/latest/datasources/influxdb/)
- Multiagent observability with Grafana: [`sample_apps/python/multiagent_observability`](https://github.com/awslabs/amazon-timestream-tools/tree/mainline/sample_apps/python/multiagent_observability#grafana-dashboard-overview).

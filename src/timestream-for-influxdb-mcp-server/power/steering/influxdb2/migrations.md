# Migrations for Timestream for InfluxDB v2

## Timestream for InfluxDB (2) → Timestream for InfluxDB 3

### State of play
There is **no turnkey migration tool** between the two engines today. The storage engines are completely different (V2 TSM/TSI on local volumes vs. V3 Parquet on S3), so you cannot snapshot/restore or attach V2 storage to V3. Migration is a manual **extract → transform → load (ETL)** of the data itself.

### Why the OSS disk-export path does NOT work here
On open-source InfluxDB you would normally run `influxd inspect export-lp` to dump TSM files directly to line protocol. **This is unavailable on Timestream for InfluxDB** — the managed service does not allow host/SSH/filesystem access (see `influxdb2/gotchas.md`). All data must leave V2 through the **query API**.

### The line-protocol catch
Both V2 and V3 *accept* line protocol on write, so line protocol seems like the obvious interchange format. The problem: **V2 cannot emit query results as line protocol.** A V2 Flux/InfluxQL query returns **annotated CSV** (or, via a client library, a DataFrame) — never line protocol. So a migration must either:
1. Convert the exported CSV/DataFrame to line protocol yourself before writing to V3, or
2. Skip line protocol entirely and load the CSV/DataFrame straight into V3.

Option 2 is simpler and is what the InfluxDB 3 Python client is built for.

### Extract from V2
- **Annotated CSV** — `influx query --raw 'from(bucket:"b") |> range(start: ...)'` or the HTTP `/api/v2/query` endpoint. Native, no extra deps, but you own the CSV→target mapping.
- **DataFrame (recommended)** — the V2 Python client (`influxdb-client`) returns pandas directly:
  ```python
  from influxdb_client import InfluxDBClient
  with InfluxDBClient(url=V2_URL, token=V2_TOKEN, org=V2_ORG) as v2:
      df = v2.query_api().query_data_frame(
          'from(bucket:"my-bucket") |> range(start: -30d)')
  ```
  Pull in **time-bounded chunks** (e.g. day-by-day) so you never hold a whole bucket in memory.

### Load into V3
The InfluxDB 3 Python client (`influxdb3-python`, module `influxdb_client_3`) has the richest file/DataFrame ingestion and is the preferred loader:
- **`write_file()`** imports **CSV, JSON, Feather, ORC, or Parquet** directly — best for offline/bulk migrations where V2 data was first dumped to files.
  ```python
  client.write_file(file="./export.csv",
                    timestamp_column="time", tag_columns=["host", "region"])
  ```
- **`write_dataframe()`** writes a pandas/polars DataFrame straight through — pairs directly with the V2 `query_data_frame()` extract above (no intermediate file).
  ```python
  client.write_dataframe(df, measurement="cpu",
                         timestamp_column="time", tags=["host", "region"])
  ```
- **Line protocol / `write()`** also works if you generated LP yourself, including via V3's v1/v2-compatible write endpoints (`/api/v2/write`) so existing V2 writers can be re-pointed unchanged.

### Recommended end-to-end pattern
Python bridge, chunked by time range: `v2.query_data_frame(range)` → `v3.write_dataframe(df, ...)`. No files, no manual line-protocol generation, and `pandas` is the only extra dependency. Use files (CSV/Parquet via `write_file`) instead when the export and import happen on different machines or you need a durable intermediate copy.

### Things to get right during migration
- **Namespace mapping:** V2 `org`/`bucket` → V3 `database`; each V2 `measurement` → a V3 `table`.
- **Tags vs. fields:** preserve which columns are tags (`tag_columns`/`tags`) vs. fields — this defines the V3 schema on first write.
- **Batching:** write **5,000+ points per request**; many tiny writes cause replica lag (see `gotchas.md`).
- **Timestamp precision:** carry the original precision (ns by default); a wrong precision silently shifts every point.
- **Historical backfill:** iterate over time windows oldest→newest; size windows to instance memory.
- **Queries/apps, not just data:** there is no Flux in V3. Rewrite all Flux queries, tasks, and dashboards to **SQL or InfluxQL** before cutover. The processing engine (Python plugins) replaces V2 Flux tasks for downsampling/alerting.

### Validate
After loading, compare per-table row counts and cardinality between source and target, and spot-check a few time ranges (`SELECT count(*)`, min/max timestamps, sample rows) before decommissioning the V2 instance.

## AWS migration tools and documentation
- **InfluxDB OSS 2.x → Timestream for InfluxDB** — the AWS InfluxDB migration script automates the extract/load flow described above. Walkthrough: [Use the AWS InfluxDB migration script to migrate your InfluxDB OSS 2.x data to Amazon Timestream for InfluxDB](https://aws.amazon.com/blogs/database/use-the-aws-influxdb-migration-script-to-migrate-your-influxdb-oss-2-x-data-to-amazon-timestream-for-influxdb/).
- **Other migration tools and guides** — see the [awslabs/amazon-timestream-tools](https://github.com/awslabs/amazon-timestream-tools) repository, including the [InfluxDB v1 → v2 migration guide](https://github.com/awslabs/amazon-timestream-tools/tree/mainline/guides/influxdb_v1_to_v2_migration).
- **Service documentation** — [Amazon Timestream for InfluxDB (InfluxDB 2) developer guide](https://docs.aws.amazon.com/timestream/latest/developerguide/timestream-for-influxdb.html).

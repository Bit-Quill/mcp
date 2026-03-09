# Troubleshooting in InfluxDB 2

This file contains common errors encountered while working with InfluxDB 2 and guidelines for how to solve them.

For general troubleshooting, see the [main troubleshooting guide](../troubleshooting.md).

---

## Query Errors

### Symptom: `error calling function "from": bucket not found`

**Possible causes:**
1. The bucket name is misspelled
2. The bucket does not exist in the specified organization
3. The token does not have read access to the bucket

**Resolution steps:**
1. Use `InfluxDBListBuckets` to list available buckets
2. Verify the bucket name matches exactly (case-sensitive)
3. Confirm the token has read permissions for the bucket

### Symptom: `SQL is not supported` or SQL query fails

**Cause:** SQL is not available in InfluxDB 2.

**Resolution:** Rewrite the query using Flux or InfluxQL. See the [query guide](./query-guide.md) for examples.

### Symptom: `type error` in Flux query

**Possible causes:**
1. Comparing values of different types (e.g., string vs integer)
2. Missing type conversion in `map()` or `filter()` functions
3. Using integer literals where floats are expected

**Resolution steps:**
1. Use explicit type conversions: `float(v: r._value)`, `int(v: r._value)`, `string(v: r._value)`
2. Use float literals with decimal points: `25.0` instead of `25`
3. Check that filter conditions compare compatible types

### Symptom: Query returns empty results

**Possible causes:**
1. Time range does not cover the period when data was written
2. Filter conditions are too restrictive
3. Wrong bucket or organization
4. Field name or measurement name is incorrect

**Resolution steps:**
1. Widen the time range: `range(start: -7d)`
2. Remove filters one at a time to identify which condition excludes all data
3. Start with a minimal query and add filters incrementally:
   ```flux
   from(bucket: "my-bucket") |> range(start: -1h) |> limit(n: 10)
   ```
4. Verify bucket and org with `InfluxDBListBuckets` and `InfluxDBListOrgs`

### Symptom: `unsupported input type for mean` or aggregation type error

**Cause:** Attempting to aggregate non-numeric fields (e.g., string fields).

**Resolution:** Filter to only numeric fields before aggregating:
```flux
from(bucket: "sensors")
  |> range(start: -1h)
  |> filter(fn: (r) => r._field == "value")
  |> mean()
```

---

## Write Errors

### Symptom: `bucket not found` on write

**Possible causes:**
1. The bucket does not exist
2. The bucket name is misspelled
3. The token does not have write access to the bucket

**Resolution steps:**
1. Use `InfluxDBListBuckets` to verify the bucket exists
2. Create the bucket with `InfluxDBCreateBucket` if needed
3. Verify the token has write permissions

### Symptom: `organization not found`

**Possible causes:**
1. The `INFLUXDB_ORG` environment variable is incorrect
2. The organization name is misspelled

**Resolution:**
1. Use `InfluxDBListOrgs` to list available organizations
2. Update `INFLUXDB_ORG` to match an existing organization name

### Symptom: `partial write: field type conflict`

**Cause:** A field was previously written with a different data type. InfluxDB 2 enforces consistent field types within a measurement.

**Resolution:**
1. Check the existing field type by querying existing data
2. Write data with the matching type
3. If the type must change, write to a new measurement or field name

---

## Authentication Errors

### Symptom: `unauthorized: unauthorized access`

**Possible causes:**
1. Invalid or revoked token
2. Token does not have permissions for the requested operation
3. Using a read-only token for a write operation

**Resolution steps:**
1. Verify the token value in `INFLUXDB_TOKEN`
2. For administrative operations (creating orgs, buckets), use an operator token
3. For read/write operations, ensure the token is scoped to the correct bucket and org

### Symptom: `forbidden` when creating an organization

**Cause:** Creating organizations requires an operator token, not a regular read/write token.

**Resolution:** Use the operator token that was created during initial InfluxDB setup.

---

## Bucket and Retention Issues

### Symptom: Data disappears after some time

**Cause:** The bucket has a retention policy that automatically deletes data older than the specified period.

**Resolution steps:**
1. Check the bucket's retention period with `InfluxDBListBuckets`
2. If data should be kept longer, create a new bucket with a longer retention period (or 0 for infinite)
3. Migrate data to the new bucket before it expires

### Symptom: Cannot delete a bucket

**Cause:** The MCP server does not currently expose a bucket deletion tool.

**Resolution:** Use the InfluxDB 2 UI or CLI to delete buckets directly.

---

## Performance Issues

### Symptom: Slow Flux queries

**Possible causes:**
1. Querying large time ranges without aggregation
2. Missing `filter()` before aggregation — processing all measurements/fields
3. High-cardinality `group()` operations

**Resolution steps:**
1. Always include `range()` with the narrowest possible time window
2. Add `filter()` for measurement and field before any aggregation
3. Use `aggregateWindow()` to downsample data before returning
4. Add `limit()` to cap result size
5. Optimal query pattern:
   ```flux
   from(bucket: "b")
     |> range(start: -1h)           // 1. Time range first
     |> filter(fn: (r) => r._measurement == "m")  // 2. Measurement filter
     |> filter(fn: (r) => r._field == "f")         // 3. Field filter
     |> aggregateWindow(every: 5m, fn: mean)       // 4. Aggregate
     |> limit(n: 1000)              // 5. Limit results
   ```

### Symptom: High series cardinality warnings

**Cause:** Too many unique tag combinations creating millions of series.

**Resolution steps:**
1. Avoid using high-cardinality values as tags (UUIDs, timestamps, IP addresses)
2. Move high-cardinality data to fields instead of tags
3. Use fewer tag keys per measurement
4. Consider splitting data across multiple measurements to reduce per-measurement cardinality

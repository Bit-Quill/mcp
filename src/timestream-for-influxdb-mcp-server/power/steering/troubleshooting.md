# Troubleshooting

This file contains common errors encountered while working with InfluxDB and guidelines for how to solve them.

For errors relating to a specific version, refer to the corresponding troubleshooting guide:

- [InfluxDB 3 Troubleshooting](./influxdb3/troubleshooting.md)
- [InfluxDB 2 Troubleshooting](./influxdb2/troubleshooting.md)

---

## Rules

- SHOULD check this guide first for general errors before consulting version-specific guides
- SHOULD verify connection details (URL, token, org) before investigating further
- SHOULD use `ListDbInstances` or `ListDbClusters` to confirm the instance/cluster status is `AVAILABLE` before debugging query or write issues
- MUST NOT modify production instances without explicit user confirmation

---

## Bad Connection / Authorization

### Symptom: `Connection refused` or `timeout`

**Possible causes:**
1. Instance or cluster is not in `AVAILABLE` status
2. Incorrect endpoint URL
3. Security group does not allow inbound traffic on the InfluxDB port (8086 for v2, 8181 for v3)
4. Instance is not publicly accessible and client is outside the VPC

**Resolution steps:**
1. Use `GetDbInstance` or `GetDbCluster` to check the status
2. Verify the endpoint URL matches the instance's `endpoint` field
3. Confirm the port is correct (default 8086 for v2, 8181 for v3)
4. Check VPC security group rules allow inbound traffic from the client IP
5. If the instance is not publicly accessible, ensure the client is within the same VPC or connected via VPN/peering

### Symptom: `401 Unauthorized` or `403 Forbidden`

**Possible causes:**
1. Invalid or revoked authentication token
2. Token does not have permissions for the requested operation
3. Incorrect organization name (InfluxDB 2)

**Resolution steps:**
1. Verify the token is correct and has not been revoked
2. For InfluxDB 2: confirm the `INFLUXDB_ORG` matches an existing organization — use `InfluxDBListOrgs` to check
3. For InfluxDB 2: use an operator token for administrative operations (creating orgs, buckets)
4. For InfluxDB 3: verify the token has the required read/write permissions for the target database

---

## AWS API Errors

### Symptom: `AccessDeniedException` from AWS API calls

**Possible causes:**
1. AWS credentials lack the required IAM permissions for Timestream for InfluxDB
2. AWS profile or region is misconfigured

**Resolution steps:**
1. Verify `AWS_PROFILE` and `AWS_REGION` environment variables are set correctly
2. Ensure the IAM role/user has permissions for `timestream-influxdb:*` actions (or scoped to specific actions)
3. Run `aws sts get-caller-identity` to confirm the active identity

### Symptom: `ResourceNotFoundException`

**Possible causes:**
1. The instance, cluster, or parameter group ID is incorrect
2. The resource was deleted or is in a different region

**Resolution steps:**
1. Use `ListDbInstances` or `ListDbClusters` to find the correct identifier
2. Confirm `AWS_REGION` matches the region where the resource was created

### Symptom: `ValidationException`

**Possible causes:**
1. Invalid parameter values (e.g., unsupported instance type, invalid storage size)
2. Missing required parameters

**Resolution steps:**
1. Check the error message for the specific parameter that failed validation
2. Refer to the AWS API documentation for valid parameter values
3. Ensure all required fields are provided

---

## Write Errors

### Symptom: `tool_write_mode is set to False`

**Cause:** All create, update, and delete tools require `tool_write_mode: true` to execute.

**Resolution:** Set `tool_write_mode: true` in the tool call. This is a safety mechanism to prevent accidental writes.

### Symptom: Write succeeds but data does not appear in queries

**Possible causes:**
1. Data was written to the wrong bucket/database
2. Timestamp precision mismatch — data may be written to an unexpected time range
3. Data was written to a different organization

**Resolution steps:**
1. Verify the bucket name with `InfluxDBListBuckets`
2. Confirm the write precision matches the timestamp format in your data
3. Check the organization with `InfluxDBListOrgs`

---

## SSL / TLS Errors

### Symptom: `SSL: CERTIFICATE_VERIFY_FAILED`

**Possible causes:**
1. Self-signed certificate on the InfluxDB endpoint
2. Missing CA certificates on the client machine
3. Endpoint URL uses HTTPS but the certificate is not trusted

**Resolution steps:**
1. If using a self-signed cert in a development environment, set `verify_ssl: false` in the tool call
2. For production, ensure the system trust store includes the appropriate CA certificates
3. MUST NOT disable SSL verification in production without explicit user confirmation

---

## Instance / Cluster Lifecycle

### Common Status Values

| Status | Meaning | Action |
|--------|---------|--------|
| `CREATING` | Resource is being provisioned | Wait for status to become `AVAILABLE` |
| `AVAILABLE` | Resource is ready for use | No action needed |
| `MODIFYING` | Resource is being updated | Wait for status to become `AVAILABLE` |
| `DELETING` | Resource is being deleted | Cannot be recovered |
| `FAILED` | Resource creation or update failed | Check error details, may need to delete and recreate |

Use `LsInstancesByStatus` or `ListClustersByStatus` to filter resources by status.

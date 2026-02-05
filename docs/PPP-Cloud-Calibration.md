# PPP Cloud Calibration Standard

This standard defines the **formal calibration workflow** for Polytopal Projection Processing (PPP) so every run can be reproduced, verified, and scaled across cloud compute environments. It is designed to operationalize the PPP architecture for continuous testing, auditability, and dataset packaging.

## 1. Objectives

- **Deterministic calibration**: Ensure the PPP pipeline can be driven by scripted motion plans with repeatable outputs.
- **Cloud portability**: Provide a headless execution path that produces identical artifacts across compute nodes.
- **Audit-ready metadata**: Capture run metadata, hashes, and parity diagnostics for traceability.
- **Benchmarkable outputs**: Standardize summaries, insights, and run manifests for regression tests.

## 2. Required Artifacts

Each cloud calibration run MUST emit the following files:

| Artifact | Purpose | Notes |
| --- | --- | --- |
| `ppp-cloud-calibration-manifest.json` | Full dataset (optionally includes samples) | Canonical output for downstream analysis |
| `ppp-cloud-calibration-summary.json` | Sample-free manifest | For fast checks and CI diffs |
| `ppp-cloud-calibration-insights.json` | Narrative + parity anomalies | Produced by `CalibrationInsightEngine` |
| `ppp-cloud-calibration-run.json` | Run metadata + hashes | Ties the run to compute + git state |

The summary manifest stores SHA-256 hashes for the manifest and insights artifacts so they can be validated after upload.

## 3. Standard Execution Command

Use the cloud runner to execute the formal calibration plan:

```bash
node scripts/ppp-cloud-calibration.js \
  --out-dir dist/cloud-calibration \
  --plan samples/calibration/ppp-cloud-plan.json \
  --run-id "ppp-cloud-$(date +%Y%m%d-%H%M%S)" \
  --release "ppp-cloud-calibration-v1"
```

Optional environment variables:

- `PPP_RUN_ID`: overrides `--run-id`
- `PPP_RELEASE`: overrides `--release`
- `PPP_NOTES`: attaches run context to metadata

Use `--no-samples` when you only need summary/insight artifacts for CI.

Validate the output (score + hash checks) with:

```bash
node scripts/ppp-cloud-validate.js --summary dist/cloud-calibration/ppp-cloud-calibration-summary.json \\
  --run dist/cloud-calibration/ppp-cloud-calibration-run.json
```

Pass `--no-artifacts` to skip manifest/insights file hash validation (for example, if artifacts were not downloaded locally).

## 4. Cloud Calibration Plan

Calibration plans are JSON arrays of sequence descriptors. Example: `samples/calibration/ppp-cloud-plan.json`.

Each entry supports:

```json
{
  "sequenceId": "hopf-orbit",
  "label": "Hopf Orbit Sweep",
  "sampleRate": 36,
  "durationSeconds": 10
}
```

Ensure plan sequences exist in `CalibrationToolkit` (see `scripts/CalibrationToolkit.js`).

## 5. Metadata Standard

`ppp-cloud-calibration-run.json` must include:

- `runId` (string)
- `release` (string)
- `notes` (string)
- `git.commit`, `git.branch`, `git.isDirty`
- `node`, `platform`, `arch`, `cpuCount`, `memoryGb`
- `plan` descriptor (path + sequence count)
- `manifestHash` (SHA-256 of summary manifest)

This metadata is required for external validation and cloud regression audits.

## 6. Acceptance Checks

A cloud calibration run is considered valid when:

1. **All sequences completed** (`status: complete`).
2. **Sample score meets the minimum threshold** (default 0.60 via `--min-score`).
3. **Parity anomalies flagged** in insights are reviewed and acknowledged.
4. **Hashes match** after upload to cloud storage.

## 7. Cloud Pipeline Integration

Recommended pipeline stages:

1. **Provision**: spin up Node 18+ worker with repository checkout.
2. **Run**: execute `scripts/ppp-cloud-calibration.js`.
3. **Validate**: run `scripts/ppp-cloud-validate.js` and enforce acceptance checks.
4. **Publish**: upload artifacts to storage (S3, GCS, etc.).
5. **Index**: register run metadata in experiment tracking.

## 8. Related References

- Calibration toolkit & dataset builder: `scripts/CalibrationToolkit.js`, `scripts/CalibrationDatasetBuilder.js`
- Telemetry schema: `docs/telemetry-schemas.md`
- Headless runtime: `scripts/headlessRunner.js`

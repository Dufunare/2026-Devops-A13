# E14 real DRAFT execution bridge — member C (241830217)

Development baseline: d43c67860b66d5ed8ac3ff95cf016d6b839650e9.
Review increment only; this is not a final acceptance record.

- DRAFT alone retains Docker socket access. Its /v1/execute is a restricted
  serial operation broker, registered after the current DRAFT succeeds.
  No arbitrary argv, mount, URL, image override or output path is accepted.
- Operation order: full-check-baseline, full-check-target, scan-baseline,
  scan-target, validate, full-check-recheck. Existing imgrunner and lab.validate
  provide actual child execution. BuildChecker/EChecker/MDFixer retain their roles.
- The orchestrator saves original request bytes in draft mode, binds the
  request and candidate hashes, resolved profile, C0/C1, Job/Trace and
  actual DRAFT image ID. It verifies every exec/inspect pair and operation
  receipt before admitting the final stage. Full-project MISSING=0 is still required.
- Existing default teaching mode retains its original contract and artifact count.
- Trusted course workspace only; not an authenticated public API or a hostile-code
  sandbox. Keep loopback bindings. A new DRAFT invalidates the previous broker
  context; execute jobs serially.

Pending: B's full-project build/run target and repair-scope contract, official
paired inputs, real-engine execution evidence and final ECS acceptance. The
existing validation assumes the build target is executable, so draft mode rejects
make all rather than invoking ./all or silently falling back to orchestrator.
Offline synthetic evidence tests are not proof of real container execution.

## Independent controlled-fixture execution gate

real_job_gate.py requires expected original request and candidate hashes; checks
all five stages, all six HTTP exchanges, raw DRAFT image inspect, report payload,
validation output, complete findings, attestation receipts and exact artifact
manifest coverage (nonempty, no fixed item count). It also checks the four
services before/after the job and preserves logs. CI runs a new controlled
fixture request with exec_image=draft and a separate candidate adding Git and
strace. The original fixture stays unchanged. CI runs that new job as root to
match ECS/Compose snapshot ownership; no wildcard Git trust is added.
The new gate is a single-job success preflight, not a substitute for formal
paired inputs or the real-project timeout/recovery campaign.

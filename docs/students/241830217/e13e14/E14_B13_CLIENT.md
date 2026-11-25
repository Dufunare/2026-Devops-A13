# B13 consumer-side client preparation — 241830217

B13 protocol reference: ma058/2026-Devops-B13 at
6244f7699e8e9920e2185860542bed54afd2123b, course/e13-e14/MEMBER2_SERVICE_PROTOCOL.md,
labs/e13e14/member2_run.py, member2_service.py, member2_runtime.py and
labs/e11e12/server.py, pipeline.py, image_runtime.py. The six historical
request originals and summary in exchange/20261123-v2-receipt are examples
only, never replayed. B13's final source/image/project/profile may change;
obtain frozen originals before any live run.

A13 connects to B13, not the reverse. PR #29's A13-side Bearer facade is a
separate proposal. This increment never installs SSH access, opens ports,
starts Docker or connects to an external IP. B13's current synchronous
health is unauthenticated and its POST /v1/run uses X-E14-Token; /v1/worker
is internal and is never called by these clients. The current B13 8081
asynchronous API uses SSH access only, not an application token. Do not
test unrelated jobs or add an unapproved forward.

## Before the window

Get independently agreed SSH account/host/host key fingerprint and port
mapping (proposed client 18301–18304 for the four roles, 18305 for 8081).
Use the dedicated private key; verify the host key out of band and use
strict host key checking. Token is entered with no echo, never in command
lines or evidence. Do not paste it into a JSON file or terminal transcript.

For each synchronous scenario, B13 prepares a FRESH server-side job:
two exact C0/C1 clones below /course/work/<run>/jobs/<job>/base and target,
with all file fingerprints verified and outputs absent, and a staged
candidate below /course/data. The server operator supplies the new job
and trace IDs, run root, candidate path, declared implementation SHA,
service image ID, scenario, manifest/profile/candidate originals plus
their independent hashes. No client-side cloning on B13 via SSH shell
is required or assumed. B13 must provide separate normal/C4/C5 deployments
as documented; use a new job for C4 recovery in the normal environment.
Do not reuse an old job/trace/path/image, or assume the old toml.o profile
supports make all.

Create the approved session JSON, schema b13-sync-session-1, with exactly:
schema_version, scenario (normal/C4/C5), service_source_sha (40 hex),
service_image_id (sha256:64 hex, service image not DRAFT output), job_id
(job-32 hex), trace_id (trace-32 hex), run_root (absolute /course/work/...),
candidate_path (absolute /course/data/.../candidate.Dockerfile), ports
(object buildchecker/echecker/draft/mdfixer with the four local forwards),
manifest_sha256, profile_raw_sha256, profile_canonical_sha256,
candidate_sha256. Freeze and exchange SHA256 of the session JSON itself.
All original files must be provided; do not reconstruct them from
historical request snippets. The canonical rule is sorted keys, UTF-8,
ensure_ascii=False, separators=(',', ':'), allow_nan=False.

## Synchronous six requests (Windows Python 3.10+ or Linux)

    python labs/e13e14/b13_sync_client.py start --session SESSION.json --session-sha256 SESSION_SHA --manifest MANIFEST.json --profile PROFILE.json --candidate CANDIDATE.Dockerfile --out FRESH_OUT

start checks four role/protocol health responses, executes DRAFT then
baseline and target full; DRAFT's NEW image ID is bound into subsequent
requests. C4 executes only DRAFT and the fixed timeout-full call on a
B13-approved C4 stack. An expected HTTP 200 TIMED_OUT result is a client
observation, not independent proof of daemon cleanup.

Normal/C5 start stops after the third POST. B13 must return the actual
baseline-full/actual-graph.json and target-full/findings.json bytes
and their independently computed SHA256 from THAT job. The full
responses do not expose these raw hashes. The client does not invent
hashes by serializing the HTTP JSON and does not access server paths.

    python labs/e13e14/b13_sync_client.py finish --out SAME_OUT --graph GRAPH.json --graph-sha256 GRAPH_SHA --findings FINDINGS.json --findings-sha256 FINDINGS_SHA

finish verifies the original findings against the target full response,
sends EChecker, passes its report/payload paths and raw hashes to MDFixer,
and runs final full. C5 sends the fixed bad-repair request before the
good repair on the approved C5 stack. It requires actual rejection and
rollback claims, then correct repair and final MISSING=0. The normal
path uses 6 POSTs, C4 2, C5 7. Never enable faults on normal stack.
An attempted POST is never retried automatically; reconcile failed/lost
responses with B13 and preserve the original folder. If finish is
interrupted after an attempted mutation, do not rerun it on the same job.

## Asynchronous C8

Obtain B13's approved E12 request bytes, candidate original, independent
SHA256, and the actual 8081 implementation and image pins (do not assume
they are the synchronous service pins).

    python labs/e13e14/b13_c8_client.py --port 18305 --request E12.json --request-sha256 REQUEST_SHA --candidate CANDIDATE.Dockerfile --candidate-sha256 CANDIDATE_SHA --service-source-sha SOURCE_SHA --service-image-id SERVICE_IMAGE_ID --out FRESH_C8_OUT

This client checks real 202 duplicate response identity, 409 with the same
key/different target, polls only its own Job, downloads all listed original
artifacts, checks per-file bytes/hash/header and five stage bindings,
requires DRAFT image reuse, accepted repair and full MISSING=0, and
replays the completed key. Distinguish raw request SHA, canonical request
SHA and B13's Store hash (json.dumps(sort_keys=True), default spacing and
ASCII). It does not test unrelated Job IDs or assume an empty shared Store.

## Receipts and boundaries

Each exchange saves exact sent body and exact received bytes (plus allowlisted
headers, timing, status and hashes). No token header value, no redirects or
proxy, no automatic POST retry. A credential echoed by the peer is rejected
rather than archived. Service source/image pins are declared, not attested by
health. The sync client verifies response-level witnesses; the two scan
containers, report/payload originals and actual daemon inspect/cleanup must
be cross-checked in the server archive. C4 needs actual cleanup originals
and a separate normal recovery receipt. C5 needs original before/after
tracked bytes, git status, apply-check stderr, actual bad/good validation
records and final full. C8 needs B13's independent Store key/job observation,
actual image-execution originals, source/image binding and artifact inventory.
Both sides exchange archives and SHA256, verify matching Job/Trace and raw
HTTP originals. Client PASS never sets formal_pair_acceptance=true.
The new clients are protocol-local preflight until actual B13 access,
freeze and paired execution; no live credentials are used in CI.

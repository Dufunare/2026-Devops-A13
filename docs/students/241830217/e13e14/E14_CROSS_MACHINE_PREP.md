# E14 cross-machine preparation — 241830217

Status: proposed, not a deployed service and not formal bilateral acceptance.
Baseline PR #28 84cc47fbd21948fb286e12cc4c49f527112a17ee has independent CI/ECS
preflight evidence. This increment must not relabel those old runs as its own.

## Access agreement (pending B13 response)

Record the actual connector, public-key fingerprint, two time windows with
timezone and end times, exact role-to-loopback mapping, independently pinned
source/request/candidate/profile identity and the permitted operations. No
private SSH key or session credential in Git, chat logs, command lines,
environment dumps, Docker inspect or evidence archives.

Do not grant root shell, Docker group, unrestricted TCP forwarding or access
to raw role APIs. The server administrator must use a dedicated unprivileged
temporary SSH identity, public-key-only authentication, AllowTcpForwarding
local, exact PermitOpen loopback destinations, no shell/subsystems/PTY/agent/
X11/tunnel, expiry and explicit session termination. Validate effective sshd
Match settings and actual denial/allowance using the agreed key before opening
the formal window. Key expiry alone does not terminate an existing SSH
connection. No changes to the server's existing root account or other groups'
authorized_keys. Confirm SSH host key fingerprint out of band. Remove the
temporary identity/access at the end, check port closure and retain redacted
authorization/revocation observations. This document does not apply changes.

## Proposed access surface (requires bilateral agreement)

Keep the four existing Compose roles on their private loopback ports.
The raw DRAFT /v1/execute and role /v1/run are trusted local interfaces, NOT
safe remote API endpoints; they accept project/output paths and build input.
pair_session.py exposes a distinct loopback listener per agreed role:
authenticated /health and /v1/session only. No forwarding of mutation
requests. For C8 use a separate agreed temporary listener and a fresh
dedicated E11/E12 async Store with a private loopback upstream. Do not include
backend ports in PermitOpen. Stop the gateways at the deadline and revoke SSH.

The async listener accepts one exact approved E12 input (strict JSON,
canonical semantic comparison) and one idempotency key; the same key may
replay or submit precisely the reserved all-zero target conflict. All other
requests fail closed, and reads are limited to that Job and manifest-listed
artifacts. It forwards actual upstream 202/409 and downloads, checks bytes
and hashes, and never writes the credential. A lost POST response reserves
the same key; restart is NOT resumable (stop the session and reconcile its
Store before opening another). The deadline blocks new requests, not an
already-running server job. Use only a staged, trusted course repository,
a read-only operator-approved candidate/profile and fresh private Store.
The gateway is not a hostile-code sandbox, not internet-facing, and does
not prove deployment identity simply from declared pins.

Start each listener on an agreed unused loopback port with:
    python3 labs/e13e14/pair_session.py --role ROLE \
      --listen-port GATEWAY_PORT --upstream-port PRIVATE_PORT \
      --approved-request REQUEST --request-sha256 REQUEST_SHA \
      --candidate-sha256 CANDIDATE_SHA --source-commit SOURCE_SHA \
      --expires ISO8601_WITH_TZ --credential-file PRIVATE_FILE

Credential file outside /course and work/evidence, owner-only mode 0600,
generated using cryptographic randomness and privately exchanged. Never use
a real credential as a CLI argument or include it in the archive. Verify
the actual deployed source, upstream service IDs and candidate/profile bytes
before startup. The async API must not be accessible on the raw backend port
through the authorized SSH account. Separate the private Store from prior
experiments. The gateway intentionally accepts no client-provided URL, path
to a local file, role command, arbitrary patch or Docker action.

Client (after SSH authorization and agreed port mapping):
    python3 labs/e13e14/pair_c8_client.py --port LOCAL_API_PORT \
      --request REQUEST --request-sha256 REQUEST_SHA \
      --candidate-sha256 CANDIDATE_SHA --source-commit SOURCE_SHA \
      --out FRESH_CLIENT_OUT

The client prompts without echo, records request/response bodies and selected
headers (never Authorization), proves actual 202 replay and 409 conflict,
polls a new Job, downloads every manifest entry and checks SHA256/bytes,
verifies stage envelopes and nested artifact references, and retries after
completion. Client receipt is not the server job-count proof: server must
independently verify exactly one new Store entry, actual exec/inspect,
source/image/profile and original artifact bytes, and exchange archive
digests. No peer signature is inferred from a local CI run.

## Synchronous E14 and C4/C5

Pending agreement on the remote invocation model. Prefer an operator-owned
fixed campaign using the existing host orchestrator, not unrestricted
remote role writes. Retain six original HTTP exchanges for five stages,
source/request/candidate/profile pins, stage reports and all exec/inspect.
Agree how the peer independently observes/initiates the campaign and obtains
originals. Four health probes alone are not a synchronous five-stage receipt.
C4 use actual bounded timeout cleanup and new-job recovery. C5 must use B's
approved bad patch in an isolated snapshot, prove real validation rejection,
rollback and original Makefile hash, then run a new normal job. Never weaken
the DRAFT broker's exact generated patch check to permit arbitrary injection.
B's full-project make all + independent run case and repair scope remain
pending. No deployment, SSH authorization or token exchange performed by
this increment.


## Guarded real API regression

The E13 explicit-input regression can select --guarded-c8. It starts the
original private Docker API with a fresh Store; the client executes through
a distinct loopback session listener. The server checks one Store entry,
actual DRAFT exec/inspect and every downloaded artifact against the original.
CI generates a credential in memory and checks that it never occurs in
client originals. This is local real Docker validation, not SSH or B13
acceptance. The CLI additionally checks clean tracked source, candidate
bytes and both full Git commit objects before startup.

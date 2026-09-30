# 2026 DevOps A13

This repository is used for the 2026-Fall DevOps course project conducted by ISE, Nanjing University.

A13 is responsible for **BuildChecker** and **EChecker**. Paired group B13 is responsible for **DRAFT** and **MDFixer**.

## E2

Key files:

- `docs/E2/B13_DELIVERY.md`: A13 -> B13 contract delivery and point-by-point reply.
- `docs/E2/A13_E2_INTERNAL_GUIDE.md`: detailed internal guide for A13 members.
- `docs/E2/PAIR_REVIEW.md`: pair-review decisions and unresolved items.
- `docs/E2/BACKLOG.md`: remaining work and acceptance criteria.
- `docs/E2/ADR-*.md`: design decisions for the E2 contract.
- `contracts/schemas/`: A13-owned schemas.
- `contracts/examples/`: valid/invalid examples.
- `contracts/artifacts/`: repository-backed E2 sample artifacts.
- `scripts/validate_e2.py`: offline semantic validator.
- `tests/test_e2_contracts.py`: contract tests.

Pinned B13 proposal reviewed by A13:

- Repository: `ma058/2026-Devops-B13`
- Branch: `main`
- Commit: `af194c40ffd1394fb56cc9f5b2367b7feffb5a3b`

Run:

```bash
python scripts/validate_e2.py
python -m unittest discover -s tests -v
```

All service-specific values in `contracts/examples/` are **synthetic E2 examples**, not claims that BuildChecker/EChecker are already implemented.

## E4

The BuildChecker environment template is under `services/buildchecker/`. See
[`docs/E4/README.md`](docs/E4/README.md) for the setup and `make all` workflow.

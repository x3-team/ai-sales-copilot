# ai-sales-copilot

## Cursor Cloud specific instructions

- As of this environment setup, the repository is a skeleton: it contains only
  `README.md` with the project title. There is no application code, dependency
  manifest, tests, services, CI, Dockerfile, or `.cursor/environment.json` yet.
  There is therefore nothing to build, run, or test until source is added.
- Baseline toolchains preinstalled in the Cloud Agent VM: Node 22 (npm, pnpm,
  yarn via corepack), Python 3.12 (pip), Go 1.22, Rust 1.83. Docker and `uv` are
  not installed.
- The Cloud Agent update script is intentionally forward-looking and guarded: it
  auto-installs dependencies only when a standard manifest is present
  (`package.json` → pnpm/yarn/npm based on the lockfile; `requirements.txt` → pip;
  `go.mod` → go mod download) and is a safe no-op while the repo is empty. Once
  real code is added, prefer running the manifest's own scripts (lint/test/build/
  dev) and update this file with service-specific run instructions.

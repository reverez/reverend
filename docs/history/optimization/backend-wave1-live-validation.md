# Backend Wave 1 — Live workstation validation

Branch: `integration/backend-wave1`

Target workstation evidence collected on 2026-09-15 from WSL2 with Windows Ollama and an NVIDIA GeForce RTX 5070 (8151 MiB VRAM).

## Runtime live validation

### Gate R-LIVE-01 — cold to warm strong-code reuse

Status: PASS

Configuration:
- role sequence: `strong_code -> strong_code`
- model: `qwen3-coder:30b`
- context: 16384
- output cap: 32
- cold start: true

Observed:
- first run residency before: `unloaded`
- first provider load: 29.888600 s
- first total elapsed: 30.812368 s
- second run residency before: `resident`
- second provider load: 0.006187 s
- second total elapsed: 0.101804 s
- no unnecessary unload
- provider-reported VRAM: 6,215,654,440 bytes
- nvidia-smi after test: approximately 6104 MiB / 8151 MiB
- loaded context: 16384

Conclusion: Reverend correctly preserves and reuses the 30B strong-code model for repeated same-role requests. Cold model load dominates latency; warm reuse is effectively immediate.

### Gate R-LIVE-02 — strong/general/strong interleaving

Status: MEASURED — EVICTION CONFIRMED

Configuration:
- role sequence: `strong_code -> fast_general -> strong_code`
- strong model: `qwen3-coder:30b`
- fast model: `qwen3.5:4b`
- strong context: 16384
- fast context: 8192
- output cap: 32
- cold start: true

Observed:
- first strong provider load: 21.639117 s
- fast-general provider load: 8.079651 s
- after fast-general, only `qwen3.5:4b` remained loaded
- final strong residency before: `unloaded`
- final strong request explicitly unloaded `qwen3.5:4b`
- final strong provider load: 21.456956 s
- final strong total elapsed: 21.950956 s
- Windows RAM before: 31.43 GB total, 2.82 GB free
- Windows RAM after: 31.43 GB total, 3.07 GB free

Conclusion: on this workstation, the 30B and 4B models do not remain resident together. A `FAST_GENERAL` interleave evicts the 30B model, so returning to `STRONG_CODE` incurs a full ~21.5 s reload. This is hardware/provider behavior, not a failure of Reverend's exclusive scheduler. Session/routing policy should avoid unnecessary 30B -> 4B -> 30B switching during strong-code workflows if later optimization is justified.

### Gate R-LIVE-03 — 5-minute delayed retention

Status: PASS / EXPECTED EXPIRY CONFIRMED

Configuration:
- role sequence: `strong_code -> strong_code`
- delay: 330 seconds
- production keep-alive: 5m

Observed:
- first provider load: 23.042753 s
- second residency before: `unloaded`
- second provider load: 23.391766 s
- second total elapsed: 23.912336 s
- Windows RAM before: 31.43 GB total, 2.78 GB free
- Windows RAM after: 31.43 GB total, 3.54 GB free

Conclusion: the 5-minute policy expires before a 330-second return and forces a full reload.

### Gate R-LIVE-04 — 10-minute delayed retention

Status: PASS

Configuration:
- role sequence: `strong_code -> strong_code`
- delay: 330 seconds
- keep-alive: 10m

Observed:
- first provider load: 21.749719 s
- second residency before: `resident`
- second provider load: 0.002529 s
- second total elapsed: 0.195906 s
- provider-reported VRAM: 6,215,654,440 bytes
- nvidia-smi after test: approximately 6104 MiB / 8151 MiB
- Windows RAM before: 31.43 GB total, 3.30 GB free
- Windows RAM after: 31.43 GB total, 3.51 GB free

Conclusion: 10-minute retention eliminates the ~23-second reload for a 330-second return with no observed adverse RAM outcome in this experiment. The staging branch therefore promotes `STRONG_CODE` from 5m to 10m retention and locks the policy with a regression assertion.

## Runtime live-gate status

Completed:
- cold -> warm same-model reuse
- strong -> shared -> strong eviction measurement
- 5-minute delayed retention
- 10-minute delayed retention comparison

Pending:
- live M16 validation
- final live validation

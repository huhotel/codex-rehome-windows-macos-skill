# Codex ReHome: verified Windows → macOS extension

[中文](README.md) | [SKILL.md](SKILL.md) | [Test report](TEST-REPORT.md)

An independent MIT extension of [CalebYcj/codex-rehome-skill](https://github.com/CalebYcj/codex-rehome-skill). It provides an agent workflow and executable helpers; the upstream [ReHome Desktop](https://github.com/CalebYcj/codex-rehome) is a separate desktop product.

Migrate selected projects and conversations without replacing target login or configuration. Resolve physical rollout lineage, prove standalone history equivalence with the native reader, sanitize and map structural paths, rebuild byte offsets, and merge selected IDs with backups and idempotence checks. Desktop host/project membership and continuation are separate acceptance stages.

Download the Skill ZIP and SHA-256 from [Releases](https://github.com/huhotel/codex-rehome-windows-macos-skill/releases). Install the extracted `codex-rehome` folder under the actual `CODEX_HOME/skills/`, or ask Codex to read this repository's SKILL.md. Back up any existing skill first.

The executable profile is limited to `codex-cli 0.158.0-alpha.2.1`, `state_5.sqlite`, and `thread_history_1.sqlite`. Unknown versions require evidence-based adaptation. Do not bypass the profile gate or use legacy one-step scripts for selected Windows-to-Mac conversation migration.

Validation: 23 synthetic tests; 11 real histories and 19 physical segments with complete native equivalence and POSIX historical context checks. Generic-wrapper native tests ran in Windows isolation; actual Mac sidebar and continuation still require target-side acceptance. See [TEST-REPORT.md](TEST-REPORT.md) for scope and limitations.

```bash
python -m unittest discover -s scripts/verified/tests -v
```

Detailed operational documents are currently in Chinese: [workflow](references/windows-to-macos-verified.md), [desktop ownership](references/desktop-membership.md), [retrospective](references/repair-retrospective.md), and [installation](EXTENSION-README.md).

Only skill code and documentation are distributed. No real conversations, project data, credentials, private probes, or databases are included. Upstream attribution and MIT license are retained in [UPSTREAM.md](UPSTREAM.md) and [LICENSE](LICENSE).

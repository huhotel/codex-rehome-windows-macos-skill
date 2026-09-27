# Upstream and extension provenance

- Upstream: https://github.com/CalebYcj/codex-rehome-skill
- Local upstream base: 0b4db49eca3e241c53d8d9921af5d76d5f6dfdf6
- License: MIT; original LICENSE retained, Copyright (c) 2026 CalebYcj.
- Extension date: 2026-09-27.
- Published independently at https://github.com/huhotel/codex-rehome-windows-macos-skill. This is not an official upstream release or an upstream pull request.

The source checkout and earlier migration archives were preserved. The copied scripts/verify_mac_codex_restore.sh already contained the earlier local structural-path adaptation; this extension does not overwrite it with a fresh upstream script. The legacy instructions are retained under references/legacy-upstream-workflow.md, but SKILL.md now explicitly routes Windows-to-macOS conversation migration to scripts/verified/.

New workflow and helper code generalize the dependency, offset, URI, historical executor context, merge/idempotence, and local/remote ownership lessons from the migration and subsequent repairs. No private conversations, native executable, application source, credentials, or real environment probe artifacts are distributed here.

# Codex ReHome：Windows → macOS 增强版

[English](README.en.md) | [Skill 入口](SKILL.md) | [使用说明](EXTENSION-README.md) | [测试报告](TEST-REPORT.md)

迁移选定 Codex 项目与对话，递归验证分页历史依赖，证明完整历史可被原生读取，再合并恢复到 Mac。默认保留源数据、Mac 登录、配置和已有对话。

基于 [CalebYcj/codex-rehome-skill](https://github.com/CalebYcj/codex-rehome-skill) 的独立 MIT 增强版；保留上游许可证与工具。[ReHome Desktop](https://github.com/CalebYcj/codex-rehome) 是上游独立桌面产品，本仓库提供给 Codex/Agent 使用的工作流与脚本。

## 快速开始

下载 [Releases](https://github.com/huhotel/codex-rehome-windows-macos-skill/releases) 中的 Skill ZIP 与 SHA-256。把解压后的 `codex-rehome` 放入实际运行任务的 `CODEX_HOME/skills/`；默认 Mac 为 `~/.codex/skills/codex-rehome/`。已有同名 Skill 先备份，避免混用脚本。

也可直接让 Codex 读取本仓库的 `SKILL.md`：

> 请使用这个 Codex ReHome 增强版 Skill，把我的 Windows Codex 项目与选定对话迁移到 Mac。先确认源/目标环境和范围，递归检查历史依赖，证明完整原生读取，再生成带校验和与恢复说明的迁移包。保留源数据和 Mac 已有登录、配置、其他对话。

Windows→Mac 对话迁移必须走 `scripts/verified/`；不要绕过入口直接运行旧一键脚本。

## 增强能力

- 区分稳定对话 ID 与物理分段 ID，递归验证 history_base、记录序号和字节边界。
- 导出独立完整历史，比较原始依赖链和导出的完整原生内容/顺序，脱敏后再次验证。
- 支持结构字段路径映射、file URI、Windows 历史执行上下文和 Windows 长路径。
- 默认排除登录、Cookies、.env、私钥、.git、node_modules、虚拟环境和未经审计的压缩容器。
- 同 ID 合并修复、备份、重复恢复保护、提交后独立读取、失败状态和回退证据。
- 分开验收原生历史、项目/主机归属、Mac 侧栏和续聊。

## 适用范围与验证

可执行 profile：`codex-cli 0.158.0-alpha.2.1`、单一 `state_5.sqlite` 和 `thread_history_1.sqlite`。新版本或未知目标结构需先适配，不应只修改版本字符串跳过检查。

23 项合成回归通过；真实 11 条历史、19 个依赖分段、219,837 条非 metadata 记录完成原生等价检查，POSIX 历史上下文测试通过。通用封装的本轮原生测试在 Windows 隔离环境执行，不能代替真实 Mac 侧栏与续聊验收。详细证据和限制见 [TEST-REPORT.md](TEST-REPORT.md)。

```bash
python -m unittest discover -s scripts/verified/tests -v
```

## 文档

- [Windows→Mac 迁移流程](references/windows-to-macos-verified.md)
- [本地/远程与侧栏归属](references/desktop-membership.md)
- [修复复盘](references/repair-retrospective.md)
- [上游来源](UPSTREAM.md) 与 [MIT 许可证](LICENSE)

仓库和 Release 仅含 Skill、通用工具和文档，不包含真实对话、项目、认证信息、测试数据库或私有诊断副本。

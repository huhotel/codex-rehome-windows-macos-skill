# Windows → macOS 增强版使用说明

本目录是一个完整 Skill，入口是 `SKILL.md`。它基于 CalebYcj/codex-rehome-skill，保留 MIT 许可证与上游文件；增加一条严格、版本明确的 Windows→Mac 对话迁移路线。原上游工作流移入 references/legacy-upstream-workflow.md，仅作为其他方向的参考。

## 安装与调用

把整个 `codex-rehome` 文件夹放到目标 Codex 实际使用的 `CODEX_HOME/skills/` 下；默认 Mac 为 `~/.codex/skills/codex-rehome/`。已有同名 Skill 时先备份，勿把新旧脚本混在同一个目录。使用自定义 home 或远程连接时，先确定运行主机和实际 home。

也可以不安装，直接把本目录的 SKILL.md 路径给 Codex，明确要求读取并使用。

源 Windows 上的调用示例：

> 请使用 Codex ReHome Skill 的 Windows→macOS 增强流程。先确认源/目标环境，让我选项目与对话；递归审计历史依赖，证明导出完整历史与原历史原生读取等价；默认排除登录、Cookies、.env、私钥、.git、node_modules 和虚拟环境。保留源数据与旧包，生成带 SHA-256 和 Mac 恢复说明的迁移包。目标路径未知时先完成源端准备。

目标 Mac 上的调用示例：

> 请使用此 Skill 导入这个迁移包。先确认你实际运行在 Mac 本地及应用实际 Codex home，检查 CLI/profile，然后合并恢复，保留登录、配置与已有对话。先验证全部历史，再检查本地主机项目归属和侧栏。不要覆盖整库；若已有旧导入，先辨认需要修复的 ID。

Skill 是给 Codex 执行迁移任务的流程与工具；最终生成的包携带 restore-tools 和 Mac-恢复说明.md，可以在应用退出后独立终端运行，不要求恢复时 Codex 进程保持运行。侧栏和续聊验收仍需重新打开应用。

## 目录重点

- SKILL.md：唯一推荐入口与路由。
- references/windows-to-macos-verified.md：按阶段执行、命令、限制与交付。
- references/desktop-membership.md：本地/远程、legacy/server 项目 ID、侧栏修复。
- references/repair-retrospective.md：复盘、测试证据与适用范围。
- scripts/verified/：通用 Python 工具，无本案例线程 ID、用户名或机器路径硬编码。
- scripts/verified/tests/：纯合成回归案例，不包含私人对话。

当前可执行 profile：codex-cli 0.158.0-alpha.2.1、单一 state_5.sqlite、thread_history_1.sqlite。其他版本需检查并适配，不能直接改版本常量。新通用脚本的 Windows 原生测试与历史 Mac 实测分开记录；没有把未来版本、所有目标环境或所有对话续聊说成已经验证。

本增强版独立发布于 huhotel/codex-rehome-windows-macos-skill，尚未合并到上游。未上传任何迁移数据。私人历史、真实环境测试 home 和旧迁移包不在本 Skill 压缩包里。

---
name: codex-rehome
description: "Migrate selected Codex projects and conversations between computers, including verified Windows-to-macOS paginated history export, merge restore, old-import repair, and local/remote sidebar diagnosis. Use for Codex migration and recovery; preserve source data and target login/configuration."
---

# Codex ReHome — verified Windows → macOS extension

基于 CalebYcj/codex-rehome-skill 的 MIT 补充版本。迁移对象是用户明确选定的项目文件和对话；两者分别盘点、验证。不要把文件复制、SQLite 有记录或 CLI 能启动说成对话迁移成功。

## 先判断走哪条流程

- **Windows → macOS，包含对话或修复旧导入：必须先完整阅读 [windows-to-macos-verified.md](references/windows-to-macos-verified.md)。使用 `scripts/verified/`，不要运行旧的一键打包/恢复脚本作为替代。** 即使对话当前没有 history_base，也必须保留结构路径语义、原生读取和合并验收。
- 只迁移项目文件：仍用下方的范围和排除规则，无须读取或迁移用户整个 Codex home。
- 其他方向：上游工具保留在 `scripts/`，说明保留于 [legacy-upstream-workflow.md](references/legacy-upstream-workflow.md)。这是原流程参考，不是分页历史兼容性证明。先检查格式/版本；涉及 history_base 或文件内容重写时沿用本技能的依赖、偏移、真实读取原则，未经适配不得宣称支持。
- 侧栏不可见、项目出现但没有对话、目标连接了远程 Windows：先读 [desktop-membership.md](references/desktop-membership.md)。不要重新导入全量 home，不要依据“我在 Mac 上打开了窗口”推断当前任务在 Mac 执行。

当前可执行适配器针对实测 `codex-cli 0.158.0-alpha.2.1`、`state_5.sqlite`、`thread_history_1.sqlite` 和该版本 paginated rollout。它不是对未来版本的兼容承诺。版本不同、多个 state 库、经典/未知格式或未支持的目标依赖形态时停止写入，在新隔离目录建立适配和原生读取证据；不能跳过版本/完整性检查继续。

## 与用户确认的最小信息

一次性收集并复用已有回答：

1. 源系统、目标系统、实际运行主机与 Codex home；目标应用是 ChatGPT.app 中 Codex 还是独立 Codex.app。
2. 项目列表与对话列表：显示名称、稳定 ID、实际路径、数量，让用户选。用户选“某项目全部对话”时检查分页、归档和别名，报告最终 ID 集合，不自动把依赖源变成额外可见对话。
3. 私人传输方式。默认不打包登录、Cookies、`.env`、私钥、`.git`、`node_modules`、虚拟环境。额外大目录、压缩包、项目外附件单列，不静默扩范围。
4. 目标路径未知不阻止源端准备。恢复时才解析目标用户名，默认 `~/Documents/Codex-Restored-Projects/<项目名>`。不把源 Windows 用户名猜成 Mac 用户名。
5. 目标 CLI 实际路径和 `--version`。ChatGPT.app 已知示例：`/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex`；独立 Codex.app 可能不同，检查实际文件而不是猜路径。

## 不可省略的操作约束

- 源数据、原包只读；所有转换在新暂存目录。报告和 probe 含私密内容，不能上传公开位置。
- 递归核实 history_base 引用的**物理分段 ID**、元数据稳定 ID、真实文件、记录序号、UTF-8 字节边界。稳定 ID 相同不等于自循环；文件名子串匹配不能确定源。
- 优先导出每条选定对话独立的完整历史。只有已解析全部依赖、证明所有非 metadata 记录内容/顺序完整、并通过相同版本原生读取的转换，才允许消除 history_base。禁止直接删引用、截断 offset、伪造源或仅改 history_mode。
- 所有脱敏、序列化、换行和结构路径改写在重建 projection 之前完成。源端和 Mac 端都验证最终字节偏移。历史文本保留旧路径允许；`file:` URI、历史 CommandExecution 的 Windows cwd/parsed_cmd 组合必须遵守语义，不能整文件字符串替换。
- 完整原生读取使用隔离 home：读全部 turns/items 游标页并核对计数、内容、顺序哈希。只看 JSON、SQLite、索引、文件大小不算成功。任何失败保留诊断，不能改 expected 哈希让测试通过。
- 默认合并、保留 Mac auth/config/其他对话。已有相同 ID 默认保留；只有明确选定的坏导入可同 ID 修复，不造新 ID。不得使用 `--replace-codex-home`、`--replace-state` 或整库覆盖。
- 目标应用需关闭才能实际合并。先完成检查、脚本和可审阅命令，再让用户在独立终端执行；不要让正在承载本任务的应用退出后才准备脚本。
- 本地与远程记录按 host + ID + project + Codex home 识别。不要把远程 Windows 项目误归到 Mac 本地；不要写裸路径进 project-order；桌面 schema/ID 桥接不清楚就先诊断。

## 可执行流程与证据

详细参数及顺序见 Windows→Mac 指南，按需调用：

| 工具 | 用途 |
| --- | --- |
| `lineage.py` | 只读递归审计、独立候选导出、记录内容/顺序账本 |
| `stage_probe.py` | 创建仅含选定历史的独立 native home |
| `native_verify.py` | 版本门禁、全部分页原生读取、最终字节边界 |
| `prove_conversion.py` | 比较原始依赖链与未脱敏完整历史；绑定脱敏账本 |
| `assemble_package.py` | 绑定上述证据、过滤项目、生成包/manifest/SHA-256 |
| `restore_verified.py` | 目标路径改写、预检、备份、合并修复、重复恢复保护 |
| `verify_committed.py` | 复制已提交记录与投影，再次原生读取；不在真实 home resume |

助手还必须完成桌面本地主机归属检查。可执行适配器不会盲写全局 UI 字典；参考 [desktop-membership.md](references/desktop-membership.md) 检查实际版本并完成这一步，不能把文档说明当作已执行修复。

## 完成条件与交付

逐项报告：源/包完整性、依赖和偏移、全部选定原生完整历史、旧导入修复与重复恢复、Mac 本地侧栏、打开和续聊。每项标记“通过 / 失败 / 未验证”，写明验证主机与 CLI 版本。

交付迁移 ZIP、SHA-256、Mac 恢复说明、排除与冲突清单、逐对话验收、备份和回退位置。恢复命令应调用包里的 `restore-tools/restore_verified.py`，无需另外下载上游脚本覆盖适配。项目路径带空格时正确引用。

没有真实 Mac UI 观察就标记侧栏待验收；没有实际续聊就标记续聊未验证。用户说“好像好了”不能等同于每条都验证完成。历史缺失时列出具体源 ID 和受影响选定对话，不宣布完整恢复。

## 维护和回归

读 [repair-retrospective.md](references/repair-retrospective.md) 了解修复依据、仍有限制和测试边界。修改适配器后运行：

```text
python -m unittest discover -s scripts/verified/tests -v
```

然后在隔离目录用相同 CLI 跑转换等价、首次恢复、坏导入修复、重复恢复和提交后读取。新 CLI/schema profile 必须重新建立证据；禁止把当前版本字符串换掉就称为适配完成。

# Windows → macOS 迁移复盘与维护说明

## 问题不是复制漏了几个文件

最初流程覆盖了文件、索引、路径和数据库记录，却没有验证分页历史如何加载祖先分段，也没有把历史重写后的字节变化纳入验收。于是项目目录存在、11 条记录可查，但只有 3 条没有 history_base 的对话能打开，其余 8 条失败。

| 现象 | 已核实原因 | 本增强版的处理 |
| --- | --- | --- |
| missing source rollout | 选中的稳定对话 ID 不等于所有必要物理分段；祖先未随选定当前文件进入包 | 从 state 指定的当前文件出发递归闭包；精确匹配物理 ID、头部身份、cutoff 和 ordinal |
| 看似同 ID 自引用 | 当前文件的稳定 ID 与早先物理源 ID 重合，文件尾另有分段 ID | 分开建 stable/physical 身份，不按文件名子串或稳定 ID 判断循环 |
| cutoff past source rollout | 脱敏/JSON 重写减少字节，但保留旧 end_byte_offset | 完整展开并证明等价；目标改写完成后原生重建投影，再核对真实字节边界 |
| 轮数/item 数一致而哈希不同 | file URI 的 Windows cwd 与 POSIX path 混用；项目外 D 盘 read 被当相对路径 | 结构字段映射、URI 百分号处理；保留外部 Windows 历史命令上下文；不改 expected 来掩盖差异 |
| Python 3.9 写报告崩溃 | 后续自定义脚本调用 Path.write_text(newline=...) | write_bytes 写 UTF-8/LF；明确此问题来自自定义适配，不归咎于上游 open(newline=...) |
| 原生历史可读、项目可见但侧栏无对话 | native 项目 ID、legacy UI assignment、projectless 与 host membership 是不同层 | 本地主机定向诊断，检查 legacy→server 桥接，仅处理选定本地副本；保留远程与其他对话 |
| 原始历史 probe 只返回叶段却不报错 | 此 alpha profile 的祖先分页还依赖已有源投影 | 原始私有基线仅复制依赖物理 ID 投影；独立导出从空缓存重建；两者必须原生等价 |

这不是通过删除 history_base 修好：先取得完整依赖，保留全部非 metadata 记录和原有顺序，再消除已展开的继承边；转换账本和独立原生比较缺一不可。源缺失就失败，不造数据。

## 从个案代码变成可复用工具

- 去掉项目名、用户名、Windows/Mac 机器路径和选定 ID 常量；使用显式选择、路径别名、CLI、home 与目标目录参数。
- 打包器要求转换等价证明、脱敏候选账本和绑定候选字节的原生报告；拒绝把未脱敏 probe 装包。
- Windows 长路径使用 extended path I/O。排除 junction/reparse point、常见秘密文件、任意目录名的 pyvenv.cfg/conda-meta 环境与未经单独审计的压缩容器；扩展名为空的私钥也按内容排除。
- 项目文件冲突保留目标版本；同 ID 对话默认保留，仅明确列入 repair 的损坏旧导入更新。
- 事务内写入失败回滚；提交后读取失败单独标为 committed_but_unverified，并用 pending receipt 阻止自动重试跳过内容比较。
- 不能仅因某个不相关旧对话的 metadata 与当前 profile 不同，阻止整个选定集合；身份错误在选定依赖闭包上严格验证。
- 上游其他方向文件保留，入口明确把含对话的 Windows→Mac 路由到新工具，不用旧结构验证器冒充完整验收。

## 证据等级

1. **此前 Mac 实际恢复日志**：0.158.0-alpha.2.1，11/11 完整历史成功读取，8 修复、3 保留。后续侧栏修复日志 11/11、历史不变。用户随后反馈“好像是对的”；这不是逐条续聊或断开远程仍独立可用的全量证明。
2. **本次通用工具测试**：见 [TEST-REPORT.md](../TEST-REPORT.md)；纯合成单测、真实同版本 Windows 原生 reader、隔离合并/修复/重复恢复、故障注入分开记录。
3. **尚不能泛化的部分**：通用包装后的全部脚本没有再次在真实 Mac 上完整执行；新版 profile、经典历史格式、带依赖的健康目标已有对话需另行适配；Python 3.9 语法/API 检查不是该解释器的完整运行测试。

## 发布与后续适配

这是独立 MIT 增强分发，不是已合并上游 PR，也不是对所有 Codex 版本的一键兼容承诺。保留 LICENSE、UPSTREAM.md 和原始工作流。

新增 profile 时检查实际应用发行版、CLI/API/schema、原始依赖读取、独立转换、完整分页、最终偏移和 Mac UI 主机归属；用反例先证明验证器能够失败。不要仅替换版本常量、规范化掉新的差异字段或扩大迁移范围来让流程继续。

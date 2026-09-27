# Windows → macOS：项目与选定对话的严格迁移

## 适用边界

这是代理执行的完整流程，不是承诺对任意未来 Codex 版本通用的一键转换器。分页历史、原生读取与合并适配器已限定到 `codex-cli 0.158.0-alpha.2.1` 的已验证协议。目标版本不同，先检查目标生成的 API/SQLite schema，并在隔离样本上建立新 profile；不能把版本检查删掉继续运行。

一次事务处理一个明确的目标项目和任意数量的选定对话。多个项目分别规划；对话有多个目录别名时显式配置。不要把一个项目下所有源电脑对话默认全部打包，更不要把需要的历史祖先注册成额外对话。

## 1. 环境、范围、工作副本

确认源/目标 OS、实际执行主机、Codex home（含环境变量、junction/symlink）、应用发行版、内置 CLI 路径与版本、Python 版本、项目目录、选定 ID、传输方式。目标用户名未知时使用 `~/Documents/Codex-Restored-Projects/<project>` 占位，目标端再解析。保留 Windows 原数据和旧 ZIP；工作目录不能位于项目或 Codex home 内。

Mac 不一定安装独立 Codex.app。检查实际应用后再选 CLI，候选包括：

* `/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex`
* `/Applications/Codex.app/Contents/Resources/codex`

不要把候选路径当已验证事实，也不要认为独立应用的 `codex app` 会打开 ChatGPT.app。必须确认应用支持的打开项目入口。

原始历史和本地 probe 可能包含敏感内容；留在私有工作目录，不上传到公共仓库、不装进 Skill。默认排除登录信息、Cookies、`.env*`、私钥、`.git`、`node_modules`、虚拟环境、运行时缓存/套接字。对话 JSON 解码后脱敏；二进制内容和嵌套压缩包不能靠文本正则保证安全。新组装器默认排除未单独审计的压缩容器和链接，输出排除清单让用户知道缺哪些项目材料。

## 2. 解析完整物理历史链

先从只读 SQLite 确认选定 ID 的当前 `rollout_path`。不能用 `*<thread-id>*.jsonl` 的第一个结果。

在已验证 profile 中，文件名形如 `rollout-<time>-<stable-id>_<physical-id>.jsonl`；无后缀时 physical ID 与 stable ID 相同。用文件名语法、首条 session_meta.id/session_id、数据库当前文件三者交叉确认。`history_base.thread_id` 是依赖的物理 rollout ID；它与当前稳定对话 ID 相同，不自动构成自引用。

按 `(physical ID, cutoff ordinal, cutoff byte)` 递归解析；验证：

* 每个依赖存在且唯一，无真正的物理环；不通过改文件名伪造依赖。
* cutoff 不超过 EOF，恰好在完整 UTF-8/LF 或 CRLF 记录末尾。
* `end_ordinal_exclusive` 与最后一个记录序号对应，分段起点与父 cutoff 对应。
* 源文件在审计和复制期间没有变化。

使用 `scripts/verified/lineage.py --home <source-home> --thread-id <id> [--thread-id <id> ...] --report <new-audit.json> --export-dir <new-candidate-dir>`。

输出有缺失、重复、未知格式或边界错误时列出受影响的选定 ID 与物理 ID，停止相关导出。不得把 cutoff 截到 EOF，也不得降低记录数来让检查通过。

## 3. 独立完整历史及转换证明

首选独立完整历史。导出器先验证完整依赖，再按原顺序拼接所有必需的非 metadata 记录，保留原 ordinal（移除祖先 header 后的间隔不等于丢失消息），仅保留选定叶子的 header，将 header ordinal 设为 0，在完整展开后移除其 history_base。保留 history_mode。输出带原始/脱敏后的有序记录哈希、文件哈希和字节数。

这一步产生的是候选，不能因 JSON 能解析就宣布可迁移。必须证明：

1. 源链的每条必需记录恰好进入输出一次，顺序一致。
2. 差异仅为明确声明的 header 转换、秘密脱敏与结构路径映射；消息、命令文本、工具输出、标题不做全局路径替换。
3. 同版本原生读取器能加载转换后的全部 turns/items。
4. 私有未脱敏的完整源链与私有未脱敏独立导出经原生读取，其内容哈希一致。可用 `--private-unredacted-probe` 生成仅在本地用于等价对照的候选；组装器拒绝将这种候选打包。原始与脱敏版本之间则以逐记录变换证明解释差异，不能拿 Mac 失败输出重新生成 expected。

若必须保留分段，在每次序列化、脱敏、换行和路径改写完成后，以原 ordinal 对应关系重新计算所有依赖 cutoff；再递归验证。当前通用辅助脚本只支持完整展开路线，不会自动重写任意未知分段格式。

## 4. 路径语义：元数据与历史执行上下文

`migration_safety.py` 仅按结构字段映射，支持普通 Windows 路径和 `file:///C:/...` URI，处理百分号编码和中文/空格。原始文本里提到旧 Windows 路径不是错误，验证器不能要求整个 JSONL 无旧路径字符串。

历史 `CommandExecution` 的 cwd 决定 Codex 如何解释 `parsed_cmd` 里的路径。cwd 改成 POSIX 而留下 `D:/...`，会把 D 盘绝对路径当相对路径拼到 Mac 项目下。只读取选定项目文件的历史命令可映射；若包含映射范围外的 Windows 绝对读取路径，保留该历史命令的原 cwd 和整组 parsed_cmd，避免一组命令混用语法。当前 session_meta、turn context 和续聊工作目录仍映射到 Mac。

不要用把 D 盘文件假装放到 Mac 项目下、忽略 commandActions.path、修改 expected 哈希来绕过这类差异。项目外附件/技能/文件仍是历史引用，不等于已经迁移；有实际依赖时单独确认范围。

## 5. 原生读取：隔离、分页、固定预期

`stage_probe.py` 建立全新私有 Codex home，复制选定依赖的最小前缀或独立候选，用实际 CLI 初始化 SQLite schema，只登记选定线程。不会复制 auth/config。`native_verify.py` 拒绝默认真实 home，要求隔离标记与已验证 CLI 版本。

在探测副本中 `thread/resume` 建立 native projection，再调用 `thread/read`、全部游标页的 `thread/turns/list(itemsView=full)` 和 `thread/items/list`。空历史、重复 cursor、提前停止、任何选定线程缺失都是失败。不得向模型发新提示或执行历史命令来“激活”对话。

示例（命令中的路径与 ID 均由本次盘点填入）：

```text
python scripts/verified/stage_probe.py --source-home <home> --audit <audit.json> --output <new-probe-home> --codex <actual-cli> --flat-dir <sanitized-candidate>
python scripts/verified/native_verify.py --home <new-probe-home> --codex <actual-cli> --project-dir <isolated-existing-directory> --normalization-map <map.json> --report <new-native-report.json>
```

`map.json` 是显式的 `[原路径前缀, "<PROJECT>"]` 列表，覆盖授权的项目别名与目标拼写，不包含粗暴的全局 C:/D: 替换。原始依赖链 probe 不传 `--flat-dir`，读取时传 `--dependency-probe`，其边界由 lineage 审计负责。这个 profile 在空 projection 缓存中可能只列出叶分段而不报错，因此原始基线还复制源 history DB 中依赖闭包的物理 ID 投影（不含其他线程，仅存私有 probe）。独立完整导出必须从空缓存重建。仅 API 返回成功不能证明基线完整，必须通过 prove_conversion 对比全部内容/顺序；源投影缺失或不一致时停止，不能以叶段输出作为预期。

API 比较只规范化声明的项目路径，及该 profile 中重建缓存新增的顶层 item `startedAtMs/completedAtMs` 包装字段；不要丢弃真正 item/turn 内容。规范化变化需要独立证据。

Windows 端的验证必须额外覆盖 POSIX 历史 cwd。仅把源 Windows 路径改成另一个 Windows 盘符，不构成 Windows→Mac 路径测试。实际 Mac 读取是独立验收项。

序列化后验证所有 ordinal 对应字节边界、turn 起止位置、item 序号、投影完整 EOF 游标。resume 可能附加运行时 context，验证的是附加后的最终字节。

## 6. 项目文件及包组装

先分别对原始依赖链、未脱敏独立候选、脱敏独立候选建立三个全新 probe。前两者使用完全相同的显式 normalizer；不能把运行过的 probe 复用成新基线。用工具绑定原生等价证明：

```text
python scripts/verified/prove_conversion.py --raw-report <raw-native-report.json> --flat-report <private-flat-native-report.json> --private-flat <private-flat-directory> --sanitized-flat <sanitized-candidate> --output <conversion-proof.json>
```

它要求前两者完整原生输出一致，两个 probe 绑定同一源审计，未脱敏源记录/输出记录顺序哈希一致，脱敏候选仍来自相同源记录与数量。脱敏替换本身还须审查；原始私有 probe 与报告不交付。完成以上证明、脱敏记录审查和脱敏候选的 native 读取后，运行：

```text
python scripts/verified/assemble_package.py --source-home <home> --flat-dir <sanitized-candidate> --project <source-project> --source-alias <historical-project-root> --native-report <native-report.json> --equivalence-proof <conversion-proof.json> --output <new-package-directory>
```

参数 `--source-alias` 可重复。组装器验证 native 报告绑定的候选哈希；生成 threads.json、path_map.json、expected-native.json、conversion-proof.json、项目文件清单、restore-tools/、manifest、ZIP 和 SHA-256。normalization_map 随 native 报告固定，声明的项目别名必须被此报告覆盖；不要临时换 normalizer 或 expected。用户必须知道排除/冲突/附件缺失清单；二进制和自定义秘密格式还需审计。不要把未脱敏 probe、数据库原件、用户完整 home 或本次工作目录装进包。

Python 最低 3.9。UTF-8 报告用 `write_bytes`；不得使用 3.9 不支持的 `Path.write_text(newline=...)`。`open(..., newline=...)` 是另一接口，3.9 支持，不能误判。区分语法测试与真实 3.9 运行测试。

## 7. Mac 合并恢复与旧包修复

确认任务实际运行在 Mac 本机、目标 home 与应用打开的数据库一致。若从 Mac 连接 Windows 发起任务，不要在 Windows 侧把那次任务当目标恢复。目标应用先完成登录初始化，然后完全退出；若当前代理也会随应用退出，先准备独立脚本，让用户在独立终端运行。

```text
python <unpacked-package>/restore-tools/restore_verified.py --package <unpacked-package> --codex-home <actual-home> --project-dir <target-project> --codex <actual-bundled-cli>
```

默认保留已有相同 ID 的对话，避免覆盖目标上新增的 turns。修复已证实损坏的旧导入时，逐个加入 `--repair-thread-id <id>`，范围必须在选定列表内。正常对话保留，新的对话导入；重复恢复使用 receipt 校验前缀，不重复创建 ID、不覆盖续聊后的数据。

对保留对话还会预先检查目标已有投影的完整性；没有投影或投影过期时，在实际合并前停止，不在真实 home 运行 resume 来修复它。

适配器先校验整个包、在隔离 home 完成目标路径映射和 native 全历史读取，再备份目标 DB、旧选定文件、索引、登记文件与 receipt，最后合并同 ID 的选定记录和对应投影。其他对话、auth/config、项目冲突文件保留；若其他目标对话引用待替换物理历史，停止而不破坏它。失败回滚已经备份的选定状态。项目文件新增与冲突保持分开记录，回滚不声称删除已复制的新项目文件。

提交后适配器将选定记录、历史和实际投影复制到新隔离 home，不执行 resume，逐条读取全部页面并验证已提交字节。若此步失败，报告保留 merge_committed 标记与备份，receipt 标记 post_commit_verified=false 并保留 pending_expected_ids，后续自动重试拒绝继续；不得声称数据未写入或自动回滚完成，先检查备份做范围内修复。

适配器不会盲写桌面全局归属：这留给下一阶段根据目标应用实际 schema 完成。它输出 HISTORY MERGE PASSED，不输出“迁移全部成功”。已有保存 receipt 的目标目录变更/内容重写会拒绝执行，交由代理判断。

## 8. 本地/远程主机、项目与侧栏

按 [desktop-membership.md](desktop-membership.md) 完成此阶段。实际使用本地主机的 `project/list` 与 `thread/list(projectId=...)`，验证选定 ID 和本地 rollout。恢复后还要在隔离副本读取已经提交的数据，不能让验证器在真实 home resume 修复自己要验证的对象。

## 9. 验收与交付

至少报告六项：包/源完整性；依赖与字节边界；所有选定 native 全历史；合并修复/重复恢复/回滚；本地主机项目列表及侧栏；实际 Mac 续聊。没有用户或 UI 工具观察，就标记界面待验证。当前用户“看起来好了”只支持有限界面反馈，不自动证明离线独立性或每条续聊。

交付 ZIP、SHA-256、准确的 Mac 恢复命令、项目排除/冲突清单、逐 ID 验证报告、备份/回退位置和简短复盘。私人传输由用户完成；不自动上传。未知版本、缺失历史、同 ID 跨主机归属冲突等剩余限制必须单列。

## 当前适配器的保守限制

- 目标只能有一个 `state_5.sqlite`；多个 state 数据库时先确认应用实际使用者，不猜最高编号。CLI、核心表和当前 profile 不匹配时不继续。
- 默认保留的现有对话若自身仍有 history_base，或恢复后已被应用再次分段，本版适配器会在写入前拒绝。它不会因此破坏该对话。需为保留历史增加独立的依赖感知 staging/验证适配，不能给健康对话加 --repair-thread-id 强行覆盖。
- 为保护所有保留历史，恢复器保守收集目标所有分段的父引用（包括本次选中的分段）；新独立文件将遮蔽现存同 ID 的其他祖先，或存在可能被替换的稳定物理源时可能拒绝本可安全修复的案例。可做只读完整闭包分析后另行适配，不能删除引用绕过保护。
- 多项目用独立包/事务，receipt 按项目目标路径隔离；不把同 ID 对话重复导入不同项目。目标原有同 ID 属于不同来源时必须先诊断身份。
- 最低语法/API 目标 Python 3.9；语法测试不等于在每个 OS/Python 组合完成运行验收。
- 路径过长、Windows reparse point、项目打包中源发生变化都应单独检查。链接和 junction 默认排除。不要为迁移改动整个操作系统的长路径策略。

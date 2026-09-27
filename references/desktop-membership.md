# 桌面归属与本地/远程同 ID

## 不同层的证据

JSONL 保存历史；state SQLite 保存 native 线程/项目；history SQLite 保存投影；桌面登记保存 legacy 项目、主机与分区。某一层通过不能替代其他层。

先确认实际进程打开的 home。Mac 可在应用打开时只读运行：

```bash
lsof -nP -u "$USER" 2>/dev/null | grep -E '/(state_[0-9]+|thread_history_[0-9]+)\.sqlite'
```

只有项目出现但没有对话时，一次性收集必要值，而不是反复只收集字段名：

* 选定线程：id、cwd、rollout_path、project_id、archived、source、thread_source、originator、model_provider、分区、pin。
* projects、project_roots、本地主机 project/list 和按项目的 thread/list 结果。
* `.codex-global-state.json` 中 `local-projects`、`selected-project`、`selected-remote-host-id`、`app-server-project-id-by-legacy-project-id-by-host`、`app-server-projects-migration-by-host`、`project-order`。
* 仅选定 ID 的 `thread-project-assignments`、`thread-project-membership-host-ids`、`projectless-thread-ids`、workspace hints。

不要导出整个 persisted atom state、认证、连接密钥或其他对话正文。

## 已验证的兼容结构，不是永久 schema

在已测桌面版本中，local-projects 以 legacy 项目 ID 为键，字段为 id/name/rootPaths；数据库 project ID 可不同。必须通过 `local:<resolved-codex-home>` 下的 legacy→server 映射确认桥接，不能见两个 UUID 不同就替换。

局部历史修复后可能出现：数据库 8 条归属正确，但桌面 assignments 为 null、projectless 列表仍含这 8 条。历史 API 读取成功不能修复此问题。另有正常的 3 条可能只保留 legacy 归属而数据库 project_id 为空。数字只是案例，不是通用条件。

同一稳定 thread ID 可同时存在于本地恢复副本和远程 Windows 源。检查当前产品如何按 `(host, thread)` 区分对象；thread-ID-only 全局映射可能产生歧义。`selected-remote-host-id` 非空可能只是保存的选择，不足以单独证明当前项目来自远程。不得直接把所有主机标记改成 local，也不得自动断开当前代理赖以运行的连接。

## 修复步骤

1. 优先用当前应用提供的、主机明确的项目/对话接口完成归属，并验证本地主机列表。先检查接口语义，不能猜参数。
2. 如果只能使用持久化字段，必须验证当前版本 schema、实际目标主机和唯一项目根路径；备份 SQLite 和全局文件，应用退出后操作。
3. 针对选定本地副本补齐 database project_id、正确 legacy assignment 和 local membership；只移除这些 ID 的 projectless 标记。若已指向另一个项目/主机，停止自动覆盖，先判断同 ID 远程碰撞或用户主动移动。
4. 保留远程连接配置、选择、非选定归属、pin/section、其他项目顺序与未完成 migration 状态。项目顺序表若存 ID，不写文件路径。不能将含有非选定 pending IDs 的迁移标记整体设为完成。
5. 对 JSONL/history DB 做前后哈希或逻辑快照证明不变；SQLite 只修改经确认的 project_id 列，其余选定字段和全部无关行保持一致。测试重复应用与写入失败回滚。
6. 重新打开应用，在本机/Local 项目下逐条打开历史；需要时临时断开远程连接验证独立性，但不能删除连接配置或中断当前代理。

本机 CLI 列出全部 ID、应用展开项目能看见全部 ID、点击加载完整历史、续聊使用 Mac cwd 是四个不同检查。报告逐项状态。

## 不要采用的“快速修复”

* 仅因为 has_user_event=0 就改成 1：已测原生列表在该值为 0 时仍能列出完整对话。
* 把所有旧对话改成新时间让它们浮到顶部。
* 更换稳定 thread ID 来规避 UI 问题，却不验证 fork/parent、投影和主机引用。
* 整份回滚 global state/数据库覆盖用户的新数据。
* 反复导入相同历史试图解决项目显示问题。

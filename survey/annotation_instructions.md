# Annotation instructions

The written instructions given to the OpenAI Codex coding agents (gpt-6-astra and gpt-6-sol) that labelled the survey's failure paths, together with the codebook (`codebook.md`). The original Chinese text follows an English translation. File, script and field names refer to the study's working repository.

## English translation

The sample was frozen at commit cb034c9; the SHA256 of the list mcp-mainstream-sample-150.csv is in study-state.json. Stop extending the sample; only carry out the complete failure-path review of the assigned repositories (at most 30 per repository), audits and formal labels. Under the original rules of the codebook, semantic labels must not be generated automatically with regular expressions or keywords.

### Procedure

- Read only the fixed Git blobs in `mainstream/clones/owner--repo` and verify the full SHA; where Windows cannot check a file out, read it with git show, and do not exclude it for lack of a working tree.
- `scripts/extract_candidates.py repo...` generates candidates from the fixed source (the freeze gate has passed). Candidates are not labels. They can be extracted repository by repository without waiting for the whole batch.
- `scripts/annotation_store.py` provides append_labels, append_protocol and append_reviews; import it by adding mainstream/scripts to sys.path in your script. Each agent uses a unique agent_id (review1/review2/review3) and appends only its own labels, errata and audits.
- Write a few repositories to disk at a time; do not accumulate 50 repositories in memory. On finishing each repository call append_reviews(status='complete'). A repository with fewer than 30 paths must be reviewed over its full scope; one that reaches 30 must confirm the 31st qualifying path, give its location in the review notes and set truncated=true. Write zero only when there is no path that can actually be included; do not pass off "not found" or "not verified" as zero.
- Sort by file path in case-sensitive Unicode lexicographic order, then numeric line number, then failure_condition. An explicit failure branch in a shared helper counts only once; for a helper shared by several tools, write the full names of the tools it applies to and their actual descriptions. Exclude by code reachability and channel first, then truncate at 30. After truncation, do not continue exhausting the remaining paths.
- Include isError text, actual SDK exception conversion and explicit error structuredContent. Ordinary text not marked as an error, logs, start-up, client, unknown-tool and SDK pre-call argument validation do not enter the main table and are audited separately. Final JSON-RPC protocol errors are recorded separately with append_protocol; do not judge by the McpError class name.
- The Python SDK 2.2 hides the message of ordinary exceptions by default, while 2.0 still exposes it; the low-level Go Server.AddTool differs from the generic mcp.AddTool; the high-level TS McpServer differs from a direct setRequestHandler; Java and C# versions differ. Decide from the actual call chain and the exact version. Consult sdk-runtime-review, dependency-evidence and sdk-conversion-matrix; for versions the matrix does not cover, read the installed source or the public release package; do not guess.
- Save wrapper prefixes, multiple text blocks and interpolation as in the template actually returned. Mark unknown downstream text with contains_downstream_message. A hidden original throw message must not be treated as visible text. Leave a truly missing description blank and give the reason from the source; do not write one yourself.
- Required fields: repo, commit, file, line, failure_condition, tool, tool_description, text_template, states_cause, has_next_step, next_step_type, depends_on_caller_state, includes_stack_or_internal, includes_exception_type, contains_downstream_message, channel, notes. Mixed-language repositories must give implementation_language for each path. notes must contain the evidence of registration, reachability and conversion. Tokens are computed by the analyser.
- Judge next steps by the codebook: only an executable next step counts as "yes", and a next step must not be guessed from unknown downstream text. When a message suggests several steps, take the first and record the others in notes. Dependence on caller state is not the same as the correctness of the step.
- Append audits of excluded candidates and scope groups to `mainstream/annotations/audit-reviewN.jsonl` (you may write the jsonl yourself), with repo/commit/file/line or range/classification/reason. Do not overwrite in place.
- If an original label is found to be wrong, only append_errata; do not rewrite labels.
- For agiresearch/aios and getsentry/xcodebuildmcp, which appear with the same SHA in the earlier random sample, the audited valid labels may be reused, but first check that this round's scope and SDK agree, and mark the reuse source and record IDs explicitly; do not claim independent relabelling. Earlier labels for other repositories with different SHAs cannot be reused directly.
- Do not run any service or model API; dynamic checks are organised separately by the main thread. There is no need to create new tasks or wait for permission. Continue until the 50 assigned repositories are done, and after every 10 repositories report the number actually written to disk and the number remaining.

## Original text

样本已在 cb034c9 提交冻结，名单 mcp-mainstream-sample-150.csv 的 SHA256 在 study-state.json。停止采样扩展；只做分配仓库的完整失败路径审阅（每库最多30条）、审计和正式标签。按编码表原规则，不能用正则关键词自动生成语义标签。

## 操作

- 只读取 `mainstream/clones/owner--repo` 固定 Git blob，校验 full SHA；Windows无法checkout文件也用git show读，不以缺工作树排除。
- `scripts/extract_candidates.py repo...` 生成固定源码候选（冻结门禁已通过），候选不是标签。可按repo逐个提取，不必等全批。
- `scripts/annotation_store.py` 提供 append_labels、append_protocol、append_reviews；在脚本中把mainstream/scripts加入sys.path导入。每个代理用唯一agent_id（review1/review2/review3）；只追加各自标签/勘误/审计。
- 每次少量仓库落盘，不要在内存积攒50库。每库完成append_reviews(status='complete')，未满30须全scope审阅；达到30须确认31st合格后续路径并在review notes写明位置，truncated=true。只有无实际可纳入路径才可写零，不用“未找到/未核实”冒充零。
- 按文件路径区分大小写Unicode字典序、数值行号、failure_condition排序；共享helper显式失败分支只计一次，多工具共享写完整适用工具名及实际描述。先按代码可达性/通道排除再截30。截断后不继续穷尽后缀。
- 包含isError文本、实际SDK异常转换、明确错误structuredContent；普通未标错文本/日志/启动/客户端/未知工具/SDK前置参数校验不进主表，分别审计。协议JSON-RPC最终error独立append_protocol，不凭McpError类名判断。
- Python2.2默认普通异常隐藏消息，2.0仍暴露；Go低层Server.AddTool与泛型mcp.AddTool不同；TS高层McpServer与直接setRequestHandler不同；Java/C#版本不同。必须结合真实调用链+精确版本。参考sdk-runtime-review、dependency-evidence与sdk-conversion-matrix，matrix未覆盖的版本可读取安装源码或公开release包，不猜。
- 包装前缀/多文本块/插值按实际返回模板保存。含未知下游文字标记contains_downstream_message。隐藏的原throw文案不得当作可见文案。真正缺失描述留空并给源码缺失理由，不能自撰。
- 必填：repo,commit,file,line,failure_condition,tool,tool_description,text_template,states_cause,has_next_step,next_step_type,depends_on_caller_state,includes_stack_or_internal,includes_exception_type,contains_downstream_message,channel,notes；混合语言repo必须逐路径写implementation_language。notes必须含注册/可达性/转换证据。token由分析器算。
- 建议判断按编码表：可执行下一步才“是”，未知下游正文不能猜建议。建议多项取首个，其他记notes。调用方状态依赖不等同建议正确率。
- 候选排除/范围分组审计追加`mainstream/annotations/audit-reviewN.jsonl`（可自写jsonl），含repo/commit/file/line或范围/classification/reason。不要原地覆盖。
- 如发现原标签错误，只append_errata，不重写labels。
- 同SHA旧随机样本 agiresearch/aios、getsentry/xcodebuildmcp 可复用已审计有效标签，但先核对本轮scope/SDK一致，显式标reuse来源与记录ID，不假称独立重标。其他不同SHA不能直接复用旧标签。
- 不运行任何服务或模型API，动态验证由主线程另行组织。无需新建任务，不必等许可。持续完成分配50仓库；每10库报实际已落盘数量与剩余。

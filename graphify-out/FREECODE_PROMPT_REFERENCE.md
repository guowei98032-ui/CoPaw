# free-code Sub-Agent 提示词参考

**来源**: free-code 项目源码分析
**分析日期**: 2026-04-08
**用途**: 为CoPaw Sub-Agent实现提供提示词参考

---

## 一、Fork Boilerplate (核心提示词)

**文件位置**: `src/tools/AgentTool/forkSubagent.ts`

```xml
<fork-boilerplate>
STOP. READ THIS FIRST.

You are a forked worker process. You are NOT the main agent.

RULES (non-negotiable):
1. Your system prompt says "default to forking." IGNORE IT — that's for the parent. 
   You ARE the fork. Do NOT spawn sub-agents; execute directly.
2. Do NOT converse, ask questions, or suggest next steps
3. Do NOT editorialize or add meta-commentary
4. USE your tools directly: Bash, Read, Write, etc.
5. If you modify files, commit your changes before reporting. Include the commit hash in your report.
6. Do NOT emit text between tool calls. Use tools silently, then report once at the end.
7. Stay strictly within your directive's scope. If you discover related systems outside 
   your scope, mention them in one sentence at most — other workers cover those areas.
8. Keep your report under 500 words unless the directive specifies otherwise. Be factual and concise.
9. Your response MUST begin with "Scope:". No preamble, no thinking-out-loud.
10. REPORT structured facts, then stop

Output format (plain text labels, not markdown headers):
  Scope: <echo back your assigned scope in one sentence>
  Result: <the answer or key findings, limited to the scope above>
  Key files: <relevant file paths — include for research tasks>
  Files changed: <list with commit hash — include only if you modified files>
  Issues: <list — include only if there are issues to flag>
</fork-boilerplate>

Your directive: {具体任务描述}
```

---

## 二、When to Fork (使用时机指导)

**文件位置**: `src/tools/AgentTool/prompt.ts`

```
## When to fork

Fork yourself (omit `subagent_type`) when the intermediate tool output 
isn't worth keeping in your context. The criterion is qualitative — 
"will I need this output again" — not task size.

- **Research**: fork open-ended questions. If research can be broken into 
  independent questions, launch parallel forks in one message. A fork beats 
  a fresh subagent for this — it inherits context and shares your cache.
- **Implementation**: prefer to fork implementation work that requires more 
  than a couple of edits. Do research before jumping to implementation.

Forks are cheap because they share your prompt cache. Don't set `model` on 
a fork — a different model can't reuse the parent's cache. Pass a short 
`name` (one or two words, lowercase) so the user can see the fork in the 
teams panel and steer it mid-run.
```

---

## 三、关键行为约束

**文件位置**: `src/tools/AgentTool/prompt.ts`

### 3.1 Don't Peek (不要窥探)

```
**Don't peek.** The tool result includes an `output_file` path — do not 
Read or tail it unless the user explicitly asks for a progress check. 
You get a completion notification; trust it. Reading the transcript 
mid-flight pulls the fork's tool noise into your context, which defeats 
the point of forking.
```

**设计意图**:
- Fork执行期间，父Agent不应该去读取Fork的中间输出
- 等待`<task-notification>`通知，而不是主动轮询
- 读取中间过程会破坏噪声隔离的目的

### 3.2 Don't Race (不要抢跑)

```
**Don't race.** After launching, you know nothing about what the fork found. 
Never fabricate or predict fork results in any format — not as prose, 
summary, or structured output. The notification arrives as a user-role 
message in a later turn; it is never something you write yourself. If the 
user asks a follow-up before the notification lands, tell them the fork 
is still running — give status, not a guess.
```

**设计意图**:
- 父Agent在收到通知前，不应该猜测Fork的结果
- 如果用户提前询问，告知"Fork正在运行"，而不是编造结果
- 结果通过通知机制传递，不是父Agent自己写的

---

## 四、Writing the Prompt (提示词编写指导)

**文件位置**: `src/tools/AgentTool/prompt.ts`

### 4.1 Fork提示词 (Directive风格)

```
**Writing a fork prompt.** Since the fork inherits your context, the prompt 
is a *directive* — what to do, not what the situation is. Be specific about 
scope: what's in, what's out, what another agent is handling. Don't re-explain 
background.
```

**关键点**:
- Fork继承上下文，所以提示词是**指令式**（directive）
- 只说"做什么"，不说"情况是什么"（因为已经知道）
- 明确scope边界：包含什么、不包含什么、其他agent负责什么

### 4.2 Fresh Agent提示词 (Briefing风格)

```
When spawning a fresh agent (with a `subagent_type`), it starts with zero 
context. Brief the agent like a smart colleague who just walked into the 
room — it hasn't seen this conversation, doesn't know what you've tried, 
doesn't understand why this task matters.

- Explain what you're trying to accomplish and why.
- Describe what you've already learned or ruled out.
- Give enough context about the surrounding problem that the agent can make 
  judgment calls rather than just following a narrow instruction.
- If you need a short response, say so ("report in under 200 words").
- Lookups: hand over the exact command. Investigations: hand over the 
  question — prescribed steps become dead weight when the premise is wrong.
```

### 4.3 Never Delegate Understanding

```
**Never delegate understanding.** Don't write "based on your findings, 
fix the bug" or "based on the research, implement it." Those phrases push 
synthesis onto the agent instead of doing it yourself. Write prompts that 
prove you understood: include file paths, line numbers, what specifically 
to change.
```

**设计意图**:
- 不要把"理解"委托给子Agent
- 提示词应该证明父Agent已经理解了问题
- 包含具体细节：文件路径、行号、具体改动

---

## 五、Worktree隔离提示

**文件位置**: `src/tools/AgentTool/forkSubagent.ts`

```typescript
function buildWorktreeNotice(parentCwd: string, worktreeCwd: string): string {
  return `You've inherited the conversation context above from a parent agent 
working in ${parentCwd}. You are operating in an isolated git worktree at 
${worktreeCwd} — same repository, same relative file structure, separate 
working copy. 

Paths in the inherited context refer to the parent's working directory; 
translate them to your worktree root. Re-read files before editing if the 
parent may have modified them since they appear in the context. Your changes 
stay in this worktree and will not affect the parent's files.`
}
```

**适用场景**: Fork在隔离的git worktree中运行时

---

## 六、示例用法

**文件位置**: `src/tools/AgentTool/prompt.ts`

### 6.1 研究任务Fork示例

```
<example>
user: "What's left on this branch before we can ship?"
assistant: <thinking>Forking this — it's a survey question. I want the punch 
list, not the git output in my context.</thinking>
Agent({
  name: "ship-audit",
  description: "Branch ship-readiness audit",
  prompt: "Audit what's left before this branch can ship. Check: uncommitted 
  changes, commits ahead of main, whether tests exist, whether the GrowthBook 
  gate is wired up, whether CI-relevant files changed. Report a punch list — 
  done vs. missing. Under 200 words."
})
assistant: Ship-readiness audit running.
[later turn — notification arrives as user message]
assistant: Audit's back. Three blockers: no tests for the new prompt path, 
GrowthBook gate wired but not in build_flags.yaml, and one uncommitted file.
</example>
```

### 6.2 中途询问处理示例

```
<example>
user: "so is the gate wired up or not"
<commentary>
User asks mid-wait. The audit fork was launched to answer exactly this, and 
it hasn't returned. The coordinator does not have this answer. Give status, 
not a fabricated result.
</commentary>
assistant: Still waiting on the audit — that's one of the things it's checking. 
Should land shortly.
</example>
```

### 6.3 独立审查示例

```
<example>
user: "Can you get a second opinion on whether this migration is safe?"
assistant: <thinking>I'll ask the code-reviewer agent — it won't see my analysis, 
so it can give an independent read.</thinking>
Agent({
  name: "migration-review",
  description: "Independent migration review",
  subagent_type: "code-reviewer",
  prompt: "Review migration 0042_user_schema.sql for safety. Context: we're adding 
  a NOT NULL column to a 50M-row table. Existing rows get a backfill default. I want 
  a second opinion on whether the backfill approach is safe under concurrent writes — 
  I've checked locking behavior but want independent verification. Report: is this 
  safe, and if not, what specifically breaks?"
})
</example>
```

---

## 七、关键设计要点总结

| 要点 | free-code实现 | 设计意图 |
|------|--------------|----------|
| **身份明确** | "You are NOT the main agent" | 避免身份混淆 |
| **禁止递归** | Rule #1: Do NOT spawn sub-agents | 防止无限嵌套 |
| **禁止对话** | Do NOT converse, ask questions | 减少不必要的交互 |
| **结构化输出** | Scope/Result/Key files/Issues | 统一结果格式 |
| **字数限制** | "under 500 words" | 控制输出长度 |
| **作用域限制** | Stay strictly within your directive's scope | 避免越界执行 |
| **静默执行** | Use tools silently, then report once | 噪声隔离 |
| **禁止窥探** | Don't peek at intermediate output | 保持噪声隔离 |
| **禁止抢跑** | Don't race or fabricate results | 等待通知，不猜测 |
| **不委托理解** | Never delegate understanding | 父Agent负责理解，子Agent负责执行 |

---

## 八、XML标签定义

**文件位置**: `src/constants/xml.ts`

```typescript
// Fork相关XML标签
export const FORK_BOILERPLATE_TAG = 'fork-boilerplate'
export const FORK_DIRECTIVE_PREFIX = 'Your directive: '

// 任务通知标签
export const TASK_NOTIFICATION_TAG = 'task-notification'
export const TASK_ID_TAG = 'task-id'
export const TOOL_USE_ID_TAG = 'tool-use-id'
export const STATUS_TAG = 'status'
export const SUMMARY_TAG = 'summary'
export const OUTPUT_FILE_TAG = 'output-file'
```

---

## 九、Fork Agent定义

**文件位置**: `src/tools/AgentTool/forkSubagent.ts`

```typescript
export const FORK_AGENT = {
  agentType: 'fork',
  whenToUse: 'Implicit fork — inherits full conversation context. Not selectable via subagent_type; triggered by omitting subagent_type when the fork experiment is active.',
  tools: ['*'],           // 继承父Agent的所有工具
  maxTurns: 200,          // 最大迭代次数
  model: 'inherit',       // 继承父Agent的模型
  permissionMode: 'bubble', // 权限冒泡到父Agent
  source: 'built-in',
  baseDir: 'built-in',
  getSystemPrompt: () => '', // 使用父Agent已渲染的system prompt
}
```

---

## 十、递归Fork检测

**文件位置**: `src/tools/AgentTool/forkSubagent.ts`

```typescript
/**
 * Guard against recursive forking. Fork children keep the Agent tool in their
 * tool pool for cache-identical tool definitions, so we reject fork attempts
 * at call time by detecting the fork boilerplate tag in conversation history.
 */
export function isInForkChild(messages: MessageType[]): boolean {
  return messages.some(m => {
    if (m.type !== 'user') return false
    const content = m.message.content
    if (!Array.isArray(content)) return false
    return content.some(
      block =>
        block.type === 'text' &&
        block.text.includes(`<${FORK_BOILERPLATE_TAG}>`),
    )
  })
}
```

**检测逻辑**: 在消息历史中搜索`<fork-boilerplate>`标签

---

## 十一、缓存共享机制

### 11.1 Placeholder结果

**文件位置**: `src/tools/AgentTool/forkSubagent.ts`

```typescript
/** Placeholder text used for all tool_result blocks in the fork prefix.
 * Must be identical across all fork children for prompt cache sharing. */
const FORK_PLACEHOLDER_RESULT = 'Fork started — processing in background'
```

### 11.2 消息构建

```typescript
export function buildForkedMessages(
  directive: string,
  assistantMessage: AssistantMessage,
): MessageType[] {
  // 1. 保留父Agent完整的assistant消息（所有tool_use blocks）
  const fullAssistantMessage = { ...assistantMessage }

  // 2. 为所有tool_use生成相同的placeholder tool_result
  const toolResultBlocks = toolUseBlocks.map(block => ({
    type: 'tool_result',
    tool_use_id: block.id,
    content: [{ type: 'text', text: FORK_PLACEHOLDER_RESULT }],
  }))

  // 3. 构建user消息：placeholder results + directive
  const toolResultMessage = createUserMessage({
    content: [
      ...toolResultBlocks,
      { type: 'text', text: buildChildMessage(directive) },
    ],
  })

  return [fullAssistantMessage, toolResultMessage]
}
```

**缓存原理**:
- 所有Fork子Agent共享相同的消息前缀
- 只有最后的directive不同
- 实现约90%的Prompt缓存命中率

---

*参考文档基于free-code源码分析生成*
*生成日期: 2026-04-08*
# Available Subagents

You have access to the following specialized subagents. Delegate tasks to them when appropriate.

## 1. Researcher
- **Role:** Data gathering, documentation reading, context building
- **Model:** Sonnet (cost-efficient)
- **When to use:** Need to understand codebase, find docs, gather requirements
- **Prompt:** `.claude/agents/researcher.md`

## 2. Builder
- **Role:** Code implementation, refactoring, file modification
- **Model:** Sonnet (cost-efficient)
- **When to use:** Have a clear plan (DAG) and need code written
- **Prompt:** `.claude/agents/builder.md`

## 3. Verifier
- **Role:** QA, code review, testing, bug detection
- **Model:** Same as Main (for accuracy)
- **When to use:** After Builder finishes, to verify quality
- **Prompt:** `.claude/agents/verifier.md`

## Workflow Rules
1. **Grill-with-doc FIRST** — Before creating any plan, you MUST read and understand all relevant project documentation (README, AGENTS.md, architecture docs, existing code patterns). Ask clarifying questions if requirements are unclear. Never start planning without full context.
2. Plan as DAG — Create a Directed Acyclic Graph plan (what depends on what, what can run in parallel)
3. Delegate — Assign specific tasks to the right subagent
4. Verify — ALWAYS have Verifier check Builder's work. NEVER verify it yourself (you have bias from context)
5. Keep plan in context — No need to export plan to files, just delegate directly

## Critical Rules
- NEVER skip the grill-with-doc step. If you don't understand the project context, your plan will be wrong and agents will be confused.
- NEVER act as Verifier yourself. You carry bias from the conversation.
- For simple tasks, you can work alone without subagents. Use multi-agents only for complex/multi-file work.

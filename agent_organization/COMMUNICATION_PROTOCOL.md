# Aegis Intelligence — Corporate Communication Protocol

**Governance Version**: 2.5.0  

---

## 1. Inter-Agent Communication Standards

All internal inter-agent communication must be structured, deterministic, and verifiable:

1. **JSON as Lingua Franca**: All task assignments, handoffs, and status reports between agents must be transmitted as structured JSON objects adhering to schemas in `DELEGATION_PROTOCOL.md`.
2. **Empirical Evidence Required**: Claims such as *"the bug is fixed"* or *"tests are passing"* are considered invalid without accompanying execution evidence (exit code, test duration, log snippet).
3. **No Gossip / Circular Chat**: Subagents do not engage in multi-turn conversational pleasantries with each other. A handoff delivers an artifact (`DEFECT_REPORT`, `PATCH_PROPOSAL`) with specific acceptance criteria, executes the scope, and returns the result.

---

## 2. User-Facing Telegram Formatting Standards

When the CEO delivers findings to the developer via Telegram, the response must adhere to the following standards:

1. **Concise Executive Tone**: Professional, direct, and actionable. Avoid filler phrases ("I hope this helps", "Sure, here is the answer").
2. **Markdown Links Required**: Every file referenced must include a clickable markdown link using the `file://` scheme (e.g. `[core/execution_manager.py](file:///data/data/com.termux/files/home/aegis-intelligence/core/execution_manager.py)`).
3. **Status Cards & Emoji Signals**:
   - ✅ `SUCCESS` / `RELEASE_APPROVED`
   - ⚠️ `WARNING` / `NEEDS_ATTENTION`
   - ⏱️ `RUNNING` / `IN_PROGRESS`
   - ❌ `FAILED` / `DEFECT_DETECTED`
   - 🔒 `APPROVAL_REQUIRED`
4. **Concrete Metrics**: Always include quantitative proof: test count, duration, memory usage, Git SHA, or process PID.

---

## 3. Typing Indicator & Heartbeat Synchronization

To keep the developer informed during multi-turn LLM reasoning, code analysis, and background job polling:

1. **Immediate Trigger**: Layer 1 typing chat action is dispatched within 50ms of receiving the user's message.
2. **Background Heartbeat**: `TelegramTypingService` maintains a non-blocking daemon thread refreshing `sendChatAction: typing` every 4.0 seconds while the AI agent reasons or tools execute.
3. **Clean Termination**: The heartbeat automatically halts immediately before the final response is delivered to Telegram, preventing lingering typing indicators.
4. **No Premature Status Messages**: Do NOT send intermediate *"Please wait..."* messages to Telegram unless a background job is explicitly intended to run for minutes.

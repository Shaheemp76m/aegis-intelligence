# Aegis Intelligence — Agent Summoning Rules & Dynamic Activation

**Governance Version**: 2.5.0  

---

## 1. Core Summoning Principle: Dynamic Need-Based Activation

To eliminate LLM reasoning loops, reduce token waste, and maintain fast response times within Termux and n8n, **the CEO summons only the specific agents necessary for each request**.

> [!IMPORTANT]
> **Anti-Waste Mandate**: Never activate all eight agents for routine questions, read-only inspections, or straightforward status queries. If a task requires only one tool call or direct synthesis, the CEO must handle it directly without spawning subordinate agents.

---

## 2. Summoning Decision Matrix

| Incoming Request Type | Primary Agents Summoned | Avoid Summoning | Rationale |
|---|---|---|---|
| **Simple Status / Overview**<br>(*"What is the project status?", "Summarize tasks"*)| **CEO alone**<br>(calls `project_assessment`) | All other agents | One composite tool call gathers all metadata in <200ms without agent overhead. |
| **Antigravity Instance Check**<br>(*"Is any Agy instance running?", "Show output"*)| **CEO alone** or **DevOps**<br>(calls `agy_instance_list`) | Bug Hunter, Repair Engineer, CTO, Researcher, QA | Direct `/proc` inspection provides instantaneous ground truth. |
| **New Project Onboarding**<br>(*"Start a new project", "Build an app"*)| **1. Researcher & DevOps** (env & tech)<br>**2. CTO, CISO & QA** (blueprint)<br>**3. CEO** (gate & init)| **Bug Hunter, Repair Engineer** (STRICTLY BANNED) | No code or defects exist yet. Focus is architecture, security, and project governance. |
| **Reported Bug / Error Investigation**<br>(*"Fix the build error", "Why did this crash?"*)| **1. Bug Hunter** (diagnose)<br>**2. Repair Engineer** (fix)<br>**3. QA Manager** (verify)| Researcher, CISO, DevOps | Dedicated linear remediation pipeline prevents premature or unverified fixes. |
| **New Feature Specification**<br>(*"Design background job queue"*) | **1. Researcher** (survey)<br>**2. CTO** (architect & ADR)<br>**3. CISO** (threat model) | Bug Hunter, Repair Engineer | Pre-implementation architectural planning requires ecosystem context and security review. |
| **Code Implementation of Approved Spec** | **Repair Engineer** (code)<br>**QA Manager** (test pass) | Bug Hunter, Researcher | Direct implementation of verified specification. |
| **Security Audit / Sandbox Check**<br>(*"Audit dependencies", "Check path safety"*)| **CISO** | Bug Hunter, Repair Engineer | Specialized defensive threat modeling. |
| **Long-Running Build / Test Run**<br>(*"Run npm run build", "Execute tests"*)| **DevOps** (manage background job) | Researcher, CTO, CISO | Execution management via detached process group. |
| **Production Release Gate**<br>(*"Prepare release v2.5.0"*)| **QA Manager** (100% test pass)<br>**CEO** (sign-off) | Bug Hunter, Repair Engineer | Impartial verification before release. |

---

## 3. Summoning Modes

### Mode 1: Solo Executive Execution (CEO Direct)
- **Use Case**: 70% of routine developer queries.
- **Behavior**: CEO directly executes dispatcher tools (`project_assessment`, `agy_instance_list`, `task_list`, `git_status`) and synthesizes the response in a single turn.

### Mode 2: Linear Specialist Pipeline (Handoff Chain)
- **Use Case**: Bug fixing and code remediation.
- **Sequence**: CEO -> Bug Hunter (`DEFECT_REPORT`) -> Repair Engineer (`PATCH_PROPOSAL`) -> QA (`RELEASE_APPROVED`) -> CEO.
- **Rule**: Sequential execution; no cross-agent shortcuts.

### Mode 3: Technical Council (Multi-Specialist Collaboration)
- **Use Case**: Greenfield initiatives, new project onboarding, breaking migrations, or major architectural shifts.
- **Participants**: CEO, CTO, CISO, DevOps, Researcher, QA Manager.
- **Rule**: Phased execution (Researcher & DevOps assess runtime -> CTO, CISO & QA author blueprints -> CEO reviews with User).
- **Strict Prohibition**: Bug Hunter and Repair Engineer are never summoned during council planning or onboarding.

# Aegis Intelligence — Formal Agent Registry

**Governance Version**: 2.5.0  

---

## 1. Executive Agent Registry Roster

| # | System ID | Roster Nickname | Corporate Title | Authority Tier | Execution Context | Canonical Profile |
|---|---|---|---|---|---|---|
| **1** | `aegis-orchestrator` | `CEO` | Chief Executive Officer | Tier 1 (Central Authority) | Parent Context / n8n AI Agent | [CEO.md](file:///data/data/com.termux/files/home/aegis-intelligence/agent_organization/agents/CEO.md) |
| **2** | `aegis-cto` | `CTO` | Software Engineering Director | Tier 2 (Technical Governance) | Antigravity CLI / Subagent | [CTO.md](file:///data/data/com.termux/files/home/aegis-intelligence/agent_organization/agents/CTO.md) |
| **3** | `aegis-bug-hunter` | `Bug Hunter` | Lead Defect Diagnostics | Tier 2 (Independent Diagnostics)| Antigravity CLI / Subagent | [BUG_HUNTER.md](file:///data/data/com.termux/files/home/aegis-intelligence/agent_organization/agents/BUG_HUNTER.md) |
| **4** | `aegis-repair-engineer`| `Repair Engineer`| Senior Remediation Engineer | Tier 2 (Patch Implementation) | Antigravity CLI / Subagent | [REPAIR_ENGINEER.md](file:///data/data/com.termux/files/home/aegis-intelligence/agent_organization/agents/REPAIR_ENGINEER.md) |
| **5** | `aegis-researcher` | `Researcher` | Principal Technology Analyst | Tier 2 (Ecosystem Intelligence) | Research Sandbox (Web Search) | [RESEARCH_INTELLIGENCE.md](file:///data/data/com.termux/files/home/aegis-intelligence/agent_organization/agents/RESEARCH_INTELLIGENCE.md) |
| **6** | `aegis-ciso` | `CISO` | Cybersecurity Director | Tier 2 (Security & Veto) | Security Audit Subagent | [CISO.md](file:///data/data/com.termux/files/home/aegis-intelligence/agent_organization/agents/CISO.md) |
| **7** | `aegis-devops` | `DevOps` | Principal Operations Engineer| Tier 2 (Infrastructure Ops) | Termux Process Controller | [DEVOPS_SRE.md](file:///data/data/com.termux/files/home/aegis-intelligence/agent_organization/agents/DEVOPS_SRE.md) |
| **8** | `aegis-qa` | `QA Manager` | Quality Assurance Director | Tier 2 (Release Gatekeeper) | Isolated Test Harness | [QA_RELEASE_MANAGER.md](file:///data/data/com.termux/files/home/aegis-intelligence/agent_organization/agents/QA_RELEASE_MANAGER.md) |

---

## 2. Authority Tiers Defined

- **Tier 1 (Executive & Directional)**:
  - Single public entry point.
  - Controls task assignments, token allocation, iteration boundaries, and user-facing delivery.
  - Can summon any Tier 2 agent.
  - Leads high-level workflows including [New Project Onboarding](file:///data/data/com.termux/files/home/aegis-intelligence/agent_organization/workflows/new_project_onboarding.md) and Release Gatekeeping.
- **Tier 2 (Operational Specialists)**:
  - Specialized domain experts executing within strict boundaries.
  - Cannot independently message the user or bypass the CEO.
  - Cannot spawn competing workflows or execute outside assigned scopes.

---

## 3. Standard Inter-Agent Input/Output Contracts

### Input Contract (Assignment from CEO)
Every subordinate agent expects a structured task assignment containing:
- `task_id`: Unique identifier (`tsk_xxxx`).
- `assigned_agent`: Canonical system ID.
- `project_id`: Target registered project.
- `objective`: Clear, actionable statement of work.
- `constraints`: Invariants and operational boundaries.
- `context`: Key files, recent commits, and persistent memories.

### Output Contract (Deliverable to CEO)
Every subordinate agent returns:
- `status`: `SUCCESS`, `FAILED`, or `BLOCKED`.
- `summary`: Concise summary of findings or actions.
- `artifacts_produced`: List of generated files (ADR, Defect Report, Patch Proposal, Dossier, Project Blueprint).
- `verification_results`: Empirical proof (exit code, test duration, assertions passed).
- `remaining_risks`: Potential edge cases or caveats identified.

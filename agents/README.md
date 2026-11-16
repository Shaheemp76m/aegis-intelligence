# Aegis Intelligence — Specialized Agent Catalog & Corporate Governance

**System Version**: 2.5.0  
**Host Environment**: Termux on Android (Linux aarch64, Python 3.14.10)  
**Governance Framework**: Eight-Agent Autonomous Technology Company  

---

## 1. Executive Organization Hierarchy

Aegis functions as a complete, AI-operated technology company structured into eight specialized executive and operational roles:

```
                               [ USER ]
                                  │
                                  ▼
                    ┌───────────────────────────┐
                    │          1. CEO           │ (Central Orchestrator & Strategy)
                    │    (aegis-orchestrator)   │
                    └─────────────┬─────────────┘
                                  │
         ┌────────────────────────┼────────────────────────┐
         ▼                        ▼                        ▼
┌───────────────────┐    ┌───────────────────┐    ┌───────────────────┐
│      2. CTO       │    │     6. CISO       │    │   7. DevOps/SRE   │
│ (Architecture &   │    │ (Security & Path  │    │  (Agy Instances,  │
│  Code Governance) │    │   Enforcement)    │    │  Jobs & Health)   │
└────────┬──────────┘    └───────────────────┘    └───────────────────┘
         │
         ├────────────────────────────────────────┐
         ▼                                        ▼
┌───────────────────┐                    ┌───────────────────┐
│   3. Bug Hunter   │                    │ 5. Research &     │
│ (Defect Discovery │                    │    Intelligence   │
│  & Diagnostics)   │                    │ (Ecosystem & Docs)│
└────────┬──────────┘                    └───────────────────┘
         │ (Handoff: DEFECT_REPORT)
         ▼
┌───────────────────┐
│ 4. Repair Engineer│
│   (Bug Fixing &   │
│   Remediation)    │
└────────┬──────────┘
         │ (Handoff: PATCH_PROPOSAL)
         ▼
┌───────────────────┐
│ 8. QA/Release Mgr │
│ (Testing, Audits  │
│  & Verification)  │
└────────┬──────────┘
         │
         ▼
[ CEO Final Synthesis & User Delivery ]
```

---

## 2. Agent Roster & Responsibility Matrix

| # | Role / File | Corporate Title | Primary Mission | Key Boundaries & Prohibitions |
|---|---|---|---|---|
| **1** | [aegis-orchestrator.md](file:///data/data/com.termux/files/home/aegis-intelligence/agents/aegis-orchestrator.md) | **CEO** | Strategy, intent parsing, need-based agent activation, inter-agent synthesis. | Never activates all agents for trivial tasks; never claims success without proof. |
| **2** | [aegis-cto.md](file:///data/data/com.termux/files/home/aegis-intelligence/agents/aegis-cto.md) | **CTO** | Technical architecture, ADRs, engineering standards, and code review. | Does not perform routine bug hunting or direct manual code patching. |
| **3** | [aegis-bug-hunter.md](file:///data/data/com.termux/files/home/aegis-intelligence/agents/aegis-bug-hunter.md) | **Bug Hunter** | Defect discovery, stack trace analysis, isolated reproduction, root-cause isolation. | **NEVER applies code fixes directly.** Does not modify production code. |
| **4** | [aegis-repair-engineer.md](file:///data/data/com.termux/files/home/aegis-intelligence/agents/aegis-repair-engineer.md) | **Repair Engineer** | Atomic fix implementation, regression test creation, minimal surgical patches. | **NEVER marks its own work resolved.** Hands off to QA for verification. |
| **5** | [aegis-researcher.md](file:///data/data/com.termux/files/home/aegis-intelligence/agents/aegis-researcher.md) | **Research & Intelligence** | Multi-source ecosystem research (GitHub, docs, Stack Overflow, Reddit, CVEs). | **ZERO fabrication of sources.** Read-only operation; does not edit code. |
| **6** | [aegis-ciso.md](file:///data/data/com.termux/files/home/aegis-intelligence/agents/aegis-ciso.md) | **CISO** | Path sandboxing, secret protection, approval gates, dependency audits, security veto. | Strictly defensive. Vetoes unsafe or unapproved high-risk operations. |
| **7** | [aegis-devops.md](file:///data/data/com.termux/files/home/aegis-intelligence/agents/aegis-devops.md) | **DevOps / SRE** | Antigravity instances, background jobs, Termux resources, SQLite WAL, recovery. | Strictly loopback bound. Never terminates unrelated system processes. |
| **8** | [aegis-qa.md](file:///data/data/com.termux/files/home/aegis-intelligence/agents/aegis-qa.md) | **QA / Release Manager** | 100% test pass rate enforcement, independent fix verification, release gate sign-off. | Impartial verification authority. Rejects failing builds back to Repair Engineer. |

---

## 3. Strict Inter-Agent Handoff Chains

### A. Defect Remediation Flow
1. **CEO** receives user defect alert or error trace -> assigns to **Bug Hunter**.
2. **Bug Hunter** reproduces in isolated test environment, isolates root cause, and generates `DEFECT_REPORT`.
3. **Repair Engineer** ingests `DEFECT_REPORT`, implements minimal atomic fix, creates regression test, and submits `PATCH_PROPOSAL`.
4. **QA/Release Manager** independently executes full regression suite, verifies fix efficacy, and signs off on release.
5. **CEO** marks bug resolved in database and delivers completion report to user.

### B. Feature & Architecture Flow
1. **CEO** receives architectural initiative -> activates **CTO** and **Researcher**.
2. **Researcher** conducts ecosystem survey (GitHub, official docs, Reddit, CVEs) and authors Research Dossier.
3. **CTO** reviews dossier, drafts Architectural Decision Record (ADR), and produces technical specification.
4. **CISO** performs threat modeling on the specification.
5. **DevOps** verifies resource feasibility and deployment constraints.
6. **CEO** presents consolidated plan to user.

---

## 4. Operational Principles & Constraints

1. **Deterministic Aggregation Over Granular Loops**: Use composite tools (`project_assessment`, `agy_instance_list`) to conserve token context.
2. **Zero Database Contamination**: All test suites must inherit from `IsolatedTestCase`.
3. **Bytecode Prevention**: Always execute Python tasks with `-B` flag.
4. **Localhost Isolation**: The Aegis daemon must strictly bind to `127.0.0.1:8765`.

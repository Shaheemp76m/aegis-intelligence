# Aegis Intelligence — Standard Workflow Catalog

**Governance Version**: 2.5.0  

---

## 1. Catalog Summary Index

Aegis implements ten standardized, multi-agent operating workflows. Each workflow defines entry triggers, participant agents, step-by-step procedures, and required artifacts.

| # | Workflow Name | Participant Agents | Trigger Condition | Output Deliverable | Detailed Spec |
|---|---|---|---|---|---|
| **1** | **Bug Investigation** | CEO, Bug Hunter | Error trace, failing test, user report | `DEFECT_REPORT` (root cause, repro) | [bug_investigation.md](file:///data/data/com.termux/files/home/aegis-intelligence/agent_organization/workflows/bug_investigation.md) |
| **2** | **Bug Repair** | CEO, Repair Engineer, QA | Verified `DEFECT_REPORT` | `PATCH_PROPOSAL` & Regression Test | [bug_repair.md](file:///data/data/com.termux/files/home/aegis-intelligence/agent_organization/workflows/bug_repair.md) |
| **3** | **Feature Development**| CEO, CTO, Researcher, Repair, QA | User feature request | Architecture Spec, Code, Tests | [feature_development.md](file:///data/data/com.termux/files/home/aegis-intelligence/agent_organization/workflows/feature_development.md) |
| **4** | **Security Audit** | CEO, CISO | Pre-release check, dependency audit| Security Audit Report, Threat Model| [security_audit.md](file:///data/data/com.termux/files/home/aegis-intelligence/agent_organization/workflows/security_audit.md) |
| **5** | **Technology Research**| CEO, Researcher, CTO | Technical decision, framework update| 9-Section Research Dossier | [technology_research.md](file:///data/data/com.termux/files/home/aegis-intelligence/agent_organization/workflows/technology_research.md) |
| **6** | **Performance Tuning** | CEO, DevOps, CTO | High latency, memory pressure in Termux| Performance Profile & Tuning Patch | [performance_optimization.md](file:///data/data/com.termux/files/home/aegis-intelligence/agent_organization/workflows/performance_optimization.md) |
| **7** | **Build & Deployment** | CEO, DevOps | `npm run build`, packaging, installs | Job Logs, Exit Code, Telegram Alert| [build_and_deployment.md](file:///data/data/com.termux/files/home/aegis-intelligence/agent_organization/workflows/build_and_deployment.md) |
| **8** | **Project Health Check**| CEO | Daily standup, project audit | Single-Call Assessment Card | [project_health_check.md](file:///data/data/com.termux/files/home/aegis-intelligence/agent_organization/workflows/project_health_check.md) |
| **9** | **Release Management** | CEO, QA Manager, CISO | Production release milestone | 100% Test Pass Sign-off, Changelog | [release_management.md](file:///data/data/com.termux/files/home/aegis-intelligence/agent_organization/workflows/release_management.md) |
| **10**| **New Project Onboarding**| CEO, Researcher, CTO, CISO, QA, DevOps | *"Start a new project"*, *"Build an app"* | Project Blueprint, Git Init, 11 Docs | [new_project_onboarding.md](file:///data/data/com.termux/files/home/aegis-intelligence/agent_organization/workflows/new_project_onboarding.md) |

---

## 2. Standard Workflow Composition

Each workflow adheres to the five-stage execution lifecycle:
1. **Intake & Triage**: CEO assesses request and verifies preconditions.
2. **Specialist Execution**: Target agent executes with sandboxing and audit logging.
3. **Verification**: QA or CISO independently validates output against assertions.
4. **Handoff / Synthesis**: Artifacts recorded in persistent SQLite memory or disk.
5. **User Delivery**: Formatted summary delivered via Telegram webhook.

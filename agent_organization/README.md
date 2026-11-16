# Aegis Intelligence — Corporate Agent Organization

**Governance Version**: 2.5.0  
**Host Environment**: Termux on Android (Linux aarch64, Python 3.14.10)  
**System Architecture**: Eight-Agent Autonomous Technology Company  
**Orchestration Engine**: Antigravity CLI (`agy` v1.5.8) & n8n 2.47.4  

---

## 1. Overview & Vision

`agent_organization/` defines the governance, organizational structure, operational protocols, executive roles, and standardized workflows for **Aegis Intelligence**. Rather than deploying a monolithic, unstructured AI assistant that attempts every software task in a single context window, Aegis operates as a complete, autonomous software technology company with eight specialized executive roles and distinct separation of responsibilities.

This repository structure codifies the rules of engagement, delegation contracts, role-based access control, summoning criteria, and end-to-end execution lifecycles that govern all autonomous actions.

---

## 2. Directory Architecture

```
agent_organization/
├── README.md                      # Master overview & governance index (this document)
├── ORGANIZATION_CHART.md          # Hierarchy, reporting chains, and escalation paths
├── AGENT_REGISTRY.md              # Formal roster, authority tiers, and system IDs
├── SUMMONING_RULES.md             # Need-based dynamic activation & anti-waste rules
├── DELEGATION_PROTOCOL.md         # Strongly-typed delegation & response contracts
├── WORKFLOW_CATALOG.md            # Index of standardized multi-agent workflows
├── PERMISSION_MATRIX.md           # Tool RBAC, risk levels, and security gates
├── COMMUNICATION_PROTOCOL.md      # Inter-agent messaging & evidence standards
├── EXECUTION_LIFECYCLE.md         # 5-stage request-to-delivery lifecycle
│
├── agents/                        # Detailed executive role definitions (17 standard sections)
│   ├── CEO.md                     # Aegis Orchestrator (Strategy & Coordinator)
│   ├── CTO.md                     # Software Engineering Director (Architecture & ADRs)
│   ├── BUG_HUNTER.md              # Defect Discovery & Diagnostics (Root-cause isolation)
│   ├── REPAIR_ENGINEER.md         # Bug Fixing & Remediation (Minimal atomic patches)
│   ├── RESEARCH_INTELLIGENCE.md   # Technology Research & Intelligence (Evidence dossiers)
│   ├── CISO.md                    # Cybersecurity Director (Path sandboxing & Veto power)
│   ├── DEVOPS_SRE.md              # Infrastructure & Operations (Agy instances & jobs)
│   └── QA_RELEASE_MANAGER.md      # Testing & Quality Assurance (100% test pass enforcement)
│
└── workflows/                     # Standard operating execution workflows
    ├── bug_investigation.md       # Defect intake, reproduction, and diagnosis
    ├── bug_repair.md              # Surgical patching and regression testing
    ├── feature_development.md     # Architecture, specification, and implementation
    ├── security_audit.md          # Path sandboxing, secrets, and dependency audits
    ├── technology_research.md     # Multi-source intelligence & trade-off analysis
    ├── performance_optimization.md# Mobile profiling, memory, and database WAL tuning
    ├── build_and_deployment.md    # Asynchronous background builds and log streaming
    ├── project_health_check.md    # Single-call composite project assessment
    ├── release_management.md      # Full-suite verification and release gate sign-off
    └── new_project_onboarding.md  # Greenfield project discovery, blueprint & 11 docs initialization
```

---

## 3. Core Corporate Operating Principles

1. **CEO as Single Entry Point**: All external requests originate through the CEO (`aegis-orchestrator`). Subagents never independently communicate with the user without CEO review.
2. **Dynamic Need-Based Summoning**: The CEO summons only the specific specialists required for the task. Trivial queries (such as checking project status or listing running instances) are resolved immediately by the CEO.
3. **Strict Separation of Duties**:
   - The agent that discovers and reproduces a bug (**Bug Hunter**) never writes application code fixes.
   - The agent that writes the fix (**Repair Engineer**) never marks its own finding as resolved.
   - The agent that verifies the fix and approves release (**QA Manager**) operates with total independence.
   - During new project onboarding, **Bug Hunter** and **Repair Engineer** are strictly banned.
4. **Zero Fabrication Policy**: The Research Agent never invents sources, URLs, library versions, or benchmark metrics.
5. **Localhost & Security Isolation**: The daemon binds strictly to `127.0.0.1:8765`. High-risk operations require explicit human approval tokens.
6. **Empirical Evidence Over Claims**: No task is declared complete without verifiable proof (passing test exit codes, live query counts, verified log files).

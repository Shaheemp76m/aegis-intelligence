# Aegis Intelligence — Formal Skill Registry (`SKILL_REGISTRY.md`)

**Governance Version**: 2.0.0  
**Catalog Source**: [skill_system/skill_catalog.json](file:///data/data/com.termux/files/home/aegis-intelligence/skill_system/skill_catalog.json)  
**Total Cataloged Skills**: 307  
**Total Curated Bundles**: 6  
**Total Canonical Aliases**: 60  
**Locally Vaulted Core Skills**: 24  

---

## 1. Skill Categories & Distribution

The 307 cataloged skills span 9 primary functional categories:

| Category | Skill Count | Primary Target Agents | Representative Skills |
|---|---|---|---|
| **`development`** | 104 | Repair Engineer, CTO, Bug Hunter | `fastapi-pro`, `python-pro`, `typescript-pro`, `react-modernization`, `debugger`, `code-refactoring-refactor-clean` |
| **`infrastructure`** | 41 | DevOps/SRE | `bash-pro`, `deployment-engineer`, `devops-troubleshooter`, `kubernetes-architect`, `terraform-specialist`, `gitops-workflow` |
| **`data-ai`** | 38 | CTO, Researcher | `ai-engineer`, `llm-evaluation`, `prompt-engineering-patterns`, `database-architect`, `sql-pro`, `dbt-transformation-patterns` |
| **`business`** | 32 | CEO, Researcher | `competitive-landscape`, `market-researcher`, `product-manager-toolkit-product-roadmap`, `seo-content-auditor` |
| **`security`** | 31 | CISO | `security-auditor`, `threat-modeling-expert`, `auth-implementation-patterns`, `sast-configuration`, `secrets-management` |
| **`workflow`** | 20 | CEO, DevOps | `agent-orchestration-multi-agent-optimize`, `conductor-implement`, `full-stack-orchestration-full-stack-feature` |
| **`architecture`** | 18 | CTO, CEO | `backend-architect`, `architecture-patterns`, `api-design-principles`, `c4-architecture-c4-architecture`, `microservices-patterns` |
| **`testing`** | 13 | QA/Release Manager | `test-automator`, `unit-testing-test-generate`, `tdd-workflows-tdd-cycle`, `e2e-testing-patterns`, `api-testing-mock` |
| **`general`** | 10 | All Agents | `accessibility-compliance-accessibility-audit`, `documentation-generator`, `markdown-pro` |

---

## 2. Curated Upstream Bundles

Bundles package up to 10 hand-picked skills targeting common operational domains:

### 1. `core-dev` (Language-Agnostic Engineering Foundations)
- `api-design-principles`, `architecture-patterns`, `backend-architect`, `code-refactoring-refactor-clean`, `code-review-excellence`, `debugger`, `error-handling-patterns`, `frontend-developer`, `git-advanced-workflows`, `test-automator`

### 2. `security-core` (Defensive Security & Threat Modeling)
- `auth-implementation-patterns`, `backend-security-coder`, `frontend-security-coder`, `sast-configuration`, `secrets-management`, `security-auditor`, `security-scanning-security-dependencies`, `security-scanning-security-hardening`, `threat-modeling-expert`

### 3. `ops-core` (Site Reliability, Metrics & Incidents)
- `deployment-engineer`, `devops-troubleshooter`, `distributed-tracing`, `grafana-dashboards`, `incident-responder`, `observability-engineer`, `postmortem-writing`, `prometheus-configuration`, `slo-implementation`, `terraform-specialist`

### 4. `data-core` (Database Design & SQL Optimization)
- `airflow-dag-patterns`, `data-engineer`, `data-quality-frameworks`, `database-architect`, `database-migrations-sql-migrations`, `database-optimizer`, `dbt-transformation-patterns`, `postgresql`, `spark-optimization`, `sql-pro`

### 5. `ai-core` (LLM Applications & Retrieval)
- `ai-engineer`, `embedding-strategies`, `langchain-architecture`, `llm-evaluation`, `ml-engineer`, `prompt-engineering-patterns`, `rag-implementation`, `vector-database-engineer`

### 6. `k8s-core` (Container & Cluster Architecture)
- `gitops-workflow`, `helm-chart-scaffolding`, `k8s-manifest-generator`, `k8s-security-policies`, `kubernetes-architect`, `service-mesh-expert`

---

## 3. The 24 Pre-Audited Vaulted Skills

The local vault at [skill_system/vault/](file:///data/data/com.termux/files/home/aegis-intelligence/skill_system/vault/) maintains audited, ready-to-activate packages that run offline with zero network latency:

| Vaulted Skill ID | Category | Primary Target Agent | Verified Scope |
|---|---|---|---|
| `fastapi-pro` | `development` | Repair Engineer, CTO | High-performance async APIs, Pydantic V2, dependency injection |
| `api-design-principles` | `architecture` | CTO | RESTful conventions, resource naming, pagination, error schemas |
| `python-pro` | `development` | Repair Engineer, CTO | Modern Python 3 idioms, type annotations, dataclasses, generators |
| `typescript-pro` | `development` | Repair Engineer, CTO | Strict typing, generics, utility types, modern TS compiler options |
| `frontend-developer` | `development` | Repair Engineer | Modern web UI development, responsive layouts, DOM manipulation |
| `react-modernization` | `development` | Repair Engineer | React 18+ hooks, concurrent rendering, component modernization |
| `debugger` | `development` | Bug Hunter | Isolated root-cause analysis, reproduction, stack trace investigation |
| `debugging-toolkit-smart-debug` | `development` | Bug Hunter | Systematic hypothesis testing, logging strategies, state verification |
| `devops-troubleshooter` | `infrastructure` | DevOps/SRE | Build failure diagnosis, toolchain issues, environment resolution |
| `code-refactoring-refactor-clean`| `development` | Repair Engineer | Clean architecture refactoring, reducing cyclomatic complexity |
| `security-auditor` | `security` | CISO | Full-spectrum vulnerability discovery, dependency checks, policy audit |
| `sast-configuration` | `security` | CISO | Static application security testing, ruleset configuration |
| `backend-security-coder` | `security` | CISO | Input sanitization, SQL injection prevention, safe cryptographic storage |
| `threat-modeling-expert` | `security` | CISO | STRIDE analysis, attack tree modeling, trust boundary mapping |
| `auth-implementation-patterns` | `security` | CISO | JWT verification, token rotation, constant-time authentication |
| `code-documentation-code-explain`| `development` | Researcher | Code analysis, technical explanation, onboarding documentation |
| `test-automator` | `testing` | QA Manager | Test suite automation, CI integration, fixture management |
| `unit-testing-test-generate` | `testing` | QA Manager | Automated unit test case derivation, edge-case boundary testing |
| `bash-pro` | `infrastructure` | DevOps/SRE | Clean POSIX shell scripting, exit-code handling, signal trapping |
| `git-advanced-workflows` | `infrastructure` | DevOps/SRE | Non-destructive branching, rebase strategies, bisecting |
| `c4-architecture-c4-architecture`| `architecture` | CTO | C4 architectural modeling (Context, Containers, Components, Code) |
| `backend-architect` | `architecture` | CTO | Service decomposition, distributed systems, caching patterns |
| `database-architect` | `architecture` | CTO | Relational & document schema modeling, normalization, WAL storage |
| `agent-orchestration-improve-agent`| `workflow` | CEO | Multi-agent evaluation, iteration boundaries, performance profiling |

---

## 4. Canonical Aliases (Shorthand Resolution)

The registry resolves 60 convenient shorthands via `skill_catalog.json`:
- `fastapi` → `fastapi-pro`
- `c4-architecture` → `c4-architecture-c4-architecture`
- `refactor` → `code-refactoring-refactor-clean`
- `deps-audit` → `dependency-management-deps-audit`
- `api-mock` → `api-testing-observability-api-mock`
- `smart-debug` → `debugging-toolkit-smart-debug`
- `k8s-manifest` → `k8s-manifest-generator`
- `git-workflow` → `git-pr-workflows-git-workflow`

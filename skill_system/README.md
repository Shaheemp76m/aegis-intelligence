# Aegis Intelligence — Centralized Skill Library & Intelligent Routing System

**System Version**: 2.0.0  
**Host Environment**: Termux on Android (Linux aarch64, Python 3.14.10)  
**Upstream Vault**: [`@rmyndharis/antigravity-skills`](https://github.com/rmyndharis/antigravity-skills) (v2.0.0, 307 cataloged skills)  
**Architecture Pattern**: Centralized Skill Registry & On-Demand Progressive Activation  
**Context Efficiency**: >97% reduction in token overhead versus bulk installation  

---

## 1. Executive Overview

The **Aegis Centralized Skill System** integrates a massive library of 307 specialized technical capabilities into the Aegis corporate operating system. Rather than blindly installing hundreds of skills into every agent's active prompt—which wastes tens of thousands of tokens per conversation turn, degrades model reasoning, and triggers irrelevant tool activations—Aegis implements an **intelligent, on-demand skill routing architecture**.

The **CEO (`aegis-orchestrator`)** serves as the central skill router. When assigning tasks to specialized agents (CTO, Bug Hunter, Repair Engineer, Researcher, CISO, DevOps, QA), the CEO searches the lightweight metadata catalog, evaluates candidate skills using multi-factor intelligence criteria, and selects the **smallest useful set (1–3 skills)** tailored to the immediate task.

```
                         [ USER REQUEST ]
                                │
                                ▼
                   ┌──────────────────────────┐
                   │  1. CEO Task Evaluation  │
                   └────────────┬─────────────┘
                                │
                                ▼
                   ┌──────────────────────────┐
                   │ 2. Skill Selection Engine│ (skill_system/selector.py)
                   │  - Role Affinity Check   │
                   │  - Tech Stack Matching   │
                   │  - Overlap Pruning       │
                   └────────────┬─────────────┘
                                │ (Selects 1-3 targeted skills)
                                ▼
         ┌──────────────────────┼──────────────────────┐
         ▼                      ▼                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  aegis-repair   │    │   aegis-ciso    │    │    aegis-qa     │
│ [fastapi-pro]   │    │[security-audit] │    │ [test-automator]│
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

---

## 2. Directory Architecture

```
skill_system/
├── README.md                      # Master architecture overview and operating principles (this document)
├── SKILL_ROUTING.md               # 9-step selection engine, scoring heuristics, and routing lifecycle
├── SKILL_REGISTRY.md              # Complete catalog breakdown (307 skills, 9 categories, 6 bundles)
├── SKILL_COMPATIBILITY.md         # Termux/Android host compatibility, Node requirements, and runtimes
├── SKILL_SECURITY_POLICY.md       # Untrusted skill vetting, static scanning, and non-override invariants
├── skill_catalog.json             # Enriched 307-skill machine-readable catalog
├── agent_skill_mapping.json       # 8-agent role affinities, approved categories, and boundary rules
├── selector.py                    # Python SkillSelector engine for search, scoring, and activation
└── vault/                         # Curated, pre-audited offline skill packages
    ├── agent-orchestration-improve-agent/
    ├── api-design-principles/
    ├── auth-implementation-patterns/
    ├── backend-architect/
    ├── backend-security-coder/
    ├── bash-pro/
    ├── c4-architecture-c4-architecture/
    ├── code-documentation-code-explain/
    ├── code-refactoring-refactor-clean/
    ├── database-architect/
    ├── debugger/
    ├── debugging-toolkit-smart-debug/
    ├── devops-troubleshooter/
    ├── fastapi-pro/
    ├── frontend-developer/
    ├── git-advanced-workflows/
    ├── python-pro/
    ├── react-modernization/
    ├── sast-configuration/
    ├── security-auditor/
    ├── test-automator/
    ├── threat-modeling-expert/
    ├── typescript-pro/
    └── unit-testing-test-generate/
```

---

## 3. Core Operating Principles

1. **Progressive Disclosure & Zero Bulk Injection**:
   - The CEO never injects all 307 skills into the prompt window.
   - Skill discovery relies on lightweight JSON catalog metadata (~220 KB total). Full `SKILL.md` instructions are loaded **only when selected** for an active task.
2. **Smallest Useful Set**:
   - For any single task, the CEO selects between 1 and 3 skills.
   - Overlap pruning prevents loading redundant skills that perform essentially identical functions.
3. **Strict Separation from Agent Identity**:
   - Skills are technical tools and knowledge packs, NOT agent identities.
   - Agents maintain their permanent roles (e.g. Bug Hunter never modifies code, CISO holds veto authority, QA gates releases). A skill can never override an agent's constitutional boundaries.
4. **Third-Party Skill Sandboxing**:
   - Upstream skills are treated as untrusted third-party instructions until audited.
   - Skills are statically analyzed for destructive commands (`rm -rf /`), credential theft, and approval gate bypasses.
5. **No Overwrite of Existing Custom Skills**:
   - Pre-existing user skills in `~/.gemini/config/skills/` (such as the 74 `gsd-*` workflow skills) remain completely untouched and separate from the third-party skill vault.

---

## 4. Context Window & Token Efficiency Metrics

| Metric | Bulk Installation (`install --all`) | Aegis On-Demand Routing (`SkillSelector`) | Efficiency Gain |
|---|---|---|---|
| **Catalog Metadata in Prompt** | ~45,000 tokens (on every turn) | 0 tokens (queried via Python engine) | **100% saved** |
| **Active Skill Instructions** | Up to 150,000 tokens (all skills) | 400 – 1,200 tokens (1–3 selected skills) | **>97% saved** |
| **Reasoning Distraction Risk** | Extreme (false trigger activations) | Minimal (targeted domain focus) | **Deterministic execution** |
| **Termux Memory Overhead** | High (large context buffers) | Low (<15 MB JSON parsing in memory) | **Safe for Android** |

---

## 5. Quick Reference & Commands

- Search skills: `python3 -B -c "from skill_system.selector import SkillSelector; print(SkillSelector.search_catalog('fastapi'))"`
- Evaluate task: `python3 -B -c "from skill_system.selector import SkillSelector; print(SkillSelector.select_skills_for_task('Build REST API', agent_id='aegis-repair-engineer'))"`
- Run test suite: `python3 -B -m unittest tests/test_skill_system.py`

"""Aegis Intelligence - Intelligent Skill Selection & Routing Engine

Implements the 9-step CEO Skill Selection Engine and the 7-criteria Skill Selection Intelligence:
1. Task identification & semantic query parsing
2. Agent role affinity verification
3. Lightweight catalog search across 307 skills
4. Multi-factor evaluation (relevance, agent affinity, tech compatibility, Termux readiness, security risk, overlap pruning)
5. Smallest-set selection (default 1-3 targeted skills)
6. Security policy auditing & static validation
7. On-demand instruction loading & non-destructive workspace activation
8. Graceful fallback on missing skills (zero hallucination)
9. Context-efficiency measurement
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT_DIR / "skill_system" / "skill_catalog.json"
MAPPING_PATH = ROOT_DIR / "skill_system" / "agent_skill_mapping.json"
VAULT_DIR = ROOT_DIR / "skill_system" / "vault"


class SkillSecurityAuditError(Exception):
    """Raised when a skill violates security policies or contains forbidden instructions."""
    pass


class SkillSelector:
    """Intelligent Skill Routing & Selection Engine for Aegis CEO and Specialized Agents."""

    _catalog: Optional[Dict[str, Any]] = None
    _mappings: Optional[Dict[str, Any]] = None

    @classmethod
    def _load_data(cls) -> None:
        """Load catalog and agent mappings if not cached."""
        if cls._catalog is None:
            if CATALOG_PATH.exists():
                with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                    cls._catalog = json.load(f)
            else:
                cls._catalog = {"skills": [], "bundles": {}, "common_skills": []}

        if cls._mappings is None:
            if MAPPING_PATH.exists():
                with open(MAPPING_PATH, "r", encoding="utf-8") as f:
                    cls._mappings = json.load(f)
            else:
                cls._mappings = {"agents": {}}

    @classmethod
    def search_catalog(
        cls,
        query: str,
        category: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search lightweight catalog metadata by query, category, and agent affinity."""
        cls._load_data()
        skills = cls._catalog.get("skills", [])
        query_terms = [q.lower().strip() for q in re.split(r"[\s\-_]+", query) if q.strip()]

        results = []
        for s in skills:
            if category and s.get("category") != category:
                continue

            agent_affinity_boost = 0
            if agent_id and agent_id in cls._mappings.get("agents", {}):
                allowed_cats = cls._mappings["agents"][agent_id].get("primary_categories", [])
                curated = cls._mappings["agents"][agent_id].get("curated_skills", [])
                forbidden = cls._mappings["agents"][agent_id].get("forbidden_categories", [])
                if s.get("category") in forbidden:
                    continue
                if s.get("id") in curated:
                    agent_affinity_boost += 30
                elif s.get("category") in allowed_cats:
                    agent_affinity_boost += 15

            # Calculate match score
            score = 0
            name_lower = s.get("name", "").lower()
            desc_lower = s.get("description", "").lower()
            tags_lower = [t.lower() for t in s.get("tags", [])]
            triggers_lower = [tr.lower() for tr in s.get("triggers", [])]
            aliases_lower = [a.lower() for a in s.get("aliases", [])]

            for term in query_terms:
                if len(term) < 2:
                    continue
                if term == s.get("id"):
                    score += 100
                elif term in aliases_lower:
                    score += 80
                elif term in name_lower:
                    score += 40
                elif term in triggers_lower or any(tr.startswith(term) or term.startswith(tr) for tr in triggers_lower):
                    score += 25
                elif term in tags_lower or any(t.startswith(term) or term.startswith(t) for t in tags_lower):
                    score += 20
                elif term in desc_lower:
                    score += 10

            if score > 0:
                results.append((score + agent_affinity_boost, s))

        results.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in results[:limit]]

    @classmethod
    def audit_skill_content(cls, skill_id: str, content: str) -> Dict[str, Any]:
        """Perform static security analysis on skill instructions before loading or activating."""
        risks_found = []
        
        # 1. Check for destructive shell commands
        destructive_patterns = [
            (r"\brm\s+-(?:rf|fr)\s+(?:/|/\*|~|\$HOME)", "Root or home directory recursive wipe"),
            (r"\bmkfs\b", "Disk formatting command"),
            (r"\bdd\s+if=.*of=/dev/(?:sda|nvme|mmc)", "Direct block device overwrite"),
            (r">>\s*/etc/(?:passwd|shadow|sudoers)", "Privileged system file tampering"),
        ]
        for pattern, desc in destructive_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                risks_found.append({"severity": "CRITICAL", "type": "destructive_command", "description": desc})

        # 2. Check for token/secret exfiltration attempts
        secret_patterns = [
            (r"curl\s+.*(?:\.api_token|\.env|id_rsa).*http", "Secret exfiltration attempt via curl"),
            (r"cat\s+.*(?:api_token|\.telegram_token)", "Dumping authentication tokens"),
        ]
        for pattern, desc in secret_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                risks_found.append({"severity": "CRITICAL", "type": "secret_exposure", "description": desc})

        # 3. Check for permission / sandboxing override claims
        override_patterns = [
            (r"override\s+aegis\s+permissions", "Attempt to override Aegis permissions"),
            (r"bypass\s+(?:approval|security\s+gate)", "Attempt to bypass human approval gate"),
        ]
        for pattern, desc in override_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                risks_found.append({"severity": "CRITICAL", "type": "governance_override", "description": desc})

        has_critical = any(r["severity"] == "CRITICAL" for r in risks_found)
        verdict = "REJECTED" if has_critical else ("FLAGGED" if risks_found else "APPROVED")

        return {
            "skill_id": skill_id,
            "verdict": verdict,
            "is_safe": not has_critical,
            "findings": risks_found
        }

    @classmethod
    def select_skills_for_task(
        cls,
        task_description: str,
        agent_id: str = "aegis-orchestrator",
        project_tech_stack: Optional[List[str]] = None,
        max_skills: int = 3
    ) -> Dict[str, Any]:
        """Evaluate and select the smallest useful set of skills using the 7 intelligence criteria."""
        cls._load_data()
        project_tech = [t.lower() for t in (project_tech_stack or [])]
        task_lower = task_description.lower()

        # Step 1: Check agent mapping boundaries
        agent_info = cls._mappings.get("agents", {}).get(agent_id, {})
        allowed_cats = set(agent_info.get("primary_categories", []))
        curated_skills = set(agent_info.get("curated_skills", []))
        forbidden_cats = set(agent_info.get("forbidden_categories", []))

        # Step 2: Search candidate skills from catalog
        candidates = cls.search_catalog(task_description, agent_id=agent_id, limit=25)
        
        task_words = set(re.findall(r"\b[a-z0-9_\-\.\+#]+\b", task_lower))

        # Step 3: Multi-criteria evaluation
        scored_candidates = []
        for s in candidates:
            sid = s["id"]
            cat = s.get("category", "")
            
            # Check forbidden boundaries (e.g. Bug Hunter cannot use code-modification skills)
            if cat in forbidden_cats:
                continue

            # 1. Task relevance (MANDATORY REQUIREMENT - Word boundary matching)
            task_relevance = 0.0
            matched_terms = 0
            triggers = s.get("triggers", [])
            for trig in triggers:
                trig_clean = trig.lower().strip()
                if not trig_clean:
                    continue
                if len(trig_clean) <= 2:
                    if trig_clean in task_words:
                        task_relevance += 15.0
                        matched_terms += 1
                else:
                    if trig_clean in task_words or re.search(r"\b" + re.escape(trig_clean) + r"\b", task_lower):
                        task_relevance += 15.0
                        matched_terms += 1

            for tag in s.get("tags", []):
                tag_clean = tag.lower().strip()
                if not tag_clean:
                    continue
                if len(tag_clean) <= 2:
                    if tag_clean in task_words:
                        task_relevance += 10.0
                        matched_terms += 1
                else:
                    if tag_clean in task_words or re.search(r"\b" + re.escape(tag_clean) + r"\b", task_lower):
                        task_relevance += 10.0
                        matched_terms += 1
            
            name_parts = [np for np in re.split(r"[\s\-_]+", s.get("name", "").lower()) if len(np) > 2]
            for np in name_parts:
                if np in task_words or re.search(r"\b" + re.escape(np) + r"\b", task_lower):
                    task_relevance += 15.0
                    matched_terms += 1

            # Require substantive relevance: either >= 2 matching terms, or at least 1 term plus a matching project tech stack
            has_tech_match = any(tech in s.get("name", "").lower() or tech in s.get("tags", []) for tech in project_tech)
            if matched_terms < 2 and not has_tech_match:
                continue

            # If the skill has ZERO task relevance, do not select it merely because of role affinity
            if task_relevance == 0.0:
                continue

            score = task_relevance

            # 2. Agent role affinity
            if sid in curated_skills:
                score += 35.0
            elif cat in allowed_cats:
                score += 20.0
            elif agent_id in s.get("target_agents", []):
                score += 15.0
            else:
                score -= 10.0  # Out of primary domain penalty

            # 3. Project technology compatibility
            for tech in project_tech:
                if tech in s.get("name", "").lower() or tech in s.get("tags", []):
                    score += 25.0
                elif tech in s.get("description", "").lower():
                    score += 15.0

            # 4. Termux compatibility
            compat = s.get("compatibility", {})
            if compat.get("termux_compatible", True):
                score += 5.0
            else:
                score -= 20.0  # Deprioritize skills requiring external desktop/cloud daemon

            # 5. Vault availability bonus (pre-audited & ready)
            if s.get("vault_status") == "vaulted":
                score += 10.0

            if score >= 25.0:
                scored_candidates.append({
                    "score": round(score, 1),
                    "task_relevance": round(task_relevance, 1),
                    "skill": s
                })

        # Sort by score descending
        scored_candidates.sort(key=lambda x: x["score"], reverse=True)

        # Step 4: Overlap pruning (Deduplication)
        # Avoid selecting two skills performing essentially the same function
        selected = []
        seen_tags = set()
        for cand in scored_candidates:
            s = cand["skill"]
            sid = s["id"]
            stags = set(s.get("tags", []))
            
            # Prune duplicate debugging/testing overlap unless distinct
            overlap = stags.intersection(seen_tags)
            if len(overlap) >= 3 and len(selected) > 0:
                continue

            selected.append(s)
            seen_tags.update(stags)
            if len(selected) >= max_skills:
                break

        # Calculate estimated context usage savings
        # Bulk loading all 307 skills metadata consumes ~45,000 tokens
        # Loading 1-3 selected skills consumes ~400-1,200 tokens
        selected_count = len(selected)
        context_usage_est = selected_count * 400
        baseline_bulk_tokens = 45000
        tokens_saved = max(0, baseline_bulk_tokens - context_usage_est)

        return {
            "task": task_description,
            "assigned_agent": agent_id,
            "skills_selected_count": selected_count,
            "skills": selected,
            "selection_rationale": [
                f"Selected '{s['id']}' for {agent_info.get('name', agent_id)} (Category: {s.get('category')})"
                for s in selected
            ],
            "missing_skill": None if selected else "No matching vetted skill found in catalog for this specific task.",
            "context_metrics": {
                "selected_token_estimate": context_usage_est,
                "bulk_all_token_estimate": baseline_bulk_tokens,
                "tokens_saved": tokens_saved,
                "token_savings_percent": round((tokens_saved / baseline_bulk_tokens) * 100, 1)
            }
        }

    @classmethod
    def load_skill_instructions(cls, skill_id: str) -> Optional[str]:
        """Load full SKILL.md instructions from local vault or cached storage."""
        # 1. Check local vault
        vault_file = VAULT_DIR / skill_id / "SKILL.md"
        if vault_file.exists():
            with open(vault_file, "r", encoding="utf-8") as f:
                content = f.read()
            audit = cls.audit_skill_content(skill_id, content)
            if not audit["is_safe"]:
                raise SkillSecurityAuditError(f"Skill '{skill_id}' failed security audit: {audit['findings']}")
            return content

        return None

    @classmethod
    def activate_for_workspace(cls, skill_id: str, workspace_path: str) -> Dict[str, Any]:
        """Copy a vaulted skill to the target project workspace (.agents/skills/) on demand."""
        instructions = cls.load_skill_instructions(skill_id)
        if not instructions:
            return {"success": False, "error": f"Skill '{skill_id}' not found in local vault."}

        dest_dir = Path(workspace_path) / ".agents" / "skills" / skill_id
        dest_file = dest_dir / "SKILL.md"

        if dest_file.exists():
            return {
                "success": True,
                "status": "already_active",
                "path": str(dest_file),
                "message": f"Skill '{skill_id}' is already active in workspace."
            }

        dest_dir.mkdir(parents=True, exist_ok=True)
        with open(dest_file, "w", encoding="utf-8") as f:
            f.write(instructions)

        return {
            "success": True,
            "status": "activated",
            "path": str(dest_file),
            "message": f"Skill '{skill_id}' successfully activated in workspace .agents/skills/{skill_id}/"
        }

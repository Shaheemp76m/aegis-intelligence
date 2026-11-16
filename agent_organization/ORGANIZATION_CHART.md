# Aegis Intelligence — Corporate Organization Chart

**Governance Version**: 2.5.0  

---

## 1. Executive Organizational Hierarchy

```
                               [ USER ]
                                  │
                                  ▼ (Telegram / n8n Webhook)
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
         │ (Verdict: RELEASE_APPROVED)
         ▼
[ CEO Final Synthesis & User Delivery ]
```

---

## 2. Reporting & Escalation Chains

| Role | Corporate Title | Direct Supervisor | Direct Handoffs To | Escalation Authority |
|---|---|---|---|---|
| **CEO** | Chief Executive Officer | User | All Agents | Final decision maker on all company operations |
| **CTO** | Software Engineering Director | CEO | Bug Hunter, Repair Engineer | Engineering standards and architectural veto |
| **Bug Hunter** | Lead Defect Diagnostics | CEO | Repair Engineer | Severity classification and defect verification |
| **Repair Engineer**| Senior Software Remediation | CEO | QA/Release Manager | Implementation feasibility |
| **Researcher** | Principal Technology Analyst | CEO | CTO, CISO, Bug Hunter | Evidence quality and source verification |
| **CISO** | Cybersecurity Director | CEO | CEO | **Veto power** over unsafe operations |
| **DevOps/SRE** | Principal Operations Engineer| CEO | CEO | Infrastructure and resource thresholds |
| **QA Manager** | Quality Assurance Director | CEO | CEO | **Release gatekeeper** (100% test pass enforcement) |

---

## 3. Executive Council & Governance Cadence

1. **Strategic Planning**: For major architectural changes or new repository onboarding, the CEO convenes the **Technical Council** (CEO, CTO, CISO, DevOps).
2. **Defect Triage**: Routine bugs flow through the **Operational Remediation Pipeline** (CEO -> Bug Hunter -> Repair Engineer -> QA -> CEO).
3. **Emergency Escalation**: Security breaches, path traversal attempts, or destructive operations immediately halt the execution chain and alert the CEO and CISO for user escalation.

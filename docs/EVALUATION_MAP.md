# Evaluation map

How each panel criterion is evidenced. ✅ Done · 🟡 Partial · 🔭 Future. Numbers marked *synthetic* come from
generated data; *real* from public data; *estimate* means not measured.

| # | Panel criterion | Where we prove it | Status |
|---|---|---|---|
| 1 | **Problem & solution fit** | README §2–5; personas and a needs-to-feature table (`docs/USERS.md`); 5-step lifecycle; user validation (`docs/VALIDATION.md`) | ✅ problem and personas; 🟡 validation (team to record real sessions) |
| 2 | **Innovation & differentiation** | README §4 (comparison with collateral loans, GST and bank-statement fintechs, TReDS, stock statements, informal lenders) and §7 (UVP, innovation type, emerging tech) | ✅ |
| 3 | **Technical architecture** | README §8 (architecture, agent-layer and communication diagrams) and §9 (why-this-tool table); `docs/SYSTEM_DESIGN.md` (built vs future, ADRs); `docs/SECURITY.md`; `docs/THREAT_MODEL.md` | ✅ |
| 4 | **Feasibility & scalability** | Free single-container deployment (`docs/DEPLOYMENT.md`: ready in 7 s, 325 MB measured); capacity plan for 10 lakh accounts (`docs/SYSTEM_DESIGN.md`); costs (₹0 prototype; pilot and production *estimates*); roadmap (README §11) | ✅ image and plan; 🟡 public URL pending the team's account; 🔭 Azure |
| 5 | **Prototype & validation** | Live link and video (README §10); 155 backend tests on SQLite and 160 on PostgreSQL + Redis, 23 web unit tests and 21 Playwright browser tests with axe; CI with blocking security gates. Model metrics with bootstrap CIs: product AUC 0.848 (0.842–0.854) *synthetic*; SBA 0.687 (0.658–0.713) and Polish 0.958 *real*. EWS precision/recall/lead table; fairness, drift and leakage audit; known limits in `docs/LIMITATIONS_AND_RISKS.md` | ✅; 🟡 video and live link to be added by the team |
| 6 | **Impact & team ownership** | README §15 (impact, each number labelled *estimate* or *measured*); `docs/TEAM.md` (proposed split with an explainer per area); `docs/QA_PREP.md` (25 questions) | 🟡 team to confirm the split |

## The Round 2 goals, answered

| Goal | Where |
|---|---|
| Define the problem | README §2 |
| Show the fix | README §5–6, guided demo in the app |
| Design the architecture | README §8–9, `docs/SYSTEM_DESIGN.md` |
| Prove feasibility | README §11, `docs/DEPLOYMENT.md`, capacity plan |
| Demo the prototype | README §10, live link, guided demo, `docs/DEMO_SCRIPT.md` |
| Spot risks and limits as you scale | README §13–14, `docs/LIMITATIONS_AND_RISKS.md` |
| Present confidently | `docs/PRESENTATION_OUTLINE.md`, `docs/QA_PREP.md`, `docs/TEAM.md` |

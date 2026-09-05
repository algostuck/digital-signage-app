# Documentation

The product documentation set, frozen with the hardening cycle
(2026-09-05). The first table is what an engineer, an operator or a
customer needs; the second is the working history behind it.

## Product documentation

| Topic | Document | What it answers |
|---|---|---|
| Architecture | [architecture.md](architecture.md) · [decisions/](decisions/) · [PHASE_2_ARCHITECTURE.md](PHASE_2_ARCHITECTURE.md) | how the system is built and why |
| API | [API.md](API.md) · [api-guidelines.md](api-guidelines.md) | authentication, conventions, resource groups, OpenAPI |
| Database | [DATABASE.md](DATABASE.md) · [domain-model.md](domain-model.md) | schema, tenancy at the data layer, migrations, retention |
| Deployment | [deployment.md](deployment.md) · [runbook.md](runbook.md) | pipeline, DEV / UAT / PRODUCTION, release and rollback, operations |
| Security | [SECURITY_REVIEW.md](SECURITY_REVIEW.md) | the production checklist, findings and go-live list |
| Observability | [OBSERVABILITY.md](OBSERVABILITY.md) | request ids, logs, jobs — "what exactly failed?" |
| RBAC | [RBAC.md](RBAC.md) | roles × permissions, custom roles, enforcement |
| Subscription | [SAAS_CORE.md](SAAS_CORE.md) · [PLATFORM_CONSOLE.md](PLATFORM_CONSOLE.md) | tenants, plans, entitlements, lifecycle, the platform console |
| Device protocol | [PLAYER_API_CONTRACT.md](PLAYER_API_CONTRACT.md) | the frozen player API native clients implement |
| TV preview | [TV_PREVIEW_ARCHITECTURE.md](TV_PREVIEW_ARCHITECTURE.md) · [TV_PREVIEW_UX.md](TV_PREVIEW_UX.md) | how the preview renders exactly what a screen plays |
| Admin guide | [ADMIN_GUIDE.md](ADMIN_GUIDE.md) | running a tenant, module by module |
| Client demo guide | [CLIENT_DEMO_GUIDE.md](CLIENT_DEMO_GUIDE.md) · [DEMO_CREDENTIALS.md](DEMO_CREDENTIALS.md) · [DEMO_DATA_CATALOG.md](DEMO_DATA_CATALOG.md) | the scripted story, accounts and dataset |
| Hardening evidence | [HARDENING_AUDIT.md](HARDENING_AUDIT.md) | every gate, its script, its results and fixes |
| Scheduling | [SCHEDULE_UX_AUDIT.md](SCHEDULE_UX_AUDIT.md) | the schedule workspace: audit, data contract, conflict rules, implementation |
| Dashboard | [ORGANIZATION_ADMIN_DASHBOARD_ARCHITECTURE.md](ORGANIZATION_ADMIN_DASHBOARD_ARCHITECTURE.md) · […_DATA_MAP.md](ORGANIZATION_ADMIN_DASHBOARD_DATA_MAP.md) · […_COMPONENTS.md](ORGANIZATION_ADMIN_DASHBOARD_COMPONENTS.md) · […_QA.md](ORGANIZATION_ADMIN_DASHBOARD_QA.md) | the executive dashboard end to end |
| Design system | [design-system/DESIGN_SYSTEM_USAGE.md](design-system/DESIGN_SYSTEM_USAGE.md) · [design-system/DESIGN_TOKENS.md](design-system/DESIGN_TOKENS.md) · [design-system/COMPONENT_CATALOGUE.md](design-system/COMPONENT_CATALOGUE.md) · [design-system/RESPONSIVE_COMPONENT_RULES.md](design-system/RESPONSIVE_COMPONENT_RULES.md) · [design-system/ACCESSIBILITY_GUIDELINES.md](design-system/ACCESSIBILITY_GUIDELINES.md) · [design-system/ANTD_REFERENCE_ANALYSIS.md](design-system/ANTD_REFERENCE_ANALYSIS.md) | how to build a page, tokens, the component catalogue, responsive and accessibility rules, the Ant Design study; audit and status in [design-system/FULL_UI_UX_AUDIT.md](design-system/FULL_UI_UX_AUDIT.md) and [design-system/UI_UX_IMPLEMENTATION_STATUS.md](design-system/UI_UX_IMPLEMENTATION_STATUS.md) |

## Requirements

[business_requirement_document.md](business_requirement_document.md),
[Digital_Signage_Cloud_SRS_FRD.md](Digital_Signage_Cloud_SRS_FRD.md),
[Digital_Signage_Cloud_Phase_2_SRS_FRD.md](Digital_Signage_Cloud_Phase_2_SRS_FRD.md),
[Digital_Signage_Cloud_Phase_3_SRS_FRD.md](Digital_Signage_Cloud_Phase_3_SRS_FRD.md)
(and their `.docx` originals).

## Working history

Audits, gap analyses, implementation status and test plans written while
the product was built. Kept for traceability; superseded where the
product documentation above says otherwise.

[development-plan.md](development-plan.md) ·
[PHASE_2_GAP_ANALYSIS.md](PHASE_2_GAP_ANALYSIS.md) ·
[PHASE_2_IMPLEMENTATION_STATUS.md](PHASE_2_IMPLEMENTATION_STATUS.md) ·
[PHASE_2_API_IMPLEMENTATION.md](PHASE_2_API_IMPLEMENTATION.md) ·
[PHASE_2_DATABASE_CHANGES.md](PHASE_2_DATABASE_CHANGES.md) ·
[PHASE_2_SCREEN_IMPLEMENTATION_MATRIX.md](PHASE_2_SCREEN_IMPLEMENTATION_MATRIX.md) ·
[PHASE_2_TEST_PLAN.md](PHASE_2_TEST_PLAN.md) ·
[UI_UX_AUDIT.md](UI_UX_AUDIT.md) · [UI_UX_DESIGN_SYSTEM.md](UI_UX_DESIGN_SYSTEM.md) · [UI_UX_ACCESSIBILITY_CHECKLIST.md](UI_UX_ACCESSIBILITY_CHECKLIST.md) · [UI_UX_RESPONSIVE_GUIDELINES.md](UI_UX_RESPONSIVE_GUIDELINES.md) ·
[UI_UX_API_CHANGES.md](UI_UX_API_CHANGES.md) ·
[UI_UX_IMPLEMENTATION_STATUS.md](UI_UX_IMPLEMENTATION_STATUS.md) ·
[UI_UX_SCREEN_REDESIGN_MATRIX.md](UI_UX_SCREEN_REDESIGN_MATRIX.md) ·
[SIDEBAR_UX_AUDIT.md](SIDEBAR_UX_AUDIT.md) ·
[TV_PREVIEW_AUDIT.md](TV_PREVIEW_AUDIT.md) ·
[TV_PREVIEW_IMPLEMENTATION.md](TV_PREVIEW_IMPLEMENTATION.md) ·
[ORGANIZATION_ADMIN_DASHBOARD_AUDIT.md](ORGANIZATION_ADMIN_DASHBOARD_AUDIT.md) ·
[DEMO_SEED_MASTER_DATA.md](DEMO_SEED_MASTER_DATA.md) ·
[DEMO_SEED_VALIDATION.md](DEMO_SEED_VALIDATION.md)

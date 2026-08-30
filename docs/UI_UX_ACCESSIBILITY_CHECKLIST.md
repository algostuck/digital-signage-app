# UI/UX Accessibility Checklist — WCAG 2.2 AA baseline

Target: WCAG 2.2 Level AA as the mandatory baseline; AAA improvements
where reasonably achievable (per W3C's own guidance that blanket AAA is
not a recommended site-wide requirement). Status column updated as the
hardening pass verifies each item.

## Systemic (inherited from the component layer)

| Item | How it's satisfied | Status |
|---|---|---|
| Focus trap + initial focus + focus return in dialogs | antd `Modal`/`Drawer` built-in behavior (replaced the legacy Modal that had none — audit finding #4) | Done via migration |
| Visible focus states | antd's focus outline tokens on every interactive control; never removed | Done via migration |
| Keyboard-operable menus/tabs/trees | antd `Menu`, `Tabs`, `Tree` ship WAI-ARIA roving-tabindex patterns (replaced 4+ hand-rolled `role="tablist"` implementations) | Done via migration |
| Form label association + error announcement | antd `Form.Item` label/`aria-describedby` wiring + validation messages | Done via migration |
| Status never color-only | `StatusBadge` renders icon + text + color for every status (brief §26/§35) | Done via migration |
| Landmark structure | Shell renders `nav` (Menu), `main` (Content), header regions | Done (AppLayout) |
| Loading announcement | `LoadingState` skeleton carries `aria-busy` | Done |
| Icon-only buttons named | `aria-label` required by the migration contract on every icon-only Button | Done via migration; re-verify in hardening pass |

## Per-screen checks (hardening pass)

For every screen: keyboard-only walkthrough (Tab/Shift+Tab/Enter/Space/
Escape/arrows), heading hierarchy sanity, contrast spot-check of any
custom color usage, screen-reader name check on row actions.

| Screen | Keyboard | Headings | Contrast | Names | Notes |
|---|---|---|---|---|---|
| Login | — | — | — | — | autofocus on email; error via Alert role="alert" |
| Dashboard | — | — | — | — | KPI cards are links; check focus order |
| Content | — | — | — | — | card grid keyboard-activatable (Enter/Space handled) |
| Devices | — | — | — | — | bulk bar uses aria-live="polite" |
| Locations | — | — | — | — | antd Tree arrow-key navigation |
| Campaigns/Schedules/Deployments/Approvals | — | — | — | — | |
| Design + Designer | — | — | — | — | canvas is mouse-first (documented exception); toolbar fully keyboard-operable |
| Monitoring/Reports/Users/Notifications/Audit | — | — | — | — | |
| Settings + sections | — | — | — | — | |
| Ads/Security/Developer/Platform | — | — | — | — | |

## Known gaps / deferred

- Canvas drag/resize has no keyboard equivalent yet — zone geometry IS
  keyboard-editable via the numeric X/Y/W/H properties panel, which is
  the accessible path. Documented as the designer's keyboard mechanism.
- Automated a11y tooling (`eslint-plugin-jsx-a11y`, axe in CI) not yet
  configured — candidate for the hardening pass.
- Contrast: `Typography.Text type="secondary"` on white meets AA for
  normal text per antd defaults; any custom slate-400 text on white used
  for non-essential captions should be verified in the hardening pass.

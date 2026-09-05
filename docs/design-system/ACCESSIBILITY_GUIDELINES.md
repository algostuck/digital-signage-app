# Accessibility Guidelines

Baseline **WCAG 2.2 AA**, mandatory on every screen; AAA where it costs
nothing (text contrast is already 7:1 in both themes). No blanket AAA
claim is made. Automated checks are a floor, not the test.

## 1. What Ant Design gives us (do not undo it)

| Capability | Component | Our obligation |
|---|---|---|
| Focus trap, initial focus, focus return | `Modal`, `Drawer`, `Popconfirm` | never render dialogs outside these |
| Roving tabindex, arrow keys | `Menu`, `Tabs`, `Tree`, `Segmented`, `Radio.Group`, `Table` selection | never re-implement these controls |
| Label / description / error wiring | `Form.Item` | every input inside `Form.Item` with a `label`, or `aria-label` on standalone controls (search, filters) |
| Sort and selection semantics | `Table` | use `DataTable`; no hand-built tables |
| `aria-busy` | `Skeleton`, `Spin` | use `LoadingState` |
| Reduced motion | antd 6.3+ controls | custom animation gates on `useReducedMotion()` |
| Visible focus | `focusOutline` token | never `outline: none` |

## 2. Product rules

1. **Contrast**: text ≥ 7:1 on its surface in both themes (tokens
   guarantee this for everything using tokens); status fills use the
   tone palette; disabled text may drop to antd's disabled colour.
2. **Colour is never the only signal**: status = icon + text + colour
   (`StatusBadge`); chart series have labels and a text summary; conflicts
   carry an icon and a dashed outline; live carries a play icon.
3. **Names**: every icon-only `Button` has `aria-label`; every chip or
   block that is a button has a full sentence name ("Diwali Offers,
   10:00–13:00, Published, conflict"); `Tooltip` supplements, never
   replaces, a name.
4. **Keyboard**: everything reachable and operable with Tab / Shift+Tab /
   Enter / Space / Escape / arrows; row actions are real buttons; drag
   interactions have a keyboard path (edit form, move buttons).
5. **Headings**: one `Title level={3}` per page (in `PageHeader`); sections
   `level={4}`; cards `level={5}`; no skipped levels inside drawers.
6. **Live regions**: bulk-action bars, "last updated" labels and range
   labels use `aria-live="polite"`; errors use `role="alert"` (antd
   `Alert` does this).
7. **Targets**: ≥ 24 × 24 CSS px everywhere (WCAG 2.2 2.5.8); ≥ 44 on
   touch layouts via padding.
8. **Forms**: required marked; errors say what to do ("Enter a valid
   campaign start time"); `scrollToFirstError`; success announced by
   `message` or an inline `Alert`, never by colour alone.
9. **Motion**: no auto-playing motion beyond antd transitions; respect
   `prefers-reduced-motion`.
10. **Language**: sentence case, plain words, no jargon in errors.

## 3. QA procedure per screen

1. Keyboard-only walkthrough (Tab order, traps, Escape closes overlays,
   arrow keys in menus/tabs/trees/segments).
2. Focus review: every focusable element shows the ring.
3. Contrast review: measure after a page reload in light and dark (the
   canvas-composited check in `backend/scripts/audit_performance.py`'s
   sibling, or the browser pane script) — never mid-transition.
4. Accessibility tree: names on buttons, roles on custom surfaces
   (`grid`, `gridcell`, `tablist`), heading order.
5. Form labels and error association.
6. Status semantics: no colour-only status.
7. Screen-reader pass on the critical screens: Login, Dashboard,
   Devices, Campaigns, Schedule, Settings.

Tooling: `eslint-plugin-jsx-a11y` in the frontend lint (Phase H); axe
via the browser pane during visual QA; Lighthouse spot checks. Scores are
recorded in `UI_UX_IMPLEMENTATION_STATUS.md`, but a screen passes only
after the manual walkthrough.

## 4. Known exceptions (documented)

* Screen Designer canvas: mouse-first; zone geometry is keyboard-editable
  through the numeric properties panel.
* Schedule time grid drag: keyboard path is "Edit window" in the popover.
* Leaflet map: `aria-hidden`; the location list beside it is the
  accessible equivalent.
* TV preview renderer: decorative playback surface; the device detail
  carries the accessible data.

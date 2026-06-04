# UI Consistency Checklist

Use this checklist for any PR that changes browser UI code in `provider` or `config-service`.

## Standards

- Keep UI architecture aligned across projects:
  - module-style vanilla JavaScript.
  - namespace factory pattern (`window.<ModuleName>` + `create(deps)`).
  - split responsibilities into:
    1. state/bootstrap
    2. behavior/functions
    3. bindings/event wiring
- Prefer dependency injection between modules instead of hidden global coupling.
- Keep UI assets as static HTML/CSS/JS served by Quart routes.

## Preferred Libraries

- Preferred: browser/platform APIs and existing in-repo helper modules.
- Preferred: no external frontend frameworks by default.
- Do not introduce React, Vue, Angular, or Svelte unless explicitly approved.

## Implementation Checklist

- [ ] UI module API is exposed via `window.<ModuleName>`.
- [ ] If a framework/bootstrap module exists, script order is:
  1. state
  2. functions/helpers
  3. framework/bootstrap
  4. bindings
- [ ] CSS changes reuse existing variables/class patterns where possible.
- [ ] New UI routes/assets are added to app route handlers.
- [ ] Existing behavior is preserved unless the PR explicitly changes it.

## Validation Checklist

- [ ] JavaScript files pass syntax checks (`node --check`).
- [ ] Python files touched for UI routing pass compile checks (`python3 -m py_compile ...`).
- [ ] Endpoint/UI tests are updated for changed script tags/routes/assets.
- [ ] Targeted tests for affected UI paths pass.

## Related Project Rules

- Canonical agent-side UI rules are documented in `agent.md` under `UI Consistency Rules`.

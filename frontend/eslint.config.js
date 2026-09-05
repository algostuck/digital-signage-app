// Design-system governance lint (docs/design-system/DESIGN_SYSTEM_USAGE.md §13).
// Rules 1, 5, 6 and the raw-control ban are enforced here; accessibility
// rules come from eslint-plugin-jsx-a11y.
import js from "@eslint/js";
import jsxA11y from "eslint-plugin-jsx-a11y";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

const COLOUR_UTILITY =
  /(^|\s)(text|bg|border|ring|divide|from|to|via|fill|stroke|outline|decoration|accent|caret|shadow)-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|white|black)(-\d+)?(\/\d+)?(\s|$)/;
const IMPORTANT_UTILITY = /(^|\s)![a-z]/;
const ARBITRARY_TEXT_SIZE = /(^|\s)text-\[[^\]]+\](\s|$)/;

/** Local plugin: the rules the design system needs that no package provides. */
const dsc = {
  rules: {
    "no-colour-utilities": {
      meta: { type: "problem", docs: { description: "Colours come from design-system tokens, never Tailwind colour utilities." } },
      create(context) {
        return {
          JSXAttribute(node) {
            if (node.name.name !== "className" || !node.value || node.value.type !== "Literal") return;
            const value = String(node.value.value);
            if (COLOUR_UTILITY.test(value)) {
              context.report({ node, message: `Colour utility in className (\"${value.match(COLOUR_UTILITY)[0].trim()}\"): use antd tokens (theme.useToken), Typography types or a design-system component.` });
            }
          },
        };
      },
    },
    "no-important-utilities": {
      meta: { type: "problem", docs: { description: "No !important-style utilities; use antd props, styles or component tokens." } },
      create(context) {
        return {
          JSXAttribute(node) {
            if (node.name.name !== "className" || !node.value || node.value.type !== "Literal") return;
            const value = String(node.value.value);
            if (IMPORTANT_UTILITY.test(value)) {
              context.report({ node, message: "`!`-prefixed utility overrides antd styles; use the component's own props/styles or a token." });
            }
            if (ARBITRARY_TEXT_SIZE.test(value)) {
              context.report({ node, message: "Arbitrary text size; use Typography roles or token.fontSize*." });
            }
          },
        };
      },
    },
    "no-raw-controls": {
      meta: { type: "problem", docs: { description: "Native controls are replaced by Ant Design components." } },
      create(context) {
        const banned = new Set(["button", "input", "select", "textarea", "table"]);
        return {
          JSXOpeningElement(node) {
            if (node.name.type === "JSXIdentifier" && banned.has(node.name.name)) {
              context.report({ node, message: `<${node.name.name}> is a raw control; use the antd component (Button, Input, Select, Table via DataTable).` });
            }
          },
        };
      },
    },
  },
};

export default tseslint.config(
  { ignores: ["dist", "node_modules", "vite.config.ts"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  jsxA11y.flatConfigs.recommended,
  {
    files: ["src/**/*.{ts,tsx}"],
    plugins: { "react-hooks": reactHooks, dsc },
    languageOptions: { globals: { ...globals.browser } },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // React-Compiler-era rules: advisory until the codebase is compiled.
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/refs": "warn",
      "react-hooks/purity": "warn",
      "react-hooks/immutability": "warn",
      "react-hooks/preserve-manual-memoization": "warn",
      // Initial focus inside dialogs and auth forms is deliberate focus
      // management (ACCESSIBILITY_GUIDELINES.md §2.4), not a trap.
      "jsx-a11y/no-autofocus": "off",
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
      "@typescript-eslint/no-explicit-any": "warn",
      "dsc/no-colour-utilities": "error",
      "dsc/no-important-utilities": "error",
      "dsc/no-raw-controls": "error",
      "no-restricted-imports": [
        "error",
        {
          paths: [
            { name: "antd", importNames: ["List"], message: "List is deprecated in antd 6; use EntityList (Listy) from @/design-system." },
          ],
          patterns: [
            { group: ["**/theme/tokens", "**/components/ui/*"], message: "Import from @/design-system." },
          ],
        },
      ],
    },
  },
  {
    // Justified custom surfaces (COMPONENT_CATALOGUE.md): pixel renderers
    // and the schedule time grid keep native elements and fixed colours.
    files: [
      "src/modules/preview/**/*.tsx",
      "src/modules/campaigns/schedule/TimeGrid.tsx",
      "src/modules/campaigns/schedule/EventChip.tsx",
      "src/modules/campaigns/schedule/MonthView.tsx",
      "src/modules/campaigns/schedule/MobileAgenda.tsx",
      "src/modules/design/DesignerPage.tsx",
      "src/modules/simulator/SimulatorPage.tsx",
      "src/modules/auth/HeroIllustration.tsx",
    ],
    rules: {
      "dsc/no-colour-utilities": "off",
      "dsc/no-important-utilities": "off",
      "dsc/no-raw-controls": "off",
      // Mouse-first composition and playback surfaces; the keyboard path is
      // the numeric properties panel / the device detail (documented).
      "jsx-a11y/no-static-element-interactions": "off",
      "jsx-a11y/no-noninteractive-element-interactions": "off",
      "jsx-a11y/media-has-caption": "off",
    },
  },
);

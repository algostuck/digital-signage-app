import { ConfigProvider, Grid, Typography, theme } from "antd";
import type { CSSProperties, ReactNode } from "react";
import { useThemeMode } from "@/design-system";
import { HeroIllustration } from "./HeroIllustration";

/** Brand gradient for the hero panel. Every stop clears 7:1 against white
 * text (#6D28D9 7.1, #4338CA 7.9, #1E40AF 8.6), so the headline and
 * subtitle are AAA anywhere on the surface. The brand blue itself
 * (#1D4ED8) is only 6.7:1, which is why the run ends on blue-800. */
export const AUTH_GRADIENT =
  "linear-gradient(135deg, #6D28D9 0%, #4338CA 55%, #1E40AF 100%)";

/** Primary action on the auth screens. Same stops as the hero so white
 * text stays AAA. In dark mode the surface itself cannot reach the 3:1
 * non-text contrast against the navy card without dropping the label
 * below 7:1 — the two constraints are mathematically exclusive — so the
 * boundary is carried by a border instead (WCAG 1.4.11). */
export function useAuthButtonStyle(): CSSProperties {
  const { mode } = useThemeMode();
  return {
    height: 44,
    background: "linear-gradient(90deg, #4338CA 0%, #1E40AF 100%)",
    border: mode === "dark" ? "1px solid rgba(255, 255, 255, 0.55)" : "0",
  };
}

/* Proportions: the card is a golden rectangle (1040 × 643) split at φ —
 * form 38.2 %, hero 61.8 %. Vertical rhythm uses Fibonacci steps
 * (13 · 21 · 34 · 55) and the type scale runs 16 → 26 (× 1.618). */
const CARD_WIDTH = 1040;
const CARD_HEIGHT = Math.round(CARD_WIDTH / 1.618);

/** Input borders: antd's default border is ~1.4:1 against the card,
 * far below the 3:1 a control boundary needs. */
const INPUT_TOKENS = {
  light: { colorBorder: "#64748B", hoverBorderColor: "#475569", activeBorderColor: "#1E40AF" },
  dark: { colorBorder: "#94A3B8", hoverBorderColor: "#CBD5E1", activeBorderColor: "#93C5FD" },
};

/** Split-panel frame shared by the sign-in and password-reset screens:
 * a form on the left, the brand panel with a curved edge on the right.
 * Below `md` the brand panel drops away and the form fills the card. */
export function AuthShell({ children }: { children: ReactNode }) {
  const { token } = theme.useToken();
  const { mode } = useThemeMode();
  const screens = Grid.useBreakpoint();
  const wide = screens.md ?? false;

  return (
    <ConfigProvider theme={{ components: { Input: INPUT_TOKENS[mode] } }}>
    <div
      className="flex min-h-screen items-center justify-center p-4 sm:p-6"
      style={{ background: token.colorBgLayout }}
    >
      <div
        className="flex w-full overflow-hidden"
        style={{
          maxWidth: wide ? CARD_WIDTH : 440,
          minHeight: wide ? CARD_HEIGHT : undefined,
          background: token.colorBgContainer,
          borderRadius: token.borderRadiusLG + 4,
          boxShadow: token.boxShadowSecondary,
        }}
      >
        <section
          className="flex flex-col justify-center"
          style={wide ? { width: "38.2%", padding: "55px 55px" } : { width: "100%", padding: "34px 34px" }}
          aria-label="Authentication"
        >
          <Brand />
          {children}
        </section>

        {wide && (
          <aside
            className="relative flex flex-col items-center justify-center text-center"
            style={{ width: "61.8%", padding: "55px 55px", background: AUTH_GRADIENT }}
            aria-hidden
          >
            {/* Curved seam: the form panel's colour intruding into the hero. */}
            <svg
              className="absolute inset-y-0 left-0 h-full w-20"
              viewBox="0 0 100 800"
              preserveAspectRatio="none"
              aria-hidden
            >
              <path
                d="M0 0 H56 C22 190, 98 430, 48 620 C30 700, 16 760, 0 800 Z"
                fill={token.colorBgContainer}
              />
            </svg>

            <Typography.Title
              level={2}
              className="!mb-2 !text-white"
              style={{ fontSize: 26, lineHeight: 1.3, maxWidth: 420 }}
            >
              It's not about what you show.
              <br />
              It's about what you make possible.
            </Typography.Title>
            <Typography.Text className="!text-white/90" style={{ fontSize: 16 }}>
              Welcome to Digital Signage Cloud!
            </Typography.Text>
            <div className="w-full" style={{ marginTop: 34 }}>
              <HeroIllustration />
            </div>
          </aside>
        )}
      </div>
    </div>
    </ConfigProvider>
  );
}

function Brand() {
  const { token } = theme.useToken();
  return (
    <div className="flex items-center gap-3" style={{ marginBottom: 34 }}>
      <span
        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-sm font-bold text-white"
        style={{ background: token.colorPrimary }}
        aria-hidden
      >
        DS
      </span>
      <span className="text-[26px] leading-none tracking-tight">
        <span className="font-bold">Digital</span>
        <span className="font-light">Signage</span>
      </span>
    </div>
  );
}

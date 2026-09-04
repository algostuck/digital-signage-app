import { Grid, Typography, theme } from "antd";
import type { ReactNode } from "react";
import { HeroIllustration } from "./HeroIllustration";

/** Brand gradient for the hero panel. Every stop clears 7:1 against white
 * text, so the headline and subtitle are AAA anywhere on the surface. */
export const AUTH_GRADIENT =
  "linear-gradient(135deg, #6D28D9 0%, #4338CA 55%, #1D4ED8 100%)";

/** Split-panel frame shared by the sign-in and password-reset screens:
 * a form on the left, the brand panel with a curved edge on the right.
 * Below `md` the brand panel drops away and the form fills the card. */
export function AuthShell({ children }: { children: ReactNode }) {
  const { token } = theme.useToken();
  const screens = Grid.useBreakpoint();
  const wide = screens.md ?? false;

  return (
    <div
      className="flex min-h-screen items-center justify-center p-4 sm:p-6"
      style={{ background: token.colorBgLayout }}
    >
      <div
        className={`flex w-full overflow-hidden ${wide ? "max-w-[1040px] min-h-[640px]" : "max-w-[440px]"}`}
        style={{
          background: token.colorBgContainer,
          borderRadius: token.borderRadiusLG + 4,
          boxShadow: token.boxShadowSecondary,
        }}
      >
        <section
          className={`flex flex-col justify-center ${wide ? "w-[46%] px-14 py-12" : "w-full px-8 py-10"}`}
          aria-label="Authentication"
        >
          <Brand />
          {children}
        </section>

        {wide && (
          <aside
            className="relative flex w-[54%] flex-col items-center justify-center px-12 py-12 text-center"
            style={{ background: AUTH_GRADIENT }}
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
            <div className="mt-10 w-full">
              <HeroIllustration />
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}

function Brand() {
  const { token } = theme.useToken();
  return (
    <div className="mb-9 flex items-center gap-3">
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

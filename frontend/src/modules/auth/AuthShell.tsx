import { Flex, Grid, Typography, theme } from "antd";
import type { ReactNode } from "react";
import { HEADING } from "@/design-system";
import { HeroIllustration } from "./HeroIllustration";

/**
 * Brand gradient for the hero panel — the one deliberately branded
 * surface in the product (docs/design-system/COMPONENT_CATALOGUE.md,
 * justified custom surfaces). Every stop clears 7:1 against white text
 * (#6D28D9 7.1, #4338CA 7.9, #1E40AF 8.6).
 */
export const AUTH_GRADIENT = "linear-gradient(135deg, #6D28D9 0%, #4338CA 55%, #1E40AF 100%)";

/* Proportions: the card is a golden rectangle (1040 × 643) split at φ —
 * form 38.2 %, hero 61.8 %. */
const CARD_WIDTH = 1040;
const CARD_HEIGHT = Math.round(CARD_WIDTH / 1.618);

/**
 * Split-panel frame shared by the sign-in and password-reset screens: a
 * standard antd form on the left, the brand panel on the right. Below `md`
 * the brand panel drops away and the form fills the card. Controls are
 * the application's own (no pill inputs, no gradient buttons) so the
 * first screen already speaks the product's design language.
 */
export function AuthShell({
  title,
  description,
  children,
}: {
  title?: string;
  description?: string;
  children: ReactNode;
}) {
  const { token } = theme.useToken();
  const screens = Grid.useBreakpoint();
  const wide = screens.md ?? false;

  return (
    <Flex
      align="center"
      justify="center"
      style={{ minHeight: "100vh", padding: wide ? token.paddingLG : token.padding, background: token.colorBgLayout }}
    >
      <Flex
        style={{
          width: "100%",
          maxWidth: wide ? CARD_WIDTH : 440,
          minHeight: wide ? CARD_HEIGHT : undefined,
          overflow: "hidden",
          background: token.colorBgContainer,
          borderRadius: token.borderRadiusLG + 4,
          boxShadow: token.boxShadowSecondary,
        }}
      >
        <Flex
          vertical
          justify="center"
          component="section"
          style={wide ? { width: "38.2%", padding: 55 } : { width: "100%", padding: 34 }}
          aria-label="Authentication"
        >
          <Brand />
          {title && (
            <Typography.Title level={HEADING.section} style={{ marginBottom: 4 }}>
              {title}
            </Typography.Title>
          )}
          {description && (
            <Typography.Paragraph type="secondary" style={{ marginBottom: 20 }}>
              {description}
            </Typography.Paragraph>
          )}
          {children}
        </Flex>

        {wide && (
          <Flex
            vertical
            align="center"
            justify="center"
            component="aside"
            style={{ position: "relative", width: "61.8%", padding: 55, textAlign: "center", background: AUTH_GRADIENT }}
            aria-hidden
          >
            {/* Curved seam: the form panel's colour intruding into the hero. */}
            <svg
              style={{ position: "absolute", insetBlock: 0, left: 0, height: "100%", width: 80 }}
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
              style={{ color: "#FFFFFF", marginBottom: 8, fontSize: 26, lineHeight: 1.3, maxWidth: 420 }}
            >
              It's not about what you show.
              <br />
              It's about what you make possible.
            </Typography.Title>
            <Typography.Text style={{ color: "rgba(255,255,255,0.9)", fontSize: token.fontSizeLG }}>
              Welcome to Digital Signage Cloud!
            </Typography.Text>
            <div style={{ width: "100%", marginTop: 34 }}>
              <HeroIllustration />
            </div>
          </Flex>
        )}
      </Flex>
    </Flex>
  );
}

function Brand() {
  const { token } = theme.useToken();
  return (
    <Flex align="center" gap={12} style={{ marginBottom: 34 }}>
      <Flex
        align="center"
        justify="center"
        style={{
          width: 40,
          height: 40,
          flexShrink: 0,
          borderRadius: token.borderRadius,
          background: token.colorPrimary,
          color: "#FFFFFF",
          fontWeight: 700,
          fontSize: token.fontSize,
        }}
        aria-hidden
      >
        DS
      </Flex>
      <span style={{ fontSize: 26, lineHeight: 1, letterSpacing: "-0.01em" }}>
        <span style={{ fontWeight: 700 }}>Digital</span>
        <span style={{ fontWeight: 300 }}>Signage</span>
      </span>
    </Flex>
  );
}

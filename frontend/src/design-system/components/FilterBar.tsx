import { ClearOutlined, FilterOutlined } from "@ant-design/icons";
import { Badge, Button, Drawer, Flex, Form, Grid, Space } from "antd";
import { useState, type ReactNode } from "react";
import { DRAWER } from "../tokens/scale";

interface FilterBarProps {
  /** The search control (usually `<SearchBar/>`); always first. */
  search?: ReactNode;
  /** Primary filters, always visible on desktop (≤ 4 controls). */
  children?: ReactNode;
  /** Secondary filters, shown in a "More filters" drawer. Render them as
   * `Form.Item`s with labels; the drawer supplies the vertical Form. */
  more?: ReactNode;
  /** Number of active filters — shown on the More/Filters badge. */
  activeCount?: number;
  onReset?: () => void;
  /** Extra right-aligned controls (view switch, density). Never a primary button. */
  extra?: ReactNode;
}

/**
 * The recognisable filter row of every data-heavy page
 * (docs/design-system/COMPONENT_CATALOGUE.md): Search · primary filters ·
 * More filters · Reset. Below `md` the primary filters move into the
 * drawer too, behind one "Filters" button, and the search stays
 * full-width.
 */
export function FilterBar({ search, children, more, activeCount = 0, onReset, extra }: FilterBarProps) {
  const screens = Grid.useBreakpoint();
  const compact = screens.md === false;
  const [open, setOpen] = useState(false);
  const hasDrawer = Boolean(more) || (compact && Boolean(children));

  const drawerButton = hasDrawer && (
    <Badge count={activeCount} size="small" offset={[-2, 2]}>
      <Button
        icon={<FilterOutlined />}
        onClick={() => setOpen(true)}
        aria-label={activeCount ? `Filters, ${activeCount} active` : "Filters"}
      >
        {compact ? "Filters" : "More filters"}
      </Button>
    </Badge>
  );
  const resetButton = onReset && (
    <Button icon={<ClearOutlined />} onClick={onReset} disabled={activeCount === 0 && !compact}>
      Reset
    </Button>
  );

  return (
    <>
      <Flex wrap gap="small" align="center" role="search" aria-label="Filters">
        {search && <div style={compact ? { width: "100%" } : undefined}>{search}</div>}
        {!compact && children}
        {drawerButton}
        {!compact && resetButton}
        {extra && <Space style={{ marginInlineStart: "auto" }}>{extra}</Space>}
      </Flex>
      {hasDrawer && (
        <Drawer
          title="Filters"
          open={open}
          onClose={() => setOpen(false)}
          size={compact ? "100%" : DRAWER.filters}
          destroyOnHidden={false}
          footer={
            <Flex justify="flex-end" gap="small">
              {onReset && (
                <Button
                  icon={<ClearOutlined />}
                  onClick={() => {
                    onReset();
                    setOpen(false);
                  }}
                >
                  Reset
                </Button>
              )}
              <Button type="primary" onClick={() => setOpen(false)}>
                Done
              </Button>
            </Flex>
          }
        >
          <Form layout="vertical">
            {compact && children && (
              <Flex vertical gap="small" style={{ marginBottom: 16 }}>
                {children}
              </Flex>
            )}
            {more}
          </Form>
        </Drawer>
      )}
    </>
  );
}

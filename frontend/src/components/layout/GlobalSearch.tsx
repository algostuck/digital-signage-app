import { SearchOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { AutoComplete, Input, Tag, Typography, theme } from "antd";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../lib/api";

interface SearchRow {
  id: string;
  name: string;
  subtitle: string | null;
  status: string | null;
}

interface SearchData {
  query: string;
  modules: Record<string, SearchRow[]>;
  total: number;
}

const MODULE_ROUTES: Record<string, string> = {
  devices: "/devices",
  content: "/content",
  locations: "/locations",
  campaigns: "/campaigns",
  playlists: "/playlists",
  schedules: "/schedules",
  users: "/users",
};

/** P2-SRC-001 global search: one box, every module you may view. */
export function GlobalSearch() {
  const { token } = theme.useToken();
  const navigate = useNavigate();
  const [term, setTerm] = useState("");
  const [debounced, setDebounced] = useState("");
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(term.trim()), 250);
    return () => clearTimeout(timer);
  }, [term]);

  const searchQuery = useQuery({
    queryKey: ["global-search", debounced],
    queryFn: () => api.get<SearchData>(`/search?q=${encodeURIComponent(debounced)}`),
    enabled: debounced.length >= 2,
  });

  const data = searchQuery.data?.data ?? null;

  const options =
    debounced.length < 2
      ? []
      : searchQuery.isLoading
        ? [{ label: <Typography.Text type="secondary">Searching…</Typography.Text>, options: [] }]
        : !data || data.total === 0
        ? [{ label: <Typography.Text type="secondary">No matches.</Typography.Text>, options: [] }]
        : Object.entries(data.modules)
            .filter(([, rows]) => rows.length > 0)
            .map(([module, rows]) => ({
              label: <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">{module}</span>,
              options: rows.map((row) => ({
                value: `${module}::${row.id}`,
                label: (
                  <span className="flex items-center gap-2">
                    <span className="font-medium text-slate-800">{row.name}</span>
                    {row.subtitle && <span className="text-xs text-slate-400">{row.subtitle}</span>}
                    {row.status && (
                      <Tag className="ml-auto" variant="filled">
                        {row.status}
                      </Tag>
                    )}
                  </span>
                ),
              })),
            }));

  return (
    <AutoComplete
      className="w-full max-w-[360px] min-w-[180px]"
      value={term}
      options={options}
      open={open && debounced.length >= 2}
      onOpenChange={setOpen}
      onSearch={(value) => {
        setTerm(value);
        setOpen(true);
      }}
      onSelect={(value: string) => {
        const [module] = value.split("::");
        setOpen(false);
        setTerm("");
        navigate(MODULE_ROUTES[module] ?? "/dashboard");
      }}
      popupMatchSelectWidth={360}
    >
      <Input
        placeholder="Search devices, content, campaigns…"
        aria-label="Global search"
        prefix={<SearchOutlined style={{ color: token.colorTextTertiary }} />}
        allowClear
        variant="filled"
        size="large"
      />
    </AutoComplete>
  );
}

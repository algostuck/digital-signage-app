import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
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
  const navigate = useNavigate();
  const [term, setTerm] = useState("");
  const [debounced, setDebounced] = useState("");
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(term.trim()), 250);
    return () => clearTimeout(timer);
  }, [term]);

  useEffect(() => {
    function onClickAway(event: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClickAway);
    return () => document.removeEventListener("mousedown", onClickAway);
  }, []);

  const searchQuery = useQuery({
    queryKey: ["global-search", debounced],
    queryFn: () => api.get<SearchData>(`/search?q=${encodeURIComponent(debounced)}`),
    enabled: debounced.length >= 2,
  });

  const data = searchQuery.data?.data ?? null;
  const showResults = open && debounced.length >= 2;

  return (
    <div ref={boxRef} className="relative w-72">
      <input
        value={term}
        onChange={(e) => {
          setTerm(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        placeholder="Search everything…"
        aria-label="Global search"
        className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
      />
      {showResults && (
        <div className="absolute left-0 right-0 top-full z-30 mt-1 max-h-96 overflow-y-auto rounded-md border border-slate-200 bg-white shadow-lg">
          {searchQuery.isLoading ? (
            <p className="px-3 py-2 text-sm text-slate-500">Searching…</p>
          ) : !data || data.total === 0 ? (
            <p className="px-3 py-2 text-sm text-slate-500">No matches.</p>
          ) : (
            Object.entries(data.modules)
              .filter(([, rows]) => rows.length > 0)
              .map(([module, rows]) => (
                <div key={module}>
                  <p className="bg-slate-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
                    {module}
                  </p>
                  {rows.map((row) => (
                    <button
                      key={row.id}
                      type="button"
                      onClick={() => {
                        setOpen(false);
                        setTerm("");
                        navigate(MODULE_ROUTES[module] ?? "/dashboard");
                      }}
                      className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm hover:bg-slate-50"
                    >
                      <span className="font-medium text-slate-800">{row.name}</span>
                      {row.subtitle && (
                        <span className="text-xs text-slate-400">{row.subtitle}</span>
                      )}
                      {row.status && (
                        <span className="ml-auto rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500">
                          {row.status}
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              ))
          )}
        </div>
      )}
    </div>
  );
}

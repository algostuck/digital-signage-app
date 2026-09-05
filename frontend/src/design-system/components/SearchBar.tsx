import { Input } from "antd";
import { useEffect, useState } from "react";

/**
 * List search (docs/design-system/COMPONENT_CATALOGUE.md): antd
 * Input.Search with clear, a debounced `onChange` and an accessible name.
 * Controlled by the page (usually URL state) so filters are shareable.
 */
export function SearchBar({
  value,
  onChange,
  placeholder = "Search",
  label = "Search",
  width = 260,
  loading,
  debounce = 250,
}: {
  value: string;
  onChange: (next: string) => void;
  placeholder?: string;
  /** Accessible name; defaults to "Search". */
  label?: string;
  width?: number | string;
  loading?: boolean;
  debounce?: number;
}) {
  const [draft, setDraft] = useState(value);
  useEffect(() => setDraft(value), [value]);
  useEffect(() => {
    if (draft === value) return;
    const timer = window.setTimeout(() => onChange(draft), debounce);
    return () => window.clearTimeout(timer);
  }, [draft, value, onChange, debounce]);

  return (
    <Input.Search
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onSearch={(term) => onChange(term)}
      placeholder={placeholder}
      aria-label={label}
      allowClear
      loading={loading}
      style={{ width, maxWidth: "100%" }}
    />
  );
}

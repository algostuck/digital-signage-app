import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface InventoryRow {
  id: string;
  name: string;
  device_id: string | null;
  location_id: string | null;
  slot_type: string;
  operating_hours: { start: string; end: string; days: number[] | null };
  rate_card_ref: string | null;
  active: boolean;
  bookings: number;
}

interface BookingRow {
  id: string;
  inventory_id: string;
  campaign_id: string;
  advertiser_ref: string;
  booked_units: number;
  start_at: string;
  end_at: string;
  status: string;
  links: number;
}

const STATUS_STYLE: Record<string, string> = {
  pending: "bg-sky-100 text-sky-700",
  confirmed: "bg-emerald-100 text-emerald-700",
  cancelled: "bg-slate-100 text-slate-500",
  completed: "bg-slate-200 text-slate-700",
};

/** P3-09/10 Ad Inventory + Bookings. Delivery rides existing campaigns;
 * bookings route through the shared Approvals inbox before confirming. */
export function AdsPage() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("ads.manage");
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<"inventory" | "bookings">("inventory");
  const [error, setError] = useState<string | null>(null);

  const inventoryQuery = useQuery({
    queryKey: ["ad-inventory"],
    queryFn: () => api.get<InventoryRow[]>("/ad-inventory"),
    retry: false,
  });
  const bookingsQuery = useQuery({
    queryKey: ["ad-bookings"],
    queryFn: () => api.get<BookingRow[]>("/ad-campaigns"),
    retry: false,
  });
  const devicesQuery = useQuery({
    queryKey: ["devices-brief"],
    queryFn: () => api.get<{ id: string; name: string }[]>("/devices?page_size=100"),
  });
  const campaignsQuery = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => api.get<{ id: string; name: string }[]>("/campaigns?page_size=100"),
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["ad-inventory"] });
    queryClient.invalidateQueries({ queryKey: ["ad-bookings"] });
  };
  const onError = (err: unknown) =>
    setError(err instanceof ApiError ? err.message : "Action failed");

  const [invForm, setInvForm] = useState({ name: "", device_id: "", start: "09:00", end: "21:00" });
  const createInventory = useMutation({
    mutationFn: () =>
      api.post("/ad-inventory", {
        name: invForm.name,
        device_id: invForm.device_id || null,
        operating_hours: { start: invForm.start, end: invForm.end },
      }),
    onSuccess: () => {
      refresh();
      setError(null);
      setInvForm({ name: "", device_id: "", start: "09:00", end: "21:00" });
    },
    onError,
  });

  const [bookForm, setBookForm] = useState({
    inventory_id: "", campaign_id: "", advertiser: "", units: "100",
    start: "", end: "",
  });
  const createBooking = useMutation({
    mutationFn: () =>
      api.post("/ad-campaigns", {
        inventory_id: bookForm.inventory_id,
        campaign_id: bookForm.campaign_id,
        advertiser_ref: bookForm.advertiser,
        booked_units: Number(bookForm.units),
        start_at: new Date(bookForm.start).toISOString(),
        end_at: new Date(bookForm.end).toISOString(),
      }),
    onSuccess: () => {
      refresh();
      setError(null);
    },
    onError,
  });
  const cancelBooking = useMutation({
    mutationFn: (id: string) => api.post(`/ad-campaigns/${id}/cancel`, {}),
    onSuccess: () => refresh(),
    onError,
  });

  if (inventoryQuery.isError)
    return (
      <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800" role="alert">
        {inventoryQuery.error instanceof ApiError
          ? inventoryQuery.error.message
          : "Advertising unavailable."}
      </p>
    );

  const inventory = inventoryQuery.data?.data ?? [];
  const bookings = bookingsQuery.data?.data ?? [];
  const devices = devicesQuery.data?.data ?? [];
  const campaigns = campaignsQuery.data?.data ?? [];
  const inventoryName = (id: string) => inventory.find((i) => i.id === id)?.name ?? "—";
  const campaignName = (id: string) => campaigns.find((c) => c.id === id)?.name ?? "—";

  function submit(e: FormEvent, mutate: () => void) {
    e.preventDefault();
    setError(null);
    mutate();
  }

  return (
    <div>
      <h1 className="text-xl font-semibold text-slate-900">Advertising</h1>
      <p className="mt-1 text-sm text-slate-500">
        Sell screen time: inventory slots, bookings against existing
        campaigns, and billing-ready proof-of-play reconciliation (see
        Reports → Ads).
      </p>
      <div className="mt-4 border-b border-slate-200" role="tablist">
        {(["inventory", "bookings"] as const).map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            onClick={() => setTab(t)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium capitalize ${
              tab === t
                ? "border-slate-900 text-slate-900"
                : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "inventory" && (
        <div className="mt-4 space-y-4">
          {canManage && (
            <form
              className="flex flex-wrap items-end gap-3 rounded-lg border border-slate-200 bg-white p-4"
              onSubmit={(e) => submit(e, () => createInventory.mutate())}
            >
              <label className="block text-sm">
                <span className="block text-xs text-slate-500">Slot name</span>
                <input
                  required
                  value={invForm.name}
                  onChange={(e) => setInvForm((p) => ({ ...p, name: e.target.value }))}
                  className="mt-0.5 w-52 rounded-md border border-slate-300 px-2 py-1.5"
                />
              </label>
              <label className="block text-sm">
                <span className="block text-xs text-slate-500">Device</span>
                <select
                  required
                  value={invForm.device_id}
                  onChange={(e) => setInvForm((p) => ({ ...p, device_id: e.target.value }))}
                  className="mt-0.5 rounded-md border border-slate-300 px-2 py-1.5"
                >
                  <option value="">Select…</option>
                  {devices.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-sm">
                <span className="block text-xs text-slate-500">Hours</span>
                <span className="flex items-center gap-1">
                  <input
                    type="time"
                    value={invForm.start}
                    onChange={(e) => setInvForm((p) => ({ ...p, start: e.target.value }))}
                    className="mt-0.5 rounded-md border border-slate-300 px-2 py-1.5"
                  />
                  –
                  <input
                    type="time"
                    value={invForm.end}
                    onChange={(e) => setInvForm((p) => ({ ...p, end: e.target.value }))}
                    className="mt-0.5 rounded-md border border-slate-300 px-2 py-1.5"
                  />
                </span>
              </label>
              <button
                type="submit"
                disabled={createInventory.isPending}
                className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
              >
                Add slot
              </button>
            </form>
          )}
          <section className="rounded-lg border border-slate-200 bg-white p-4">
            <table className="w-full text-left text-sm">
              <tbody>
                {inventory.length === 0 && (
                  <tr>
                    <td className="py-3 text-sm text-slate-400">No inventory yet.</td>
                  </tr>
                )}
                {inventory.map((slot) => (
                  <tr key={slot.id} className="border-t border-slate-100">
                    <td className="py-2 pr-4 font-medium text-slate-800">{slot.name}</td>
                    <td className="py-2 pr-4 text-xs text-slate-500">
                      {slot.slot_type} · {slot.operating_hours.start}–
                      {slot.operating_hours.end} · {slot.bookings} booking
                      {slot.bookings === 1 ? "" : "s"}
                    </td>
                    <td className="py-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          slot.active
                            ? "bg-emerald-100 text-emerald-700"
                            : "bg-slate-100 text-slate-500"
                        }`}
                      >
                        {slot.active ? "active" : "inactive"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </div>
      )}

      {tab === "bookings" && (
        <div className="mt-4 space-y-4">
          {canManage && (
            <form
              className="grid grid-cols-2 items-end gap-3 rounded-lg border border-slate-200 bg-white p-4 sm:grid-cols-3 lg:grid-cols-6"
              onSubmit={(e) => submit(e, () => createBooking.mutate())}
            >
              <label className="block text-sm">
                <span className="block text-xs text-slate-500">Slot</span>
                <select
                  required
                  value={bookForm.inventory_id}
                  onChange={(e) =>
                    setBookForm((p) => ({ ...p, inventory_id: e.target.value }))
                  }
                  className="mt-0.5 w-full rounded-md border border-slate-300 px-2 py-1.5"
                >
                  <option value="">Select…</option>
                  {inventory.map((i) => (
                    <option key={i.id} value={i.id}>
                      {i.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-sm">
                <span className="block text-xs text-slate-500">Campaign</span>
                <select
                  required
                  value={bookForm.campaign_id}
                  onChange={(e) =>
                    setBookForm((p) => ({ ...p, campaign_id: e.target.value }))
                  }
                  className="mt-0.5 w-full rounded-md border border-slate-300 px-2 py-1.5"
                >
                  <option value="">Select…</option>
                  {campaigns.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-sm">
                <span className="block text-xs text-slate-500">Advertiser</span>
                <input
                  required
                  value={bookForm.advertiser}
                  onChange={(e) =>
                    setBookForm((p) => ({ ...p, advertiser: e.target.value }))
                  }
                  className="mt-0.5 w-full rounded-md border border-slate-300 px-2 py-1.5"
                />
              </label>
              <label className="block text-sm">
                <span className="block text-xs text-slate-500">Units (plays)</span>
                <input
                  type="number"
                  min={1}
                  value={bookForm.units}
                  onChange={(e) => setBookForm((p) => ({ ...p, units: e.target.value }))}
                  className="mt-0.5 w-full rounded-md border border-slate-300 px-2 py-1.5"
                />
              </label>
              <label className="block text-sm">
                <span className="block text-xs text-slate-500">From</span>
                <input
                  required
                  type="datetime-local"
                  value={bookForm.start}
                  onChange={(e) => setBookForm((p) => ({ ...p, start: e.target.value }))}
                  className="mt-0.5 w-full rounded-md border border-slate-300 px-2 py-1.5"
                />
              </label>
              <label className="block text-sm">
                <span className="block text-xs text-slate-500">To</span>
                <input
                  required
                  type="datetime-local"
                  value={bookForm.end}
                  onChange={(e) => setBookForm((p) => ({ ...p, end: e.target.value }))}
                  className="mt-0.5 w-full rounded-md border border-slate-300 px-2 py-1.5"
                />
              </label>
              <button
                type="submit"
                disabled={createBooking.isPending}
                className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
              >
                Book
              </button>
            </form>
          )}
          <section className="rounded-lg border border-slate-200 bg-white p-4">
            <p className="text-xs text-slate-400">
              New bookings await approval in the Approvals inbox before
              confirming.
            </p>
            <table className="mt-2 w-full text-left text-sm">
              <tbody>
                {bookings.length === 0 && (
                  <tr>
                    <td className="py-3 text-sm text-slate-400">No bookings yet.</td>
                  </tr>
                )}
                {bookings.map((b) => (
                  <tr key={b.id} className="border-t border-slate-100">
                    <td className="py-2 pr-4 font-medium text-slate-800">
                      {b.advertiser_ref}
                    </td>
                    <td className="py-2 pr-4 text-xs text-slate-500">
                      {inventoryName(b.inventory_id)} · {campaignName(b.campaign_id)} ·{" "}
                      {b.booked_units} plays · {b.links} delivered
                    </td>
                    <td className="py-2 pr-4">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          STATUS_STYLE[b.status] ?? ""
                        }`}
                      >
                        {b.status}
                      </span>
                    </td>
                    <td className="py-2">
                      {canManage &&
                        (b.status === "pending" || b.status === "confirmed") && (
                          <button
                            type="button"
                            onClick={() => cancelBooking.mutate(b.id)}
                            className="rounded-md border border-red-300 px-2 py-1 text-xs font-medium text-red-600"
                          >
                            Cancel
                          </button>
                        )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </div>
      )}

      {error && (
        <p role="alert" className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}
    </div>
  );
}

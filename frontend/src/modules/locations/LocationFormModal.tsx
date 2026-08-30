import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { FormField } from "../../components/ui/FormField";
import { Modal } from "../../components/ui/Modal";
import { api, ApiError } from "../../lib/api";
import type { LocationDetail, LocationType } from "./types";

interface Props {
  existing?: LocationDetail;
  parentId?: string | null;
  parentName?: string | null;
  onClose: () => void;
  onSaved: (id: string) => void;
}

export function LocationFormModal({ existing, parentId, parentName, onClose, onSaved }: Props) {
  const [name, setName] = useState(existing?.name ?? "");
  const [code, setCode] = useState(existing?.code ?? "");
  const [typeId, setTypeId] = useState(existing?.type?.id ?? "");
  const [address, setAddress] = useState(existing?.address ?? "");
  const [timezone, setTimezone] = useState(existing?.timezone ?? "");
  const [error, setError] = useState<string | null>(null);

  const typesQuery = useQuery({
    queryKey: ["location-types"],
    queryFn: () => api.get<LocationType[]>("/location-types"),
  });

  const save = useMutation({
    mutationFn: () => {
      const body = {
        name,
        code: code || null,
        type_id: typeId || null,
        address: address || null,
        timezone: timezone || null,
      };
      return existing
        ? api.patch<LocationDetail>(`/locations/${existing.id}`, body)
        : api.post<LocationDetail>("/locations", { ...body, parent_id: parentId ?? null });
    },
    onSuccess: (envelope) => onSaved(envelope.data!.id),
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Failed to save location"),
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    save.mutate();
  }

  const title = existing
    ? `Edit location: ${existing.name}`
    : parentName
      ? `Add child under ${parentName}`
      : "Add root location";

  return (
    <Modal title={title} open onClose={onClose}>
      <form className="space-y-4" onSubmit={onSubmit}>
        <FormField
          id="loc-name"
          label="Name"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <FormField
          id="loc-code"
          label="Code (unique among siblings, optional)"
          value={code}
          onChange={(e) => setCode(e.target.value)}
        />
        <div>
          <label htmlFor="loc-type" className="block text-sm font-medium text-slate-700">
            Type
          </label>
          <select
            id="loc-type"
            value={typeId}
            onChange={(e) => setTypeId(e.target.value)}
            className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm"
          >
            <option value="">— none —</option>
            {(typesQuery.data?.data ?? []).map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </div>
        <FormField
          id="loc-address"
          label="Address (optional)"
          value={address}
          onChange={(e) => setAddress(e.target.value)}
        />
        <FormField
          id="loc-timezone"
          label="Timezone (IANA, optional — inherits when empty)"
          value={timezone}
          onChange={(e) => setTimezone(e.target.value)}
          placeholder="e.g. Asia/Kolkata"
        />
        {error && (
          <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={save.isPending}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {save.isPending ? "Saving…" : existing ? "Save changes" : "Create location"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

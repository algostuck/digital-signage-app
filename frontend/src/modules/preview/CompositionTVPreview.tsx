import { ApiError } from "../../lib/api";
import type { LayoutCanvas } from "../design/types";
import { TVPreviewModal } from "./TVPreviewModal";
import type { ManifestPlaylist } from "./types";
import { useCompositionPreviewSource } from "./usePreviewSource";

/** Previews editor state the backend has never seen — an unsaved canvas or
 * a playlist mid-edit. It deliberately resolves no schedule or targeting;
 * the modal labels it a draft composition so it is never mistaken for what
 * a device would play. Callers holding a `PlaylistDetail` convert it with
 * `playlistToManifestShape` first. */
export function CompositionTVPreview({
  open,
  onClose,
  title,
  canvas = null,
  playlist = null,
}: {
  open: boolean;
  onClose(): void;
  title: string;
  canvas?: LayoutCanvas | null;
  playlist?: ManifestPlaylist | null;
}) {
  const { source, query } = useCompositionPreviewSource({
    canvas,
    playlist,
    label: title,
    enabled: open,
  });

  return (
    <TVPreviewModal
      open={open}
      onClose={onClose}
      title={title}
      source={source}
      // `isPending` stays true for a disabled query, which would show a
      // skeleton forever when a composition has no assets to resolve.
      loading={query.isPending && query.fetchStatus === "fetching"}
      error={
        query.error
          ? query.error instanceof ApiError
            ? query.error.message
            : "Could not resolve media for this preview"
          : null
      }
      onRetry={() => void query.refetch()}
    />
  );
}

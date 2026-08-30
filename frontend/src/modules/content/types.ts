export interface Folder {
  id: string;
  parent_id: string | null;
  name: string;
  status: string;
}

export interface AssetVersion {
  id: string;
  version_no: number;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  checksum: string | null;
  width: number | null;
  height: number | null;
  duration_ms: number | null;
  processing_status: string;
  processing_error: string | null;
  created_at: string;
}

export interface Asset {
  id: string;
  folder_id: string | null;
  type: string;
  name: string;
  description: string | null;
  status: string;
  checksum: string | null;
  created_at: string;
  updated_at: string;
  tags: { id: string; key: string; value: string }[];
  current_version: AssetVersion | null;
  thumbnail_url: string | null;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

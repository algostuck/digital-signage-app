export interface LocationType {
  id: string;
  code: string;
  name: string;
}

export interface LocationTag {
  id: string;
  key: string;
  value: string;
}

export interface LocationNode {
  id: string;
  parent_id: string | null;
  name: string;
  code: string | null;
  path: string;
  depth: number;
  address: string | null;
  latitude: number | null;
  longitude: number | null;
  timezone: string | null;
  status: string;
  metadata_json: Record<string, unknown> | null;
  type: LocationType | null;
  tags: LocationTag[];
}

export interface LocationDetail extends LocationNode {
  effective_timezone: string;
  children_count: number;
  descendants_count: number;
}

export interface TreeEntry {
  node: LocationNode;
  children: TreeEntry[];
}

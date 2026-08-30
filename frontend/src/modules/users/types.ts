export interface RoleBrief {
  id: string;
  name: string;
  is_system: boolean;
}

export interface UserRow {
  id: string;
  email: string;
  full_name: string;
  status: string;
  last_login_at: string | null;
  created_at: string;
  roles: RoleBrief[];
}

export interface Permission {
  code: string;
  description: string | null;
}

export interface Role {
  id: string;
  name: string;
  description: string | null;
  is_system: boolean;
  permissions: Permission[];
}

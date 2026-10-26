export type Staff = {
  id: string;
  email: string;
  full_name: string;
  is_staff: boolean;
  is_superuser: boolean;
};

export type StaffMe = {
  user: Staff;
};

export type DemoGrant = {
  id: string;
  email: string;
  full_name: string;
  access_pme: boolean;
  access_cabinet: boolean;
  is_active: boolean;
  notes: string;
  granted_by_email: string;
  last_emailed_at: string | null;
  created_at: string;
  temporary_password?: string | null;
  email_sent?: boolean;
  email_error?: string;
};

export type TenantOfficer = {
  full_name: string;
  role: string;
  role_label: string;
};

export type TenantCompany = {
  id: string;
  name: string;
  legal_name: string;
  country_code: string;
  country_label: string;
  currency_code: string;
  rccm: string;
  tax_id: string;
  legal_form: string;
  legal_form_label: string;
  tax_regime: string;
  tax_regime_label: string;
  accounting_regime: string;
  accounting_regime_label: string;
  activity_kind: string;
  activity_label: string;
  city: string;
  address: string;
  is_active: boolean;
  identity_complete: boolean;
  identity_missing: string[];
  officers: TenantOfficer[];
  created_at: string | null;
};

export type TenantMember = {
  id: string;
  email: string;
  full_name: string;
  role: string;
  role_label: string;
  is_active: boolean;
  last_login: string | null;
  date_joined: string | null;
};

export type TenantOrg = {
  id: string;
  name: string;
  slug: string;
  type: string;
  type_label: string;
  is_demo: boolean;
  setup_data: string;
  identity_complete: boolean;
  company_count: number;
  member_count: number;
  created_at: string | null;
  updated_at: string | null;
  companies: TenantCompany[];
  members: TenantMember[];
};

export type TenantDirectory = {
  org_count: number;
  pme_count: number;
  cabinet_count: number;
  demo_count: number;
  client_count: number;
  company_count: number;
  user_count: number;
  organizations: TenantOrg[];
};

export type PlatformUserOrg = {
  id: string;
  name: string;
  slug: string;
  type: string;
  type_label: string;
  is_demo: boolean;
  role: string;
  role_label: string;
};

export type PlatformUser = {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_staff: boolean;
  last_login: string | null;
  date_joined: string | null;
  has_demo_grant: boolean;
  organizations: PlatformUserOrg[];
};

export type ChartPoint = {
  label: string;
  value: number;
  code?: string;
};

export type Dashboard = {
  kpis: {
    org_count: number;
    client_count: number;
    demo_count: number;
    company_count: number;
    user_count: number;
    grants_active: number;
    identity_complete: number;
    identity_incomplete: number;
    identity_rate: number;
    users_active_7d: number;
    users_never: number;
    entries_posted: number;
    entries_draft: number;
  };
  by_type: ChartPoint[];
  by_kind: ChartPoint[];
  by_identity: ChartPoint[];
  by_country: ChartPoint[];
  orgs_by_week: ChartPoint[];
  users_by_week: ChartPoint[];
  grants: { active: number; revoked: number };
  watch: { id: string; name: string; slug: string; type_label: string; reason: string }[];
  recent: {
    id: string;
    name: string;
    slug: string;
    type_label: string;
    is_demo: boolean;
    created_at: string | null;
  }[];
};

export type MailStatus = {
  provider: string;
  host: string;
  port: number;
  use_ssl: boolean;
  use_tls: boolean;
  username: string;
  from_email: string;
  password_set: boolean;
  backend: string;
  mode: string;
  configured: boolean;
  erp_url: string;
};

export type MailTestResult = {
  ok: boolean;
  to: string;
  from_email: string;
  mode: string;
  message: string;
};



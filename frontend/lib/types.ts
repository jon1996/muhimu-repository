export type OrganizationType = "sme" | "cabinet";

export type Role = "owner" | "admin" | "accountant" | "auditor" | "viewer";

export type Organization = {
  id: string;
  name: string;
  slug: string;
  type: OrganizationType;
  setup_data?: "" | "empty" | "demo";
  is_demo?: boolean;
};

export type Membership = {
  id: string;
  role: Role;
  organization: Organization;
};

export type User = {
  id: string;
  email: string;
  full_name: string;
  is_staff: boolean;
};

export type Me = {
  user: User;
  memberships: Membership[];
};

export type CompanyOfficer = {
  id: string;
  full_name: string;
  role: string;
  role_label: string;
  nationality: string;
  position: number;
};

export type Company = {
  id: string;
  name: string;
  legal_name: string;
  country_code: string;
  country_label?: string;
  currency_code: string;
  accounting_regime: "normal" | "smt";
  activity_kind: "trade" | "craft" | "services";
  procedure_manual: string;
  going_concern: boolean;
  is_active: boolean;
  acronym: string;
  address: string;
  city: string;
  postal_code: string;
  phone: string;
  email: string;
  tax_id: string;
  rccm: string;
  social_register: string;
  legal_form: string;
  legal_form_label: string;
  tax_regime: string;
  tax_regime_label: string;
  naema_code: string;
  control_kind: string;
  control_label: string;
  establishments_domestic: number;
  establishments_foreign: number;
  distinct_branch_accounts: boolean;
  auditor_name: string;
  auditor_order_no: string;
  signatory_name: string;
  signatory_title: string;
  banks: string;
  setup_data?: "" | "empty" | "demo";
  officers: CompanyOfficer[];
  identity_complete?: boolean;
  identity_missing?: string[];
};

export type AuditLog = {
  id: string;
  action: string;
  resource_type: string;
  resource_id: string;
  actor_email: string | null;
  company_id: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type LedgerExercise = {
  id: string;
  year: number;
  starts_on: string;
  ends_on: string;
  status: string;
  closed_on: string | null;
  approved_on: string | null;
  net_result: string;
  revenue: string;
  legal_reserve_amount: string;
  free_reserve_amount: string;
  retained_amount: string;
  dividends_amount: string;
  result_entry_id: string | null;
  allocation_entry_id: string | null;
  payment_entry_id: string | null;
  opening_entry_id?: string | null;
  suggested_legal_reserve: string;
  suggested_retained: string;
  blockers: string[];
  can_close: boolean;
  can_allocate: boolean;
};

export type OpeningState = {
  year: number;
  prior_year: number;
  posted: boolean;
  entry_id: string | null;
  entry_number: string;
  prior_seeded: number;
  can_post: boolean;
  blockers: string[];
  template: string;
};

export type OpeningPreview = {
  rows: { account_id: string; code: string; label: string; debit: string; credit: string; kind: string }[];
  an_lines: { account_id: string; code: string; label: string; debit: string; credit: string; kind: string }[];
  pnl_count: number;
  an_debit: string;
  an_credit: string;
  net_result_prior: string;
  warnings: string[];
  errors: string[];
  ok: boolean;
  posted: boolean;
  entry_id: string | null;
  entry_number: string;
  prior_seeded: number;
};

export type LedgerStatus = {
  ready: boolean;
  exercise: LedgerExercise | null;
  current_period: {
    id: string;
    year: number;
    month: number;
    starts_on: string;
    ends_on: string;
    status: string;
  } | null;
  accounts: number;
  journals: number;
  setup_data?: "" | "empty" | "demo";
  needs_choice?: boolean;
  entries?: number;
};

export type AccountLevel = "class" | "subclass" | "principal" | "secondary" | "auxiliary";

export type AccountFamily =
  | "resource"
  | "fixed_asset"
  | "stock"
  | "third_party"
  | "treasury"
  | "expense"
  | "income"
  | "other";

export type AccountSense = "debit" | "credit" | "either";

export type LedgerAccount = {
  id: string;
  code: string;
  label: string;
  account_class: string;
  level: AccountLevel;
  level_label: string;
  family: AccountFamily;
  family_label: string;
  sense: AccountSense;
  sense_label: string;
  is_postable: boolean;
  is_collective: boolean;
  is_syscohada: boolean;
  notes: string;
  parent_id: string | null;
  parent_code: string | null;
  children_count: number;
  anatomy: {
    class_code: string | null;
    two_digit: string | null;
    principal: string | null;
    divisionary: string | null;
    entity: string | null;
    subclass: string | null;
    secondary: string | null;
    auxiliary: string | null;
  };
  reading?: {
    constants: { kind: string; title: string; detail: string }[];
    parallel_code: string | null;
    parallel_label: string | null;
    parallel_kind: string | null;
  };
};

export type AccountFiche = {
  code: string;
  fiche_code: string;
  title: string;
  contenu: string;
  subdivisions: string;
  commentaires: string;
  fonctionnement: string;
  exclusions: string;
  controles: string;
  debit: string[];
  credit: string[];
};

export type AccountImportRow = {
  line: number;
  code: string;
  label: string;
  action: "create" | "update" | string;
  errors: string[];
  level: string;
  family: string;
  account_class: string;
};

export type AccountImportReport = {
  applied: boolean;
  created: number;
  updated: number;
  errors: number;
  rows: AccountImportRow[];
};

export type LedgerJournal = {
  id: string;
  code: string;
  name: string;
  type: string;
};

export type LedgerPeriod = {
  id: string;
  year: number;
  month: number;
  starts_on: string;
  ends_on: string;
  status: string;
  validated_at?: string | null;
  it_closed_at?: string | null;
  seal?: string;
};

export type StatementLine = {
  code: string;
  label: string;
  current: string;
  prior: string;
  bold: boolean;
  gross?: string | null;
  amort?: string | null;
  kind?: string;
};

export type StatementIndicator = {
  current: string;
  prior: string;
};

export type StatementNote = {
  number: number;
  title: string;
  status: "A" | "NA" | string;
  required: boolean;
  body: string;
  conformity: string;
  methods: string;
  derogations: string;
  extra: string;
  computed?: string;
};

export type FinancialStatements = {
  regime: string;
  scope?: string | null;
  exercise_year: number;
  period_id: string;
  period_label: string;
  comparative_year: number | null;
  going_concern: boolean;
  closed_on: string | null;
  approved_on: string | null;
  arrete_due_on: string;
  ago_due_on: string;
  notes_annexes: string;
  entity?: {
    name: string;
    legal_name: string;
    country_code: string;
    country_label?: string;
    currency_code: string;
    regime: string;
    regime_label: string;
    activity_kind: string;
    activity_label: string;
    starts_on: string;
    ends_on: string;
    duration_months: number;
    acronym?: string;
    address?: string;
    city?: string;
    postal_code?: string;
    phone?: string;
    email?: string;
    tax_id?: string;
    rccm?: string;
    social_register?: string;
    legal_form?: string;
    legal_form_label?: string;
    tax_regime?: string;
    tax_regime_label?: string;
    naema_code?: string;
    control_kind?: string;
    control_label?: string;
    establishments_domestic?: number;
    establishments_foreign?: number;
    distinct_branch_accounts?: boolean;
    auditor_name?: string;
    auditor_order_no?: string;
    signatory_name?: string;
    signatory_title?: string;
    banks?: string;
    officers?: { full_name: string; role_label: string; nationality: string }[];
  } | null;
  analysis?: {
    fr: StatementIndicator;
    fr_bas: StatementIndicator;
    bfg: StatementIndicator;
    bfe: StatementIndicator;
    bf_hao: StatementIndicator;
    tn: StatementIndicator;
    conversion: StatementIndicator;
    cafg: StatementIndicator;
    ebe: StatementIndicator;
    net: StatementIndicator;
  } | null;
  notes?: StatementNote[];
  bilan: { actif: StatementLine[]; passif: StatementLine[]; balanced: boolean };
  result: { lines: StatementLine[]; net: string };
  tft: { lines: StatementLine[] };
  smt?: {
    regime: string;
    activity_kind: string;
    threshold: string;
    threshold_label: string;
    revenue: string;
    eligible: boolean;
    warning: string;
  } | null;
};

export type SmtEligibility = NonNullable<FinancialStatements["smt"]>;

export type SourceDocument = {
  id: string;
  entry_id: string | null;
  original_name: string;
  content_type: string;
  size: number;
  sha256: string;
  issued_on: string;
  keep_until: string;
  created_at: string;
};

export type InventoryLine = {
  id: string;
  account_id: string | null;
  account_code: string;
  description: string;
  quantity: string;
  unit: string;
  unit_value: string;
  amount: string;
};

export type InventoryCampaign = {
  id: string;
  inventoried_on: string;
  status: "draft" | "closed" | string;
  notes: string;
  method?: string;
  method_label?: string;
  variation_entry_id?: string | null;
  variation_entry_number?: string;
  lines: InventoryLine[];
  total: string;
};

export type LegalBooks = {
  numbered: boolean;
  dated: string;
  journal: {
    id: string;
    number_display: string;
    journal_code: string;
    accounting_date: string;
    value_date: string;
    description: string;
    document_ref: string;
    total: string;
  }[];
  inventory_summary: string;
};

export type EntryLine = {
  id: string;
  account_id: string;
  account_code: string;
  account_label: string;
  label: string;
  debit: string;
  credit: string;
  third_party_id?: string | null;
  third_party_name?: string;
  lettering?: string;
  due_on?: string;
  cage_section_id?: string | null;
  cage_section_code?: string;
  currency_code?: string;
  foreign_amount?: string;
  fx_rate?: string;
};

export type ThirdParty = {
  id: string;
  kind: string;
  kind_label: string;
  name: string;
  reference: string;
  tax_id: string;
  account_id: string;
  account_code: string;
  is_active: boolean;
};

export type OpenItem = {
  id: string;
  entry_id: string;
  entry_number: string;
  accounting_date: string;
  account_id: string;
  account_code: string;
  third_party_id: string | null;
  third_party_name: string;
  label: string;
  debit: string;
  credit: string;
  lettering: string;
  due_on: string;
  bucket: string;
};

export type BankBookLine = {
  id: string;
  entry_id: string;
  entry_number: string;
  accounting_date: string;
  account_id: string;
  account_code: string;
  label: string;
  debit: string;
  credit: string;
  pointage: string;
};

export type BankStatementLine = {
  id: string;
  statement_id: string;
  line_date: string;
  label: string;
  bank_debit: string;
  bank_credit: string;
  pointage: string;
};

export type BankStatement = {
  id: string;
  account_id: string;
  account_code: string;
  statement_date: string;
  bank_balance: string;
};

export type BankRecon = {
  account_id: string;
  account_code: string;
  account_label: string;
  book_balance: string;
  bank_balance: string;
  unpointed_book_net: string;
  unpointed_statement_net: string;
  control: string;
  statement: BankStatement | null;
  book_lines: BankBookLine[];
  statement_lines: BankStatementLine[];
};

export type OfxImport = {
  created: number;
  skipped: number;
  statement: BankStatement;
};

export type CashCount = {
  id: string;
  account_id: string;
  account_code: string;
  counted_on: string;
  physical_amount: string;
  book_amount: string;
  variance: string;
  variance_kind: string;
  contra_code: string;
  notes: string;
  entry_id: string | null;
  entry_number: string;
};

export type CashPanel = {
  account_id: string;
  account_code: string;
  account_label: string;
  book_balance: string;
  physical_amount: string;
  variance: string;
  variance_kind: string;
  contra_code: string;
  count: CashCount | null;
  counts: CashCount[];
  book_lines: BankBookLine[];
};

export type Commitment = {
  id: string;
  kind: string;
  kind_label: string;
  side: string;
  side_label: string;
  label: string;
  counterparty: string;
  amount: string;
  starts_on: string;
  ends_on: string;
  is_active: boolean;
  entry_id: string | null;
  entry_number: string;
  origin_entry_id: string | null;
  class9_debit: string;
  class9_credit: string;
};

export type EscomptePreview = {
  journal_id: string;
  journal_code: string;
  description: string;
  nominal: string;
  agios: string;
  net: string;
  liability_code: string;
  lines: Array<{
    account_id: string;
    account_code: string;
    account_label: string;
    debit: string;
    credit: string;
    label: string;
    third_party_id: string | null;
    due_on: string;
  }>;
};

export type EsgReport = {
  id: string;
  year: number;
  headcount: number;
  hires: number;
  dismissals: number;
  disabled_count: number;
  social_dialogue: string;
  health: string;
  training: string;
  equality: string;
  env_policy: string;
  waste: string;
  water: string;
  energy: string;
  ghg: string;
  biodiversity: string;
  territory: string;
  neighbors: string;
  patronage: string;
  purchases: string;
  required: boolean;
  threshold: number;
  chapter30_threshold: number;
  payroll: string;
  note_preview: string;
};

export type JournalEntry = {
  id: string;
  journal_id: string;
  journal_code: string;
  number: number | null;
  number_display: string;
  accounting_date: string;
  value_date: string;
  description: string;
  document_ref: string;
  status: "draft" | "posted";
  period_id: string;
  exercise_id: string;
  reversed_entry_id: string | null;
  lines: EntryLine[];
  total_debit: string;
  total_credit: string;
};

export type BalanceRow = {
  account_id: string;
  code: string;
  label: string;
  open_debit: string;
  open_credit: string;
  mov_debit: string;
  mov_credit: string;
  close_debit: string;
  close_credit: string;
};

export type Class9Balance = {
  engagements: BalanceRow[];
  cage: BalanceRow[];
};

export type CageSection = {
  id: string;
  code: string;
  label: string;
  account_id: string;
  account_code: string;
  is_default: boolean;
  is_active: boolean;
};

export type CageResult = {
  section_id: string;
  code: string;
  label: string;
  charges: string;
  products: string;
  result: string;
};

export type CagePanel = {
  sections: CageSection[];
  results: CageResult[];
  pending: number;
  reflected: number;
  last_entry_id: string | null;
  last_entry_number: string;
  created: number;
  skipped: number;
  closed?: boolean;
  close_entry_id?: string | null;
  close_entry_number?: string;
  analytical_result?: string;
};

export type GeneralLedger = {
  account_id: string;
  code: string;
  label: string;
  open_debit: string;
  open_credit: string;
  close_balance: string;
  lines: {
    id: string;
    entry_id: string;
    number_display: string;
    journal_code: string;
    accounting_date: string;
    label: string;
    debit: string;
    credit: string;
    balance: string;
  }[];
};

export type FixedAsset = {
  id: string;
  reference: string;
  label: string;
  kind: string;
  parent_id: string | null;
  acquired_on: string;
  in_service_on: string;
  cost: string;
  residual_value: string;
  useful_life_months: number;
  method: string;
  asset_account_id: string;
  asset_account_code: string;
  amort_account_id: string | null;
  amort_account_code: string;
  expense_account_id: string | null;
  expense_account_code: string;
  status: string;
  disposed_on: string | null;
  notes: string;
  accumulated: string;
  net: string;
  depreciable: boolean;
  charge_preview?: string | null;
};

export type AssetSuggest = {
  amort_account_id: string | null;
  amort_account_code: string;
  expense_account_id: string | null;
  expense_account_code: string;
};

export type DepreciateResult = {
  posted: boolean;
  count: number;
  total: string;
  entry_id: string | null;
  number_display: string;
};

export type ConsolidationMember = {
  id: string;
  company_id: string;
  company_name: string;
  currency_code: string;
  method: string;
  ownership_pct: string;
  is_parent: boolean;
  is_active: boolean;
};

export type ConsolidationElimination = {
  id: string;
  code: string;
  label: string;
  amount: string;
  kind: string;
};

export type ConsolidationSummary = ConsolidationMember & {
  included: boolean;
  warning: string;
  period_label: string;
  sales: string;
  net: string;
  total_actif: string;
};

export type ConsolidationGroup = {
  id: string;
  name: string;
  kind: "consolidated" | "combined" | string;
  year: number;
  currency_code: string;
  parent_id: string | null;
  parent_name: string;
  notes: string;
  members: ConsolidationMember[];
  eliminations: ConsolidationElimination[];
  warnings?: string[];
  minorities?: string;
  summaries?: ConsolidationSummary[];
  statements?: FinancialStatements | null;
};

export type FxRate = {
  id: string;
  currency_code: string;
  rate_date: string;
  rate: string;
};

export type FxRevalueLine = {
  account_id: string;
  account_code: string;
  account_label: string;
  currency_code: string;
  foreign_net: string;
  book_net: string;
  closing_rate: string;
  target: string;
  difference: string;
  kind: string;
  debit_account_code: string;
  credit_account_code: string;
};

export type FxRevaluePreview = {
  as_of: string;
  functional: string;
  ok: boolean;
  posted: boolean;
  entry_id: string | null;
  entry_number: string;
  lines: FxRevalueLine[];
  gain: string;
  loss: string;
  warnings: string[];
  errors: string[];
};

export const ROLE_LABELS: Record<Role, string> = {
  owner: "Propriétaire",
  admin: "Administrateur",
  accountant: "Comptable",
  auditor: "Auditeur",
  viewer: "Lecteur",
};

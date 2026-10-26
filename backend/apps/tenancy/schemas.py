from ninja import Schema


class OrganizationOut(Schema):
    id: str
    name: str
    slug: str
    type: str
    setup_data: str = ""
    is_demo: bool = False


class OrganizationIn(Schema):
    name: str
    type: str


class OwnOrganizationIn(Schema):
    type: str
    name: str
    company_name: str
    legal_name: str = ""
    country_code: str = "CI"
    currency_code: str = "XOF"


class MembershipOut(Schema):
    id: str
    role: str
    organization: OrganizationOut


class OfficerOut(Schema):
    id: str
    full_name: str
    role: str
    role_label: str = ""
    nationality: str = ""
    position: int = 0


class OfficerIn(Schema):
    full_name: str
    role: str = "manager"
    nationality: str = ""
    position: int = 0


class CompanyOut(Schema):
    id: str
    name: str
    legal_name: str
    country_code: str
    currency_code: str
    accounting_regime: str = "normal"
    activity_kind: str = "trade"
    procedure_manual: str = ""
    going_concern: bool = True
    is_active: bool
    acronym: str = ""
    address: str = ""
    city: str = ""
    postal_code: str = ""
    phone: str = ""
    email: str = ""
    tax_id: str = ""
    rccm: str = ""
    social_register: str = ""
    legal_form: str = ""
    legal_form_label: str = ""
    tax_regime: str = ""
    tax_regime_label: str = ""
    naema_code: str = ""
    control_kind: str = ""
    control_label: str = ""
    country_label: str = ""
    establishments_domestic: int = 1
    establishments_foreign: int = 0
    distinct_branch_accounts: bool = False
    auditor_name: str = ""
    auditor_order_no: str = ""
    signatory_name: str = ""
    signatory_title: str = ""
    banks: str = ""
    setup_data: str = ""
    officers: list[OfficerOut] = []
    identity_complete: bool = False
    identity_missing: list[str] = []


class CompanyIn(Schema):
    name: str
    legal_name: str = ""
    country_code: str = "CI"
    currency_code: str = "XOF"
    accounting_regime: str = "normal"
    activity_kind: str = "trade"
    procedure_manual: str = ""
    going_concern: bool = True


class CompanySettingsIn(Schema):
    accounting_regime: str | None = None
    activity_kind: str | None = None
    procedure_manual: str | None = None
    going_concern: bool | None = None
    legal_name: str | None = None
    country_code: str | None = None
    acronym: str | None = None
    address: str | None = None
    city: str | None = None
    postal_code: str | None = None
    phone: str | None = None
    email: str | None = None
    tax_id: str | None = None
    rccm: str | None = None
    social_register: str | None = None
    legal_form: str | None = None
    tax_regime: str | None = None
    naema_code: str | None = None
    control_kind: str | None = None
    establishments_domestic: int | None = None
    establishments_foreign: int | None = None
    distinct_branch_accounts: bool | None = None
    auditor_name: str | None = None
    auditor_order_no: str | None = None
    signatory_name: str | None = None
    signatory_title: str | None = None
    banks: str | None = None


class CompanyAccessIn(Schema):
    user_email: str


class CompanyAccessOut(Schema):
    id: str
    user_email: str
    user_id: str
    company_id: str

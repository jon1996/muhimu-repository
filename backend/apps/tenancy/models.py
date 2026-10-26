import uuid

from django.conf import settings
from django.db import models
from django.utils.text import slugify


class OrganizationType(models.TextChoices):
    SME = "sme", "PME"
    CABINET = "cabinet", "Cabinet"


class Role(models.TextChoices):
    OWNER = "owner", "Propriétaire"
    ADMIN = "admin", "Administrateur"
    ACCOUNTANT = "accountant", "Comptable"
    AUDITOR = "auditor", "Auditeur"
    VIEWER = "viewer", "Lecteur"


class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=80, unique=True)
    type = models.CharField(max_length=20, choices=OrganizationType.choices)
    is_demo = models.BooleanField(
        default=False,
        help_text="Sandbox de démonstration, hors clients réels.",
    )
    setup_data = models.CharField(
        max_length=16,
        blank=True,
        default="",
        help_text="Choix d'initialisation de l'organisation : vide, demo, ou non renseigné.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "organisation"
        verbose_name_plural = "organisations"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:70] or "org"
            slug = base
            i = 2
            while Organization.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)


class Membership(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "appartenance"
        verbose_name_plural = "appartenances"
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"], name="uniq_membership_org_user"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} @ {self.organization} ({self.role})"

    @property
    def is_org_admin(self) -> bool:
        return self.role in (Role.OWNER, Role.ADMIN)


class AccountingRegime(models.TextChoices):
    NORMAL = "normal", "Système normal"
    SMT = "smt", "Système minimal de trésorerie"


class ActivityKind(models.TextChoices):
    TRADE = "trade", "Négoce"
    CRAFT = "craft", "Artisanat"
    SERVICES = "services", "Services"


class LegalForm(models.TextChoices):
    SA = "sa", "SA"
    SAS = "sas", "SAS"
    SARL = "sarl", "SARL"
    SUARL = "suarl", "SUARL"
    SNC = "snc", "SNC"
    SCS = "scs", "SCS"
    GIE = "gie", "GIE"
    ETS = "ets", "Entreprise individuelle"
    COOP = "coop", "Coopérative"
    OTHER = "other", "Autre"


class TaxRegime(models.TextChoices):
    REEL_NORMAL = "reel_normal", "Réel normal"
    REEL_SIMPLIFIE = "reel_simplifie", "Réel simplifié"
    SYNTHETIQUE = "synthetique", "Synthétique / unique"
    EXEMPTION = "exemption", "Exonéré"
    OTHER = "other", "Autre"


class ControlKind(models.TextChoices):
    PRIVATE_NATIONAL = "private_national", "Privé national"
    PUBLIC = "public", "Public"
    PRIVATE_FOREIGN = "private_foreign", "Privé étranger"


class OfficerRole(models.TextChoices):
    MANAGER = "manager", "Gérant"
    CHAIRMAN = "chairman", "Président"
    DIRECTOR = "director", "Directeur général"
    BOARD = "board", "Administrateur"
    OTHER = "other", "Autre"


class Company(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="companies"
    )
    name = models.CharField(max_length=255)
    legal_name = models.CharField(max_length=255, blank=True)
    country_code = models.CharField(max_length=2, default="CI")
    currency_code = models.CharField(max_length=3, default="XOF")
    accounting_regime = models.CharField(
        max_length=16, choices=AccountingRegime.choices, default=AccountingRegime.NORMAL
    )
    activity_kind = models.CharField(
        max_length=16, choices=ActivityKind.choices, default=ActivityKind.TRADE
    )
    procedure_manual = models.TextField(blank=True)
    going_concern = models.BooleanField(default=True)
    acronym = models.CharField(max_length=32, blank=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=80, blank=True)
    postal_code = models.CharField(max_length=16, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    tax_id = models.CharField("NIF", max_length=32, blank=True)
    rccm = models.CharField("RCCM", max_length=40, blank=True)
    social_register = models.CharField(max_length=40, blank=True)
    legal_form = models.CharField(max_length=16, choices=LegalForm.choices, blank=True)
    tax_regime = models.CharField(max_length=20, choices=TaxRegime.choices, blank=True)
    naema_code = models.CharField(max_length=16, blank=True)
    control_kind = models.CharField(max_length=20, choices=ControlKind.choices, blank=True)
    establishments_domestic = models.PositiveSmallIntegerField(default=1)
    establishments_foreign = models.PositiveSmallIntegerField(default=0)
    distinct_branch_accounts = models.BooleanField(default=False)
    auditor_name = models.CharField(max_length=255, blank=True)
    auditor_order_no = models.CharField(max_length=40, blank=True)
    signatory_name = models.CharField(max_length=255, blank=True)
    signatory_title = models.CharField(max_length=80, blank=True)
    banks = models.CharField(max_length=255, blank=True)
    setup_data = models.CharField(
        max_length=16,
        blank=True,
        default="",
        help_text="Choix d'initialisation : vide, demo, ou non renseigné.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "société"
        verbose_name_plural = "sociétés"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"], name="uniq_company_org_name"
            )
        ]

    def __str__(self) -> str:
        return self.name


class CompanyAccess(models.Model):
    """Assignment cabinet → société. Les owner/admin n'en ont pas besoin."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="company_accesses"
    )
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="accesses")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="company_accesses"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "accès société"
        verbose_name_plural = "accès sociétés"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "user"], name="uniq_company_access_user"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} → {self.company}"

    def save(self, *args, **kwargs):
        if self.company_id and not self.organization_id:
            self.organization_id = self.company.organization_id
        super().save(*args, **kwargs)


class CompanyOfficer(models.Model):
    """Dirigeants et administrateurs — fiche R3."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="officers"
    )
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="officers")
    full_name = models.CharField(max_length=255)
    role = models.CharField(max_length=16, choices=OfficerRole.choices, default=OfficerRole.MANAGER)
    nationality = models.CharField(max_length=64, blank=True)
    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "full_name"]

    def __str__(self) -> str:
        return f"{self.full_name} ({self.get_role_display()})"

    def save(self, *args, **kwargs):
        if self.company_id and not self.organization_id:
            self.organization_id = self.company.organization_id
        super().save(*args, **kwargs)

import uuid
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.ledger.immutability import (
    ENTRY_LINE_ANNOTATION_FIELDS,
    EntryLineManager,
    EntryManager,
    IMMUTABLE_LINE_MSG,
    IMMUTABLE_POSTED_MSG,
)


class ExerciseStatus(models.TextChoices):
    OPEN = "open", "Ouvert"
    CLOSING = "closing", "En clôture"
    CLOSED = "closed", "Clôturé"


class PeriodStatus(models.TextChoices):
    OPEN = "open", "Ouverte"
    VALIDATED = "validated", "Validée"
    IT_CLOSED = "it_closed", "Clôture informatique"


class JournalType(models.TextChoices):
    OD = "od", "Opérations diverses"
    PURCHASE = "purchase", "Achats"
    SALE = "sale", "Ventes"
    BANK = "bank", "Banque"
    CASH = "cash", "Caisse"


class EntryStatus(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    POSTED = "posted", "Validée"


class AccountLevel(models.TextChoices):
    CLASS = "class", "Classe"
    SUBCLASS = "subclass", "Compte à 2 chiffres"
    PRINCIPAL = "principal", "Compte principal"
    SECONDARY = "secondary", "Divisionnaire"
    AUXILIARY = "auxiliary", "Subdivision d'entité"


class AccountFamily(models.TextChoices):
    RESOURCE = "resource", "Ressources durables"
    FIXED_ASSET = "fixed_asset", "Actif immobilisé"
    STOCK = "stock", "Stocks"
    THIRD_PARTY = "third_party", "Tiers"
    TREASURY = "treasury", "Trésorerie"
    EXPENSE = "expense", "Charges AO"
    INCOME = "income", "Produits AO"
    OTHER = "other", "Autres charges / produits"
    OFF_BALANCE = "off_balance", "Engagements / CAGE"


class AccountSense(models.TextChoices):
    DEBIT = "debit", "Débiteur"
    CREDIT = "credit", "Créditeur"
    EITHER = "either", "Mixte"


class Exercise(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "tenancy.Organization", on_delete=models.CASCADE, related_name="exercises"
    )
    company = models.ForeignKey(
        "tenancy.Company", on_delete=models.CASCADE, related_name="exercises"
    )
    year = models.PositiveSmallIntegerField()
    starts_on = models.DateField()
    ends_on = models.DateField()
    status = models.CharField(max_length=16, choices=ExerciseStatus.choices, default=ExerciseStatus.OPEN)
    closed_on = models.DateField(null=True, blank=True)
    approved_on = models.DateField(null=True, blank=True)
    notes_annexes = models.TextField(blank=True)
    net_result = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal("0"))
    revenue = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal("0"))
    legal_reserve_amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal("0"))
    free_reserve_amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal("0"))
    retained_amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal("0"))
    dividends_amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal("0"))
    result_entry = models.ForeignKey(
        "Entry", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    allocation_entry = models.ForeignKey(
        "Entry", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    payment_entry = models.ForeignKey(
        "Entry", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    opening_entry = models.ForeignKey(
        "Entry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="À-nouveaux de reprise (journal AN).",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-year"]
        constraints = [
            models.UniqueConstraint(fields=["company", "year"], name="uniq_exercise_company_year"),
        ]

    def __str__(self) -> str:
        return f"{self.company} {self.year}"


class AccountingPeriod(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "tenancy.Organization", on_delete=models.CASCADE, related_name="periods"
    )
    company = models.ForeignKey(
        "tenancy.Company", on_delete=models.CASCADE, related_name="periods"
    )
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE, related_name="periods")
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()
    starts_on = models.DateField()
    ends_on = models.DateField()
    status = models.CharField(max_length=16, choices=PeriodStatus.choices, default=PeriodStatus.OPEN)
    validated_at = models.DateTimeField(null=True, blank=True)
    it_closed_at = models.DateTimeField(null=True, blank=True)
    seal = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["year", "month"]
        constraints = [
            models.UniqueConstraint(
                fields=["exercise", "year", "month"], name="uniq_period_exercise_month"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.year}-{self.month:02d}"


class Journal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "tenancy.Organization", on_delete=models.CASCADE, related_name="journals"
    )
    company = models.ForeignKey(
        "tenancy.Company", on_delete=models.CASCADE, related_name="journals"
    )
    code = models.CharField(max_length=8)
    name = models.CharField(max_length=80)
    type = models.CharField(max_length=16, choices=JournalType.choices)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="uniq_journal_company_code"),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class JournalSequence(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.CASCADE)
    company = models.ForeignKey("tenancy.Company", on_delete=models.CASCADE)
    journal = models.ForeignKey(Journal, on_delete=models.CASCADE, related_name="sequences")
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE, related_name="sequences")
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["journal", "exercise"], name="uniq_journal_seq_exercise"
            ),
        ]


class Account(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "tenancy.Organization", on_delete=models.CASCADE, related_name="accounts"
    )
    company = models.ForeignKey(
        "tenancy.Company", on_delete=models.CASCADE, related_name="accounts"
    )
    code = models.CharField(max_length=24)
    label = models.CharField(max_length=255)
    account_class = models.CharField(max_length=1)
    level = models.CharField(max_length=16, choices=AccountLevel.choices, default=AccountLevel.PRINCIPAL)
    family = models.CharField(max_length=20, choices=AccountFamily.choices, default=AccountFamily.OTHER)
    sense = models.CharField(max_length=8, choices=AccountSense.choices, default=AccountSense.EITHER)
    parent = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children"
    )
    is_postable = models.BooleanField(default=True)
    is_collective = models.BooleanField(default=False)
    is_syscohada = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="uniq_account_company_code"),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.label}"

    def apply_taxonomy(self) -> None:
        from apps.ledger.taxonomy import classify

        info = classify(self.code)
        self.code = info["code"]
        self.account_class = info["account_class"] or self.account_class
        self.level = info["level"]
        self.family = info["family"]
        self.sense = info["sense"]
        self.is_collective = info["is_collective"]
        if info["level"] == "class":
            self.is_postable = False

    def save(self, *args, **kwargs):
        self.apply_taxonomy()
        super().save(*args, **kwargs)


class Entry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "tenancy.Organization", on_delete=models.CASCADE, related_name="entries"
    )
    company = models.ForeignKey(
        "tenancy.Company", on_delete=models.CASCADE, related_name="entries"
    )
    exercise = models.ForeignKey(Exercise, on_delete=models.PROTECT, related_name="entries")
    period = models.ForeignKey(AccountingPeriod, on_delete=models.PROTECT, related_name="entries")
    journal = models.ForeignKey(Journal, on_delete=models.PROTECT, related_name="entries")
    number = models.PositiveIntegerField(null=True, blank=True)
    number_display = models.CharField(max_length=32, blank=True)
    accounting_date = models.DateField()
    value_date = models.DateField()
    description = models.CharField(max_length=255)
    document_ref = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=12, choices=EntryStatus.choices, default=EntryStatus.DRAFT)
    source = models.CharField(max_length=32, default="manual")
    idempotency_key = models.CharField(max_length=64, blank=True)
    reversed_entry = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="reversals"
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="posted_entries",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = EntryManager()

    class Meta:
        ordering = ["-accounting_date", "-number", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["journal", "exercise", "number"],
                name="uniq_entry_journal_exercise_number",
            ),
            models.UniqueConstraint(
                fields=["company", "idempotency_key"],
                condition=models.Q(idempotency_key__gt=""),
                name="uniq_entry_company_idempotency",
            ),
        ]

    def __str__(self) -> str:
        return self.number_display or f"brouillon {self.id}"

    def save(self, *args, **kwargs):
        allow_posted_write = kwargs.pop("allow_posted_write", False)
        if self.pk and not allow_posted_write:
            previous = Entry.objects.filter(pk=self.pk).only("status").first()
            if previous and previous.status == EntryStatus.POSTED:
                raise ValidationError(IMMUTABLE_POSTED_MSG)
        super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        if self.status == EntryStatus.POSTED:
            raise ValidationError(IMMUTABLE_POSTED_MSG)
        return super().delete(using=using, keep_parents=keep_parents)


class PartyKind(models.TextChoices):
    CUSTOMER = "customer", "Client"
    SUPPLIER = "supplier", "Fournisseur"
    BOTH = "both", "Client et fournisseur"


class ThirdParty(models.Model):
    """Fiche tiers — auxiliaire classe 4 (lettrage, notes 7 et 17)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.CASCADE)
    company = models.ForeignKey("tenancy.Company", on_delete=models.CASCADE, related_name="parties")
    kind = models.CharField(max_length=16, choices=PartyKind.choices, default=PartyKind.CUSTOMER)
    name = models.CharField(max_length=255)
    reference = models.CharField(max_length=32)
    tax_id = models.CharField("NIF", max_length=32, blank=True)
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="parties")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["company", "reference"], name="uniq_party_company_ref"),
        ]

    def __str__(self) -> str:
        return f"{self.reference} {self.name}"


class EntryLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.CASCADE)
    company = models.ForeignKey("tenancy.Company", on_delete=models.CASCADE)
    entry = models.ForeignKey(Entry, on_delete=models.CASCADE, related_name="lines")
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="lines")
    third_party = models.ForeignKey(
        "ThirdParty", on_delete=models.SET_NULL, null=True, blank=True, related_name="lines"
    )
    lettering = models.CharField(max_length=16, blank=True)
    bank_pointage = models.CharField(max_length=16, blank=True)
    due_on = models.DateField(null=True, blank=True)
    cage_section = models.ForeignKey(
        "CageSection",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lines",
    )
    label = models.CharField(max_length=255, blank=True)
    debit = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal("0"))
    credit = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal("0"))
    currency_code = models.CharField(max_length=3, blank=True)
    foreign_amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal("0"))
    fx_rate = models.DecimalField(max_digits=19, decimal_places=8, default=Decimal("1"))
    position = models.PositiveSmallIntegerField(default=0)

    objects = EntryLineManager()

    class Meta:
        ordering = ["position", "id"]

    def save(self, *args, **kwargs):
        allow_posted_write = kwargs.pop("allow_posted_write", False)
        if self.entry_id and not allow_posted_write:
            if Entry.objects.filter(pk=self.entry_id, status=EntryStatus.POSTED).exists():
                if not self.pk:
                    raise ValidationError(IMMUTABLE_LINE_MSG)
                previous = (
                    EntryLine.objects.filter(pk=self.pk)
                    .values(
                        "organization_id",
                        "company_id",
                        "entry_id",
                        "account_id",
                        "third_party_id",
                        "lettering",
                        "bank_pointage",
                        "due_on",
                        "cage_section_id",
                        "label",
                        "debit",
                        "credit",
                        "currency_code",
                        "foreign_amount",
                        "fx_rate",
                        "position",
                    )
                    .first()
                )
                if previous is None:
                    raise ValidationError(IMMUTABLE_LINE_MSG)
                changed = set()
                current = {
                    "organization_id": self.organization_id,
                    "company_id": self.company_id,
                    "entry_id": self.entry_id,
                    "account_id": self.account_id,
                    "third_party_id": self.third_party_id,
                    "lettering": self.lettering or "",
                    "bank_pointage": self.bank_pointage or "",
                    "due_on": self.due_on,
                    "cage_section_id": self.cage_section_id,
                    "label": self.label or "",
                    "debit": self.debit,
                    "credit": self.credit,
                    "currency_code": self.currency_code or "",
                    "foreign_amount": self.foreign_amount,
                    "fx_rate": self.fx_rate,
                    "position": self.position,
                }
                for key, old in previous.items():
                    if current.get(key) != old:
                        changed.add(key)
                if changed and not changed.issubset(ENTRY_LINE_ANNOTATION_FIELDS):
                    raise ValidationError(IMMUTABLE_LINE_MSG)
        super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        if self.entry_id and Entry.objects.filter(
            pk=self.entry_id, status=EntryStatus.POSTED
        ).exists():
            raise ValidationError(IMMUTABLE_LINE_MSG)
        return super().delete(using=using, keep_parents=keep_parents)


class BalanceSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.CASCADE)
    company = models.ForeignKey("tenancy.Company", on_delete=models.CASCADE)
    period = models.ForeignKey(AccountingPeriod, on_delete=models.CASCADE, related_name="snapshots")
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="snapshots")
    open_debit = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal("0"))
    open_credit = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal("0"))
    mov_debit = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal("0"))
    mov_credit = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal("0"))

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["period", "account"], name="uniq_snapshot_period_account"
            ),
        ]


def _document_upload_to(instance, filename: str) -> str:
    suffix = Path(filename).suffix[:12]
    return f"documents/{instance.company_id}/{uuid.uuid4().hex}{suffix}"


class SourceDocument(models.Model):
    """Pièce justificative (art. 17-3, 22-7, 24) — conservation 10 ans."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.CASCADE)
    company = models.ForeignKey("tenancy.Company", on_delete=models.CASCADE, related_name="documents")
    entry = models.ForeignKey(
        Entry, on_delete=models.SET_NULL, null=True, blank=True, related_name="documents"
    )
    original_name = models.CharField(max_length=255)
    file = models.FileField(upload_to=_document_upload_to)
    content_type = models.CharField(max_length=120, blank=True)
    size = models.PositiveIntegerField(default=0)
    sha256 = models.CharField(max_length=64)
    issued_on = models.DateField()
    keep_until = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class InventoryStatus(models.TextChoices):
    DRAFT = "draft", "En cours"
    CLOSED = "closed", "Arrêté"


class StockMethod(models.TextChoices):
    CUMP = "cump", "CUMP"
    PEPS = "peps", "PEPS"


class InventoryCampaign(models.Model):
    """Inventaire physique annuel (art. 16, 17-6). Les lignes classe 3 passent en variation (VIII.14)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.CASCADE)
    company = models.ForeignKey("tenancy.Company", on_delete=models.CASCADE, related_name="inventories")
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE, related_name="inventories")
    inventoried_on = models.DateField()
    status = models.CharField(max_length=12, choices=InventoryStatus.choices, default=InventoryStatus.DRAFT)
    method = models.CharField(max_length=8, choices=StockMethod.choices, default=StockMethod.CUMP)
    notes = models.TextField(blank=True)
    variation_entry = models.ForeignKey(
        "Entry", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-inventoried_on"]


class InventoryLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.CASCADE)
    company = models.ForeignKey("tenancy.Company", on_delete=models.CASCADE)
    campaign = models.ForeignKey(InventoryCampaign, on_delete=models.CASCADE, related_name="lines")
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=19, decimal_places=3, default=Decimal("0"))
    unit = models.CharField(max_length=24, blank=True)
    unit_value = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal("0"))
    amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal("0"))

    class Meta:
        ordering = ["description", "id"]


class AssetKind(models.TextChoices):
    STANDALONE = "standalone", "Bien unique"
    STRUCTURE = "structure", "Structure"
    COMPONENT = "component", "Composant"


class AssetStatus(models.TextChoices):
    IN_SERVICE = "in_service", "En service"
    DISPOSED = "disposed", "Sorti"


class AssetMethod(models.TextChoices):
    LINEAR = "linear", "Linéaire"


class FixedAsset(models.Model):
    """Journal des immobilisations (Titre I.4, VIII.1–4) — une ligne = un plan d’amortissement."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.CASCADE)
    company = models.ForeignKey("tenancy.Company", on_delete=models.CASCADE, related_name="fixed_assets")
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="components"
    )
    reference = models.CharField(max_length=32)
    label = models.CharField(max_length=255)
    kind = models.CharField(max_length=16, choices=AssetKind.choices, default=AssetKind.STANDALONE)
    acquired_on = models.DateField()
    in_service_on = models.DateField()
    cost = models.DecimalField(max_digits=19, decimal_places=2)
    residual_value = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal("0"))
    useful_life_months = models.PositiveSmallIntegerField(default=0)
    method = models.CharField(max_length=16, choices=AssetMethod.choices, default=AssetMethod.LINEAR)
    asset_account = models.ForeignKey(
        Account, on_delete=models.PROTECT, related_name="fixed_assets_gross"
    )
    amort_account = models.ForeignKey(
        Account, on_delete=models.PROTECT, null=True, blank=True, related_name="fixed_assets_amort"
    )
    expense_account = models.ForeignKey(
        Account, on_delete=models.PROTECT, null=True, blank=True, related_name="fixed_assets_expense"
    )
    status = models.CharField(max_length=16, choices=AssetStatus.choices, default=AssetStatus.IN_SERVICE)
    disposed_on = models.DateField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["reference"]
        constraints = [
            models.UniqueConstraint(fields=["company", "reference"], name="uniq_fixed_asset_company_ref"),
        ]

    def __str__(self) -> str:
        return f"{self.reference} {self.label}"

    @property
    def depreciable(self) -> bool:
        return self.useful_life_months > 0 and self.method == AssetMethod.LINEAR


class DepreciationCharge(models.Model):
    """Dotation d’une période pour un bien — une seule fois (idempotent)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.CASCADE)
    company = models.ForeignKey("tenancy.Company", on_delete=models.CASCADE)
    asset = models.ForeignKey(FixedAsset, on_delete=models.CASCADE, related_name="charges")
    period = models.ForeignKey(AccountingPeriod, on_delete=models.PROTECT, related_name="depreciation_charges")
    entry = models.ForeignKey(Entry, on_delete=models.PROTECT, related_name="depreciation_charges")
    amount = models.DecimalField(max_digits=19, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["asset", "period"], name="uniq_depreciation_asset_period"),
        ]


class BankStatement(models.Model):
    """Relevé bancaire (rapprochement du 52, note 11)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.CASCADE)
    company = models.ForeignKey("tenancy.Company", on_delete=models.CASCADE, related_name="bank_statements")
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="bank_statements")
    statement_date = models.DateField()
    bank_balance = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal("0"),
        help_text="Solde du relevé en notre faveur (positif = disponible, comme un 52 débiteur).",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-statement_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "account", "statement_date"],
                name="uniq_bank_statement_account_date",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.account.code} {self.statement_date}"


class BankStatementLine(models.Model):
    """Ligne du relevé : débit banque = sortie, crédit banque = entrée."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.CASCADE)
    company = models.ForeignKey("tenancy.Company", on_delete=models.CASCADE, related_name="bank_statement_lines")
    statement = models.ForeignKey(BankStatement, on_delete=models.CASCADE, related_name="lines")
    line_date = models.DateField()
    label = models.CharField(max_length=255)
    bank_debit = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal("0"))
    bank_credit = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal("0"))
    pointage = models.CharField(max_length=16, blank=True)
    external_id = models.CharField(max_length=64, blank=True)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["line_date", "position", "id"]

    def __str__(self) -> str:
        return self.label


class CashCount(models.Model):
    """Inventaire physique de caisse — contrôle du 57."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.CASCADE)
    company = models.ForeignKey("tenancy.Company", on_delete=models.CASCADE, related_name="cash_counts")
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="cash_counts")
    counted_on = models.DateField()
    physical_amount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal("0"),
        help_text="Espèces réellement en caisse.",
    )
    book_amount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal("0"),
        help_text="Solde comptable du 57 au moment du contrôle.",
    )
    notes = models.CharField(max_length=255, blank=True)
    entry = models.ForeignKey(
        "Entry", on_delete=models.SET_NULL, null=True, blank=True, related_name="cash_counts"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-counted_on", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "account", "counted_on"],
                name="uniq_cash_count_account_date",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.account.code} {self.counted_on}"


class CommitmentKind(models.TextChoices):
    MORTGAGE = "mortgage", "Hypothèque"
    PLEDGE = "pledge", "Nantissement"
    GAGE = "gage", "Gage"
    GUARANTEE = "guarantee", "Caution / aval"
    DISCOUNT = "discount", "Effets escomptés non échus"
    ASSIGNED = "assigned", "Créances cédées"
    LEASE = "lease", "Location-acquisition / loyers"
    OTHER = "other", "Autre engagement"


class CommitmentSide(models.TextChoices):
    GIVEN = "given", "Donné par l’entité"
    RECEIVED = "received", "Reçu par l’entité"


class Commitment(models.Model):
    """Hors bilan — note 1 (sûretés et engagements). Classe 9 facultative (90/91)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.CASCADE)
    company = models.ForeignKey("tenancy.Company", on_delete=models.CASCADE, related_name="commitments")
    kind = models.CharField(max_length=16, choices=CommitmentKind.choices)
    side = models.CharField(max_length=16, choices=CommitmentSide.choices, default=CommitmentSide.GIVEN)
    label = models.CharField(max_length=255)
    counterparty = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=19, decimal_places=2)
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    entry = models.ForeignKey(
        "Entry", on_delete=models.SET_NULL, null=True, blank=True, related_name="commitments"
    )
    origin_entry = models.ForeignKey(
        "Entry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="origin_commitments",
        help_text="Écriture 1–8 qui a fait naître l’engagement (escompte, etc.).",
    )

    class Meta:
        ordering = ["side", "kind", "label"]

    def __str__(self) -> str:
        return self.label


class CageSection(models.Model):
    """Section analytique CAGE — compte 95-{CODE}, facultatif."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.CASCADE)
    company = models.ForeignKey(
        "tenancy.Company", on_delete=models.CASCADE, related_name="cage_sections"
    )
    code = models.CharField(max_length=12)
    label = models.CharField(max_length=255)
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="cage_sections")
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_default", "code"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="uniq_cage_section_company_code"),
            models.UniqueConstraint(fields=["account"], name="uniq_cage_section_account"),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.label}"


class CageReflection(models.Model):
    """Lien écriture 1–8 → écriture de réfléchissement classe 9 (idempotent)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.CASCADE)
    company = models.ForeignKey(
        "tenancy.Company", on_delete=models.CASCADE, related_name="cage_reflections"
    )
    source_entry = models.OneToOneField(
        Entry, on_delete=models.CASCADE, related_name="cage_reflection"
    )
    cage_entry = models.ForeignKey(
        Entry, on_delete=models.PROTECT, related_name="cage_reflected_from"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"CAGE {self.source_entry_id}"


class EsgReport(models.Model):
    """Note 35 — informations sociales, environnementales et sociétales."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.CASCADE)
    company = models.ForeignKey("tenancy.Company", on_delete=models.CASCADE, related_name="esg_reports")
    year = models.PositiveSmallIntegerField()
    headcount = models.PositiveIntegerField(default=0)
    hires = models.PositiveIntegerField(default=0)
    dismissals = models.PositiveIntegerField(default=0)
    disabled_count = models.PositiveIntegerField(default=0)
    social_dialogue = models.TextField(blank=True)
    health = models.TextField(blank=True)
    training = models.TextField(blank=True)
    equality = models.TextField(blank=True)
    env_policy = models.TextField(blank=True)
    waste = models.TextField(blank=True)
    water = models.TextField(blank=True)
    energy = models.TextField(blank=True)
    ghg = models.TextField(blank=True)
    biodiversity = models.TextField(blank=True)
    territory = models.TextField(blank=True)
    neighbors = models.TextField(blank=True)
    patronage = models.TextField(blank=True)
    purchases = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year"]
        constraints = [
            models.UniqueConstraint(fields=["company", "year"], name="uniq_esg_company_year"),
        ]

    def __str__(self) -> str:
        return f"RSE {self.year}"


class FxRate(models.Model):
    """Cours de change : 1 unité de devise cotée = rate unités de devise de tenue."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.CASCADE)
    company = models.ForeignKey("tenancy.Company", on_delete=models.CASCADE, related_name="fx_rates")
    currency_code = models.CharField(max_length=3)
    rate_date = models.DateField()
    rate = models.DecimalField(max_digits=19, decimal_places=8)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-rate_date", "currency_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "currency_code", "rate_date"],
                name="uniq_fx_rate_company_currency_date",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.currency_code} {self.rate_date} {self.rate}"


class ConsolidationKind(models.TextChoices):
    CONSOLIDATED = "consolidated", "Consolidé"
    COMBINED = "combined", "Combiné"


class ConsolidationMethod(models.TextChoices):
    FULL = "full", "Intégration globale"
    PROPORTIONAL = "proportional", "Intégration proportionnelle"
    EQUITY = "equity", "Mise en équivalence"
    COMBINED = "combined", "Combinaison"


class EliminationKind(models.TextChoices):
    SALES = "sales", "Chiffre d’affaires / achats"
    REC_PAY = "rec_pay", "Créances / dettes"
    INVESTMENT = "investment", "Titres / capitaux"
    DIVIDEND = "dividend", "Dividendes"
    OTHER = "other", "Autre"


class ConsolidationGroup(models.Model):
    """Périmètre consolidé ou combiné (AUDCIF art. 5)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "tenancy.Organization", on_delete=models.CASCADE, related_name="consolidation_groups"
    )
    name = models.CharField(max_length=255)
    kind = models.CharField(
        max_length=16, choices=ConsolidationKind.choices, default=ConsolidationKind.CONSOLIDATED
    )
    year = models.PositiveSmallIntegerField()
    currency_code = models.CharField(max_length=3, default="XOF")
    parent = models.ForeignKey(
        "tenancy.Company",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="consolidation_parents",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-year", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name", "year"], name="uniq_consolidation_org_name_year"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} {self.year}"


class ConsolidationMember(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.CASCADE)
    group = models.ForeignKey(
        ConsolidationGroup, on_delete=models.CASCADE, related_name="members"
    )
    company = models.ForeignKey(
        "tenancy.Company", on_delete=models.CASCADE, related_name="consolidation_memberships"
    )
    method = models.CharField(
        max_length=16, choices=ConsolidationMethod.choices, default=ConsolidationMethod.FULL
    )
    ownership_pct = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("100"))
    is_parent = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-is_parent", "company__name"]
        constraints = [
            models.UniqueConstraint(fields=["group", "company"], name="uniq_consolidation_member"),
        ]

    def __str__(self) -> str:
        return f"{self.company} @ {self.group}"


class ConsolidationElimination(models.Model):
    """Retraitement manuel sur un poste SN (montant soustrait de la colonne N)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.CASCADE)
    group = models.ForeignKey(
        ConsolidationGroup, on_delete=models.CASCADE, related_name="eliminations"
    )
    code = models.CharField(max_length=8)
    label = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=19, decimal_places=2, default=Decimal("0"))
    kind = models.CharField(
        max_length=16, choices=EliminationKind.choices, default=EliminationKind.OTHER
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code", "created_at"]

    def __str__(self) -> str:
        return f"{self.code} {self.label}"


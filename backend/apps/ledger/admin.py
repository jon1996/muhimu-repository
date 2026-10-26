from django.contrib import admin

from apps.ledger.models import (
    Account,
    AccountingPeriod,
    BankStatement,
    BankStatementLine,
    Entry,
    EntryLine,
    Exercise,
    FixedAsset,
    FxRate,
    InventoryCampaign,
    Journal,
    SourceDocument,
    ThirdParty,
    CashCount,
    Commitment,
    CageSection,
    CageReflection,
    ConsolidationElimination,
    ConsolidationGroup,
    ConsolidationMember,
    EsgReport,
)


class EntryLineInline(admin.TabularInline):
    model = EntryLine
    extra = 0
    readonly_fields = ("account", "label", "debit", "credit", "currency_code", "foreign_amount", "fx_rate")

    def has_add_permission(self, request, obj=None):
        from apps.ledger.models import EntryStatus

        if obj is not None and obj.status == EntryStatus.POSTED:
            return False
        return super().has_add_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        from apps.ledger.models import EntryStatus

        if obj is not None and obj.status == EntryStatus.POSTED:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ("company", "year", "status", "net_result", "closed_on", "approved_on")
    list_filter = ("status", "year")


@admin.register(AccountingPeriod)
class PeriodAdmin(admin.ModelAdmin):
    list_display = ("company", "year", "month", "status")
    list_filter = ("status", "year")


@admin.register(Journal)
class JournalAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "company", "type")


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "company", "is_postable")
    search_fields = ("code", "label")
    list_filter = ("account_class", "is_postable")


@admin.register(SourceDocument)
class SourceDocumentAdmin(admin.ModelAdmin):
    list_display = ("original_name", "company", "issued_on", "keep_until")


@admin.register(InventoryCampaign)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ("company", "inventoried_on", "status")


@admin.register(FixedAsset)
class FixedAssetAdmin(admin.ModelAdmin):
    list_display = ("reference", "label", "cost", "useful_life_months", "status", "company")
    list_filter = ("status", "kind")
    search_fields = ("reference", "label")


@admin.register(ThirdParty)
class ThirdPartyAdmin(admin.ModelAdmin):
    list_display = ("reference", "name", "kind", "account", "company")
    list_filter = ("kind",)
    search_fields = ("name", "reference", "tax_id")


class BankStatementLineInline(admin.TabularInline):
    model = BankStatementLine
    extra = 0


@admin.register(BankStatement)
class BankStatementAdmin(admin.ModelAdmin):
    list_display = ("account", "statement_date", "bank_balance", "company")
    list_filter = ("statement_date",)
    inlines = [BankStatementLineInline]


@admin.register(CashCount)
class CashCountAdmin(admin.ModelAdmin):
    list_display = ("account", "counted_on", "physical_amount", "book_amount", "company")
    list_filter = ("counted_on",)


@admin.register(Commitment)
class CommitmentAdmin(admin.ModelAdmin):
    list_display = ("label", "kind", "side", "amount", "is_active", "company")
    list_filter = ("kind", "side", "is_active")
    search_fields = ("label", "counterparty")


@admin.register(CageSection)
class CageSectionAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "account", "is_default", "is_active", "company")
    list_filter = ("is_active", "is_default")
    search_fields = ("code", "label")


@admin.register(CageReflection)
class CageReflectionAdmin(admin.ModelAdmin):
    list_display = ("source_entry", "cage_entry", "company", "created_at")
    list_filter = ("created_at",)


@admin.register(EsgReport)
class EsgReportAdmin(admin.ModelAdmin):
    list_display = ("year", "headcount", "hires", "dismissals", "company")
    list_filter = ("year",)


@admin.register(FxRate)
class FxRateAdmin(admin.ModelAdmin):
    list_display = ("currency_code", "rate_date", "rate", "company")
    list_filter = ("currency_code",)


@admin.register(ConsolidationGroup)
class ConsolidationGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "year", "currency_code", "parent", "organization")
    list_filter = ("kind", "year")
    search_fields = ("name",)


@admin.register(ConsolidationMember)
class ConsolidationMemberAdmin(admin.ModelAdmin):
    list_display = ("company", "group", "method", "ownership_pct", "is_parent", "is_active")
    list_filter = ("method", "is_parent", "is_active")


@admin.register(ConsolidationElimination)
class ConsolidationEliminationAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "amount", "kind", "group")
    list_filter = ("kind",)


@admin.register(Entry)
class EntryAdmin(admin.ModelAdmin):
    list_display = ("number_display", "journal", "accounting_date", "status", "company")
    list_filter = ("status",)
    inlines = [EntryLineInline]

    def has_delete_permission(self, request, obj=None):
        from apps.ledger.models import EntryStatus

        if obj is not None and obj.status == EntryStatus.POSTED:
            return False
        return super().has_delete_permission(request, obj)

    def get_readonly_fields(self, request, obj=None):
        from apps.ledger.models import EntryStatus

        base = list(super().get_readonly_fields(request, obj))
        if obj is not None and obj.status == EntryStatus.POSTED:
            return base + [
                "organization",
                "company",
                "exercise",
                "period",
                "journal",
                "number",
                "number_display",
                "accounting_date",
                "value_date",
                "description",
                "document_ref",
                "status",
                "source",
                "idempotency_key",
                "reversed_entry",
                "posted_at",
                "posted_by",
            ]
        return base

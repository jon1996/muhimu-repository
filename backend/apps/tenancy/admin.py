from django.contrib import admin

from apps.tenancy.models import Company, CompanyAccess, CompanyOfficer, Membership, Organization


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0


class CompanyInline(admin.TabularInline):
    model = Company
    extra = 0


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "type", "is_demo", "created_at")
    search_fields = ("name", "slug")
    list_filter = ("type", "is_demo")
    inlines = [MembershipInline, CompanyInline]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "role", "is_active")
    list_filter = ("role", "is_active")
    search_fields = ("user__email", "organization__name")


class CompanyOfficerInline(admin.TabularInline):
    model = CompanyOfficer
    extra = 0


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "rccm", "tax_id", "country_code", "is_active")
    list_filter = ("country_code", "currency_code", "legal_form", "is_active")
    search_fields = ("name", "legal_name", "rccm", "tax_id")
    inlines = [CompanyOfficerInline]


@admin.register(CompanyAccess)
class CompanyAccessAdmin(admin.ModelAdmin):
    list_display = ("user", "company", "organization")
    search_fields = ("user__email", "company__name")

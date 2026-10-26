from django.contrib import admin

from apps.platform.models import DemoGrant


@admin.register(DemoGrant)
class DemoGrantAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "access_pme",
        "access_cabinet",
        "is_active",
        "granted_by",
        "last_emailed_at",
        "created_at",
    )
    list_filter = ("is_active", "access_pme", "access_cabinet")
    search_fields = ("user__email", "user__full_name", "notes")

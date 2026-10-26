from django.contrib import admin

from apps.identity.models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "full_name", "is_active", "is_staff", "date_joined")
    search_fields = ("email", "full_name")
    list_filter = ("is_active", "is_staff")
    ordering = ("email",)

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "display_name", "email", "role", "district", "is_active")
    list_filter = ("role", "is_active", "is_staff", "district")
    search_fields = ("username", "first_name", "last_name", "email", "phone")
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("SAWIE profile", {
            "fields": ("role", "phone", "designation", "district", "avatar", "last_seen")
        }),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ("SAWIE profile", {"fields": ("role", "phone", "designation", "district")}),
    )

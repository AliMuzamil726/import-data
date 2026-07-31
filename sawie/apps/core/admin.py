from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "level", "category", "recipient", "is_read", "created_at")
    list_filter = ("level", "category", "is_read")
    search_fields = ("title", "body")
    date_hierarchy = "created_at"

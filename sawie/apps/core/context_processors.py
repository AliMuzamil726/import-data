"""Template context shared by every page."""
from .models import Notification

NAV_ITEMS = [
    {"module": "dashboard", "label": "Dashboard", "url": "core:dashboard", "icon": "layout-grid"},
    {"module": "farmers", "label": "Farmers", "url": "farmers:list", "icon": "users"},
    {"module": "fields", "label": "Fields", "url": "fields:list", "icon": "square-dashed"},
    {"module": "map", "label": "Map", "url": "fields:map", "icon": "map"},
    {"module": "crops", "label": "Crops", "url": "crops:list", "icon": "sprout"},
    {"module": "weather", "label": "Weather", "url": "weather:index", "icon": "cloud-sun"},
    {"module": "ndvi", "label": "NDVI", "url": "ndvi:list", "icon": "satellite"},
    {"module": "analytics", "label": "Analytics", "url": "analytics:index", "icon": "bar-chart-3"},
    {"module": "reports", "label": "Reports", "url": "reports:index", "icon": "file-text"},
    {"module": "projects", "label": "Projects", "url": "projects:list", "icon": "folder"},
    {"module": "users", "label": "Users", "url": "accounts:user_list", "icon": "shield-check"},
]


def navigation(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"nav_items": [], "unread_notifications": 0}

    items = [item for item in NAV_ITEMS if user.can_access(item["module"])]
    unread = Notification.objects.for_user(user).filter(is_read=False).count()
    return {"nav_items": items, "unread_notifications": unread}

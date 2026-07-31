"""Row-level scoping so each role only sees the records it should."""
from django.db.models import QuerySet


def scope_farmers(queryset: QuerySet, user) -> QuerySet:
    """Farmer-role users only ever see their own record."""
    if user.is_superuser or user.role != "farmer":
        return queryset
    profile = getattr(user, "farmer_profile", None)
    return queryset.filter(pk=profile.pk) if profile else queryset.none()


def scope_fields(queryset: QuerySet, user) -> QuerySet:
    if user.is_superuser:
        return queryset
    if user.role == "farmer":
        profile = getattr(user, "farmer_profile", None)
        return queryset.filter(farmer=profile) if profile else queryset.none()
    return queryset


def scope_crops(queryset: QuerySet, user) -> QuerySet:
    if user.is_superuser:
        return queryset
    if user.role == "farmer":
        profile = getattr(user, "farmer_profile", None)
        return queryset.filter(field__farmer=profile) if profile else queryset.none()
    return queryset

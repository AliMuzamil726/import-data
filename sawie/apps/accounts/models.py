"""User accounts and role-based access."""
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class Role(models.TextChoices):
    SUPER_ADMIN = "super_admin", "Super Admin"
    AGRI_MANAGER = "agri_manager", "Agriculture Manager"
    FIELD_OFFICER = "field_officer", "Field Officer"
    FARMER = "farmer", "Farmer"


#: Which modules each role may open. Enforced by apps.accounts.permissions.
ROLE_MODULES: dict[str, set[str]] = {
    Role.SUPER_ADMIN: {
        "dashboard", "farmers", "fields", "crops", "map", "weather",
        "ndvi", "analytics", "reports", "projects", "users", "notifications",
    },
    Role.AGRI_MANAGER: {
        "dashboard", "farmers", "fields", "crops", "map", "weather",
        "ndvi", "analytics", "reports", "projects", "notifications",
    },
    Role.FIELD_OFFICER: {
        "dashboard", "farmers", "fields", "crops", "map", "weather",
        "ndvi", "projects", "notifications",
    },
    Role.FARMER: {"dashboard", "fields", "crops", "map", "weather", "notifications"},
}


class User(AbstractUser):
    """Platform user. Role drives module visibility and object scoping."""

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.FIELD_OFFICER)
    phone = models.CharField(max_length=20, blank=True)
    designation = models.CharField(max_length=120, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    district = models.CharField(max_length=100, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("first_name", "last_name", "username")
        indexes = [models.Index(fields=["role"]), models.Index(fields=["is_active"])]

    def __str__(self) -> str:
        return self.get_full_name() or self.username

    # ---------------------------------------------------------------- helpers
    @property
    def display_name(self) -> str:
        return self.get_full_name() or self.username

    @property
    def initials(self) -> str:
        parts = [p for p in (self.first_name, self.last_name) if p]
        if not parts:
            return self.username[:2].upper()
        return "".join(p[0] for p in parts[:2]).upper()

    @property
    def modules(self) -> set[str]:
        if self.is_superuser:
            return ROLE_MODULES[Role.SUPER_ADMIN]
        return ROLE_MODULES.get(self.role, set())

    def can_access(self, module: str) -> bool:
        return module in self.modules

    @property
    def can_edit_records(self) -> bool:
        """Farmers get a read-only portal; everyone else can write."""
        return self.is_superuser or self.role in {
            Role.SUPER_ADMIN, Role.AGRI_MANAGER, Role.FIELD_OFFICER,
        }

    @property
    def can_delete_records(self) -> bool:
        return self.is_superuser or self.role in {Role.SUPER_ADMIN, Role.AGRI_MANAGER}

    def touch(self) -> None:
        User.objects.filter(pk=self.pk).update(last_seen=timezone.now())

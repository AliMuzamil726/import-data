"""Create the four role accounts needed to sign in for the first time."""
import secrets
import string

from django.core.management.base import BaseCommand

from apps.accounts.models import Role, User


def strong_password(length: int = 14) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


class Command(BaseCommand):
    help = "Create one account per role. Passwords are generated unless you pass --password."

    DEFAULTS = [
        ("admin", Role.SUPER_ADMIN, "Platform", "Administrator", True),
        ("manager", Role.AGRI_MANAGER, "Agriculture", "Manager", False),
        ("officer", Role.FIELD_OFFICER, "Field", "Officer", False),
        ("grower", Role.FARMER, "Farmer", "Portal", False),
    ]

    def add_arguments(self, parser):
        parser.add_argument("--password", help="Use this password for every account created.")
        parser.add_argument("--email-domain", default="sawie.local")

    def handle(self, *args, **options):
        created = []
        for username, role, first, last, is_super in self.DEFAULTS:
            if User.objects.filter(username=username).exists():
                self.stdout.write(f"  {username:<8} already exists, skipping")
                continue
            password = options["password"] or strong_password()
            user = User.objects.create_user(
                username=username,
                email=f"{username}@{options['email_domain']}",
                password=password,
                first_name=first,
                last_name=last,
                role=role,
                is_staff=is_super,
                is_superuser=is_super,
            )
            created.append((user.username, user.get_role_display(), password))

        if not created:
            self.stdout.write(self.style.WARNING("No new accounts were created."))
            return

        self.stdout.write(self.style.SUCCESS("\nAccounts created — store these credentials now:\n"))
        for username, role, password in created:
            self.stdout.write(f"  {username:<8} {role:<22} {password}")
        self.stdout.write(
            self.style.WARNING("\nChange these passwords after your first sign-in.\n")
        )

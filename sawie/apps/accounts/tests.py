"""Authentication and role-permission tests."""
from django.test import TestCase
from django.urls import reverse

from .models import Role, User


class RoleAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.users = {
            role: User.objects.create_user(
                username=role, password="test-pass-1234", role=role
            )
            for role in [Role.SUPER_ADMIN, Role.AGRI_MANAGER, Role.FIELD_OFFICER, Role.FARMER]
        }

    def test_login_page_renders(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sign in")

    def test_dashboard_requires_authentication(self):
        response = self.client.get(reverse("core:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_bad_credentials_are_rejected(self):
        self.assertFalse(self.client.login(username="super_admin", password="wrong"))

    def test_only_super_admin_reaches_user_admin(self):
        expected = {
            Role.SUPER_ADMIN: 200, Role.AGRI_MANAGER: 403,
            Role.FIELD_OFFICER: 403, Role.FARMER: 403,
        }
        for role, status in expected.items():
            with self.subTest(role=role):
                self.client.force_login(self.users[role])
                self.assertEqual(
                    self.client.get(reverse("accounts:user_list")).status_code, status
                )

    def test_farmer_role_cannot_open_the_farmer_registry(self):
        self.client.force_login(self.users[Role.FARMER])
        self.assertEqual(self.client.get(reverse("farmers:list")).status_code, 403)

    def test_field_officer_cannot_delete(self):
        self.assertFalse(self.users[Role.FIELD_OFFICER].can_delete_records)
        self.assertTrue(self.users[Role.FIELD_OFFICER].can_edit_records)

    def test_farmer_role_is_read_only(self):
        self.assertFalse(self.users[Role.FARMER].can_edit_records)

    def test_passwords_are_hashed(self):
        user = self.users[Role.AGRI_MANAGER]
        self.assertNotEqual(user.password, "test-pass-1234")
        self.assertTrue(user.check_password("test-pass-1234"))

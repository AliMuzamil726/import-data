"""Farmer CRUD, validation and export tests."""
from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Role, User

from .models import Farmer


class FarmerModelTests(TestCase):
    def test_cnic_is_normalised_to_the_dashed_format(self):
        farmer = Farmer(
            full_name="Test Grower", cnic="3520212345671", phone="03001234567",
            city="Faisalabad", registration_date=date(2026, 1, 1),
        )
        farmer.clean()
        self.assertEqual(farmer.cnic, "35202-1234567-1")

    def test_short_cnic_is_rejected(self):
        farmer = Farmer(
            full_name="Test", cnic="123", phone="03001234567",
            city="Faisalabad", registration_date=date(2026, 1, 1),
        )
        with self.assertRaises(ValidationError):
            farmer.clean()


class FarmerViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(
            username="manager", password="test-pass-1234", role=Role.AGRI_MANAGER
        )
        cls.officer = User.objects.create_user(
            username="officer", password="test-pass-1234", role=Role.FIELD_OFFICER
        )
        cls.farmer = Farmer.objects.create(
            full_name="Existing Grower", cnic="35202-7654321-9", phone="03007654321",
            city="Sahiwal", registration_date=date(2026, 2, 1), total_land_acres=20,
        )

    def setUp(self):
        self.client.force_login(self.manager)

    def test_list_and_detail_render(self):
        self.assertContains(self.client.get(reverse("farmers:list")), "Existing Grower")
        self.assertContains(self.client.get(self.farmer.get_absolute_url()), "Sahiwal")

    def test_create_writes_to_the_database(self):
        response = self.client.post(reverse("farmers:create"), {
            "full_name": "New Grower", "father_name": "Someone", "cnic": "35202-1112223-4",
            "phone": "+92 300 1112223", "city": "Multan", "province": "Punjab",
            "total_land_acres": "15.5", "registration_date": "2026-03-15", "status": "active",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Farmer.objects.filter(cnic="35202-1112223-4").exists())

    def test_duplicate_cnic_is_rejected(self):
        response = self.client.post(reverse("farmers:create"), {
            "full_name": "Duplicate", "cnic": "35202-7654321-9", "phone": "03001111111",
            "city": "Multan", "province": "Punjab", "total_land_acres": "5",
            "registration_date": "2026-03-15", "status": "active",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")

    def test_search_filters_the_queryset(self):
        response = self.client.get(reverse("farmers:list"), {"q": "nothing-matches-this"})
        self.assertNotContains(response, "Existing Grower")

    def test_field_officer_cannot_delete(self):
        self.client.force_login(self.officer)
        response = self.client.post(
            reverse("farmers:delete", args=[self.farmer.pk]), follow=True
        )
        self.assertTrue(Farmer.objects.filter(pk=self.farmer.pk).exists())
        self.assertEqual(response.status_code, 200)

    def test_exports_return_the_right_content_types(self):
        cases = {
            "csv": "text/csv",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "pdf": "application/pdf",
        }
        for fmt, content_type in cases.items():
            with self.subTest(fmt=fmt):
                response = self.client.get(reverse("farmers:export", args=[fmt]))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], content_type)
                self.assertIn("attachment", response["Content-Disposition"])

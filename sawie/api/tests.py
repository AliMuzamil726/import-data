"""REST API authentication and role-scoping tests."""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.farmers.models import Farmer
from apps.fields.models import Field


class ApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="admin", password="test-pass-1234", role=Role.SUPER_ADMIN
        )
        cls.grower_user = User.objects.create_user(
            username="grower", password="test-pass-1234", role=Role.FARMER
        )
        cls.owned = Farmer.objects.create(
            full_name="Own Grower", cnic="35202-1111111-1", phone="03001111111",
            city="Multan", registration_date=date(2026, 1, 1), portal_user=cls.grower_user,
        )
        cls.other = Farmer.objects.create(
            full_name="Other Grower", cnic="35202-2222222-2", phone="03002222222",
            city="Sahiwal", registration_date=date(2026, 1, 1),
        )
        for farmer, code in [(cls.owned, "A-1"), (cls.other, "B-1")]:
            Field.objects.create(
                name="Block", code=code, farmer=farmer, latitude=Decimal("31.4"),
                longitude=Decimal("73.0"), area_acres=Decimal("5.00"),
            )

    def test_api_requires_authentication(self):
        self.assertEqual(self.client.get("/api/v1/farmers/").status_code, 403)

    def test_admin_sees_every_field(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get("/api/v1/fields/").json()["count"], 2)

    def test_farmer_role_only_sees_its_own_fields(self):
        self.client.force_login(self.grower_user)
        payload = self.client.get("/api/v1/fields/").json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["code"], "A-1")

    def test_geojson_action_returns_a_feature_collection(self):
        self.client.force_login(self.admin)
        payload = self.client.get("/api/v1/fields/geojson/").json()
        self.assertEqual(payload["type"], "FeatureCollection")

    def test_create_records_the_author(self):
        self.client.force_login(self.admin)
        response = self.client.post("/api/v1/farmers/", {
            "full_name": "API Grower", "cnic": "35202-3333333-3", "phone": "03003333333",
            "city": "Vehari", "registration_date": "2026-04-01", "status": "active",
            "total_land_acres": "8.00", "province": "Punjab",
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            Farmer.objects.get(cnic="35202-3333333-3").created_by, self.admin
        )

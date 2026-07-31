"""Field geometry, map endpoints and activity logging."""
import json
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.farmers.models import Farmer

from .models import Field

SQUARE = {
    "type": "Polygon",
    "coordinates": [[
        [73.050000, 31.400000], [73.060000, 31.400000],
        [73.060000, 31.410000], [73.050000, 31.410000], [73.050000, 31.400000],
    ]],
}


class FieldTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="officer", password="test-pass-1234", role=Role.FIELD_OFFICER
        )
        cls.farmer = Farmer.objects.create(
            full_name="Grower", cnic="35202-1234567-1", phone="03001234567",
            city="Faisalabad", registration_date=date(2026, 1, 1),
        )
        cls.field = Field.objects.create(
            name="North block", code="FSD-001-A", farmer=cls.farmer,
            latitude=Decimal("31.405000"), longitude=Decimal("73.055000"),
            area_acres=Decimal("24.50"), boundary=SQUARE,
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_invalid_geometry_is_rejected(self):
        field = Field(
            name="Bad", code="BAD-1", farmer=self.farmer, latitude=Decimal("31.4"),
            longitude=Decimal("73.0"), area_acres=Decimal("1"),
            boundary={"type": "LineString", "coordinates": [[1, 2]]},
        )
        with self.assertRaises(ValidationError):
            field.clean()

    def test_geojson_feature_shape(self):
        feature = self.field.as_geojson_feature()
        self.assertEqual(feature["type"], "Feature")
        self.assertEqual(feature["geometry"]["type"], "Polygon")
        self.assertEqual(feature["properties"]["code"], "FSD-001-A")

    def test_map_endpoint_returns_a_feature_collection(self):
        payload = json.loads(self.client.get(reverse("fields:geojson")).content)
        self.assertEqual(payload["type"], "FeatureCollection")
        self.assertEqual(len(payload["features"]), 1)

    def test_boundary_endpoint_saves_geometry_and_area(self):
        response = self.client.post(
            reverse("fields:boundary_save", args=[self.field.pk]),
            data=json.dumps({"boundary": SQUARE, "area_acres": 30.25,
                             "latitude": 31.4055, "longitude": 73.0555}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.field.refresh_from_db()
        self.assertEqual(self.field.area_acres, Decimal("30.25"))

    def test_boundary_endpoint_rejects_non_polygons(self):
        response = self.client.post(
            reverse("fields:boundary_save", args=[self.field.pk]),
            data=json.dumps({"boundary": {"type": "Point", "coordinates": [1, 2]}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_activity_can_be_logged(self):
        response = self.client.post(
            reverse("fields:activity_create", args=[self.field.pk]),
            {"kind": "irrigation", "performed_on": "2026-06-01", "detail": "Canal turn",
             "quantity": "3", "unit": "acre-inch"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.field.activities.count(), 1)

    def test_map_page_renders(self):
        self.assertEqual(self.client.get(reverse("fields:map")).status_code, 200)

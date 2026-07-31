"""Vegetation-index calculation tests."""
from datetime import date
from decimal import Decimal
from io import BytesIO

import numpy as np
from django.core.files.base import ContentFile
from django.test import TestCase
from PIL import Image

from apps.accounts.models import Role, User
from apps.farmers.models import Farmer
from apps.fields.models import Field

from .models import NDVIRecord, NDVIStatus
from .tasks import process_ndvi_record


def band(value: int, size: int = 64) -> ContentFile:
    buffer = BytesIO()
    Image.fromarray(np.full((size, size), value, dtype=np.uint8), mode="L").save(
        buffer, format="PNG"
    )
    return ContentFile(buffer.getvalue())


class NDVIProcessingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        farmer = Farmer.objects.create(
            full_name="Grower", cnic="35202-1234567-1", phone="03001234567",
            city="Faisalabad", registration_date=date(2026, 1, 1),
        )
        cls.field = Field.objects.create(
            name="Block", code="FSD-001-A", farmer=farmer,
            latitude=Decimal("31.405000"), longitude=Decimal("73.055000"),
            area_acres=Decimal("10.00"),
        )
        cls.user = User.objects.create_user(
            username="officer", password="test-pass-1234", role=Role.FIELD_OFFICER
        )

    def test_uniform_bands_give_the_expected_ndvi(self):
        """red=50, nir=200 -> (200-50)/(200+50) = 0.6, a healthy canopy."""
        record = NDVIRecord(field=self.field, captured_on=date(2026, 6, 1))
        record.red_band.save("r.png", band(50), save=False)
        record.nir_band.save("n.png", band(200), save=False)
        record.save()

        process_ndvi_record(record.pk)
        record.refresh_from_db()

        self.assertEqual(record.status, NDVIStatus.DONE)
        self.assertEqual(record.index_used, "NDVI")
        self.assertAlmostEqual(record.mean_index, 0.6, places=2)
        self.assertAlmostEqual(record.healthy_pct, 100.0, places=1)
        self.assertTrue(record.overlay)

    def test_processing_updates_the_field_health_band(self):
        record = NDVIRecord(field=self.field, captured_on=date(2026, 6, 2))
        record.red_band.save("r2.png", band(200), save=False)
        record.nir_band.save("n2.png", band(210), save=False)
        record.save()

        process_ndvi_record(record.pk)
        self.field.refresh_from_db()

        self.assertEqual(self.field.health, "critical")
        self.assertIsNotNone(self.field.ndvi_updated_at)

    def test_mismatched_bands_fail_without_raising(self):
        record = NDVIRecord(field=self.field, captured_on=date(2026, 6, 3))
        record.red_band.save("r3.png", band(50, size=32), save=False)
        record.nir_band.save("n3.png", band(200, size=64), save=False)
        record.save()

        process_ndvi_record(record.pk)
        record.refresh_from_db()

        self.assertEqual(record.status, NDVIStatus.FAILED)
        self.assertIn("Band sizes differ", record.error_message)

    def test_rgb_upload_falls_back_to_vari(self):
        buffer = BytesIO()
        rgb = np.dstack([
            np.full((64, 64), 60, np.uint8),
            np.full((64, 64), 200, np.uint8),
            np.full((64, 64), 50, np.uint8),
        ])
        Image.fromarray(rgb, "RGB").save(buffer, format="PNG")

        record = NDVIRecord(field=self.field, captured_on=date(2026, 6, 4))
        record.rgb_image.save("rgb.png", ContentFile(buffer.getvalue()), save=False)
        record.save()

        process_ndvi_record(record.pk)
        record.refresh_from_db()

        self.assertEqual(record.index_used, "VARI")
        self.assertEqual(record.status, NDVIStatus.DONE)

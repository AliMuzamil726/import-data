"""Notification routing and dashboard aggregation."""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.crops.models import Crop, CropStatus
from apps.farmers.models import Farmer
from apps.fields.models import Field

from .models import Notification, NotificationLevel
from .notifications import notify
from .services import dashboard_metrics


class NotificationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user(
            username="alice", password="test-pass-1234", role=Role.AGRI_MANAGER
        )
        cls.bob = User.objects.create_user(
            username="bob", password="test-pass-1234", role=Role.FIELD_OFFICER
        )

    def test_broadcasts_reach_every_user(self):
        notify("Broadcast", "Visible to all")
        self.assertEqual(Notification.objects.for_user(self.alice).count(), 1)
        self.assertEqual(Notification.objects.for_user(self.bob).count(), 1)

    def test_targeted_alerts_stay_private(self):
        notify("Private", "Only Alice", recipient=self.alice)
        self.assertEqual(Notification.objects.for_user(self.alice).count(), 1)
        self.assertEqual(Notification.objects.for_user(self.bob).count(), 0)

    def test_feed_and_mark_read_endpoints(self):
        notify("Alert", "Check this", level=NotificationLevel.WARNING)
        self.client.force_login(self.alice)

        feed = self.client.get(reverse("core:notification_feed")).json()
        self.assertEqual(feed["unread"], 1)

        self.client.post(reverse("core:notification_read"))
        self.assertEqual(
            self.client.get(reverse("core:notification_feed")).json()["unread"], 0
        )

    def test_registering_a_farmer_raises_a_notification(self):
        Farmer.objects.create(
            full_name="Signal Grower", cnic="35202-9999999-9", phone="03001234567",
            city="Multan", registration_date=date(2026, 1, 1),
        )
        self.assertTrue(Notification.objects.filter(category="farmers").exists())


class DashboardMetricTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="admin", password="test-pass-1234", role=Role.SUPER_ADMIN
        )
        farmer = Farmer.objects.create(
            full_name="Grower", cnic="35202-1234567-1", phone="03001234567",
            city="Faisalabad", registration_date=date.today(),
        )
        field = Field.objects.create(
            name="Block", code="FSD-001-A", farmer=farmer,
            latitude=Decimal("31.4"), longitude=Decimal("73.0"),
            area_acres=Decimal("10.00"), health="healthy",
        )
        Crop.objects.create(
            name="Cotton", category="fibre", season="kharif", field=field,
            planting_date=date.today(), actual_harvest_date=date.today(),
            area_acres=Decimal("10.00"), production_tonnes=Decimal("9.000"),
            price_per_tonne=Decimal("165000.00"), status=CropStatus.HARVESTED,
        )

    def test_headline_cards_are_computed_from_the_database(self):
        metrics = dashboard_metrics(self.user)
        cards = {card["key"]: card for card in metrics["cards"]}

        self.assertEqual(cards["farmers"]["value"], 1)
        self.assertEqual(cards["fields"]["value"], 1)
        self.assertEqual(cards["acres"]["value"], 10.0)
        self.assertEqual(cards["healthy"]["value"], 1)
        # Revenue, Production and Open-alerts cards were removed by request.
        self.assertNotIn("revenue", cards)
        self.assertNotIn("production", cards)

    def test_dashboard_page_renders(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("core:dashboard")).status_code, 200)

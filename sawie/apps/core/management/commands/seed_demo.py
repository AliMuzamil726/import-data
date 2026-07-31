"""Populate the database with a realistic sample dataset.

This is for evaluating the interface before real data is loaded. It is opt-in,
never runs automatically, and refuses to touch a database that already holds
farmer records unless you pass --force.
"""
import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Role, User
from apps.crops.models import Crop, CropCategory, CropStatus, Season
from apps.farmers.models import Farmer, FarmerStatus
from apps.fields.models import (
    FarmActivity, Field, FieldStatus, HealthBand, IrrigationType, SoilType,
)

# Punjab cotton and rice belt, roughly Faisalabad to Bahawalpur.
CENTRES = [
    ("Faisalabad", 31.4180, 73.0790),
    ("Sahiwal", 30.6682, 73.1114),
    ("Multan", 30.1575, 71.5249),
    ("Bahawalpur", 29.3956, 71.6836),
    ("Vehari", 30.0331, 72.3489),
]
FIRST = ["Muhammad", "Ali", "Ahmed", "Usman", "Bilal", "Hassan", "Imran", "Nadeem",
         "Rashid", "Tariq", "Zubair", "Kashif", "Adnan", "Faisal", "Sajid"]
LAST = ["Aslam", "Iqbal", "Hussain", "Khan", "Farooq", "Yousaf", "Mehmood",
        "Anwar", "Riaz", "Sattar", "Bashir", "Javed"]
CROPS = [
    ("Cotton", CropCategory.FIBRE, Season.KHARIF, ["FH-490", "IUB-2013", "CIM-602"], 0.9, 165000),
    ("Rice", CropCategory.CEREAL, Season.KHARIF, ["Super Basmati", "Kainat", "PK-386"], 2.6, 92000),
    ("Wheat", CropCategory.CEREAL, Season.RABI, ["Akbar-19", "Faisalabad-08"], 3.1, 88000),
    ("Maize", CropCategory.CEREAL, Season.KHARIF, ["Pioneer 30Y87", "DK-6103"], 4.2, 76000),
    ("Sugarcane", CropCategory.SUGAR, Season.PERENNIAL, ["CPF-247", "HSF-240"], 28.0, 8500),
]


class Command(BaseCommand):
    help = "Create sample farmers, fields, crops and activities for evaluation."

    def add_arguments(self, parser):
        parser.add_argument("--farmers", type=int, default=40)
        parser.add_argument("--force", action="store_true",
                            help="Seed even if farmer records already exist.")
        parser.add_argument("--seed", type=int, default=20260723,
                            help="Random seed, so runs are reproducible.")

    @transaction.atomic
    def handle(self, *args, **options):
        if Farmer.objects.exists() and not options["force"]:
            self.stdout.write(self.style.ERROR(
                "This database already holds farmer records. Re-run with --force if you are sure."
            ))
            return

        random.seed(options["seed"])
        officers = list(User.objects.filter(role=Role.FIELD_OFFICER))
        today = date.today()
        counts = {"farmers": 0, "fields": 0, "crops": 0, "activities": 0}

        for index in range(options["farmers"]):
            city, base_lat, base_lng = random.choice(CENTRES)
            name = f"{random.choice(FIRST)} {random.choice(LAST)}"
            declared = Decimal(random.randint(6, 90))

            farmer = Farmer.objects.create(
                full_name=name,
                father_name=f"{random.choice(FIRST)} {random.choice(LAST)}",
                cnic=f"3{random.randint(1000, 9999)}-{random.randint(1000000, 9999999)}-{random.randint(1, 9)}",
                phone=f"+92 3{random.randint(10, 49)} {random.randint(1000000, 9999999)}",
                email=f"{name.split()[0].lower()}{index}@example.pk",
                village=f"Chak {random.randint(10, 460)} {random.choice(['GB', 'JB', 'RB', 'ML'])}",
                city=city,
                district=city,
                total_land_acres=declared,
                registration_date=today - timedelta(days=random.randint(1, 900)),
                status=random.choices(
                    [FarmerStatus.ACTIVE, FarmerStatus.PENDING, FarmerStatus.INACTIVE],
                    weights=[8, 1, 1],
                )[0],
            )
            counts["farmers"] += 1

            for plot in range(random.randint(1, 3)):
                area = Decimal(str(round(random.uniform(2.5, 28.0), 2)))
                lat = base_lat + random.uniform(-0.42, 0.42)
                lng = base_lng + random.uniform(-0.42, 0.42)
                span = 0.004 + float(area) * 0.00012
                boundary = {
                    "type": "Polygon",
                    "coordinates": [[
                        [round(lng - span, 6), round(lat - span * 0.7, 6)],
                        [round(lng + span, 6), round(lat - span * 0.7, 6)],
                        [round(lng + span, 6), round(lat + span * 0.7, 6)],
                        [round(lng - span, 6), round(lat + span * 0.7, 6)],
                        [round(lng - span, 6), round(lat - span * 0.7, 6)],
                    ]],
                }
                health = random.choices(
                    [HealthBand.HEALTHY, HealthBand.MODERATE, HealthBand.POOR,
                     HealthBand.CRITICAL, HealthBand.UNKNOWN],
                    weights=[10, 6, 3, 1, 4],
                )[0]
                ndvi = {
                    HealthBand.HEALTHY: round(random.uniform(0.52, 0.82), 3),
                    HealthBand.MODERATE: round(random.uniform(0.31, 0.49), 3),
                    HealthBand.POOR: round(random.uniform(0.16, 0.29), 3),
                    HealthBand.CRITICAL: round(random.uniform(0.02, 0.14), 3),
                }.get(health)

                field = Field.objects.create(
                    name=f"{random.choice(['North', 'South', 'East', 'West', 'Canal', 'Corner'])} block",
                    code=f"{city[:3].upper()}-{index + 1:03d}-{chr(65 + plot)}",
                    farmer=farmer,
                    latitude=Decimal(str(round(lat, 6))),
                    longitude=Decimal(str(round(lng, 6))),
                    boundary=boundary,
                    area_acres=area,
                    soil_type=random.choice(list(SoilType)),
                    irrigation_type=random.choice(list(IrrigationType)),
                    status=random.choices(
                        [FieldStatus.ACTIVE, FieldStatus.FALLOW, FieldStatus.HARVESTED],
                        weights=[8, 1, 2],
                    )[0],
                    health=health,
                    latest_ndvi=ndvi,
                    officer=random.choice(officers) if officers else None,
                )
                counts["fields"] += 1

                for cycle in range(random.randint(1, 3)):
                    crop_name, category, season, varieties, base_yield, price = random.choice(CROPS)
                    planted = today - timedelta(days=random.randint(30, 700))
                    duration = random.randint(95, 165)
                    expected = planted + timedelta(days=duration)
                    harvested = expected < today and random.random() < 0.85

                    sown = Decimal(str(round(float(area) * random.uniform(0.55, 1.0), 2)))
                    production = Decimal("0")
                    if harvested:
                        production = Decimal(str(round(
                            float(sown) * base_yield * random.uniform(0.72, 1.22), 3
                        )))

                    crop = Crop.objects.create(
                        name=crop_name,
                        variety=random.choice(varieties),
                        category=category,
                        season=season,
                        field=field,
                        planting_date=planted,
                        expected_harvest_date=expected,
                        actual_harvest_date=expected if harvested else None,
                        area_acres=sown,
                        production_tonnes=production,
                        price_per_tonne=Decimal(str(price)),
                        status=(
                            CropStatus.HARVESTED if harvested
                            else CropStatus.GROWING if expected >= today
                            else CropStatus.FAILED
                        ),
                    )
                    counts["crops"] += 1

                    for offset, kind in [
                        (0, FarmActivity.Kind.SOWING),
                        (18, FarmActivity.Kind.IRRIGATION),
                        (34, FarmActivity.Kind.FERTILISER),
                        (58, FarmActivity.Kind.PESTICIDE),
                    ]:
                        performed = planted + timedelta(days=offset)
                        if performed > today:
                            continue
                        FarmActivity.objects.create(
                            field=field, crop=crop, kind=kind, performed_on=performed,
                            detail={
                                FarmActivity.Kind.SOWING: f"{crop.variety} drilled",
                                FarmActivity.Kind.IRRIGATION: "Canal turn",
                                FarmActivity.Kind.FERTILISER: "Urea top dressing",
                                FarmActivity.Kind.PESTICIDE: "Sucking pest spray",
                            }[kind],
                            quantity=Decimal(str(round(random.uniform(20, 120), 2))),
                            unit=random.choice(["kg", "bag", "litre", "acre-inch"]),
                            cost=Decimal(str(round(random.uniform(3000, 45000), 2))),
                        )
                        counts["activities"] += 1

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {counts['farmers']} farmers, {counts['fields']} fields, "
            f"{counts['crops']} crop cycles and {counts['activities']} activities."
        ))

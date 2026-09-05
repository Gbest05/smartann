import os
import sys
import click
import random
from datetime import datetime, date, timedelta, timezone
from app import create_app, init_db_and_defaults
from app.models import db, User, EnergyRecord, Prediction, ANNModel, SystemSetting, Recommendation, ActivityLog
from app.ml.train_model import train_ann_model

app = create_app(os.environ.get('FLASK_ENV', 'default'))
init_db_and_defaults(app)


def init_db_func():
    """Create all database tables."""
    with app.app_context():
        db.create_all()
        print("[OK] Database tables initialized successfully.")


def create_admin_func(name: str = 'Project Administrator', email: str = 'admin@energy.test', password: str = 'AdminPass123!'):
    """Create or update administrator account securely."""
    with app.app_context():
        db.create_all()
        email_clean = email.lower().strip()
        existing = User.query.filter_by(email=email_clean).first()
        if existing:
            existing.full_name = name
            existing.role = 'admin'
            existing.set_password(password)
            db.session.commit()
            print(f"[OK] Updated existing user '{email_clean}' to Administrator.")
        else:
            admin_user = User(
                full_name=name,
                email=email_clean,
                role='admin'
            )
            admin_user.set_password(password)
            db.session.add(admin_user)
            db.session.commit()
            print(f"[OK] Created new Administrator account: {email_clean}")


def seed_data_func(records_count: int = 365):
    """Seed the database with default settings, demo accounts, recommendations, and realistic historical Demo Data."""
    with app.app_context():
        db.create_all()
        print("Seeding Smart Energy Management System...")

        # 1. System Settings Defaults
        settings_data = [
            ('tariff_per_kwh', '120.0', 'Electricity tariff rate in Nigerian Naira per kWh (NGN/kWh)'),
            ('low_consumption_threshold', '5.0', 'Daily consumption threshold in kWh for Low tier (Green)'),
            ('moderate_consumption_threshold', '10.0', 'Daily consumption threshold in kWh for Moderate tier (Amber)')
        ]
        for key, val, desc in settings_data:
            setting = SystemSetting.query.filter_by(key=key).first()
            if not setting:
                db.session.add(SystemSetting(key=key, value=val, description=desc))
        db.session.commit()
        print("[OK] Default system settings and tariff rate configured.")

        # 2. Create Demo Accounts
        admin_email = 'admin@energy.test'
        admin = User.query.filter_by(email=admin_email).first()
        if not admin:
            admin = User(full_name='Project Administrator', email=admin_email, role='admin')
            admin.set_password('AdminPass123!')
            db.session.add(admin)

        resident_email = 'resident@energy.test'
        resident = User.query.filter_by(email=resident_email).first()
        if not resident:
            resident = User(full_name='Ibrahim Bello', email=resident_email, role='resident')
            resident.set_password('ResidentPass123!')
            db.session.add(resident)

        resident2_email = 'chinwe.eze@energy.test'
        resident2 = User.query.filter_by(email=resident2_email).first()
        if not resident2:
            resident2 = User(full_name='Chinwe Eze', email=resident2_email, role='resident')
            resident2.set_password('ResidentPass123!')
            db.session.add(resident2)

        db.session.commit()
        print("[OK] Demo accounts created (Admin: admin@energy.test / Resident: resident@energy.test).")

        # 3. Seed Default Recommendations
        recs_data = [
            ("Air Conditioning Temperature Optimization", "Keep cooling thermostats set to 24C-26C. Each degree below 24C increases electricity consumption by 6-8%.", "high", "bi-snow"),
            ("Water Heater Operating Schedule", "Switch off electric water heaters once warm. Avoid continuous 24-hour boiling standby.", "high", "bi-fire"),
            ("Off-Peak Appliance Scheduling", "Operate washing machines, pumping machines, and iron boxes during off-peak morning hours.", "moderate", "bi-clock-history"),
            ("LED Lighting Transition", "Ensure all room fixtures use energy-efficient LED luminaires instead of halogen or incandescent bulbs.", "moderate", "bi-lightbulb-fill"),
            ("Natural Cross-Ventilation", "Open windows in the early morning and evening to cool interior rooms naturally.", "low", "bi-wind")
        ]
        for title, msg, tier, icon in recs_data:
            existing_rec = Recommendation.query.filter_by(title=title).first()
            if not existing_rec:
                db.session.add(Recommendation(title=title, message=msg, consumption_level=tier, icon=icon, is_active=True))
        db.session.commit()
        print("[OK] Smart recommendation rules seeded.")

        # 4. Generate Realistic Synthetic Daily Consumption Records (Labeled as Demo Data)
        tariff = 120.0
        start_date = date.today() - timedelta(days=records_count)
        
        # Clear previous synthetic records if any to avoid duplication
        EnergyRecord.query.filter_by(is_synthetic=True).delete()
        db.session.commit()

        records_to_insert = []
        random.seed(42)  # Deterministic realistic pattern

        for user_obj in [resident, resident2]:
            base_kwh = 8.2 if user_obj.id == resident.id else 6.8
            for d_idx in range(records_count):
                rec_date = start_date + timedelta(days=d_idx)
                
                # Seasonal variation
                month = rec_date.month
                season_factor = 1.25 if month in [2, 3, 4, 11, 12] else 0.95
                
                # Weekend variation
                weekend_factor = 1.20 if rec_date.weekday() in [5, 6] else 1.0
                
                # Random realistic fluctuation
                noise = random.uniform(-1.5, 1.8)
                daily_kwh = max(2.5, round((base_kwh * season_factor * weekend_factor) + noise, 2))
                
                # Split into Peak (52-64%) and Off-Peak
                peak_ratio = random.uniform(0.52, 0.64)
                peak_kwh = round(daily_kwh * peak_ratio, 2)
                off_peak_kwh = round(daily_kwh - peak_kwh, 2)
                
                appliance_hours = round(min(24.0, max(2.0, (daily_kwh * 0.9) + random.uniform(-1.0, 1.0))), 1)
                cost = round(daily_kwh * tariff, 2)

                rec = EnergyRecord(
                    user_id=user_obj.id,
                    date=rec_date,
                    electricity_consumption_kwh=daily_kwh,
                    peak_consumption_kwh=peak_kwh,
                    off_peak_consumption_kwh=off_peak_kwh,
                    appliance_usage_hours=appliance_hours,
                    estimated_cost=cost,
                    is_synthetic=True  # Labeled Demo Data
                )
                records_to_insert.append(rec)

        db.session.bulk_save_objects(records_to_insert)
        db.session.commit()
        print(f"[OK] Generated {len(records_to_insert)} realistic historical daily energy records (labeled as Demo Data).")

        # 5. Train initial ANN Model
        print("Training initial Artificial Neural Network (MLPRegressor)...")
        train_result = train_ann_model(user_id=admin.id)
        if train_result['success']:
            print(f"[OK] ANN Model successfully trained! R2 Score: {train_result['r2_score']}, MAE: {train_result['mae']} kWh.")
        else:
            print(f"[!] ANN Model training note: {train_result['message']}")

        # 6. Generate a few initial predictions for demo display
        pred_date = date.today() + timedelta(days=1)
        pred_entry = Prediction(
            user_id=resident.id,
            prediction_date=pred_date,
            predicted_consumption_kwh=9.42,
            estimated_cost=round(9.42 * tariff, 2),
            peak_consumption_kwh=5.20,
            off_peak_consumption_kwh=4.22,
            appliance_usage_hours=8.5,
            consumption_level='Moderate',
            model_version='ANN (MLPRegressor v1.0)'
        )
        db.session.add(pred_entry)
        db.session.commit()
        print("[OK] Sample ANN prediction logged.")
        print("\nSetup complete! You can now start the application with 'python run.py'.")


# Click CLI Wrappers
@app.cli.command("init-db")
def init_db_cli():
    """Create all database tables."""
    init_db_func()


@app.cli.command("create-admin")
@click.option('--name', default='System Administrator', help='Full name of administrator')
@click.option('--email', default='admin@energy.test', help='Email of administrator')
@click.option('--password', default='AdminPass123!', help='Password')
def create_admin_cli(name, email, password):
    """Create an administrator account securely."""
    create_admin_func(name=name, email=email, password=password)


@app.cli.command("seed-data")
@click.option('--records-count', default=365, help='Number of days of historical records to generate')
def seed_data_cli(records_count):
    """Seed the database with default settings, sample users, recommendations, and realistic Demo Data."""
    seed_data_func(records_count=records_count)


@app.cli.command("train-ann")
def train_ann_cli():
    """Train the Scikit-learn Artificial Neural Network (MLPRegressor) model."""
    with app.app_context():
        result = train_ann_model()
        if result['success']:
            print(f"SUCCESS: {result['message']}")
            print(f"Metrics: R2={result['r2_score']}, MAE={result['mae']}, MSE={result['mse']}, RMSE={result['rmse']}")
        else:
            print(f"WARNING: {result['message']}")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == 'seed-data':
            count = int(sys.argv[2]) if len(sys.argv) > 2 else 365
            seed_data_func(records_count=count)
        elif cmd == 'create-admin':
            name = sys.argv[2] if len(sys.argv) > 2 else 'Project Administrator'
            email = sys.argv[3] if len(sys.argv) > 3 else 'admin@energy.test'
            pwd = sys.argv[4] if len(sys.argv) > 4 else 'AdminPass123!'
            create_admin_func(name=name, email=email, password=pwd)
        elif cmd == 'init-db':
            init_db_func()
        elif cmd == 'train-ann':
            with app.app_context():
                res = train_ann_model()
                print(res)
        else:
            print(f"Unknown command: {cmd}. Supported: seed-data, create-admin, init-db, train-ann")
    else:
        with app.app_context():
            db.create_all()
        app.run(debug=True, host='127.0.0.1', port=5000)

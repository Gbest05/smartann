import csv
import io
from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request, Response, current_app
from flask_login import login_required, current_user
from app.models import db, EnergyRecord, User
from app.forms import EnergyRecordForm, CSVUploadForm
from app.utils.decorators import admin_required
from app.utils.helpers import calculate_cost, get_active_tariff, log_activity

energy_bp = Blueprint('energy', __name__, url_prefix='/energy')


@energy_bp.route('/records')
@login_required
def records():
    """List historical energy consumption records with filtering and pagination."""
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('ITEMS_PER_PAGE', 15)
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    user_filter = request.args.get('user_id', type=int)

    # Base query: Residents see own records, Admins see all unless filtered
    if current_user.is_admin:
        query = EnergyRecord.query
        if user_filter:
            query = query.filter_by(user_id=user_filter)
    else:
        query = EnergyRecord.query.filter_by(user_id=current_user.id)

    # Apply date filters
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            query = query.filter(EnergyRecord.date >= start_date)
        except ValueError:
            pass

    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            query = query.filter(EnergyRecord.date <= end_date)
        except ValueError:
            pass

    pagination = query.order_by(EnergyRecord.date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    records_list = pagination.items

    users_list = User.query.all() if current_user.is_admin else []

    return render_template(
        'energy/list.html',
        records=records_list,
        pagination=pagination,
        users=users_list,
        selected_user=user_filter,
        start_date=start_date_str,
        end_date=end_date_str
    )


@energy_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_record():
    """Manually add an energy consumption record."""
    form = EnergyRecordForm()

    if form.validate_on_submit():
        tariff = get_active_tariff()
        kwh = form.electricity_consumption_kwh.data
        cost = form.estimated_cost.data
        if not cost or cost <= 0:
            cost = calculate_cost(kwh, tariff)

        record = EnergyRecord(
            user_id=current_user.id,
            date=form.date.data,
            electricity_consumption_kwh=kwh,
            peak_consumption_kwh=form.peak_consumption_kwh.data or 0.0,
            off_peak_consumption_kwh=form.off_peak_consumption_kwh.data or 0.0,
            appliance_usage_hours=form.appliance_usage_hours.data or 0.0,
            estimated_cost=cost,
            is_synthetic=form.is_synthetic.data
        )

        db.session.add(record)
        db.session.commit()

        log_activity(
            current_user.id,
            'ADD_RECORD',
            f"Added energy record for {record.date}: {record.electricity_consumption_kwh} kWh (₦{record.estimated_cost:,.2f})"
        )
        flash(f"Energy record for {record.date.strftime('%B %d, %Y')} saved successfully!", 'success')
        return redirect(url_for('energy.records'))

    return render_template('energy/add.html', form=form)


@energy_bp.route('/edit/<int:record_id>', methods=['GET', 'POST'])
@login_required
def edit_record(record_id):
    """Edit an existing energy record."""
    record = EnergyRecord.query.get_or_404(record_id)

    # Authorization check
    if not current_user.is_admin and record.user_id != current_user.id:
        flash("You do not have permission to edit this record.", 'danger')
        return redirect(url_for('energy.records'))

    form = EnergyRecordForm(obj=record)

    if form.validate_on_submit():
        record.date = form.date.data
        record.electricity_consumption_kwh = form.electricity_consumption_kwh.data
        record.peak_consumption_kwh = form.peak_consumption_kwh.data or 0.0
        record.off_peak_consumption_kwh = form.off_peak_consumption_kwh.data or 0.0
        record.appliance_usage_hours = form.appliance_usage_hours.data or 0.0
        record.is_synthetic = form.is_synthetic.data

        # Calculate or update cost
        if form.estimated_cost.data and form.estimated_cost.data > 0:
            record.estimated_cost = form.estimated_cost.data
        else:
            record.estimated_cost = calculate_cost(record.electricity_consumption_kwh)

        db.session.commit()

        log_activity(
            current_user.id,
            'EDIT_RECORD',
            f"Updated energy record #{record.id} for {record.date}."
        )
        flash('Energy record updated successfully!', 'success')
        return redirect(url_for('energy.records'))

    return render_template('energy/edit.html', form=form, record=record)


@energy_bp.route('/delete/<int:record_id>', methods=['POST'])
@login_required
def delete_record(record_id):
    """Delete an energy consumption record."""
    record = EnergyRecord.query.get_or_404(record_id)

    if not current_user.is_admin and record.user_id != current_user.id:
        flash("You do not have permission to delete this record.", 'danger')
        return redirect(url_for('energy.records'))

    date_str = record.date.strftime('%Y-%m-%d')
    kwh = record.electricity_consumption_kwh

    db.session.delete(record)
    db.session.commit()

    log_activity(
        current_user.id,
        'DELETE_RECORD',
        f"Deleted energy record #{record_id} ({date_str}, {kwh} kWh)."
    )
    flash('Energy record deleted successfully.', 'info')
    return redirect(url_for('energy.records'))


@energy_bp.route('/import-csv', methods=['GET', 'POST'])
@admin_required
def import_csv():
    """Administrator batch CSV energy data import with validation and error reporting."""
    form = CSVUploadForm()
    users = User.query.order_by(User.full_name.asc()).all()
    form.user_id.choices = [(u.id, f"{u.full_name} ({u.email})") for u in users]

    if form.validate_on_submit():
        file = form.csv_file.data
        user_id = form.user_id.data
        is_synthetic = form.is_synthetic.data
        tariff = get_active_tariff()

        try:
            stream = io.StringIO(file.stream.read().decode("utf-8-sig"), newline=None)
            csv_reader = csv.DictReader(stream)

            # Standardize column headers (lowercase, trimmed)
            if not csv_reader.fieldnames:
                flash('The uploaded CSV file appears to be empty.', 'danger')
                return render_template('energy/import_csv.html', form=form)

            headers = [h.strip().lower() for h in csv_reader.fieldnames]
            
            # Verify minimum required columns
            required_cols = {'date', 'electricity_consumption_kwh'}
            if not required_cols.issubset(set(headers)):
                flash(f"Invalid CSV structure. Missing required columns: {required_cols - set(headers)}. Expected headers: date, electricity_consumption_kwh, peak_consumption_kwh, off_peak_consumption_kwh, appliance_usage_hours, estimated_cost", 'danger')
                return render_template('energy/import_csv.html', form=form)

            success_count = 0
            failed_rows = []
            row_num = 1

            for row in csv_reader:
                row_num += 1
                # Clean row dictionary keys
                cleaned_row = {k.strip().lower(): (v.strip() if v else '') for k, v in row.items() if k}

                try:
                    # 1. Parse date
                    raw_date = cleaned_row.get('date', '')
                    record_date = None
                    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y/%m/%d'):
                        try:
                            record_date = datetime.strptime(raw_date, fmt).date()
                            break
                        except ValueError:
                            continue
                    
                    if not record_date:
                        failed_rows.append(f"Row {row_num}: Invalid date format '{raw_date}'. Use YYYY-MM-DD.")
                        continue

                    # 2. Parse consumption
                    kwh_str = cleaned_row.get('electricity_consumption_kwh', '')
                    kwh = float(kwh_str)
                    if kwh <= 0:
                        failed_rows.append(f"Row {row_num}: Electricity consumption must be positive, got '{kwh}'.")
                        continue

                    # 3. Parse optional fields
                    peak_str = cleaned_row.get('peak_consumption_kwh', '0')
                    peak_kwh = max(0.0, float(peak_str)) if peak_str else 0.0

                    off_peak_str = cleaned_row.get('off_peak_consumption_kwh', '0')
                    off_peak_kwh = max(0.0, float(off_peak_str)) if off_peak_str else 0.0

                    hours_str = cleaned_row.get('appliance_usage_hours', '0')
                    appliance_hours = max(0.0, min(24.0, float(hours_str))) if hours_str else 0.0

                    cost_str = cleaned_row.get('estimated_cost', '')
                    if cost_str:
                        cost = max(0.0, float(cost_str))
                    else:
                        cost = calculate_cost(kwh, tariff)

                    # Create record
                    rec = EnergyRecord(
                        user_id=user_id,
                        date=record_date,
                        electricity_consumption_kwh=kwh,
                        peak_consumption_kwh=peak_kwh,
                        off_peak_consumption_kwh=off_peak_kwh,
                        appliance_usage_hours=appliance_hours,
                        estimated_cost=cost,
                        is_synthetic=is_synthetic
                    )
                    db.session.add(rec)
                    success_count += 1

                except Exception as row_err:
                    failed_rows.append(f"Row {row_num}: Failed to parse record ({str(row_err)})")

            if success_count > 0:
                db.session.commit()
                log_activity(
                    current_user.id,
                    'CSV_IMPORT',
                    f"Successfully imported {success_count} energy records from CSV. Failed rows: {len(failed_rows)}."
                )
                flash(f"CSV import completed! Successfully imported {success_count} energy record(s).", 'success')
            else:
                flash("No records could be imported from the CSV file. Please review the errors below.", 'danger')

            return render_template(
                'energy/import_csv.html',
                form=form,
                success_count=success_count,
                failed_rows=failed_rows
            )

        except Exception as e:
            db.session.rollback()
            flash(f"CSV processing error: {str(e)}", 'danger')

    return render_template('energy/import_csv.html', form=form)


@energy_bp.route('/sample-csv')
def sample_csv():
    """Generate and serve downloadable sample CSV template for energy data import."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'date',
        'electricity_consumption_kwh',
        'peak_consumption_kwh',
        'off_peak_consumption_kwh',
        'appliance_usage_hours',
        'estimated_cost'
    ])
    # Sample rows
    writer.writerow(['2026-08-01', '8.45', '4.80', '3.65', '8.5', '1014.00'])
    writer.writerow(['2026-08-02', '9.10', '5.20', '3.90', '9.0', '1092.00'])
    writer.writerow(['2026-08-03', '7.80', '4.10', '3.70', '7.0', '936.00'])
    writer.writerow(['2026-08-04', '11.20', '6.80', '4.40', '11.5', '1344.00'])
    writer.writerow(['2026-08-05', '6.50', '3.50', '3.00', '6.0', '780.00'])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=energy_sample_data.csv"}
    )

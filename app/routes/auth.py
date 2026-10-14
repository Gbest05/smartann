import os
import uuid
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from app.models import db, User
from app.forms import LoginForm, RegistrationForm, ProfileUpdateForm, ChangePasswordForm
from app.utils.helpers import log_activity

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User authentication route."""
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('dashboard.resident_dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        try:
            user = User.query.filter_by(email=email).first()
        except Exception as e:
            try:
                db.session.rollback()
            except Exception:
                pass
            current_app.logger.error(f"Database error during login query: {e}")
            flash('Database connection failed. Please ensure the database server is running and reachable.', 'danger')
            return render_template('auth/login.html', form=form)

        if user and user.check_password(form.password.data.strip()):
            try:
                login_user(user, remember=form.remember_me.data)
                log_activity(user.id, 'LOGIN', f"User {user.email} signed in successfully.")
            except Exception as e:
                current_app.logger.warning(f"Session or activity logging warning: {e}")

            flash(f"Welcome back, {user.full_name}!", 'success')

            # Handle next redirection
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)

            if user.is_admin:
                return redirect(url_for('admin.dashboard'))
            return redirect(url_for('dashboard.resident_dashboard'))
        else:
            flash('Invalid email address or password. Please try again.', 'danger')

    return render_template('auth/login.html', form=form)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration route."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.resident_dashboard'))

    form = RegistrationForm()
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        role = form.role.data if form.role.data in ['resident', 'admin'] else 'resident'

        try:
            user = User(
                full_name=form.full_name.data.strip(),
                email=email,
                role=role
            )
            user.set_password(form.password.data)

            db.session.add(user)
            db.session.commit()

            login_user(user)
            log_activity(user.id, 'REGISTER', f"New account registered as {role.upper()} for {email}.")
            flash(f"Registration successful! Welcome to the Smart Energy Management Platform, {user.full_name}.", 'success')

            if user.is_admin:
                return redirect(url_for('admin.dashboard'))
            return redirect(url_for('dashboard.resident_dashboard'))
        except Exception as e:
            try:
                db.session.rollback()
            except Exception:
                pass
            current_app.logger.error(f"Database error during user registration: {e}")
            flash('Database connection failed. Unable to complete registration.', 'danger')
            return render_template('auth/register.html', form=form)

    return render_template('auth/register.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    """Sign out the current user."""
    user_id = current_user.id
    email = current_user.email
    logout_user()
    log_activity(user_id, 'LOGOUT', f"User {email} signed out.")
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile overview, avatar upload, and password reset."""
    profile_form = ProfileUpdateForm(prefix="profile", full_name=current_user.full_name)
    password_form = ChangePasswordForm(prefix="password")

    action = request.form.get('action')

    # Handle Profile & Avatar Update
    if action == 'update_profile' and profile_form.validate_on_submit():
        current_user.full_name = profile_form.full_name.data.strip()

        if profile_form.avatar.data:
            file = profile_form.avatar.data
            ext = os.path.splitext(file.filename)[1].lower()
            unique_filename = f"avatar_{current_user.id}_{uuid.uuid4().hex[:8]}{ext}"
            
            upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'avatars')
            os.makedirs(upload_dir, exist_ok=True)
            
            file_path = os.path.join(upload_dir, unique_filename)
            file.save(file_path)
            current_user.avatar = unique_filename

        db.session.commit()
        log_activity(current_user.id, 'UPDATE_PROFILE', "Updated profile details and avatar.")
        flash('Profile details updated successfully!', 'success')
        return redirect(url_for('auth.profile'))

    # Handle Password Reset / Change
    if action == 'change_password' and password_form.validate_on_submit():
        if not current_user.check_password(password_form.current_password.data.strip()):
            flash('Your current password was incorrect. Please try again.', 'danger')
        else:
            current_user.set_password(password_form.new_password.data.strip())
            db.session.commit()
            log_activity(current_user.id, 'CHANGE_PASSWORD', "Successfully changed account password.")
            flash('Your password has been changed successfully!', 'success')
            return redirect(url_for('auth.profile'))

    total_records = current_user.energy_records.count()
    total_predictions = current_user.predictions.count()
    
    return render_template(
        'auth/profile.html',
        profile_form=profile_form,
        password_form=password_form,
        total_records=total_records,
        total_predictions=total_predictions
    )

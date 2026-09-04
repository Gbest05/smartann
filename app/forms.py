from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import (
    StringField, PasswordField, BooleanField, SubmitField,
    FloatField, DateField, TextAreaField, SelectField
)
from wtforms.validators import (
    DataRequired, EqualTo, Length, NumberRange, Optional, ValidationError, Regexp
)
from datetime import date
from app.models import User

# Universal email format validator regex (allows .test, .local, .ng, .com, etc.)
EMAIL_REGEX = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'


class LoginForm(FlaskForm):
    """User login form."""
    email = StringField('Email Address', validators=[
        DataRequired(message='Please provide your email address.'),
        Regexp(EMAIL_REGEX, message='Please enter a valid email address (e.g. admin@energy.test).')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message='Please enter your password.')
    ])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')


class RegistrationForm(FlaskForm):
    """User registration form."""
    full_name = StringField('Full Name', validators=[
        DataRequired(message='Please enter your full name.'),
        Length(min=2, max=100, message='Name must be between 2 and 100 characters.')
    ])
    email = StringField('Email Address', validators=[
        DataRequired(message='Please enter your email address.'),
        Regexp(EMAIL_REGEX, message='Please enter a valid email address.')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message='Please create a password.'),
        Length(min=6, max=50, message='Password must be at least 6 characters long.')
    ])
    password2 = PasswordField('Confirm Password', validators=[
        DataRequired(message='Please confirm your password.'),
        EqualTo('password', message='Passwords must match.')
    ])
    role = SelectField('Account Role', choices=[('resident', 'Resident / Household'), ('admin', 'Administrator')], default='resident')
    submit = SubmitField('Create Account')

    def validate_email(self, field):
        user = User.query.filter_by(email=field.data.lower().strip()).first()
        if user:
            raise ValidationError('An account with this email address already exists. Please log in or use a different email.')


class EnergyRecordForm(FlaskForm):
    """Form to manually enter or update an energy consumption record."""
    date = DateField('Record Date', default=date.today, validators=[
        DataRequired(message='Please select the record date.')
    ])
    electricity_consumption_kwh = FloatField('Total Consumption (kWh)', validators=[
        DataRequired(message='Please enter the total electricity consumption in kWh.'),
        NumberRange(min=0.01, max=10000.0, message='Consumption must be a positive number greater than 0.')
    ])
    peak_consumption_kwh = FloatField('Peak Consumption (kWh)', default=0.0, validators=[
        NumberRange(min=0.0, message='Peak consumption cannot be negative.')
    ])
    off_peak_consumption_kwh = FloatField('Off-Peak Consumption (kWh)', default=0.0, validators=[
        NumberRange(min=0.0, message='Off-peak consumption cannot be negative.')
    ])
    appliance_usage_hours = FloatField('Appliance Usage Hours (hrs)', default=0.0, validators=[
        NumberRange(min=0.0, max=24.0, message='Appliance usage hours must be between 0 and 24 hours.')
    ])
    estimated_cost = FloatField('Estimated Cost (₦ - optional, auto-calculated if left blank)', validators=[
        Optional(),
        NumberRange(min=0.0, message='Cost cannot be negative.')
    ])
    is_synthetic = BooleanField('Mark as Synthetic / Demo Data')
    submit = SubmitField('Save Energy Record')


class PredictionForm(FlaskForm):
    """Form to request an ANN energy demand prediction."""
    prediction_date = DateField('Target Prediction Date', default=date.today, validators=[
        DataRequired(message='Please specify the target date for prediction.')
    ])
    appliance_usage_hours = FloatField('Expected Appliance Usage (Hours)', default=8.0, validators=[
        DataRequired(message='Please enter expected appliance usage hours.'),
        NumberRange(min=0.0, max=24.0, message='Usage hours must be between 0 and 24.')
    ])
    expected_peak_kwh = FloatField('Estimated Peak Hours Consumption (kWh)', default=4.5, validators=[
        NumberRange(min=0.0, message='Peak consumption cannot be negative.')
    ])
    expected_off_peak_kwh = FloatField('Estimated Off-Peak Hours Consumption (kWh)', default=3.5, validators=[
        NumberRange(min=0.0, message='Off-peak consumption cannot be negative.')
    ])
    recent_avg_kwh = FloatField('Recent Daily Average Baseline (kWh, optional)', default=8.0, validators=[
        Optional(),
        NumberRange(min=0.0, message='Baseline cannot be negative.')
    ])
    submit = SubmitField('Generate ANN Energy Prediction')


class CSVUploadForm(FlaskForm):
    """Form for administrators to batch-import historical energy data via CSV."""
    csv_file = FileField('Select CSV File', validators=[
        FileRequired(message='Please select a CSV file to upload.'),
        FileAllowed(['csv'], message='Only .csv files are supported.')
    ])
    user_id = SelectField('Assign Records To User', coerce=int, validators=[DataRequired()])
    is_synthetic = BooleanField('Mark imported records as Demo Data', default=False)
    submit = SubmitField('Upload & Process CSV')


class SystemSettingsForm(FlaskForm):
    """Form for administrators to modify system settings."""
    tariff_per_kwh = FloatField('Electricity Tariff (₦ / kWh)', validators=[
        DataRequired(message='Please specify the tariff rate.'),
        NumberRange(min=1.0, max=5000.0, message='Tariff rate must be positive.')
    ])
    low_consumption_threshold = FloatField('Low Consumption Threshold (kWh/day)', validators=[
        DataRequired(message='Please specify the low threshold.'),
        NumberRange(min=0.1, max=100.0, message='Must be positive.')
    ])
    moderate_consumption_threshold = FloatField('Moderate Consumption Threshold (kWh/day)', validators=[
        DataRequired(message='Please specify the moderate threshold.'),
        NumberRange(min=0.1, max=500.0, message='Must be positive.')
    ])
    submit = SubmitField('Save System Settings')

    def validate_moderate_consumption_threshold(self, field):
        if self.low_consumption_threshold.data and field.data <= self.low_consumption_threshold.data:
            raise ValidationError('Moderate threshold must be strictly greater than the Low threshold.')


class RecommendationForm(FlaskForm):
    """Form to manage recommendations."""
    title = StringField('Recommendation Title', validators=[
        DataRequired(message='Please provide a title.'),
        Length(min=3, max=150)
    ])
    message = TextAreaField('Detailed Advisory Message', validators=[
        DataRequired(message='Please provide the advisory message.'),
        Length(min=10, max=1000)
    ])
    consumption_level = SelectField('Applicable Consumption Level', choices=[
        ('all', 'All Users (General Advice)'),
        ('low', 'Low Consumption Tier'),
        ('moderate', 'Moderate Consumption Tier'),
        ('high', 'High Consumption Tier')
    ], default='all')
    is_active = BooleanField('Active', default=True)
    submit = SubmitField('Save Recommendation')


class UserEditForm(FlaskForm):
    """Form for admin to edit user details."""
    full_name = StringField('Full Name', validators=[
        DataRequired(),
        Length(min=2, max=100)
    ])
    email = StringField('Email Address', validators=[
        DataRequired(),
        Regexp(EMAIL_REGEX, message='Please enter a valid email address.')
    ])
    role = SelectField('Role', choices=[('resident', 'Resident'), ('admin', 'Administrator')])
    submit = SubmitField('Update User')


class ProfileUpdateForm(FlaskForm):
    """Form for users to update profile details and upload avatar image."""
    full_name = StringField('Full Name', validators=[
        DataRequired(message='Please provide your full name.'),
        Length(min=2, max=100)
    ])
    avatar = FileField('Profile Image / Avatar', validators=[
        Optional(),
        FileAllowed(['jpg', 'jpeg', 'png', 'webp', 'svg'], message='Only image files (.jpg, .jpeg, .png, .webp, .svg) are allowed.')
    ])
    submit = SubmitField('Save Profile Details')


class ChangePasswordForm(FlaskForm):
    """Form for users to reset / change their password."""
    current_password = PasswordField('Current Password', validators=[
        DataRequired(message='Please enter your current password.')
    ])
    new_password = PasswordField('New Password', validators=[
        DataRequired(message='Please enter your new password.'),
        Length(min=6, max=50, message='New password must be at least 6 characters long.')
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(message='Please confirm your new password.'),
        EqualTo('new_password', message='New passwords must match.')
    ])
    submit = SubmitField('Change Password')

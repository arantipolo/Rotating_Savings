from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Email, EqualTo

# Handles new user account creation with validation
# Ensures data integrity before saving to database
class RegistrationForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired()])      # User's full name
    email = StringField('Email', validators=[DataRequired(), Email()])      # Email must be valid format and cannot be empty
    password = PasswordField('Password', validators=[DataRequired()])       # Password input
    confirm_password = PasswordField('Confirm Password',
                                     validators=[DataRequired(), EqualTo('password')])      # Ensures user correctly confirms password entry

    submit = SubmitField('Register')        # Submit button for registration form

# Handles authentication input for existing users
class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')     # Optional feature to keep user logged in across sessions
    submit = SubmitField('Login')

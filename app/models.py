from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from datetime import datetime
from flask_login import UserMixin


# This model connects Users and Groups (many-to-many relationship)
# Each record represents:
# a user belonging to a group
# their payout position in that group
# whether they already received their payout
class GroupMember(db.Model):
    # Prevents duplicate membership (same user cannot join same group twice)
    __table_args__ = (
        db.UniqueConstraint('user_id', 'group_id', name='unique_user_group'),
    )
    id = db.Column(db.Integer, primary_key=True)

    # Foreign keys linking user to group relationship
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    payout_position = db.Column(db.Integer)     # Order in which user receives payout (assigned randomly)
    has_received = db.Column(db.Boolean, default=False)      # Tracks whether user already received their payout

    #this is for easy access in templates and routes
    user = db.relationship('User', back_populates='groups')
    group = db.relationship('Group', back_populates='members')

# Represents application users and handles authentication data
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # user identity fields
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)     # Timestamp for account creation

    groups = db.relationship('GroupMember', back_populates='user')

    # Tracks payments this user has made in different payout cycles
    payments_made = db.relationship('Payment', foreign_keys='Payment.payer_id', backref='payer')

    # Tracks payouts this user has received
    payouts_received = db.relationship('PayoutSchedule', foreign_keys='PayoutSchedule.recipient_id',
                                       backref='recipient')
    # this is a score to represent a user's reliability in making payments
    # default starts a 1.0 and can go up or down based on behaviour
    reliability_score =db.Column(db.Float, default=1.0)

    # Hash password before storing in database
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    # Compare entered password with stored hashed password
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):   # Defines how object are displayed for debugging purposes
        return f"<User {self.email}>"

# Represents a rotating savings group
class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    contribution_amount = db.Column(db.Float, nullable=False)      # Amount each member contributes per cycle
    payout_frequency_days = db.Column(db.Integer, default=14) # defines payout cycle frequency
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    members = db.relationship('GroupMember', back_populates='group', cascade="all, delete-orphan")      # All members in this group via GroupMember table
    payouts = db.relationship('PayoutSchedule', backref='group', lazy=True, cascade="all, delete-orphan")     # Payout schedule entries for this group
    is_payout_locked = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<Group {self.name}>"

# Represents when and who receives money in each cycle
class PayoutSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    payout_date = db.Column(db.Date, nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'))     # Who receives the payout in this cycle
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'))      # Group this payout belongs to
    payments = db.relationship('Payment', backref='payout', lazy=True)     # Payments linked to this payout cycle
    cycle_number = db.Column(db.Integer, nullable=False)  # This represents which cycle this payout to, example, 1st round, 2nd round, etc...

    def __repr__(self):
        return f"<Payout {self.payout_date}>"


# Tracks contributions made by users toward payouts
# Includes optional proof (screenshot upload)
class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    payer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # who made the payment
    payout_id = db.Column(db.Integer, db.ForeignKey('payout_schedule.id'), nullable=False)     # Which payout cycle this payment belongs to
    amount = db.Column(db.Float, nullable=False)
    proof_image = db.Column(db.String(255))   #proof of payment
    paid_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_on_time = db.Column(db.Boolean, default=True)  # This indicates if the payment was made before or on expected payout

    def __repr__(self):
        return f"<Payment {self.amount}>"


# Required for session management and authentication
from app import login

@login.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

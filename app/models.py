from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from datetime import datetime
from flask_login import UserMixin

class GroupMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'))
    payout_position = db.Column(db.Integer)
    has_received = db.Column(db.Boolean, default=False)

    user = db.relationship('User', back_populates='groups')
    group = db.relationship('Group', back_populates='members')

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    groups = db.relationship('GroupMember', back_populates='user')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.email}>"


class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    contribution_amount = db.Column(db.Float, nullable=False)
    payout_frequency_days = db.Column(db.Integer, default=14)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    members = db.relationship('GroupMember', back_populates='group')

    payouts = db.relationship('PayoutSchedule', backref='group', lazy=True)

    def __repr__(self):
        return f"<Group {self.name}>"

class PayoutSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    payout_date = db.Column(db.Date, nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'))

    payments = db.relationship('Payment', backref='payout', lazy=True)

    def __repr__(self):
        return f"<Payout {self.payout_date}>"

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    payer_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    payout_id = db.Column(db.Integer, db.ForeignKey('payout_schedule.id'))
    amount = db.Column(db.Float, nullable=False)
    proof_image = db.Column(db.String(255))
    paid_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Payment {self.amount}>"

from app import login

@login.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

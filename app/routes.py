from flask import Blueprint, render_template, redirect, url_for, flash, request, session, jsonify, abort
from flask_login import login_user, logout_user, login_required, current_user
from app.forms import RegistrationForm, LoginForm
from app.models import User, Group, GroupMember, PayoutSchedule, Payment
from app import db
from datetime import datetime, timedelta
import random

main = Blueprint('main', __name__)

# Randomly assigns payout positions to group members
# This determines the order each member receives payouts
def assign_payouts(group_id):
    members = GroupMember.query.filter_by(group_id=group_id).all()

    positions = list(range(1, len(members) + 1)) # Create sequential positions
    random.shuffle(positions)  # Shuffle to randomize payout order

    for member, pos in zip(members, positions):  # Assign each member a payout position
        member.payout_position = pos

    # Save changes to database
    db.session.commit()

# Generates payout dates for each member
def generate_payout_schedule(group_id):

    # prevent duplicate schedules if function is called again
    PayoutSchedule.query.filter_by(group_id=group_id).delete()
    db.session.commit()

    # Get all members in this group
    members = GroupMember.query.filter_by(group_id=group_id).all()

    # Get group details (needed for frequency)
    group = Group.query.get(group_id)

    # Use today's date as the starting point
    start_date = datetime.utcnow().date()

    # Loop through each member and assign a payout date
    for member in members:

        # payout_position determines when they receive payout
        # For example, if position 1 gets paid today, then position 2 will get paid in 14 days
        # position 3 will be at 28th day.
        payout_date = start_date + timedelta(
            days=group.payout_frequency_days * (member.payout_position - 1)
        )

        # Create a payout schedule entry
        payout = PayoutSchedule(
            payout_date=payout_date,
            recipient_id=member.user_id,
            group_id=group_id
        )

        db.session.add(payout)
    print(f"Created payout for user {member.user_id} on {payout_date}")
    # Save all payout schedules to database
    db.session.commit()

def build_breadcrumbs(*items):
    return [{"label": label, "url": url} for label, url in items]

# home page
@main.route('/')
def home():
    return render_template('home.html', breadcrumb=[{'name': 'Home', "url": None}])

# User dashboard showing all groups they belong to
@main.route('/dashboard')
@login_required
def dashboard():
    memberships = list(current_user.groups)  # already gives GroupMember objects
    breadcrumbs = [
        {"label": "Home", "url": url_for('main.home')},
        {"label": "Dashboard", "url": None}
    ]

    return render_template('dashboard.html', memberships=memberships,
                           breadcrumb=breadcrumbs
                           )

# Displays all available groups so users can browse and join
@main.route('/groups')
@login_required
def groups():
    all_groups = Group.query.all()
    breadcrumbs = [
        {"label": "Home", "url": url_for('main.home')},
        {"label": "Dashboard", "url": url_for('main.dashboard')},
        {"label": "Groups", "url": None}
    ]
    return render_template('groups.html', groups=all_groups, breadcrumb=breadcrumbs)

# Handles joining a group (prevents duplicate memberships)
@main.route('/join_group/<int:group_id>', methods=['POST'])
@login_required
def join_group(group_id):

    # check if user is already part of the group
    existing = GroupMember.query.filter_by(
        user_id=current_user.id,
        group_id=group_id
    ).first()

    if existing:
        flash("You already joined this group", "warning")
        return redirect(url_for('main.dashboard'))

    # add user to group
    membership = GroupMember(
        user_id=current_user.id,
        group_id=group_id
    )

    db.session.add(membership)
    db.session.commit()

    flash("Joined group successfully!", "success")
    return redirect(url_for('main.dashboard'))


@main.route('/generate_payouts/<int:group_id>', methods=['POST'])
@login_required
# this function is responsible for assigning and generating payout schedule
def generate_payouts(group_id):

    group = Group.query.get_or_404(group_id)

    # security check
    if group.owner_id != current_user.id:
        flash("You are not authorized to generate payouts for this group.", "warning")
        return redirect(url_for('main.dashboard'))

    assign_payouts(group_id)
    generate_payout_schedule(group_id)

    flash("Payout schedule generated!", "success")
    return jsonify({
        "success": True,
        "message": "Payout schedule generated"
    })


@main.route('/group_details/<int:group_id>')
@login_required
def group_details(group_id):

    group = Group.query.get_or_404(group_id)

    return render_template('group_details.html', group=group)


# Creates a new savings group and adds creator as first member
@main.route('/create_group', methods=['GET', 'POST'])
@login_required
def create_group():
    if request.method == 'POST':
        name = request.form.get('name')
        amount = request.form.get('amount')
        members = request.form.get('members')

        if not name or not amount:
            flash("Missing required fields", "danger")
            return redirect(url_for('main.create_group'))

        group = Group(
            name = name,
            contribution_amount=float(amount),
            owner_id = current_user.id
        )

        db.session.add(group)
        db.session.commit()

        # automatically add creator to the group
        membership = GroupMember(
            user_id = current_user.id,
            group_id = group.id,
            payout_position=None
        )

        db.session.add(membership)
        db.session.commit()

        flash("Group created", "success")
        return redirect(url_for('main.dashboard'))

    bredcrumbs = [
        {"label": "Home", "url": url_for('main.home')},
        {"label": "Dashboard", "url": url_for('main.dashboard')},
        {"label": "Create Group", "url": None}
    ]

    return render_template(
        'create_group.html', breadcrumb=bredcrumbs)

@main.route("/delete_group/<int:group_id>", methods=["POST"])
@login_required
def delete_group(group_id):
    print("DELETE HIT") # debug
    group = Group.query.get_or_404(group_id)

    #security check
    if group.owner_id != current_user.id:
        abort(403)

    # force detach relationships first
    GroupMember.query.filter_by(group_id=group.id).delete()
    PayoutSchedule.query.filter_by(group_id=group_id).delete()

    db.session.delete(group)
    db.session.commit()
    db.session.expire_all()

    return jsonify({"Success": True})


#user registration flow
@main.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()

    if form.validate_on_submit():
        user = User(
            full_name=form.full_name.data,
            email=form.email.data,
        )
        user.set_password(form.password.data)

        db.session.add(user)
        db.session.commit()

        flash('Registration successful! Please log in.')
        return redirect(url_for('main.login'))
    breadcrumbs = [
        {"label": "Home", "url": url_for('main.home')},
        {"label": "Register", "url": None}
    ]
    return render_template('register.html', form=form, breadcrumb=breadcrumbs)

# Login with clear error handling for missing user or wrong password
@main.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:  # Prevent logged-in users from seeing login page again
        return redirect(url_for('main.dashboard'))

    form = LoginForm()

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()

        # If email does not exist in system
        if not user:
            flash("No account found with this email. Please register.", "danger")
            return redirect(url_for('main.register'))

        # If password is incorrect
        if not user.check_password(form.password.data):
            flash("Incorrect password. Please try again.", "danger")
            return redirect(url_for('main.login'))

        # successful login
        login_user(user, remember=form.remember.data)
        flash("You have been logged in.", "success")

        next_page = request.args.get('next')
        return redirect(next_page) if next_page else redirect(url_for('main.dashboard'))
    breadcrumb = [
        {"label": "Home", "url": url_for('main.home')},
        {"label": "Login", "url": None}
    ]
    return render_template('login.html', form=form, breadcrumb=breadcrumb)


# logout and clears session and forces cookie reset
@main.route('/logout')
@login_required
def logout():

    logout_user()
    session.clear()

    # force cookie reset
    # response = redirect(url_for('main.login'))
    # response.delete_cookie('session')
     #return response
    # response.set_cookie('session', '', expires=0)
    flash('You have been logged out.', 'success')

    return redirect(url_for('main.login'))
from flask import Blueprint, render_template, redirect, url_for, flash, request, session, jsonify, abort, current_app
from flask_login import login_user, logout_user, login_required, current_user
from wtforms.validators import equal_to

from app.forms import RegistrationForm, LoginForm
from app.models import User, Group, GroupMember, PayoutSchedule, Payment
from app import db
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import random, os


main = Blueprint('main', __name__)

@main.route('/debug-session')
def debug_session():
    return {
        "authenticated": current_user.is_authenticated,
        "user_id": current_user.get_id()
    }

# Assign payout positions using a weighted random approach.
#instead of assigning pure randomness, this method look at how reliable each user based on past behaviour (ontime or late payment)
# Also reduces priority for users who have already received payouts
def assign_payouts(group_id):

    members = GroupMember.query.filter_by(group_id=group_id).all() # get all group members

    scored_members = []  # this list will store tuples of (member, calculated_score)

    for member in members:
        user = member.user # get the actual user object linked to this membership

        # This value increases if user pays on time, otherwise decreases if late
        reliability = user.reliability_score if user.reliability_score else 1.0

        # fairness adjustment
        #if user already received payout before, reduce their priority
        # This prevents the same user from being early in the payout order
        if member.has_received:
            fairness_multiplier = 0.5
        else:
            fairness_multiplier = 1.0

        # Include random factor
        random_factor = random.uniform(0.8, 1.2)

        #final score calculation, the higher the score, the earlier the user is in the payout order
        priority_score = reliability * fairness_multiplier * random_factor

        #store the results for sorting later
        scored_members.append({member, priority_score})

    def get_score(item): # here, item is a tuple (member, score)
        return item[1]   # return the score which is the second value from the tuple

    # Sort members based on score (highest first)
    scored_members.sort(key=get_score, reverse=True)

    # Assign payout positions based on sorted order
    for index, (member, score) in enumerate(scored_members):

        #position starts at 1
        member.payout_position = index + 1
    #save all updates to the database
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

#helper function to validate uploaded file types for payment proof uploads
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in {"png", "jpg", "jpeg", "gif"}

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


# Handles uploading proof of payment (image file) for a specific payment record
@main.route("/upload_proof/<int:payment_id>", methods=["POST"])
@login_required
def upload_proof(payment_id):

    # Get the payment record or fail if it doesn't exist
    payment = Payment.query.get_or_404(payment_id)

    # Retrieve uploaded file from request
    file = request.files.get("file")

    # Basic validation: make sure a file was actually uploaded
    if not file or file.filename == "":
        return jsonify({"error": "No file provided"}), 400

    # Security check: only allow image file types (prevents malicious uploads)
    if not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type"}), 400

    # Secure filename to prevent path injection or weird file names
    filename = secure_filename(file.filename)

    # Build full file path using configured upload folder
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)

    # Save file to server
    file.save(path)

    # Store filename in database so we can display/download later
    payment.proof_image = filename
    db.session.commit()

    # Return success response for frontend (AJAX)
    return jsonify({"success": True, "filename": filename})

@main.route("/submit_payment/<int:payout_id>", methods=["POST"])
@login_required
def submit_payment(payout_id):
    # This creates a Payment record and evaluates whether the payment
    #  was made on time, which will later affect the user's reliability score.
    payout = PayoutSchedule.query.get_or_404(payout_id)

    # This prevents paying yourself
    if payout.recipient_id == current_user.id:
        return jsonify({"error": "You cannot pay yourself"}), 400

    # Check if user already submitted payment for this payout
    existing_payment = Payment.query.filter_by(
        payer_id=current_user.id,
        payout_id=payout.id
    ).first()

    if existing_payment:
        return jsonify({"error": "Payment already submitted"}), 400

    # This determines if payment is made on time
    today = datetime.utcnow().date()
    is_on_time = today <= payout.payout_date

    #This creates payment record
    payment = Payment(
        payer_id = current_user.id,
        payout_id = payout.id,
        amount = payout.group.contribution_amount,
        is_on_time = is_on_time
    )

    db.session.add(payment)

    #reliability score adjustment
    if is_on_time:
        #reward consistency
        current_user.reliability_score += 0.05
    else:
        # Penalize lateness
        current_user.reliability_score -= 0.1

    # clamp values so they dont go crazy
    current_user.reliability_score = max(0.5, min(current_user.reliability_score, 2.0))

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Payment submitted successfully",
        "on_time": is_on_time
    })


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

        pwd = user.check_password(form.password.data)
        confirmPassword = form.confirm_password.data
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
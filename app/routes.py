from flask import Blueprint, render_template, redirect, url_for, flash, request, session, jsonify, abort, current_app, send_from_directory
from flask_login import login_user, logout_user, login_required, current_user
from wtforms.validators import equal_to

from app.forms import RegistrationForm, LoginForm
from app.models import User, Group, GroupMember, PayoutSchedule, Payment
from app import db
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import random, os, uuid


main = Blueprint('main', __name__)

@main.route('/debug-session')
@login_required
def debug_session():
    return {
        "authenticated": current_user.is_authenticated,
        "user_id": current_user.get_id()
    }

def current_user_membership(group_id):
    # Finds the membership record for the logged-in user
    # This stops users from viewing or changing groups they do not belong to
    return GroupMember.query.filter_by(
        user_id=current_user.id,
        group_id=group_id
    ).first()

def require_group_member(group_id):
    # Blocks access when a user tries to open a group by guessing its URL id
    membership = current_user_membership(group_id)
    if not membership:
        abort(403)
    return membership

def require_group_owner(group):
    # Only the group creator should control payouts, locks, and destructive actions
    if group.owner_id != current_user.id:
        abort(403)

# Assign payout positions using a weighted random approach.
#instead of assigning pure randomness, this method look at how reliable each user based on past behaviour (ontime or late payment)
# Also reduces priority for users who have already received payouts
def assign_payouts(group_id):
    # get all group members and fix ordering.
    members = GroupMember.query.filter_by(group_id=group_id)\
        .order_by(GroupMember.payout_position.asc())\
        .all()

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
        scored_members.append((member, priority_score))

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
            group_id=group_id,
            cycle_number=member.payout_position
        )

        db.session.add(payout)
    print(f"Created payout for user {member.user_id} on {payout_date}")
    # Save all payout schedules to database
    db.session.commit()

#helper function to validate uploaded file types for payment proof uploads
# def allowed_file(filename):
#     return "." in filename and filename.rsplit(".", 1)[1].lower() in {"png", "jpg", "jpeg", "gif", "pdf"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in current_app.config["ALLOWED_EXTENSIONS"]
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
    group = Group.query.get_or_404(group_id)

    # check if user is already part of the group
    existing = GroupMember.query.filter_by(
        user_id=current_user.id,
        group_id=group.id
    ).first()

    if existing:
        flash("You already joined this group", "warning")
        return redirect(url_for('main.dashboard'))

    # add user to group
    membership = GroupMember(
        user_id=current_user.id,
        group_id=group.id
    )

    db.session.add(membership)
    db.session.commit()

    flash("Joined group successfully!", "success")
    return redirect(url_for('main.dashboard'))


@main.route('/generate_payouts/<int:group_id>', methods=['POST'])
@login_required
def generate_payouts(group_id):

    print("\n========== GENERATE PAYOUTS START ==========")
    print("[DEBUG] Group ID:", group_id)

    # get the group or fail if it doesn't exist
    group = Group.query.get_or_404(group_id)
    require_group_owner(group)

    print("[DEBUG] GROUP OBJECT:", group)
    print("[DEBUG] GROUP ID TYPE:", type(group.id))
    print("[DEBUG] GROUP ID VALUE:", group.id)

    if group.is_payout_locked:
        return jsonify({
            "success": False,
            "error": "Payout already locked!"
        }), 403

    # get members in stable order
    from app.services.payout_services import generate_payout_order  # include payout_services

    members = generate_payout_order(group)  # get properly ordered members
    print("AFTER ORDER:", [m.user.full_name for m in members])
    print("[DEBUG] Members found:", len(members))

    # prevent duplicate payout schedules
    existing = PayoutSchedule.query.filter_by(group_id=group.id).all()

    print("[DEBUG] Existing payouts:", len(existing))

    if existing:
        print("[BLOCKED] Payouts already exist for this group")
        #return jsonify({"error": "Payouts already generated!"}), 400
        PayoutSchedule.query.filter_by(group_id=group.id).delete()
        db.session.commit()

    payouts = []

    # create payout schedule
    for i, recipient in enumerate(members):
        # we calculate payout date based on position in the cycle
        # cycle 0 = today, cycle 1 = +14 days
        payout_date = datetime.utcnow().date() + timedelta(days=group.payout_frequency_days * i)

        payout = PayoutSchedule(
            group_id = group.id,
            recipient_id = recipient.user_id,
            cycle_number = i + 1,
            payout_date = payout_date  # Every payout must have a date, otherwise sqlite will reject it
        )

        db.session.add(payout)

        recipient.payout_position = i + 1

        print(f"[CREATE] payout cycle={i + 1}, user={recipient.user_id}")
        payouts.append(payout)

    db.session.flush()  # ensures payout.id exists

    # create payment obligations
    for payout in payouts:

        print(f"[PAYMENTS] building for payout {payout.id}")

        for member in members:

            # skip recipient (they don't pay themselves)
            if member.user_id == payout.recipient_id:
                continue

            payment = Payment(
                payer_id=member.user_id,  #  each payout belongs to a specific payout cycle
                payout_id=payout.id,        # links payment to the payout cycle it contributes to
                amount=group.contribution_amount       # how much each member contributes
            )
            print(f"[PAYMENT CREATED] payer={member.user_id}, payout={payout.id}, amount={group.contribution_amount}")

            db.session.add(payment)

            print(f"[PAYMENT] payer={member.user_id} → payout={payout.id}")

    print("\n[DEBUG] FINAL PAYOUT CHECK:")
    for p in payouts:
        print(f"  payout_id={p.id}, user={p.recipient_id}, date={p.payout_date}")

    db.session.commit()

    print("======= GENERATE PAYOUTS END =======\n")

    return jsonify({
        "success": True,
        "total_payouts": len(payouts),
        "total_members": len(members)
    }), 200


@main.route('/toggle_lock/<int:group_id>', methods=['POST'])
@login_required
def toggle_lock(group_id):

    group =Group.query.get_or_404(group_id)

    if group.owner_id != current_user.id:
        return jsonify({"Error": "Unauthorized!"}), 403
    #toogle the lock
    group.is_payout_locked = not group.is_payout_locked

    db.session.commit()

    print(f"[LOCK TOGGLED] Group {group.id} -> {group.is_payout_locked}")

    return jsonify({
        "group_id": group_id,
        "is_payout_locked": group.is_payout_locked
    }), 200

@main.route('/reset_payouts/<int:group_id>', methods=['POST'])
@login_required
def reset_payouts(group_id):

    print("\n========== RESET PAYOUTS ==========")
    print("[RESET] Group ID:", group_id)

    group = Group.query.get_or_404(group_id)

    # only group owner can reset everything
    if group.owner_id != current_user.id:
        print("[BLOCKED] Not owner")
        return jsonify({"error": "Not authorized"}), 403

    # delete payments through payouts (
    payout_ids = [p.id for p in PayoutSchedule.query.filter_by(group_id=group_id).all()]

    print("[DEBUG] Payout IDs:", payout_ids)

    deleted_payments = 0
    if payout_ids:
        deleted_payments = Payment.query.filter(Payment.payout_id.in_(payout_ids)).delete(synchronize_session=False)

    print("[RESET] Payments deleted:", deleted_payments)

    # delete payouts
    deleted_payouts = PayoutSchedule.query.filter_by(group_id=group_id).delete()

    print("[RESET] Payouts deleted:", deleted_payouts)

    # reset member state
    members = GroupMember.query.filter_by(group_id=group_id).all()
    for m in members:
        m.payout_position = None
        m.has_received = False

    db.session.commit()

    print("[RESET COMPLETE]\n")

    return jsonify({
        "success": True,
        "message": "Reset successful"
    }), 200


@main.route("/mark_payout/<int:payout_id>/<int:user_id>", methods=['POST'])
@login_required
def mark_payout(payout_id, user_id):
    # This route is used by the group owner to confirm that a payout has been completed for a specific user
    # It connects the payout cycle with user status updates and esures fairness tracking works corectly

    payout = PayoutSchedule.query.get_or_404(payout_id) # Get payout record

    group = Group.query.get_or_404(payout.group_id)  # get the group for security check

    if group.owner_id != current_user.id:  #Only group owner can mark a payout as completed
        abort(403)   # prevents unauthorized access

    # Find the group membership record for this user
    member = GroupMember.query.filter_by(
        user_id=user_id,
        group_id=group.id
    ).first()

    if not member:
        return jsonify({"error": "Member not found"}), 404

    member.has_received = True  # This marks that this member has received their payout

    if hasattr(member.user, "reliability_score") and member.user.reliability_score:
        member.user.reliability_score += 0.1
    else:
        member.user.reliability_score = 1.0

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Payout marked as completed"
    })


@main.route('/group_details/<int:group_id>')
@login_required
def group_details(group_id):
    # Get group
    group = Group.query.get_or_404(group_id)
    require_group_member(group.id)

    # Members ordered correctly
    members = GroupMember.query.filter_by(group_id=group_id) \
        .order_by(GroupMember.payout_position.asc()) \
        .all()

    # Payouts ordered
    payouts = PayoutSchedule.query \
        .filter_by(group_id=group_id) \
        .order_by(PayoutSchedule.payout_date.asc()) \
        .all()

    #  map payout by recipient_id
    payout_map = {p.recipient_id: p for p in payouts}

   # print("Payout Map:", payout_map)

    # map payments by (payout_id, payer_id)
    payments = Payment.query.join(PayoutSchedule).filter(
        PayoutSchedule.group_id == group_id
    ).all()

    payment_map = {
        (p.payout_id, p.payer_id): p
        for p in payments
    }

   # print("Payment Map:", payment_map)

    # Find current payout (next upcoming or active)
    today = datetime.utcnow().date()

    current_payout = PayoutSchedule.query.filter(
        PayoutSchedule.group_id == group_id,
        PayoutSchedule.payout_date >= today
    ).order_by(PayoutSchedule.payout_date.asc()).first()

    return render_template(
        "group_details.html",
        group=group,
        members=members,
        payouts=payouts,
        payout_map=payout_map,
        payment_map=payment_map,
        current_payout=current_payout
    )

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

print("ROUTES LOADED")


# Handles uploading proof of payment (image file) for a specific payment record
@main.route("/upload_proof/<int:payment_id>", methods=["POST"])
@login_required
def upload_proof(payment_id):

    print("\n----[UPLOAD] START----]")
    print("[UPLOAD] Payment ID:", payment_id)

    # Find the payment record for this user and payout
    # This ensures users can only upload for their own payment
    payment = Payment.query.filter_by(
        id = payment_id,
        payer_id=current_user.id
    ).first()

    print(f"[DEBUG] Trying to find payment: payment_id={payment_id}, payer_id={current_user.id}")
    #payment = Payment.query.get(payment_id)

    if not payment:
        print("[UPLOAD] ERROR: Payment not found")
        return jsonify({"error": "Payment record not found"}), 404

    print("[UPLOAD] current_user.id:", current_user.id)
    print("[UPLOAD] payment.payer_id:", payment.payer_id)

    if payment.payer_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    require_group_member(payment.payout.group_id)

    # get the file from request
    file = request.files.get("file")

    print("[UPLOAD] File received:", file)

    if not file:
        print("[UPLOAD] ERROR: No file in request")
        return jsonify({"error": "No file received"}), 400

    if file.filename == "":
        print("[UPLOAD] ERROR: Empty filename")
        return jsonify({"error": "No selected file"}), 400

    if not allowed_file(file.filename):
        print("[UPLOAD] ERROR: Invalid file type")
        return jsonify({"error": "Invalid file type. Only PNG, JPG, JPEG, GIF, and PDF are allowed."}), 400

    # secure file name to prevent weird chars or path attacks
    # unique prefix keeps two users from overwriting files with the same name
    filename = secure_filename(file.filename)
    filename = f"{payment.id}-{uuid.uuid4().hex}-{filename}"

    # build the path to upload folder
    os.makedirs(current_app.config["UPLOAD_FOLDER"], exist_ok=True)
    upload_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)

    try:
        # Save file to disk
        file.save(upload_path)
    except Exception as e:
        print(f"[UPLOAD] ERROR: {e}")
        return jsonify({"error": "Failed to save the file."}), 500

    #Store filename in database
    payment.proof_image = filename

    member = GroupMember.query.filter_by(
        user_id = payment.payer_id,
        group_id = payment.payout.group_id
    ).first()

    if member:
        member.has_received = True

    db.session.commit()

    print("[UPLOAD] File saved + DB updated")

    return jsonify({
        "success": True,
        "message": "Upload Successful",
        "filename": filename
    })


@main.route("/submit_payment/<int:payout_id>", methods=["POST"])
@login_required
def submit_payment(payout_id):
    # This creates a Payment record and evaluates whether the payment
    #  was made on time, which will later affect the user's reliability score.
    payout = PayoutSchedule.query.get_or_404(payout_id)
    require_group_member(payout.group_id)

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

#this exposes the upload directory to the browser
@main.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)

#user registration flow
@main.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()

    if form.validate_on_submit():
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            flash("An account with this email already exists. Please log in.", "warning")
            return redirect(url_for('main.login'))

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

    # Sends the user home after logout and clears login cookies
    # This also removes remember-me login so the user cannot be silently signed back in
    response = redirect(url_for('main.home'))
    response.delete_cookie(current_app.config.get("SESSION_COOKIE_NAME", "session"))
    response.delete_cookie(current_app.config.get("REMEMBER_COOKIE_NAME", "remember_token"))

    return response


# https://flask.palletsprojects.com/en/stable/quickstart/#routing

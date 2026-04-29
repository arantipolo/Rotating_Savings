import random
from app.models import GroupMember, Payment, PayoutSchedule
from app import db

def generate_payout_order(group):
    # Generates payout order ased on fairness and reliability.
    # This avoids always placing the same users early, and includes randomness to keep it fair

    members = GroupMember.query.filter_by(group_id=group.id).all()
    random.shuffle(members)

    scored_members = []   #scoring list

    for member in members:
        user = member.user

        reliability = user.reliability_score or 1.0

        fairness_penalty = 0.5 if member.has_received else 1.0

        randomness = random.uniform(0.8, 1.2) # keeps system from being too predictable

        priority_score = (reliability * fairness_penalty) * randomness

        scored_members.append((member, priority_score))

    def get_score(item): # item is a tuple (member, score)
        return item[1]   # access and return the score

    # Sort members based on score, highest score goes first
    scored_members.sort(key=get_score, reverse=True)

    #assign payout positions
    ordered_members = []

    for index, (member, score) in enumerate(scored_members):
        member.payout_position = index + 1
        ordered_members.append(member)

    db.session.commit()

    return ordered_members

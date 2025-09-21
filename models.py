# models.py
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# association table for group members
group_members = db.Table(
    'group_members',
    db.Column('group_id', db.Integer, db.ForeignKey('groups.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True)
)

@dataclass
class User(db.Model):
    __tablename__ = 'users'
    id: int = db.Column(db.Integer, primary_key=True)
    name: str = db.Column(db.String(120), nullable=False)

@dataclass
class Group(db.Model):
    __tablename__ = 'groups'
    id: int = db.Column(db.Integer, primary_key=True)
    name: str = db.Column(db.String(140), nullable=False)
    users = db.relationship('User', secondary=group_members, backref='groups')

@dataclass
class Expense(db.Model):
    __tablename__ = 'expenses'
    id: int = db.Column(db.Integer, primary_key=True)
    group_id: int = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    payer_id: int = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount: float = db.Column(db.Float, nullable=False)
    description: str = db.Column(db.String(300), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    group = db.relationship('Group', backref='expenses')
    payer = db.relationship('User')

# utility: compute net balances for a group
def compute_net_balances(group: Group) -> Dict[int, float]:
    """
    Return map user_id -> net balance.
    Positive means the user should receive money; negative means they owe.
    """
    members = group.users
    if not members:
        return {}

    # start with zeros
    net = {u.id: 0.0 for u in members}

    # total each expense split equally among all group members
    for e in group.expenses:
        split = e.amount / len(members)
        # payer receives the full amount
        net[e.payer_id] += e.amount - split  # payer's net increases by (amount - their share)
        # every member (including payer) owes split; subtract split from each
        for m in members:
            net[m.id] -= split if m.id != e.payer_id else 0.0  # payer already accounted above

    # simpler approach: compute total paid per user, total owed per user, net = paid - owed
    # To be safe, recompute using that:
    totals_paid = {u.id: 0.0 for u in members}
    totals_owed = {u.id: 0.0 for u in members}
    for e in group.expenses:
        totals_paid[e.payer_id] += e.amount
        per = e.amount / len(members)
        for m in members:
            totals_owed[m.id] += per
    net = {uid: round(totals_paid[uid] - totals_owed[uid], 2) for uid in totals_paid}
    return net

def simplify_debts(net: Dict[int, float]) -> List[Tuple[int,int,float]]:
    """
    Greedy settlement:
    net: user_id -> balance (positive receive, negative owes)
    Returns list of (from_id, to_id, amount)
    """
    # convert to lists
    creditors = []
    debtors = []
    for uid, bal in net.items():
        if round(bal,2) > 0:
            creditors.append([uid, round(bal,2)])
        elif round(bal,2) < 0:
            debtors.append([uid, round(-bal,2)])  # store positive owed amount

    creditors.sort(key=lambda x: x[1], reverse=True)  # largest creditor first
    debtors.sort(key=lambda x: x[1], reverse=True)    # largest debtor first

    settlements = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        debtor_id, debt_amt = debtors[i]
        cred_id, cred_amt = creditors[j]
        amt = min(debt_amt, cred_amt)
        settlements.append((debtor_id, cred_id, round(amt,2)))
        debtors[i][1] -= amt
        creditors[j][1] -= amt
        if abs(debtors[i][1]) < 0.01:
            i += 1
        if abs(creditors[j][1]) < 0.01:
            j += 1
    return settlements

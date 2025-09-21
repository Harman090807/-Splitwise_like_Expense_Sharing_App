# app.py
from flask import Flask, jsonify, request, abort
from models import db, User, Group, Expense, compute_net_balances, simplify_debts
import os

def create_app(db_path='sqlite:///expenses.db'):
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_path
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    @app.route('/api/users', methods=['POST'])
    def create_user():
        data = request.json or {}
        name = data.get('name')
        if not name:
            return jsonify({'error': 'name required'}), 400
        u = User(name=name)
        db.session.add(u)
        db.session.commit()
        return jsonify({'id': u.id, 'name': u.name}), 201

    @app.route('/api/groups', methods=['POST'])
    def create_group():
        data = request.json or {}
        name = data.get('name')
        member_ids = data.get('members', [])
        if not name:
            return jsonify({'error':'name required'}), 400
        g = Group(name=name)
        db.session.add(g)
        # attach members
        if member_ids:
            users = User.query.filter(User.id.in_(member_ids)).all()
            g.users = users
        db.session.commit()
        return jsonify({'id': g.id, 'name': g.name}), 201

    @app.route('/api/groups/<int:group_id>/add_member', methods=['POST'])
    def add_member(group_id):
        data = request.json or {}
        uid = data.get('user_id')
        g = Group.query.get_or_404(group_id)
        u = User.query.get_or_404(uid)
        if u not in g.users:
            g.users.append(u)
            db.session.commit()
        return jsonify({'ok': True})

    @app.route('/api/groups/<int:group_id>/expenses', methods=['POST'])
    def add_expense(group_id):
        data = request.json or {}
        payer_id = data.get('payer_id')
        amount = float(data.get('amount',0))
        desc = data.get('description','')
        g = Group.query.get_or_404(group_id)
        # validation: payer must be member
        if not any(u.id == payer_id for u in g.users):
            return jsonify({'error':'payer not in group'}), 400
        exp = Expense(group_id=group_id, payer_id=payer_id, amount=amount, description=desc)
        db.session.add(exp)
        db.session.commit()
        return jsonify({'id': exp.id}), 201

    @app.route('/api/groups/<int:group_id>/balances', methods=['GET'])
    def balances(group_id):
        g = Group.query.get_or_404(group_id)
        net = compute_net_balances(g)
        return jsonify(net)

    @app.route('/api/groups/<int:group_id>/settle', methods=['GET'])
    def settle(group_id):
        g = Group.query.get_or_404(group_id)
        net = compute_net_balances(g)
        settlements = simplify_debts(net)
        # attach user names
        result = []
        for frm, to, amt in settlements:
            result.append({
                'from_id': frm,
                'to_id': to,
                'amount': amt
            })
        return jsonify(result)

    @app.route('/api/groups/<int:group_id>', methods=['GET'])
    def group_detail(group_id):
        g = Group.query.get_or_404(group_id)
        return jsonify({
            'id': g.id,
            'name': g.name,
            'members': [{'id': u.id, 'name': u.name} for u in g.users],
            'expenses': [{'id': e.id, 'payer_id': e.payer_id, 'amount': e.amount, 'description': e.description} for e in g.expenses]
        })

    return app

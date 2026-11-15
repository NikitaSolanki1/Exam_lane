from flask import Blueprint, request, render_template, redirect, url_for, session
from models import db, Account

access_bp = Blueprint('access', __name__)


@access_bp.route('/sign_in', methods=['GET', 'POST'])
def sign_in():
    if request.method == 'POST':
        mail = request.form['email']
        pin = request.form['password']
        person = Account.query.filter_by(email=mail).first()

        if not person or person.password != pin:
            return render_template('access/sign_in.html', msg='Wrong email or password')

        if not person.active_flag:
            return render_template('access/sign_in.html', msg='This account is blocked.')

        if person.role == 'marker' and not person.verified_flag:
            return render_template('access/sign_in.html', msg='Wait for admin approval.')

        session['uid'] = person.id
        session['role'] = person.role

        if person.role == 'admin':
            return redirect(url_for('control.control_home'))
        if person.role == 'marker':
            return redirect(url_for('marker.marker_home'))
        if person.role == 'learner':
            return redirect(url_for('learner.learner_home'))

        return render_template('access/sign_in.html', msg='Unknown role')

    return render_template('access/sign_in.html')


@access_bp.route('/join', methods=['GET', 'POST'])
def join():
    if request.method == 'POST':
        display_name = request.form['display_name']
        login_name = request.form['login_name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']

        if role not in ('learner', 'marker'):
            return render_template('access/join.html', msg='Pick learner or marker.')

        if Account.query.filter_by(email=email).first():
            return render_template('access/join.html', msg='Email already used. Please sign in.')

        ok = True
        if role == 'marker':
            ok = False

        row = Account(
            display_name=display_name,
            login_name=login_name,
            email=email,
            password=password,
            role=role,
            verified_flag=ok,
            active_flag=True
        )
        db.session.add(row)
        db.session.commit()
        return redirect(url_for('access.sign_in'))

    return render_template('access/join.html')

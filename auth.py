from flask import Blueprint, request, render_template, redirect, url_for, session
from models import db, User

auth_blueprint = Blueprint('auth', __name__)


@auth_blueprint.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if not user or user.password != password:
            return render_template('Authentication/login.html', error='Wrong email or password')

        if not user.is_active:
            return render_template('Authentication/login.html', error='This account is blocked.')

        if user.account_type == 'examiner' and not user.approval_status:
            return render_template('Authentication/login.html', error='Wait for admin approval.')

        session['user_id'] = user.id
        session['account_type'] = user.account_type

        if user.account_type == 'admin':
            return redirect(url_for('admin_routes.admin_dashboard'))
        if user.account_type == 'examiner':
            return redirect(url_for('examiner_routes.examiner_dashboard'))
        if user.account_type == 'student':
            return redirect(url_for('student_routes.student_dashboard'))

        return render_template('Authentication/login.html', error='Unknown account type')

    return render_template('Authentication/login.html')


@auth_blueprint.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form['full_name']
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        account_type = request.form['account_type']

        if account_type not in ('student', 'examiner'):
            return render_template('Authentication/register.html', error='Choose student or examiner.')

        if User.query.filter_by(email=email).first():
            return render_template('Authentication/register.html', error='Email already used. Please login.')

        approved = True
        if account_type == 'examiner':
            approved = False

        user = User(
            full_name=full_name,
            username=username,
            email=email,
            password=password,
            account_type=account_type,
            approval_status=approved,
            is_active=True
        )
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('auth.login'))

    return render_template('Authentication/register.html')

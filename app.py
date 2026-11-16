from flask import Flask, render_template, redirect, url_for, session
from models import db, User
from auth import auth_blueprint
from admin_routes import admin_blueprint
from examiner_routes import examiner_blueprint
from student_routes import student_blueprint

app = Flask(__name__)
app.secret_key = 'examlane_secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///examlane.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.register_blueprint(auth_blueprint, url_prefix='/auth')
app.register_blueprint(admin_blueprint, url_prefix='/admin_routes')
app.register_blueprint(examiner_blueprint, url_prefix='/examiner_routes')
app.register_blueprint(student_blueprint, url_prefix='/student_routes')

db.init_app(app)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.pop('user_id', None)
    session.pop('account_type', None)
    return redirect(url_for('index'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if User.query.filter_by(email='admin@examlane.in').first() is None:
            admin = User(
                full_name='ExamLane Admin',
                username='admin',
                email='admin@examlane.in',
                password='lane_admin_2026',
                account_type='admin',
                approval_status=True,
                is_active=True
            )
            db.session.add(admin)
            db.session.commit()
    app.run(debug=True, port=5002, use_reloader=False)

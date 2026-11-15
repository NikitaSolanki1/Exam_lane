from flask import Flask, render_template, redirect, url_for, session
from models import db, Account
from access import access_bp
from control import control_bp
from marker import marker_bp
from learner import learner_bp

app = Flask(__name__)
app.secret_key = 'examlane_secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///examlane.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.register_blueprint(access_bp, url_prefix='/access')
app.register_blueprint(control_bp, url_prefix='/control')
app.register_blueprint(marker_bp, url_prefix='/marker')
app.register_blueprint(learner_bp, url_prefix='/learner')

db.init_app(app)


@app.route('/')
def home_page():
    return render_template('index.html')


@app.route('/sign_out', methods=['GET', 'POST'])
def sign_out():
    session.pop('uid', None)
    session.pop('role', None)
    return redirect(url_for('home_page'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if Account.query.filter_by(email='admin@examlane.in').first() is None:
            boss = Account(
                display_name='ExamLane Admin',
                login_name='lane_admin',
                email='admin@examlane.in',
                password='lane_admin_2026',
                role='admin',
                verified_flag=True,
                active_flag=True
            )
            db.session.add(boss)
            db.session.commit()
    app.run(debug=True, port=5002, use_reloader=False)

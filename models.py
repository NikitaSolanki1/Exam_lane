from flask_sqlalchemy import SQLAlchemy
from datetime import date

db = SQLAlchemy()


class Account(db.Model):
    __tablename__ = 'account'
    id = db.Column(db.Integer, primary_key=True)
    display_name = db.Column(db.String(100), nullable=False)
    login_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), nullable=False, unique=True)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin / marker / learner
    active_flag = db.Column(db.Boolean, default=True)
    verified_flag = db.Column(db.Boolean, default=True)


class MarkerBio(db.Model):
    __tablename__ = 'marker_bio'
    id = db.Column(db.Integer, primary_key=True)
    dept = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    office = db.Column(db.String(100), nullable=False)
    years = db.Column(db.String(20), default='0')
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False, unique=True)


class LearnerBio(db.Model):
    __tablename__ = 'learner_bio'
    id = db.Column(db.Integer, primary_key=True)
    roll_no = db.Column(db.String(30), unique=True)
    phone = db.Column(db.String(20), nullable=False)
    home_address = db.Column(db.String(100), nullable=False)
    batch_year = db.Column(db.String(100), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False, unique=True)


class Subject(db.Model):
    __tablename__ = 'subject'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False)
    name = db.Column(db.String(50), nullable=False)
    summary = db.Column(db.String(200), nullable=False)
    weeks = db.Column(db.String(20), nullable=False)
    state = db.Column(db.String(20), default='Active')


class Assessment(db.Model):
    __tablename__ = 'assessment'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    summary = db.Column(db.String(200), nullable=False)
    kind = db.Column(db.String(40), default='Assessment')
    hold_date = db.Column(db.Date, nullable=False)
    minutes = db.Column(db.Integer, nullable=False)
    total_marks = db.Column(db.Integer, default=100)

    slot_from = db.Column(db.Date, nullable=False)
    slot_until = db.Column(db.Date, nullable=False)
    book_from = db.Column(db.Date, nullable=False)
    book_until = db.Column(db.Date, nullable=False)

    phase = db.Column(db.String(30), default='Draft')
    slot_open = db.Column(db.Boolean, default=False)
    book_open = db.Column(db.Boolean, default=False)
    result_live = db.Column(db.Boolean, default=False)

    marker_label = db.Column(db.String(100), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    marker_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)


class RubricLine(db.Model):
    __tablename__ = 'rubric_line'
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(120), nullable=False)
    max_points = db.Column(db.Integer, nullable=False)
    weight = db.Column(db.Float, default=1.0)
    note = db.Column(db.String(200), default='')
    assessment_id = db.Column(db.Integer, db.ForeignKey('assessment.id'), nullable=False)


class TimeSlot(db.Model):
    __tablename__ = 'time_slot'
    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.Date, nullable=False)
    start_clock = db.Column(db.Time, nullable=False)
    end_clock = db.Column(db.Time, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    free_seats = db.Column(db.Integer, nullable=False)
    state = db.Column(db.String(30), default='Available')
    marker_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    assessment_id = db.Column(db.Integer, db.ForeignKey('assessment.id'), nullable=False)


class SeatHold(db.Model):
    __tablename__ = 'seat_hold'
    id = db.Column(db.Integer, primary_key=True)
    state = db.Column(db.String(30), default='Booked')
    held_on = db.Column(db.Date, default=date.today)
    slot_id = db.Column(db.Integer, db.ForeignKey('time_slot.id'), nullable=False)
    learner_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    assessment_id = db.Column(db.Integer, db.ForeignKey('assessment.id'), nullable=False)


class ScoreLine(db.Model):
    __tablename__ = 'score_line'
    id = db.Column(db.Integer, primary_key=True)
    points = db.Column(db.Integer, nullable=False)
    rubric_id = db.Column(db.Integer, db.ForeignKey('rubric_line.id'), nullable=False)
    assessment_id = db.Column(db.Integer, db.ForeignKey('assessment.id'), nullable=False)
    learner_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    marker_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)


class FeedbackNote(db.Model):
    __tablename__ = 'feedback_note'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False)
    assessment_id = db.Column(db.Integer, db.ForeignKey('assessment.id'), nullable=False)
    learner_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    marker_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)

from flask_sqlalchemy import SQLAlchemy
from datetime import date

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), nullable=False, unique=True)
    password = db.Column(db.String(100), nullable=False)
    account_type = db.Column(db.String(20), nullable=False)  # admin / examiner / student
    is_active = db.Column(db.Boolean, default=True)
    approval_status = db.Column(db.Boolean, default=True)


class Examiner_profile(db.Model):
    __tablename__ = 'examiner_profile'
    id = db.Column(db.Integer, primary_key=True)
    department_name = db.Column(db.String(100), nullable=False)
    contact_number = db.Column(db.String(20), nullable=False)
    office_address = db.Column(db.String(100), nullable=False)
    experience_years = db.Column(db.String(20), default='0')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)


class Student_profile(db.Model):
    __tablename__ = 'student_profile'
    id = db.Column(db.Integer, primary_key=True)
    registration_number = db.Column(db.String(30), unique=True)
    contact_number = db.Column(db.String(20), nullable=False)
    residential_address = db.Column(db.String(100), nullable=False)
    academic_year = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)


class Course(db.Model):
    __tablename__ = 'course'
    id = db.Column(db.Integer, primary_key=True)
    course_code = db.Column(db.String(30), unique=True, nullable=False)
    title = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    duration_weeks = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='Active')


class Examination(db.Model):
    __tablename__ = 'examination'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    exam_type = db.Column(db.String(40), default='Assessment')
    scheduled_date = db.Column(db.Date, nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    max_marks = db.Column(db.Integer, default=100)

    slot_creation_from = db.Column(db.Date, nullable=False)
    slot_creation_until = db.Column(db.Date, nullable=False)
    booking_opens_at = db.Column(db.Date, nullable=False)
    booking_closes_at = db.Column(db.Date, nullable=False)

    exam_status = db.Column(db.String(30), default='Draft')
    still_slot_creation = db.Column(db.Boolean, default=False)
    still_booking = db.Column(db.Boolean, default=False)
    published_result = db.Column(db.Boolean, default=False)

    examiner_name = db.Column(db.String(100), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    examiner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


class Rubrics(db.Model):
    __tablename__ = 'rubrics'
    id = db.Column(db.Integer, primary_key=True)
    criterion_title = db.Column(db.String(120), nullable=False)
    max_score = db.Column(db.Integer, nullable=False)
    weightage = db.Column(db.Float, default=1.0)
    description = db.Column(db.String(200), default='')
    exam_id = db.Column(db.Integer, db.ForeignKey('examination.id'), nullable=False)


class Slot(db.Model):
    __tablename__ = 'slot'
    id = db.Column(db.Integer, primary_key=True)
    slot_date = db.Column(db.Date, nullable=False)
    begins_at = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    max_students = db.Column(db.Integer, nullable=False)
    available_seats = db.Column(db.Integer, nullable=False)
    slot_status = db.Column(db.String(30), default='Available')
    examiner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    exam_id = db.Column(db.Integer, db.ForeignKey('examination.id'), nullable=False)


class Booking(db.Model):
    __tablename__ = 'booking'
    id = db.Column(db.Integer, primary_key=True)
    reservation_status = db.Column(db.String(30), default='Booked')
    booking_date = db.Column(db.Date, default=date.today)
    slot_id = db.Column(db.Integer, db.ForeignKey('slot.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    exam_id = db.Column(db.Integer, db.ForeignKey('examination.id'), nullable=False)


class Evaluation(db.Model):
    __tablename__ = 'evaluation'
    id = db.Column(db.Integer, primary_key=True)
    awarded_marks = db.Column(db.Integer, nullable=False)
    rubric_id = db.Column(db.Integer, db.ForeignKey('rubrics.id'), nullable=False)
    exam_id = db.Column(db.Integer, db.ForeignKey('examination.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    examiner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


class Remark(db.Model):
    __tablename__ = 'remark'
    id = db.Column(db.Integer, primary_key=True)
    examiner_remarks = db.Column(db.String(500), nullable=False)
    exam_id = db.Column(db.Integer, db.ForeignKey('examination.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    examiner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

from flask import Blueprint, render_template, request, redirect, url_for, session
from models import *
from datetime import datetime, date, timedelta

examiner_blueprint = Blueprint('examiner_routes', __name__)


@examiner_blueprint.before_request
def examiner_only():
    if session.get('account_type') != 'examiner':
        return redirect(url_for('index'))
    user = User.query.get(session.get('user_id'))
    if not user or not user.approval_status or not user.is_active:
        session.pop('user_id', None)
        session.pop('account_type', None)
        return redirect(url_for('auth.login'))


@examiner_blueprint.route('/examiner_dashboard', methods=['GET', 'POST'])
def examiner_dashboard():
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    profile = Examiner_profile.query.filter_by(user_id=user_id).first()

    assigned_exams = Examination.query.filter_by(examiner_id=user_id).all()
    slots = Slot.query.filter_by(examiner_id=user_id).all()
    exam_ids = [e.id for e in assigned_exams]

    bookings = []
    if exam_ids:
        bookings = Booking.query.filter(
            Booking.exam_id.in_(exam_ids),
            Booking.reservation_status.in_(['Booked', 'Completed'])
        ).all()

    # pending evaluations = booked/completed students without any marks yet
    pending = 0
    for booking in bookings:
        has_marks = Evaluation.query.filter_by(
            exam_id=booking.exam_id, student_id=booking.student_id
        ).first()
        if not has_marks:
            pending += 1

    student_map = {u.id: u for u in User.query.filter_by(account_type='student').all()}
    exam_map = {e.id: e for e in assigned_exams}
    slot_map = {s.id: s for s in slots}

    return render_template(
        'Examiner_Dashboard/examiner_dashboard.html',
        user=user,
        profile=profile,
        assigned_exams=assigned_exams,
        slots=slots,
        bookings=bookings,
        pending=pending,
        student_map=student_map,
        exam_map=exam_map,
        slot_map=slot_map
    )


@examiner_blueprint.route('/create_profile', methods=['GET', 'POST'])
def create_profile():
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    pf = Examiner_profile.query.filter_by(user_id=user_id).first()

    if request.method == 'POST':
        user.full_name = request.form['name']
        user.email = request.form['email']
        if pf:
            pf.department_name = request.form['department_name']
            pf.office_address = request.form['office_address']
            pf.contact_number = request.form['contact_number']
            pf.experience_years = request.form['experience_years']
        else:
            pf = Examiner_profile(
                department_name=request.form['department_name'],
                contact_number=request.form['contact_number'],
                office_address=request.form['office_address'],
                experience_years=request.form['experience_years'],
                user_id=user_id
            )
            db.session.add(pf)
        db.session.commit()
        return redirect(url_for('examiner_routes.examiner_dashboard'))

    return render_template('Examiner_Dashboard/create_profile.html', pf=pf, user=user)


@examiner_blueprint.route('/update_profile', methods=['GET', 'POST'])
def update_profile():
    user_id = session.get('user_id')
    pf = Examiner_profile.query.filter_by(user_id=user_id).first()
    if not pf:
        return redirect(url_for('examiner_routes.create_profile'))

    if request.method == 'POST':
        pf.department_name = request.form['department_name']
        pf.office_address = request.form['office_address']
        pf.contact_number = request.form['contact_number']
        pf.experience_years = request.form['experience_years']
        db.session.commit()
        return redirect(url_for('examiner_routes.examiner_dashboard'))

    return render_template('Examiner_Dashboard/update_profile.html', pf=pf)


@examiner_blueprint.route('/assigned_exams', methods=['GET', 'POST'])
def assigned_exams():
    examiner_id = session.get('user_id')
    exams = Examination.query.filter_by(examiner_id=examiner_id).all()
    courses = {c.id: c for c in Course.query.all()}
    return render_template(
        'Examiner_Dashboard/assigned_exams.html',
        assigned_exams=exams, courses=courses
    )


@examiner_blueprint.route('/give_slot/<int:exam_id>', methods=['GET', 'POST'])
def give_slot(exam_id):
    examiner_id = session.get('user_id')
    exam = Examination.query.get(exam_id)
    if not exam or exam.examiner_id != examiner_id:
        return redirect(url_for('examiner_routes.assigned_exams'))

    error = None
    if request.method == 'POST':
        if not exam.still_slot_creation:
            error = 'Admin has closed slot creation for this exam.'
        else:
            try:
                slot_date = datetime.strptime(request.form['slot_date'], '%Y-%m-%d').date()
                begins_at = datetime.strptime(request.form['begins_at'], '%H:%M').time()
                max_students = int(request.form.get('max_students') or 1)
            except (ValueError, TypeError):
                error = 'Enter a valid date, time and capacity.'
                slot_date = None
                begins_at = None
                max_students = 0

            if not error:
                if slot_date < exam.slot_creation_from or slot_date > exam.slot_creation_until:
                    error = 'Slot date must be between {} and {}.'.format(
                        exam.slot_creation_from, exam.slot_creation_until
                    )
                elif max_students < 1:
                    error = 'Capacity must be at least 1.'
                elif Slot.query.filter_by(
                    exam_id=exam.id, slot_date=slot_date, begins_at=begins_at, examiner_id=examiner_id
                ).first():
                    error = 'A slot already exists at this date and time.'
                else:
                    # end time = start + exam duration
                    start_dt = datetime.combine(slot_date, begins_at)
                    end_dt = start_dt + timedelta(minutes=exam.duration_minutes)
                    slot = Slot(
                        exam_id=exam.id,
                        slot_date=slot_date,
                        begins_at=begins_at,
                        end_time=end_dt.time(),
                        examiner_id=examiner_id,
                        max_students=max_students,
                        available_seats=max_students,
                        slot_status='Available'
                    )
                    db.session.add(slot)
                    db.session.commit()
                    return redirect(url_for('examiner_routes.give_slot', exam_id=exam.id))

    slots = Slot.query.filter_by(exam_id=exam.id, examiner_id=examiner_id).order_by(
        Slot.slot_date, Slot.begins_at
    ).all()

    booking_by_slot = {}
    student_map = {}
    for slot in slots:
        rows = Booking.query.filter_by(slot_id=slot.id, reservation_status='Booked').all()
        booking_by_slot[slot.id] = rows
        for b in rows:
            student_map[b.student_id] = User.query.get(b.student_id)

    booking_started = exam.still_booking
    return render_template(
        'Examiner_Dashboard/give_slot.html',
        exam=exam,
        slots=slots,
        error=error,
        booking_by_slot=booking_by_slot,
        student_map=student_map,
        booking_started=booking_started,
        creation_open=exam.still_slot_creation,
        locked=request.args.get('locked')
    )


@examiner_blueprint.route('/update_slot/<int:slot_id>', methods=['GET', 'POST'])
def update_slot(slot_id):
    slot = Slot.query.get(slot_id)
    exam = Examination.query.get(slot.exam_id) if slot else None
    if not slot or not exam or exam.examiner_id != session.get('user_id'):
        return redirect(url_for('examiner_routes.assigned_exams'))

    if exam.still_booking or Booking.query.filter_by(slot_id=slot.id, reservation_status='Booked').first():
        return redirect(url_for('examiner_routes.give_slot', exam_id=exam.id, locked=1))

    error = None
    if request.method == 'POST':
        try:
            slot_date = datetime.strptime(request.form['slot_date'], '%Y-%m-%d').date()
            begins_at = datetime.strptime(request.form['begins_at'], '%H:%M').time()
            max_students = int(request.form.get('max_students') or slot.max_students)
        except (ValueError, TypeError):
            error = 'Enter a valid date, time and capacity.'
            slot_date = None
            begins_at = None
            max_students = 0

        if not error:
            if slot_date < exam.slot_creation_from or slot_date > exam.slot_creation_until:
                error = 'Slot date must stay between {} and {}.'.format(
                    exam.slot_creation_from, exam.slot_creation_until
                )
            elif max_students < 1:
                error = 'Capacity must be at least 1.'
            else:
                taken = Slot.query.filter_by(
                    exam_id=exam.id, slot_date=slot_date, begins_at=begins_at, examiner_id=session.get('user_id')
                ).first()
                if taken and taken.id != slot.id:
                    error = 'A slot already exists at this date and time.'
                else:
                    start_dt = datetime.combine(slot_date, begins_at)
                    end_dt = start_dt + timedelta(minutes=exam.duration_minutes)
                    slot.slot_date = slot_date
                    slot.begins_at = begins_at
                    slot.end_time = end_dt.time()
                    slot.max_students = max_students
                    slot.available_seats = max_students
                    db.session.commit()
                    return redirect(url_for('examiner_routes.give_slot', exam_id=exam.id))

    return render_template('Examiner_Dashboard/update_slot.html', exam=exam, slot=slot, error=error)


@examiner_blueprint.route('/remove_slot/<int:slot_id>', methods=['GET', 'POST'])
def remove_slot(slot_id):
    slot = Slot.query.get(slot_id)
    exam = Examination.query.get(slot.exam_id) if slot else None
    if not slot or not exam or slot.examiner_id != session.get('user_id'):
        return redirect(url_for('examiner_routes.assigned_exams'))

    if exam.still_booking or Booking.query.filter_by(slot_id=slot.id, reservation_status='Booked').first():
        return redirect(url_for('examiner_routes.give_slot', exam_id=exam.id, locked=1))

    db.session.delete(slot)
    db.session.commit()
    return redirect(url_for('examiner_routes.give_slot', exam_id=exam.id))


@examiner_blueprint.route('/all_bookings', methods=['GET'])
def all_bookings():
    examiner_id = session.get('user_id')
    assigned_exams = Examination.query.filter_by(examiner_id=examiner_id).all()
    exam_ids = [e.id for e in assigned_exams]
    bookings = []
    if exam_ids:
        bookings = Booking.query.filter(
            Booking.exam_id.in_(exam_ids),
            Booking.reservation_status.in_(['Booked', 'Completed'])
        ).all()

    exam_map = {e.id: e for e in assigned_exams}
    slot_map = {s.id: s for s in Slot.query.filter(Slot.id.in_([b.slot_id for b in bookings])).all()} if bookings else {}
    student_map = {u.id: u for u in User.query.filter(User.id.in_([b.student_id for b in bookings])).all()} if bookings else {}

    # mark summary
    mark_summary = {}
    for booking in bookings:
        rows = Evaluation.query.filter_by(exam_id=booking.exam_id, student_id=booking.student_id).all()
        criteria = Rubrics.query.filter_by(exam_id=booking.exam_id).all()
        awarded = sum(r.awarded_marks for r in rows) if rows else None
        possible = sum(c.max_score for c in criteria)
        mark_summary[booking.id] = {'awarded': awarded, 'possible': possible}

    return render_template(
        'Examiner_Dashboard/all_bookings.html',
        bookings=bookings,
        exam_map=exam_map,
        slot_map=slot_map,
        student_map=student_map,
        mark_summary=mark_summary
    )


@examiner_blueprint.route('/view_details/<int:booking_id>', methods=['GET'])
def view_details(booking_id):
    booking = Booking.query.get(booking_id)
    exam = Examination.query.get(booking.exam_id) if booking else None
    if not booking or not exam or exam.examiner_id != session.get('user_id'):
        return redirect(url_for('examiner_routes.all_bookings'))

    student = User.query.get(booking.student_id)
    profile = Student_profile.query.filter_by(user_id=student.id).first()
    slot = Slot.query.get(booking.slot_id)
    remark = Remark.query.filter_by(exam_id=exam.id, student_id=student.id).first()

    return render_template(
        'Examiner_Dashboard/detail_booking.html',
        booking=booking, exam=exam, student=student,
        profile=profile, slot=slot, remark=remark
    )


@examiner_blueprint.route('/evaluate_marks/<int:booking_id>', methods=['GET', 'POST'])
def evaluate_marks(booking_id):
    booking = Booking.query.get(booking_id)
    exam = Examination.query.get(booking.exam_id) if booking else None
    if not booking or not exam or exam.examiner_id != session.get('user_id'):
        return redirect(url_for('examiner_routes.all_bookings'))
    if booking.reservation_status == 'Cancelled':
        return redirect(url_for('examiner_routes.all_bookings'))

    student = User.query.get(booking.student_id)
    criteria = Rubrics.query.filter_by(exam_id=exam.id).all()
    saved = {}
    for mark in Evaluation.query.filter_by(exam_id=exam.id, student_id=student.id).all():
        saved[mark.rubric_id] = mark
    remark = Remark.query.filter_by(exam_id=exam.id, student_id=student.id).first()
    error = None

    if request.method == 'POST':
        awarded = {}
        for criterion in criteria:
            raw = (request.form.get('marks_' + str(criterion.id)) or '').strip()
            try:
                value = int(raw)
            except ValueError:
                error = 'Enter a whole number for every criterion.'
                break
            if value < 0 or value > criterion.max_score:
                error = 'Marks for "{}" must be from 0 to {}.'.format(
                    criterion.criterion_title, criterion.max_score
                )
                break
            awarded[criterion.id] = value

        if not error and not criteria:
            error = 'This exam has no rubric yet. Ask admin to create one.'

        if not error:
            for criterion in criteria:
                row = saved.get(criterion.id)
                if row:
                    row.awarded_marks = awarded[criterion.id]
                    row.examiner_id = session.get('user_id')
                else:
                    db.session.add(Evaluation(
                        exam_id=exam.id,
                        student_id=student.id,
                        rubric_id=criterion.id,
                        awarded_marks=awarded[criterion.id],
                        examiner_id=session.get('user_id')
                    ))

            remark_text = (request.form.get('remark') or '').strip()
            if remark:
                remark.examiner_remarks = remark_text or remark.examiner_remarks
                remark.examiner_id = session.get('user_id')
            elif remark_text:
                db.session.add(Remark(
                    exam_id=exam.id,
                    student_id=student.id,
                    examiner_remarks=remark_text,
                    examiner_id=session.get('user_id')
                ))

            db.session.commit()
            return redirect(url_for('examiner_routes.all_bookings'))

    return render_template(
        'Examiner_Dashboard/evaluate_marks.html',
        exam=exam, student=student, criteria=criteria,
        saved=saved, remark=remark, error=error
    )

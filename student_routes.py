from flask import Blueprint, render_template, request, redirect, url_for, session
from models import *
from datetime import date

student_blueprint = Blueprint('student_routes', __name__)


@student_blueprint.before_request
def student_only():
    if session.get('account_type') != 'student':
        return redirect(url_for('index'))
    user = User.query.get(session.get('user_id'))
    if not user or not user.is_active:
        session.pop('user_id', None)
        session.pop('account_type', None)
        return redirect(url_for('auth.login'))


@student_blueprint.route('/student_dashboard', methods=['GET'])
def student_dashboard():
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    pf = Student_profile.query.filter_by(user_id=user_id).first()

    exams = Examination.query.order_by(Examination.scheduled_date).all()
    courses = {c.id: c for c in Course.query.all()}
    bookings = Booking.query.filter_by(student_id=user_id).all()
    exam_map = {e.id: e for e in exams}
    slot_map = {s.id: s for s in Slot.query.all()}

    today = date.today()
    for booking in bookings:
        if booking.reservation_status == 'Booked':
            exam = exam_map.get(booking.exam_id)
            if exam and exam.scheduled_date and exam.scheduled_date < today:
                booking.reservation_status = 'Completed'
    db.session.commit()

    booked_exam_ids = set()
    for b in bookings:
        if b.reservation_status == 'Booked':
            booked_exam_ids.add(b.exam_id)

    open_slots = []
    for slot in Slot.query.order_by(Slot.slot_date).all():
        exam = exam_map.get(slot.exam_id)
        if not exam or not exam.still_booking:
            continue
        if slot.exam_id in booked_exam_ids:
            continue
        taken = Booking.query.filter_by(slot_id=slot.id, reservation_status='Booked').count()
        if taken < slot.max_students:
            open_slots.append(slot)

    upcoming = []
    for b in bookings:
        if b.reservation_status == 'Booked':
            upcoming.append(b)

    published = []
    for b in bookings:
        exam = exam_map.get(b.exam_id)
        if exam and exam.published_result:
            published.append(b)

    cancel_open = {}
    for b in bookings:
        exam = exam_map.get(b.exam_id)
        can = False
        if b.reservation_status == 'Booked' and exam:
            if exam.booking_closes_at and today <= exam.booking_closes_at:
                can = True
        cancel_open[b.id] = can

    return render_template(
        'Student_Dashboard/student_dashboard.html',
        user=user,
        pf=pf,
        exams=exams,
        courses=courses,
        open_slots=open_slots,
        bookings=bookings,
        upcoming=upcoming,
        published=published,
        exam_map=exam_map,
        slot_map=slot_map,
        cancel_open=cancel_open,
        today=today
    )


@student_blueprint.route('/create_profile', methods=['GET', 'POST'])
def create_profile():
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    pf = Student_profile.query.filter_by(user_id=user_id).first()

    if request.method == 'POST':
        user.full_name = request.form['full_name']
        user.email = request.form['email']
        if pf:
            pf.registration_number = request.form['registration_number']
            pf.residential_address = request.form['residential_address']
            pf.contact_number = request.form['contact_number']
            pf.academic_year = request.form['academic_year']
        else:
            pf = Student_profile(
                registration_number=request.form['registration_number'],
                residential_address=request.form['residential_address'],
                contact_number=request.form['contact_number'],
                academic_year=request.form['academic_year'],
                user_id=user_id
            )
            db.session.add(pf)
        db.session.commit()
        return redirect(url_for('student_routes.student_dashboard'))

    return render_template('Student_Dashboard/create_profile.html', pf=pf, user=user)


@student_blueprint.route('/update_profile', methods=['GET', 'POST'])
def update_profile():
    user_id = session.get('user_id')
    pf = Student_profile.query.filter_by(user_id=user_id).first()
    if not pf:
        return redirect(url_for('student_routes.create_profile'))

    if request.method == 'POST':
        pf.registration_number = request.form['registration_number']
        pf.residential_address = request.form['residential_address']
        pf.contact_number = request.form['contact_number']
        pf.academic_year = request.form['academic_year']
        db.session.commit()
        return redirect(url_for('student_routes.student_dashboard'))

    return render_template('Student_Dashboard/update_profile.html', pf=pf)


@student_blueprint.route('/examinations', methods=['GET'])
def examinations():
    value = (request.args.get('q') or '').strip()
    course_filter = (request.args.get('course') or '').strip()
    booking_filter = (request.args.get('booking') or 'all').strip()
    when_filter = (request.args.get('when') or 'all').strip()
    today = date.today()

    courses = Course.query.order_by(Course.title).all()
    course_map = {c.id: c for c in courses}
    user_id = session.get('user_id')

    booked_exam_ids = set()
    for b in Booking.query.filter_by(student_id=user_id, reservation_status='Booked').all():
        booked_exam_ids.add(b.exam_id)

    slots_by_exam = {}
    for slot in Slot.query.order_by(Slot.slot_date).all():
        exam = Examination.query.get(slot.exam_id)
        if not exam or not exam.still_booking:
            continue
        if slot.exam_id in booked_exam_ids:
            continue
        taken = Booking.query.filter_by(slot_id=slot.id, reservation_status='Booked').count()
        if taken < slot.max_students:
            slots_by_exam.setdefault(slot.exam_id, []).append(slot)

    visible = []
    phases = {}
    can_book = {}
    for exam in Examination.query.order_by(Examination.scheduled_date).all():
        if value:
            if value.isdigit():
                if str(exam.id) != value:
                    continue
            elif value.lower() not in (exam.title or '').lower():
                continue
        if course_filter and str(exam.course_id) != course_filter:
            continue
        if booking_filter == 'open' and not exam.still_booking:
            continue
        if booking_filter == 'closed' and exam.still_booking:
            continue
        if when_filter == 'upcoming' and exam.scheduled_date < today:
            continue
        if when_filter == 'past' and exam.scheduled_date >= today:
            continue

        visible.append(exam)
        if exam.scheduled_date < today:
            phases[exam.id] = 'Completed'
        elif exam.still_booking:
            phases[exam.id] = 'Booking Open'
        elif exam.still_slot_creation:
            phases[exam.id] = 'Slot Creation'
        else:
            phases[exam.id] = exam.exam_status or 'Draft'
        can_book[exam.id] = bool(exam.still_booking)

    return render_template(
        'Student_Dashboard/examinations.html',
        exams=visible,
        courses=courses,
        course_map=course_map,
        slots_by_exam=slots_by_exam,
        booked_exam_ids=booked_exam_ids,
        q=value,
        course_filter=course_filter,
        booking_filter=booking_filter,
        when_filter=when_filter,
        phases=phases,
        can_book=can_book,
        today=today
    )


@student_blueprint.route('/slot_book/<int:slot_id>', methods=['GET'])
def slot_book(slot_id):
    student_id = session.get('user_id')
    slot = Slot.query.get(slot_id)
    if not slot:
        return redirect(url_for('student_routes.student_dashboard'))

    exam = Examination.query.get(slot.exam_id)
    already = Booking.query.filter_by(
        student_id=student_id, exam_id=slot.exam_id, reservation_status='Booked'
    ).first()
    taken = Booking.query.filter_by(slot_id=slot.id, reservation_status='Booked').count()

    if exam and exam.still_booking and not already and taken < slot.max_students:
        booking = Booking(
            slot_id=slot.id,
            exam_id=slot.exam_id,
            student_id=student_id,
            reservation_status='Booked',
            booking_date=date.today()
        )
        db.session.add(booking)
        taken = taken + 1
        slot.available_seats = slot.max_students - taken
        if taken >= slot.max_students:
            slot.slot_status = 'Full'
        db.session.commit()

    return redirect(url_for('student_routes.bookings'))


@student_blueprint.route('/cancel_booking/<int:booking_id>', methods=['GET'])
def cancel_booking(booking_id):
    booking = Booking.query.get(booking_id)
    if booking and booking.student_id == session.get('user_id'):
        exam = Examination.query.get(booking.exam_id)
        today = date.today()
        if booking.reservation_status == 'Booked' and exam and exam.booking_closes_at and today <= exam.booking_closes_at:
            booking.reservation_status = 'Cancelled'
            slot = Slot.query.get(booking.slot_id)
            if slot:
                taken = Booking.query.filter(
                    Booking.slot_id == slot.id,
                    Booking.reservation_status == 'Booked',
                    Booking.id != booking.id
                ).count()
                slot.available_seats = slot.max_students - taken
                slot.slot_status = 'Available'
            db.session.commit()
    return redirect(url_for('student_routes.bookings'))


@student_blueprint.route('/bookings', methods=['GET'])
def bookings():
    user_id = session.get('user_id')
    rows = Booking.query.filter_by(student_id=user_id).all()
    exams = {e.id: e for e in Examination.query.all()}
    slots = {s.id: s for s in Slot.query.all()}
    today = date.today()

    for booking in rows:
        if booking.reservation_status == 'Booked':
            exam = exams.get(booking.exam_id)
            if exam and exam.scheduled_date and exam.scheduled_date < today:
                booking.reservation_status = 'Completed'
    db.session.commit()

    details = []
    for booking in rows:
        exam = exams.get(booking.exam_id)
        slot = slots.get(booking.slot_id)
        can_cancel = False
        if booking.reservation_status == 'Booked' and exam and exam.booking_closes_at:
            if today <= exam.booking_closes_at:
                can_cancel = True
        details.append({
            'booking': booking,
            'exam': exam,
            'slot': slot,
            'reservation_status': booking.reservation_status,
            'can_cancel': can_cancel,
            'published': bool(exam and exam.published_result)
        })

    return render_template('Student_Dashboard/bookings.html', details=details)


@student_blueprint.route('/exam_history', methods=['GET'])
def exam_history():
    user_id = session.get('user_id')
    rows = Booking.query.filter_by(student_id=user_id).all()
    exams = {e.id: e for e in Examination.query.all()}
    slots = {s.id: s for s in Slot.query.all()}
    today = date.today()

    for booking in rows:
        if booking.reservation_status == 'Booked':
            exam = exams.get(booking.exam_id)
            if exam and exam.scheduled_date and exam.scheduled_date < today:
                booking.reservation_status = 'Completed'
    db.session.commit()

    history = []
    for booking in rows:
        if booking.reservation_status in ('Completed', 'Cancelled'):
            exam = exams.get(booking.exam_id)
            slot = slots.get(booking.slot_id)
            history.append({
                'booking': booking,
                'exam': exam,
                'slot': slot,
                'reservation_status': booking.reservation_status,
                'published': bool(exam and exam.published_result)
            })

    history.sort(key=lambda item: item['exam'].scheduled_date if item['exam'] else date.min, reverse=True)
    return render_template('Student_Dashboard/exam_history.html', history=history)


@student_blueprint.route('/evaluating_marks', methods=['GET'])
def evaluating_marks():
    user_id = session.get('user_id')
    bookings = Booking.query.filter_by(student_id=user_id).all()
    marks = Evaluation.query.filter_by(student_id=user_id).all()

    exam_ids = set()
    for b in bookings:
        exam_ids.add(b.exam_id)
    for m in marks:
        exam_ids.add(m.exam_id)

    exams = []
    if exam_ids:
        exams = Examination.query.filter(Examination.id.in_(exam_ids)).order_by(Examination.scheduled_date).all()

    published_ids = set()
    for exam in exams:
        if exam.published_result:
            published_ids.add(exam.id)

    criteria_by_exam = {}
    if published_ids:
        for criterion in Rubrics.query.filter(Rubrics.exam_id.in_(published_ids)).all():
            criteria_by_exam.setdefault(criterion.exam_id, []).append(criterion)

    marks_by_criterion = {}
    for mark in marks:
        if mark.exam_id in published_ids:
            marks_by_criterion[mark.rubric_id] = mark.awarded_marks

    examiner_remarks = {}
    for item in Remark.query.filter_by(student_id=user_id).all():
        if item.exam_id in published_ids:
            examiner_remarks[item.exam_id] = item.examiner_remarks

    return render_template(
        'Student_Dashboard/evaluating_marks.html',
        exams=exams,
        criteria_by_exam=criteria_by_exam,
        marks_by_criterion=marks_by_criterion,
        examiner_remarks=examiner_remarks
    )

from flask import Blueprint, render_template, request, redirect, url_for, session
from models import *
from datetime import datetime, date

admin_blueprint = Blueprint('admin_routes', __name__)


@admin_blueprint.before_request
def admin_only():
    if session.get('account_type') != 'admin':
        return redirect(url_for('index'))


@admin_blueprint.route('/admin_dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    return render_template(
        'Admin_Dashboard/admin_dashboard.html',
        course_count=Course.query.count(),
        exam_count=Examination.query.count(),
        student_count=User.query.filter_by(account_type='student').count(),
        examiner_count=User.query.filter_by(account_type='examiner').count(),
        slot_count=Slot.query.count(),
        booking_count=Booking.query.count()
    )


# ---------- Courses ----------

@admin_blueprint.route('/create_course', methods=['GET', 'POST'])
def create_course():
    if request.method == 'POST':
        course = Course(
            course_code=request.form['course_code'],
            title=request.form['title'],
            description=request.form['description'],
            duration_weeks=request.form['duration_weeks'],
            status=request.form.get('status', 'Active')
        )
        db.session.add(course)
        db.session.commit()
        return redirect(url_for('admin_routes.manage_courses'))
    return render_template('Admin_Dashboard/create_course.html')


@admin_blueprint.route('/manage_courses', methods=['GET', 'POST'])
def manage_courses():
    q = (request.args.get('q') or '').strip()
    courses = Course.query.all()
    if q:
        filtered = []
        for c in courses:
            if q.isdigit() and int(q) == c.id:
                filtered.append(c)
            elif q.lower() in (c.title or '').lower() or q.lower() in (c.course_code or '').lower():
                filtered.append(c)
        courses = filtered
    return render_template('Admin_Dashboard/manage_courses.html', courses=courses, q=q)


@admin_blueprint.route('/update_course/<int:id>', methods=['GET', 'POST'])
def update_course(id):
    course = Course.query.get(id)
    if request.method == 'POST':
        course.course_code = request.form['course_code']
        course.title = request.form['title']
        course.description = request.form['description']
        course.duration_weeks = request.form['duration_weeks']
        course.status = request.form.get('status', course.status)
        db.session.commit()
        return redirect(url_for('admin_routes.manage_courses'))
    return render_template('Admin_Dashboard/update_course.html', course=course)


@admin_blueprint.route('/delete_course/<int:id>', methods=['GET', 'POST'])
def delete_course(id):
    exams = Examination.query.filter_by(course_id=id).all()
    for exam in exams:
        Rubrics.query.filter_by(exam_id=exam.id).delete()
        Evaluation.query.filter_by(exam_id=exam.id).delete()
        Remark.query.filter_by(exam_id=exam.id).delete()
        Booking.query.filter_by(exam_id=exam.id).delete()
        Slot.query.filter_by(exam_id=exam.id).delete()
        db.session.delete(exam)
    course = Course.query.get(id)
    db.session.delete(course)
    db.session.commit()
    return redirect(url_for('admin_routes.manage_courses'))


# ---------- Examinations ----------

@admin_blueprint.route('/create_exam', methods=['GET', 'POST'])
def create_exam():
    examiners = User.query.filter_by(account_type='examiner', approval_status=True, is_active=True).all()
    courses = Course.query.filter_by(status='Active').all()

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        exam_type = request.form.get('exam_type', 'Assessment')
        scheduled_date = datetime.strptime(request.form['scheduled_date'], '%Y-%m-%d').date()
        duration_minutes = int(request.form['duration_minutes'])
        max_marks = int(request.form.get('max_marks') or 100)
        slot_creation_from = datetime.strptime(request.form['slot_creation_from'], '%Y-%m-%d').date()
        slot_creation_until = datetime.strptime(request.form['slot_creation_until'], '%Y-%m-%d').date()
        booking_opens_at = datetime.strptime(request.form['booking_opens_at'], '%Y-%m-%d').date()
        booking_closes_at = datetime.strptime(request.form['booking_closes_at'], '%Y-%m-%d').date()
        course_id = int(request.form['course_id'])
        examiner_id = int(request.form['examiner_id'])

        error = None
        if slot_creation_until < slot_creation_from:
            error = 'Slot creation end date must be on or after the start date.'
        elif booking_opens_at <= slot_creation_until:
            error = 'Booking must open after the slot creation end date.'
        elif booking_closes_at < booking_opens_at:
            error = 'Booking close date must be on or after the date booking opens.'
        elif scheduled_date < booking_closes_at:
            error = 'Exam date must be on or after the day booking closes.'

        if error:
            return render_template(
                'Admin_Dashboard/create_exam.html',
                examiners=examiners, courses=courses, error=error
            )

        user = User.query.get(examiner_id)
        exam = Examination(
            title=title,
            description=description,
            exam_type=exam_type,
            scheduled_date=scheduled_date,
            duration_minutes=duration_minutes,
            max_marks=max_marks,
            slot_creation_from=slot_creation_from,
            slot_creation_until=slot_creation_until,
            booking_opens_at=booking_opens_at,
            booking_closes_at=booking_closes_at,
            course_id=course_id,
            examiner_id=examiner_id,
            examiner_name=user.full_name,
            exam_status='Draft'
        )
        db.session.add(exam)
        db.session.commit()
        return redirect(url_for('admin_routes.manage_exams'))

    return render_template('Admin_Dashboard/create_exam.html', examiners=examiners, courses=courses)


@admin_blueprint.route('/manage_exams', methods=['GET', 'POST'])
def manage_exams():
    q = (request.args.get('q') or '').strip()
    exams = Examination.query.all()
    if q:
        filtered = []
        for exam in exams:
            if q.isdigit() and int(q) == exam.id:
                filtered.append(exam)
            elif q.lower() in (exam.title or '').lower():
                filtered.append(exam)
        exams = filtered

    phases = {}
    today = date.today()
    for exam in exams:
        if exam.scheduled_date and exam.scheduled_date < today:
            phases[exam.id] = 'Completed'
        elif exam.still_booking:
            phases[exam.id] = 'Booking Open'
        elif exam.still_slot_creation:
            phases[exam.id] = 'Slot Creation'
        elif exam.booking_closes_at and today > exam.booking_closes_at:
            phases[exam.id] = 'Closed'
        else:
            phases[exam.id] = exam.exam_status or 'Draft'

    return render_template('Admin_Dashboard/manage_exams.html', exams=exams, q=q, phases=phases)


@admin_blueprint.route('/update_exam/<int:id>', methods=['GET', 'POST'])
def update_exam(id):
    exam = Examination.query.get(id)
    examiners = User.query.filter_by(account_type='examiner', approval_status=True, is_active=True).all()
    courses = Course.query.all()
    has_booking = Booking.query.filter_by(exam_id=exam.id, reservation_status='Booked').first() is not None

    if request.method == 'POST':
        new_examiner_id = int(request.form['examiner_id'])
        error = None

        if new_examiner_id != exam.examiner_id and has_booking:
            error = 'Students have booked this exam. Cancel bookings before changing examiner.'

        slot_creation_from = datetime.strptime(request.form['slot_creation_from'], '%Y-%m-%d').date()
        slot_creation_until = datetime.strptime(request.form['slot_creation_until'], '%Y-%m-%d').date()
        booking_opens_at = datetime.strptime(request.form['booking_opens_at'], '%Y-%m-%d').date()
        booking_closes_at = datetime.strptime(request.form['booking_closes_at'], '%Y-%m-%d').date()
        scheduled_date = datetime.strptime(request.form['scheduled_date'], '%Y-%m-%d').date()

        if not error:
            if slot_creation_until < slot_creation_from:
                error = 'Slot creation end date must be on or after the start date.'
            elif booking_opens_at <= slot_creation_until:
                error = 'Booking must open after the slot creation end date.'
            elif booking_closes_at < booking_opens_at:
                error = 'Booking close date must be on or after the date booking opens.'
            elif scheduled_date < booking_closes_at:
                error = 'Exam date must be on or after the day booking closes.'

        if error:
            return render_template(
                'Admin_Dashboard/update_exam.html',
                exam=exam, examiners=examiners, courses=courses,
                error=error, this_exam_booked=has_booking
            )

        exam.title = request.form['title']
        exam.description = request.form['description']
        exam.exam_type = request.form.get('exam_type', exam.exam_type)
        exam.scheduled_date = scheduled_date
        exam.duration_minutes = int(request.form['duration_minutes'])
        exam.max_marks = int(request.form.get('max_marks') or exam.max_marks)
        exam.slot_creation_from = slot_creation_from
        exam.slot_creation_until = slot_creation_until
        exam.booking_opens_at = booking_opens_at
        exam.booking_closes_at = booking_closes_at
        exam.course_id = int(request.form['course_id'])
        exam.examiner_id = new_examiner_id
        exam.examiner_name = User.query.get(new_examiner_id).full_name
        db.session.commit()
        return redirect(url_for('admin_routes.manage_exams'))

    return render_template(
        'Admin_Dashboard/update_exam.html',
        exam=exam, examiners=examiners, courses=courses, this_exam_booked=has_booking
    )


@admin_blueprint.route('/delete_exam/<int:id>', methods=['GET', 'POST'])
def delete_exam(id):
    Rubrics.query.filter_by(exam_id=id).delete()
    Evaluation.query.filter_by(exam_id=id).delete()
    Remark.query.filter_by(exam_id=id).delete()
    Booking.query.filter_by(exam_id=id).delete()
    Slot.query.filter_by(exam_id=id).delete()
    exam = Examination.query.get(id)
    db.session.delete(exam)
    db.session.commit()
    return redirect(url_for('admin_routes.manage_exams'))


@admin_blueprint.route('/allow_slot_creation/<int:id>')
def allow_slot_creation(id):
    exam = Examination.query.get(id)
    exam.still_slot_creation = True
    exam.exam_status = 'Slot Creation'
    db.session.commit()
    return redirect(url_for('admin_routes.manage_exams'))


@admin_blueprint.route('/close_slot_creation/<int:id>')
def close_slot_creation(id):
    exam = Examination.query.get(id)
    exam.still_slot_creation = False
    db.session.commit()
    return redirect(url_for('admin_routes.manage_exams'))


@admin_blueprint.route('/allow_booking/<int:id>')
def allow_booking(id):
    exam = Examination.query.get(id)
    exam.still_booking = True
    exam.still_slot_creation = False
    exam.exam_status = 'Booking Open'
    db.session.commit()
    return redirect(url_for('admin_routes.manage_exams'))


@admin_blueprint.route('/close_booking/<int:id>')
def close_booking(id):
    exam = Examination.query.get(id)
    exam.still_booking = False
    exam.exam_status = 'Closed'
    db.session.commit()
    return redirect(url_for('admin_routes.manage_exams'))


@admin_blueprint.route('/publish_results/<int:id>')
def publish_results(id):
    exam = Examination.query.get(id)
    exam.published_result = True
    db.session.commit()
    return redirect(url_for('admin_routes.manage_exams'))


@admin_blueprint.route('/hide_results/<int:id>')
def hide_results(id):
    exam = Examination.query.get(id)
    exam.published_result = False
    db.session.commit()
    return redirect(url_for('admin_routes.manage_exams'))


# ---------- Rubrics ----------

@admin_blueprint.route('/create_rubric/<int:id>', methods=['GET', 'POST'])
def create_rubric(id):
    if request.method == 'POST':
        rubric = Rubrics(
            criterion_title=request.form['criterion'],
            max_score=int(request.form['max_score']),
            weightage=float(request.form.get('weightage') or 1),
            description=request.form.get('description', ''),
            exam_id=id
        )
        db.session.add(rubric)
        db.session.commit()
        return redirect(url_for('admin_routes.manage_rubrics', id=id))
    return render_template('Admin_Dashboard/create_rubric.html', id=id)


@admin_blueprint.route('/manage_rubrics/<int:id>', methods=['GET', 'POST'])
def manage_rubrics(id):
    criteria = Rubrics.query.filter_by(exam_id=id).all()
    return render_template('Admin_Dashboard/manage_rubrics.html', criteria=criteria, exam_id=id)


@admin_blueprint.route('/update_rubric/<int:id>', methods=['GET', 'POST'])
def update_rubric(id):
    rubric = Rubrics.query.get(id)
    if request.method == 'POST':
        rubric.criterion_title = request.form['criterion']
        rubric.max_score = int(request.form['max_score'])
        rubric.weightage = float(request.form.get('weightage') or 1)
        rubric.description = request.form.get('description', '')
        db.session.commit()
        return redirect(url_for('admin_routes.manage_rubrics', id=rubric.exam_id))
    return render_template('Admin_Dashboard/update_rubric.html', rubric=rubric)


@admin_blueprint.route('/delete_rubric/<int:id>', methods=['GET', 'POST'])
def delete_rubric(id):
    rubric = Rubrics.query.get(id)
    exam_id = rubric.exam_id
    Evaluation.query.filter_by(rubric_id=rubric.id).delete()
    db.session.delete(rubric)
    db.session.commit()
    return redirect(url_for('admin_routes.manage_rubrics', id=exam_id))


# ---------- Examiners ----------

@admin_blueprint.route('/manage_examiners', methods=['GET', 'POST'])
def manage_examiners():
    q = (request.args.get('q') or '').strip()
    examiners = User.query.filter_by(account_type='examiner').all()
    if q:
        filtered = []
        for user in examiners:
            if q.isdigit() and int(q) == user.id:
                filtered.append(user)
            elif q.lower() in (user.full_name or '').lower() or q.lower() in (user.email or '').lower():
                filtered.append(user)
        examiners = filtered
    return render_template('Admin_Dashboard/manage_examiners.html', examiners=examiners, q=q)


@admin_blueprint.route('/approve_examiner/<int:id>')
def approve_examiner(id):
    examiner = User.query.get(id)
    examiner.approval_status = True
    db.session.commit()
    return redirect(url_for('admin_routes.manage_examiners'))


@admin_blueprint.route('/examiner_details/<int:id>')
def examiner_details(id):
    user = User.query.get(id)
    profile = Examiner_profile.query.filter_by(user_id=id).first()
    return render_template('Admin_Dashboard/examiner_details.html', user=user, profile=profile)


# ---------- Students ----------

@admin_blueprint.route('/manage_students', methods=['GET', 'POST'])
def manage_students():
    q = (request.args.get('q') or '').strip()
    users = User.query.filter_by(account_type='student').all()
    if q:
        filtered = []
        for user in users:
            if q.isdigit() and int(q) == user.id:
                filtered.append(user)
            elif q.lower() in (user.full_name or '').lower() or q.lower() in (user.email or '').lower():
                filtered.append(user)
        users = filtered
    return render_template('Admin_Dashboard/manage_students.html', users=users, q=q)


@admin_blueprint.route('/student_details/<int:id>')
def student_details(id):
    user = User.query.get(id)
    profile = Student_profile.query.filter_by(user_id=id).first()
    return render_template('Admin_Dashboard/student_details.html', user=user, profile=profile)


@admin_blueprint.route('/block_user/<int:id>')
def block_user(id):
    user = User.query.get(id)
    user.is_active = False
    db.session.commit()
    if user.account_type == 'examiner':
        return redirect(url_for('admin_routes.manage_examiners'))
    return redirect(url_for('admin_routes.manage_students'))


@admin_blueprint.route('/unblock_user/<int:id>')
def unblock_user(id):
    user = User.query.get(id)
    user.is_active = True
    db.session.commit()
    if user.account_type == 'examiner':
        return redirect(url_for('admin_routes.manage_examiners'))
    return redirect(url_for('admin_routes.manage_students'))


# ---------- Slots & Bookings ----------

@admin_blueprint.route('/all_slots', methods=['GET'])
def all_slots():
    q = (request.args.get('q') or '').strip()
    slots = Slot.query.order_by(Slot.slot_date, Slot.begins_at).all()
    exams = {e.id: e for e in Examination.query.all()}
    examiners = {u.id: u for u in User.query.filter_by(account_type='examiner').all()}

    if q:
        filtered = []
        for slot in slots:
            exam = exams.get(slot.exam_id)
            examiner = examiners.get(slot.examiner_id)
            if q.isdigit() and int(q) == slot.id:
                filtered.append(slot)
            elif exam and q.lower() in (exam.title or '').lower():
                filtered.append(slot)
            elif examiner and q.lower() in (examiner.full_name or '').lower():
                filtered.append(slot)
        slots = filtered

    booked_counts = {}
    for b in Booking.query.filter_by(reservation_status='Booked').all():
        booked_counts[b.slot_id] = booked_counts.get(b.slot_id, 0) + 1

    return render_template(
        'Admin_Dashboard/all_slots.html',
        slots=slots, exams=exams, examiners=examiners,
        booked_counts=booked_counts, q=q
    )


@admin_blueprint.route('/all_bookings', methods=['GET'])
def all_bookings():
    q = (request.args.get('q') or '').strip()
    bookings = Booking.query.all()
    exams = {e.id: e for e in Examination.query.all()}
    students = {u.id: u for u in User.query.filter_by(account_type='student').all()}
    slots = {s.id: s for s in Slot.query.all()}
    profiles = {p.user_id: p for p in Student_profile.query.all()}

    # mark completed if exam date passed
    today = date.today()
    changed = False
    for booking in bookings:
        if booking.reservation_status == 'Booked':
            exam = exams.get(booking.exam_id)
            if exam and exam.scheduled_date and exam.scheduled_date < today:
                booking.reservation_status = 'Completed'
                changed = True
    if changed:
        db.session.commit()

    if q:
        filtered = []
        for booking in bookings:
            exam = exams.get(booking.exam_id)
            student = students.get(booking.student_id)
            if q.isdigit() and (int(q) == booking.id or int(q) == booking.student_id or int(q) == booking.exam_id):
                filtered.append(booking)
            elif student and q.lower() in (student.full_name or '').lower():
                filtered.append(booking)
            elif exam and q.lower() in (exam.title or '').lower():
                filtered.append(booking)
        bookings = filtered

    return render_template(
        'Admin_Dashboard/all_booking.html',
        bookings=bookings, exams=exams, slots=slots,
        students=students, profiles=profiles, q=q
    )


@admin_blueprint.route('/reschedule_booking/<int:booking_id>', methods=['GET', 'POST'])
def reschedule_booking(booking_id):
    booking = Booking.query.get(booking_id)
    if not booking or booking.reservation_status == 'Cancelled':
        return redirect(url_for('admin_routes.all_bookings'))

    exam = Examination.query.get(booking.exam_id)
    all_slots = Slot.query.filter_by(exam_id=exam.id).order_by(Slot.slot_date, Slot.begins_at).all()

    # seats taken per slot
    open_slots = []
    for slot in all_slots:
        taken = Booking.query.filter_by(slot_id=slot.id, reservation_status='Booked').count()
        if slot.id == booking.slot_id or taken < slot.max_students:
            open_slots.append(slot)

    error = None
    if request.method == 'POST':
        new_slot = Slot.query.get(int(request.form['slot_id']))
        if not new_slot or new_slot.exam_id != exam.id:
            error = 'Choose a valid slot for this exam.'
        else:
            taken = Booking.query.filter_by(slot_id=new_slot.id, reservation_status='Booked').count()
            if new_slot.id != booking.slot_id and taken >= new_slot.max_students:
                error = 'That slot is full.'
            else:
                old_slot = Slot.query.get(booking.slot_id)
                booking.slot_id = new_slot.id
                booking.reservation_status = 'Booked'

                # refresh old slot seats
                if old_slot:
                    old_taken = Booking.query.filter_by(slot_id=old_slot.id, reservation_status='Booked').count()
                    old_slot.available_seats = old_slot.max_students - old_taken
                    old_slot.slot_status = 'Full' if old_taken >= old_slot.max_students else 'Available'

                new_taken = Booking.query.filter_by(slot_id=new_slot.id, reservation_status='Booked').count()
                # include this booking in new slot if it was counted already as Booked on old - recount after assign
                new_taken = Booking.query.filter_by(slot_id=new_slot.id, reservation_status='Booked').count()
                new_slot.available_seats = new_slot.max_students - new_taken
                new_slot.slot_status = 'Full' if new_taken >= new_slot.max_students else 'Available'

                db.session.commit()
                return redirect(url_for('admin_routes.all_bookings'))

    return render_template(
        'Admin_Dashboard/reschedule_booking.html',
        booking=booking, exam=exam, slots=open_slots, error=error
    )


@admin_blueprint.route('/cancel_booking/<int:booking_id>')
def cancel_booking(booking_id):
    booking = Booking.query.get(booking_id)
    if booking and booking.reservation_status == 'Booked':
        booking.reservation_status = 'Cancelled'
        slot = Slot.query.get(booking.slot_id)
        if slot:
            taken = Booking.query.filter_by(slot_id=slot.id, reservation_status='Booked').count()
            # after status change, recount without this booking
            taken = Booking.query.filter(
                Booking.slot_id == slot.id,
                Booking.reservation_status == 'Booked',
                Booking.id != booking.id
            ).count()
            slot.available_seats = slot.max_students - taken
            slot.slot_status = 'Available'
        db.session.commit()
    return redirect(url_for('admin_routes.all_bookings'))

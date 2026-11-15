from flask import Blueprint, render_template, request, redirect, url_for, session
from models import *
from datetime import date

learner_bp = Blueprint('learner', __name__)


@learner_bp.before_request
def need_learner():
    if session.get('role') != 'learner':
        return redirect(url_for('home_page'))
    person = Account.query.get(session.get('uid'))
    if not person or not person.active_flag:
        session.pop('uid', None)
        session.pop('role', None)
        return redirect(url_for('access.sign_in'))


@learner_bp.route('/home')
def learner_home():
    uid = session.get('uid')
    person = Account.query.get(uid)
    bio = LearnerBio.query.filter_by(account_id=uid).first()
    exams = Assessment.query.order_by(Assessment.hold_date).all()
    subjects = {s.id: s for s in Subject.query.all()}
    holds = SeatHold.query.filter_by(learner_id=uid).all()
    exam_map = {e.id: e for e in exams}
    slot_map = {s.id: s for s in TimeSlot.query.all()}
    today = date.today()
    for h in holds:
        if h.state == 'Booked':
            exam = exam_map.get(h.assessment_id)
            if exam and exam.hold_date and exam.hold_date < today:
                h.state = 'Completed'
    db.session.commit()

    taken_exams = set()
    for h in holds:
        if h.state == 'Booked':
            taken_exams.add(h.assessment_id)

    open_slots = []
    for slot in TimeSlot.query.order_by(TimeSlot.day).all():
        exam = exam_map.get(slot.assessment_id)
        if not exam or not exam.book_open:
            continue
        if slot.assessment_id in taken_exams:
            continue
        taken = SeatHold.query.filter_by(slot_id=slot.id, state='Booked').count()
        if taken < slot.capacity:
            open_slots.append(slot)

    upcoming = [h for h in holds if h.state == 'Booked']
    published = [h for h in holds if exam_map.get(h.assessment_id) and exam_map[h.assessment_id].result_live]

    can_cancel = {}
    for h in holds:
        exam = exam_map.get(h.assessment_id)
        ok = False
        if h.state == 'Booked' and exam and exam.book_until and today <= exam.book_until:
            ok = True
        can_cancel[h.id] = ok

    return render_template(
        'learner/home.html',
        person=person, bio=bio, exams=exams, subjects=subjects,
        open_slots=open_slots, holds=holds, upcoming=upcoming,
        published=published, exam_map=exam_map, slot_map=slot_map,
        can_cancel=can_cancel, today=today
    )


@learner_bp.route('/make_bio', methods=['GET', 'POST'])
def make_bio():
    uid = session.get('uid')
    person = Account.query.get(uid)
    bio = LearnerBio.query.filter_by(account_id=uid).first()
    if request.method == 'POST':
        person.display_name = request.form['display_name']
        person.email = request.form['email']
        if bio:
            bio.roll_no = request.form['roll_no']
            bio.home_address = request.form['home_address']
            bio.phone = request.form['phone']
            bio.batch_year = request.form['batch_year']
        else:
            bio = LearnerBio(
                roll_no=request.form['roll_no'],
                home_address=request.form['home_address'],
                phone=request.form['phone'],
                batch_year=request.form['batch_year'],
                account_id=uid
            )
            db.session.add(bio)
        db.session.commit()
        return redirect(url_for('learner.learner_home'))
    return render_template('learner/make_bio.html', person=person, bio=bio)


@learner_bp.route('/edit_bio', methods=['GET', 'POST'])
def edit_bio():
    uid = session.get('uid')
    bio = LearnerBio.query.filter_by(account_id=uid).first()
    if not bio:
        return redirect(url_for('learner.make_bio'))
    if request.method == 'POST':
        bio.roll_no = request.form['roll_no']
        bio.home_address = request.form['home_address']
        bio.phone = request.form['phone']
        bio.batch_year = request.form['batch_year']
        db.session.commit()
        return redirect(url_for('learner.learner_home'))
    return render_template('learner/edit_bio.html', bio=bio)


@learner_bp.route('/browse')
def browse():
    q = (request.args.get('q') or '').strip()
    subject_filter = (request.args.get('subject') or '').strip()
    book_filter = (request.args.get('booking') or 'all').strip()
    when_filter = (request.args.get('when') or 'all').strip()
    today = date.today()
    subjects = Subject.query.order_by(Subject.name).all()
    subject_map = {s.id: s for s in subjects}
    uid = session.get('uid')

    taken_exams = set()
    for h in SeatHold.query.filter_by(learner_id=uid, state='Booked').all():
        taken_exams.add(h.assessment_id)

    slots_by_exam = {}
    for slot in TimeSlot.query.order_by(TimeSlot.day).all():
        exam = Assessment.query.get(slot.assessment_id)
        if not exam or not exam.book_open:
            continue
        if slot.assessment_id in taken_exams:
            continue
        taken = SeatHold.query.filter_by(slot_id=slot.id, state='Booked').count()
        if taken < slot.capacity:
            slots_by_exam.setdefault(slot.assessment_id, []).append(slot)

    visible = []
    labels = {}
    can_book = {}
    for exam in Assessment.query.order_by(Assessment.hold_date).all():
        if q:
            if q.isdigit():
                if str(exam.id) != q:
                    continue
            elif q.lower() not in (exam.name or '').lower():
                continue
        if subject_filter and str(exam.subject_id) != subject_filter:
            continue
        if book_filter == 'open' and not exam.book_open:
            continue
        if book_filter == 'closed' and exam.book_open:
            continue
        if when_filter == 'upcoming' and exam.hold_date < today:
            continue
        if when_filter == 'past' and exam.hold_date >= today:
            continue
        visible.append(exam)
        if exam.hold_date < today:
            labels[exam.id] = 'Completed'
        elif exam.book_open:
            labels[exam.id] = 'Booking Open'
        elif exam.slot_open:
            labels[exam.id] = 'Slot Creation'
        else:
            labels[exam.id] = exam.phase or 'Draft'
        can_book[exam.id] = bool(exam.book_open)

    return render_template(
        'learner/browse.html',
        exams=visible, subjects=subjects, subject_map=subject_map,
        slots_by_exam=slots_by_exam, taken_exams=taken_exams,
        q=q, subject_filter=subject_filter, book_filter=book_filter,
        when_filter=when_filter, labels=labels, can_book=can_book, today=today
    )


@learner_bp.route('/take_seat/<int:sid>')
def take_seat(sid):
    uid = session.get('uid')
    slot = TimeSlot.query.get(sid)
    if not slot:
        return redirect(url_for('learner.learner_home'))
    exam = Assessment.query.get(slot.assessment_id)
    already = SeatHold.query.filter_by(
        learner_id=uid, assessment_id=slot.assessment_id, state='Booked'
    ).first()
    taken = SeatHold.query.filter_by(slot_id=slot.id, state='Booked').count()
    if exam and exam.book_open and not already and taken < slot.capacity:
        hold = SeatHold(
            slot_id=slot.id,
            assessment_id=slot.assessment_id,
            learner_id=uid,
            state='Booked',
            held_on=date.today()
        )
        db.session.add(hold)
        taken = taken + 1
        slot.free_seats = slot.capacity - taken
        if taken >= slot.capacity:
            slot.state = 'Full'
        db.session.commit()
    return redirect(url_for('learner.my_holds'))


@learner_bp.route('/drop_seat/<int:hid>')
def drop_seat(hid):
    hold = SeatHold.query.get(hid)
    if hold and hold.learner_id == session.get('uid'):
        exam = Assessment.query.get(hold.assessment_id)
        today = date.today()
        if hold.state == 'Booked' and exam and exam.book_until and today <= exam.book_until:
            hold.state = 'Cancelled'
            slot = TimeSlot.query.get(hold.slot_id)
            if slot:
                taken = SeatHold.query.filter(
                    SeatHold.slot_id == slot.id,
                    SeatHold.state == 'Booked',
                    SeatHold.id != hold.id
                ).count()
                slot.free_seats = slot.capacity - taken
                slot.state = 'Available'
            db.session.commit()
    return redirect(url_for('learner.my_holds'))


@learner_bp.route('/my_holds')
def my_holds():
    uid = session.get('uid')
    rows = SeatHold.query.filter_by(learner_id=uid).all()
    exams = {e.id: e for e in Assessment.query.all()}
    slots = {s.id: s for s in TimeSlot.query.all()}
    today = date.today()
    for h in rows:
        if h.state == 'Booked':
            exam = exams.get(h.assessment_id)
            if exam and exam.hold_date and exam.hold_date < today:
                h.state = 'Completed'
    db.session.commit()
    items = []
    for h in rows:
        exam = exams.get(h.assessment_id)
        slot = slots.get(h.slot_id)
        ok = False
        if h.state == 'Booked' and exam and exam.book_until and today <= exam.book_until:
            ok = True
        items.append({
            'hold': h, 'exam': exam, 'slot': slot,
            'state': h.state, 'can_cancel': ok,
            'live': bool(exam and exam.result_live)
        })
    return render_template('learner/my_holds.html', items=items)


@learner_bp.route('/history')
def history():
    uid = session.get('uid')
    rows = SeatHold.query.filter_by(learner_id=uid).all()
    exams = {e.id: e for e in Assessment.query.all()}
    slots = {s.id: s for s in TimeSlot.query.all()}
    today = date.today()
    for h in rows:
        if h.state == 'Booked':
            exam = exams.get(h.assessment_id)
            if exam and exam.hold_date and exam.hold_date < today:
                h.state = 'Completed'
    db.session.commit()
    items = []
    for h in rows:
        if h.state in ('Completed', 'Cancelled'):
            exam = exams.get(h.assessment_id)
            slot = slots.get(h.slot_id)
            items.append({
                'hold': h, 'exam': exam, 'slot': slot,
                'state': h.state, 'live': bool(exam and exam.result_live)
            })
    items.sort(key=lambda x: x['exam'].hold_date if x['exam'] else date.min, reverse=True)
    return render_template('learner/history.html', items=items)


@learner_bp.route('/scores')
def scores():
    uid = session.get('uid')
    holds = SeatHold.query.filter_by(learner_id=uid).all()
    marks = ScoreLine.query.filter_by(learner_id=uid).all()
    ids = set()
    for h in holds:
        ids.add(h.assessment_id)
    for m in marks:
        ids.add(m.assessment_id)
    exams = []
    if ids:
        exams = Assessment.query.filter(Assessment.id.in_(ids)).order_by(Assessment.hold_date).all()
    live = set()
    for e in exams:
        if e.result_live:
            live.add(e.id)
    lines_by = {}
    if live:
        for line in RubricLine.query.filter(RubricLine.assessment_id.in_(live)).all():
            lines_by.setdefault(line.assessment_id, []).append(line)
    points = {}
    for m in marks:
        if m.assessment_id in live:
            points[m.rubric_id] = m.points
    notes = {}
    for n in FeedbackNote.query.filter_by(learner_id=uid).all():
        if n.assessment_id in live:
            notes[n.assessment_id] = n.text
    return render_template(
        'learner/scores.html', exams=exams, lines_by=lines_by,
        points=points, notes=notes
    )

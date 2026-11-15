from flask import Blueprint, render_template, request, redirect, url_for, session
from models import *
from datetime import datetime, date

control_bp = Blueprint('control', __name__)


@control_bp.before_request
def need_admin():
    if session.get('role') != 'admin':
        return redirect(url_for('home_page'))


@control_bp.route('/home')
def control_home():
    return render_template(
        'control/home.html',
        n_subject=Subject.query.count(),
        n_assessment=Assessment.query.count(),
        n_learner=Account.query.filter_by(role='learner').count(),
        n_marker=Account.query.filter_by(role='marker').count(),
        n_slot=TimeSlot.query.count(),
        n_hold=SeatHold.query.count()
    )


@control_bp.route('/add_subject', methods=['GET', 'POST'])
def add_subject():
    if request.method == 'POST':
        row = Subject(
            code=request.form['code'],
            name=request.form['name'],
            summary=request.form['summary'],
            weeks=request.form['weeks'],
            state=request.form.get('state', 'Active')
        )
        db.session.add(row)
        db.session.commit()
        return redirect(url_for('control.list_subjects'))
    return render_template('control/add_subject.html')


@control_bp.route('/list_subjects')
def list_subjects():
    q = (request.args.get('q') or '').strip()
    rows = Subject.query.all()
    if q:
        out = []
        for s in rows:
            if q.isdigit() and int(q) == s.id:
                out.append(s)
            elif q.lower() in (s.name or '').lower() or q.lower() in (s.code or '').lower():
                out.append(s)
        rows = out
    return render_template('control/list_subjects.html', rows=rows, q=q)


@control_bp.route('/edit_subject/<int:sid>', methods=['GET', 'POST'])
def edit_subject(sid):
    row = Subject.query.get(sid)
    if request.method == 'POST':
        row.code = request.form['code']
        row.name = request.form['name']
        row.summary = request.form['summary']
        row.weeks = request.form['weeks']
        row.state = request.form.get('state', row.state)
        db.session.commit()
        return redirect(url_for('control.list_subjects'))
    return render_template('control/edit_subject.html', row=row)


@control_bp.route('/drop_subject/<int:sid>')
def drop_subject(sid):
    exams = Assessment.query.filter_by(subject_id=sid).all()
    for ex in exams:
        RubricLine.query.filter_by(assessment_id=ex.id).delete()
        ScoreLine.query.filter_by(assessment_id=ex.id).delete()
        FeedbackNote.query.filter_by(assessment_id=ex.id).delete()
        SeatHold.query.filter_by(assessment_id=ex.id).delete()
        TimeSlot.query.filter_by(assessment_id=ex.id).delete()
        db.session.delete(ex)
    db.session.delete(Subject.query.get(sid))
    db.session.commit()
    return redirect(url_for('control.list_subjects'))


@control_bp.route('/add_assessment', methods=['GET', 'POST'])
def add_assessment():
    markers = Account.query.filter_by(role='marker', verified_flag=True, active_flag=True).all()
    subjects = Subject.query.filter_by(state='Active').all()
    if request.method == 'POST':
        hold_date = datetime.strptime(request.form['hold_date'], '%Y-%m-%d').date()
        slot_from = datetime.strptime(request.form['slot_from'], '%Y-%m-%d').date()
        slot_until = datetime.strptime(request.form['slot_until'], '%Y-%m-%d').date()
        book_from = datetime.strptime(request.form['book_from'], '%Y-%m-%d').date()
        book_until = datetime.strptime(request.form['book_until'], '%Y-%m-%d').date()
        msg = None
        if slot_until < slot_from:
            msg = 'Slot end must be on/after slot start.'
        elif book_from <= slot_until:
            msg = 'Booking must start after slot creation ends.'
        elif book_until < book_from:
            msg = 'Booking end must be on/after booking start.'
        elif hold_date < book_until:
            msg = 'Exam date must be on/after booking end.'
        if msg:
            return render_template('control/add_assessment.html', markers=markers, subjects=subjects, msg=msg)

        mid = int(request.form['marker_id'])
        person = Account.query.get(mid)
        row = Assessment(
            name=request.form['name'],
            summary=request.form['summary'],
            kind=request.form.get('kind', 'Assessment'),
            hold_date=hold_date,
            minutes=int(request.form['minutes']),
            total_marks=int(request.form.get('total_marks') or 100),
            slot_from=slot_from,
            slot_until=slot_until,
            book_from=book_from,
            book_until=book_until,
            subject_id=int(request.form['subject_id']),
            marker_id=mid,
            marker_label=person.display_name,
            phase='Draft'
        )
        db.session.add(row)
        db.session.commit()
        return redirect(url_for('control.list_assessments'))
    return render_template('control/add_assessment.html', markers=markers, subjects=subjects)


@control_bp.route('/list_assessments')
def list_assessments():
    q = (request.args.get('q') or '').strip()
    rows = Assessment.query.all()
    if q:
        out = []
        for a in rows:
            if q.isdigit() and int(q) == a.id:
                out.append(a)
            elif q.lower() in (a.name or '').lower():
                out.append(a)
        rows = out
    today = date.today()
    labels = {}
    for a in rows:
        if a.hold_date and a.hold_date < today:
            labels[a.id] = 'Completed'
        elif a.book_open:
            labels[a.id] = 'Booking Open'
        elif a.slot_open:
            labels[a.id] = 'Slot Creation'
        elif a.book_until and today > a.book_until:
            labels[a.id] = 'Closed'
        else:
            labels[a.id] = a.phase or 'Draft'
    return render_template('control/list_assessments.html', rows=rows, q=q, labels=labels)


@control_bp.route('/edit_assessment/<int:aid>', methods=['GET', 'POST'])
def edit_assessment(aid):
    row = Assessment.query.get(aid)
    markers = Account.query.filter_by(role='marker', verified_flag=True, active_flag=True).all()
    subjects = Subject.query.all()
    locked = SeatHold.query.filter_by(assessment_id=row.id, state='Booked').first() is not None
    if request.method == 'POST':
        new_mid = int(request.form['marker_id'])
        hold_date = datetime.strptime(request.form['hold_date'], '%Y-%m-%d').date()
        slot_from = datetime.strptime(request.form['slot_from'], '%Y-%m-%d').date()
        slot_until = datetime.strptime(request.form['slot_until'], '%Y-%m-%d').date()
        book_from = datetime.strptime(request.form['book_from'], '%Y-%m-%d').date()
        book_until = datetime.strptime(request.form['book_until'], '%Y-%m-%d').date()
        msg = None
        if new_mid != row.marker_id and locked:
            msg = 'Cancel bookings before changing marker.'
        elif slot_until < slot_from:
            msg = 'Slot end must be on/after slot start.'
        elif book_from <= slot_until:
            msg = 'Booking must start after slot creation ends.'
        elif book_until < book_from:
            msg = 'Booking end must be on/after booking start.'
        elif hold_date < book_until:
            msg = 'Exam date must be on/after booking end.'
        if msg:
            return render_template(
                'control/edit_assessment.html', row=row, markers=markers,
                subjects=subjects, msg=msg, locked=locked
            )
        row.name = request.form['name']
        row.summary = request.form['summary']
        row.kind = request.form.get('kind', row.kind)
        row.hold_date = hold_date
        row.minutes = int(request.form['minutes'])
        row.total_marks = int(request.form.get('total_marks') or row.total_marks)
        row.slot_from = slot_from
        row.slot_until = slot_until
        row.book_from = book_from
        row.book_until = book_until
        row.subject_id = int(request.form['subject_id'])
        row.marker_id = new_mid
        row.marker_label = Account.query.get(new_mid).display_name
        db.session.commit()
        return redirect(url_for('control.list_assessments'))
    return render_template(
        'control/edit_assessment.html', row=row, markers=markers,
        subjects=subjects, locked=locked
    )


@control_bp.route('/drop_assessment/<int:aid>')
def drop_assessment(aid):
    RubricLine.query.filter_by(assessment_id=aid).delete()
    ScoreLine.query.filter_by(assessment_id=aid).delete()
    FeedbackNote.query.filter_by(assessment_id=aid).delete()
    SeatHold.query.filter_by(assessment_id=aid).delete()
    TimeSlot.query.filter_by(assessment_id=aid).delete()
    db.session.delete(Assessment.query.get(aid))
    db.session.commit()
    return redirect(url_for('control.list_assessments'))


@control_bp.route('/open_slots/<int:aid>')
def open_slots(aid):
    a = Assessment.query.get(aid)
    a.slot_open = True
    a.phase = 'Slot Creation'
    db.session.commit()
    return redirect(url_for('control.list_assessments'))


@control_bp.route('/close_slots/<int:aid>')
def close_slots(aid):
    a = Assessment.query.get(aid)
    a.slot_open = False
    db.session.commit()
    return redirect(url_for('control.list_assessments'))


@control_bp.route('/open_books/<int:aid>')
def open_books(aid):
    a = Assessment.query.get(aid)
    a.book_open = True
    a.slot_open = False
    a.phase = 'Booking Open'
    db.session.commit()
    return redirect(url_for('control.list_assessments'))


@control_bp.route('/close_books/<int:aid>')
def close_books(aid):
    a = Assessment.query.get(aid)
    a.book_open = False
    a.phase = 'Closed'
    db.session.commit()
    return redirect(url_for('control.list_assessments'))


@control_bp.route('/show_results/<int:aid>')
def show_results(aid):
    a = Assessment.query.get(aid)
    a.result_live = True
    db.session.commit()
    return redirect(url_for('control.list_assessments'))


@control_bp.route('/hide_results/<int:aid>')
def hide_results(aid):
    a = Assessment.query.get(aid)
    a.result_live = False
    db.session.commit()
    return redirect(url_for('control.list_assessments'))


@control_bp.route('/add_rubric/<int:aid>', methods=['GET', 'POST'])
def add_rubric(aid):
    if request.method == 'POST':
        line = RubricLine(
            label=request.form['label'],
            max_points=int(request.form['max_points']),
            weight=float(request.form.get('weight') or 1),
            note=request.form.get('note', ''),
            assessment_id=aid
        )
        db.session.add(line)
        db.session.commit()
        return redirect(url_for('control.list_rubrics', aid=aid))
    return render_template('control/add_rubric.html', aid=aid)


@control_bp.route('/list_rubrics/<int:aid>')
def list_rubrics(aid):
    lines = RubricLine.query.filter_by(assessment_id=aid).all()
    return render_template('control/list_rubrics.html', lines=lines, aid=aid)


@control_bp.route('/edit_rubric/<int:rid>', methods=['GET', 'POST'])
def edit_rubric(rid):
    line = RubricLine.query.get(rid)
    if request.method == 'POST':
        line.label = request.form['label']
        line.max_points = int(request.form['max_points'])
        line.weight = float(request.form.get('weight') or 1)
        line.note = request.form.get('note', '')
        db.session.commit()
        return redirect(url_for('control.list_rubrics', aid=line.assessment_id))
    return render_template('control/edit_rubric.html', line=line)


@control_bp.route('/drop_rubric/<int:rid>')
def drop_rubric(rid):
    line = RubricLine.query.get(rid)
    aid = line.assessment_id
    ScoreLine.query.filter_by(rubric_id=line.id).delete()
    db.session.delete(line)
    db.session.commit()
    return redirect(url_for('control.list_rubrics', aid=aid))


@control_bp.route('/list_markers')
def list_markers():
    q = (request.args.get('q') or '').strip()
    rows = Account.query.filter_by(role='marker').all()
    if q:
        out = []
        for u in rows:
            if q.isdigit() and int(q) == u.id:
                out.append(u)
            elif q.lower() in (u.display_name or '').lower() or q.lower() in (u.email or '').lower():
                out.append(u)
        rows = out
    return render_template('control/list_markers.html', rows=rows, q=q)


@control_bp.route('/verify_marker/<int:uid>')
def verify_marker(uid):
    u = Account.query.get(uid)
    u.verified_flag = True
    db.session.commit()
    return redirect(url_for('control.list_markers'))


@control_bp.route('/marker_card/<int:uid>')
def marker_card(uid):
    u = Account.query.get(uid)
    bio = MarkerBio.query.filter_by(account_id=uid).first()
    return render_template('control/marker_card.html', u=u, bio=bio)


@control_bp.route('/list_learners')
def list_learners():
    q = (request.args.get('q') or '').strip()
    rows = Account.query.filter_by(role='learner').all()
    if q:
        out = []
        for u in rows:
            if q.isdigit() and int(q) == u.id:
                out.append(u)
            elif q.lower() in (u.display_name or '').lower() or q.lower() in (u.email or '').lower():
                out.append(u)
        rows = out
    return render_template('control/list_learners.html', rows=rows, q=q)


@control_bp.route('/learner_card/<int:uid>')
def learner_card(uid):
    u = Account.query.get(uid)
    bio = LearnerBio.query.filter_by(account_id=uid).first()
    return render_template('control/learner_card.html', u=u, bio=bio)


@control_bp.route('/freeze_user/<int:uid>')
def freeze_user(uid):
    u = Account.query.get(uid)
    u.active_flag = False
    db.session.commit()
    if u.role == 'marker':
        return redirect(url_for('control.list_markers'))
    return redirect(url_for('control.list_learners'))


@control_bp.route('/unfreeze_user/<int:uid>')
def unfreeze_user(uid):
    u = Account.query.get(uid)
    u.active_flag = True
    db.session.commit()
    if u.role == 'marker':
        return redirect(url_for('control.list_markers'))
    return redirect(url_for('control.list_learners'))


@control_bp.route('/list_slots')
def list_slots():
    q = (request.args.get('q') or '').strip()
    slots = TimeSlot.query.order_by(TimeSlot.day, TimeSlot.start_clock).all()
    exams = {a.id: a for a in Assessment.query.all()}
    markers = {u.id: u for u in Account.query.filter_by(role='marker').all()}
    if q:
        out = []
        for s in slots:
            exam = exams.get(s.assessment_id)
            marker = markers.get(s.marker_id)
            if q.isdigit() and int(q) == s.id:
                out.append(s)
            elif exam and q.lower() in (exam.name or '').lower():
                out.append(s)
            elif marker and q.lower() in (marker.display_name or '').lower():
                out.append(s)
        slots = out
    counts = {}
    for h in SeatHold.query.filter_by(state='Booked').all():
        counts[h.slot_id] = counts.get(h.slot_id, 0) + 1
    return render_template(
        'control/list_slots.html', slots=slots, exams=exams,
        markers=markers, counts=counts, q=q
    )


@control_bp.route('/list_holds')
def list_holds():
    q = (request.args.get('q') or '').strip()
    holds = SeatHold.query.all()
    exams = {a.id: a for a in Assessment.query.all()}
    learners = {u.id: u for u in Account.query.filter_by(role='learner').all()}
    slots = {s.id: s for s in TimeSlot.query.all()}
    today = date.today()
    dirty = False
    for h in holds:
        if h.state == 'Booked':
            exam = exams.get(h.assessment_id)
            if exam and exam.hold_date and exam.hold_date < today:
                h.state = 'Completed'
                dirty = True
    if dirty:
        db.session.commit()
    if q:
        out = []
        for h in holds:
            exam = exams.get(h.assessment_id)
            learner = learners.get(h.learner_id)
            if q.isdigit() and (int(q) == h.id or int(q) == h.learner_id or int(q) == h.assessment_id):
                out.append(h)
            elif learner and q.lower() in (learner.display_name or '').lower():
                out.append(h)
            elif exam and q.lower() in (exam.name or '').lower():
                out.append(h)
        holds = out
    return render_template(
        'control/list_holds.html', holds=holds, exams=exams,
        slots=slots, learners=learners, q=q
    )


@control_bp.route('/move_hold/<int:hid>', methods=['GET', 'POST'])
def move_hold(hid):
    hold = SeatHold.query.get(hid)
    if not hold or hold.state == 'Cancelled':
        return redirect(url_for('control.list_holds'))
    exam = Assessment.query.get(hold.assessment_id)
    all_slots = TimeSlot.query.filter_by(assessment_id=exam.id).order_by(TimeSlot.day, TimeSlot.start_clock).all()
    free = []
    for s in all_slots:
        taken = SeatHold.query.filter_by(slot_id=s.id, state='Booked').count()
        if s.id == hold.slot_id or taken < s.capacity:
            free.append(s)
    msg = None
    if request.method == 'POST':
        new_slot = TimeSlot.query.get(int(request.form['slot_id']))
        if not new_slot or new_slot.assessment_id != exam.id:
            msg = 'Pick a valid slot.'
        else:
            taken = SeatHold.query.filter_by(slot_id=new_slot.id, state='Booked').count()
            if new_slot.id != hold.slot_id and taken >= new_slot.capacity:
                msg = 'That slot is full.'
            else:
                old = TimeSlot.query.get(hold.slot_id)
                hold.slot_id = new_slot.id
                hold.state = 'Booked'
                if old:
                    old_taken = SeatHold.query.filter_by(slot_id=old.id, state='Booked').count()
                    old.free_seats = old.capacity - old_taken
                    old.state = 'Full' if old_taken >= old.capacity else 'Available'
                new_taken = SeatHold.query.filter_by(slot_id=new_slot.id, state='Booked').count()
                new_slot.free_seats = new_slot.capacity - new_taken
                new_slot.state = 'Full' if new_taken >= new_slot.capacity else 'Available'
                db.session.commit()
                return redirect(url_for('control.list_holds'))
    return render_template('control/move_hold.html', hold=hold, exam=exam, slots=free, msg=msg)


@control_bp.route('/cancel_hold/<int:hid>')
def cancel_hold(hid):
    hold = SeatHold.query.get(hid)
    if hold and hold.state == 'Booked':
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
    return redirect(url_for('control.list_holds'))

from flask import Blueprint, render_template, request, redirect, url_for, session
from models import *
from datetime import datetime, date, timedelta

marker_bp = Blueprint('marker', __name__)


@marker_bp.before_request
def need_marker():
    if session.get('role') != 'marker':
        return redirect(url_for('home_page'))
    person = Account.query.get(session.get('uid'))
    if not person or not person.verified_flag or not person.active_flag:
        session.pop('uid', None)
        session.pop('role', None)
        return redirect(url_for('access.sign_in'))


@marker_bp.route('/home')
def marker_home():
    uid = session.get('uid')
    person = Account.query.get(uid)
    bio = MarkerBio.query.filter_by(account_id=uid).first()
    exams = Assessment.query.filter_by(marker_id=uid).all()
    slots = TimeSlot.query.filter_by(marker_id=uid).all()
    ids = [e.id for e in exams]
    holds = []
    if ids:
        holds = SeatHold.query.filter(
            SeatHold.assessment_id.in_(ids),
            SeatHold.state.in_(['Booked', 'Completed'])
        ).all()
    waiting = 0
    for h in holds:
        if not ScoreLine.query.filter_by(assessment_id=h.assessment_id, learner_id=h.learner_id).first():
            waiting += 1
    return render_template(
        'marker/home.html',
        person=person, bio=bio, exams=exams, slots=slots,
        holds=holds, waiting=waiting
    )


@marker_bp.route('/make_bio', methods=['GET', 'POST'])
def make_bio():
    uid = session.get('uid')
    person = Account.query.get(uid)
    bio = MarkerBio.query.filter_by(account_id=uid).first()
    if request.method == 'POST':
        person.display_name = request.form['display_name']
        person.email = request.form['email']
        if bio:
            bio.dept = request.form['dept']
            bio.office = request.form['office']
            bio.phone = request.form['phone']
            bio.years = request.form['years']
        else:
            bio = MarkerBio(
                dept=request.form['dept'],
                phone=request.form['phone'],
                office=request.form['office'],
                years=request.form['years'],
                account_id=uid
            )
            db.session.add(bio)
        db.session.commit()
        return redirect(url_for('marker.marker_home'))
    return render_template('marker/make_bio.html', person=person, bio=bio)


@marker_bp.route('/edit_bio', methods=['GET', 'POST'])
def edit_bio():
    uid = session.get('uid')
    bio = MarkerBio.query.filter_by(account_id=uid).first()
    if not bio:
        return redirect(url_for('marker.make_bio'))
    if request.method == 'POST':
        bio.dept = request.form['dept']
        bio.office = request.form['office']
        bio.phone = request.form['phone']
        bio.years = request.form['years']
        db.session.commit()
        return redirect(url_for('marker.marker_home'))
    return render_template('marker/edit_bio.html', bio=bio)


@marker_bp.route('/my_exams')
def my_exams():
    exams = Assessment.query.filter_by(marker_id=session.get('uid')).all()
    subjects = {s.id: s for s in Subject.query.all()}
    return render_template('marker/my_exams.html', exams=exams, subjects=subjects)


@marker_bp.route('/manage_slots/<int:aid>', methods=['GET', 'POST'])
def manage_slots(aid):
    uid = session.get('uid')
    exam = Assessment.query.get(aid)
    if not exam or exam.marker_id != uid:
        return redirect(url_for('marker.my_exams'))
    msg = None
    if request.method == 'POST':
        if not exam.slot_open:
            msg = 'Admin closed slot creation.'
        else:
            try:
                day = datetime.strptime(request.form['day'], '%Y-%m-%d').date()
                start_clock = datetime.strptime(request.form['start_clock'], '%H:%M').time()
                capacity = int(request.form.get('capacity') or 1)
            except (ValueError, TypeError):
                msg = 'Enter valid date, time and capacity.'
                day = None
                start_clock = None
                capacity = 0
            if not msg:
                if day < exam.slot_from or day > exam.slot_until:
                    msg = 'Date must be between {} and {}.'.format(exam.slot_from, exam.slot_until)
                elif capacity < 1:
                    msg = 'Capacity must be at least 1.'
                elif TimeSlot.query.filter_by(
                    assessment_id=exam.id, day=day, start_clock=start_clock, marker_id=uid
                ).first():
                    msg = 'Slot already exists at this time.'
                else:
                    end_dt = datetime.combine(day, start_clock) + timedelta(minutes=exam.minutes)
                    slot = TimeSlot(
                        assessment_id=exam.id,
                        day=day,
                        start_clock=start_clock,
                        end_clock=end_dt.time(),
                        marker_id=uid,
                        capacity=capacity,
                        free_seats=capacity,
                        state='Available'
                    )
                    db.session.add(slot)
                    db.session.commit()
                    return redirect(url_for('marker.manage_slots', aid=exam.id))

    slots = TimeSlot.query.filter_by(assessment_id=exam.id, marker_id=uid).order_by(
        TimeSlot.day, TimeSlot.start_clock
    ).all()
    by_slot = {}
    people = {}
    for slot in slots:
        rows = SeatHold.query.filter_by(slot_id=slot.id, state='Booked').all()
        by_slot[slot.id] = rows
        for h in rows:
            people[h.learner_id] = Account.query.get(h.learner_id)
    return render_template(
        'marker/manage_slots.html',
        exam=exam, slots=slots, msg=msg, by_slot=by_slot, people=people,
        book_started=exam.book_open, creation_open=exam.slot_open,
        locked=request.args.get('locked')
    )


@marker_bp.route('/edit_slot/<int:sid>', methods=['GET', 'POST'])
def edit_slot(sid):
    slot = TimeSlot.query.get(sid)
    exam = Assessment.query.get(slot.assessment_id) if slot else None
    if not slot or not exam or exam.marker_id != session.get('uid'):
        return redirect(url_for('marker.my_exams'))
    if exam.book_open or SeatHold.query.filter_by(slot_id=slot.id, state='Booked').first():
        return redirect(url_for('marker.manage_slots', aid=exam.id, locked=1))
    msg = None
    if request.method == 'POST':
        try:
            day = datetime.strptime(request.form['day'], '%Y-%m-%d').date()
            start_clock = datetime.strptime(request.form['start_clock'], '%H:%M').time()
            capacity = int(request.form.get('capacity') or slot.capacity)
        except (ValueError, TypeError):
            msg = 'Enter valid date, time and capacity.'
            day = None
            start_clock = None
            capacity = 0
        if not msg:
            if day < exam.slot_from or day > exam.slot_until:
                msg = 'Date must stay between {} and {}.'.format(exam.slot_from, exam.slot_until)
            elif capacity < 1:
                msg = 'Capacity must be at least 1.'
            else:
                other = TimeSlot.query.filter_by(
                    assessment_id=exam.id, day=day, start_clock=start_clock, marker_id=session.get('uid')
                ).first()
                if other and other.id != slot.id:
                    msg = 'Slot already exists at this time.'
                else:
                    end_dt = datetime.combine(day, start_clock) + timedelta(minutes=exam.minutes)
                    slot.day = day
                    slot.start_clock = start_clock
                    slot.end_clock = end_dt.time()
                    slot.capacity = capacity
                    slot.free_seats = capacity
                    db.session.commit()
                    return redirect(url_for('marker.manage_slots', aid=exam.id))
    return render_template('marker/edit_slot.html', exam=exam, slot=slot, msg=msg)


@marker_bp.route('/drop_slot/<int:sid>')
def drop_slot(sid):
    slot = TimeSlot.query.get(sid)
    exam = Assessment.query.get(slot.assessment_id) if slot else None
    if not slot or not exam or slot.marker_id != session.get('uid'):
        return redirect(url_for('marker.my_exams'))
    if exam.book_open or SeatHold.query.filter_by(slot_id=slot.id, state='Booked').first():
        return redirect(url_for('marker.manage_slots', aid=exam.id, locked=1))
    db.session.delete(slot)
    db.session.commit()
    return redirect(url_for('marker.manage_slots', aid=exam.id))


@marker_bp.route('/see_holds')
def see_holds():
    uid = session.get('uid')
    exams = Assessment.query.filter_by(marker_id=uid).all()
    ids = [e.id for e in exams]
    holds = []
    if ids:
        holds = SeatHold.query.filter(
            SeatHold.assessment_id.in_(ids),
            SeatHold.state.in_(['Booked', 'Completed'])
        ).all()
    exam_map = {e.id: e for e in exams}
    slot_map = {s.id: s for s in TimeSlot.query.filter(TimeSlot.id.in_([h.slot_id for h in holds])).all()} if holds else {}
    people = {u.id: u for u in Account.query.filter(Account.id.in_([h.learner_id for h in holds])).all()} if holds else {}
    scores = {}
    for h in holds:
        given = ScoreLine.query.filter_by(assessment_id=h.assessment_id, learner_id=h.learner_id).all()
        lines = RubricLine.query.filter_by(assessment_id=h.assessment_id).all()
        awarded = sum(g.points for g in given) if given else None
        possible = sum(l.max_points for l in lines)
        scores[h.id] = {'awarded': awarded, 'possible': possible}
    return render_template(
        'marker/see_holds.html', holds=holds, exam_map=exam_map,
        slot_map=slot_map, people=people, scores=scores
    )


@marker_bp.route('/hold_card/<int:hid>')
def hold_card(hid):
    hold = SeatHold.query.get(hid)
    exam = Assessment.query.get(hold.assessment_id) if hold else None
    if not hold or not exam or exam.marker_id != session.get('uid'):
        return redirect(url_for('marker.see_holds'))
    learner = Account.query.get(hold.learner_id)
    bio = LearnerBio.query.filter_by(account_id=learner.id).first()
    slot = TimeSlot.query.get(hold.slot_id)
    note = FeedbackNote.query.filter_by(assessment_id=exam.id, learner_id=learner.id).first()
    return render_template(
        'marker/hold_card.html', hold=hold, exam=exam, learner=learner,
        bio=bio, slot=slot, note=note
    )


@marker_bp.route('/grade/<int:hid>', methods=['GET', 'POST'])
def grade(hid):
    hold = SeatHold.query.get(hid)
    exam = Assessment.query.get(hold.assessment_id) if hold else None
    if not hold or not exam or exam.marker_id != session.get('uid') or hold.state == 'Cancelled':
        return redirect(url_for('marker.see_holds'))
    learner = Account.query.get(hold.learner_id)
    lines = RubricLine.query.filter_by(assessment_id=exam.id).all()
    saved = {}
    for s in ScoreLine.query.filter_by(assessment_id=exam.id, learner_id=learner.id).all():
        saved[s.rubric_id] = s
    note = FeedbackNote.query.filter_by(assessment_id=exam.id, learner_id=learner.id).first()
    msg = None
    if request.method == 'POST':
        values = {}
        for line in lines:
            raw = (request.form.get('points_' + str(line.id)) or '').strip()
            try:
                val = int(raw)
            except ValueError:
                msg = 'Enter a whole number for every line.'
                break
            if val < 0 or val > line.max_points:
                msg = 'Points for "{}" must be 0 to {}.'.format(line.label, line.max_points)
                break
            values[line.id] = val
        if not msg and not lines:
            msg = 'No rubric yet. Ask admin to add one.'
        if not msg:
            for line in lines:
                row = saved.get(line.id)
                if row:
                    row.points = values[line.id]
                    row.marker_id = session.get('uid')
                else:
                    db.session.add(ScoreLine(
                        assessment_id=exam.id,
                        learner_id=learner.id,
                        rubric_id=line.id,
                        points=values[line.id],
                        marker_id=session.get('uid')
                    ))
            text = (request.form.get('text') or '').strip()
            if note:
                note.text = text or note.text
                note.marker_id = session.get('uid')
            elif text:
                db.session.add(FeedbackNote(
                    assessment_id=exam.id,
                    learner_id=learner.id,
                    text=text,
                    marker_id=session.get('uid')
                ))
            db.session.commit()
            return redirect(url_for('marker.see_holds'))
    return render_template(
        'marker/grade.html', exam=exam, learner=learner, lines=lines,
        saved=saved, note=note, msg=msg
    )

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app import get_db_connection

event_bp = Blueprint('event', __name__)

@event_bp.route('/create_event', methods=['GET', 'POST'])
def create_event():
    if 'user_id' not in session or session.get('role') != 'organizer':
        flash('Access denied!', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        event_name = request.form.get('event_name').strip()
        event_date = request.form.get('event_date').strip()
        event_description = request.form.get('event_description').strip()

        if not event_name or not event_date or not event_description:
            flash('All fields are required!', 'error')
            return redirect(url_for('event.create_event'))

        conn = get_db_connection()
        if not conn:
            return redirect(url_for('dashboard'))

        cursor = conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO events (name, date, description, organizer_id) VALUES (%s, %s, %s, %s)',
                (event_name, event_date, event_description, session['user_id'])
            )
            conn.commit()
            flash('Event created successfully!', 'success')
        except Exception as e:
            flash(f'Error creating event: {e}', 'error')
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for('dashboard'))

    return render_template('create_event.html')

@event_bp.route('/events')
def view_events():
    conn = get_db_connection()
    if not conn:
        return redirect(url_for('dashboard'))

    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM events')
    events = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('events.html', events=events)

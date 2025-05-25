from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_bcrypt import Bcrypt
import mysql.connector
import secrets
from datetime import datetime

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # Or use a fixed string for development
bcrypt = Bcrypt(app)

# Database configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'priya@9841',
    'database': 'eventlogin'
}

def get_db_connection():
    try:
        return mysql.connector.connect(**db_config)
    except mysql.connector.Error as err:
        flash(f'Database connection error: {err}', 'error')
        return None

def is_event_past(event_date):
    try:
        return datetime.now() > datetime.strptime(str(event_date), '%Y-%m-%d')
    except:
        return False


@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password').strip()
        role = request.form.get('role')

        if not username or not password or not role:
            flash('All fields are required!', 'error')
            return redirect(url_for('login'))

        conn = get_db_connection()
        if not conn:
            return redirect(url_for('login'))

        cursor = None
        try:
            cursor = conn.cursor(buffered=True, dictionary=True)
            cursor.execute(
                'SELECT * FROM accounts WHERE username = %s AND role = %s',
                (username, role)
            )
            user = cursor.fetchone()
            
            if user and bcrypt.check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = user['role'].strip().lower()
                flash('Login successful!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid username or password!', 'error')
                
        except mysql.connector.Error as err:
            flash(f'Database error: {err}', 'error')
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        email = request.form.get('email').strip()
        password = request.form.get('password').strip()
        role = request.form.get('role')

        if not username or not email or not password or not role:
            flash('All fields are required!', 'error')
            return redirect(url_for('register'))

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        conn = get_db_connection()
        if not conn:
            return redirect(url_for('register'))

        cursor = conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO accounts (username, email, password, role) VALUES (%s, %s, %s, %s)',
                (username, email, hashed_password, role)
            )
            conn.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except mysql.connector.IntegrityError:
            flash('Username or email already exists!', 'error')
        except mysql.connector.Error as err:
            flash(f'Database error: {err}', 'error')
        finally:
            cursor.close()
            conn.close()

    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('You need to login first!', 'error')
        return redirect(url_for('login'))

    role = session['role']
    conn = get_db_connection()
    if not conn:
        flash('Database connection failed!', 'error')
        return redirect(url_for('login'))

    cursor = None
    try:
        cursor = conn.cursor(buffered=True, dictionary=True)
        
        if role == 'participant':
            # Fetch all events
            cursor.execute("SELECT * FROM events WHERE event_date >= CURDATE()")
            events = cursor.fetchall()

            # Fetch event IDs that the participant has registered for
            cursor.execute(
                "SELECT event_id FROM registrations WHERE participant_id = %s",
                (session['user_id'],)
            )
            registered_events = cursor.fetchall()
            registered_event_ids = [reg['event_id'] for reg in registered_events]

            return render_template('participant_dashboard.html', 
                                events=events, 
                                registered_event_ids=registered_event_ids)

        elif role == 'organizer':
            # Organizer dashboard code remains the same
            # In organizer dashboard route
            cursor.execute("""
                SELECT * FROM events 
                WHERE organizer_id = %s 
                AND event_date >= CURDATE()
            """, (session['user_id'],))
            events = cursor.fetchall()
            return render_template('organizer_dashboard.html', events=events)

    except mysql.connector.Error as err:
        flash(f'Database error: {err}', 'error')
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/create_event', methods=['GET', 'POST'])
def create_event():
    if 'user_id' not in session or session.get('role') != 'organizer':
        flash('Access denied!', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        event_name = request.form['event_name']
        description = request.form['description']
        event_date = request.form['event_date']
        location = request.form['location']
        organizer_id = session['user_id']

        conn = get_db_connection()
        if not conn:
            return redirect(url_for('dashboard'))

        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO events (event_name, description, event_date, location, organizer_id) VALUES (%s, %s, %s, %s, %s)",
                (event_name, description, event_date, location, organizer_id)
            )
            conn.commit()
            flash('Event created successfully!', 'success')
            return redirect(url_for('dashboard'))

        except mysql.connector.Error as err:
            flash(f'Database error: {err}', 'error')

        finally:
            cursor.close()
            conn.close()

    return render_template('create_event.html')

@app.route('/register_event/<int:event_id>', methods=['GET', 'POST'])
def register_event(event_id):
    if 'user_id' not in session or session.get('role') != 'participant':
        flash('Access denied!', 'error')
        return redirect(url_for('dashboard'))

    participant_id = session['user_id']
    conn = get_db_connection()
    
    if request.method == 'POST':
        cursor = None
        try:
            # Get form data
            form_data = {
                'full_name': request.form['full_name'],
                'gender': request.form['gender'],
                'phone': request.form['phone'],
                'department': request.form['department'],
                'college': request.form['college'],
                'email': request.form['email'],
                'event_id': event_id,
                'participant_id': participant_id
            }

            cursor = conn.cursor()
            
            # Check if already registered
            cursor.execute(
                "SELECT * FROM registrations WHERE event_id = %s AND participant_id = %s",
                (event_id, participant_id)
            )
            if cursor.fetchone():
                flash('You are already registered for this event!', 'warning')
                return redirect(url_for('dashboard'))

            # Insert new registration
            cursor.execute(
                """INSERT INTO registrations 
                (event_id, participant_id, full_name, gender, phone, department, college, email)
                VALUES (%(event_id)s, %(participant_id)s, %(full_name)s, %(gender)s, 
                %(phone)s, %(department)s, %(college)s, %(email)s)""",
                form_data
            )
            conn.commit()
            flash('Successfully registered for the event!', 'success')
            return redirect(url_for('my_events'))

        except KeyError as e:
            flash(f'Missing required field: {e}', 'error')
            return redirect(url_for('register_event', event_id=event_id))
        except mysql.connector.Error as err:
            conn.rollback()
            flash(f'Registration failed: {err}', 'error')
            return redirect(url_for('dashboard'))
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    # GET request - show registration form
    return render_template('register_event.html', event_id=event_id)

# View Participants for an Event (Organizer Only)
@app.route('/event_participants/<int:event_id>')
def event_participants(event_id):
    if 'user_id' not in session or session.get('role') != 'organizer':
        flash('Access denied!', 'error')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    if not conn:
        return redirect(url_for('dashboard'))

    cursor = conn.cursor(dictionary=True)
    try:
        # Fetch event details
        cursor.execute("SELECT * FROM events WHERE id = %s", (event_id,))
        event = cursor.fetchone()

        # Fetch registered participants
        cursor.execute(
            "SELECT a.username, a.email FROM registrations r "
            "JOIN accounts a ON r.participant_id = a.id "
            "WHERE r.event_id = %s", (event_id,)
        )
        participants = cursor.fetchall()

        return render_template('event_participants.html', event=event, participants=participants)

    except mysql.connector.Error as err:
        flash(f'Database error: {err}', 'error')
        return redirect(url_for('dashboard'))

    finally:
        cursor.close()
        conn.close()

@app.route('/my_events')
def my_events():
    if 'user_id' not in session or session['role'] != 'participant':
        flash('Access denied!', 'error')
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
                    SELECT e.id, e.event_name, e.event_date, e.location, e.description 
                    FROM registrations r
                    JOIN events e ON r.event_id = e.id
                    WHERE r.participant_id = %s AND e.event_date >= CURDATE()
                """, (session['user_id'],))
        
        registrations = cursor.fetchall()
        return render_template('my_events.html', 
                             registrations=registrations,
                             username=session.get('username'))
    
    except mysql.connector.Error as err:
        flash(f'Database error: {err}', 'error')
        return redirect(url_for('dashboard'))
    finally:
        cursor.close()
        conn.close()


@app.route('/feedback')
def feedback():
    if 'user_id' not in session:
        flash('Please login to view feedback', 'error')
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get past events with registrations but no feedback
        cursor.execute("""
            SELECT e.id, e.event_name, e.event_date 
            FROM registrations r
            JOIN events e ON r.event_id = e.id
            LEFT JOIN feedback f 
                ON f.event_id = e.id 
                AND f.participant_id = r.participant_id
            WHERE r.participant_id = %s 
                AND DATE(e.event_date) < CURDATE()
                AND f.id IS NULL
        """, (session['user_id'],))
        
        feedback_events = cursor.fetchall()
        return render_template('feedback.html', events=feedback_events)
    
    except mysql.connector.Error as err:
        flash(f'Database error: {err}', 'error')
        return redirect(url_for('dashboard'))
    finally:
        cursor.close()
        conn.close()

@app.route('/submit_feedback/<int:event_id>', methods=['GET', 'POST'])
def submit_feedback(event_id):
    if 'user_id' not in session or session.get('role') != 'participant':
        flash('Access denied!', 'error')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Get event details
        cursor.execute("SELECT * FROM events WHERE id = %s", (event_id,))
        event = cursor.fetchone()

        if not event:
            flash('Event not found', 'error')
            return redirect(url_for('feedback'))

        # Format the event_date if it's a string
        try:
            if isinstance(event['event_date'], str):
                event_date_obj = datetime.strptime(event['event_date'], '%Y-%m-%d')
            else:
                event_date_obj = event['event_date']
            event['formatted_date'] = event_date_obj.strftime('%B %d, %Y')
        except Exception:
            event['formatted_date'] = event['event_date']  # fallback

        if request.method == 'POST':
            form_data = {
                'event_id': event_id,
                'participant_id': session['user_id'],
                'venue_rating': int(request.form['venue']),
                'coordinators_rating': int(request.form['coordinators']),
                'time_rating': int(request.form['time']),
                'helpfulness_rating': int(request.form['helpfulness']),
                'comments': request.form.get('comments', '')
            }

            cursor.execute("""
                INSERT INTO feedback 
                (event_id, participant_id, venue_rating, coordinators_rating, 
                 time_rating, helpfulness_rating, comments)
                VALUES (%(event_id)s, %(participant_id)s, %(venue_rating)s, 
                        %(coordinators_rating)s, %(time_rating)s, 
                        %(helpfulness_rating)s, %(comments)s)
            """, form_data)

            conn.commit()
            flash('Feedback submitted successfully!', 'success')
            return redirect(url_for('feedback'))

        return render_template('feedback_form.html', event=event)

    except ValueError:
        flash('Please provide valid ratings', 'error')
    except mysql.connector.Error as err:
        conn.rollback()
        flash(f'Database error: {err}', 'error')
    finally:
        cursor.close()
        conn.close()


@app.route('/event_feedback/<int:event_id>')
def event_feedback(event_id):
    if 'user_id' not in session or session.get('role') != 'organizer':
        flash('Access denied!', 'error')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get event details
        cursor.execute("SELECT * FROM events WHERE id = %s", (event_id,))
        event = cursor.fetchone()

        # Get feedback
        cursor.execute("""
            SELECT f.*, a.username 
            FROM feedback f
            JOIN accounts a ON f.participant_id = a.id
            WHERE f.event_id = %s
        """, (event_id,))
        feedbacks = cursor.fetchall()

        return render_template('event_feedback.html', 
                             event=event, 
                             feedbacks=feedbacks)

    except mysql.connector.Error as err:
        flash(f'Database error: {err}', 'error')
        return redirect(url_for('dashboard'))
    finally:
        cursor.close()
        conn.close()

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

from flask import render_template, request, redirect, url_for, flash

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        # Here, you can save the updated settings to the database
        flash("Changes saved successfully!")
        return redirect(url_for('settings'))  # This will reload the settings page with the flash message
    return render_template('settings.html')


@app.route('/participant_dashboard')
def participant_dashboard():
    # Your logic here
    return render_template('participant_dashboard.html')

from flask import Flask, render_template

# Feedback Analysis Route
@app.route('/feedback_analysis')
def feedback_analysis():
    if 'user_id' not in session or session.get('role') != 'organizer':
        flash('Access denied!', 'error')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get events with feedback count
        cursor.execute("""
            SELECT e.id, e.event_name, e.event_date, e.location, COUNT(f.id) as feedback_count
            FROM events e
            LEFT JOIN feedback f ON e.id = f.event_id
            WHERE e.organizer_id = %s
            GROUP BY e.id
            HAVING feedback_count > 0
            ORDER BY e.event_date DESC
        """, (session['user_id'],))
        
        events = cursor.fetchall()
        return render_template('feedback_analysis.html', events=events)
    
    except mysql.connector.Error as err:
        flash(f'Database error: {err}', 'error')
        return redirect(url_for('dashboard'))
    finally:
        cursor.close()
        conn.close()

@app.route('/event_feedback_analysis/<int:event_id>')
def event_feedback_analysis(event_id):
    if 'user_id' not in session or session.get('role') != 'organizer':
        flash('Access denied!', 'error')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get event details
        cursor.execute("SELECT * FROM events WHERE id = %s", (event_id,))
        event = cursor.fetchone()
        
        if not event:
            flash('Event not found', 'error')
            return redirect(url_for('feedback_analysis'))

        # Get feedback averages
        cursor.execute("""
            SELECT
                AVG(venue_rating) as venue,
                AVG(coordinators_rating) as coordinators,
                AVG(time_rating) as time,
                AVG(helpfulness_rating) as helpfulness
            FROM feedback
            WHERE event_id = %s
        """, (event_id,))
        
        averages = cursor.fetchone()
        
        # Get individual feedback with usernames
        cursor.execute("""
            SELECT f.*, a.username
            FROM feedback f
            JOIN accounts a ON f.participant_id = a.id
            WHERE f.event_id = %s
            ORDER BY f.submission_date DESC
        """, (event_id,))
        
        feedbacks = cursor.fetchall()
        
        return render_template('event_feedback_analysis.html',
                             event=event,
                             averages=averages,
                             feedbacks=feedbacks)
    
    except mysql.connector.Error as err:
        flash(f'Database error: {err}', 'error')
        return redirect(url_for('feedback_analysis'))
    finally:
        cursor.close()
        conn.close()

@app.route('/leaderboard')
def leaderboard():
    if 'user_id' not in session or session.get('role') != 'organizer':
        flash('Access denied!', 'error')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get events organized by this user
        cursor.execute("""
            SELECT e.id, e.event_name 
            FROM events e
            WHERE e.organizer_id = %s
            ORDER BY e.event_date DESC
        """, (session['user_id'],))
        
        events = cursor.fetchall()
        return render_template('organizer_leaderboard.html', events=events)
    
    except mysql.connector.Error as err:
        flash(f'Database error: {err}', 'error')
        return redirect(url_for('dashboard'))
    finally:
        cursor.close()
        conn.close()


@app.route('/update_leaderboard/<int:event_id>', methods=['GET', 'POST'])
def update_leaderboard(event_id):
    if 'user_id' not in session:
        flash('Please login first', 'error')
        return redirect(url_for('login'))
    
    if session.get('role') != 'organizer':
        flash('Organizer access required', 'error')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT * FROM events WHERE id = %s", (event_id,))
        event = cursor.fetchone()
        
        if request.method == 'POST':
            # Directly process form data without CSRF validation
            first_place = request.form.get('first_place')
            second_place = request.form.get('second_place')
            third_place = request.form.get('third_place')
            
            cursor.execute("SELECT * FROM leaderboard WHERE event_id = %s", (event_id,))
            existing = cursor.fetchone()
            
            if existing:
                cursor.execute("""
                    UPDATE leaderboard 
                    SET first_place = %s, second_place = %s, third_place = %s
                    WHERE event_id = %s
                """, (first_place, second_place, third_place, event_id))
            else:
                cursor.execute("""
                    INSERT INTO leaderboard 
                    (event_id, first_place, second_place, third_place)
                    VALUES (%s, %s, %s, %s)
                """, (event_id, first_place, second_place, third_place))
            
            conn.commit()
            flash('Leaderboard updated successfully!', 'success')
            return redirect(url_for('leaderboard'))
        
        cursor.execute("SELECT * FROM leaderboard WHERE event_id = %s", (event_id,))
        leaderboard_data = cursor.fetchone()
        
        return render_template('update_leaderboard.html', 
                             event=event, 
                             leaderboard=leaderboard_data)
    
    except mysql.connector.Error as err:
        flash(f'Database error: {err}', 'error')
        return redirect(url_for('leaderboard'))
    finally:
        cursor.close()
        conn.close()


@app.route('/participant_leaderboard')
def participant_leaderboard():
    if 'user_id' not in session or session.get('role') != 'participant':
        flash('Access denied!', 'error')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get events the participant is registered for
        cursor.execute("""
            SELECT e.id, e.event_name 
            FROM registrations r
            JOIN events e ON r.event_id = e.id
            WHERE r.participant_id = %s
            ORDER BY e.event_date DESC
        """, (session['user_id'],))
        
        events = cursor.fetchall()
        return render_template('participant_leaderboard.html', events=events)
    
    except mysql.connector.Error as err:
        flash(f'Database error: {err}', 'error')
        return redirect(url_for('dashboard'))
    finally:
        cursor.close()
        conn.close()

@app.route('/view_leaderboard/<int:event_id>')
def view_leaderboard(event_id):
    if 'user_id' not in session or session.get('role') != 'participant':
        flash('Access denied!', 'error')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get event details
        cursor.execute("SELECT * FROM events WHERE id = %s", (event_id,))
        event = cursor.fetchone()
        
        # Get leaderboard
        cursor.execute("""
            SELECT first_place, second_place, third_place 
            FROM leaderboard 
            WHERE event_id = %s
        """, (event_id,))
        
        leaderboard = cursor.fetchone()
        
        return render_template('view_leaderboard.html', 
                             event=event, 
                             leaderboard=leaderboard)
    
    except mysql.connector.Error as err:
        flash(f'Database error: {err}', 'error')
        return redirect(url_for('participant_leaderboard'))
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    app.run(debug=True)
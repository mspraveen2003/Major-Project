from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Change to a strong secret key

DATABASE = 'database.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# Initialize DB with tables if not exist
def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                fullname TEXT,
                email TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                start_hour INTEGER NOT NULL,
                end_hour INTEGER NOT NULL
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                service_id INTEGER NOT NULL,
                place_name TEXT NOT NULL,
                booking_time TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(service_id) REFERENCES services(id)
            )
        ''')

init_db()

# User registration route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']  # In production, hash passwords!
        fullname = request.form['fullname']
        email = request.form['email']
        with get_db() as conn:
            try:
                conn.execute("INSERT INTO users (username, password, fullname, email) VALUES (?, ?, ?, ?)",
                             (username, password, fullname, email))
                flash('Registration successful! Please log in.', 'success')
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                flash('Username already exists.', 'error')
    return render_template('register.html')

# Login route
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with get_db() as conn:
            user = conn.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password)).fetchone()
            if user:
                session['user_id'] = user['id']
                session['username'] = user['username']
                return redirect(url_for('profile'))
            else:
                flash('Invalid username or password', 'error')
    return render_template('login.html')

# User profile - show details & allow edit
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    with get_db() as conn:
        if request.method == 'POST':
            fullname = request.form['fullname']
            email = request.form['email']
            conn.execute("UPDATE users SET fullname=?, email=? WHERE id=?", (fullname, email, user_id))
            flash('Profile updated.', 'success')
        user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return render_template('profile.html', user=user)

# Select service
@app.route('/select_service', methods=['GET', 'POST'])
def select_service():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    with get_db() as conn:
        services = conn.execute("SELECT * FROM services").fetchall()
        if request.method == 'POST':
            service_id = request.form['service_id']
            return redirect(url_for('book_appointment', service_id=service_id))
    return render_template('select_service.html', services=services)

# Book appointment with slot suggestions
@app.route('/book/<int:service_id>', methods=['GET', 'POST'])
def book_appointment(service_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    with get_db() as conn:
        service = conn.execute("SELECT * FROM services WHERE id=?", (service_id,)).fetchone()
        if not service:
            flash('Service not found', 'error')
            return redirect(url_for('select_service'))

        # Generate slots for today and tomorrow based on service hours
        def generate_slots_for_day(base_date, start_hour, end_hour):
            return [base_date.replace(hour=h, minute=0, second=0, microsecond=0)
                    for h in range(start_hour, end_hour)]

        now = datetime.now()
        today = now.date()
        tomorrow = today + timedelta(days=1)

        # Fetch booked slots for this service (all places considered same here)
        booked_times = conn.execute(
            "SELECT booking_time FROM bookings WHERE service_id=?", (service_id,)
        ).fetchall()
        booked_slots = set(datetime.fromisoformat(b['booking_time']) for b in booked_times)

        # Generate available slots today and tomorrow excluding booked slots
        today_slots = generate_slots_for_day(datetime.combine(today, datetime.min.time()),
                                             service['start_hour'], service['end_hour'])
        available_today = [slot for slot in today_slots if slot > now and slot not in booked_slots]

        tomorrow_slots = generate_slots_for_day(datetime.combine(tomorrow, datetime.min.time()),
                                                service['start_hour'], service['end_hour'])
        available_tomorrow = [slot for slot in tomorrow_slots if slot not in booked_slots]

        # Show tomorrow slots if today none available
        available_slots = available_today if available_today else available_tomorrow

        if request.method == 'POST':
            selected_time_idx = int(request.form['slot'])
            chosen_slot = available_slots[selected_time_idx]

            place_name = request.form.get('place_name', 'Default Place')

            conn.execute(
                "INSERT INTO bookings (user_id, service_id, place_name, booking_time) VALUES (?, ?, ?, ?)",
                (user_id, service_id, place_name, chosen_slot.isoformat())
            )
            conn.commit()
            flash(f"Appointment booked for {chosen_slot.strftime('%Y-%m-%d %H:%M')}", 'success')
            return redirect(url_for('profile'))

    return render_template('booking.html',
                           service=service,
                           available_slots=available_slots,
                           has_today_slots=bool(available_today))


# Admin route to update service hours (simple password protection)
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    admin_password = "admin123"  # change this securely in production
    if request.method == 'POST':
        password = request.form['password']
        if password == admin_password:
            return redirect(url_for('admin_services'))
        else:
            flash('Incorrect admin password', 'error')
    return render_template('admin_login.html')

@app.route('/admin/services', methods=['GET', 'POST'])
def admin_services():
    if request.method == 'POST':
        service_name = request.form['service_name'].strip()
        start_hour = int(request.form['start_hour'])
        end_hour = int(request.form['end_hour'])
        with get_db() as conn:
            existing = conn.execute("SELECT * FROM services WHERE name=?", (service_name,)).fetchone()
            if existing:
                conn.execute("UPDATE services SET start_hour=?, end_hour=? WHERE name=?",
                             (start_hour, end_hour, service_name))
                flash(f"Updated hours for {service_name}", 'success')
            else:
                conn.execute("INSERT INTO services (name, start_hour, end_hour) VALUES (?, ?, ?)",
                             (service_name, start_hour, end_hour))
                flash(f"Added new service {service_name}", 'success')
    with get_db() as conn:
        services = conn.execute("SELECT * FROM services").fetchall()
    return render_template('admin_services.html', services=services)

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)

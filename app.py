from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO

app = Flask(__name__)
app.config['SECRET_KEY'] = 'bunny'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///clinic.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin, doctor, patient
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    doctor_profile = db.relationship('Doctor', backref='user', uselist=False, cascade='all, delete-orphan')
    patient_profile = db.relationship('Patient', backref='user', uselist=False, cascade='all, delete-orphan')

class Doctor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    name = db.Column(db.String(100), nullable=False)
    specialization = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    consultation_fee = db.Column(db.Float, default=500.0)
    is_active = db.Column(db.Boolean, default=True)
    
    appointments = db.relationship('Appointment', backref='doctor', lazy=True)
    medical_records = db.relationship('MedicalRecord', backref='doctor', lazy=True)

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    date_of_birth = db.Column(db.Date)
    gender = db.Column(db.String(10))
    
    appointments = db.relationship('Appointment', backref='patient', lazy=True)
    medical_records = db.relationship('MedicalRecord', backref='patient', lazy=True)
    bills = db.relationship('Bill', backref='patient', lazy=True)

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    appointment_date = db.Column(db.Date, nullable=False)
    appointment_time = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected, completed
    reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    medical_record = db.relationship('MedicalRecord', backref='appointment', uselist=False, cascade='all, delete-orphan')
    bill = db.relationship('Bill', backref='appointment', uselist=False, cascade='all, delete-orphan')

class MedicalRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointment.id'), nullable=False, unique=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    diagnosis = db.Column(db.Text)
    prescription = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Bill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointment.id'), nullable=False, unique=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    consultation_fee = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, paid
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime)

# Helper Functions
def login_required(role=None):
    def decorator(f):
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please login to access this page.', 'warning')
                return redirect(url_for('login'))
            if role and session.get('role') != role:
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        decorated_function.__name__ = f.__name__
        return decorated_function
    return decorator

# Routes - Authentication
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        
        user = User.query.filter_by(username=username, role=role).first()
        
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username, password, or role.', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        phone = request.form.get('phone')
        address = request.form.get('address')
        date_of_birth = request.form.get('date_of_birth')
        gender = request.form.get('gender')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists.', 'danger')
            return render_template('register.html')
        
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            role='patient'
        )
        db.session.add(user)
        db.session.flush()
        
        patient = Patient(
            user_id=user.id,
            name=name,
            phone=phone,
            address=address,
            date_of_birth=datetime.strptime(date_of_birth, '%Y-%m-%d').date() if date_of_birth else None,
            gender=gender
        )
        db.session.add(patient)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required()
def dashboard():
    role = session.get('role')
    
    if role == 'admin':
        total_doctors = Doctor.query.count()
        total_patients = Patient.query.count()
        total_appointments = Appointment.query.count()
        pending_appointments = Appointment.query.filter_by(status='pending').count()
        
        return render_template('admin/dashboard.html',
                             total_doctors=total_doctors,
                             total_patients=total_patients,
                             total_appointments=total_appointments,
                             pending_appointments=pending_appointments)
    
    elif role == 'doctor':
        doctor = Doctor.query.filter_by(user_id=session['user_id']).first()
        if not doctor:
            flash('Doctor profile not found.', 'danger')
            return redirect(url_for('logout'))
        
        today_appointments = Appointment.query.filter_by(
            doctor_id=doctor.id,
            appointment_date=datetime.now().date()
        ).count()
        
        pending_appointments = Appointment.query.filter_by(
            doctor_id=doctor.id,
            status='pending'
        ).count()
        
        total_appointments = Appointment.query.filter_by(doctor_id=doctor.id).count()
        
        return render_template('doctor/dashboard.html',
                             doctor=doctor,
                             today_appointments=today_appointments,
                             pending_appointments=pending_appointments,
                             total_appointments=total_appointments)
    
    elif role == 'patient':
        patient = Patient.query.filter_by(user_id=session['user_id']).first()
        if not patient:
            flash('Patient profile not found.', 'danger')
            return redirect(url_for('logout'))
        
        upcoming_appointments = Appointment.query.filter_by(
            patient_id=patient.id
        ).filter(
            Appointment.appointment_date >= datetime.now().date()
        ).count()
        
        total_appointments = Appointment.query.filter_by(patient_id=patient.id).count()
        
        return render_template('patient/dashboard.html',
                             patient=patient,
                             upcoming_appointments=upcoming_appointments,
                             total_appointments=total_appointments)

# Admin Routes
@app.route('/admin/doctors')
@login_required('admin')
def admin_doctors():
    doctors = Doctor.query.all()
    return render_template('admin/doctors.html', doctors=doctors)

@app.route('/admin/add-doctor', methods=['GET', 'POST'])
@login_required('admin')
def add_doctor():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        specialization = request.form.get('specialization')
        phone = request.form.get('phone')
        consultation_fee = float(request.form.get('consultation_fee', 500))
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return render_template('admin/add_doctor.html')
        
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            role='doctor'
        )
        db.session.add(user)
        db.session.flush()
        
        doctor = Doctor(
            user_id=user.id,
            name=name,
            specialization=specialization,
            phone=phone,
            consultation_fee=consultation_fee
        )
        db.session.add(doctor)
        db.session.commit()
        
        flash('Doctor added successfully!', 'success')
        return redirect(url_for('admin_doctors'))
    
    return render_template('admin/add_doctor.html')

@app.route('/admin/patients')
@login_required('admin')
def admin_patients():
    patients = Patient.query.all()
    return render_template('admin/patients.html', patients=patients)

@app.route('/admin/appointments')
@login_required('admin')
def admin_appointments():
    appointments = Appointment.query.order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.desc()).all()
    return render_template('admin/appointments.html', appointments=appointments)

@app.route('/admin/generate-bill/<int:appointment_id>', methods=['GET', 'POST'])
@login_required('admin')
def generate_bill(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    
    if request.method == 'POST':
        amount = float(request.form.get('amount', appointment.doctor.consultation_fee))
        
        if not appointment.bill:
            bill = Bill(
                appointment_id=appointment.id,
                patient_id=appointment.patient_id,
                amount=amount,
                consultation_fee=amount,
                status='pending'
            )
            db.session.add(bill)
            db.session.commit()
            flash('Bill generated successfully!', 'success')
        else:
            flash('Bill already exists for this appointment.', 'warning')
        
        return redirect(url_for('admin_appointments'))
    
    return render_template('admin/generate_bill.html', appointment=appointment)

@app.route('/admin/bills')
@login_required('admin')
def admin_bills():
    """View all bills so admin can verify payment status."""
    bills = Bill.query.order_by(Bill.created_at.desc()).all()
    return render_template('admin/bills.html', bills=bills)

@app.route('/admin/bill/<int:bill_id>/mark-paid', methods=['POST'])
@login_required('admin')
def mark_bill_paid(bill_id):
    """Mark a bill as paid and store the payment date."""
    bill = Bill.query.get_or_404(bill_id)
    if bill.status == 'paid':
        flash('Bill is already marked as paid.', 'info')
        return redirect(url_for('admin_bills'))
    
    bill.status = 'paid'
    bill.paid_at = datetime.utcnow()
    db.session.commit()
    flash('Bill marked as paid successfully.', 'success')
    return redirect(url_for('admin_bills'))

# Doctor Routes
@app.route('/doctor/appointments')
@login_required('doctor')
def doctor_appointments():
    doctor = Doctor.query.filter_by(user_id=session['user_id']).first()
    if not doctor:
        flash('Doctor profile not found.', 'danger')
        return redirect(url_for('logout'))
    
    appointments = Appointment.query.filter_by(doctor_id=doctor.id).order_by(
        Appointment.appointment_date.desc(), Appointment.appointment_time.desc()
    ).all()
    
    return render_template('doctor/appointments.html', appointments=appointments, doctor=doctor)

@app.route('/doctor/appointment/<int:appointment_id>/approve', methods=['POST'])
@login_required('doctor')
def approve_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    doctor = Doctor.query.filter_by(user_id=session['user_id']).first()
    
    if appointment.doctor_id != doctor.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('doctor_appointments'))
    
    appointment.status = 'approved'
    db.session.commit()
    flash('Appointment approved!', 'success')
    return redirect(url_for('doctor_appointments'))

@app.route('/doctor/appointment/<int:appointment_id>/reject', methods=['POST'])
@login_required('doctor')
def reject_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    doctor = Doctor.query.filter_by(user_id=session['user_id']).first()
    
    if appointment.doctor_id != doctor.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('doctor_appointments'))
    
    appointment.status = 'reject'
    db.session.commit()
    flash('Appointment rejected.', 'info')
    return redirect(url_for('doctor_appointments'))

@app.route('/doctor/appointment/<int:appointment_id>/medical-record', methods=['GET', 'POST'])
@login_required('doctor')
def add_medical_record(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    doctor = Doctor.query.filter_by(user_id=session['user_id']).first()
    
    if appointment.doctor_id != doctor.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('doctor_appointments'))
    
    if request.method == 'POST':
        diagnosis = request.form.get('diagnosis')
        prescription = request.form.get('prescription')
        notes = request.form.get('notes')
        
        medical_record = MedicalRecord.query.filter_by(appointment_id=appointment_id).first()
        
        if medical_record:
            medical_record.diagnosis = diagnosis
            medical_record.prescription = prescription
            medical_record.notes = notes
            medical_record.updated_at = datetime.utcnow()
        else:
            medical_record = MedicalRecord(
                appointment_id=appointment_id,
                patient_id=appointment.patient_id,
                doctor_id=doctor.id,
                diagnosis=diagnosis,
                prescription=prescription,
                notes=notes
            )
            db.session.add(medical_record)
        
        appointment.status = 'completed'
        db.session.commit()
        
        flash('Medical record saved successfully!', 'success')
        return redirect(url_for('doctor_appointments'))
    
    medical_record = MedicalRecord.query.filter_by(appointment_id=appointment_id).first()
    return render_template('doctor/medical_record.html', appointment=appointment, medical_record=medical_record)

@app.route('/doctor/patient-history/<int:patient_id>')
@login_required('doctor')
def patient_history(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    doctor = Doctor.query.filter_by(user_id=session['user_id']).first()
    
    records = MedicalRecord.query.filter_by(
        patient_id=patient_id,
        doctor_id=doctor.id
    ).order_by(MedicalRecord.created_at.desc()).all()
    
    return render_template('doctor/patient_history.html', patient=patient, records=records)

# Patient Routes
@app.route('/patient/book-appointment', methods=['GET', 'POST'])
@login_required('patient')
def book_appointment():
    patient = Patient.query.filter_by(user_id=session['user_id']).first()
    if not patient:
        flash('Patient profile not found.', 'danger')
        return redirect(url_for('logout'))
    
    if request.method == 'POST':
        doctor_id = int(request.form.get('doctor_id'))
        appointment_date = datetime.strptime(request.form.get('appointment_date'), '%Y-%m-%d').date()
        appointment_time = datetime.strptime(request.form.get('appointment_time'), '%H:%M').time()
        reason = request.form.get('reason')
        
        appointment = Appointment(
            patient_id=patient.id,
            doctor_id=doctor_id,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            reason=reason,
            status='pending'
        )
        db.session.add(appointment)
        db.session.commit()
        
        flash('Appointment booked successfully! Waiting for doctor approval.', 'success')
        return redirect(url_for('patient_appointments'))
    
    doctors = Doctor.query.filter_by(is_active=True).all()
    min_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    return render_template('patient/book_appointment.html', doctors=doctors, min_date=min_date)

@app.route('/patient/appointments')
@login_required('patient')
def patient_appointments():
    patient = Patient.query.filter_by(user_id=session['user_id']).first()
    if not patient:
        flash('Patient profile not found.', 'danger')
        return redirect(url_for('logout'))
    
    appointments = Appointment.query.filter_by(patient_id=patient.id).order_by(
        Appointment.appointment_date.desc(), Appointment.appointment_time.desc()
    ).all()
    
    return render_template('patient/appointments.html', appointments=appointments)

@app.route('/patient/medical-records')
@login_required('patient')
def patient_medical_records():
    patient = Patient.query.filter_by(user_id=session['user_id']).first()
    if not patient:
        flash('Patient profile not found.', 'danger')
        return redirect(url_for('logout'))
    
    records = MedicalRecord.query.filter_by(patient_id=patient.id).order_by(
        MedicalRecord.created_at.desc()
    ).all()
    
    return render_template('patient/medical_records.html', records=records)

@app.route('/patient/bills')
@login_required('patient')
def patient_bills():
    patient = Patient.query.filter_by(user_id=session['user_id']).first()
    if not patient:
        flash('Patient profile not found.', 'danger')
        return redirect(url_for('logout'))
    
    bills = Bill.query.filter_by(patient_id=patient.id).order_by(Bill.created_at.desc()).all()
    return render_template('patient/bills.html', bills=bills)

@app.route('/patient/bill/<int:bill_id>/download')
@login_required('patient')
def download_bill(bill_id):
    bill = Bill.query.get_or_404(bill_id)
    patient = Patient.query.filter_by(user_id=session['user_id']).first()
    
    if bill.patient_id != patient.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('patient_bills'))
    
    # Generate PDF
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Header
    p.setFont("Helvetica-Bold", 20)
    p.drawString(50, height - 50, "Medical Invoice")
    
    # Patient Info
    p.setFont("Helvetica", 12)
    y = height - 100
    p.drawString(50, y, f"Patient: {bill.patient.name}")
    y -= 20
    p.drawString(50, y, f"Date: {bill.created_at.strftime('%Y-%m-%d')}")
    y -= 20
    p.drawString(50, y, f"Appointment Date: {bill.appointment.appointment_date}")
    
    # Bill Details
    y -= 40
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, y, "Bill Details")
    y -= 30
    p.setFont("Helvetica", 12)
    p.drawString(50, y, f"Consultation Fee: ${bill.consultation_fee:.2f}")
    y -= 20
    p.drawString(50, y, f"Total Amount: ${bill.amount:.2f}")
    y -= 20
    p.drawString(50, y, f"Status: {bill.status.upper()}")
    
    p.showPage()
    p.save()
    
    buffer.seek(0)
    return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name=f'bill_{bill.id}.pdf')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Create default admin user if not exists
        if not User.query.filter_by(role='admin').first():
            admin_user = User(
                username='admin',
                email='admin@clinic.com',
                password_hash=generate_password_hash('admin123'),
                role='admin'
            )
            db.session.add(admin_user)
            db.session.commit()
            print("Default admin created: username='admin', password='admin123'")
    
    app.run(host='0.0.0.0', port=5000, debug=False)


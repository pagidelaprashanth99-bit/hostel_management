"""
Database Reset Script
This script will drop all tables and recreate them with fresh data.
WARNING: This will delete all existing data!
"""

from app import app, db, User, Doctor, Patient, Appointment, MedicalRecord, Bill
from werkzeug.security import generate_password_hash
from datetime import datetime

def reset_database():
    """Drop all tables and recreate them"""
    with app.app_context():
        print("Dropping all tables...")
        db.drop_all()
        
        print("Creating all tables...")
        db.create_all()
        
        # Create default admin user
        print("Creating default admin user...")
        admin_user = User(
            username='admin',
            email='admin@clinic.com',
            password_hash=generate_password_hash('admin123'),
            role='admin'
        )
        db.session.add(admin_user)
        db.session.commit()
        
        print("✅ Database reset complete!")
        print("\nDefault Admin Credentials:")
        print("  Username: admin")
        print("  Password: admin123")
        print("\nYou can now run 'python app.py' to start the application.")

if __name__ == '__main__':
    confirm = input("⚠️  WARNING: This will delete ALL data! Type 'yes' to continue: ")
    if confirm.lower() == 'yes':
        reset_database()
    else:
        print("Database reset cancelled.")


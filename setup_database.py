import sqlite3
import random
import os
from datetime import datetime, timedelta

DB_PATH = os.getenv("CLINIC_DB_PATH", "clinic.db")
random.seed(42)

def create_database():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cursor = conn.cursor()

    cursor.execute("PRAGMA journal_mode = OFF;")
    cursor.execute("PRAGMA foreign_keys = OFF;")
    for table in ("invoices", "treatments", "appointments", "doctors", "patients"):
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
    cursor.execute("PRAGMA foreign_keys = ON;")

    # 1. Create Tables
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        date_of_birth DATE,
        gender TEXT,
        city TEXT,
        registered_date DATE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS doctors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        specialization TEXT,
        department TEXT,
        phone TEXT
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        doctor_id INTEGER,
        appointment_date DATETIME,
        status TEXT,
        notes TEXT,
        FOREIGN KEY(patient_id) REFERENCES patients(id),
        FOREIGN KEY(doctor_id) REFERENCES doctors(id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS treatments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        appointment_id INTEGER,
        treatment_name TEXT,
        cost REAL,
        duration_minutes INTEGER,
        FOREIGN KEY(appointment_id) REFERENCES appointments(id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        invoice_date DATE,
        total_amount REAL,
        paid_amount REAL,
        status TEXT,
        FOREIGN KEY(patient_id) REFERENCES patients(id)
    );
    """)

    # 2. Insert Dummy Data
    # print("Generating dummy data...")

    # Doctors (15 doctors, 5 specializations)
    specs = [
        ("Dermatology", "Skin Care"),
        ("Cardiology", "Heart Center"),
        ("Orthopedics", "Bone & Joint"),
        ("General", "Primary Care"),
        ("Pediatrics", "Childrens Health")
    ]
    doctor_names = [
        "Dr. Rajesh Khanna", "Dr. Anita Desai", "Dr. Vikram Seth", 
        "Dr. Meera Nair", "Dr. Sanjay Gupta", "Dr. Shalini Singh", 
        "Dr. Amit Shah", "Dr. Pooja Bajaj", "Dr. Rahul Dravid", 
        "Dr. Sneha Roy", "Dr. Kiran Mazumdar", "Dr. Sunil Gavaskar", 
        "Dr. Aruna Irani", "Dr. Kapil Dev", "Dr. Mary Kom"
    ]
    
    for i in range(15):
        spec, dept = specs[i % 5]
        cursor.execute("INSERT INTO doctors (name, specialization, department, phone) VALUES (?, ?, ?, ?)",
                       (doctor_names[i], spec, dept, f"9876543{i:02d}"))

    # Patients (200 patients, 8-10 cities)
    cities = ["Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai", "Kolkata", "Pune", "Ahmedabad", "Jaipur", "Lucknow"]
    first_names = ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Ishaan", "Aaryan", "Ayaan", "Krishna", "Ananya", "Diya", "Pari", "Myra", "Aadhya", "Saanvi", "Kyra", "Anvi", "Aavya", "Aradhya"]
    last_names = ["Sharma", "Verma", "Gupta", "Malhotra", "Kapoor", "Singh", "Joshi", "Patel", "Reddy", "Iyer"]

    for _ in range(200):
        fn = random.choice(first_names)
        ln = random.choice(last_names)
        city = random.choice(cities)
        gender = random.choice(["M", "F"])
        email = f"{fn.lower()}.{ln.lower()}@example.com" if random.random() > 0.1 else None
        phone = f"9{random.randint(100000000, 999999999)}" if random.random() > 0.1 else None
        dob = (datetime.now() - timedelta(days=random.randint(365*5, 365*70))).date()
        reg_date = (datetime.now() - timedelta(days=random.randint(1, 365))).date()
        
        cursor.execute("INSERT INTO patients (first_name, last_name, email, phone, date_of_birth, gender, city, registered_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                       (fn, ln, email, phone, dob, gender, city, reg_date))

    # Appointments (500 over last 12 months)
    statuses = ["Scheduled", "Completed", "Cancelled", "No-Show"]
    patient_weights = [5 if i <= 40 else 1 for i in range(1, 201)]
    doctor_weights = [6, 4, 5, 3, 4, 8, 3, 5, 4, 3, 2, 3, 2, 4, 2]
    for _ in range(500):
        p_id = random.choices(range(1, 201), weights=patient_weights)[0]
        d_id = random.choices(range(1, 16), weights=doctor_weights)[0]
        date = datetime.now() - timedelta(days=random.randint(0, 365), hours=random.randint(0, 23))
        status = random.choices(statuses, weights=[10, 70, 10, 10])[0]
        notes = "Follow up required" if random.random() > 0.5 else None
        
        cursor.execute("INSERT INTO appointments (patient_id, doctor_id, appointment_date, status, notes) VALUES (?, ?, ?, ?, ?)",
                       (p_id, d_id, date, status, notes))

    # Treatments (350 linked to Completed appointments)
    cursor.execute("SELECT id FROM appointments WHERE status = 'Completed'")
    completed_appt_ids = [row[0] for row in cursor.fetchall()]
    treatment_types = [
        ("Consultation", 500, 15),
        ("Routine Checkup", 800, 30),
        ("X-Ray", 1200, 20),
        ("Blood Test", 1500, 10),
        ("Physical Therapy", 2000, 45),
        ("Minor Surgery", 5000, 90)
    ]
    
    for _ in range(350):
        if not completed_appt_ids: break
        a_id = random.choice(completed_appt_ids)
        name, base_cost, duration = random.choice(treatment_types)
        cost = min(5000, max(50, base_cost + random.uniform(-100, 500)))
        cursor.execute("INSERT INTO treatments (appointment_id, treatment_name, cost, duration_minutes) VALUES (?, ?, ?, ?)",
                       (a_id, name, round(cost, 2), duration))

    # Invoices (300 with mix of Paid, Pending, Overdue)
    inv_statuses = ["Paid", "Pending", "Overdue"]
    for _ in range(300):
        p_id = random.randint(1, 200)
        date = (datetime.now() - timedelta(days=random.randint(1, 300))).date()
        total = random.uniform(500, 5000)
        status = random.choices(inv_statuses, weights=[60, 30, 10])[0]
        paid = total if status == "Paid" else (total * random.uniform(0, 0.5) if status == "Pending" else 0)
        
        cursor.execute("INSERT INTO invoices (patient_id, invoice_date, total_amount, paid_amount, status) VALUES (?, ?, ?, ?, ?)",
                       (p_id, date, round(total, 2), round(paid, 2), status))

    conn.commit()
    
    # Verify counts
    # print("-" * 30)
    cursor.execute("SELECT COUNT(*) FROM patients")
    patients_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM doctors")
    doctors_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM appointments")
    appts_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM treatments")
    treats_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM invoices")
    inv_count = cursor.fetchone()[0]
    
    print(f"Created {patients_count} patients, {doctors_count} doctors, {appts_count} appointments, {treats_count} treatments, {inv_count} invoices.")
    # print(" Database and tables created successfully with dummy data!")
    # print("-" * 30)

    conn.close()

if __name__ == "__main__":
    create_database()

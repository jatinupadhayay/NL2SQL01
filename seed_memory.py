# seed_memory.py

from vanna_setup import agent  # make sure your agent is created here


def seed_memory():
    print("Seeding agent memory with example Q&A pairs...")

    examples = [
        # Patient queries
        ("How many patients do we have?",
         "SELECT COUNT(*) AS total_patients FROM patients"),

        ("List all patients in Delhi",
         "SELECT first_name, last_name FROM patients WHERE city = 'Delhi'"),

        ("How many female patients are there?",
         "SELECT COUNT(*) FROM patients WHERE gender = 'F'"),

        # Doctor queries
        ("List all doctors and their specializations",
         "SELECT name, specialization FROM doctors"),

        ("Which doctor has the most appointments?",
         """SELECT d.name, COUNT(*) as total_appointments
            FROM appointments a
            JOIN doctors d ON a.doctor_id = d.id
            GROUP BY d.name
            ORDER BY total_appointments DESC LIMIT 1"""),

        # Appointment queries
        ("How many appointments are completed?",
         "SELECT COUNT(*) FROM appointments WHERE status = 'Completed'"),

        ("Show appointments by status",
         """SELECT status, COUNT(*) as count
            FROM appointments
            GROUP BY status"""),

        ("Appointments in last 3 months",
         """SELECT *
            FROM appointments
            WHERE appointment_date >= date('now', '-3 months')"""),

        # Financial queries
        ("What is the total revenue?",
         "SELECT SUM(total_amount) AS total_revenue FROM invoices"),

        ("Show unpaid invoices",
         "SELECT * FROM invoices WHERE status != 'Paid'"),

        ("Average treatment cost",
         "SELECT AVG(cost) FROM treatments"),

        # Revenue by doctor
        ("Show revenue by doctor",
         """SELECT d.name, SUM(i.total_amount) as revenue
            FROM invoices i
            JOIN appointments a ON i.patient_id = a.patient_id
            JOIN doctors d ON a.doctor_id = d.id
            GROUP BY d.name
            ORDER BY revenue DESC"""),

        # Time-based queries
        ("Monthly appointment count",
         """SELECT strftime('%Y-%m', appointment_date) as month,
                   COUNT(*) as total
            FROM appointments
            GROUP BY month
            ORDER BY month"""),

        ("Revenue trend by month",
         """SELECT strftime('%Y-%m', invoice_date) as month,
                   SUM(total_amount) as revenue
            FROM invoices
            GROUP BY month
            ORDER BY month"""),

        # Advanced
        ("Top 5 patients by spending",
         """SELECT p.first_name, p.last_name, SUM(i.total_amount) as total_spent
            FROM patients p
            JOIN invoices i ON p.id = i.patient_id
            GROUP BY p.id
            ORDER BY total_spent DESC
            LIMIT 5"""),

        ("Which city has most patients?",
         """SELECT city, COUNT(*) as total
            FROM patients
            GROUP BY city
            ORDER BY total DESC
            LIMIT 1"""),
    ]

    count = 0

    for question, sql in examples:
        try:
            agent.memory.add_correct_example(
                question=question,
                sql=sql
            )
            count += 1
        except Exception as e:
            print(f"Error adding example: {e}")

    print(f"✅ Seeded {count} examples into memory!")


if __name__ == "__main__":
    seed_memory()
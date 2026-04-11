"""
seed_memory.py
Pre-seeds Vanna 2.0 DemoAgentMemory with curated Q&A pairs so the agent
has context about the clinic database schema from the first request.
"""

import asyncio
import uuid

from vanna.core.tool import ToolContext
from vanna.core.user import User

from vanna_setup import agent


EXAMPLES = [
    # --- Patient queries ---
    (
        "How many patients do we have?",
        "SELECT COUNT(*) AS total_patients FROM patients",
    ),
    (
        "List all patients in Delhi",
        "SELECT first_name, last_name, email FROM patients WHERE city = 'Delhi'",
    ),
    (
        "How many female patients are there?",
        "SELECT COUNT(*) AS female_patients FROM patients WHERE gender = 'F'",
    ),
    (
        "Which city has the most patients?",
        """SELECT city, COUNT(*) AS patient_count
           FROM patients
           GROUP BY city
           ORDER BY patient_count DESC
           LIMIT 1""",
    ),
    (
        "List patients who visited more than 3 times",
        """SELECT p.first_name, p.last_name, COUNT(a.id) AS visit_count
           FROM patients p
           JOIN appointments a ON a.patient_id = p.id
           GROUP BY p.id
           HAVING visit_count > 3
           ORDER BY visit_count DESC""",
    ),
    # --- Doctor queries ---
    (
        "List all doctors and their specializations",
        "SELECT name, specialization, department FROM doctors",
    ),
    (
        "Which doctor has the most appointments?",
        """SELECT d.name, COUNT(*) AS total_appointments
           FROM appointments a
           JOIN doctors d ON a.doctor_id = d.id
           GROUP BY d.name
           ORDER BY total_appointments DESC
           LIMIT 1""",
    ),
    (
        "Show average appointment duration by doctor",
        """SELECT d.name, ROUND(AVG(t.duration_minutes), 1) AS avg_duration_minutes
           FROM treatments t
           JOIN appointments a ON t.appointment_id = a.id
           JOIN doctors d ON a.doctor_id = d.id
           GROUP BY d.name
           ORDER BY avg_duration_minutes DESC""",
    ),
    # --- Appointment queries ---
    (
        "Show appointments for last month",
        """SELECT * FROM appointments
           WHERE appointment_date >= date('now', '-1 month')""",
    ),
    (
        "How many cancelled appointments last quarter?",
        """SELECT COUNT(*) AS cancelled_count
           FROM appointments
           WHERE status = 'Cancelled'
             AND appointment_date >= date('now', '-3 months')""",
    ),
    (
        "What percentage of appointments are no-shows?",
        """SELECT
             ROUND(100.0 * SUM(CASE WHEN status = 'No-Show' THEN 1 ELSE 0 END) / COUNT(*), 2)
               AS no_show_percentage
           FROM appointments""",
    ),
    (
        "Show monthly appointment count for the past 6 months",
        """SELECT strftime('%Y-%m', appointment_date) AS month, COUNT(*) AS total
           FROM appointments
           WHERE appointment_date >= date('now', '-6 months')
           GROUP BY month
           ORDER BY month""",
    ),
    # --- Financial queries ---
    (
        "What is the total revenue?",
        "SELECT ROUND(SUM(total_amount), 2) AS total_revenue FROM invoices",
    ),
    (
        "Show revenue by doctor",
        """SELECT d.name, ROUND(SUM(i.total_amount), 2) AS total_revenue
           FROM invoices i
           JOIN appointments a ON a.patient_id = i.patient_id
           JOIN doctors d ON d.id = a.doctor_id
           GROUP BY d.name
           ORDER BY total_revenue DESC""",
    ),
    (
        "Show unpaid invoices",
        "SELECT * FROM invoices WHERE status != 'Paid' ORDER BY invoice_date DESC",
    ),
    # --- Time-based queries ---
    (
        "Revenue trend by month",
        """SELECT strftime('%Y-%m', invoice_date) AS month,
                  ROUND(SUM(total_amount), 2) AS revenue
           FROM invoices
           GROUP BY month
           ORDER BY month""",
    ),
    (
        "Show patient registration trend by month",
        """SELECT strftime('%Y-%m', registered_date) AS month,
                  COUNT(*) AS new_patients
           FROM patients
           GROUP BY month
           ORDER BY month""",
    ),
    # --- Multi-table JOIN examples (treatments -> appointments -> patients/doctors) ---
    (
        "Top 5 patients by total spending",
        """SELECT p.first_name, p.last_name, ROUND(SUM(t.cost), 2) AS total_spending
           FROM treatments t
           JOIN appointments a ON t.appointment_id = a.id
           JOIN patients p ON a.patient_id = p.id
           GROUP BY p.id, p.first_name, p.last_name
           ORDER BY total_spending DESC
           LIMIT 5""",
    ),
    (
        "Average treatment cost by specialization",
        """SELECT d.specialization, ROUND(AVG(t.cost), 2) AS avg_cost
           FROM treatments t
           JOIN appointments a ON t.appointment_id = a.id
           JOIN doctors d ON a.doctor_id = d.id
           GROUP BY d.specialization
           ORDER BY avg_cost DESC""",
    ),
    (
        "Show the busiest day of the week for appointments",
        """SELECT CASE CAST(strftime('%w', appointment_date) AS INTEGER)
                WHEN 0 THEN 'Sunday' WHEN 1 THEN 'Monday' WHEN 2 THEN 'Tuesday'
                WHEN 3 THEN 'Wednesday' WHEN 4 THEN 'Thursday' WHEN 5 THEN 'Friday'
                WHEN 6 THEN 'Saturday' END AS day_of_week,
                COUNT(*) AS total
           FROM appointments
           GROUP BY day_of_week
           ORDER BY total DESC""",
    ),
    (
        "Compare revenue between departments",
        """SELECT d.department, ROUND(SUM(i.total_amount), 2) AS total_revenue
           FROM invoices i
           JOIN appointments a ON a.patient_id = i.patient_id
           JOIN doctors d ON d.id = a.doctor_id
           GROUP BY d.department
           ORDER BY total_revenue DESC""",
    ),
    (
        "List patients with overdue invoices",
        """SELECT DISTINCT p.first_name, p.last_name, p.email, p.phone
           FROM patients p
           JOIN invoices i ON i.patient_id = p.id
           WHERE i.status = 'Overdue'
           ORDER BY p.last_name""",
    ),
    (
        "Patients who have never had an appointment",
        """SELECT p.first_name, p.last_name, p.city
           FROM patients p
           WHERE p.id NOT IN (SELECT DISTINCT patient_id FROM appointments)""",
    ),
    (
        "Total treatment cost per patient",
        """SELECT p.first_name, p.last_name, ROUND(SUM(t.cost), 2) AS total_cost
           FROM treatments t
           JOIN appointments a ON t.appointment_id = a.id
           JOIN patients p ON a.patient_id = p.id
           GROUP BY p.id, p.first_name, p.last_name
           ORDER BY total_cost DESC""",
    ),
    (
        "How many patients registered this year?",
        """SELECT COUNT(*) AS patients_this_year
           FROM patients
           WHERE strftime('%Y', registered_date) = strftime('%Y', 'now')""",
    ),
    (
        "Total amount of overdue invoices",
        """SELECT ROUND(SUM(total_amount - paid_amount), 2) AS total_overdue
           FROM invoices
           WHERE status = 'Overdue'""",
    ),
    (
        "Most expensive treatment given",
        """SELECT t.treatment_name, t.cost, p.first_name, p.last_name
           FROM treatments t
           JOIN appointments a ON t.appointment_id = a.id
           JOIN patients p ON a.patient_id = p.id
           ORDER BY t.cost DESC
           LIMIT 1""",
    ),
    (
        "Number of appointments by department",
        """SELECT d.department, COUNT(*) AS appointment_count
           FROM appointments a
           JOIN doctors d ON a.doctor_id = d.id
           GROUP BY d.department
           ORDER BY appointment_count DESC""",
    ),
]


async def seed_memory_async() -> None:
    print("Seeding agent memory with example Q&A pairs...")

    context = ToolContext(
        user=User(id="seed-user", username="seed-user", group_memberships=["user"]),
        conversation_id=f"seed-{uuid.uuid4().hex}",
        request_id=uuid.uuid4().hex,
        agent_memory=agent.agent_memory,
    )

    count = 0
    for question, sql in EXAMPLES:
        try:
            await agent.agent_memory.save_tool_usage(
                question=question,
                tool_name="run_sql",
                args={"sql": sql},
                context=context,
                success=True,
            )
            count += 1
        except Exception as exc:
            print(f"  ⚠  Error adding example '{question[:40]}': {exc}")

    print(f"Seeded {count} examples into memory!")


def seed_memory() -> None:
    asyncio.run(seed_memory_async())


if __name__ == "__main__":
    seed_memory()
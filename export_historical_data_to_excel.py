"""
Export all historical (completed/old) data from MongoDB Atlas into a structured,
executive-ready Excel workbook (.xlsx).
"""
import os
import pymongo
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb+srv://learnanddrive:T5cYO6bCZYwYXP9w@driving.ws3cihd.mongodb.net/ridewell?retryWrites=true&w=majority"
)

def build_excel_export():
    print("Connecting to MongoDB Atlas...")
    client = pymongo.MongoClient(MONGO_URI)
    db = client.ridewell

    # 1. Fetch lookup maps
    print("Fetching trainers and students lookup...")
    trainers = {
        u["id"]: u.get("name", "Unknown Trainer")
        for u in db.users.find({"role": "trainer"}, {"id": 1, "name": 1})
    }
    trainers_phone = {
        u["id"]: u.get("phone", "")
        for u in db.users.find({"role": "trainer"}, {"id": 1, "phone": 1})
    }

    all_students_cursor = db.students.find({}, {"_id": 0})
    students_map = {}
    completed_students = []
    active_students = []

    for s in all_students_cursor:
        students_map[s["id"]] = s
        if s.get("status") in ["completed", "dropped"]:
            completed_students.append(s)
        elif s.get("status") == "active":
            active_students.append(s)

    print(f"Found {len(completed_students)} completed students and {len(active_students)} active students.")

    # 2. Fetch completed classes
    completed_student_ids = set(s["id"] for s in completed_students)
    classes_cursor = db.classes.find(
        {"$or": [{"student_id": {"$in": list(completed_student_ids)}}, {"status": "completed"}]},
        {"_id": 0}
    ).sort([("student_id", 1), ("class_number", 1)])
    old_classes = list(classes_cursor)
    print(f"Found {len(old_classes)} completed/historical class records.")

    # 3. Fetch payments for completed students
    payments_cursor = db.payments.find(
        {"student_id": {"$in": list(completed_student_ids)}},
        {"_id": 0}
    ).sort("date", -1)
    old_payments = list(payments_cursor)
    print(f"Found {len(old_payments)} payments for completed students.")

    # 4. Create Workbook
    wb = Workbook()
    
    # Styles
    HEADER_FILL = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid") # Dark Blue
    HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    TITLE_FONT = Font(name="Calibri", size=14, bold=True, color="1E3A8A")
    SUBTITLE_FONT = Font(name="Calibri", size=10, italic=True, color="64748B")
    BOLD_FONT = Font(name="Calibri", size=11, bold=True)
    REGULAR_FONT = Font(name="Calibri", size=11)
    
    ZEBRA_FILL = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    TOTAL_FILL = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")
    
    THIN_BORDER = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    # ── SHEET 1: EXECUTIVE SUMMARY ──
    ws_sum = wb.active
    ws_sum.title = "Executive_Summary"
    ws_sum.views.sheetView[0].showGridLines = True

    ws_sum.append(["LEARN & DRIVE - HISTORICAL DATA ARCHIVE REPORT"])
    ws_sum["A1"].font = TITLE_FONT
    ws_sum.append(["Generated on 2026-10-25 | All Completed Students & Class Records Export"])
    ws_sum["A2"].font = SUBTITLE_FONT
    ws_sum.append([])

    total_fees_billed = sum(float(s.get("fees_total") or 0) for s in completed_students)
    total_fees_collected = sum(float(s.get("fees_paid") or 0) for s in completed_students)
    total_balance_due = sum(max(0, float(s.get("fees_total") or 0) - float(s.get("fees_paid") or 0)) for s in completed_students)

    ws_sum.append(["METRIC", "COUNT / AMOUNT", "NOTES"])
    ws_sum.append(["Total Completed Students", len(completed_students), "Archived from active database"])
    ws_sum.append(["Total Currently Active Students", len(active_students), "Retained in active database"])
    ws_sum.append(["Total Completed Class Sessions", len(old_classes), "Classes conducted for completed batches"])
    ws_sum.append(["Total Historical Course Fees", total_fees_billed, "Sum of total course fees for old students"])
    ws_sum.append(["Total Historical Fees Collected", total_fees_collected, "Sum of fees actually paid"])
    ws_sum.append(["Total Outstanding Balance on Old Batches", total_balance_due, "Uncollected pending fees from old students"])
    ws_sum.append([])

    # Branch breakdown
    ws_sum.append(["BRANCH BREAKDOWN", "COMPLETED STUDENTS", "TOTAL REVENUE COLLECTED"])
    branches = {}
    for s in completed_students:
        loc = s.get("location") or "Khajaguda"
        branches.setdefault(loc, {"count": 0, "paid": 0})
        branches[loc]["count"] += 1
        branches[loc]["paid"] += float(s.get("fees_paid") or 0)

    for loc, bdata in sorted(branches.items()):
        ws_sum.append([loc, bdata["count"], bdata["paid"]])
    ws_sum.append([])

    # Trainer breakdown
    ws_sum.append(["TRAINER PERFORMANCE", "STUDENTS COMPLETED"])
    t_counts = {}
    for s in completed_students:
        tname = trainers.get(s.get("assigned_trainer_id"), "Unassigned / Direct")
        t_counts[tname] = t_counts.get(tname, 0) + 1
    for tname, cnt in sorted(t_counts.items(), key=lambda x: x[1], reverse=True):
        ws_sum.append([tname, cnt])

    # Format summary table
    for r in range(4, 11):
        ws_sum.cell(row=r, column=1).font = BOLD_FONT if r == 4 else REGULAR_FONT
        ws_sum.cell(row=r, column=2).font = BOLD_FONT if r == 4 else REGULAR_FONT
        if r == 4:
            ws_sum.cell(row=r, column=1).fill = HEADER_FILL
            ws_sum.cell(row=r, column=2).fill = HEADER_FILL
            ws_sum.cell(row=r, column=3).fill = HEADER_FILL
            ws_sum.cell(row=r, column=1).font = HEADER_FONT
            ws_sum.cell(row=r, column=2).font = HEADER_FONT
            ws_sum.cell(row=r, column=3).font = HEADER_FONT
        elif r in [8, 9, 10]:
            ws_sum.cell(row=r, column=2).number_format = '₹ #,##0'

    # ── SHEET 2: COMPLETED STUDENTS ──
    ws_students = wb.create_sheet("Completed_Students")
    ws_students.views.sheetView[0].showGridLines = True
    student_headers = [
        "Student ID", "Full Name", "Phone", "Email", "Location / Branch",
        "Status", "Joining Date", "Completion Date", "Slot Time",
        "Total Classes", "Total Fees (₹)", "Fees Paid (₹)", "Balance Due (₹)",
        "Assigned Trainer", "Trainer Phone", "License Type", "Needs Pickup", "Pickup Address", "Notes"
    ]
    ws_students.append(student_headers)
    for col_num in range(1, len(student_headers) + 1):
        cell = ws_students.cell(row=1, column=col_num)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for i, s in enumerate(completed_students, start=2):
        t_id = s.get("assigned_trainer_id")
        t_name = trainers.get(t_id, "Unassigned")
        t_phone = trainers_phone.get(t_id, "")
        f_total = float(s.get("fees_total") or 0)
        f_paid = float(s.get("fees_paid") or 0)
        f_bal = max(0.0, f_total - f_paid)

        row = [
            s.get("id", ""),
            s.get("name", ""),
            s.get("phone", ""),
            s.get("email", ""),
            s.get("location", "Khajaguda"),
            s.get("status", "completed"),
            s.get("joining_date", ""),
            s.get("completed_at", ""),
            s.get("slot_time", ""),
            s.get("total_classes", 10),
            f_total,
            f_paid,
            f_bal,
            t_name,
            t_phone,
            s.get("license_type", "4W"),
            "Yes" if s.get("needs_pickup") else "No",
            s.get("pickup_address", ""),
            s.get("notes", "")
        ]
        ws_students.append(row)
        fill = ZEBRA_FILL if i % 2 == 0 else None
        for col_idx in range(1, len(row) + 1):
            c = ws_students.cell(row=i, column=col_idx)
            c.font = REGULAR_FONT
            c.border = THIN_BORDER
            if fill:
                c.fill = fill
            if col_idx in [11, 12, 13]:
                c.number_format = '₹ #,##0'

    # ── SHEET 3: COMPLETED CLASSES ──
    ws_classes = wb.create_sheet("Completed_Classes")
    ws_classes.views.sheetView[0].showGridLines = True
    class_headers = [
        "Class ID", "Student Name", "Student Phone", "Branch",
        "Class #", "Scheduled Date", "Completed Date", "Status",
        "Conducted By Trainer", "Notes / Feedback"
    ]
    ws_classes.append(class_headers)
    for col_num in range(1, len(class_headers) + 1):
        cell = ws_classes.cell(row=1, column=col_num)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for i, c in enumerate(old_classes, start=2):
        s_info = students_map.get(c.get("student_id"), {})
        t_name = trainers.get(c.get("trainer_id"), "Unassigned")
        row = [
            c.get("id", ""),
            s_info.get("name", "Unknown Student"),
            s_info.get("phone", ""),
            s_info.get("location", "Khajaguda"),
            c.get("class_number", 1),
            c.get("scheduled_date", ""),
            c.get("completed_date", ""),
            c.get("status", "completed"),
            t_name,
            c.get("notes", "")
        ]
        ws_classes.append(row)
        fill = ZEBRA_FILL if i % 2 == 0 else None
        for col_idx in range(1, len(row) + 1):
            cell = ws_classes.cell(row=i, column=col_idx)
            cell.font = REGULAR_FONT
            cell.border = THIN_BORDER
            if fill:
                cell.fill = fill

    # ── SHEET 4: HISTORICAL PAYMENTS ──
    ws_pay = wb.create_sheet("Old_Students_Payments")
    ws_pay.views.sheetView[0].showGridLines = True
    pay_headers = [
        "Payment ID", "Student Name", "Student Phone", "Branch",
        "Payment Date", "Amount (₹)", "Payment Method", "Recorded By", "Notes"
    ]
    ws_pay.append(pay_headers)
    for col_num in range(1, len(pay_headers) + 1):
        cell = ws_pay.cell(row=1, column=col_num)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for i, p in enumerate(old_payments, start=2):
        s_info = students_map.get(p.get("student_id"), {})
        row = [
            p.get("id", ""),
            s_info.get("name", "Unknown Student"),
            s_info.get("phone", ""),
            s_info.get("location", "Khajaguda"),
            p.get("date", ""),
            float(p.get("amount") or 0),
            p.get("method", "cash"),
            p.get("recorded_by", "admin"),
            p.get("notes", "")
        ]
        ws_pay.append(row)
        fill = ZEBRA_FILL if i % 2 == 0 else None
        for col_idx in range(1, len(row) + 1):
            cell = ws_pay.cell(row=i, column=col_idx)
            cell.font = REGULAR_FONT
            cell.border = THIN_BORDER
            if fill:
                cell.fill = fill
            if col_idx == 6:
                cell.number_format = '₹ #,##0'

    # ── SHEET 5: ACTIVE STUDENTS (SNAPSHOT) ──
    ws_active = wb.create_sheet("Active_Students_Snapshot")
    ws_active.views.sheetView[0].showGridLines = True
    act_headers = [
        "Student ID", "Full Name", "Phone", "Branch", "Joining Date", "Slot Time",
        "Course Classes", "Total Fees (₹)", "Fees Paid (₹)", "Balance Due (₹)",
        "Assigned Trainer", "Pickup Address"
    ]
    ws_active.append(act_headers)
    for col_num in range(1, len(act_headers) + 1):
        cell = ws_active.cell(row=1, column=col_num)
        cell.fill = PatternFill(start_color="047857", end_color="047857", fill_type="solid") # Dark Green
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for i, s in enumerate(active_students, start=2):
        t_id = s.get("assigned_trainer_id")
        t_name = trainers.get(t_id, "Unassigned")
        f_total = float(s.get("fees_total") or 0)
        f_paid = float(s.get("fees_paid") or 0)
        f_bal = max(0.0, f_total - f_paid)
        row = [
            s.get("id", ""),
            s.get("name", ""),
            s.get("phone", ""),
            s.get("location", "Khajaguda"),
            s.get("joining_date", ""),
            s.get("slot_time", ""),
            s.get("total_classes", 12),
            f_total,
            f_paid,
            f_bal,
            t_name,
            s.get("pickup_address", "")
        ]
        ws_active.append(row)
        fill = ZEBRA_FILL if i % 2 == 0 else None
        for col_idx in range(1, len(row) + 1):
            cell = ws_active.cell(row=i, column=col_idx)
            cell.font = REGULAR_FONT
            cell.border = THIN_BORDER
            if fill:
                cell.fill = fill
            if col_idx in [8, 9, 10]:
                cell.number_format = '₹ #,##0'

    # Auto-adjust column widths for all sheets
    for ws in [ws_sum, ws_students, ws_classes, ws_pay, ws_active]:
        ws.freeze_panes = "A2"
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val = str(cell.value or "")
                if len(val) > max_len:
                    max_len = len(val)
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 40)

    # Save to file
    out_path = "LearnAndDrive_Historical_Archive_2026-10-25.xlsx"
    wb.save(out_path)
    print(f"SUCCESS! Excel workbook created and saved to: {out_path}")
    file_size_kb = os.path.getsize(out_path) / 1024
    print(f"File size: {file_size_kb:.1f} KB")

if __name__ == "__main__":
    build_excel_export()

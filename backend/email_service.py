"""
Hostinger Email Service for RideWell / Adarsh Motor Driving School
Handles transactional emails via Hostinger SMTP (smtp.hostinger.com).
Supports SSL (port 465) and STARTTLS (port 587).
"""

import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Dict, Any, List

logger = logging.getLogger("ridewell.email")

# Hostinger SMTP Configuration
HOSTINGER_SMTP_HOST = os.environ.get("HOSTINGER_SMTP_HOST", "smtp.hostinger.com")
HOSTINGER_SMTP_PORT = int(os.environ.get("HOSTINGER_SMTP_PORT", "465"))
HOSTINGER_SMTP_USER = os.environ.get("HOSTINGER_SMTP_USER", "")
HOSTINGER_SMTP_PASSWORD = os.environ.get("HOSTINGER_SMTP_PASSWORD", "")
HOSTINGER_SENDER_EMAIL = os.environ.get("HOSTINGER_SENDER_EMAIL", HOSTINGER_SMTP_USER or "noreply@ridewell.com")
HOSTINGER_SENDER_NAME = os.environ.get("HOSTINGER_SENDER_NAME", "Adarsh Driving School")

def is_smtp_configured() -> bool:
    """Check if Hostinger SMTP credentials have been provided in the environment."""
    return bool(HOSTINGER_SMTP_USER and HOSTINGER_SMTP_PASSWORD)

def get_email_config_status() -> Dict[str, Any]:
    """Returns safe summary of email configuration for admin dashboard."""
    return {
        "configured": is_smtp_configured(),
        "host": HOSTINGER_SMTP_HOST,
        "port": HOSTINGER_SMTP_PORT,
        "sender_email": HOSTINGER_SENDER_EMAIL,
        "sender_name": HOSTINGER_SENDER_NAME,
        "username_masked": f"{HOSTINGER_SMTP_USER[:3]}***@{HOSTINGER_SMTP_USER.split('@')[-1]}" if "@" in HOSTINGER_SMTP_USER else ("Configured" if HOSTINGER_SMTP_USER else "Not set")
    }

def send_smtp_email(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
    reply_to: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send an email using Hostinger SMTP.
    Returns {"success": True/False, "message": "..."}
    """
    if not is_smtp_configured():
        logger.warning("Hostinger SMTP is not configured (missing HOSTINGER_SMTP_USER or HOSTINGER_SMTP_PASSWORD). Email not sent to %s", to_email)
        return {
            "success": False,
            "error": "Hostinger SMTP credentials not configured in environment.",
            "simulated": True
        }

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{HOSTINGER_SENDER_NAME} <{HOSTINGER_SENDER_EMAIL}>"
        msg["To"] = to_email
        if reply_to:
            msg["Reply-To"] = reply_to

        # Attach text and HTML parts
        if text_body:
            msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        if HOSTINGER_SMTP_PORT == 465:
            # SSL connection
            with smtplib.SMTP_SSL(HOSTINGER_SMTP_HOST, HOSTINGER_SMTP_PORT, timeout=15) as server:
                server.login(HOSTINGER_SMTP_USER, HOSTINGER_SMTP_PASSWORD)
                server.sendmail(HOSTINGER_SENDER_EMAIL, [to_email], msg.as_string())
        else:
            # STARTTLS connection (typically port 587)
            with smtplib.SMTP(HOSTINGER_SMTP_HOST, HOSTINGER_SMTP_PORT, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(HOSTINGER_SMTP_USER, HOSTINGER_SMTP_PASSWORD)
                server.sendmail(HOSTINGER_SENDER_EMAIL, [to_email], msg.as_string())

        logger.info("Successfully sent Hostinger email to %s (Subject: %s)", to_email, subject)
        return {"success": True, "message": f"Email delivered to {to_email}"}
    except Exception as e:
        logger.error("Failed to send Hostinger email to %s: %s", to_email, str(e), exc_info=True)
        return {"success": False, "error": str(e)}


# -------------------------------------------------------------
# Pre-built Email Templates for Driving School Workflows
# -------------------------------------------------------------

def send_enrollment_email(student: Dict[str, Any]) -> Dict[str, Any]:
    """Send welcome and enrollment confirmation email to newly enrolled student."""
    to_email = student.get("email")
    if not to_email:
        return {"success": False, "skipped": True, "reason": "Student has no email"}

    student_name = student.get("name", "Student")
    joining_date = student.get("joining_date", "Today")
    slot_time = student.get("slot_time", "Assigned slot")
    location = student.get("location", "Hyderabad")
    total_classes = student.get("total_classes", 20)
    license_type = student.get("license_type", "4 Wheeler")
    fees_total = student.get("fees_total", 0)
    fees_paid = student.get("fees_paid", 0)
    fees_due = max(0, fees_total - fees_paid)

    subject = f"Welcome to Adarsh Driving School! Your Enrollment is Confirmed"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f4f4f5; margin: 0; padding: 20px; }}
        .card {{ max-width: 580px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.06); border: 1px solid #e4e4e7; }}
        .header {{ background: #09090b; color: #ffffff; padding: 32px 28px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 24px; font-weight: 700; letter-spacing: -0.5px; }}
        .header p {{ margin: 8px 0 0; color: #a1a1aa; font-size: 14px; }}
        .content {{ padding: 28px; color: #27272a; line-height: 1.6; font-size: 15px; }}
        .highlight-box {{ background: #fafafa; border: 1px solid #e4e4e7; border-radius: 8px; padding: 18px; margin: 20px 0; }}
        .grid-row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px dashed #e4e4e7; font-size: 14px; }}
        .grid-row:last-child {{ border-bottom: none; }}
        .label {{ color: #71717a; font-weight: 500; }}
        .value {{ font-weight: 600; color: #09090b; }}
        .badge {{ display: inline-block; background: #16a34a; color: white; padding: 3px 10px; border-radius: 9999px; font-size: 12px; font-weight: 600; }}
        .footer {{ text-align: center; padding: 24px; color: #71717a; font-size: 12px; border-top: 1px solid #f4f4f5; background: #fafafa; }}
      </style>
    </head>
    <body>
      <div class="card">
        <div class="header">
          <h1>Adarsh Motor Driving School</h1>
          <p>Training Safe & Confident Drivers</p>
        </div>
        <div class="content">
          <p>Dear <strong>{student_name}</strong>,</p>
          <p>Congratulations on taking the first step towards becoming a licensed, confident driver! Your enrollment has been successfully recorded in our academy.</p>
          
          <div class="highlight-box">
            <div style="font-weight: 700; margin-bottom: 12px; color: #09090b; font-size: 16px;">Enrollment Summary</div>
            <div class="grid-row"><span class="label">Course:</span> <span class="value">{license_type}</span></div>
            <div class="grid-row"><span class="label">Branch / Location:</span> <span class="value">{location}</span></div>
            <div class="grid-row"><span class="label">Batch Time:</span> <span class="value">{slot_time}</span></div>
            <div class="grid-row"><span class="label">Total Practical Classes:</span> <span class="value">{total_classes} sessions</span></div>
            <div class="grid-row"><span class="label">Start Date:</span> <span class="value">{joining_date}</span></div>
            <div class="grid-row"><span class="label">Fee Paid:</span> <span class="value">₹{fees_paid:,} / ₹{fees_total:,}</span></div>
            <div class="grid-row"><span class="label">Balance Due:</span> <span class="value" style="color: {'#dc2626' if fees_due > 0 else '#16a34a'};">₹{fees_due:,}</span></div>
          </div>

          <p><strong>What to expect on your first session:</strong></p>
          <ul>
            <li>Please arrive 5-10 minutes prior to your allocated slot.</li>
            <li>Wear comfortable flat-soled footwear (avoid high heels or heavy boots).</li>
            <li>Carry your Learner's License (LLR) copy or Aadhaar card.</li>
          </ul>

          <p>For any queries or schedule changes, reach out to your instructor or visit the academy desk.</p>
        </div>
        <div class="footer">
          <p>Adarsh Motor Driving School • Hyderabad</p>
          <p>Powered by Hostinger Email Services</p>
        </div>
      </div>
    </body>
    </html>
    """

    text_body = f"""Welcome to Adarsh Driving School, {student_name}!

Your enrollment is confirmed:
- Course: {license_type}
- Branch: {location}
- Daily Slot: {slot_time}
- Start Date: {joining_date}
- Total Classes: {total_classes}
- Fee Paid: ₹{fees_paid} (Due: ₹{fees_due})

Please bring your valid ID or Learner License.
Adarsh Motor Driving School
"""
    return send_smtp_email(to_email, subject, html_body, text_body)


def send_payment_receipt_email(payment: Dict[str, Any], student: Dict[str, Any]) -> Dict[str, Any]:
    """Send payment acknowledgement / digital receipt to student."""
    to_email = student.get("email")
    if not to_email:
        return {"success": False, "skipped": True, "reason": "Student has no email"}

    student_name = student.get("name", "Student")
    amount = payment.get("amount", 0)
    date = payment.get("date", "Today")
    method = payment.get("method", "Cash").upper()
    receipt_id = payment.get("id", "REC-001")[:8].upper()

    subject = f"Receipt #{receipt_id}: Payment of ₹{amount:,} received - Adarsh Driving School"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f4f4f5; margin: 0; padding: 20px; }}
        .card {{ max-width: 540px; margin: 0 auto; background: #ffffff; border-radius: 12px; border: 1px solid #e4e4e7; overflow: hidden; }}
        .header {{ background: #16a34a; color: white; padding: 24px; text-align: center; }}
        .body {{ padding: 28px; color: #27272a; line-height: 1.5; }}
        .amount-box {{ background: #f0fdf4; border: 1px solid #bbf7d0; text-align: center; padding: 20px; border-radius: 8px; margin: 16px 0; }}
        .amount-num {{ font-size: 32px; font-weight: 800; color: #166534; }}
        .table {{ width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 14px; }}
        .table td {{ padding: 8px 4px; border-bottom: 1px solid #f4f4f5; }}
        .table td.title {{ color: #71717a; }}
        .table td.val {{ text-align: right; font-weight: 600; color: #09090b; }}
      </style>
    </head>
    <body>
      <div class="card">
        <div class="header">
          <h2 style="margin: 0;">Payment Receipt</h2>
          <p style="margin: 4px 0 0; opacity: 0.9; font-size: 13px;">Adarsh Motor Driving School</p>
        </div>
        <div class="body">
          <p>Hello <strong>{student_name}</strong>,</p>
          <p>Thank you for your payment. Here is your transaction confirmation:</p>
          <div class="amount-box">
            <div style="font-size: 13px; color: #15803d; font-weight: 600; text-transform: uppercase;">Amount Paid</div>
            <div class="amount-num">₹{amount:,}</div>
            <div style="font-size: 12px; color: #166534;">Payment Successful</div>
          </div>
          <table class="table">
            <tr><td class="title">Receipt Number</td><td class="val">{receipt_id}</td></tr>
            <tr><td class="title">Payment Date</td><td class="val">{date}</td></tr>
            <tr><td class="title">Payment Mode</td><td class="val">{method}</td></tr>
            <tr><td class="title">Student Name</td><td class="val">{student_name}</td></tr>
            <tr><td class="title">Student ID</td><td class="val">{student.get('id', '—')}</td></tr>
          </table>
        </div>
      </div>
    </body>
    </html>
    """
    return send_smtp_email(to_email, subject, html_body)

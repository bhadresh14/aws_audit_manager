"""
AWS Audit Manager - Email Reports & Scheduled Scans
=====================================================
Sends PDF audit reports via email using AWS SES.
Supports scheduled scans (daily/weekly/monthly).
"""

import boto3
import json
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import Dict, Any, Optional, List
from datetime import datetime


# Configuration file for schedules
SCHEDULE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "output", "schedules.json"
)


def send_report_email(
    to_emails: List[str],
    subject: str,
    body_html: str,
    pdf_bytes: bytes = None,
    pdf_filename: str = "audit_report.pdf",
    from_email: str = None,
    profile: str = None
) -> Dict[str, Any]:
    """
    Send audit report email via Gmail SMTP.
    
    Configuration is read from /opt/aws-health-check/output/email_config.json:
    {
        "smtp_email": "your@gmail.com",
        "smtp_password": "your-app-password",
        "from_name": "AWS Audit Manager"
    }
    """
    try:
        import smtplib

        # Load config
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "output", "email_config.json"
        )
        if not os.path.exists(config_path):
            return {"status": "error", "error": "Email not configured. Go to Settings to configure Gmail SMTP."}

        with open(config_path, 'r') as f:
            config = json.load(f)

        smtp_email = config.get('smtp_email', '')
        smtp_password = config.get('smtp_password', '')
        from_name = config.get('from_name', 'AWS Audit Manager')

        if not smtp_email or not smtp_password:
            return {"status": "error", "error": "Gmail credentials not configured."}

        sender = f"{from_name} <{smtp_email}>"

        # Build email
        msg = MIMEMultipart('mixed')
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = ', '.join(to_emails)

        # HTML body
        body_part = MIMEMultipart('alternative')
        html_part = MIMEText(body_html, 'html')
        body_part.attach(html_part)
        msg.attach(body_part)

        # PDF attachment
        if pdf_bytes:
            pdf_part = MIMEApplication(pdf_bytes, _subtype='pdf')
            pdf_part.add_header('Content-Disposition', 'attachment', filename=pdf_filename)
            msg.attach(pdf_part)

        # Send via Gmail SMTP
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, to_emails, msg.as_string())

        return {
            "status": "sent",
            "message": f"Report sent to {', '.join(to_emails)}",
            "recipients": to_emails
        }

    except Exception as e:
        error = str(e)
        if 'Authentication' in error or 'credentials' in error.lower():
            return {"status": "error", "error": "Gmail authentication failed. Check your App Password."}
        elif 'Connection' in error:
            return {"status": "error", "error": "Cannot connect to Gmail SMTP. Check network."}
        else:
            return {"status": "error", "error": error[:200]}


def build_report_email_html(report_data: Dict[str, Any]) -> str:
    """Build a nice HTML email body summarizing the audit"""
    exec_sum = report_data.get('executive_summary', {})
    scores = report_data.get('scores', {})
    security = report_data.get('security_audit', {}).get('summary', {})
    cost = report_data.get('cost_analysis', {})
    opt = report_data.get('optimization', {}).get('summary', {})

    overall = scores.get('overall_score', 'N/A')
    status = scores.get('overall_status', '')
    account = report_data.get('report_metadata', {}).get('account_info', {}).get('account_id', 'N/A')

    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #232F3E; padding: 20px; text-align: center;">
            <h1 style="color: #FF9900; margin: 0;">AWS Audit Manager</h1>
            <p style="color: #ffffff; margin: 5px 0 0 0;">Weekly Security &amp; Cost Report</p>
        </div>
        
        <div style="padding: 20px; background: #ffffff;">
            <p>Here's your AWS audit summary for account <strong>{account}</strong>:</p>
            
            <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
                <tr style="background: #f8f9fa;">
                    <td style="padding: 12px; text-align: center; border: 1px solid #dee2e6;">
                        <div style="font-size: 24px; font-weight: bold; color: {'#28a745' if overall != 'N/A' and overall >= 70 else '#dc3545'};">{overall}/100</div>
                        <div style="font-size: 12px; color: #666;">Health Score</div>
                    </td>
                    <td style="padding: 12px; text-align: center; border: 1px solid #dee2e6;">
                        <div style="font-size: 24px; font-weight: bold;">${cost.get('total_cost', 0):,.2f}</div>
                        <div style="font-size: 12px; color: #666;">Monthly Cost</div>
                    </td>
                    <td style="padding: 12px; text-align: center; border: 1px solid #dee2e6;">
                        <div style="font-size: 24px; font-weight: bold; color: #dc3545;">{security.get('critical', 0)}</div>
                        <div style="font-size: 12px; color: #666;">Critical Issues</div>
                    </td>
                    <td style="padding: 12px; text-align: center; border: 1px solid #dee2e6;">
                        <div style="font-size: 24px; font-weight: bold; color: #28a745;">${opt.get('potential_monthly_savings', 0):,.2f}</div>
                        <div style="font-size: 12px; color: #666;">Savings/mo</div>
                    </td>
                </tr>
            </table>
            
            <p>{exec_sum.get('text_summary', 'Scan completed successfully.')}</p>
            
            <p style="margin-top: 20px;">
                <a href="https://auditmanager.calyzatech.com" style="background: #FF9900; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Full Report</a>
            </p>
        </div>
        
        <div style="padding: 15px; background: #f8f9fa; text-align: center; font-size: 12px; color: #666;">
            AWS Audit Manager | Automated report | <a href="https://auditmanager.calyzatech.com">auditmanager.calyzatech.com</a>
        </div>
    </div>
    """
    return html


# ============ SCHEDULE MANAGEMENT ============

def get_schedules() -> List[Dict]:
    """Get all configured scan schedules"""
    if os.path.exists(SCHEDULE_FILE):
        with open(SCHEDULE_FILE, 'r') as f:
            return json.load(f)
    return []


def save_schedule(schedule: Dict) -> Dict:
    """Save a new schedule"""
    schedules = get_schedules()
    schedule['id'] = f"sched_{len(schedules)+1}_{int(datetime.utcnow().timestamp())}"
    schedule['created_at'] = datetime.utcnow().isoformat()
    schedule['last_run'] = None
    schedule['active'] = True
    schedules.append(schedule)

    with open(SCHEDULE_FILE, 'w') as f:
        json.dump(schedules, f, indent=2)

    return schedule


def delete_schedule(schedule_id: str) -> bool:
    """Delete a schedule by ID"""
    schedules = get_schedules()
    schedules = [s for s in schedules if s.get('id') != schedule_id]
    with open(SCHEDULE_FILE, 'w') as f:
        json.dump(schedules, f, indent=2)
    return True

"""
AWS Audit Manager - Web Dashboard
FastAPI-based web interface with compliance, PDF export, and analytics.
"""

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import os
import sys
import json
import glob
import io
from datetime import datetime
from typing import Optional, List, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = FastAPI(
    title="AWS Audit Manager",
    description="Web interface for AWS Audit Manager",
    version="2.0.0"
)

# Configuration
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

# Setup templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Dashboard home page"""
    reports = get_available_reports()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "reports": reports,
            "title": "AWS Audit Manager Dashboard"
        }
    )


@app.get("/api/reports", response_class=JSONResponse)
async def list_reports():
    """API endpoint to list all available reports"""
    reports = get_available_reports()
    return {"reports": reports, "count": len(reports)}


@app.get("/api/reports/{report_id}", response_class=JSONResponse)
async def get_report(report_id: str):
    """API endpoint to get a specific report's JSON data"""
    json_path = os.path.join(OUTPUT_DIR, f"{report_id}.json")
    if not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail="Report not found")
    with open(json_path, 'r') as f:
        data = json.load(f)
    return data


@app.get("/report/{report_id}", response_class=HTMLResponse)
async def view_report(request: Request, report_id: str):
    """View a specific report in the dashboard"""
    json_path = os.path.join(OUTPUT_DIR, f"{report_id}.json")
    if not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail="Report not found")
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    # Compute scores on-the-fly if not present (for older reports)
    if 'scores' not in data or 'executive_summary' not in data:
        try:
            from modules.scoring import calculate_scores, generate_executive_summary, get_top_priority_actions
            scores = calculate_scores(data)
            data['scores'] = scores
            data['executive_summary'] = generate_executive_summary(data, scores)
            data['top_priority_actions'] = get_top_priority_actions(data)
        except Exception:
            pass
    
    return templates.TemplateResponse(
        request=request,
        name="report.html",
        context={
            "report": data,
            "report_id": report_id,
            "title": f"Report - {report_id}"
        }
    )


@app.get("/report/{report_id}/html", response_class=HTMLResponse)
async def get_html_report(report_id: str):
    """Return the original HTML report"""
    html_path = os.path.join(OUTPUT_DIR, f"{report_id}.html")
    if not os.path.exists(html_path):
        raise HTTPException(status_code=404, detail="HTML report not found")
    return FileResponse(html_path, media_type="text/html")


@app.get("/report/{report_id}/download/{format}")
async def download_report(report_id: str, format: str):
    """Download report in specified format (json, html, md, pdf)"""
    if format.lower() == 'pdf':
        return await generate_pdf_report(report_id)

    ext_map = {"json": "json", "html": "html", "md": "md", "markdown": "md"}
    ext = ext_map.get(format.lower())
    if not ext:
        raise HTTPException(status_code=400, detail="Invalid format. Use: json, html, md, pdf")

    file_path = os.path.join(OUTPUT_DIR, f"{report_id}.{ext}")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"{format.upper()} report not found")

    return FileResponse(
        file_path,
        filename=f"{report_id}.{ext}",
        media_type="application/octet-stream"
    )


async def generate_pdf_report(report_id: str):
    """Generate a business-friendly PDF report"""
    json_path = os.path.join(OUTPUT_DIR, f"{report_id}.json")
    if not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail="Report not found")

    with open(json_path, 'r') as f:
        data = json.load(f)

    # Ensure scores and executive summary are present
    if 'scores' not in data or 'executive_summary' not in data:
        try:
            from modules.scoring import calculate_scores, generate_executive_summary, get_top_priority_actions
            scores = calculate_scores(data)
            data['scores'] = scores
            data['executive_summary'] = generate_executive_summary(data, scores)
            data['top_priority_actions'] = get_top_priority_actions(data)
        except Exception:
            pass

    # Use the new business-friendly PDF generator
    try:
        from modules.pdf_report import generate_business_pdf
        pdf_bytes = generate_business_pdf(data, report_id)
    except Exception as e:
        # Fallback to old generator
        print(f"Business PDF failed, using fallback: {e}")
        pdf_bytes = create_pdf(data, report_id)

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={report_id}.pdf"}
    )


@app.post("/api/scan")
async def trigger_scan(
    background_tasks: BackgroundTasks,
    profile: Optional[str] = None,
    region: Optional[str] = None
):
    """Trigger a new health check scan"""
    background_tasks.add_task(run_health_check, profile, region)
    return {
        "status": "started",
        "message": "Health check scan started in background",
        "profile": profile,
        "region": region
    }


@app.post("/api/remediate/ec2-resize")
async def remediate_ec2_resize(request: Request):
    """Resize an EC2 instance (stop → change type → start). Requires explicit confirmation."""
    try:
        body = await request.json()
        instance_id = body.get('instance_id', '').strip()
        new_instance_type = body.get('new_instance_type', '').strip()
        region = body.get('region', '').strip()
        confirmed = body.get('confirmed', False)

        if not instance_id or not new_instance_type or not region:
            raise HTTPException(status_code=400, detail="instance_id, new_instance_type, and region are required")

        if not confirmed:
            raise HTTPException(status_code=400, detail="Action not confirmed. Set confirmed=true to proceed.")

        # Validate instance ID format
        if not instance_id.startswith('i-'):
            raise HTTPException(status_code=400, detail="Invalid instance ID format")

        # Get the profile to use
        profiles = get_aws_profiles()
        profile_name = profiles[0]['name'] if profiles else None

        from modules.remediation import resize_ec2_instance
        result = resize_ec2_instance(
            instance_id=instance_id,
            new_instance_type=new_instance_type,
            region=region,
            profile=profile_name
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        return {"status": "failed", "message": f"Error: {str(e)[:200]}"}


@app.get("/api/remediate/log")
async def get_remediation_activity_log():
    """Get the log of all remediation actions performed"""
    from modules.remediation import get_remediation_log
    return {"log": get_remediation_log()}


@app.post("/api/advisor")
async def ask_audit_advisor(request: Request):
    """AI Audit Advisor - ask questions about scan results"""
    try:
        body = await request.json()
        question = body.get('question', '').strip()
        report_id = body.get('report_id', '').strip()

        if not question:
            raise HTTPException(status_code=400, detail="Question is required")

        # Load report data
        if report_id:
            json_path = os.path.join(OUTPUT_DIR, f"{report_id}.json")
        else:
            # Use latest report
            reports = get_available_reports()
            if not reports:
                return {"answer": "No scan data available. Please run a scan first.", "status": "no_data"}
            json_path = os.path.join(OUTPUT_DIR, f"{reports[0]['id']}.json")

        if not os.path.exists(json_path):
            raise HTTPException(status_code=404, detail="Report not found")

        with open(json_path, 'r') as f:
            report_data = json.load(f)

        # Compute scores if not present
        if 'scores' not in report_data:
            try:
                from modules.scoring import calculate_scores, generate_executive_summary, get_top_priority_actions
                scores = calculate_scores(report_data)
                report_data['scores'] = scores
                report_data['executive_summary'] = generate_executive_summary(report_data, scores)
                report_data['top_priority_actions'] = get_top_priority_actions(report_data)
            except Exception:
                pass

        # Ask the AI
        from modules.ai_advisor import ask_advisor
        result = ask_advisor(question, report_data)
        return result

    except HTTPException:
        raise
    except Exception as e:
        return {"answer": f"Error: {str(e)[:200]}", "status": "error"}


@app.get("/api/advisor/suggestions")
async def get_advisor_suggestions():
    """Get suggested questions for the AI Advisor"""
    from modules.ai_advisor import SUGGESTED_QUESTIONS
    return {"suggestions": SUGGESTED_QUESTIONS}


@app.get("/api/status")
async def get_status():
    """Get dashboard status"""
    reports = get_available_reports()
    return {
        "status": "running",
        "reports_count": len(reports),
        "output_dir": OUTPUT_DIR,
        "latest_report": reports[0] if reports else None
    }


@app.get("/api/profiles")
async def list_profiles():
    """List available AWS profiles"""
    profiles = get_aws_profiles()
    return {"profiles": profiles, "count": len(profiles)}


@app.post("/api/profiles")
async def create_profile(request: Request):
    """Create a new AWS profile using IAM Role ARN (cross-account assume role)"""
    try:
        data = await request.json()
        profile_name = data.get('profile_name', '').strip()
        role_arn = data.get('role_arn', '').strip()
        external_id = data.get('external_id', '').strip()
        region = data.get('region', 'ap-south-1').strip()

        if not profile_name:
            raise HTTPException(status_code=400, detail="Profile name is required")
        if not role_arn:
            raise HTTPException(status_code=400, detail="Role ARN is required")
        if not role_arn.startswith('arn:aws:iam::'):
            raise HTTPException(status_code=400, detail="Invalid Role ARN format. Expected: arn:aws:iam::ACCOUNT_ID:role/ROLE_NAME")

        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', profile_name):
            raise HTTPException(status_code=400, detail="Invalid profile name format")

        existing_profiles = get_aws_profiles()
        if any(p['name'] == profile_name for p in existing_profiles):
            raise HTTPException(status_code=400, detail=f"Profile '{profile_name}' already exists")

        import boto3
        from botocore.exceptions import ClientError
        import configparser

        home_dir = os.path.expanduser("~")
        credentials_file = os.path.join(home_dir, ".aws", "credentials")
        config_file = os.path.join(home_dir, ".aws", "config")
        aws_dir = os.path.join(home_dir, ".aws")
        os.makedirs(aws_dir, exist_ok=True)

        # Validate by assuming the role
        try:
            source_session = boto3.Session()
            try:
                sts = source_session.client('sts')
                sts.get_caller_identity()
            except Exception:
                creds_parser = configparser.ConfigParser()
                if os.path.exists(credentials_file):
                    creds_parser.read(credentials_file)
                profiles = [s for s in creds_parser.sections() if s != 'default']
                if profiles:
                    source_session = boto3.Session(profile_name=profiles[0])

            sts = source_session.client('sts')
            assume_params = {
                'RoleArn': role_arn,
                'RoleSessionName': f'AuditManager-{profile_name}',
                'DurationSeconds': 900
            }
            if external_id:
                assume_params['ExternalId'] = external_id

            response = sts.assume_role(**assume_params)
            credentials = response['Credentials']

            # Verify the assumed role works
            assumed_session = boto3.Session(
                aws_access_key_id=credentials['AccessKeyId'],
                aws_secret_access_key=credentials['SecretAccessKey'],
                aws_session_token=credentials['SessionToken'],
                region_name=region
            )
            assumed_sts = assumed_session.client('sts')
            identity = assumed_sts.get_caller_identity()
            account_id = identity.get('Account')
            user_arn_result = identity.get('Arn')

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'AccessDenied':
                raise HTTPException(status_code=400, detail="Access denied. Check the role's trust policy allows this account to assume it.")
            raise HTTPException(status_code=400, detail=f"AWS Error: {error_code} - {str(e)[:100]}")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to assume role: {str(e)[:150]}")

        # Save to config file (role-based profile)
        config_parser = configparser.ConfigParser()
        if os.path.exists(config_file):
            config_parser.read(config_file)
        config_section = f'profile {profile_name}'
        config_parser[config_section] = {
            'role_arn': role_arn,
            'region': region,
        }
        if external_id:
            config_parser[config_section]['external_id'] = external_id

        # Find a source profile to use
        creds_parser = configparser.ConfigParser()
        if os.path.exists(credentials_file):
            creds_parser.read(credentials_file)
        source_profiles = [s for s in creds_parser.sections() if s != 'default']
        if source_profiles:
            config_parser[config_section]['source_profile'] = source_profiles[0]

        with open(config_file, 'w') as f:
            config_parser.write(f)

        return {
            "success": True,
            "message": f"Profile '{profile_name}' connected via IAM Role",
            "profile_name": profile_name,
            "account_id": account_id,
            "user_arn": user_arn_result,
            "region": region,
            "auth_method": "role_arn"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create profile: {str(e)}")


# ============ ONBOARDING ============

CFN_TEMPLATE = open(os.path.join(BASE_DIR, "deploy", "audit-manager-role.yaml")).read() if os.path.exists(os.path.join(BASE_DIR, "deploy", "audit-manager-role.yaml")) else "Template not found"
TOOL_ACCOUNT_ID = "508137168365"

@app.get("/onboarding", response_class=HTMLResponse)
async def onboarding_page(request: Request):
    """Onboarding wizard for new customers"""
    return templates.TemplateResponse(
        request=request,
        name="onboarding.html",
        context={
            "title": "Connect AWS Account",
            "cfn_template": CFN_TEMPLATE,
            "tool_account_id": TOOL_ACCOUNT_ID
        }
    )


# ============ EMAIL & SCHEDULING ============

@app.post("/api/email/send-report")
async def send_report_via_email(request: Request):
    """Send a report PDF via email"""
    try:
        body = await request.json()
        report_id = body.get('report_id', '').strip()
        to_emails = body.get('emails', [])

        if not to_emails:
            raise HTTPException(status_code=400, detail="At least one email is required")
        if not report_id:
            reports = get_available_reports()
            if not reports:
                raise HTTPException(status_code=404, detail="No reports available")
            report_id = reports[0]['id']

        # Load report
        json_path = os.path.join(OUTPUT_DIR, f"{report_id}.json")
        if not os.path.exists(json_path):
            raise HTTPException(status_code=404, detail="Report not found")
        with open(json_path, 'r') as f:
            report_data = json.load(f)

        # Add scores if missing
        if 'scores' not in report_data:
            try:
                from modules.scoring import calculate_scores, generate_executive_summary, get_top_priority_actions
                scores = calculate_scores(report_data)
                report_data['scores'] = scores
                report_data['executive_summary'] = generate_executive_summary(report_data, scores)
                report_data['top_priority_actions'] = get_top_priority_actions(report_data)
            except Exception:
                pass

        # Generate PDF
        try:
            from modules.pdf_report import generate_business_pdf
            pdf_bytes = generate_business_pdf(report_data, report_id)
        except Exception:
            pdf_bytes = None

        # Build email
        from modules.email_reports import send_report_email, build_report_email_html
        html_body = build_report_email_html(report_data)

        account_id = report_data.get('report_metadata', {}).get('account_info', {}).get('account_id', 'N/A')
        subject = f"AWS Audit Report - Account {account_id} - {datetime.now().strftime('%Y-%m-%d')}"

        result = send_report_email(
            to_emails=to_emails,
            subject=subject,
            body_html=html_body,
            pdf_bytes=pdf_bytes,
            pdf_filename=f"{report_id}.pdf"
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "error": str(e)[:200]}


@app.post("/api/email/configure")
async def configure_email(request: Request):
    """Configure Gmail SMTP settings"""
    try:
        body = await request.json()
        smtp_email = body.get('smtp_email', '').strip()
        smtp_password = body.get('smtp_password', '').strip()
        from_name = body.get('from_name', 'AWS Audit Manager').strip()

        if not smtp_email or not smtp_password:
            raise HTTPException(status_code=400, detail="Email and App Password are required")

        # Test the connection
        import smtplib
        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=10) as server:
                server.login(smtp_email, smtp_password)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Gmail login failed: {str(e)[:100]}")

        # Save config
        config_path = os.path.join(OUTPUT_DIR, "email_config.json")
        with open(config_path, 'w') as f:
            json.dump({
                "smtp_email": smtp_email,
                "smtp_password": smtp_password,
                "from_name": from_name
            }, f)

        return {"status": "configured", "message": f"Email configured: {smtp_email}"}

    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "error": str(e)[:200]}


@app.get("/api/email/status")
async def email_status():
    """Check if email is configured"""
    config_path = os.path.join(OUTPUT_DIR, "email_config.json")
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = json.load(f)
        return {"configured": True, "email": config.get("smtp_email", "")}
    return {"configured": False}


@app.get("/api/schedules")
async def list_schedules():
    """List all scan schedules"""
    from modules.email_reports import get_schedules
    return {"schedules": get_schedules()}


@app.post("/api/schedules")
async def create_schedule(request: Request):
    """Create a new scan schedule"""
    try:
        body = await request.json()
        from modules.email_reports import save_schedule
        schedule = save_schedule({
            "profile": body.get('profile', ''),
            "region": body.get('region', 'ap-south-1'),
            "frequency": body.get('frequency', 'weekly'),  # daily, weekly, monthly
            "day": body.get('day', 'monday'),  # for weekly
            "emails": body.get('emails', []),
            "send_email": body.get('send_email', True),
        })
        return {"status": "created", "schedule": schedule}
    except Exception as e:
        return {"status": "error", "error": str(e)[:200]}


@app.delete("/api/schedules/{schedule_id}")
async def remove_schedule(schedule_id: str):
    """Delete a schedule"""
    from modules.email_reports import delete_schedule
    delete_schedule(schedule_id)
    return {"status": "deleted"}


# ============ COMPLIANCE ENDPOINTS ============

@app.get("/compliance", response_class=HTMLResponse)
async def compliance_dashboard(request: Request):
    """Compliance dashboard with CIS, SOC2, HIPAA mappings"""
    reports = get_available_reports()
    if not reports:
        return templates.TemplateResponse(
            request=request,
            name="compliance.html",
            context={"title": "Compliance", "report": None,
                     "cis_checks": [], "soc2_checks": [], "hipaa_checks": [],
                     "cis_score": 0, "soc2_score": 0, "hipaa_score": 0,
                     "cis_pass": 0, "cis_total": 0,
                     "soc2_pass": 0, "soc2_total": 0,
                     "hipaa_pass": 0, "hipaa_total": 0}
        )

    # Load latest report
    json_path = os.path.join(OUTPUT_DIR, f"{reports[0]['id']}.json")
    with open(json_path, 'r') as f:
        report_data = json.load(f)

    # Generate compliance mappings
    findings = report_data.get('security_audit', {}).get('findings', [])
    cis_checks = map_to_cis(findings, report_data)
    soc2_checks = map_to_soc2(findings, report_data)
    hipaa_checks = map_to_hipaa(findings, report_data)

    cis_pass = sum(1 for c in cis_checks if c['status'] == 'PASS')
    soc2_pass = sum(1 for c in soc2_checks if c['status'] == 'PASS')
    hipaa_pass = sum(1 for c in hipaa_checks if c['status'] == 'PASS')

    cis_total = len(cis_checks)
    soc2_total = len(soc2_checks)
    hipaa_total = len(hipaa_checks)

    cis_score = int((cis_pass / cis_total * 100)) if cis_total > 0 else 0
    soc2_score = int((soc2_pass / soc2_total * 100)) if soc2_total > 0 else 0
    hipaa_score = int((hipaa_pass / hipaa_total * 100)) if hipaa_total > 0 else 0

    return templates.TemplateResponse(
        request=request,
        name="compliance.html",
        context={
            "title": "Compliance",
            "report": report_data,
            "cis_checks": cis_checks, "soc2_checks": soc2_checks, "hipaa_checks": hipaa_checks,
            "cis_score": cis_score, "soc2_score": soc2_score, "hipaa_score": hipaa_score,
            "cis_pass": cis_pass, "cis_total": cis_total,
            "soc2_pass": soc2_pass, "soc2_total": soc2_total,
            "hipaa_pass": hipaa_pass, "hipaa_total": hipaa_total
        }
    )


@app.get("/compliance/export/pdf")
async def export_compliance_pdf():
    """Export compliance report as PDF"""
    reports = get_available_reports()
    if not reports:
        raise HTTPException(status_code=404, detail="No reports available")

    json_path = os.path.join(OUTPUT_DIR, f"{reports[0]['id']}.json")
    with open(json_path, 'r') as f:
        report_data = json.load(f)

    findings = report_data.get('security_audit', {}).get('findings', [])
    cis_checks = map_to_cis(findings, report_data)
    soc2_checks = map_to_soc2(findings, report_data)
    hipaa_checks = map_to_hipaa(findings, report_data)

    pdf_bytes = create_compliance_pdf(report_data, cis_checks, soc2_checks, hipaa_checks)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=compliance_report.pdf"}
    )


# ============ COMPLIANCE MAPPING FUNCTIONS ============

def map_to_cis(findings: list, report_data: dict) -> List[Dict]:
    """Map security findings to CIS AWS Foundations Benchmark v1.5"""
    finding_categories = set(f.get('category', '').lower() for f in findings)
    finding_texts = ' '.join(f.get('description', '').lower() for f in findings)

    checks = [
        {"id": "1.1", "title": "Maintain current contact details",
         "description": "Ensure account contact information is current",
         "category": "iam", "keywords": ["contact"]},
        {"id": "1.4", "title": "Ensure no root account access key exists",
         "description": "Root account should not have access keys",
         "category": "iam", "keywords": ["root", "access key"]},
        {"id": "1.5", "title": "Ensure MFA is enabled for root account",
         "description": "Root account must have MFA enabled",
         "category": "iam", "keywords": ["root", "mfa"]},
        {"id": "1.10", "title": "Ensure MFA enabled for all IAM users with console access",
         "description": "All IAM users with console password should have MFA",
         "category": "iam", "keywords": ["mfa", "iam user"]},
        {"id": "1.12", "title": "Ensure credentials unused for 45+ days are disabled",
         "description": "Remove or deactivate unused credentials",
         "category": "iam", "keywords": ["unused", "credential", "inactive"]},
        {"id": "1.14", "title": "Ensure access keys are rotated every 90 days",
         "description": "Regular key rotation reduces risk",
         "category": "iam", "keywords": ["rotate", "access key", "90 day"]},
        {"id": "2.1.1", "title": "Ensure S3 buckets are not publicly accessible",
         "description": "S3 buckets should block public access",
         "category": "s3", "keywords": ["public", "s3", "bucket"]},
        {"id": "2.1.2", "title": "Ensure S3 bucket policy denies HTTP requests",
         "description": "Enforce encryption in transit for S3",
         "category": "s3", "keywords": ["s3", "encryption", "http"]},
        {"id": "2.2.1", "title": "Ensure EBS volume encryption is enabled",
         "description": "EBS volumes should be encrypted at rest",
         "category": "ebs", "keywords": ["ebs", "encrypt", "volume"]},
        {"id": "2.3.1", "title": "Ensure RDS instances are encrypted",
         "description": "RDS database storage should be encrypted",
         "category": "rds", "keywords": ["rds", "encrypt"]},
        {"id": "3.1", "title": "Ensure CloudTrail is enabled in all regions",
         "description": "CloudTrail provides audit logging",
         "category": "logging", "keywords": ["cloudtrail", "logging"]},
        {"id": "4.1", "title": "Ensure no security groups allow ingress from 0.0.0.0/0 to port 22",
         "description": "SSH should not be open to the world",
         "category": "networking", "keywords": ["security group", "0.0.0.0", "ssh", "port 22"]},
        {"id": "4.2", "title": "Ensure no security groups allow ingress from 0.0.0.0/0 to port 3389",
         "description": "RDP should not be open to the world",
         "category": "networking", "keywords": ["security group", "0.0.0.0", "rdp", "3389"]},
        {"id": "4.3", "title": "Ensure default security group restricts all traffic",
         "description": "Default SG should have no inbound/outbound rules",
         "category": "networking", "keywords": ["default", "security group"]},
        {"id": "5.1", "title": "Ensure no Network ACLs allow unrestricted ingress",
         "description": "NACLs should restrict inbound traffic",
         "category": "networking", "keywords": ["nacl", "network acl", "unrestricted"]},
    ]

    for check in checks:
        has_issue = any(kw in finding_texts for kw in check['keywords'])
        check['status'] = 'FAIL' if has_issue else 'PASS'

    return checks


def map_to_soc2(findings: list, report_data: dict) -> List[Dict]:
    """Map findings to SOC 2 Trust Service Criteria"""
    finding_texts = ' '.join(f.get('description', '').lower() for f in findings)

    checks = [
        {"id": "CC6.1", "title": "Logical and Physical Access Controls",
         "description": "Restrict access to information assets",
         "keywords": ["security group", "public", "0.0.0.0", "unrestricted"]},
        {"id": "CC6.2", "title": "User Authentication",
         "description": "Authenticate users before granting access",
         "keywords": ["mfa", "password", "authentication"]},
        {"id": "CC6.3", "title": "User Authorization",
         "description": "Authorize access based on business need",
         "keywords": ["iam", "policy", "permission", "overly permissive"]},
        {"id": "CC6.6", "title": "Encryption of Data in Transit",
         "description": "Protect data during transmission",
         "keywords": ["ssl", "tls", "https", "encryption in transit"]},
        {"id": "CC6.7", "title": "Encryption of Data at Rest",
         "description": "Protect stored data with encryption",
         "keywords": ["encrypt", "unencrypted", "ebs", "rds", "s3"]},
        {"id": "CC7.1", "title": "Detect and Monitor Anomalies",
         "description": "Implement monitoring and detection controls",
         "keywords": ["cloudtrail", "monitoring", "logging", "cloudwatch"]},
        {"id": "CC7.2", "title": "Monitor System Components",
         "description": "Monitor infrastructure for security events",
         "keywords": ["alarm", "monitor", "alert", "detection"]},
        {"id": "CC8.1", "title": "Change Management",
         "description": "Control changes to infrastructure",
         "keywords": ["version", "change", "deployment"]},
        {"id": "A1.1", "title": "Availability - Capacity Planning",
         "description": "Plan and manage capacity requirements",
         "keywords": ["capacity", "scaling", "auto scaling"]},
        {"id": "A1.2", "title": "Availability - Backup and Recovery",
         "description": "Implement data backup procedures",
         "keywords": ["backup", "snapshot", "recovery", "disaster"]},
    ]

    for check in checks:
        has_issue = any(kw in finding_texts for kw in check['keywords'])
        check['status'] = 'FAIL' if has_issue else 'PASS'

    return checks


def map_to_hipaa(findings: list, report_data: dict) -> List[Dict]:
    """Map findings to HIPAA Technical Safeguards"""
    finding_texts = ' '.join(f.get('description', '').lower() for f in findings)

    checks = [
        {"id": "164.312(a)(1)", "title": "Access Control - Unique User Identification",
         "description": "Assign unique identifier to each user",
         "keywords": ["iam user", "shared", "root account"]},
        {"id": "164.312(a)(2)(i)", "title": "Access Control - Emergency Access",
         "description": "Establish procedures for emergency access",
         "keywords": ["emergency", "break glass", "root"]},
        {"id": "164.312(a)(2)(iv)", "title": "Access Control - Encryption and Decryption",
         "description": "Implement encryption mechanisms for ePHI",
         "keywords": ["encrypt", "unencrypted", "ebs", "rds", "s3"]},
        {"id": "164.312(b)", "title": "Audit Controls",
         "description": "Implement audit logging mechanisms",
         "keywords": ["cloudtrail", "logging", "audit", "monitor"]},
        {"id": "164.312(c)(1)", "title": "Integrity - ePHI Protection",
         "description": "Protect ePHI from improper modification",
         "keywords": ["integrity", "versioning", "backup"]},
        {"id": "164.312(d)", "title": "Person or Entity Authentication",
         "description": "Verify identity before granting access",
         "keywords": ["mfa", "authentication", "multi-factor"]},
        {"id": "164.312(e)(1)", "title": "Transmission Security",
         "description": "Protect ePHI during transmission",
         "keywords": ["ssl", "tls", "https", "public", "unencrypted"]},
        {"id": "164.312(e)(2)(ii)", "title": "Transmission Security - Encryption",
         "description": "Encrypt ePHI when transmitted over networks",
         "keywords": ["encrypt", "transit", "ssl", "tls"]},
        {"id": "164.308(a)(5)", "title": "Security Awareness Training",
         "description": "Implement security awareness program",
         "keywords": ["training", "awareness"]},
        {"id": "164.310(d)(1)", "title": "Device and Media Controls",
         "description": "Govern hardware and electronic media",
         "keywords": ["ebs", "snapshot", "ami", "volume"]},
    ]

    for check in checks:
        has_issue = any(kw in finding_texts for kw in check['keywords'])
        check['status'] = 'FAIL' if has_issue else 'PASS'

    return checks


# ============ PDF GENERATION ============

def create_pdf(data: dict, report_id: str) -> bytes:
    """Create a branded PDF report using simple HTML-to-text approach"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import inch, cm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        return _create_reportlab_pdf(data, report_id)
    except ImportError:
        # Fallback: generate a simple text-based PDF-like format
        return _create_simple_pdf(data, report_id)


def _create_reportlab_pdf(data: dict, report_id: str) -> bytes:
    """Generate PDF using ReportLab"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.75*inch, bottomMargin=0.75*inch)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title_style = ParagraphStyle('CustomTitle', parent=styles['Title'],
                                  fontSize=22, textColor=colors.HexColor('#232F3E'))
    story.append(Paragraph("AWS Audit Manager", title_style))
    story.append(Paragraph("Infrastructure Health Check Report", styles['Heading2']))
    story.append(Spacer(1, 20))

    # Report metadata
    account_info = data.get('report_metadata', {}).get('account_info', {})
    meta_data = [
        ['Report ID:', report_id],
        ['Account:', account_info.get('account_id', 'N/A')],
        ['Region:', account_info.get('region', 'N/A')],
        ['Generated:', data.get('report_metadata', {}).get('generated_at', 'N/A')[:19]],
    ]
    meta_table = Table(meta_data, colWidths=[100, 350])
    meta_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 20))

    # Cost Summary
    story.append(Paragraph("Cost Summary", styles['Heading2']))
    cost = data.get('cost_analysis', {})
    story.append(Paragraph(f"Total Monthly Cost: ${cost.get('total_cost', 0):.2f}", styles['Normal']))
    story.append(Spacer(1, 10))

    # Cost by service table
    cost_services = cost.get('cost_by_service', [])[:8]
    if cost_services:
        svc_data = [['Service', 'Cost', 'Percentage']]
        for svc in cost_services:
            svc_data.append([svc['service'], f"${svc['cost']:.2f}", f"{svc['percentage']}%"])
        svc_table = Table(svc_data, colWidths=[250, 80, 80])
        svc_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#232F3E')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(svc_table)
    story.append(Spacer(1, 20))

    # Security Summary
    story.append(Paragraph("Security Findings", styles['Heading2']))
    security = data.get('security_audit', {}).get('summary', {})
    story.append(Paragraph(
        f"Critical: {security.get('critical', 0)} | High: {security.get('high', 0)} | "
        f"Medium: {security.get('medium', 0)} | Low: {security.get('low', 0)} | "
        f"Total: {security.get('total', 0)}", styles['Normal']))
    story.append(Spacer(1, 10))

    # Security findings table
    sec_findings = data.get('security_audit', {}).get('findings', [])[:15]
    if sec_findings:
        sec_data = [['Severity', 'Category', 'Description']]
        for f in sec_findings:
            sec_data.append([f.get('severity', 'N/A'), f.get('category', 'N/A'),
                           f.get('description', 'N/A')[:60]])
        sec_table = Table(sec_data, colWidths=[70, 100, 250])
        sec_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#232F3E')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(sec_table)
    story.append(Spacer(1, 20))

    # Optimization
    story.append(Paragraph("Optimization Recommendations", styles['Heading2']))
    opt = data.get('optimization', {}).get('summary', {})
    story.append(Paragraph(
        f"Potential Monthly Savings: ${opt.get('potential_monthly_savings', 0):.2f} | "
        f"Annual: ${opt.get('potential_annual_savings', 0):.2f}", styles['Normal']))

    doc.build(story)
    return buffer.getvalue()


def _create_simple_pdf(data: dict, report_id: str) -> bytes:
    """Fallback PDF generation without ReportLab (plain text PDF)"""
    # Minimal PDF structure
    account_info = data.get('report_metadata', {}).get('account_info', {})
    cost = data.get('cost_analysis', {})
    security = data.get('security_audit', {}).get('summary', {})
    opt = data.get('optimization', {}).get('summary', {})

    lines = [
        "AWS AUDIT MANAGER - HEALTH CHECK REPORT",
        "=" * 50,
        f"Report ID: {report_id}",
        f"Account: {account_info.get('account_id', 'N/A')}",
        f"Region: {account_info.get('region', 'N/A')}",
        f"Generated: {data.get('report_metadata', {}).get('generated_at', 'N/A')[:19]}",
        "",
        "COST SUMMARY",
        "-" * 30,
        f"Total Monthly Cost: ${cost.get('total_cost', 0):.2f}",
        "",
        "SECURITY FINDINGS",
        "-" * 30,
        f"Critical: {security.get('critical', 0)}",
        f"High: {security.get('high', 0)}",
        f"Medium: {security.get('medium', 0)}",
        f"Low: {security.get('low', 0)}",
        f"Total: {security.get('total', 0)}",
        "",
        "OPTIMIZATION",
        "-" * 30,
        f"Potential Monthly Savings: ${opt.get('potential_monthly_savings', 0):.2f}",
        f"Potential Annual Savings: ${opt.get('potential_annual_savings', 0):.2f}",
    ]

    content = '\n'.join(lines)
    # Return as UTF-8 text content (not a real PDF, but functional fallback)
    return content.encode('utf-8')


def create_compliance_pdf(report_data: dict, cis_checks: list,
                          soc2_checks: list, hipaa_checks: list) -> bytes:
    """Generate compliance PDF report"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                topMargin=0.75*inch, bottomMargin=0.75*inch)
        styles = getSampleStyleSheet()
        story = []

        # Title
        title_style = ParagraphStyle('CustomTitle', parent=styles['Title'],
                                      fontSize=22, textColor=colors.HexColor('#232F3E'))
        story.append(Paragraph("AWS Audit Manager", title_style))
        story.append(Paragraph("Compliance Assessment Report", styles['Heading2']))
        story.append(Spacer(1, 10))

        account_info = report_data.get('report_metadata', {}).get('account_info', {})
        story.append(Paragraph(
            f"Account: {account_info.get('account_id', 'N/A')} | "
            f"Region: {account_info.get('region', 'N/A')} | "
            f"Date: {report_data.get('report_metadata', {}).get('generated_at', '')[:10]}",
            styles['Normal']))
        story.append(Spacer(1, 20))

        # Summary scores
        cis_pass = sum(1 for c in cis_checks if c['status'] == 'PASS')
        soc2_pass = sum(1 for c in soc2_checks if c['status'] == 'PASS')
        hipaa_pass = sum(1 for c in hipaa_checks if c['status'] == 'PASS')

        summary_data = [
            ['Framework', 'Passed', 'Total', 'Score'],
            ['CIS AWS Benchmark', str(cis_pass), str(len(cis_checks)),
             f"{int(cis_pass/len(cis_checks)*100) if cis_checks else 0}%"],
            ['SOC 2', str(soc2_pass), str(len(soc2_checks)),
             f"{int(soc2_pass/len(soc2_checks)*100) if soc2_checks else 0}%"],
            ['HIPAA', str(hipaa_pass), str(len(hipaa_checks)),
             f"{int(hipaa_pass/len(hipaa_checks)*100) if hipaa_checks else 0}%"],
        ]
        sum_table = Table(summary_data, colWidths=[200, 60, 60, 60])
        sum_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#232F3E')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(sum_table)
        story.append(Spacer(1, 20))

        # CIS Details
        story.append(Paragraph("CIS AWS Foundations Benchmark v1.5", styles['Heading2']))
        for check in cis_checks:
            status_icon = "PASS" if check['status'] == 'PASS' else "FAIL"
            story.append(Paragraph(
                f"[{status_icon}] {check['id']} - {check['title']}",
                styles['Normal']))
        story.append(Spacer(1, 15))

        # SOC 2 Details
        story.append(Paragraph("SOC 2 Trust Service Criteria", styles['Heading2']))
        for check in soc2_checks:
            status_icon = "PASS" if check['status'] == 'PASS' else "FAIL"
            story.append(Paragraph(
                f"[{status_icon}] {check['id']} - {check['title']}",
                styles['Normal']))
        story.append(Spacer(1, 15))

        # HIPAA Details
        story.append(Paragraph("HIPAA Technical Safeguards", styles['Heading2']))
        for check in hipaa_checks:
            status_icon = "PASS" if check['status'] == 'PASS' else "FAIL"
            story.append(Paragraph(
                f"[{status_icon}] {check['id']} - {check['title']}",
                styles['Normal']))

        doc.build(story)
        return buffer.getvalue()

    except ImportError:
        # Fallback
        lines = ["AWS AUDIT MANAGER - COMPLIANCE REPORT", "=" * 50, ""]
        for fw, checks in [("CIS", cis_checks), ("SOC2", soc2_checks), ("HIPAA", hipaa_checks)]:
            passed = sum(1 for c in checks if c['status'] == 'PASS')
            lines.append(f"{fw}: {passed}/{len(checks)} passed")
            for c in checks:
                lines.append(f"  [{c['status']}] {c['id']} - {c['title']}")
            lines.append("")
        return '\n'.join(lines).encode('utf-8')


# ============ HELPER FUNCTIONS ============

def get_aws_profiles() -> List[Dict[str, Any]]:
    """Get list of configured AWS profiles"""
    import configparser
    profiles = []
    home_dir = os.path.expanduser("~")
    credentials_file = os.path.join(home_dir, ".aws", "credentials")
    config_file = os.path.join(home_dir, ".aws", "config")
    profile_names = set()

    if os.path.exists(credentials_file):
        try:
            creds_parser = configparser.ConfigParser()
            creds_parser.read(credentials_file)
            for section in creds_parser.sections():
                profile_names.add(section)
        except Exception:
            pass

    if os.path.exists(config_file):
        try:
            config_parser = configparser.ConfigParser()
            config_parser.read(config_file)
            for section in config_parser.sections():
                if section.startswith("profile "):
                    profile_names.add(section.replace("profile ", ""))
                elif section == "default":
                    profile_names.add("default")
        except Exception:
            pass

    for name in sorted(profile_names):
        if name == "default":
            continue
        profile_info = {
            "name": name,
            "display_name": name.replace("-", " ").replace("_", " ").title(),
            "account_id": None,
            "region": None
        }
        try:
            import boto3
            session = boto3.Session(profile_name=name)
            sts = session.client('sts')
            identity = sts.get_caller_identity()
            profile_info["account_id"] = identity.get('Account')
            profile_info["region"] = session.region_name
        except Exception:
            pass
        profiles.append(profile_info)

    return profiles


def get_available_reports() -> List[Dict[str, Any]]:
    """Get list of available reports from output directory"""
    reports = []
    json_files = glob.glob(os.path.join(OUTPUT_DIR, "aws_health_check_*.json"))

    for json_file in sorted(json_files, reverse=True):
        try:
            filename = os.path.basename(json_file)
            report_id = filename.replace(".json", "")
            date_part = report_id.replace("aws_health_check_", "")
            try:
                report_date = datetime.strptime(date_part, "%Y%m%d_%H%M%S")
            except Exception:
                report_date = datetime.fromtimestamp(os.path.getmtime(json_file))

            with open(json_file, 'r') as f:
                data = json.load(f)

            account_info = data.get('report_metadata', {}).get('account_info', {})
            cost_data = data.get('cost_analysis', {})
            security_data = data.get('security_audit', {}).get('summary', {})
            optimization_data = data.get('optimization', {}).get('summary', {})

            reports.append({
                'id': report_id,
                'date': report_date.isoformat(),
                'date_formatted': report_date.strftime("%Y-%m-%d %H:%M:%S"),
                'account_id': account_info.get('account_id', 'Unknown'),
                'region': account_info.get('region', 'Unknown'),
                'total_cost': cost_data.get('total_cost', 0),
                'data_source': cost_data.get('data_source', 'unknown'),
                'security_findings': security_data.get('total', 0),
                'critical_findings': security_data.get('critical', 0),
                'optimization_savings': optimization_data.get('potential_monthly_savings', 0),
                'has_html': os.path.exists(json_file.replace('.json', '.html')),
                'has_md': os.path.exists(json_file.replace('.json', '.md'))
            })
        except Exception:
            continue

    return reports


def run_health_check(profile: Optional[str] = None, region: Optional[str] = None):
    """Run health check in background"""
    try:
        from main import AWSHealthCheck
        health_check = AWSHealthCheck(profile=profile, region=region)
        health_check.run_full_check(output_dir=OUTPUT_DIR)
    except Exception as e:
        print(f"Health check error: {e}")


# Run with: uvicorn dashboard.app:app --reload --host 0.0.0.0 --port 8000
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

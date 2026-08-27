"""
AWS Audit Manager - Business-Friendly PDF Report Generator
===========================================================
Generates executive-ready PDF reports that business users can understand.
Uses deterministic scan data only — no fabricated information.
"""

import io
from typing import Dict, Any, List


def generate_business_pdf(data: Dict[str, Any], report_id: str) -> bytes:
    """Generate a business-friendly PDF report"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.6*inch,
                            bottomMargin=0.6*inch, leftMargin=0.6*inch, rightMargin=0.6*inch)
    styles = getSampleStyleSheet()
    story = []

    # Custom styles
    AWS_ORANGE = colors.HexColor('#FF9900')
    AWS_DARK = colors.HexColor('#232F3E')

    title_style = ParagraphStyle('T', parent=styles['Title'], fontSize=24, textColor=AWS_DARK, spaceAfter=4)
    subtitle_style = ParagraphStyle('ST', parent=styles['Normal'], fontSize=13, textColor=colors.HexColor('#666666'), spaceAfter=2)
    h2_style = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=15, textColor=AWS_DARK, spaceBefore=16, spaceAfter=8)
    body_style = ParagraphStyle('B', parent=styles['Normal'], fontSize=10, leading=15, spaceAfter=6)
    small_style = ParagraphStyle('SM', parent=styles['Normal'], fontSize=8, textColor=colors.HexColor('#666666'))
    cell_style = ParagraphStyle('C', parent=styles['Normal'], fontSize=8, leading=11)
    cell_bold = ParagraphStyle('CB', parent=styles['Normal'], fontSize=8, leading=11, fontName='Helvetica-Bold')

    # ============ COVER / HEADER ============
    story.append(Paragraph("AWS Audit Manager", title_style))
    story.append(Paragraph("Security, Cost &amp; Compliance Assessment", subtitle_style))
    story.append(Spacer(1, 12))

    account_info = data.get('report_metadata', {}).get('account_info', {})
    generated = data.get('report_metadata', {}).get('generated_at', 'N/A')[:19].replace('T', ' ')
    meta = [
        ['AWS Account:', account_info.get('account_id', 'N/A'), 'Region:', account_info.get('region', 'N/A')],
        ['Report Date:', generated, 'Report ID:', report_id.replace('aws_health_check_', '')],
    ]
    mt = Table(meta, colWidths=[80, 180, 70, 130])
    mt.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TEXTCOLOR', (0, 0), (-1, -1), AWS_DARK),
    ]))
    story.append(mt)
    story.append(Spacer(1, 16))

    _add_what_this_means(story, data, h2_style, body_style, AWS_DARK, AWS_ORANGE)
    _add_executive_summary(story, data, h2_style, body_style, AWS_DARK, AWS_ORANGE)
    _add_risk_in_money(story, data, h2_style, body_style, AWS_DARK)
    _add_health_scores(story, data, h2_style, AWS_DARK)
    _add_compliance_readiness(story, data, h2_style, body_style, cell_style, AWS_DARK)
    _add_priority_actions(story, data, h2_style, body_style, cell_style, cell_bold, AWS_DARK)
    _add_action_plan(story, data, h2_style, body_style, cell_style, cell_bold, AWS_DARK)
    _add_cost_section(story, data, h2_style, body_style, cell_style, AWS_DARK)
    _add_optimization_section(story, data, h2_style, body_style, cell_style, AWS_DARK)
    _add_quick_wins_matrix(story, data, h2_style, body_style, cell_style, AWS_DARK)
    _add_security_section(story, data, h2_style, body_style, cell_style, cell_bold, AWS_DARK)
    _add_glossary(story, data, h2_style, body_style, cell_style, AWS_DARK)

    # Footer note
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "This report is a point-in-time assessment based on data collected during the scan. "
        "Cost figures reflect AWS billing data or estimates where noted. Savings are estimated potential savings, not guaranteed. "
        "This is a read-only assessment; no changes were made to your AWS environment.",
        small_style))

    doc.build(story)
    return buffer.getvalue()


def _add_executive_summary(story, data, h2, body, dark, orange):
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors

    story.append(Paragraph("Executive Summary", h2))

    exec_sum = data.get('executive_summary', {})
    scores = data.get('scores', {})
    security = data.get('security_audit', {}).get('summary', {})
    cost = data.get('cost_analysis', {})
    opt = data.get('optimization', {}).get('summary', {})

    text = exec_sum.get('text_summary', '')
    if text:
        story.append(Paragraph(text, body))
        story.append(Spacer(1, 10))

    # Key metrics box
    overall = scores.get('overall_score', 'N/A')
    status = scores.get('overall_status', '')
    monthly_cost = cost.get('total_cost', 0)
    savings = opt.get('potential_monthly_savings', 0)

    metrics = [
        ['Health Score', 'Monthly Cost', 'Potential Savings', 'Critical Issues'],
        [f"{overall}/100\n{status}", f"${monthly_cost:,.2f}", f"${savings:,.2f}/mo", str(security.get('critical', 0))],
    ]
    mt = Table(metrics, colWidths=[125, 125, 125, 110])
    mt.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), dark),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTSIZE', (0, 1), (-1, 1), 13),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.white),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#f0f2f5')),
        ('TEXTCOLOR', (3, 1), (3, 1), colors.HexColor('#dc3545')),
        ('TEXTCOLOR', (2, 1), (2, 1), colors.HexColor('#28a745')),
    ]))
    story.append(mt)
    story.append(Spacer(1, 6))


def _add_health_scores(story, data, h2, dark):
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors

    scores = data.get('scores', {})
    categories = scores.get('categories', {})
    if not categories:
        return

    story.append(Paragraph("Health Score Breakdown", h2))

    rows = [['Category', 'Score', 'What It Measures']]
    labels = {
        'security': 'Security',
        'cost_optimization': 'Cost Efficiency',
        'compliance': 'Compliance',
        'operations': 'Operations'
    }
    for key, cat in categories.items():
        rows.append([
            labels.get(key, key.title()),
            f"{cat.get('score', 0)}/100",
            cat.get('description', '')
        ])

    t = Table(rows, colWidths=[110, 60, 315])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), dark),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
    ]))
    story.append(t)


def _add_priority_actions(story, data, h2, body, cell, cell_bold, dark):
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors

    priorities = data.get('top_priority_actions', [])
    if not priorities:
        return

    story.append(Paragraph("Top Priority Actions", h2))
    story.append(Paragraph("These are the most important issues to address first, ranked by risk and business impact:", body))
    story.append(Spacer(1, 6))

    rows = [[Paragraph('<b>#</b>', cell), Paragraph('<b>Priority</b>', cell),
             Paragraph('<b>Issue</b>', cell), Paragraph('<b>Business Impact &amp; Recommendation</b>', cell)]]

    for i, action in enumerate(priorities[:5], 1):
        sev = action.get('severity', 'MEDIUM')
        sev_color = {'CRITICAL': '#dc3545', 'HIGH': '#fd7e14', 'MEDIUM': '#0d6efd', 'LOW': '#6c757d'}.get(sev, '#6c757d')

        impact = action.get('business_impact', '')
        rec = action.get('recommendation', '')
        combined = f"<b>Impact:</b> {impact}"
        if rec:
            combined += f"<br/><b>Fix:</b> {rec}"

        rows.append([
            Paragraph(str(i), cell),
            Paragraph(f'<font color="{sev_color}"><b>{sev}</b></font>', cell),
            Paragraph(action.get('title', ''), cell_bold),
            Paragraph(combined, cell)
        ])

    t = Table(rows, colWidths=[18, 55, 130, 282])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), dark),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t)


def _add_cost_section(story, data, h2, body, cell, dark):
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors

    story.append(Paragraph("Cost Overview", h2))

    cost = data.get('cost_analysis', {})
    total = cost.get('total_cost', 0)
    data_source = cost.get('data_source', 'unknown')
    source_note = "actual AWS billing data" if data_source == 'billing_api' else "estimated from your resources"

    services = cost.get('cost_by_service', [])
    top_service = services[0] if services else None

    intro = f"Your total AWS spend is <b>${total:,.2f}/month</b> (based on {source_note})."
    if top_service:
        intro += f" Your largest expense is <b>{top_service['service']}</b> at ${top_service['cost']:,.2f}/month ({top_service.get('percentage', 0)}% of total spend)."
    story.append(Paragraph(intro, body))
    story.append(Spacer(1, 8))

    if services:
        rows = [['Service', 'Monthly Cost', '% of Total']]
        for svc in services[:8]:
            rows.append([svc['service'], f"${svc['cost']:,.2f}", f"{svc.get('percentage', 0)}%"])

        t = Table(rows, colWidths=[300, 100, 85])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), dark),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ]))
        story.append(t)


def _get_business_explanation(finding):
    """Generate business-friendly explanation for a finding"""
    desc = (finding.get('description', '') + ' ' + finding.get('title', '')).lower()

    if '0.0.0.0' in desc and ('22' in desc or 'ssh' in desc):
        return "This server can be accessed from anywhere on the internet via SSH. Attackers constantly scan for this and attempt to break in."
    elif '0.0.0.0' in desc and ('3389' in desc or 'rdp' in desc):
        return "Windows remote desktop is open to the entire internet, making it a prime target for attacks."
    elif 'postgre' in desc or 'mysql' in desc or 'database' in desc and 'public' in desc:
        return "Your database is reachable from the public internet. This risks data theft and unauthorized access to sensitive information."
    elif 'all traffic' in desc or 'all inbound' in desc:
        return "This firewall rule allows unrestricted access from anywhere, exposing your systems to a wide range of attacks."
    elif 'publicly accessible' in desc and 'rds' in desc:
        return "This database is exposed to the public internet. Sensitive data could be stolen if credentials are compromised."
    elif 'mfa' in desc:
        return "This user account lacks two-factor authentication, making it vulnerable if the password is leaked or guessed."
    elif 'root' in desc and 'key' in desc:
        return "The master account has access keys, which is extremely risky. If leaked, an attacker gains full control of everything."
    elif 'encrypt' in desc and 'ebs' in desc:
        return "This storage disk is not encrypted. If the underlying hardware is compromised, data could be read directly."
    elif 'encrypt' in desc:
        return "This data is stored without encryption, increasing the risk of exposure if accessed by unauthorized parties."
    elif 'default vpc' in desc:
        return "Resources are running in the default network which has looser security settings than a custom-configured network."
    elif 'password policy' in desc:
        return "There are no rules requiring strong passwords, making accounts easier to compromise through guessing."
    elif 'access key' in desc and ('old' in desc or 'rotat' in desc or 'day' in desc):
        return "This access credential is old and hasn't been rotated. Older keys are more likely to have been leaked over time."
    else:
        return "This is a security best-practice issue that should be reviewed and addressed."


def _add_security_section(story, data, h2, body, cell, cell_bold, dark):
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors

    story.append(Paragraph("Security Findings", h2))

    security = data.get('security_audit', {})
    summary = security.get('summary', {})
    findings = security.get('findings', [])

    intro = (f"We found <b>{summary.get('total', 0)} security issues</b>: "
             f"<font color='#dc3545'><b>{summary.get('critical', 0)} Critical</b></font>, "
             f"<font color='#fd7e14'><b>{summary.get('high', 0)} High</b></font>, "
             f"{summary.get('medium', 0)} Medium, and {summary.get('low', 0)} Low. "
             f"Critical and High issues should be addressed as soon as possible.")
    story.append(Paragraph(intro, body))
    story.append(Spacer(1, 8))

    # Sort findings: critical first
    sev_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
    sorted_findings = sorted(findings, key=lambda f: sev_order.get(f.get('severity', 'LOW'), 4))

    rows = [[Paragraph('<b>Risk</b>', cell), Paragraph('<b>What We Found</b>', cell),
             Paragraph('<b>Why It Matters (Business Impact)</b>', cell)]]

    for f in sorted_findings[:25]:
        sev = f.get('severity', 'MEDIUM')
        sev_color = {'CRITICAL': '#dc3545', 'HIGH': '#fd7e14', 'MEDIUM': '#0d6efd', 'LOW': '#6c757d'}.get(sev, '#6c757d')

        title = f.get('title', '')
        resource = f.get('resource', '')
        what = f"<b>{title}</b>"
        if resource and resource != 'N/A':
            what += f"<br/><font size=7 color='#666666'>{resource}</font>"

        impact = _get_business_explanation(f)

        rows.append([
            Paragraph(f'<font color="{sev_color}"><b>{sev}</b></font>', cell),
            Paragraph(what, cell),
            Paragraph(impact, cell)
        ])

    t = Table(rows, colWidths=[55, 175, 255])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), dark),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
    ]))
    story.append(t)

    if len(sorted_findings) > 25:
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"<font size=8 color='#666666'>Showing top 25 of {len(sorted_findings)} findings. See the online dashboard for the complete list.</font>", body))


def _add_optimization_section(story, data, h2, body, cell, dark):
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors

    story.append(Paragraph("Cost Savings Opportunities", h2))

    opt = data.get('optimization', {})
    summary = opt.get('summary', {})
    recs = [r for r in opt.get('recommendations', []) if r.get('estimated_monthly_savings', 0) > 0]

    monthly = summary.get('potential_monthly_savings', 0)
    annual = summary.get('potential_annual_savings', 0)

    intro = (f"We identified <b>${monthly:,.2f}/month</b> in estimated potential savings "
             f"(approximately <b>${annual:,.2f}/year</b>). These are estimates based on your current usage — "
             f"actual savings depend on implementation.")
    story.append(Paragraph(intro, body))
    story.append(Spacer(1, 8))

    if not recs:
        story.append(Paragraph("No cost savings opportunities were identified in this scan.", body))
        return

    # Sort by savings descending
    recs.sort(key=lambda r: r.get('estimated_monthly_savings', 0), reverse=True)

    rows = [[Paragraph('<b>Opportunity</b>', cell), Paragraph('<b>What To Do</b>', cell), Paragraph('<b>Est. Savings</b>', cell)]]

    for r in recs[:15]:
        title = r.get('title', '')
        action = r.get('action', '')
        savings = r.get('estimated_monthly_savings', 0)

        rows.append([
            Paragraph(f"<b>{title}</b>", cell),
            Paragraph(action[:150] if action else 'Review resource', cell),
            Paragraph(f"<font color='#28a745'><b>${savings:,.2f}/mo</b></font>", cell)
        ])

    t = Table(rows, colWidths=[160, 245, 80])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), dark),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
    ]))
    story.append(t)


def _add_what_this_means(story, data, h2, body, dark, orange):
    """Plain-language callout box at the top"""
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle

    security = data.get('security_audit', {})
    summary = security.get('summary', {})
    findings = security.get('findings', [])
    opt = data.get('optimization', {}).get('summary', {})

    critical = summary.get('critical', 0)
    savings = opt.get('potential_monthly_savings', 0)

    # Build plain-language summary
    parts = []

    # Check for internet-exposed resources
    exposed_db = any('publicly accessible' in f.get('description', '').lower() and 'rds' in f.get('description', '').lower() for f in findings)
    exposed_ssh = any('0.0.0.0' in f.get('description', '') and ('22' in f.get('description', '') or 'ssh' in f.get('description', '').lower()) for f in findings)
    no_mfa = any('mfa' in f.get('description', '').lower() for f in findings)
    unencrypted = any('encrypt' in f.get('description', '').lower() for f in findings)

    if exposed_db:
        parts.append("Your databases are exposed to the internet and need immediate attention.")
    if exposed_ssh:
        parts.append("Some servers can be accessed from anywhere online, which is risky.")
    if no_mfa:
        parts.append("Some user accounts lack two-factor authentication.")
    if unencrypted:
        parts.append("Some of your data is stored without encryption.")

    if not parts and critical == 0:
        parts.append("No critical security issues were found — good work!")

    security_text = " ".join(parts) if parts else f"You have {critical} critical security issues to review."

    cost_text = ""
    if savings > 0:
        cost_text = f" On the cost side, you could save approximately ${savings:,.2f}/month by removing waste and right-sizing resources."

    full_text = f"<b>In simple terms:</b> {security_text}{cost_text}"

    box_style = ParagraphStyle('box', parent=body, fontSize=11, leading=16, textColor=dark)

    t = Table([[Paragraph(full_text, box_style)]], colWidths=[490])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FFF3CD')),
        ('BOX', (0, 0), (-1, -1), 2, orange),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
    ]))
    story.append(t)
    story.append(Spacer(1, 12))


def _add_risk_in_money(story, data, h2, body, dark):
    """Frame security risk in financial terms"""
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors

    summary = data.get('security_audit', {}).get('summary', {})
    critical = summary.get('critical', 0)
    high = summary.get('high', 0)

    if critical == 0 and high == 0:
        return

    story.append(Paragraph("Security Risk in Business Terms", h2))

    text = (
        f"You have <b>{critical} critical</b> and <b>{high} high-severity</b> security issues. "
        f"These represent real business risk — internet-exposed systems and databases are the leading cause of data breaches. "
        f"Industry research places the average cost of a cloud data breach in the millions of dollars, including recovery costs, "
        f"regulatory fines, legal fees, and reputational damage. "
        f"Addressing these {critical + high} priority issues significantly reduces your exposure to these outcomes."
    )
    story.append(Paragraph(text, body))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "<font size=8 color='#666666'>Note: Breach cost figures are industry averages for context only and are not specific predictions for your organization.</font>",
        body))


def _add_compliance_readiness(story, data, h2, body, cell, dark):
    """Compliance readiness summary (CIS, SOC2, HIPAA)"""
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors

    findings = data.get('security_audit', {}).get('findings', [])

    # Calculate compliance scores using same logic as web (from dashboard app)
    try:
        from dashboard.app import map_to_cis, map_to_soc2, map_to_hipaa
        cis = map_to_cis(findings, data)
        soc2 = map_to_soc2(findings, data)
        hipaa = map_to_hipaa(findings, data)
    except Exception:
        cis = soc2 = hipaa = []

    if not cis and not soc2 and not hipaa:
        return

    story.append(Paragraph("Compliance Readiness Assessment", h2))
    story.append(Paragraph(
        "This shows how well your environment aligns with common compliance frameworks, based on the controls we could evaluate. "
        "This is a readiness indicator, not a formal certification.", body))
    story.append(Spacer(1, 8))

    def score(checks):
        if not checks:
            return 0, 0, 0
        passed = sum(1 for c in checks if c.get('status') == 'PASS')
        return int(passed / len(checks) * 100), passed, len(checks)

    cis_pct, cis_p, cis_t = score(cis)
    soc2_pct, soc2_p, soc2_t = score(soc2)
    hipaa_pct, hipaa_p, hipaa_t = score(hipaa)

    def color_for(pct):
        if pct >= 70:
            return '#28a745'
        elif pct >= 50:
            return '#fd7e14'
        return '#dc3545'

    rows = [
        [Paragraph('<b>Framework</b>', cell), Paragraph('<b>Readiness</b>', cell), Paragraph('<b>Controls Passed</b>', cell)],
        [Paragraph('CIS AWS Benchmark', cell), Paragraph(f"<font color='{color_for(cis_pct)}'><b>{cis_pct}%</b></font>", cell), Paragraph(f"{cis_p} of {cis_t}", cell)],
        [Paragraph('SOC 2 Readiness', cell), Paragraph(f"<font color='{color_for(soc2_pct)}'><b>{soc2_pct}%</b></font>", cell), Paragraph(f"{soc2_p} of {soc2_t}", cell)],
        [Paragraph('HIPAA Alignment', cell), Paragraph(f"<font color='{color_for(hipaa_pct)}'><b>{hipaa_pct}%</b></font>", cell), Paragraph(f"{hipaa_p} of {hipaa_t}", cell)],
    ]

    t = Table(rows, colWidths=[200, 140, 145])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), dark),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
    ]))
    story.append(t)


def _add_action_plan(story, data, h2, body, cell, cell_bold, dark):
    """30-60-90 day action plan"""
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors

    summary = data.get('security_audit', {}).get('summary', {})
    opt = data.get('optimization', {}).get('summary', {})
    critical = summary.get('critical', 0)
    high = summary.get('high', 0)
    medium = summary.get('medium', 0)
    savings = opt.get('potential_monthly_savings', 0)

    story.append(Paragraph("Recommended Action Plan", h2))

    day30 = f"Fix all {critical} critical security issues (internet-exposed systems, databases, and access controls)." if critical else "Review and confirm no urgent security gaps remain."
    day60 = f"Address {high} high-priority issues and implement cost savings (~${savings:,.2f}/month opportunity)." if (high or savings) else "Optimize resource usage and review spending."
    day90 = f"Resolve remaining {medium} medium issues and improve compliance posture toward audit readiness." if medium else "Establish ongoing monitoring and periodic audits."

    rows = [
        [Paragraph('<b>Timeframe</b>', cell), Paragraph('<b>Focus</b>', cell)],
        [Paragraph('<b>First 30 Days</b>', cell_bold), Paragraph(day30, cell)],
        [Paragraph('<b>31-60 Days</b>', cell_bold), Paragraph(day60, cell)],
        [Paragraph('<b>61-90 Days</b>', cell_bold), Paragraph(day90, cell)],
    ]

    t = Table(rows, colWidths=[95, 390])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), dark),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
    ]))
    story.append(t)


def _add_quick_wins_matrix(story, data, h2, body, cell, dark):
    """Effort vs Impact matrix for cost recommendations"""
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors

    recs = [r for r in data.get('optimization', {}).get('recommendations', []) if r.get('estimated_monthly_savings', 0) > 0]
    if not recs:
        return

    story.append(Paragraph("Prioritizing Cost Savings: Quick Wins vs Bigger Projects", h2))
    story.append(Paragraph(
        "This helps you decide where to start. Quick Wins deliver savings with minimal effort. "
        "Bigger Projects need more planning but may save more.", body))
    story.append(Spacer(1, 8))

    quick_wins = [r for r in recs if r.get('effort', 'Low') == 'Low']
    bigger = [r for r in recs if r.get('effort', 'Low') != 'Low']

    qw_savings = sum(r.get('estimated_monthly_savings', 0) for r in quick_wins)
    bp_savings = sum(r.get('estimated_monthly_savings', 0) for r in bigger)

    def top_items(lst, n=3):
        lst = sorted(lst, key=lambda r: r.get('estimated_monthly_savings', 0), reverse=True)[:n]
        if not lst:
            return "None identified"
        return "<br/>".join(f"• {r.get('title', '')[:45]} (${r.get('estimated_monthly_savings', 0):,.2f}/mo)" for r in lst)

    rows = [
        [Paragraph('<b>Quick Wins (Low Effort)</b>', cell), Paragraph('<b>Bigger Projects (More Effort)</b>', cell)],
        [Paragraph(f"<b>Total: ${qw_savings:,.2f}/month</b><br/><br/>{top_items(quick_wins)}", cell),
         Paragraph(f"<b>Total: ${bp_savings:,.2f}/month</b><br/><br/>{top_items(bigger)}", cell)],
    ]

    t = Table(rows, colWidths=[242, 243])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#28a745')),
        ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#fd7e14')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t)


def _add_glossary(story, data, h2, body, cell, dark):
    """Glossary of technical terms"""
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors

    story.append(Spacer(1, 12))
    story.append(Paragraph("Glossary: Technical Terms Explained", h2))

    terms = [
        ("EC2 Instance", "A virtual server running in AWS — like a computer you rent by the hour."),
        ("EBS Volume", "A virtual hard drive attached to a server, where data is stored."),
        ("RDS", "A managed database service (e.g., for PostgreSQL or MySQL databases)."),
        ("S3 Bucket", "Cloud storage for files, backups, images, and documents."),
        ("Security Group", "A virtual firewall that controls what network traffic can reach your servers."),
        ("IAM", "Identity &amp; Access Management — controls who can access your AWS account and what they can do."),
        ("MFA", "Multi-Factor Authentication — a second login step (like a phone code) for extra security."),
        ("VPC", "Virtual Private Cloud — your own isolated private network within AWS."),
        ("Encryption", "Scrambling data so it can't be read without the right key, protecting it if stolen."),
        ("0.0.0.0/0", "Means 'open to the entire internet' — anyone, anywhere can attempt to connect."),
    ]

    rows = [[Paragraph('<b>Term</b>', cell), Paragraph('<b>What It Means</b>', cell)]]
    for term, defn in terms:
        rows.append([Paragraph(f"<b>{term}</b>", cell), Paragraph(defn, cell)])

    t = Table(rows, colWidths=[110, 375])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), dark),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
    ]))
    story.append(t)

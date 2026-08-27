"""
AWS Audit Manager - Scoring Engine
===================================
Deterministic scoring system for AWS health assessment.
The LLM/AI never calculates these scores.

Scoring Methodology:
- Each category starts at 100 points
- Points are deducted based on findings
- Final score is weighted average of all categories

Categories & Weights:
- Security (30%): Network, IAM, data protection findings
- Cost Optimization (20%): Waste, unused resources, savings potential
- Compliance (25%): CIS, encryption, logging, access controls
- Operations (25%): Architecture, availability, best practices

Deduction Rules:
- CRITICAL finding: -20 points per finding (max -60)
- HIGH finding: -10 points per finding (max -40)
- MEDIUM finding: -5 points per finding (max -30)
- LOW finding: -2 points per finding (max -10)

Score Ranges:
- 90-100: Excellent
- 75-89: Good
- 60-74: Fair (Needs Attention)
- 40-59: Poor (Significant Risk)
- 0-39: Critical (Immediate Action Required)
"""

from typing import Dict, Any, List


def calculate_scores(report_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate all scores from scan report data.
    This is the ONLY source of truth for scores.
    
    Args:
        report_data: Full JSON report structure
        
    Returns:
        Dictionary with all scores and metadata
    """
    security = report_data.get('security_audit', {})
    cost = report_data.get('cost_analysis', {})
    optimization = report_data.get('optimization', {})
    inventory = report_data.get('resource_inventory', {})
    
    findings = security.get('findings', [])
    summary = security.get('summary', {})
    recommendations = optimization.get('recommendations', [])
    
    # Calculate individual category scores
    security_score = _calculate_security_score(findings, summary)
    cost_score = _calculate_cost_score(cost, optimization)
    compliance_score = _calculate_compliance_score(findings)
    operations_score = _calculate_operations_score(findings, inventory)
    
    # Weighted overall score
    overall_score = int(
        security_score * 0.30 +
        cost_score * 0.20 +
        compliance_score * 0.25 +
        operations_score * 0.25
    )
    overall_score = max(0, min(100, overall_score))
    
    return {
        "overall_score": overall_score,
        "overall_grade": _get_grade(overall_score),
        "overall_status": _get_status(overall_score),
        "categories": {
            "security": {
                "score": security_score,
                "grade": _get_grade(security_score),
                "weight": "30%",
                "description": "Network exposure, access controls, data protection"
            },
            "cost_optimization": {
                "score": cost_score,
                "grade": _get_grade(cost_score),
                "weight": "20%",
                "description": "Resource efficiency, waste elimination"
            },
            "compliance": {
                "score": compliance_score,
                "grade": _get_grade(compliance_score),
                "weight": "25%",
                "description": "Encryption, logging, access management"
            },
            "operations": {
                "score": operations_score,
                "grade": _get_grade(operations_score),
                "weight": "25%",
                "description": "Architecture, availability, best practices"
            }
        },
        "scoring_methodology": "Deterministic rule-based scoring. See scoring.py for full documentation."
    }


def _calculate_security_score(findings: List[Dict], summary: Dict) -> int:
    """
    Security score based on network and access findings.
    Categories: Network Security, Identity & Access
    """
    score = 100
    
    for finding in findings:
        severity = finding.get('severity', '').upper()
        category = finding.get('category', '').lower()
        
        # Only count security-relevant categories
        if category in ['network security', 'identity & access', 'data security']:
            if severity == 'CRITICAL':
                score -= 20
            elif severity == 'HIGH':
                score -= 10
            elif severity == 'MEDIUM':
                score -= 5
            elif severity == 'LOW':
                score -= 2
    
    return max(0, min(100, score))


def _calculate_cost_score(cost: Dict, optimization: Dict) -> int:
    """
    Cost score based on optimization opportunities.
    More unused resources / savings potential = lower score.
    """
    score = 100
    
    recommendations = optimization.get('recommendations', [])
    total_cost = cost.get('total_cost', 0)
    potential_savings = optimization.get('summary', {}).get('potential_monthly_savings', 0)
    
    # Deduct for each optimization recommendation
    for rec in recommendations:
        effort = rec.get('effort', 'Low')
        savings = rec.get('estimated_monthly_savings', 0)
        
        if savings <= 0:
            continue  # Skip negative/zero savings
            
        if savings > 50:
            score -= 15  # Big waste
        elif savings > 20:
            score -= 10
        elif savings > 5:
            score -= 5
        else:
            score -= 2
    
    # Extra penalty if savings > 10% of total spend
    if total_cost > 0 and potential_savings > 0:
        waste_ratio = potential_savings / total_cost
        if waste_ratio > 0.20:
            score -= 15  # >20% waste
        elif waste_ratio > 0.10:
            score -= 10  # >10% waste
        elif waste_ratio > 0.05:
            score -= 5   # >5% waste
    
    return max(0, min(100, score))


def _calculate_compliance_score(findings: List[Dict]) -> int:
    """
    Compliance score based on encryption, logging, and access findings.
    Maps to CIS/SOC2/HIPAA relevant controls.
    """
    score = 100
    
    compliance_keywords = {
        'encrypt': 15,      # Unencrypted resources are serious
        'mfa': 15,          # MFA is critical for compliance
        'public': 10,       # Public exposure
        'logging': 10,      # Audit logging
        'password': 8,      # Password policy
        'access key': 8,    # Key rotation
        'unused': 5,        # Unused credentials
        'default': 5,       # Default configs
    }
    
    for finding in findings:
        desc = finding.get('description', '').lower()
        title = finding.get('title', '').lower()
        combined = desc + ' ' + title
        
        for keyword, penalty in compliance_keywords.items():
            if keyword in combined:
                score -= penalty
                break  # Only one penalty per finding
    
    return max(0, min(100, score))


def _calculate_operations_score(findings: List[Dict], inventory: Dict) -> int:
    """
    Operations score based on architecture best practices.
    """
    score = 100
    
    inv_summary = inventory.get('summary', {})
    
    # Check for architecture concerns
    for finding in findings:
        category = finding.get('category', '').lower()
        if category == 'architecture':
            severity = finding.get('severity', '').upper()
            if severity == 'CRITICAL':
                score -= 15
            elif severity == 'HIGH':
                score -= 10
            elif severity == 'MEDIUM':
                score -= 5
    
    # Penalize for unattached resources (operational waste)
    unused_volumes = inv_summary.get('unattached_volumes', 0)
    unused_eips = inv_summary.get('unused_elastic_ips', 0)
    
    score -= unused_volumes * 3
    score -= unused_eips * 3
    
    return max(0, min(100, score))


def _get_grade(score: int) -> str:
    """Convert score to letter grade"""
    if score >= 90:
        return "A"
    elif score >= 75:
        return "B"
    elif score >= 60:
        return "C"
    elif score >= 40:
        return "D"
    else:
        return "F"


def _get_status(score: int) -> str:
    """Convert score to human-readable status"""
    if score >= 90:
        return "Excellent"
    elif score >= 75:
        return "Good"
    elif score >= 60:
        return "Needs Attention"
    elif score >= 40:
        return "Poor"
    else:
        return "Critical"


def generate_executive_summary(report_data: Dict[str, Any], scores: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate executive summary from scan data.
    All values come from deterministic scan results — never fabricated.
    
    Returns structured summary for display and AI context.
    """
    security = report_data.get('security_audit', {})
    cost = report_data.get('cost_analysis', {})
    optimization = report_data.get('optimization', {})
    inventory = report_data.get('resource_inventory', {})
    
    summary_data = security.get('summary', {})
    opt_summary = optimization.get('summary', {})
    inv_summary = inventory.get('summary', {})
    
    # Calculate total positive savings only
    recommendations = optimization.get('recommendations', [])
    positive_savings = sum(
        r.get('estimated_monthly_savings', 0) 
        for r in recommendations 
        if r.get('estimated_monthly_savings', 0) > 0
    )
    
    total_cost = cost.get('total_cost', 0)
    critical = summary_data.get('critical', 0)
    high = summary_data.get('high', 0)
    medium = summary_data.get('medium', 0)
    low = summary_data.get('low', 0)
    total_findings = summary_data.get('total', 0)
    
    # Count affected resources
    affected_resources = set()
    for finding in security.get('findings', []):
        resource = finding.get('resource', '')
        if resource and resource != 'N/A':
            affected_resources.add(resource)
    
    # Generate business-friendly text summary
    text_parts = []
    
    overall = scores.get('overall_score', 0)
    if overall >= 75:
        text_parts.append(f"Your AWS environment is in {scores.get('overall_status', 'good').lower()} condition (score: {overall}/100).")
    else:
        text_parts.append(f"Your AWS environment requires attention (health score: {overall}/100).")
    
    if critical > 0:
        text_parts.append(f"We identified {critical} critical security finding{'s' if critical != 1 else ''} that need immediate attention.")
    
    if total_findings > 0:
        # Identify main issue areas
        categories = {}
        for f in security.get('findings', []):
            cat = f.get('category', 'Other')
            categories[cat] = categories.get(cat, 0) + 1
        top_category = max(categories, key=categories.get) if categories else "security"
        text_parts.append(f"The primary concern area is {top_category} ({categories.get(top_category, 0)} findings).")
    
    if total_cost > 0:
        text_parts.append(f"Your estimated AWS spend is ${total_cost:,.2f}/month.")
    
    if positive_savings > 0:
        text_parts.append(f"We identified approximately ${positive_savings:,.2f}/month in optimization opportunities (${positive_savings*12:,.2f}/year).")
    
    return {
        "overall_score": overall,
        "overall_status": scores.get('overall_status', 'Unknown'),
        "scores": scores.get('categories', {}),
        "monthly_cost": total_cost,
        "potential_monthly_savings": round(positive_savings, 2),
        "potential_annual_savings": round(positive_savings * 12, 2),
        "critical_findings": critical,
        "high_findings": high,
        "medium_findings": medium,
        "low_findings": low,
        "total_findings": total_findings,
        "affected_resources": len(affected_resources),
        "total_resources": (
            inv_summary.get('total_ec2_instances', 0) +
            inv_summary.get('total_rds_instances', 0) +
            inv_summary.get('total_s3_buckets', 0) +
            inv_summary.get('total_lambda_functions', 0) +
            inv_summary.get('total_load_balancers', 0)
        ),
        "text_summary": ' '.join(text_parts),
        "data_source": cost.get('data_source', 'unknown')
    }


def get_top_priority_actions(report_data: Dict[str, Any], max_items: int = 5) -> List[Dict[str, Any]]:
    """
    Rank and return top priority actions from findings.
    Prioritizes by: severity → business impact → resource count.
    """
    findings = report_data.get('security_audit', {}).get('findings', [])
    
    # Score each finding for priority
    severity_weight = {'CRITICAL': 100, 'HIGH': 70, 'MEDIUM': 40, 'LOW': 10}
    
    # Business impact mapping based on finding characteristics
    impact_keywords = {
        'internet': 25, '0.0.0.0': 25, 'public': 20,
        'mfa': 20, 'root': 20, 'encrypt': 15,
        'all traffic': 15, 'unused': 5, 'password': 10,
    }
    
    scored_findings = []
    for finding in findings:
        priority_score = severity_weight.get(finding.get('severity', '').upper(), 0)
        
        # Add impact score based on keywords
        desc = (finding.get('description', '') + ' ' + finding.get('title', '')).lower()
        for keyword, weight in impact_keywords.items():
            if keyword in desc:
                priority_score += weight
        
        # Generate business impact text
        business_impact = _get_business_impact(finding)
        
        scored_findings.append({
            "priority_score": priority_score,
            "severity": finding.get('severity', 'MEDIUM'),
            "title": finding.get('title', ''),
            "category": finding.get('category', ''),
            "resource": finding.get('resource', 'N/A'),
            "region": finding.get('region', 'global'),
            "business_impact": business_impact,
            "recommendation": finding.get('recommendation', ''),
            "description": finding.get('description', ''),
        })
    
    # Sort by priority score descending, take top N
    scored_findings.sort(key=lambda x: x['priority_score'], reverse=True)
    
    # Deduplicate similar findings (same title)
    seen_titles = set()
    unique_findings = []
    for f in scored_findings:
        if f['title'] not in seen_titles:
            seen_titles.add(f['title'])
            unique_findings.append(f)
    
    return unique_findings[:max_items]


def _get_business_impact(finding: Dict) -> str:
    """Generate business impact text from finding characteristics"""
    desc = (finding.get('description', '') + ' ' + finding.get('title', '')).lower()
    severity = finding.get('severity', '').upper()
    
    if '0.0.0.0' in desc and ('22' in desc or 'ssh' in desc):
        return "Unauthorized server access risk. Attackers can attempt to log into your servers from anywhere on the internet."
    elif '0.0.0.0' in desc and ('3389' in desc or 'rdp' in desc):
        return "Remote desktop exposed to the internet. Attackers can attempt to access your Windows servers."
    elif 'all traffic' in desc or 'all inbound' in desc:
        return "Unrestricted network access increases exposure to attacks and data breaches."
    elif 'mfa' in desc:
        return "Accounts without multi-factor authentication are vulnerable to password-based attacks and account takeover."
    elif 'root' in desc:
        return "Root account compromise gives complete control over your entire AWS environment."
    elif 'public' in desc and 's3' in desc:
        return "Publicly accessible storage can lead to data leaks and regulatory violations."
    elif 'encrypt' in desc:
        return "Unencrypted data is vulnerable to unauthorized access if storage is compromised."
    elif 'unused' in desc and 'credential' in desc:
        return "Stale credentials increase the attack surface. Unused accounts may be compromised without detection."
    elif 'access key' in desc and ('rotation' in desc or 'old' in desc or 'age' in desc):
        return "Old access keys are more likely to have been leaked or compromised over time."
    elif 'password policy' in desc:
        return "Weak password policies make brute-force attacks more likely to succeed."
    elif 'default' in desc and 'security group' in desc:
        return "Default security groups with open rules expose resources unintentionally."
    elif 'public' in desc:
        return "Publicly accessible resources increase risk of unauthorized access and data exposure."
    elif severity == 'CRITICAL':
        return "Critical security risk that requires immediate attention to prevent potential breach."
    elif severity == 'HIGH':
        return "Significant security gap that should be addressed promptly."
    else:
        return "Security best practice violation that should be reviewed and remediated."

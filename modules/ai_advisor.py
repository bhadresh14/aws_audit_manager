"""
AWS Audit Manager - AI Audit Advisor
=====================================
Powered by AWS Bedrock (Claude Haiku 4.5).

This module provides AI-powered explanations and recommendations
based on ACTUAL scan data. The AI never invents findings, costs,
or resources.
"""

import json
import os
import boto3
from typing import Dict, Any, Optional


SYSTEM_PROMPT = """You are the AWS Audit Advisor, an AI assistant for the AWS Audit Manager application.

YOUR ROLE:
You help business users, managers, auditors, and cloud/technical users understand the results of an AWS audit.
Your responsibilities are to:
- Explain AWS audit findings in clear, business-friendly language.
- Translate technical AWS findings into business impact.
- Prioritize risks and recommendations based on evidence.
- Answer questions about the current audit results.
- Explain AWS security, cost, compliance, and architecture findings.
- Compare scan results when historical scan data is explicitly provided.
- Help users understand what should be addressed first.
- Provide recommendations without making AWS changes.

==================================================
SOURCE OF TRUTH
==================================================
The AUDIT CONTEXT provided below is the ONLY source of truth for AWS-specific information.
Use only information explicitly contained in the audit context.

Never use assumptions, general AWS knowledge, or invented data as evidence about the user's environment.

==================================================
STRICT RULES
==================================================
1. NEVER invent AWS resources, findings, configurations, costs, savings, compliance results, or evidence.
2. If information is not present in the audit context, say: "This information was not collected in the current scan."
3. Never assume that an AWS service, security control, configuration, or resource exists simply because it is commonly used in AWS.
4. Never infer that a security control is enabled or disabled unless the audit context explicitly states its status.
5. Never claim a security control passed unless the audit context shows it passed.
6. Never claim a security control failed unless the audit context shows it failed.
7. Never claim that an AWS environment is completely secure, even if the scan reports zero findings. Instead say: "No findings were identified in the controls evaluated by the current scan."
8. Clearly distinguish between: Facts from the audit, Analysis based on those facts, AI recommendations.
9. Never present an AI recommendation as an AWS configuration that currently exists.
10. Never directly modify AWS resources. The assistant is READ-ONLY.
11. Never provide AWS access keys, secret keys, passwords, tokens, or credentials.
12. Never fabricate AWS API responses or evidence.
13. If a user asks you to make AWS changes, explain that you cannot modify resources directly. Point them to the "Apply" button in the Optimization Recommendations section for supported actions.

==================================================
MISSING DATA
==================================================
When information is unavailable, do NOT guess.
Use: "This information was not collected in the current scan."

Example: If GuardDuty is not mentioned in the audit context, do NOT say "GuardDuty is disabled."
Instead say: "GuardDuty status was not collected in the current scan."

==================================================
COST RULES
==================================================
- Use only cost values provided in the audit context.
- Do not invent costs or estimate AWS prices using external knowledge.
- You may perform simple arithmetic using explicitly provided values.
- Clearly identify calculated values.

==================================================
SAVINGS RULES
==================================================
Always describe optimization savings as "estimated potential savings."
Never describe them as guaranteed savings.
Do not claim that savings will definitely be realized.

==================================================
SECURITY FINDINGS
==================================================
When explaining a finding, use this structure:
- Finding: What was detected
- Severity: Critical/High/Medium/Low
- Business Impact: Why it matters to the business
- Technical Evidence: Specific resource/config from the scan
- Recommendation: What to do about it

Do not invent technical evidence.

==================================================
COMPLIANCE
==================================================
Never claim "The company is SOC 2 compliant" or "certified" or "HIPAA compliant."
Use: "readiness", "control coverage", "assessment", "potential gaps", "evaluated controls."

==================================================
RESOURCE COUNTS
==================================================
IMPORTANT: The audit context provides specific resource counts with breakdowns (e.g., running vs stopped instances).
Always use the EXACT breakdown provided. For example:
- If context says "total_ec2_instances: 6, running: 3, stopped: 3" — report it accurately with the breakdown.
- Never say "6 running instances" when only 3 are running.
- Always distinguish between total count and active/running count.

==================================================
RESPONSE STYLE
==================================================
- Lead with the most important information.
- Use plain language a business person can understand.
- Keep responses concise.
- Use bullet points where appropriate.
- Include relevant numbers from the audit context.
- End with clear next steps when appropriate.
- For simple factual questions, provide a direct answer first, then offer to explain further.

Use this structure when appropriate:
### Summary
Short business-friendly answer.
### What the audit found
Specific facts from the scan.
### Why it matters
Business impact.
### Recommended next steps
Actionable recommendations.

==================================================
IMPORTANT DISTINCTION
==================================================
FACT: Information explicitly reported by the AWS audit scanner.
ANALYSIS: Reasoning based only on the reported facts.
RECOMMENDATION: Suggested action based on the findings.
Never present analysis or recommendations as facts.

==================================================
AUDIT CONTEXT
==================================================
The following is the actual audit data. This is your ONLY source of truth:
"""


def build_audit_context(report_data: Dict[str, Any]) -> str:
    """
    Build a structured context string from scan results.
    This is the ONLY data the AI can reference.
    Provides precise breakdowns to prevent misrepresentation.
    """
    context = {}

    # Account info
    metadata = report_data.get('report_metadata', {})
    context['account'] = metadata.get('account_info', {})
    context['scan_time'] = metadata.get('generated_at', 'Unknown')

    # Cost summary
    cost = report_data.get('cost_analysis', {})
    context['cost'] = {
        'total_monthly_cost_usd': cost.get('total_cost', 0),
        'data_source': cost.get('data_source', 'unknown'),
        'note': 'billing_api means real AWS billing data; estimated means calculated from inventory',
        'top_services': cost.get('cost_by_service', [])[:10],
        'cost_by_region': cost.get('cost_by_region', [])[:5],
    }

    # Security summary
    security = report_data.get('security_audit', {})
    summary = security.get('summary', {})
    context['security'] = {
        'total_findings': summary.get('total', 0),
        'critical': summary.get('critical', 0),
        'high': summary.get('high', 0),
        'medium': summary.get('medium', 0),
        'low': summary.get('low', 0),
        'findings_detail': security.get('findings', [])[:25],
    }

    # Optimization
    optimization = report_data.get('optimization', {})
    opt_summary = optimization.get('summary', {})
    context['optimization'] = {
        'total_recommendations': opt_summary.get('total_recommendations', 0),
        'estimated_potential_monthly_savings_usd': opt_summary.get('potential_monthly_savings', 0),
        'estimated_potential_annual_savings_usd': opt_summary.get('potential_annual_savings', 0),
        'note': 'These are estimated potential savings, not guaranteed',
        'recommendations': optimization.get('recommendations', [])[:15],
    }

    # Resource inventory - PRECISE breakdown
    inventory = report_data.get('resource_inventory', {})
    inv_summary = inventory.get('summary', {})
    context['resources'] = {
        'ec2_instances': {
            'total': inv_summary.get('total_ec2_instances', 0),
            'running': inv_summary.get('running_ec2_instances', 0),
            'stopped': inv_summary.get('stopped_ec2_instances', 0),
        },
        'ebs_volumes': {
            'total': inv_summary.get('total_ebs_volumes', 0),
            'unattached': inv_summary.get('unattached_volumes', 0),
            'total_storage_gb': inv_summary.get('total_ebs_storage_gb', 0),
        },
        'rds_instances': inv_summary.get('total_rds_instances', 0),
        's3_buckets': inv_summary.get('total_s3_buckets', 0),
        'lambda_functions': inv_summary.get('total_lambda_functions', 0),
        'load_balancers': inv_summary.get('total_load_balancers', 0),
        'nat_gateways': inv_summary.get('total_nat_gateways', 0),
        'elastic_ips': {
            'total': inv_summary.get('total_elastic_ips', 0),
            'unused': inv_summary.get('unused_elastic_ips', 0),
        },
        'security_groups': inv_summary.get('total_security_groups', 0),
        'regions_scanned': inv_summary.get('regions_scanned', []),
    }

    # Scores (if available)
    scores = report_data.get('scores', {})
    if scores:
        context['health_scores'] = {
            'overall': scores.get('overall_score', 'Not calculated'),
            'grade': scores.get('overall_grade', 'N/A'),
            'status': scores.get('overall_status', 'N/A'),
            'categories': scores.get('categories', {}),
        }

    # Executive summary (if available)
    exec_summary = report_data.get('executive_summary', {})
    if exec_summary:
        context['executive_summary'] = {
            'text': exec_summary.get('text_summary', ''),
            'affected_resources': exec_summary.get('affected_resources', 0),
        }

    # Top priorities (if available)
    priorities = report_data.get('top_priority_actions', [])[:5]
    if priorities:
        context['top_priority_actions'] = priorities

    return json.dumps(context, indent=2, default=str)


def ask_advisor(
    question: str,
    report_data: Dict[str, Any],
    session: Optional[boto3.Session] = None,
    model_id: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
) -> Dict[str, Any]:
    """
    Ask the AI Audit Advisor a question about the scan results.
    """
    try:
        # Build context from scan data
        audit_context = build_audit_context(report_data)

        # Create Bedrock client - try configured profiles first
        bedrock = None
        if session:
            bedrock = session.client('bedrock-runtime', region_name='us-east-1')
        else:
            import configparser
            home_dir = os.path.expanduser("~")
            credentials_file = os.path.join(home_dir, ".aws", "credentials")
            if os.path.exists(credentials_file):
                creds_parser = configparser.ConfigParser()
                creds_parser.read(credentials_file)
                profiles = [s for s in creds_parser.sections() if s != 'default']
                if profiles:
                    profile_session = boto3.Session(profile_name=profiles[0])
                    bedrock = profile_session.client('bedrock-runtime', region_name='us-east-1')

            if not bedrock:
                bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

        # Build the prompt
        full_system = SYSTEM_PROMPT + "\n" + audit_context

        # Call Bedrock
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "system": full_system,
            "messages": [
                {"role": "user", "content": question}
            ],
            "temperature": 0.2,
        }

        response = bedrock.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(request_body)
        )

        response_body = json.loads(response['body'].read())

        answer = response_body.get('content', [{}])[0].get('text', 'No response generated.')
        input_tokens = response_body.get('usage', {}).get('input_tokens', 0)
        output_tokens = response_body.get('usage', {}).get('output_tokens', 0)

        return {
            "answer": answer,
            "model": model_id,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "status": "success"
        }

    except Exception as e:
        error_msg = str(e)
        if 'AccessDeniedException' in error_msg:
            return {
                "answer": f"Access denied to Bedrock. Ensure IAM policy includes bedrock:InvokeModel. Detail: {error_msg[:150]}",
                "model": model_id,
                "status": "error",
                "error": "access_denied"
            }
        elif 'ResourceNotFoundException' in error_msg or 'model_not_found' in error_msg.lower():
            return {
                "answer": f"AI model not available: {error_msg[:200]}",
                "model": model_id,
                "status": "error",
                "error": "model_not_enabled"
            }
        elif 'ThrottlingException' in error_msg:
            return {
                "answer": "Too many requests. Please wait a moment and try again.",
                "model": model_id,
                "status": "error",
                "error": "throttled"
            }
        else:
            return {
                "answer": f"AI Advisor error: {error_msg[:200]}",
                "model": model_id,
                "status": "error",
                "error": "unknown"
            }


# Suggested questions for the UI
SUGGESTED_QUESTIONS = [
    "Is my AWS environment secure?",
    "What are my biggest risks?",
    "What should I fix first?",
    "Why is my AWS bill high?",
    "How much can I save?",
    "Explain this audit in simple terms",
    "Are we ready for SOC 2?",
    "Which resources are publicly exposed?",
    "Which resources are not encrypted?",
    "Summarize this audit for management",
]

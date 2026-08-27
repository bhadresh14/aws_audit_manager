"""
AWS Health Check Tool - Report Generator Module
Generates comprehensive reports in multiple formats with client-friendly information
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, Optional


class ReportGenerator:
    """Generates reports from health check results"""
    
    def __init__(self, output_dir: str = "output"):
        self.output_dir = output_dir
        self.timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
    
    def generate_all_reports(self, data: Dict[str, Any], 
                            account_info: Dict[str, str]) -> Dict[str, str]:
        """Generate reports in all formats"""
        print("[Report] Generating Reports...")
        
        reports = {}
        reports['html'] = self.generate_html_report(data, account_info)
        reports['markdown'] = self.generate_markdown_report(data, account_info)
        reports['json'] = self.generate_json_report(data, account_info)
        
        print(f"  Reports saved to: {self.output_dir}/")
        return reports

    def generate_html_report(self, data: Dict[str, Any], 
                            account_info: Dict[str, str]) -> str:
        """Generate HTML report"""
        print("  - Generating HTML report...")
        
        html_content = self._build_html_report(data, account_info)
        filename = f"aws_health_check_{self.timestamp}.html"
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"    Saved: {filename}")
        return filepath

    def generate_markdown_report(self, data: Dict[str, Any],
                                 account_info: Dict[str, str]) -> str:
        """Generate Markdown report"""
        print("  - Generating Markdown report...")
        
        md_content = self._build_markdown_report(data, account_info)
        filename = f"aws_health_check_{self.timestamp}.md"
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        print(f"    Saved: {filename}")
        return filepath

    def generate_json_report(self, data: Dict[str, Any],
                            account_info: Dict[str, str]) -> str:
        """Generate JSON report"""
        print("  - Generating JSON report...")
        
        report_data = {
            "report_metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "tool_version": "2.0.0",
                "account_info": account_info
            },
            "cost_analysis": data.get('cost', {}),
            "resource_inventory": data.get('inventory', {}),
            "security_audit": data.get('security', {}),
            "optimization": data.get('optimization', {})
        }
        
        # Add scoring and executive summary
        try:
            from modules.scoring import calculate_scores, generate_executive_summary, get_top_priority_actions
            scores = calculate_scores(report_data)
            executive_summary = generate_executive_summary(report_data, scores)
            top_priorities = get_top_priority_actions(report_data)
            
            report_data["scores"] = scores
            report_data["executive_summary"] = executive_summary
            report_data["top_priority_actions"] = top_priorities
        except Exception as e:
            print(f"    Warning: Scoring calculation failed: {e}")
        
        # Fix savings: ensure only positive values
        opt = report_data.get('optimization', {})
        recs = opt.get('recommendations', [])
        positive_savings = sum(r.get('estimated_monthly_savings', 0) for r in recs if r.get('estimated_monthly_savings', 0) > 0)
        if 'summary' in opt:
            opt['summary']['potential_monthly_savings'] = round(positive_savings, 2)
            opt['summary']['potential_annual_savings'] = round(positive_savings * 12, 2)
        
        filename = f"aws_health_check_{self.timestamp}.json"
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, default=str)
        
        print(f"    Saved: {filename}")
        return filepath

    def _build_markdown_report(self, data: Dict[str, Any],
                               account_info: Dict[str, str]) -> str:
        """Build markdown report content"""
        cost = data.get('cost', {})
        security = data.get('security', {})
        optimization = data.get('optimization', {})
        inventory = data.get('inventory', {})
        
        md = []
        md.append("# 🔍 AWS Health Check Report\n\n")
        md.append(f"**📅 Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n")
        md.append(f"**🏢 Account ID:** {account_info.get('account_id', 'N/A')}\n\n")
        md.append(f"**🌍 Region:** {account_info.get('region', 'N/A')}\n\n")
        md.append("---\n\n")
        
        # Executive Summary
        md.append("## 📊 Executive Summary\n\n")
        sec_summary = security.get('summary', {})
        opt_summary = optimization.get('summary', {})
        
        cost_label = "Monthly Cost"
        if cost.get('data_source') == 'estimated':
            cost_label = "Monthly Cost (Estimated)"
        
        md.append("| Metric | Value |\n")
        md.append("|--------|-------|\n")
        md.append(f"| 💰 {cost_label} | **${cost.get('total_cost', 0):.2f}** |\n")
        md.append(f"| 🔒 Security Findings | **{sec_summary.get('total', 0)}** |\n")
        md.append(f"| 🚨 Critical Issues | **{sec_summary.get('critical', 0)}** |\n")
        md.append(f"| 🚀 Optimization Opportunities | **{opt_summary.get('total_recommendations', 0)}** |\n")
        md.append(f"| 💵 Potential Monthly Savings | **${opt_summary.get('potential_monthly_savings', 0):.2f}** |\n\n")
        
        # Cost Analysis
        md.append("## 💰 Cost Analysis\n\n")
        if cost.get('data_source') == 'estimated':
            md.append("> ⚠️ **Note:** Costs are ESTIMATED from resource inventory (billing API access unavailable)\n\n")
        
        md.append(f"**Total Monthly Cost:** ${cost.get('total_cost', 0):.2f}\n\n")
        
        if cost.get('cost_by_service'):
            md.append("### Cost by Service\n\n")
            md.append("| Service | Cost (USD) | % |\n")
            md.append("|---------|------------|---|\n")
            for svc in cost.get('cost_by_service', [])[:10]:
                md.append(f"| {svc['service']} | ${svc['cost']:.2f} | {svc.get('percentage', 0):.1f}% |\n")
        md.append("\n")
        
        # Security Section - Enhanced
        md.append("## 🔒 Security Audit\n\n")
        md.append("### Summary\n\n")
        md.append(f"| Severity | Count |\n")
        md.append(f"|----------|-------|\n")
        md.append(f"| 🚨 Critical | **{sec_summary.get('critical', 0)}** |\n")
        md.append(f"| ⚠️ High | **{sec_summary.get('high', 0)}** |\n")
        md.append(f"| 📋 Medium | **{sec_summary.get('medium', 0)}** |\n")
        md.append(f"| ℹ️ Low | **{sec_summary.get('low', 0)}** |\n\n")
        
        findings = security.get('findings', [])
        if findings:
            md.append("### Security Findings Detail\n\n")
            md.append("| Severity | Issue | Resource Name | What's Wrong | How to Fix |\n")
            md.append("|----------|-------|---------------|--------------|------------|\n")
            
            for f in findings:
                sev_icon = {'CRITICAL': '🚨', 'HIGH': '⚠️', 'MEDIUM': '📋', 'LOW': 'ℹ️'}.get(f['severity'], '•')
                resource = f['resource']
                desc = f.get('description', f['title'])[:80]
                rec = f.get('recommendation', 'Review and remediate')[:60]
                md.append(f"| {sev_icon} {f['severity']} | {f['title']} | `{resource}` | {desc} | {rec} |\n")
        md.append("\n")
        
        # Optimization Section - Enhanced  
        md.append("## 🚀 Optimization Recommendations\n\n")
        md.append(f"**💵 Potential Monthly Savings:** ${opt_summary.get('potential_monthly_savings', 0):.2f}\n\n")
        md.append(f"**📅 Potential Annual Savings:** ${opt_summary.get('potential_annual_savings', 0):.2f}\n\n")
        
        recs = optimization.get('recommendations', [])
        if recs:
            md.append("### Recommendations Detail\n\n")
            md.append("| Category | Issue | Resource | Savings | Action Required |\n")
            md.append("|----------|-------|----------|---------|----------------|\n")
            
            # Sort by savings
            sorted_recs = sorted(recs, key=lambda x: x.get('estimated_monthly_savings', 0), reverse=True)
            
            for r in sorted_recs:
                cat_icon = {'Storage': '💾', 'Compute': '🖥️', 'Networking': '🌐', 'Database': '🗄️', 'Commitments': '📋'}.get(r['category'], '📊')
                resource = r['resource'][:30] if len(r['resource']) > 30 else r['resource']
                action = r.get('action', 'Review and optimize')[:50]
                md.append(f"| {cat_icon} {r['category']} | {r['title']} | `{resource}` | **${r.get('estimated_monthly_savings', 0):.2f}/mo** | {action} |\n")
        
        md.append("\n")
        
        # Resource Inventory
        md.append("## 🖥️ Resource Inventory\n\n")
        inv_summary = inventory.get('summary', {})
        md.append("| Resource Type | Count |\n")
        md.append("|---------------|-------|\n")
        md.append(f"| EC2 Instances | {inv_summary.get('total_ec2_instances', 0)} |\n")
        md.append(f"| EBS Volumes | {inv_summary.get('total_ebs_volumes', 0)} |\n")
        md.append(f"| RDS Instances | {inv_summary.get('total_rds_instances', 0)} |\n")
        md.append(f"| S3 Buckets | {inv_summary.get('total_s3_buckets', 0)} |\n")
        md.append(f"| Lambda Functions | {inv_summary.get('total_lambda_functions', 0)} |\n")
        md.append(f"| Load Balancers | {inv_summary.get('total_load_balancers', 0)} |\n")
        md.append(f"| NAT Gateways | {inv_summary.get('total_nat_gateways', 0)} |\n")
        md.append(f"| Elastic IPs | {inv_summary.get('total_elastic_ips', 0)} |\n")
        
        return ''.join(md)

    def _build_html_report(self, data: Dict[str, Any], account_info: Dict[str, str]) -> str:
        """Build HTML report with client-friendly information"""
        cost = data.get('cost', {})
        security = data.get('security', {})
        optimization = data.get('optimization', {})
        inventory = data.get('inventory', {})
        
        # Build cost rows
        cost_rows = ""
        for svc in cost.get('cost_by_service', [])[:10]:
            pct = svc.get('percentage', 0)
            cost_rows += f"""<tr>
                <td><strong>{svc['service']}</strong></td>
                <td class="cost">${svc['cost']:.2f}</td>
                <td>
                    <div class="progress-bar"><div class="progress-fill" style="width:{min(pct, 100)}%"></div></div>
                    {pct:.1f}%
                </td>
            </tr>"""
        
        # Build security rows with enhanced client-friendly information
        security_rows = ""
        for finding in security.get('findings', []):
            sev = finding['severity'].lower()
            sev_icon = {'critical': '🚨', 'high': '⚠️', 'medium': '📋', 'low': 'ℹ️'}.get(sev, '•')
            
            resource = finding['resource']
            description = finding.get('description', finding['title'])
            recommendation = finding.get('recommendation', '')
            
            security_rows += f"""<tr>
                <td><span class="badge badge-{sev}">{sev_icon} {finding['severity']}</span></td>
                <td><strong>{finding['category']}</strong></td>
                <td>
                    <div class="item-title">{finding['title']}</div>
                    <div class="item-desc">{description}</div>
                </td>
                <td>
                    <code class="resource-code">{resource}</code>
                    {f'<div class="action-box">💡 <strong>Fix:</strong> {recommendation}</div>' if recommendation else ''}
                </td>
            </tr>"""
        
        # Build optimization rows with enhanced client-friendly information
        opt_rows = ""
        sorted_recs = sorted(optimization.get('recommendations', []), 
                            key=lambda x: x.get('estimated_monthly_savings', 0), reverse=True)
        
        for rec in sorted_recs:
            cat_icon = {
                'Storage': '💾',
                'Compute': '🖥️',
                'Networking': '🌐',
                'Database': '🗄️',
                'Commitments': '📋'
            }.get(rec['category'], '📊')
            
            action = rec.get('action', '')
            description = rec.get('description', '')
            
            opt_rows += f"""<tr>
                <td><span class="category-badge">{cat_icon} {rec['category']}</span></td>
                <td>
                    <div class="item-title">{rec['title']}</div>
                    <div class="item-desc">{description}</div>
                </td>
                <td><code class="resource-code">{rec['resource']}</code></td>
                <td class="savings-cell">${rec.get('estimated_monthly_savings', 0):.2f}<br><small>/month</small></td>
                <td>
                    {f'<div class="action-box">💡 {action}</div>' if action else '<span class="text-muted">Review resource</span>'}
                </td>
            </tr>"""
        
        summary = security.get('summary', {})
        opt_summary = optimization.get('summary', {})
        inv_summary = inventory.get('summary', {})
        
        # Check if costs are estimated
        cost_estimated = cost.get('data_source') == 'estimated'
        cost_badge = ' <span class="badge badge-info">ESTIMATED</span>' if cost_estimated else ''
        cost_note = '<div class="alert alert-warning">⚠️ Costs are estimated from resource inventory because billing API access is unavailable. Actual costs may vary.</div>' if cost_estimated else ''

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AWS Health Check Report - {account_info.get('account_id', 'N/A')}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            background: #f0f2f5; 
            color: #333; 
            line-height: 1.6;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
        
        /* Header */
        .header {{ 
            background: linear-gradient(135deg, #232f3e 0%, #37475a 100%); 
            color: white; 
            padding: 30px; 
            border-radius: 12px; 
            margin-bottom: 24px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .header h1 {{ font-size: 28px; margin-bottom: 8px; }}
        .header .meta {{ opacity: 0.9; font-size: 14px; }}
        .header .meta p {{ margin: 4px 0; }}
        
        /* Cards */
        .card {{ 
            background: white; 
            border-radius: 12px; 
            padding: 24px; 
            margin-bottom: 24px; 
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}
        .card h2 {{ 
            color: #232f3e; 
            margin-bottom: 20px; 
            padding-bottom: 12px; 
            border-bottom: 3px solid #ff9900;
            font-size: 22px;
        }}
        
        /* Summary Grid */
        .summary-grid {{ 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); 
            gap: 16px; 
        }}
        .summary-item {{ 
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            padding: 24px; 
            border-radius: 12px; 
            text-align: center;
            border: 1px solid #dee2e6;
        }}
        .summary-item .value {{ font-size: 36px; font-weight: 700; color: #232f3e; }}
        .summary-item .label {{ color: #666; font-size: 14px; margin-top: 8px; font-weight: 500; }}
        .summary-item.critical .value {{ color: #dc3545; }}
        .summary-item.warning .value {{ color: #fd7e14; }}
        .summary-item.success .value {{ color: #28a745; }}
        
        /* Tables */
        table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
        th, td {{ padding: 14px 12px; text-align: left; border-bottom: 1px solid #e9ecef; vertical-align: top; }}
        th {{ 
            background: #f8f9fa; 
            font-weight: 600; 
            color: #495057;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        tr:hover {{ background: #f8f9fa; }}
        
        /* Badges */
        .badge {{ 
            padding: 6px 12px; 
            border-radius: 20px; 
            font-size: 12px; 
            font-weight: 600;
            display: inline-block;
        }}
        .badge-critical {{ background: #fee2e2; color: #dc2626; }}
        .badge-high {{ background: #ffedd5; color: #ea580c; }}
        .badge-medium {{ background: #fef3c7; color: #d97706; }}
        .badge-low {{ background: #dcfce7; color: #16a34a; }}
        .badge-info {{ background: #dbeafe; color: #2563eb; }}
        
        /* Category Badge */
        .category-badge {{
            background: #e9ecef;
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 500;
            display: inline-block;
        }}
        
        /* Item styling */
        .item-title {{ font-weight: 600; color: #232f3e; margin-bottom: 6px; font-size: 14px; }}
        .item-desc {{ font-size: 13px; color: #6c757d; line-height: 1.5; }}
        
        /* Resource code */
        .resource-code {{ 
            background: #f1f3f4; 
            padding: 6px 10px; 
            border-radius: 6px; 
            font-size: 12px;
            font-family: 'Monaco', 'Consolas', monospace;
            display: inline-block;
            max-width: 200px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        
        /* Action box */
        .action-box {{ 
            font-size: 12px; 
            color: #0d6efd; 
            margin-top: 8px; 
            padding: 10px 12px; 
            background: #e7f1ff; 
            border-radius: 8px;
            border-left: 3px solid #0d6efd;
        }}
        
        /* Savings cell */
        .savings-cell {{ 
            font-weight: 700; 
            color: #28a745; 
            font-size: 18px;
            text-align: center;
        }}
        .savings-cell small {{ font-size: 11px; color: #6c757d; font-weight: 400; }}
        
        /* Cost cell */
        .cost {{ font-weight: 600; color: #232f3e; }}
        
        /* Progress bar */
        .progress-bar {{ 
            height: 8px; 
            background: #e9ecef; 
            border-radius: 4px; 
            overflow: hidden; 
            width: 100px; 
            display: inline-block; 
            vertical-align: middle; 
            margin-right: 8px; 
        }}
        .progress-fill {{ height: 100%; background: linear-gradient(90deg, #ff9900, #ffb84d); }}
        
        /* Alert */
        .alert {{ padding: 16px; border-radius: 8px; margin-bottom: 16px; }}
        .alert-warning {{ background: #fff3cd; color: #856404; border: 1px solid #ffeeba; }}
        
        /* Text muted */
        .text-muted {{ color: #6c757d; font-style: italic; }}
        
        /* Print styles */
        @media print {{
            body {{ background: white; }}
            .card {{ box-shadow: none; border: 1px solid #dee2e6; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 AWS Health Check Report</h1>
            <div class="meta">
                <p>📅 <strong>Generated:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                <p>🏢 <strong>Account:</strong> {account_info.get('account_id', 'N/A')} | 🌍 <strong>Region:</strong> {account_info.get('region', 'N/A')}</p>
                <p>👤 <strong>Scanned by:</strong> {account_info.get('user_arn', 'N/A').split('/')[-1]}</p>
            </div>
        </div>

        <div class="card">
            <h2>📊 Executive Summary</h2>
            <div class="summary-grid">
                <div class="summary-item">
                    <div class="value">${cost.get('total_cost', 0):.2f}</div>
                    <div class="label">💰 Monthly Cost{' (Est.)' if cost_estimated else ''}</div>
                </div>
                <div class="summary-item {'critical' if summary.get('critical', 0) > 0 else ''}">
                    <div class="value">{summary.get('critical', 0)}</div>
                    <div class="label">🚨 Critical Issues</div>
                </div>
                <div class="summary-item warning">
                    <div class="value">{summary.get('total', 0)}</div>
                    <div class="label">🔒 Security Findings</div>
                </div>
                <div class="summary-item success">
                    <div class="value">${opt_summary.get('potential_monthly_savings', 0):.2f}</div>
                    <div class="label">💵 Potential Savings/mo</div>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>💰 Cost Analysis{cost_badge}</h2>
            {cost_note}
            <p style="font-size: 18px; margin-bottom: 16px;"><strong>Total Monthly Cost:</strong> <span class="cost" style="font-size: 24px;">${cost.get('total_cost', 0):.2f}</span></p>
            <table>
                <thead><tr><th>Service</th><th>Cost (USD)</th><th>Percentage</th></tr></thead>
                <tbody>{cost_rows if cost_rows else '<tr><td colspan="3" class="text-muted">No cost data available</td></tr>'}</tbody>
            </table>
        </div>

        <div class="card">
            <h2>🔒 Security Audit</h2>
            <div class="summary-grid" style="margin-bottom: 20px;">
                <div class="summary-item critical"><div class="value">{summary.get('critical', 0)}</div><div class="label">🚨 Critical</div></div>
                <div class="summary-item warning"><div class="value">{summary.get('high', 0)}</div><div class="label">⚠️ High</div></div>
                <div class="summary-item"><div class="value">{summary.get('medium', 0)}</div><div class="label">📋 Medium</div></div>
                <div class="summary-item" style="background: #d4edda;"><div class="value">{summary.get('low', 0)}</div><div class="label">ℹ️ Low</div></div>
            </div>
            <table>
                <thead>
                    <tr>
                        <th style="width:120px">Severity</th>
                        <th style="width:140px">Category</th>
                        <th>Issue & Description</th>
                        <th style="width:280px">Resource & How to Fix</th>
                    </tr>
                </thead>
                <tbody>{security_rows if security_rows else '<tr><td colspan="4" class="text-muted">No security issues found - Great job!</td></tr>'}</tbody>
            </table>
        </div>

        <div class="card">
            <h2>🚀 Optimization Recommendations</h2>
            <div class="summary-grid" style="margin-bottom: 20px;">
                <div class="summary-item success">
                    <div class="value">${opt_summary.get('potential_monthly_savings', 0):.2f}</div>
                    <div class="label">💵 Monthly Savings</div>
                </div>
                <div class="summary-item success">
                    <div class="value">${opt_summary.get('potential_annual_savings', 0):.2f}</div>
                    <div class="label">📅 Annual Savings</div>
                </div>
                <div class="summary-item">
                    <div class="value">{opt_summary.get('total_recommendations', 0)}</div>
                    <div class="label">📋 Recommendations</div>
                </div>
            </div>
            <table>
                <thead>
                    <tr>
                        <th style="width:130px">Category</th>
                        <th>Issue & Details</th>
                        <th style="width:180px">Resource</th>
                        <th style="width:100px">Savings</th>
                        <th style="width:250px">Action Required</th>
                    </tr>
                </thead>
                <tbody>{opt_rows if opt_rows else '<tr><td colspan="5" class="text-muted">No optimization recommendations - Resources are well optimized!</td></tr>'}</tbody>
            </table>
        </div>

        <div class="card">
            <h2>🖥️ Resource Inventory</h2>
            <div class="summary-grid">
                <div class="summary-item"><div class="value">{inv_summary.get('total_ec2_instances', 0)}</div><div class="label">EC2 Instances</div></div>
                <div class="summary-item"><div class="value">{inv_summary.get('total_ebs_volumes', 0)}</div><div class="label">EBS Volumes</div></div>
                <div class="summary-item"><div class="value">{inv_summary.get('total_s3_buckets', 0)}</div><div class="label">S3 Buckets</div></div>
                <div class="summary-item"><div class="value">{inv_summary.get('total_lambda_functions', 0)}</div><div class="label">Lambda Functions</div></div>
                <div class="summary-item"><div class="value">{inv_summary.get('total_rds_instances', 0)}</div><div class="label">RDS Instances</div></div>
                <div class="summary-item"><div class="value">{inv_summary.get('total_load_balancers', 0)}</div><div class="label">Load Balancers</div></div>
            </div>
        </div>

        <footer style="text-align: center; padding: 20px; color: #6c757d; font-size: 12px;">
            Generated by AWS Health Check Tool v1.0.0 | Report ID: {self.timestamp}
        </footer>
    </div>
</body>
</html>"""
        return html


if __name__ == "__main__":
    generator = ReportGenerator()
    print("Report generator initialized successfully")

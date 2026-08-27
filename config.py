"""
AWS Health Check Tool - Configuration
"""

from datetime import datetime, timedelta

# AWS Configuration
AWS_REGIONS = [
    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
    "eu-west-1", "eu-west-2", "eu-central-1",
    "ap-south-1", "ap-southeast-1", "ap-southeast-2", "ap-northeast-1"
]

# Default region (will be overridden by AWS profile)
DEFAULT_REGION = "ap-south-1"

# Cost Analysis Settings
COST_LOOKBACK_DAYS = 30
COST_FORECAST_DAYS = 30

# Date ranges for cost analysis
def get_cost_dates():
    """Get date ranges for cost analysis"""
    today = datetime.utcnow().date()
    first_of_month = today.replace(day=1)
    last_month_end = first_of_month - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    
    return {
        "current_month_start": first_of_month.strftime("%Y-%m-%d"),
        "current_month_end": today.strftime("%Y-%m-%d"),
        "last_month_start": last_month_start.strftime("%Y-%m-%d"),
        "last_month_end": first_of_month.strftime("%Y-%m-%d"),
        "last_30_days_start": (today - timedelta(days=30)).strftime("%Y-%m-%d"),
        "last_30_days_end": today.strftime("%Y-%m-%d"),
    }

# Security Audit Settings
SECURITY_CHECKS = {
    "check_open_security_groups": True,
    "check_public_s3_buckets": True,
    "check_iam_users_without_mfa": True,
    "check_root_account_usage": True,
    "check_unused_credentials": True,
    "check_unencrypted_ebs": True,
    "check_unencrypted_rds": True,
    "check_public_rds": True,
    "check_default_vpc_usage": True,
}

# Critical ports to check in security groups
CRITICAL_PORTS = {
    22: "SSH",
    3389: "RDP",
    3306: "MySQL",
    5432: "PostgreSQL",
    1433: "MSSQL",
    27017: "MongoDB",
    6379: "Redis",
    11211: "Memcached",
    9200: "Elasticsearch",
    5601: "Kibana",
}

# Resource Inventory Settings
RESOURCE_TYPES = [
    "ec2_instances",
    "ec2_volumes",
    "ec2_security_groups",
    "ec2_elastic_ips",
    "rds_instances",
    "s3_buckets",
    "lambda_functions",
    "ecs_clusters",
    "eks_clusters",
    "load_balancers",
    "nat_gateways",
    "vpc",
    "cloudfront_distributions",
    "route53_hosted_zones",
    "secrets_manager",
    "ecr_repositories",
]

# Optimization Thresholds
OPTIMIZATION_THRESHOLDS = {
    "cpu_underutilized_percent": 10,  # Below this is underutilized
    "cpu_overutilized_percent": 80,   # Above this is overutilized
    "memory_underutilized_percent": 20,
    "ebs_unused_days": 30,            # Days volume unattached
    "eip_unused_cost_per_month": 3.6, # Cost of unused EIP
    "snapshot_age_days": 90,          # Old snapshots
    "ami_age_days": 180,              # Old AMIs
}

# Report Settings
REPORT_SETTINGS = {
    "company_name": "AWS Health Check Report",
    "output_format": ["html", "markdown"],  # Options: html, markdown, json, pdf
    "include_recommendations": True,
    "include_cost_projections": True,
}

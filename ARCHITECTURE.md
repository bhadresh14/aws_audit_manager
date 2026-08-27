# AWS Health Check Tool - Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                           AWS HEALTH CHECK TOOL v1.0.0                                  │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                              MAIN ENTRY POINT                                    │   │
│  │                                 main.py                                          │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────┐    │   │
│  │  │  • Parse CLI arguments (--profile, --region, --output-dir)              │    │   │
│  │  │  • Initialize AWS Session (boto3)                                        │    │   │
│  │  │  • Get Account Info via STS                                              │    │   │
│  │  │  • Orchestrate all module execution                                      │    │   │
│  │  │  • Print summary to console                                              │    │   │
│  │  └─────────────────────────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                         │                                               │
│                                         ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                           CONFIGURATION                                          │   │
│  │                             config.py                                            │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────┐    │   │
│  │  │  • AWS_REGIONS list                    • CRITICAL_PORTS mapping         │    │   │
│  │  │  • Date range functions                • OPTIMIZATION_THRESHOLDS        │    │   │
│  │  │  • SECURITY_CHECKS flags               • REPORT_SETTINGS                │    │   │
│  │  └─────────────────────────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                         │                                               │
│         ┌───────────────────────────────┼───────────────────────────────┐               │
│         │                               │                               │               │
│         ▼                               ▼                               ▼               │
│  ┌─────────────────┐             ┌─────────────────┐             ┌─────────────────┐   │
│  │   MODULES/      │             │   MODULES/      │             │   MODULES/      │   │
│  └─────────────────┘             └─────────────────┘             └─────────────────┘   │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    MODULES                                              │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│  ┌──────────────────────────┐    ┌──────────────────────────┐                          │
│  │  💰 COST ANALYZER        │    │  💵 COST ESTIMATOR       │                          │
│  │    cost_analyzer.py      │───▶│    cost_estimator.py     │                          │
│  ├──────────────────────────┤    ├──────────────────────────┤                          │
│  │ AWS APIs Used:           │    │ Fallback when billing    │                          │
│  │ • Cost Explorer (ce)     │    │ API access denied        │                          │
│  │                          │    │                          │                          │
│  │ Features:                │    │ Features:                │                          │
│  │ • Cost by Service        │    │ • MULTI-REGION PRICING   │                          │
│  │ • Cost by Region         │    │ • EC2 pricing by region  │                          │
│  │ • Daily Cost Trend       │    │ • EBS pricing by region  │                          │
│  │ • Cost Forecast          │    │ • NAT/ELB regional rates │                          │
│  │ • Anomaly Detection      │    │ • EIP cost detection     │                          │
│  │ • Cost Drivers Analysis  │    │ • Regional multipliers   │                          │
│  │                          │    │ • Auto region detection  │                          │
│  └──────────────────────────┘    └──────────────────────────┘                          │
│                                                                                         │
│  ┌──────────────────────────┐    ┌──────────────────────────┐                          │
│  │  🖥️ RESOURCE INVENTORY   │    │  🔒 SECURITY AUDIT       │                          │
│  │   resource_inventory.py  │    │    security_audit.py     │                          │
│  ├──────────────────────────┤    ├──────────────────────────┤                          │
│  │ AWS APIs Used:           │    │ AWS APIs Used:           │                          │
│  │ • EC2                    │    │ • EC2 (Security Groups)  │                          │
│  │ • RDS                    │    │ • S3 (Bucket Policies)   │                          │
│  │ • S3                     │    │ • IAM (Users, MFA, Keys) │                          │
│  │ • Lambda                 │    │ • RDS (Encryption)       │                          │
│  │ • ECS                    │    │                          │                          │
│  │ • ELB                    │    │ Checks:                  │                          │
│  │ • VPC/NAT                │    │ • Open Security Groups   │                          │
│  │ • CloudFront             │    │ • Public S3 Buckets      │                          │
│  │ • ECR                    │    │ • IAM MFA Status         │                          │
│  │ • Secrets Manager        │    │ • Root Account Usage     │                          │
│  │ • IAM                    │    │ • Unused Credentials     │                          │
│  │                          │    │ • Unencrypted EBS/RDS    │                          │
│  │ Collects:                │    │ • Password Policy        │                          │
│  │ • Instance details       │    │ • Access Key Rotation    │                          │
│  │ • Volume info            │    │ • Public RDS             │                          │
│  │ • Bucket list            │    │ • Default VPC Usage      │                          │
│  │ • Function configs       │    │                          │                          │
│  │ • Cluster info           │    │ Severity Levels:         │                          │
│  │ • Network resources      │    │ • CRITICAL (Red)         │                          │
│  └──────────────────────────┘    │ • HIGH (Orange)          │                          │
│                                  │ • MEDIUM (Yellow)        │                          │
│                                  │ • LOW (Green)            │                          │
│                                  └──────────────────────────┘                          │
│                                                                                         │
│  ┌──────────────────────────┐                                                          │
│  │  📊 OPTIMIZER            │                                                          │
│  │    optimizer.py          │                                                          │
│  ├──────────────────────────┤                                                          │
│  │ AWS APIs Used:           │                                                          │
│  │ • EC2                    │                                                          │
│  │ • CloudWatch (Metrics)   │                                                          │
│  │ • RDS                    │                                                          │
│  │ • ECS                    │                                                          │
│  │ • S3                     │                                                          │
│  │ • ECR                    │                                                          │
│  │ • Cost Explorer          │                                                          │
│  │                          │                                                          │
│  │ Optimization Checks:     │                                                          │
│  │ • Unused EBS Volumes     │                                                          │
│  │ • Unused Elastic IPs     │                                                          │
│  │ • Idle EC2 Instances     │                                                          │
│  │ • Old Snapshots          │                                                          │
│  │ • Old AMIs               │                                                          │
│  │ • Underutilized RDS      │                                                          │
│  │ • NAT Gateway (VPC Endpoints)                                                       │
│  │ • ECS Cluster Utilization│                                                          │
│  │ • gp2 to gp3 Migration   │                                                          │
│  │ • ECR Lifecycle Policies │                                                          │
│  │ • S3 Lifecycle Policies  │                                                          │
│  │ • Reserved Instances     │                                                          │
│  │ • Savings Plans          │                                                          │
│  └──────────────────────────┘                                                          │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              REPORT GENERATOR                                           │
│                            reports/report_generator.py                                  │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│  ┌─────────────┐        ┌─────────────┐        ┌─────────────┐                         │
│  │   📄 HTML   │        │   📝 MD     │        │   📊 JSON   │                         │
│  │   Report    │        │   Report    │        │   Report    │                         │
│  ├─────────────┤        ├─────────────┤        ├─────────────┤                         │
│  │ • Executive │        │ • Tables    │        │ • Raw Data  │                         │
│  │   Summary   │        │ • Markdown  │        │ • API Ready │                         │
│  │ • Charts    │        │   Formatting│        │ • Parseable │                         │
│  │ • Color     │        │ • GitHub    │        │             │                         │
│  │   Coded     │        │   Compatible│        │             │                         │
│  │ • Actions   │        │             │        │             │                         │
│  └─────────────┘        └─────────────┘        └─────────────┘                         │
│         │                      │                      │                                 │
│         └──────────────────────┼──────────────────────┘                                 │
│                                ▼                                                        │
│                    ┌───────────────────────┐                                            │
│                    │     output/           │                                            │
│                    │  ├── *.html           │                                            │
│                    │  ├── *.md             │                                            │
│                    │  └── *.json           │                                            │
│                    └───────────────────────┘                                            │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              AWS SERVICES ACCESSED                                      │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                           COMPUTE & CONTAINERS                                   │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐          │   │
│  │  │   EC2    │  │   ECS    │  │  Lambda  │  │   ECR    │  │   EKS    │          │   │
│  │  │Instances │  │ Clusters │  │Functions │  │  Repos   │  │ Clusters │          │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘          │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                              STORAGE                                             │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐                         │   │
│  │  │   EBS    │  │    S3    │  │Snapshots │  │   AMIs   │                         │   │
│  │  │ Volumes  │  │ Buckets  │  │          │  │          │                         │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘                         │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                              DATABASE                                            │   │
│  │  ┌──────────┐  ┌──────────┐                                                     │   │
│  │  │   RDS    │  │ Secrets  │                                                     │   │
│  │  │Instances │  │ Manager  │                                                     │   │
│  │  └──────────┘  └──────────┘                                                     │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                              NETWORKING                                          │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐          │   │
│  │  │   VPC    │  │   NAT    │  │   ELB    │  │CloudFront│  │ Route53  │          │   │
│  │  │          │  │ Gateway  │  │ALB/NLB/CL│  │   CDN    │  │   DNS    │          │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘          │   │
│  │  ┌──────────┐  ┌──────────┐                                                     │   │
│  │  │ Elastic  │  │ Security │                                                     │   │
│  │  │   IPs    │  │  Groups  │                                                     │   │
│  │  └──────────┘  └──────────┘                                                     │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                         SECURITY & IDENTITY                                      │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐                                       │   │
│  │  │   IAM    │  │   STS    │  │   KMS    │                                       │   │
│  │  │Users/Keys│  │ Identity │  │   Keys   │                                       │   │
│  │  └──────────┘  └──────────┘  └──────────┘                                       │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                         MONITORING & BILLING                                     │   │
│  │  ┌──────────┐  ┌──────────┐                                                     │   │
│  │  │CloudWatch│  │   Cost   │                                                     │   │
│  │  │ Metrics  │  │ Explorer │                                                     │   │
│  │  └──────────┘  └──────────┘                                                     │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                 DATA FLOW                                               │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│   ┌─────────┐         ┌──────────────┐         ┌──────────────┐         ┌─────────┐   │
│   │  USER   │────────▶│   main.py    │────────▶│   MODULES    │────────▶│  AWS    │   │
│   │   CLI   │         │  Orchestrate │         │  Analyzers   │         │  APIs   │   │
│   └─────────┘         └──────────────┘         └──────────────┘         └─────────┘   │
│        │                     │                        │                       │        │
│        │                     │                        │                       │        │
│        │                     ▼                        ▼                       │        │
│        │              ┌──────────────┐         ┌──────────────┐              │        │
│        │              │   config.py  │         │   Results    │◀─────────────┘        │
│        │              │   Settings   │         │   Dict       │                        │
│        │              └──────────────┘         └──────────────┘                        │
│        │                                              │                                 │
│        │                                              ▼                                 │
│        │                                       ┌──────────────┐                        │
│        │                                       │   Report     │                        │
│        │                                       │  Generator   │                        │
│        │                                       └──────────────┘                        │
│        │                                              │                                 │
│        │                                              ▼                                 │
│        │                                       ┌──────────────┐                        │
│        └──────────────────────────────────────▶│   OUTPUT     │                        │
│              View Reports                      │  HTML/MD/JSON│                        │
│                                                └──────────────┘                        │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              FILE STRUCTURE                                             │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│   aws-health-check/                                                                     │
│   │                                                                                     │
│   ├── main.py                    # Entry point, CLI handling, orchestration            │
│   ├── config.py                  # Configuration, thresholds, settings                 │
│   ├── requirements.txt           # Python dependencies (boto3)                         │
│   ├── README.md                  # Documentation                                       │
│   ├── ARCHITECTURE.md            # This file                                           │
│   │                                                                                     │
│   ├── modules/                   # Analysis modules                                    │
│   │   ├── __init__.py                                                                  │
│   │   ├── cost_analyzer.py       # 💰 Billing API cost analysis                        │
│   │   ├── cost_estimator.py      # 💵 Fallback cost estimation                         │
│   │   ├── resource_inventory.py  # 🖥️ Resource discovery                               │
│   │   ├── security_audit.py      # 🔒 Security checks                                  │
│   │   └── optimizer.py           # 📊 Optimization recommendations                     │
│   │                                                                                     │
│   ├── reports/                   # Report generation                                   │
│   │   ├── __init__.py                                                                  │
│   │   └── report_generator.py    # 📄 HTML/MD/JSON report builder                      │
│   │                                                                                     │
│   └── output/                    # Generated reports                                   │
│       ├── aws_health_check_*.html                                                      │
│       ├── aws_health_check_*.md                                                        │
│       └── aws_health_check_*.json                                                      │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                           REQUIRED IAM PERMISSIONS                                      │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│   {                                                                                     │
│     "Version": "2012-10-17",                                                           │
│     "Statement": [                                                                      │
│       {                                                                                 │
│         "Sid": "HealthCheckReadOnly",                                                  │
│         "Effect": "Allow",                                                              │
│         "Action": [                                                                     │
│           "ec2:Describe*",                                                              │
│           "rds:Describe*",                                                              │
│           "s3:List*",                                                                   │
│           "s3:GetBucket*",                                                              │
│           "lambda:List*",                                                               │
│           "ecs:List*",                                                                  │
│           "ecs:Describe*",                                                              │
│           "elasticloadbalancing:Describe*",                                            │
│           "cloudfront:List*",                                                           │
│           "ecr:Describe*",                                                              │
│           "secretsmanager:List*",                                                       │
│           "iam:List*",                                                                  │
│           "iam:Get*",                                                                   │
│           "iam:GenerateCredentialReport",                                              │
│           "cloudwatch:GetMetricStatistics",                                            │
│           "sts:GetCallerIdentity",                                                      │
│           "ce:*",           # Cost Explorer (optional)                                 │
│           "budgets:*",      # Budgets (optional)                                       │
│           "pricing:*"       # Pricing API (optional)                                   │
│         ],                                                                              │
│         "Resource": "*"                                                                 │
│       }                                                                                 │
│     ]                                                                                   │
│   }                                                                                     │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

## Summary

| Component | Purpose |
|-----------|---------|
| **main.py** | Entry point, CLI, orchestration |
| **config.py** | Settings, thresholds, AWS regions |
| **cost_analyzer.py** | Billing API cost analysis |
| **cost_estimator.py** | Fallback cost estimation from inventory |
| **resource_inventory.py** | Discover all AWS resources |
| **security_audit.py** | Security vulnerability checks |
| **optimizer.py** | Cost optimization recommendations |
| **report_generator.py** | Generate HTML/MD/JSON reports |


---

## Multi-Region Pricing Support

The Cost Estimator module supports **accurate pricing for all major AWS regions**:

### Supported Regions with Exact Pricing

| Region Code | Region Name | Price vs us-east-1 |
|-------------|-------------|-------------------|
| us-east-1 | N. Virginia | Baseline |
| us-east-2 | Ohio | ~Same |
| us-west-1 | N. California | +8% |
| us-west-2 | Oregon | ~Same |
| eu-west-1 | Ireland | +5-8% |
| eu-west-2 | London | +8% |
| eu-central-1 | Frankfurt | +8% |
| ap-south-1 | Mumbai | +12-15% |
| ap-southeast-1 | Singapore | +15-18% |
| ap-southeast-2 | Sydney | +18% |
| ap-northeast-1 | Tokyo | +25-30% |
| ap-northeast-2 | Seoul | +20% |
| sa-east-1 | São Paulo | +50% |

### How It Works

1. **Auto-detection**: Region is automatically detected from your AWS session/profile
2. **Exact pricing**: Major regions (us-east-1, ap-south-1, eu-west-1, ap-northeast-1) have exact prices
3. **Multiplier fallback**: Other regions use us-east-1 prices with regional multipliers
4. **Services covered**: EC2, EBS, NAT Gateway, ALB/NLB/CLB, RDS, S3, Lambda, CloudFront, etc.

### Example Regional Pricing (same resources)

```
Region          | t3.micro + 100GB gp3 + NAT | vs Baseline
----------------|---------------------------|------------
us-east-1       | $177.04/month            | Baseline
ap-south-1      | $196.53/month            | +11%
eu-west-1       | $192.74/month            | +9%
ap-northeast-1  | $227.21/month            | +28%
```

### Usage

```bash
# Auto-detects region from profile
python main.py --profile my-mumbai-profile

# Explicit region
python main.py --region ap-south-1
```

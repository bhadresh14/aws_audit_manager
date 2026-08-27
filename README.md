# AWS Health Check Tool 🔍

A comprehensive Python tool for analyzing AWS infrastructure health, costs, security posture, and optimization opportunities.

## Features

### 💰 Cost Analysis
- Monthly cost breakdown by service
- Cost trends and forecasting
- Cost anomaly detection
- Top cost drivers analysis

### 🖥️ Resource Inventory
- Complete resource discovery across regions
- EC2, RDS, S3, Lambda, ECS, and more
- Detailed resource attributes and metadata

### 🔒 Security Audit
- Open security groups detection
- Public S3 bucket identification
- IAM best practices validation
- MFA enforcement checking
- Encryption status verification
- Unused credentials detection

### 📊 Optimization Recommendations
- Unused resource identification
- Rightsizing recommendations
- Reserved Instance opportunities
- Cost-saving actions with estimates

## Installation

### Prerequisites
- Python 3.8 or higher
- AWS CLI configured with valid credentials
- Appropriate IAM permissions

### Setup

```bash
# Clone or navigate to the project
cd aws-health-check

# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Basic Usage

```bash
# Run with default AWS credentials
python main.py

# Use specific AWS profile
python main.py --profile myprofile

# Scan specific region
python main.py --region ap-south-1

# Custom output directory
python main.py --output-dir ./my-reports

# Combine options
python main.py --profile prod-account --region us-east-1 --output-dir ./reports
```

### Command Line Options

| Option | Short | Description |
|--------|-------|-------------|
| `--profile` | `-p` | AWS profile name to use |
| `--region` | `-r` | AWS region to scan |
| `--output-dir` | `-o` | Output directory for reports |
| `--version` | `-v` | Show version information |
| `--help` | `-h` | Show help message |

## Output

The tool generates reports in multiple formats:

- **HTML** - Interactive, styled report for viewing in browser
- **Markdown** - Text-based report for documentation
- **JSON** - Machine-readable format for integration

Reports are saved to the `output/` directory by default.

## Required IAM Permissions

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ce:*",
                "ec2:Describe*",
                "rds:Describe*",
                "s3:GetBucket*",
                "s3:ListBucket*",
                "s3:ListAllMyBuckets",
                "lambda:List*",
                "ecs:Describe*",
                "ecs:List*",
                "elasticloadbalancing:Describe*",
                "cloudwatch:GetMetricStatistics",
                "cloudwatch:ListMetrics",
                "iam:Get*",
                "iam:List*",
                "iam:GenerateCredentialReport",
                "ecr:Describe*",
                "ecr:GetLifecyclePolicy",
                "cloudfront:List*",
                "secretsmanager:List*",
                "sts:GetCallerIdentity"
            ],
            "Resource": "*"
        }
    ]
}
```

## Project Structure

```
aws-health-check/
├── main.py                      # Main entry point
├── config.py                    # Configuration settings
├── requirements.txt             # Python dependencies
├── README.md                    # This file
├── ARCHITECTURE.md              # Architecture documentation
├── modules/
│   ├── __init__.py
│   ├── cost_analyzer.py         # Cost analysis module
│   ├── cost_estimator.py        # Multi-region cost estimation
│   ├── pricing_api.py           # Live AWS Pricing API
│   ├── cloudwatch_metrics.py    # CloudWatch metrics for usage
│   ├── resource_inventory.py    # Resource discovery module
│   ├── security_audit.py        # Security checks module
│   └── optimizer.py             # Optimization recommendations
├── reports/
│   ├── __init__.py
│   └── report_generator.py      # Report generation
├── dashboard/                   # Web Dashboard (FastAPI)
│   ├── __init__.py
│   ├── app.py                   # FastAPI application
│   └── templates/               # HTML templates
│       ├── base.html
│       ├── index.html
│       └── report.html
└── output/                      # Generated reports (created automatically)
```

## Web Dashboard

The tool includes a web dashboard for viewing reports in your browser.

### Starting the Dashboard

```bash
# Install dependencies (if not done)
pip install -r requirements.txt

# Start the dashboard
cd aws-health-check
uvicorn dashboard.app:app --reload --host 0.0.0.0 --port 8000

# Or run directly
python -m dashboard.app
```

### Dashboard Features

- 📊 **Report Listing** - View all health check reports
- 📈 **Interactive Charts** - Cost breakdown visualizations
- 🔍 **Report Details** - Drill down into security findings and recommendations
- 📥 **Download Reports** - Export in JSON, HTML, or Markdown
- 🔄 **Trigger Scans** - Start new health checks from the UI

### Dashboard URLs

| URL | Description |
|-----|-------------|
| `http://localhost:8000` | Dashboard home |
| `http://localhost:8000/report/{id}` | View specific report |
| `http://localhost:8000/api/reports` | JSON API - list reports |
| `http://localhost:8000/api/reports/{id}` | JSON API - get report |
| `http://localhost:8000/api/status` | Dashboard status |

### API Endpoints

```bash
# List all reports
curl http://localhost:8000/api/reports

# Get specific report
curl http://localhost:8000/api/reports/aws_health_check_20260807_094042

# Trigger new scan
curl -X POST "http://localhost:8000/api/scan?profile=myprofile&region=ap-south-1"
```

## Sample Output

```
============================================================
   AWS HEALTH CHECK TOOL
============================================================
   Account: 123456789012
   Region:  ap-south-1
   User:    arn:aws:iam::123456789012:user/admin
============================================================

💰 Running Cost Analysis...
  ├── Analyzing costs by service...
  │   └── Total: $1869.91 across 15 services
  ├── Analyzing costs by region...
  └── Generating recommendations...

🖥️  Running Resource Inventory...
  ├── Scanning region: ap-south-1
  └── Generating summary...

🔒 Running Security Audit...
  ├── Checking S3 bucket policies...
  ├── Checking IAM MFA status...
  └── Found 12 security findings

📊 Running Optimization Analysis...
  └── Found 8 optimization opportunities
      Potential monthly savings: $674.91

============================================================
   HEALTH CHECK COMPLETE
============================================================
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - feel free to use and modify for your needs.

## Author

Cloud Engineering Team

## Support

For issues or questions, please open a GitHub issue.

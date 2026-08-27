# Deployment Guide - AWS Health Check Dashboard

## Instance Details
- **Name:** AWS_Audit_Manager
- **Type:** t3.micro
- **IP:** 65.1.253.48
- **Region:** ap-south-1
- **OS:** Amazon Linux 2

---

## Step 1: Security Group

Make sure port **80** is open in the Security Group:

| Type | Port | Source |
|------|------|--------|
| HTTP | 80 | 0.0.0.0/0 (or your IP) |
| SSH  | 22 | Your IP |

---

## Step 2: IAM Role (Important!)

Attach an IAM role to the EC2 instance with these permissions:
- `ce:*` (Cost Explorer)
- `ec2:Describe*`
- `rds:Describe*`
- `s3:List*`, `s3:GetBucket*`
- `lambda:List*`, `lambda:GetFunction`
- `elasticloadbalancing:Describe*`
- `cloudwatch:GetMetricData`, `cloudwatch:ListMetrics`
- `iam:List*`, `iam:GetAccountAuthorizationDetails`
- `sts:GetCallerIdentity`

This way the app uses the instance role — no credentials stored on disk.

---

## Step 3: Copy Files to EC2

From your local machine (PowerShell):

```powershell
# Copy the entire project to EC2
scp -i "your-key.pem" -r "C:\Users\LOTUS IT SOLUTION\Desktop\Cargodham\aws-health-check" ec2-user@65.1.253.48:/opt/aws-health-check
```

Or use git:
```bash
# SSH into EC2 first
ssh -i "your-key.pem" ec2-user@65.1.253.48

# Clone from your repo
cd /opt
git clone <your-repo-url> aws-health-check
```

---

## Step 4: Run Setup Script

```bash
ssh -i "your-key.pem" ec2-user@65.1.253.48

cd /opt/aws-health-check
chmod +x deploy/setup.sh
./deploy/setup.sh
```

---

## Step 5: Verify

Open browser: **http://65.1.253.48**

---

## Useful Commands

```bash
# Check app status
sudo systemctl status aws-health-check

# View logs
sudo journalctl -u aws-health-check -f

# Restart app
sudo systemctl restart aws-health-check

# Restart nginx
sudo systemctl restart nginx

# Update app
cd /opt/aws-health-check
git pull
sudo systemctl restart aws-health-check
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| 502 Bad Gateway | App not running: `sudo systemctl start aws-health-check` |
| Connection refused | Security group missing port 80 |
| Scan fails | IAM role not attached or missing permissions |
| Profiles not loading | Configure profiles in `/home/ec2-user/.aws/credentials` |

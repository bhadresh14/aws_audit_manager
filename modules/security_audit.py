"""
AWS Health Check Tool - Security Audit Module
Performs comprehensive security checks on AWS resources
"""

import boto3
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SECURITY_CHECKS, CRITICAL_PORTS


class SecurityAudit:
    """Performs security audits on AWS resources"""
    
    SEVERITY_CRITICAL = "CRITICAL"
    SEVERITY_HIGH = "HIGH"
    SEVERITY_MEDIUM = "MEDIUM"
    SEVERITY_LOW = "LOW"
    SEVERITY_INFO = "INFO"
    
    def __init__(self, session: Optional[boto3.Session] = None, regions: List[str] = None):
        self.session = session or boto3.Session()
        self.regions = regions or [self.session.region_name or 'us-east-1']
        self.findings = []
        self.summary = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "info": 0,
            "total": 0
        }
    
    def run_all_checks(self) -> Dict[str, Any]:
        """Run all security checks"""
        print("🔒 Running Security Audit...")
        
        # Regional checks
        for region in self.regions:
            print(f"  ├── Scanning region: {region}")
            self._check_open_security_groups(region)
            self._check_unencrypted_ebs(region)
            self._check_unencrypted_rds(region)
            self._check_public_rds(region)
            self._check_default_vpc_usage(region)
            self._check_public_ec2_instances(region)
        
        # Global checks
        print("  ├── Running global security checks...")
        self._check_public_s3_buckets()
        self._check_iam_users_without_mfa()
        self._check_root_account_usage()
        self._check_unused_iam_credentials()
        self._check_iam_password_policy()
        self._check_access_keys_rotation()
        
        self._update_summary()
        
        return {
            "findings": self.findings,
            "summary": self.summary
        }
    
    def _add_finding(self, severity: str, category: str, title: str, 
                     description: str, resource: str, region: str = "global",
                     recommendation: str = ""):
        """Add a security finding"""
        self.findings.append({
            "severity": severity,
            "category": category,
            "title": title,
            "description": description,
            "resource": resource,
            "region": region,
            "recommendation": recommendation,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def _check_open_security_groups(self, region: str):
        """Check for security groups with dangerous open ports"""
        try:
            ec2 = self.session.client('ec2', region_name=region)
            paginator = ec2.get_paginator('describe_security_groups')
            
            for page in paginator.paginate():
                for sg in page['SecurityGroups']:
                    sg_id = sg['GroupId']
                    sg_name = sg['GroupName']
                    
                    for rule in sg.get('IpPermissions', []):
                        # Check for 0.0.0.0/0 access
                        for ip_range in rule.get('IpRanges', []):
                            if ip_range.get('CidrIp') == '0.0.0.0/0':
                                from_port = rule.get('FromPort', 0)
                                to_port = rule.get('ToPort', 65535)
                                protocol = rule.get('IpProtocol', '-1')
                                
                                # All traffic open
                                if protocol == '-1':
                                    self._add_finding(
                                        self.SEVERITY_CRITICAL,
                                        "Network Security",
                                        "Security Group Open to All Traffic",
                                        f"Security group {sg_name} ({sg_id}) allows ALL inbound traffic from 0.0.0.0/0",
                                        sg_id,
                                        region,
                                        "Restrict inbound rules to specific IPs and ports"
                                    )
                                # Critical ports open
                                elif from_port and to_port:
                                    for port, service in CRITICAL_PORTS.items():
                                        if from_port <= port <= to_port:
                                            severity = self.SEVERITY_CRITICAL if port in [22, 3389, 3306, 5432] else self.SEVERITY_HIGH
                                            self._add_finding(
                                                severity,
                                                "Network Security",
                                                f"{service} Port Open to Internet",
                                                f"Security group {sg_name} ({sg_id}) allows {service} (port {port}) from 0.0.0.0/0",
                                                sg_id,
                                                region,
                                                f"Restrict {service} access to specific IP addresses"
                                            )
                        
                        # Check for ::/0 (IPv6)
                        for ip_range in rule.get('Ipv6Ranges', []):
                            if ip_range.get('CidrIpv6') == '::/0':
                                from_port = rule.get('FromPort', 0)
                                to_port = rule.get('ToPort', 65535)
                                
                                for port, service in CRITICAL_PORTS.items():
                                    if from_port and to_port and from_port <= port <= to_port:
                                        self._add_finding(
                                            self.SEVERITY_HIGH,
                                            "Network Security",
                                            f"{service} Port Open to Internet (IPv6)",
                                            f"Security group {sg_name} ({sg_id}) allows {service} (port {port}) from ::/0",
                                            sg_id,
                                            region,
                                            f"Restrict {service} access to specific IP addresses"
                                        )
        except Exception as e:
            print(f"  │   └── SG Check Error: {str(e)[:50]}")
    
    def _check_public_s3_buckets(self):
        """Check for public S3 buckets"""
        print("  │   ├── Checking S3 bucket policies...")
        try:
            s3 = self.session.client('s3')
            buckets = s3.list_buckets().get('Buckets', [])
            max_buckets = 30  # Limit to avoid long-running scans
            
            for i, bucket in enumerate(buckets):
                if i >= max_buckets:
                    print(f"  │   │   └── Checked {max_buckets} of {len(buckets)} buckets (limit)")
                    break
                    
                bucket_name = bucket['Name']
                
                # Check public access block
                try:
                    public_access = s3.get_public_access_block(Bucket=bucket_name)
                    config = public_access.get('PublicAccessBlockConfiguration', {})
                    
                    if not all([
                        config.get('BlockPublicAcls', False),
                        config.get('IgnorePublicAcls', False),
                        config.get('BlockPublicPolicy', False),
                        config.get('RestrictPublicBuckets', False)
                    ]):
                        self._add_finding(
                            self.SEVERITY_MEDIUM,
                            "Data Security",
                            "S3 Bucket Missing Full Public Access Block",
                            f"Bucket {bucket_name} does not have all public access blocks enabled",
                            bucket_name,
                            "global",
                            "Enable all public access block settings"
                        )
                except s3.exceptions.NoSuchPublicAccessBlockConfiguration:
                    self._add_finding(
                        self.SEVERITY_HIGH,
                        "Data Security",
                        "S3 Bucket Has No Public Access Block",
                        f"Bucket {bucket_name} has no public access block configuration",
                        bucket_name,
                        "global",
                        "Enable public access block for the bucket"
                    )
                except Exception:
                    pass
                
                # Check bucket ACL
                try:
                    acl = s3.get_bucket_acl(Bucket=bucket_name)
                    for grant in acl.get('Grants', []):
                        grantee = grant.get('Grantee', {})
                        if grantee.get('URI') in [
                            'http://acs.amazonaws.com/groups/global/AllUsers',
                            'http://acs.amazonaws.com/groups/global/AuthenticatedUsers'
                        ]:
                            self._add_finding(
                                self.SEVERITY_CRITICAL,
                                "Data Security",
                                "S3 Bucket is Publicly Accessible via ACL",
                                f"Bucket {bucket_name} grants access to AllUsers or AuthenticatedUsers",
                                bucket_name,
                                "global",
                                "Remove public ACL grants immediately"
                            )
                except Exception:
                    pass
                
        except Exception as e:
            print(f"  │   └── S3 Check Error: {str(e)[:50]}")
    
    def _check_iam_users_without_mfa(self):
        """Check for IAM users without MFA enabled"""
        print("  │   ├── Checking IAM MFA status...")
        try:
            iam = self.session.client('iam')
            paginator = iam.get_paginator('list_users')
            
            for page in paginator.paginate():
                for user in page['Users']:
                    username = user['UserName']
                    
                    # Check if user has MFA
                    mfa_devices = iam.list_mfa_devices(UserName=username)
                    if not mfa_devices.get('MFADevices'):
                        # Check if user has console access
                        try:
                            iam.get_login_profile(UserName=username)
                            # User has console access but no MFA
                            self._add_finding(
                                self.SEVERITY_HIGH,
                                "Identity & Access",
                                "IAM User Without MFA",
                                f"IAM user {username} has console access but no MFA enabled",
                                username,
                                "global",
                                "Enable MFA for all users with console access"
                            )
                        except iam.exceptions.NoSuchEntityException:
                            # No console access, lower severity
                            pass
        except Exception as e:
            print(f"  │   └── IAM MFA Check Error: {str(e)[:50]}")
    
    def _check_root_account_usage(self):
        """Check for recent root account usage"""
        print("  │   ├── Checking root account usage...")
        try:
            iam = self.session.client('iam')
            summary = iam.get_account_summary()
            
            # Check if root has access keys
            if summary['SummaryMap'].get('AccountAccessKeysPresent', 0) > 0:
                self._add_finding(
                    self.SEVERITY_CRITICAL,
                    "Identity & Access",
                    "Root Account Has Access Keys",
                    "The root account has active access keys. This is a critical security risk.",
                    "root-account",
                    "global",
                    "Delete root account access keys immediately"
                )
            
            # Check root MFA
            if summary['SummaryMap'].get('AccountMFAEnabled', 0) == 0:
                self._add_finding(
                    self.SEVERITY_CRITICAL,
                    "Identity & Access",
                    "Root Account MFA Not Enabled",
                    "MFA is not enabled for the root account",
                    "root-account",
                    "global",
                    "Enable MFA for root account immediately"
                )
        except Exception as e:
            print(f"  │   └── Root Check Error: {str(e)[:50]}")
    
    def _check_unused_iam_credentials(self):
        """Check for unused IAM credentials"""
        print("  │   ├── Checking unused credentials...")
        try:
            iam = self.session.client('iam')
            
            # Generate credential report
            try:
                iam.generate_credential_report()
            except:
                pass
            
            # Get credential report
            import time
            for _ in range(5):
                try:
                    response = iam.get_credential_report()
                    break
                except iam.exceptions.CredentialReportNotReadyException:
                    time.sleep(2)
            else:
                return
            
            import csv
            from io import StringIO
            
            report = response['Content'].decode('utf-8')
            reader = csv.DictReader(StringIO(report))
            
            threshold = datetime.utcnow() - timedelta(days=90)
            
            for row in reader:
                user = row['user']
                if user == '<root_account>':
                    continue
                
                # Check password last used
                password_last_used = row.get('password_last_used', 'N/A')
                if password_last_used not in ['N/A', 'no_information', 'not_supported']:
                    try:
                        last_used = datetime.strptime(password_last_used.split('T')[0], '%Y-%m-%d')
                        if last_used < threshold:
                            self._add_finding(
                                self.SEVERITY_MEDIUM,
                                "Identity & Access",
                                "Unused IAM Password",
                                f"User {user} has not used their password in over 90 days",
                                user,
                                "global",
                                "Consider disabling or removing unused credentials"
                            )
                    except:
                        pass
                
                # Check access keys
                for key_num in ['1', '2']:
                    key_active = row.get(f'access_key_{key_num}_active', 'false')
                    if key_active == 'true':
                        key_last_used = row.get(f'access_key_{key_num}_last_used_date', 'N/A')
                        if key_last_used not in ['N/A', 'no_information']:
                            try:
                                last_used = datetime.strptime(key_last_used.split('T')[0], '%Y-%m-%d')
                                if last_used < threshold:
                                    self._add_finding(
                                        self.SEVERITY_MEDIUM,
                                        "Identity & Access",
                                        "Unused Access Key",
                                        f"User {user} access key {key_num} not used in over 90 days",
                                        user,
                                        "global",
                                        "Rotate or delete unused access keys"
                                    )
                            except:
                                pass
        except Exception as e:
            print(f"  │   └── Credentials Check Error: {str(e)[:50]}")
    
    def _check_iam_password_policy(self):
        """Check IAM password policy"""
        print("  │   ├── Checking password policy...")
        try:
            iam = self.session.client('iam')
            
            try:
                policy = iam.get_account_password_policy()['PasswordPolicy']
                
                issues = []
                if policy.get('MinimumPasswordLength', 0) < 14:
                    issues.append("minimum length < 14")
                if not policy.get('RequireSymbols', False):
                    issues.append("symbols not required")
                if not policy.get('RequireNumbers', False):
                    issues.append("numbers not required")
                if not policy.get('RequireUppercaseCharacters', False):
                    issues.append("uppercase not required")
                if not policy.get('RequireLowercaseCharacters', False):
                    issues.append("lowercase not required")
                if policy.get('MaxPasswordAge', 0) == 0 or policy.get('MaxPasswordAge', 999) > 90:
                    issues.append("password expiry > 90 days or disabled")
                
                if issues:
                    self._add_finding(
                        self.SEVERITY_MEDIUM,
                        "Identity & Access",
                        "Weak Password Policy",
                        f"Password policy issues: {', '.join(issues)}",
                        "password-policy",
                        "global",
                        "Strengthen password policy requirements"
                    )
            except iam.exceptions.NoSuchEntityException:
                self._add_finding(
                    self.SEVERITY_HIGH,
                    "Identity & Access",
                    "No Password Policy Configured",
                    "No custom password policy is configured for the account",
                    "password-policy",
                    "global",
                    "Configure a strong password policy"
                )
        except Exception as e:
            print(f"  │   └── Password Policy Check Error: {str(e)[:50]}")
    
    def _check_access_keys_rotation(self):
        """Check for old access keys that need rotation"""
        print("  │   ├── Checking access key age...")
        try:
            iam = self.session.client('iam')
            paginator = iam.get_paginator('list_users')
            
            threshold = datetime.utcnow() - timedelta(days=90)
            users_checked = 0
            max_users = 50  # Limit to avoid long-running scans
            
            for page in paginator.paginate():
                for user in page['Users']:
                    if users_checked >= max_users:
                        print(f"  │   │   └── Checked {max_users} users (limit reached)")
                        return
                    
                    username = user['UserName']
                    users_checked += 1
                    
                    try:
                        keys = iam.list_access_keys(UserName=username)
                        for key in keys.get('AccessKeyMetadata', []):
                            if key['Status'] == 'Active':
                                create_date = key['CreateDate'].replace(tzinfo=None)
                                if create_date < threshold:
                                    age_days = (datetime.utcnow() - create_date).days
                                    self._add_finding(
                                        self.SEVERITY_MEDIUM,
                                        "Identity & Access",
                                        "Access Key Needs Rotation",
                                        f"User {username} has access key {key['AccessKeyId'][:8]}... that is {age_days} days old",
                                        username,
                                        "global",
                                        "Rotate access keys at least every 90 days"
                                    )
                    except Exception:
                        continue
        except Exception as e:
            print(f"  │   └── Key Rotation Check Error: {str(e)[:50]}")
    
    def _check_unencrypted_ebs(self, region: str):
        """Check for unencrypted EBS volumes"""
        try:
            ec2 = self.session.client('ec2', region_name=region)
            paginator = ec2.get_paginator('describe_volumes')
            
            for page in paginator.paginate():
                for volume in page['Volumes']:
                    if not volume.get('Encrypted', False):
                        self._add_finding(
                            self.SEVERITY_MEDIUM,
                            "Data Security",
                            "Unencrypted EBS Volume",
                            f"EBS volume {volume['VolumeId']} ({volume['Size']} GB) is not encrypted",
                            volume['VolumeId'],
                            region,
                            "Enable encryption for EBS volumes"
                        )
        except Exception as e:
            print(f"  │   └── EBS Encryption Check Error: {str(e)[:50]}")
    
    def _check_unencrypted_rds(self, region: str):
        """Check for unencrypted RDS instances"""
        try:
            rds = self.session.client('rds', region_name=region)
            paginator = rds.get_paginator('describe_db_instances')
            
            for page in paginator.paginate():
                for db in page['DBInstances']:
                    if not db.get('StorageEncrypted', False):
                        self._add_finding(
                            self.SEVERITY_HIGH,
                            "Data Security",
                            "Unencrypted RDS Instance",
                            f"RDS instance {db['DBInstanceIdentifier']} is not encrypted",
                            db['DBInstanceIdentifier'],
                            region,
                            "Enable encryption for RDS instances"
                        )
        except Exception as e:
            print(f"  │   └── RDS Encryption Check Error: {str(e)[:50]}")
    
    def _check_public_rds(self, region: str):
        """Check for publicly accessible RDS instances"""
        try:
            rds = self.session.client('rds', region_name=region)
            paginator = rds.get_paginator('describe_db_instances')
            
            for page in paginator.paginate():
                for db in page['DBInstances']:
                    if db.get('PubliclyAccessible', False):
                        self._add_finding(
                            self.SEVERITY_CRITICAL,
                            "Network Security",
                            "Publicly Accessible RDS Instance",
                            f"RDS instance {db['DBInstanceIdentifier']} is publicly accessible",
                            db['DBInstanceIdentifier'],
                            region,
                            "Disable public accessibility for RDS instances"
                        )
        except Exception as e:
            print(f"  │   └── RDS Public Check Error: {str(e)[:50]}")
    
    def _check_default_vpc_usage(self, region: str):
        """Check for resources in default VPC"""
        try:
            ec2 = self.session.client('ec2', region_name=region)
            
            # Find default VPC
            vpcs = ec2.describe_vpcs(Filters=[{'Name': 'is-default', 'Values': ['true']}])
            
            for vpc in vpcs.get('Vpcs', []):
                default_vpc_id = vpc['VpcId']
                
                # Check for instances in default VPC
                instances = ec2.describe_instances(
                    Filters=[{'Name': 'vpc-id', 'Values': [default_vpc_id]}]
                )
                
                instance_count = sum(
                    len(r['Instances']) 
                    for r in instances.get('Reservations', [])
                )
                
                if instance_count > 0:
                    self._add_finding(
                        self.SEVERITY_LOW,
                        "Architecture",
                        "Resources in Default VPC",
                        f"{instance_count} EC2 instances found in default VPC {default_vpc_id}",
                        default_vpc_id,
                        region,
                        "Consider using custom VPCs for better network isolation"
                    )
        except Exception as e:
            print(f"  │   └── Default VPC Check Error: {str(e)[:50]}")
    
    def _check_public_ec2_instances(self, region: str):
        """Check for EC2 instances with public IPs"""
        try:
            ec2 = self.session.client('ec2', region_name=region)
            paginator = ec2.get_paginator('describe_instances')
            
            for page in paginator.paginate():
                for reservation in page['Reservations']:
                    for instance in reservation['Instances']:
                        if instance['State']['Name'] != 'running':
                            continue
                        
                        if instance.get('PublicIpAddress'):
                            name = ''
                            for tag in instance.get('Tags', []):
                                if tag['Key'] == 'Name':
                                    name = tag['Value']
                                    break
                            
                            self._add_finding(
                                self.SEVERITY_INFO,
                                "Network Security",
                                "EC2 Instance with Public IP",
                                f"Instance {instance['InstanceId']} ({name}) has public IP {instance['PublicIpAddress']}",
                                instance['InstanceId'],
                                region,
                                "Review if public IP is necessary; consider using NAT Gateway"
                            )
        except Exception as e:
            print(f"  │   └── Public EC2 Check Error: {str(e)[:50]}")
    
    def _update_summary(self):
        """Update findings summary"""
        print("  └── Generating security summary...")
        
        for finding in self.findings:
            severity = finding['severity'].lower()
            if severity in self.summary:
                self.summary[severity] += 1
        
        self.summary['total'] = len(self.findings)
        
        print(f"      └── Found {self.summary['total']} security findings")
        print(f"          Critical: {self.summary['critical']}, High: {self.summary['high']}, Medium: {self.summary['medium']}, Low: {self.summary['low']}")
    
    def get_findings_by_severity(self, severity: str) -> List[Dict]:
        """Get findings filtered by severity"""
        return [f for f in self.findings if f['severity'] == severity]
    
    def get_findings_by_category(self, category: str) -> List[Dict]:
        """Get findings filtered by category"""
        return [f for f in self.findings if f['category'] == category]


if __name__ == "__main__":
    audit = SecurityAudit()
    results = audit.run_all_checks()
    
    print("\n" + "="*50)
    print("SECURITY AUDIT SUMMARY")
    print("="*50)
    print(f"Total Findings: {results['summary']['total']}")
    print(f"  Critical: {results['summary']['critical']}")
    print(f"  High: {results['summary']['high']}")
    print(f"  Medium: {results['summary']['medium']}")
    print(f"  Low: {results['summary']['low']}")

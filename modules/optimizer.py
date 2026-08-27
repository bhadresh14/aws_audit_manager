"""
AWS Health Check Tool - Optimizer Module
Identifies cost optimization opportunities and provides recommendations
"""

import boto3
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OPTIMIZATION_THRESHOLDS


class Optimizer:
    """Identifies optimization opportunities across AWS resources"""
    
    def __init__(self, session: Optional[boto3.Session] = None, regions: List[str] = None):
        self.session = session or boto3.Session()
        self.regions = regions or [self.session.region_name or 'us-east-1']
        self.recommendations = []
        self.summary = {
            "total_recommendations": 0,
            "potential_monthly_savings": 0,
            "by_category": {}
        }
    
    def run_all_checks(self) -> Dict[str, Any]:
        """Run all optimization checks"""
        print("📊 Running Optimization Analysis...")
        
        # Regional checks
        for region in self.regions:
            print(f"  ├── Analyzing region: {region}")
            self._check_unused_ebs_volumes(region)
            self._check_unused_elastic_ips(region)
            self._check_idle_ec2_instances(region)
            self._check_old_snapshots(region)
            self._check_old_amis(region)
            self._check_underutilized_rds(region)
            self._check_nat_gateway_optimization(region)
            self._check_ecs_optimization(region)
            self._check_ebs_optimization(region)
        
        # Global checks
        print("  ├── Running global optimization checks...")
        self._check_ecr_image_cleanup()
        self._check_s3_lifecycle_policies()
        self._check_reserved_instances()
        self._check_savings_plans()
        
        self._update_summary()
        
        return {
            "recommendations": self.recommendations,
            "summary": self.summary
        }
    
    def _add_recommendation(self, category: str, title: str, description: str,
                           resource: str, region: str, estimated_savings: float,
                           effort: str = "Low", risk: str = "Low", action: str = ""):
        """Add an optimization recommendation"""
        self.recommendations.append({
            "category": category,
            "title": title,
            "description": description,
            "resource": resource,
            "region": region,
            "estimated_monthly_savings": estimated_savings,
            "effort": effort,  # Low, Medium, High
            "risk": risk,      # Low, Medium, High
            "action": action,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def _check_unused_ebs_volumes(self, region: str):
        """Check for unattached EBS volumes"""
        try:
            ec2 = self.session.client('ec2', region_name=region)
            paginator = ec2.get_paginator('describe_volumes')
            
            for page in paginator.paginate(Filters=[{'Name': 'status', 'Values': ['available']}]):
                for volume in page['Volumes']:
                    size_gb = volume['Size']
                    volume_type = volume['VolumeType']
                    vol_id = volume['VolumeId']
                    
                    # Get name tag
                    name = ''
                    for tag in volume.get('Tags', []):
                        if tag['Key'] == 'Name':
                            name = tag['Value']
                            break
                    
                    cost_per_gb = {
                        'gp2': 0.10, 'gp3': 0.08, 'io1': 0.125,
                        'io2': 0.125, 'st1': 0.045, 'sc1': 0.025
                    }
                    monthly_cost = size_gb * cost_per_gb.get(volume_type, 0.10)
                    
                    display_name = f"{name} ({vol_id})" if name else vol_id
                    
                    description = (
                        f"This disk '{display_name}' is not connected to any server.\n"
                        f"• Size: {size_gb} GB | Type: {volume_type}\n"
                        f"• You're paying ${monthly_cost:.2f}/month for storage nobody is using\n"
                        f"• This may be a leftover from a deleted server"
                    )
                    
                    action = (
                        f"If you don't need this data: Delete it to stop charges. "
                        f"If unsure: Take a snapshot (backup) first, then delete the disk."
                    )
                    
                    self._add_recommendation(
                        "Disk Storage (EBS)",
                        f"Unused disk: {display_name} ({size_gb} GB)",
                        description,
                        display_name,
                        region,
                        round(monthly_cost, 2),
                        "Low",
                        "Low",
                        action
                    )
        except Exception as e:
            print(f"  │   └── EBS Check Error: {str(e)[:50]}")
    
    def _check_unused_elastic_ips(self, region: str):
        """Check for unassociated Elastic IPs"""
        try:
            ec2 = self.session.client('ec2', region_name=region)
            addresses = ec2.describe_addresses()
            
            for eip in addresses.get('Addresses', []):
                if not eip.get('AssociationId'):
                    ip_addr = eip.get('PublicIp', 'Unknown')
                    alloc_id = eip.get('AllocationId', '')
                    
                    description = (
                        f"Elastic IP {ip_addr} is allocated but NOT attached to any server.\n"
                        f"• AWS charges $3.60/month ($0.005/hour) for unused IP addresses\n"
                        f"• This IP is costing you money without serving any purpose\n"
                        f"• If you don't need a fixed IP address, release it immediately"
                    )
                    
                    action = (
                        f"Release this IP: Go to AWS Console → EC2 → Elastic IPs → "
                        f"Select {ip_addr} → Actions → Release"
                    )
                    
                    self._add_recommendation(
                        "IP Addresses",
                        f"Unused IP Address: {ip_addr}",
                        description,
                        f"{ip_addr} ({alloc_id})",
                        region,
                        3.60,
                        "Low",
                        "Low",
                        action
                    )
        except Exception as e:
            print(f"  │   └── EIP Check Error: {str(e)[:50]}")
    
    def _check_idle_ec2_instances(self, region: str):
        """Check for idle/underutilized EC2 instances using CloudWatch"""
        try:
            ec2 = self.session.client('ec2', region_name=region)
            cloudwatch = self.session.client('cloudwatch', region_name=region)
            
            # Get running instances
            paginator = ec2.get_paginator('describe_instances')
            
            for page in paginator.paginate(Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]):
                for reservation in page['Reservations']:
                    for instance in reservation['Instances']:
                        instance_id = instance['InstanceId']
                        instance_type = instance['InstanceType']
                        
                        # Get CPU utilization for last 7 days
                        end_time = datetime.utcnow()
                        start_time = end_time - timedelta(days=7)
                        
                        try:
                            metrics = cloudwatch.get_metric_statistics(
                                Namespace='AWS/EC2',
                                MetricName='CPUUtilization',
                                Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                                StartTime=start_time,
                                EndTime=end_time,
                                Period=86400,  # 1 day
                                Statistics=['Average', 'Maximum']
                            )
                            
                            if metrics['Datapoints']:
                                avg_cpu = sum(d['Average'] for d in metrics['Datapoints']) / len(metrics['Datapoints'])
                                max_cpu = max(d.get('Maximum', d['Average']) for d in metrics['Datapoints'])
                                
                                if avg_cpu < OPTIMIZATION_THRESHOLDS['cpu_underutilized_percent']:
                                    name = ''
                                    for tag in instance.get('Tags', []):
                                        if tag['Key'] == 'Name':
                                            name = tag['Value']
                                            break
                                    
                                    # Get current instance specs and recommend downgrade
                                    current_hourly = self._get_instance_hourly_cost(instance_type, region)
                                    current_monthly = current_hourly * 730
                                    recommended_type = self._get_downgrade_recommendation(instance_type, avg_cpu, max_cpu)
                                    recommended_hourly = self._get_instance_hourly_cost(recommended_type, region)
                                    recommended_monthly = recommended_hourly * 730
                                    potential_savings = current_monthly - recommended_monthly
                                    
                                    # Skip if no actual savings (bad recommendation)
                                    if potential_savings <= 0:
                                        continue
                                    
                                    # Get instance specs for display
                                    current_specs = self._get_instance_specs(instance_type)
                                    recommended_specs = self._get_instance_specs(recommended_type)
                                    
                                    display_name = f"{name} ({instance_id})" if name else instance_id
                                    
                                    description = (
                                        f"This server '{display_name}' is barely being used.\n"
                                        f"• Current usage: Only {avg_cpu:.1f}% average CPU (peak: {max_cpu:.1f}%) over 7 days\n"
                                        f"• You're paying for: {instance_type} ({current_specs}) — ${current_monthly:.2f}/month\n"
                                        f"• You only need: {recommended_type} ({recommended_specs}) — ${recommended_monthly:.2f}/month\n"
                                        f"• You'll save: ${potential_savings:.2f}/month (${potential_savings*12:.0f}/year)"
                                    )
                                    
                                    action = (
                                        f"Switch from {instance_type} to {recommended_type}. "
                                        f"How: Stop the server → Change type to {recommended_type} → Start it again. "
                                        f"No data is lost. Takes about 2 minutes."
                                    )
                                    
                                    self._add_recommendation(
                                        "Servers (EC2)",
                                        f"Downsize server: {instance_type} → {recommended_type}",
                                        description,
                                        display_name,
                                        region,
                                        round(potential_savings, 2),
                                        "Medium",
                                        "Low",
                                        action
                                    )
                        except Exception:
                            pass
        except Exception as e:
            print(f"  │   └── EC2 Idle Check Error: {str(e)[:50]}")
    
    def _get_downgrade_recommendation(self, current_type: str, avg_cpu: float, max_cpu: float) -> str:
        """Suggest a smaller instance type based on usage"""
        # Parse current instance family and size
        parts = current_type.split('.')
        family = parts[0]  # e.g., 't3', 'c5', 'm5'
        size = parts[1]    # e.g., 'xlarge', '2xlarge'
        
        # Size hierarchy for downsizing
        size_ladder = ['nano', 'micro', 'small', 'medium', 'large', 'xlarge', '2xlarge', '4xlarge', '8xlarge', '12xlarge', '16xlarge', '24xlarge']
        
        try:
            current_idx = size_ladder.index(size)
        except ValueError:
            current_idx = 4  # default to 'large'
        
        # Determine how many steps to downgrade
        if avg_cpu < 2 and max_cpu < 10:
            steps_down = 2  # Very idle — go down 2 sizes
        elif avg_cpu < 5:
            steps_down = 2
        else:
            steps_down = 1  # Slightly underutilized — go down 1 size
        
        new_idx = max(0, current_idx - steps_down)
        recommended_size = size_ladder[new_idx]
        
        # Prefer newer generation if possible
        family_upgrades = {
            't2': 't3', 't3': 't3', 't3a': 't3a',
            'c4': 'c5', 'c5': 'c6i', 'c6i': 'c6i',
            'm4': 'm5', 'm5': 'm6i', 'm6i': 'm6i',
            'r4': 'r5', 'r5': 'r6i', 'r6i': 'r6i',
        }
        recommended_family = family_upgrades.get(family, family)
        
        return f"{recommended_family}.{recommended_size}"
    
    def _get_instance_specs(self, instance_type: str) -> str:
        """Get human-readable specs for an instance type"""
        specs = {
            't2.nano': '1 vCPU, 0.5 GB RAM',
            't2.micro': '1 vCPU, 1 GB RAM',
            't2.small': '1 vCPU, 2 GB RAM',
            't2.medium': '2 vCPU, 4 GB RAM',
            't2.large': '2 vCPU, 8 GB RAM',
            't2.xlarge': '4 vCPU, 16 GB RAM',
            't2.2xlarge': '8 vCPU, 32 GB RAM',
            't3.nano': '2 vCPU, 0.5 GB RAM',
            't3.micro': '2 vCPU, 1 GB RAM',
            't3.small': '2 vCPU, 2 GB RAM',
            't3.medium': '2 vCPU, 4 GB RAM',
            't3.large': '2 vCPU, 8 GB RAM',
            't3.xlarge': '4 vCPU, 16 GB RAM',
            't3.2xlarge': '8 vCPU, 32 GB RAM',
            't3a.nano': '2 vCPU, 0.5 GB RAM',
            't3a.micro': '2 vCPU, 1 GB RAM',
            't3a.small': '2 vCPU, 2 GB RAM',
            't3a.medium': '2 vCPU, 4 GB RAM',
            't3a.large': '2 vCPU, 8 GB RAM',
            't3a.xlarge': '4 vCPU, 16 GB RAM',
            'm5.large': '2 vCPU, 8 GB RAM',
            'm5.xlarge': '4 vCPU, 16 GB RAM',
            'm5.2xlarge': '8 vCPU, 32 GB RAM',
            'm5.4xlarge': '16 vCPU, 64 GB RAM',
            'm5a.small': '1 vCPU, 4 GB RAM',
            'm5a.medium': '1 vCPU, 4 GB RAM',
            'm5a.large': '2 vCPU, 8 GB RAM',
            'm5a.xlarge': '4 vCPU, 16 GB RAM',
            'm5a.2xlarge': '8 vCPU, 32 GB RAM',
            'm5a.4xlarge': '16 vCPU, 64 GB RAM',
            'm6i.large': '2 vCPU, 8 GB RAM',
            'm6i.xlarge': '4 vCPU, 16 GB RAM',
            'm6i.2xlarge': '8 vCPU, 32 GB RAM',
            'c5.large': '2 vCPU, 4 GB RAM',
            'c5.xlarge': '4 vCPU, 8 GB RAM',
            'c5.2xlarge': '8 vCPU, 16 GB RAM',
            'c5.4xlarge': '16 vCPU, 32 GB RAM',
            'c6i.large': '2 vCPU, 4 GB RAM',
            'c6i.xlarge': '4 vCPU, 8 GB RAM',
            'c6i.2xlarge': '8 vCPU, 16 GB RAM',
            'r5.large': '2 vCPU, 16 GB RAM',
            'r5.xlarge': '4 vCPU, 32 GB RAM',
            'r5.2xlarge': '8 vCPU, 64 GB RAM',
            'r6i.large': '2 vCPU, 16 GB RAM',
            'r6i.xlarge': '4 vCPU, 32 GB RAM',
        }
        return specs.get(instance_type, self._estimate_specs(instance_type))
    
    def _estimate_specs(self, instance_type: str) -> str:
        """Estimate specs from instance type name"""
        size_specs = {
            'nano': '1 vCPU, 0.5 GB', 'micro': '1-2 vCPU, 1 GB',
            'small': '1-2 vCPU, 2 GB', 'medium': '2 vCPU, 4 GB',
            'large': '2 vCPU, 8 GB', 'xlarge': '4 vCPU, 16 GB',
            '2xlarge': '8 vCPU, 32 GB', '4xlarge': '16 vCPU, 64 GB',
            '8xlarge': '32 vCPU, 128 GB', '12xlarge': '48 vCPU, 192 GB',
        }
        parts = instance_type.split('.')
        size = parts[1] if len(parts) > 1 else 'medium'
        return size_specs.get(size, f'{size} size')
    
    def _check_old_snapshots(self, region: str):
        """Check for old EBS snapshots"""
        try:
            ec2 = self.session.client('ec2', region_name=region)
            account_id = self.session.client('sts').get_caller_identity()['Account']
            
            paginator = ec2.get_paginator('describe_snapshots')
            threshold_date = datetime.utcnow() - timedelta(days=OPTIMIZATION_THRESHOLDS['snapshot_age_days'])
            
            old_snapshots = []
            total_size = 0
            
            for page in paginator.paginate(OwnerIds=[account_id]):
                for snapshot in page['Snapshots']:
                    start_time = snapshot['StartTime'].replace(tzinfo=None)
                    if start_time < threshold_date:
                        old_snapshots.append(snapshot)
                        total_size += snapshot['VolumeSize']
            
            if old_snapshots:
                # ~$0.05 per GB-month for snapshots
                monthly_cost = total_size * 0.05
                
                self._add_recommendation(
                    "Storage",
                    "Old EBS Snapshots",
                    f"Found {len(old_snapshots)} snapshots older than {OPTIMIZATION_THRESHOLDS['snapshot_age_days']} days ({total_size} GB total)",
                    f"{len(old_snapshots)} snapshots",
                    region,
                    round(monthly_cost, 2),
                    "Medium",
                    "Medium",
                    "Review and delete unnecessary old snapshots"
                )
        except Exception as e:
            print(f"  │   └── Snapshot Check Error: {str(e)[:50]}")
    
    def _check_old_amis(self, region: str):
        """Check for old unused AMIs"""
        try:
            ec2 = self.session.client('ec2', region_name=region)
            account_id = self.session.client('sts').get_caller_identity()['Account']
            
            # Get all AMIs owned by account
            images = ec2.describe_images(Owners=[account_id])
            
            threshold_date = datetime.utcnow() - timedelta(days=OPTIMIZATION_THRESHOLDS['ami_age_days'])
            old_amis = []
            
            for image in images.get('Images', []):
                try:
                    creation_date = datetime.strptime(image['CreationDate'][:10], '%Y-%m-%d')
                    if creation_date < threshold_date:
                        old_amis.append(image)
                except:
                    pass
            
            if old_amis:
                self._add_recommendation(
                    "Storage",
                    "Old AMIs",
                    f"Found {len(old_amis)} AMIs older than {OPTIMIZATION_THRESHOLDS['ami_age_days']} days",
                    f"{len(old_amis)} AMIs",
                    region,
                    len(old_amis) * 1.0,  # Rough estimate
                    "Medium",
                    "Low",
                    "Review and deregister old unused AMIs"
                )
        except Exception as e:
            print(f"  │   └── AMI Check Error: {str(e)[:50]}")
    
    def _check_underutilized_rds(self, region: str):
        """Check for underutilized RDS instances"""
        try:
            rds = self.session.client('rds', region_name=region)
            cloudwatch = self.session.client('cloudwatch', region_name=region)
            
            paginator = rds.get_paginator('describe_db_instances')
            
            for page in paginator.paginate():
                for db in page['DBInstances']:
                    if db['DBInstanceStatus'] != 'available':
                        continue
                    
                    db_id = db['DBInstanceIdentifier']
                    
                    # Check CPU utilization
                    end_time = datetime.utcnow()
                    start_time = end_time - timedelta(days=7)
                    
                    try:
                        metrics = cloudwatch.get_metric_statistics(
                            Namespace='AWS/RDS',
                            MetricName='CPUUtilization',
                            Dimensions=[{'Name': 'DBInstanceIdentifier', 'Value': db_id}],
                            StartTime=start_time,
                            EndTime=end_time,
                            Period=86400,
                            Statistics=['Average']
                        )
                        
                        if metrics['Datapoints']:
                            avg_cpu = sum(d['Average'] for d in metrics['Datapoints']) / len(metrics['Datapoints'])
                            
                            if avg_cpu < 10:  # Less than 10% average CPU
                                self._add_recommendation(
                                    "Database",
                                    "Underutilized RDS Instance",
                                    f"RDS instance {db_id} ({db['DBInstanceClass']}) has {avg_cpu:.1f}% average CPU",
                                    db_id,
                                    region,
                                    20.0,  # Rough estimate
                                    "Medium",
                                    "Medium",
                                    "Consider downsizing or using Aurora Serverless"
                                )
                    except Exception:
                        pass
        except Exception as e:
            print(f"  │   └── RDS Check Error: {str(e)[:50]}")
    
    def _check_nat_gateway_optimization(self, region: str):
        """Check NAT Gateway usage and suggest VPC endpoints"""
        try:
            ec2 = self.session.client('ec2', region_name=region)
            
            nat_gateways = ec2.describe_nat_gateways(
                Filters=[{'Name': 'state', 'Values': ['available']}]
            )
            
            if nat_gateways.get('NatGateways'):
                # Check if VPC endpoints exist
                endpoints = ec2.describe_vpc_endpoints()
                endpoint_services = [e.get('ServiceName', '') for e in endpoints.get('VpcEndpoints', [])]
                
                missing_endpoints = []
                common_services = ['s3', 'dynamodb', 'ecr.api', 'ecr.dkr', 'logs', 'monitoring']
                
                for service in common_services:
                    if not any(service in ep for ep in endpoint_services):
                        missing_endpoints.append(service)
                
                if missing_endpoints:
                    self._add_recommendation(
                        "Networking",
                        "Missing VPC Endpoints",
                        f"NAT Gateway detected but missing VPC endpoints for: {', '.join(missing_endpoints)}. VPC endpoints can reduce NAT costs.",
                        "VPC Endpoints",
                        region,
                        50.0,  # Estimated savings
                        "Medium",
                        "Low",
                        "Create VPC endpoints for frequently used AWS services"
                    )
        except Exception as e:
            print(f"  │   └── NAT Check Error: {str(e)[:50]}")
    
    def _check_ecs_optimization(self, region: str):
        """Check ECS cluster optimization opportunities"""
        try:
            ecs = self.session.client('ecs', region_name=region)
            cloudwatch = self.session.client('cloudwatch', region_name=region)
            
            clusters = ecs.list_clusters()
            
            for cluster_arn in clusters.get('clusterArns', []):
                cluster_name = cluster_arn.split('/')[-1]
                
                # Get cluster utilization
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(days=7)
                
                try:
                    metrics = cloudwatch.get_metric_statistics(
                        Namespace='AWS/ECS',
                        MetricName='CPUUtilization',
                        Dimensions=[{'Name': 'ClusterName', 'Value': cluster_name}],
                        StartTime=start_time,
                        EndTime=end_time,
                        Period=86400,
                        Statistics=['Average']
                    )
                    
                    if metrics['Datapoints']:
                        avg_cpu = sum(d['Average'] for d in metrics['Datapoints']) / len(metrics['Datapoints'])
                        
                        if avg_cpu < 20:
                            # Get cluster details
                            details = ecs.describe_clusters(clusters=[cluster_arn])
                            cluster = details['clusters'][0] if details['clusters'] else {}
                            instance_count = cluster.get('registeredContainerInstancesCount', 0)
                            
                            if instance_count > 0:
                                self._add_recommendation(
                                    "Compute",
                                    "Underutilized ECS Cluster",
                                    f"ECS cluster {cluster_name} has {avg_cpu:.1f}% average CPU with {instance_count} instances",
                                    cluster_name,
                                    region,
                                    instance_count * 25.0,  # Rough estimate
                                    "Medium",
                                    "Medium",
                                    "Consider reducing task CPU reservations or instance count"
                                )
                except Exception:
                    pass
        except Exception as e:
            print(f"  │   └── ECS Check Error: {str(e)[:50]}")
    
    def _check_ebs_optimization(self, region: str):
        """Check for EBS volume type optimization opportunities"""
        try:
            ec2 = self.session.client('ec2', region_name=region)
            paginator = ec2.get_paginator('describe_volumes')
            
            gp2_volumes = []
            
            for page in paginator.paginate():
                for volume in page['Volumes']:
                    if volume['VolumeType'] == 'gp2':
                        gp2_volumes.append({
                            'id': volume['VolumeId'],
                            'size': volume['Size']
                        })
            
            if gp2_volumes:
                total_size = sum(v['size'] for v in gp2_volumes)
                # gp3 is typically 20% cheaper than gp2
                potential_savings = total_size * 0.10 * 0.20  # 20% of gp2 cost
                
                self._add_recommendation(
                    "Storage",
                    "EBS gp2 to gp3 Migration",
                    f"Found {len(gp2_volumes)} gp2 volumes ({total_size} GB). gp3 offers better price-performance.",
                    f"{len(gp2_volumes)} volumes",
                    region,
                    round(potential_savings, 2),
                    "Low",
                    "Low",
                    "Migrate gp2 volumes to gp3 for cost savings"
                )
        except Exception as e:
            print(f"  │   └── EBS Type Check Error: {str(e)[:50]}")
    
    def _check_ecr_image_cleanup(self):
        """Check for ECR repositories needing image cleanup"""
        print("  │   ├── Checking ECR image cleanup...")
        try:
            for region in self.regions:
                ecr = self.session.client('ecr', region_name=region)
                
                paginator = ecr.get_paginator('describe_repositories')
                
                for page in paginator.paginate():
                    for repo in page['repositories']:
                        repo_name = repo['repositoryName']
                        
                        # Get image count
                        try:
                            images = ecr.describe_images(repositoryName=repo_name)
                            image_count = len(images.get('imageDetails', []))
                            
                            if image_count > 20:
                                # Check for lifecycle policy
                                try:
                                    ecr.get_lifecycle_policy(repositoryName=repo_name)
                                except ecr.exceptions.LifecyclePolicyNotFoundException:
                                    self._add_recommendation(
                                        "Storage",
                                        "ECR Repository Without Lifecycle Policy",
                                        f"Repository {repo_name} has {image_count} images but no lifecycle policy",
                                        repo_name,
                                        region,
                                        image_count * 0.10,  # Rough estimate
                                        "Low",
                                        "Low",
                                        f"Add lifecycle policy: aws ecr put-lifecycle-policy --repository-name {repo_name}"
                                    )
                        except Exception:
                            pass
        except Exception as e:
            print(f"  │   └── ECR Check Error: {str(e)[:50]}")
    
    def _check_s3_lifecycle_policies(self):
        """Check for S3 buckets without lifecycle policies — uses actual bucket size for savings calc"""
        print("  │   ├── Checking S3 lifecycle policies...")
        try:
            s3 = self.session.client('s3')
            cloudwatch = self.session.client('cloudwatch', region_name='us-east-1')
            buckets = s3.list_buckets().get('Buckets', [])
            
            for bucket in buckets[:30]:  # Limit to avoid timeout
                bucket_name = bucket['Name']
                
                try:
                    s3.get_bucket_lifecycle_configuration(Bucket=bucket_name)
                except s3.exceptions.ClientError as e:
                    if 'NoSuchLifecycleConfiguration' in str(e):
                        # Get actual bucket size from CloudWatch
                        bucket_size_gb = self._get_s3_bucket_size_gb(cloudwatch, bucket_name)
                        
                        # Skip tiny buckets (< 1 GB) — not worth optimizing
                        if bucket_size_gb < 1.0:
                            continue
                        
                        # Calculate real savings:
                        # S3 Standard: $0.023/GB/month (ap-south-1: $0.025)
                        # S3 Glacier: $0.004/GB/month
                        # Assume 50% of data is old and can move to Glacier
                        # Savings = bucket_size * 50% * (standard_price - glacier_price)
                        standard_price = 0.025  # ap-south-1
                        glacier_price = 0.004
                        savings_per_gb = standard_price - glacier_price  # $0.021/GB
                        estimated_old_data_ratio = 0.50  # Assume 50% is old
                        potential_savings = bucket_size_gb * estimated_old_data_ratio * savings_per_gb
                        potential_savings = round(potential_savings, 2)
                        
                        # Only recommend if savings > $0.50/mo
                        if potential_savings < 0.50:
                            continue
                        
                        description = (
                            f"Storage bucket '{bucket_name}' has NO automatic cleanup rules.\n"
                            f"• Bucket size: {bucket_size_gb:.1f} GB\n"
                            f"• Current monthly storage cost: ~${bucket_size_gb * standard_price:.2f}/month\n"
                            f"• If 50% of data is older than 90 days, moving it to cheaper storage saves ~${potential_savings:.2f}/month\n"
                            f"• Lifecycle policies automate this — no manual work needed"
                        )
                        
                        action = (
                            f"Go to AWS Console → S3 → {bucket_name} → Management tab → "
                            f"Create lifecycle rule → Move to Glacier after 90 days"
                        )
                        
                        self._add_recommendation(
                            "File Storage (S3)",
                            f"No cleanup rules: {bucket_name} ({bucket_size_gb:.1f} GB)",
                            description,
                            bucket_name,
                            "global",
                            potential_savings,
                            "Low",
                            "Low",
                            action
                        )
        except Exception as e:
            print(f"  │   └── S3 Lifecycle Check Error: {str(e)[:50]}")
    
    def _get_s3_bucket_size_gb(self, cloudwatch, bucket_name: str) -> float:
        """Get S3 bucket size in GB from CloudWatch metrics"""
        try:
            from datetime import datetime, timedelta
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=3)
            
            response = cloudwatch.get_metric_statistics(
                Namespace='AWS/S3',
                MetricName='BucketSizeBytes',
                Dimensions=[
                    {'Name': 'BucketName', 'Value': bucket_name},
                    {'Name': 'StorageType', 'Value': 'StandardStorage'}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,
                Statistics=['Average']
            )
            
            datapoints = response.get('Datapoints', [])
            if datapoints:
                # Get the most recent datapoint
                latest = max(datapoints, key=lambda x: x['Timestamp'])
                size_bytes = latest['Average']
                return size_bytes / (1024 ** 3)  # Convert bytes to GB
        except Exception:
            pass
        
        return 0.0  # Unknown size
    
    def _check_reserved_instances(self):
        """Check Reserved Instance utilization and recommendations"""
        print("  │   ├── Checking Reserved Instance utilization...")
        try:
            ce = self.session.client('ce', region_name='us-east-1')
            
            # Get RI utilization
            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=30)
            
            try:
                response = ce.get_reservation_utilization(
                    TimePeriod={
                        'Start': start_date.strftime('%Y-%m-%d'),
                        'End': end_date.strftime('%Y-%m-%d')
                    },
                    Granularity='MONTHLY'
                )
                
                for result in response.get('UtilizationsByTime', []):
                    utilization = float(result.get('Total', {}).get('UtilizationPercentage', '100'))
                    
                    if utilization < 80:
                        self._add_recommendation(
                            "Commitments",
                            "Low Reserved Instance Utilization",
                            f"Reserved Instance utilization is {utilization:.1f}%. Consider modifying or selling unused RIs.",
                            "Reserved Instances",
                            "global",
                            50.0,  # Rough estimate
                            "Medium",
                            "Low",
                            "Review RI usage and consider modifications"
                        )
            except Exception:
                pass
            
            # Get RI recommendations
            try:
                recommendations = ce.get_reservation_purchase_recommendation(
                    Service='Amazon Elastic Compute Cloud - Compute',
                    LookbackPeriodInDays='SIXTY_DAYS',
                    TermInYears='ONE_YEAR',
                    PaymentOption='NO_UPFRONT'
                )
                
                for rec in recommendations.get('Recommendations', []):
                    estimated_savings = float(rec.get('RecommendationSummary', {}).get('TotalEstimatedMonthlySavingsAmount', 0))
                    
                    if estimated_savings > 50:
                        self._add_recommendation(
                            "Commitments",
                            "Reserved Instance Opportunity",
                            f"Purchasing Reserved Instances could save ~${estimated_savings:.0f}/month",
                            "EC2 Reserved Instances",
                            "global",
                            estimated_savings,
                            "Medium",
                            "Low",
                            "Review RI purchase recommendations in AWS Cost Explorer"
                        )
            except Exception:
                pass
        except Exception as e:
            print(f"  │   └── RI Check Error: {str(e)[:50]}")
    
    def _check_savings_plans(self):
        """Check Savings Plans recommendations"""
        print("  │   ├── Checking Savings Plans opportunities...")
        try:
            ce = self.session.client('ce', region_name='us-east-1')
            
            try:
                recommendations = ce.get_savings_plans_purchase_recommendation(
                    SavingsPlansType='COMPUTE_SP',
                    LookbackPeriodInDays='SIXTY_DAYS',
                    TermInYears='ONE_YEAR',
                    PaymentOption='NO_UPFRONT'
                )
                
                summary = recommendations.get('SavingsPlansPurchaseRecommendation', {}).get('SavingsPlansPurchaseRecommendationSummary', {})
                estimated_savings = float(summary.get('EstimatedMonthlySavingsAmount', 0))
                
                if estimated_savings > 50:
                    self._add_recommendation(
                        "Commitments",
                        "Savings Plans Opportunity",
                        f"Purchasing Savings Plans could save ~${estimated_savings:.0f}/month",
                        "Compute Savings Plans",
                        "global",
                        estimated_savings,
                        "Medium",
                        "Low",
                        "Review Savings Plans recommendations in AWS Cost Explorer"
                    )
            except Exception:
                pass
        except Exception as e:
            print(f"  │   └── Savings Plans Check Error: {str(e)[:50]}")
    
    def _get_instance_hourly_cost(self, instance_type: str, region: str) -> float:
        """
        Get EC2 instance hourly cost.
        Priority:
        1. AWS Pricing API (live, accurate, real-time)
        2. Hardcoded fallback table (for when API is unavailable)
        3. Size-based estimate (last resort)
        """
        # Try live pricing API first (most accurate)
        try:
            from modules.pricing_api import get_pricing_api
            pricing_api = get_pricing_api(self.session)
            live_price = pricing_api.get_ec2_price(instance_type, region)
            if live_price is not None and live_price > 0:
                return live_price
        except Exception:
            pass
        
        # Fallback: hardcoded ap-south-1 (Mumbai) pricing
        # Last verified: August 2026 from AWS official pricing page
        fallback_costs = {
            # T2 family
            't2.nano': 0.0065, 't2.micro': 0.0116, 't2.small': 0.023,
            't2.medium': 0.0464, 't2.large': 0.0928, 't2.xlarge': 0.1856,
            't2.2xlarge': 0.3712,
            # T3 family
            't3.nano': 0.0058, 't3.micro': 0.0116, 't3.small': 0.0232,
            't3.medium': 0.0464, 't3.large': 0.0928, 't3.xlarge': 0.1856,
            't3.2xlarge': 0.3712,
            # T3a family (AMD)
            't3a.nano': 0.0052, 't3a.micro': 0.0104, 't3a.small': 0.0209,
            't3a.medium': 0.0418, 't3a.large': 0.0835, 't3a.xlarge': 0.167,
            't3a.2xlarge': 0.334,
            # M5 family (General Purpose Intel)
            'm5.large': 0.107, 'm5.xlarge': 0.214, 'm5.2xlarge': 0.428,
            'm5.4xlarge': 0.856, 'm5.8xlarge': 1.712, 'm5.12xlarge': 2.568,
            'm5.16xlarge': 3.424, 'm5.24xlarge': 5.136,
            # M5a family (General Purpose AMD)
            'm5a.large': 0.096, 'm5a.xlarge': 0.192, 'm5a.2xlarge': 0.384,
            'm5a.4xlarge': 0.768, 'm5a.8xlarge': 1.536, 'm5a.12xlarge': 2.304,
            'm5a.16xlarge': 3.072, 'm5a.24xlarge': 4.608,
            # M5a small/medium (half of large)
            'm5a.small': 0.048,
            # M6i family
            'm6i.large': 0.107, 'm6i.xlarge': 0.214, 'm6i.2xlarge': 0.428,
            'm6i.4xlarge': 0.856, 'm6i.8xlarge': 1.712,
            # C5 family (Compute Optimized)
            'c5.large': 0.093, 'c5.xlarge': 0.186, 'c5.2xlarge': 0.372,
            'c5.4xlarge': 0.744, 'c5.9xlarge': 1.674, 'c5.12xlarge': 2.232,
            'c5.18xlarge': 3.348, 'c5.24xlarge': 4.464,
            # C5a family (Compute AMD)
            'c5a.large': 0.084, 'c5a.xlarge': 0.168, 'c5a.2xlarge': 0.336,
            'c5a.4xlarge': 0.672, 'c5a.8xlarge': 1.344,
            # C6i family
            'c6i.large': 0.093, 'c6i.xlarge': 0.186, 'c6i.2xlarge': 0.372,
            'c6i.4xlarge': 0.744, 'c6i.8xlarge': 1.488,
            # R5 family (Memory Optimized)
            'r5.large': 0.139, 'r5.xlarge': 0.278, 'r5.2xlarge': 0.556,
            'r5.4xlarge': 1.112, 'r5.8xlarge': 2.224, 'r5.12xlarge': 3.336,
            'r5.16xlarge': 4.448, 'r5.24xlarge': 6.672,
            # R5a family (Memory AMD)
            'r5a.large': 0.125, 'r5a.xlarge': 0.25, 'r5a.2xlarge': 0.5,
            'r5a.4xlarge': 1.0, 'r5a.8xlarge': 2.0,
            # R6i family
            'r6i.large': 0.139, 'r6i.xlarge': 0.278, 'r6i.2xlarge': 0.556,
            'r6i.4xlarge': 1.112, 'r6i.8xlarge': 2.224,
            # M4 family (older general purpose)
            'm4.large': 0.111, 'm4.xlarge': 0.222, 'm4.2xlarge': 0.444,
            'm4.4xlarge': 0.888, 'm4.10xlarge': 2.22,
            # C4 family (older compute)
            'c4.large': 0.11, 'c4.xlarge': 0.22, 'c4.2xlarge': 0.44,
            'c4.4xlarge': 0.88, 'c4.8xlarge': 1.76,
            # I3 family (Storage Optimized)
            'i3.large': 0.172, 'i3.xlarge': 0.344, 'i3.2xlarge': 0.688,
            'i3.4xlarge': 1.376, 'i3.8xlarge': 2.752,
            # D2 family (Dense Storage)
            'd2.xlarge': 0.756, 'd2.2xlarge': 1.512, 'd2.4xlarge': 3.024,
        }
        
        if instance_type in fallback_costs:
            return fallback_costs[instance_type]
        
        # Last resort: estimate from instance size
        size_costs = {
            'nano': 0.006, 'micro': 0.012, 'small': 0.024,
            'medium': 0.048, 'large': 0.096, 'xlarge': 0.192,
            '2xlarge': 0.384, '4xlarge': 0.768, '8xlarge': 1.536,
            '9xlarge': 1.728, '12xlarge': 2.304, '16xlarge': 3.072,
            '24xlarge': 4.608,
        }
        parts = instance_type.split('.')
        size = parts[1] if len(parts) > 1 else 'medium'
        return size_costs.get(size, 0.096)
    
    def _update_summary(self):
        """Update optimization summary — only counts positive savings"""
        print("  └── Generating optimization summary...")
        
        total_savings = 0
        by_category = {}
        
        for rec in self.recommendations:
            savings = rec.get('estimated_monthly_savings', 0)
            # Only count positive savings
            if savings > 0:
                total_savings += savings
            
            category = rec['category']
            if category not in by_category:
                by_category[category] = {'count': 0, 'savings': 0}
            by_category[category]['count'] += 1
            if savings > 0:
                by_category[category]['savings'] += savings
        
        # Remove recommendations with negative savings from the list
        self.recommendations = [r for r in self.recommendations if r.get('estimated_monthly_savings', 0) > 0]
        
        self.summary = {
            "total_recommendations": len(self.recommendations),
            "potential_monthly_savings": round(total_savings, 2),
            "potential_annual_savings": round(total_savings * 12, 2),
            "by_category": by_category
        }
        
        print(f"      └── Found {len(self.recommendations)} optimization opportunities")
        print(f"          Potential monthly savings: ${total_savings:.2f}")
    
    def get_recommendations_by_category(self, category: str) -> List[Dict]:
        """Get recommendations filtered by category"""
        return [r for r in self.recommendations if r['category'] == category]
    
    def get_quick_wins(self) -> List[Dict]:
        """Get low-effort, low-risk recommendations"""
        return [r for r in self.recommendations if r['effort'] == 'Low' and r['risk'] == 'Low']


if __name__ == "__main__":
    optimizer = Optimizer()
    results = optimizer.run_all_checks()
    
    print("\n" + "="*50)
    print("OPTIMIZATION SUMMARY")
    print("="*50)
    print(f"Total Recommendations: {results['summary']['total_recommendations']}")
    print(f"Potential Monthly Savings: ${results['summary']['potential_monthly_savings']:.2f}")
    print(f"Potential Annual Savings: ${results['summary']['potential_annual_savings']:.2f}")
    print("\nBy Category:")
    for cat, data in results['summary']['by_category'].items():
        print(f"  {cat}: {data['count']} recommendations (${data['savings']:.2f}/month)")

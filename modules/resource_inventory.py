"""
AWS Health Check Tool - Resource Inventory Module
Scans and inventories all AWS resources across regions
"""

import boto3
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import AWS_REGIONS, RESOURCE_TYPES


class ResourceInventory:
    """Scans and inventories all AWS resources"""
    
    def __init__(self, session: Optional[boto3.Session] = None, regions: List[str] = None):
        self.session = session or boto3.Session()
        self.regions = regions or [self.session.region_name or 'us-east-1']
        self.results = {
            "ec2_instances": [],
            "ec2_volumes": [],
            "ec2_security_groups": [],
            "ec2_elastic_ips": [],
            "rds_instances": [],
            "s3_buckets": [],
            "lambda_functions": [],
            "ecs_clusters": [],
            "load_balancers": [],
            "nat_gateways": [],
            "vpcs": [],
            "ecr_repositories": [],
            "cloudfront_distributions": [],
            "secrets": [],
            "summary": {}
        }
    
    def run_all_checks(self) -> Dict[str, Any]:
        """Run all resource inventory checks"""
        print("🖥️  Running Resource Inventory...")
        
        for region in self.regions:
            print(f"  ├── Scanning region: {region}")
            self._scan_region(region)
        
        # Global services (region-independent)
        self._scan_s3_buckets()
        self._scan_cloudfront()
        self._scan_iam_summary()
        
        self._generate_summary()
        
        return self.results
    
    def _scan_region(self, region: str):
        """Scan all resources in a specific region"""
        self._scan_ec2_instances(region)
        self._scan_ec2_volumes(region)
        self._scan_security_groups(region)
        self._scan_elastic_ips(region)
        self._scan_rds_instances(region)
        self._scan_lambda_functions(region)
        self._scan_ecs_clusters(region)
        self._scan_load_balancers(region)
        self._scan_nat_gateways(region)
        self._scan_vpcs(region)
        self._scan_ecr_repositories(region)
        self._scan_secrets(region)
    
    def _scan_ec2_instances(self, region: str):
        """Scan EC2 instances (excludes terminated instances)"""
        try:
            ec2 = self.session.client('ec2', region_name=region)
            paginator = ec2.get_paginator('describe_instances')
            
            # Exclude terminated instances - they are no longer active
            filters = [{'Name': 'instance-state-name', 'Values': ['running', 'stopped', 'pending', 'stopping']}]
            
            for page in paginator.paginate(Filters=filters):
                for reservation in page['Reservations']:
                    for instance in reservation['Instances']:
                        name = ''
                        for tag in instance.get('Tags', []):
                            if tag['Key'] == 'Name':
                                name = tag['Value']
                                break
                        
                        self.results['ec2_instances'].append({
                            'instance_id': instance['InstanceId'],
                            'instance_type': instance['InstanceType'],
                            'state': instance['State']['Name'],
                            'name': name,
                            'launch_time': str(instance.get('LaunchTime', '')),
                            'private_ip': instance.get('PrivateIpAddress', ''),
                            'public_ip': instance.get('PublicIpAddress', ''),
                            'vpc_id': instance.get('VpcId', ''),
                            'region': region
                        })
        except Exception as e:
            print(f"  │   └── EC2 Error in {region}: {str(e)[:50]}")
    
    def _scan_ec2_volumes(self, region: str):
        """Scan EBS volumes"""
        try:
            ec2 = self.session.client('ec2', region_name=region)
            paginator = ec2.get_paginator('describe_volumes')
            
            for page in paginator.paginate():
                for volume in page['Volumes']:
                    attached_to = ''
                    if volume['Attachments']:
                        attached_to = volume['Attachments'][0].get('InstanceId', '')
                    
                    name = ''
                    for tag in volume.get('Tags', []):
                        if tag['Key'] == 'Name':
                            name = tag['Value']
                            break
                    
                    self.results['ec2_volumes'].append({
                        'volume_id': volume['VolumeId'],
                        'size_gb': volume['Size'],
                        'volume_type': volume['VolumeType'],
                        'state': volume['State'],
                        'attached_to': attached_to,
                        'encrypted': volume.get('Encrypted', False),
                        'name': name,
                        'region': region
                    })
        except Exception as e:
            print(f"  │   └── EBS Error in {region}: {str(e)[:50]}")
    
    def _scan_security_groups(self, region: str):
        """Scan Security Groups"""
        try:
            ec2 = self.session.client('ec2', region_name=region)
            paginator = ec2.get_paginator('describe_security_groups')
            
            for page in paginator.paginate():
                for sg in page['SecurityGroups']:
                    self.results['ec2_security_groups'].append({
                        'group_id': sg['GroupId'],
                        'group_name': sg['GroupName'],
                        'description': sg.get('Description', ''),
                        'vpc_id': sg.get('VpcId', ''),
                        'inbound_rules_count': len(sg.get('IpPermissions', [])),
                        'outbound_rules_count': len(sg.get('IpPermissionsEgress', [])),
                        'region': region
                    })
        except Exception as e:
            print(f"  │   └── SG Error in {region}: {str(e)[:50]}")
    
    def _scan_elastic_ips(self, region: str):
        """Scan Elastic IPs"""
        try:
            ec2 = self.session.client('ec2', region_name=region)
            response = ec2.describe_addresses()
            
            for eip in response.get('Addresses', []):
                self.results['ec2_elastic_ips'].append({
                    'public_ip': eip.get('PublicIp', ''),
                    'allocation_id': eip.get('AllocationId', ''),
                    'instance_id': eip.get('InstanceId', ''),
                    'association_id': eip.get('AssociationId', ''),
                    'is_attached': bool(eip.get('AssociationId')),
                    'region': region
                })
        except Exception as e:
            print(f"  │   └── EIP Error in {region}: {str(e)[:50]}")
    
    def _scan_rds_instances(self, region: str):
        """Scan RDS instances"""
        try:
            rds = self.session.client('rds', region_name=region)
            paginator = rds.get_paginator('describe_db_instances')
            
            for page in paginator.paginate():
                for db in page['DBInstances']:
                    self.results['rds_instances'].append({
                        'db_identifier': db['DBInstanceIdentifier'],
                        'db_class': db['DBInstanceClass'],
                        'engine': db['Engine'],
                        'engine_version': db.get('EngineVersion', ''),
                        'status': db['DBInstanceStatus'],
                        'multi_az': db.get('MultiAZ', False),
                        'storage_type': db.get('StorageType', ''),
                        'allocated_storage': db.get('AllocatedStorage', 0),
                        'encrypted': db.get('StorageEncrypted', False),
                        'publicly_accessible': db.get('PubliclyAccessible', False),
                        'region': region
                    })
        except Exception as e:
            print(f"  │   └── RDS Error in {region}: {str(e)[:50]}")
    
    def _scan_lambda_functions(self, region: str):
        """Scan Lambda functions"""
        try:
            lambda_client = self.session.client('lambda', region_name=region)
            paginator = lambda_client.get_paginator('list_functions')
            
            for page in paginator.paginate():
                for func in page['Functions']:
                    self.results['lambda_functions'].append({
                        'function_name': func['FunctionName'],
                        'runtime': func.get('Runtime', 'N/A'),
                        'memory': func.get('MemorySize', 0),
                        'timeout': func.get('Timeout', 0),
                        'last_modified': func.get('LastModified', ''),
                        'code_size': func.get('CodeSize', 0),
                        'region': region
                    })
        except Exception as e:
            print(f"  │   └── Lambda Error in {region}: {str(e)[:50]}")
    
    def _scan_ecs_clusters(self, region: str):
        """Scan ECS clusters"""
        try:
            ecs = self.session.client('ecs', region_name=region)
            clusters_response = ecs.list_clusters()
            cluster_arns = clusters_response.get('clusterArns', [])
            
            if cluster_arns:
                details = ecs.describe_clusters(
                    clusters=cluster_arns,
                    include=['STATISTICS']
                )
                
                for cluster in details.get('clusters', []):
                    self.results['ecs_clusters'].append({
                        'cluster_name': cluster['clusterName'],
                        'status': cluster['status'],
                        'registered_instances': cluster.get('registeredContainerInstancesCount', 0),
                        'running_tasks': cluster.get('runningTasksCount', 0),
                        'pending_tasks': cluster.get('pendingTasksCount', 0),
                        'active_services': cluster.get('activeServicesCount', 0),
                        'region': region
                    })
        except Exception as e:
            print(f"  │   └── ECS Error in {region}: {str(e)[:50]}")
    
    def _scan_load_balancers(self, region: str):
        """Scan Load Balancers (ALB, NLB)"""
        try:
            elbv2 = self.session.client('elbv2', region_name=region)
            paginator = elbv2.get_paginator('describe_load_balancers')
            
            for page in paginator.paginate():
                for lb in page['LoadBalancers']:
                    self.results['load_balancers'].append({
                        'name': lb['LoadBalancerName'],
                        'arn': lb.get('LoadBalancerArn', ''),  # Added for CloudWatch metrics
                        'type': lb['Type'],
                        'scheme': lb['Scheme'],
                        'state': lb['State']['Code'],
                        'dns_name': lb.get('DNSName', ''),
                        'vpc_id': lb.get('VpcId', ''),
                        'region': region
                    })
        except Exception as e:
            print(f"  │   └── ELB Error in {region}: {str(e)[:50]}")
    
    def _scan_nat_gateways(self, region: str):
        """Scan NAT Gateways"""
        try:
            ec2 = self.session.client('ec2', region_name=region)
            paginator = ec2.get_paginator('describe_nat_gateways')
            
            for page in paginator.paginate():
                for nat in page['NatGateways']:
                    name = ''
                    for tag in nat.get('Tags', []):
                        if tag['Key'] == 'Name':
                            name = tag['Value']
                            break
                    
                    self.results['nat_gateways'].append({
                        'nat_gateway_id': nat['NatGatewayId'],
                        'state': nat['State'],
                        'subnet_id': nat.get('SubnetId', ''),
                        'vpc_id': nat.get('VpcId', ''),
                        'name': name,
                        'region': region
                    })
        except Exception as e:
            print(f"  │   └── NAT Error in {region}: {str(e)[:50]}")
    
    def _scan_vpcs(self, region: str):
        """Scan VPCs"""
        try:
            ec2 = self.session.client('ec2', region_name=region)
            response = ec2.describe_vpcs()
            
            for vpc in response.get('Vpcs', []):
                name = ''
                for tag in vpc.get('Tags', []):
                    if tag['Key'] == 'Name':
                        name = tag['Value']
                        break
                
                self.results['vpcs'].append({
                    'vpc_id': vpc['VpcId'],
                    'cidr_block': vpc.get('CidrBlock', ''),
                    'state': vpc['State'],
                    'is_default': vpc.get('IsDefault', False),
                    'name': name,
                    'region': region
                })
        except Exception as e:
            print(f"  │   └── VPC Error in {region}: {str(e)[:50]}")
    
    def _scan_ecr_repositories(self, region: str):
        """Scan ECR repositories"""
        try:
            ecr = self.session.client('ecr', region_name=region)
            paginator = ecr.get_paginator('describe_repositories')
            
            for page in paginator.paginate():
                for repo in page['repositories']:
                    self.results['ecr_repositories'].append({
                        'repository_name': repo['repositoryName'],
                        'repository_uri': repo['repositoryUri'],
                        'created_at': str(repo.get('createdAt', '')),
                        'region': region
                    })
        except Exception as e:
            print(f"  │   └── ECR Error in {region}: {str(e)[:50]}")
    
    def _scan_secrets(self, region: str):
        """Scan Secrets Manager secrets"""
        try:
            sm = self.session.client('secretsmanager', region_name=region)
            paginator = sm.get_paginator('list_secrets')
            
            for page in paginator.paginate():
                for secret in page['SecretList']:
                    self.results['secrets'].append({
                        'name': secret['Name'],
                        'created_date': str(secret.get('CreatedDate', '')),
                        'last_accessed': str(secret.get('LastAccessedDate', '')),
                        'region': region
                    })
        except Exception as e:
            print(f"  │   └── Secrets Error in {region}: {str(e)[:50]}")
    
    def _scan_s3_buckets(self):
        """Scan S3 buckets (global service)"""
        print("  ├── Scanning S3 buckets (global)...")
        try:
            s3 = self.session.client('s3')
            response = s3.list_buckets()
            
            for bucket in response.get('Buckets', []):
                bucket_info = {
                    'bucket_name': bucket['Name'],
                    'creation_date': str(bucket.get('CreationDate', '')),
                    'region': 'global'
                }
                
                # Try to get bucket location
                try:
                    location = s3.get_bucket_location(Bucket=bucket['Name'])
                    bucket_info['region'] = location.get('LocationConstraint') or 'us-east-1'
                except:
                    pass
                
                self.results['s3_buckets'].append(bucket_info)
            
            print(f"  │   └── Found {len(self.results['s3_buckets'])} buckets")
        except Exception as e:
            print(f"  │   └── S3 Error: {str(e)[:50]}")
    
    def _scan_cloudfront(self):
        """Scan CloudFront distributions (global service)"""
        print("  ├── Scanning CloudFront distributions...")
        try:
            cf = self.session.client('cloudfront')
            paginator = cf.get_paginator('list_distributions')
            
            for page in paginator.paginate():
                dist_list = page.get('DistributionList', {})
                for dist in dist_list.get('Items', []):
                    self.results['cloudfront_distributions'].append({
                        'distribution_id': dist['Id'],
                        'domain_name': dist['DomainName'],
                        'status': dist['Status'],
                        'enabled': dist['Enabled'],
                        'region': 'global'
                    })
            
            print(f"  │   └── Found {len(self.results['cloudfront_distributions'])} distributions")
        except Exception as e:
            print(f"  │   └── CloudFront Error: {str(e)[:50]}")
    
    def _scan_iam_summary(self):
        """Get IAM account summary"""
        print("  ├── Scanning IAM summary...")
        try:
            iam = self.session.client('iam')
            summary = iam.get_account_summary()
            
            self.results['iam_summary'] = {
                'users': summary['SummaryMap'].get('Users', 0),
                'groups': summary['SummaryMap'].get('Groups', 0),
                'roles': summary['SummaryMap'].get('Roles', 0),
                'policies': summary['SummaryMap'].get('Policies', 0),
                'mfa_devices': summary['SummaryMap'].get('MFADevices', 0),
                'access_keys': summary['SummaryMap'].get('AccessKeysPerUserQuota', 0)
            }
            print(f"  │   └── Found {self.results['iam_summary']['users']} IAM users")
        except Exception as e:
            print(f"  │   └── IAM Error: {str(e)[:50]}")
    
    def _generate_summary(self):
        """Generate resource summary"""
        print("  └── Generating summary...")
        
        self.results['summary'] = {
            'total_ec2_instances': len(self.results['ec2_instances']),
            'running_ec2_instances': len([i for i in self.results['ec2_instances'] if i['state'] == 'running']),
            'stopped_ec2_instances': len([i for i in self.results['ec2_instances'] if i['state'] == 'stopped']),
            'total_ebs_volumes': len(self.results['ec2_volumes']),
            'unattached_volumes': len([v for v in self.results['ec2_volumes'] if not v['attached_to']]),
            'total_ebs_storage_gb': sum(v['size_gb'] for v in self.results['ec2_volumes']),
            'total_security_groups': len(self.results['ec2_security_groups']),
            'total_elastic_ips': len(self.results['ec2_elastic_ips']),
            'unused_elastic_ips': len([e for e in self.results['ec2_elastic_ips'] if not e['is_attached']]),
            'total_rds_instances': len(self.results['rds_instances']),
            'total_s3_buckets': len(self.results['s3_buckets']),
            'total_lambda_functions': len(self.results['lambda_functions']),
            'total_ecs_clusters': len(self.results['ecs_clusters']),
            'total_load_balancers': len(self.results['load_balancers']),
            'total_nat_gateways': len(self.results['nat_gateways']),
            'total_vpcs': len(self.results['vpcs']),
            'total_ecr_repositories': len(self.results['ecr_repositories']),
            'total_cloudfront_distributions': len(self.results['cloudfront_distributions']),
            'total_secrets': len(self.results['secrets']),
            'regions_scanned': self.regions
        }
        
        print(f"      └── Total resources found: {sum(v for k, v in self.results['summary'].items() if isinstance(v, int))}")
    
    def get_summary(self) -> Dict:
        """Return the summary"""
        return self.results['summary']


if __name__ == "__main__":
    inventory = ResourceInventory()
    results = inventory.run_all_checks()
    
    print("\n" + "="*50)
    print("RESOURCE INVENTORY SUMMARY")
    print("="*50)
    for key, value in results['summary'].items():
        if isinstance(value, int):
            print(f"  {key}: {value}")

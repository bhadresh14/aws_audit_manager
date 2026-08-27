"""
AWS Health Check Tool - Cost Estimator Module
Estimates costs from resource inventory when billing API access is unavailable.
Supports multi-region pricing for accurate estimates across all AWS regions.
"""

import boto3
from typing import Dict, List, Any, Optional
from datetime import datetime


# =============================================================================
# REGIONAL PRICING DATA
# =============================================================================
# Prices in USD per hour (for EC2) or per GB-month (for storage)
# Last updated: August 2026
# Source: AWS Pricing Calculator & Price List API
# 
# Note: Prices vary by region. ap-south-1 (Mumbai) is typically 15-30% higher
# than us-east-1. EU regions are 5-15% higher. Japan is 20-35% higher.
# =============================================================================

# Regional multipliers relative to us-east-1 baseline
# These are approximate and applied to base prices
REGION_MULTIPLIERS = {
    "us-east-1": 1.00,      # N. Virginia - baseline
    "us-east-2": 1.00,      # Ohio
    "us-west-1": 1.08,      # N. California
    "us-west-2": 1.00,      # Oregon
    "eu-west-1": 1.05,      # Ireland
    "eu-west-2": 1.08,      # London
    "eu-west-3": 1.08,      # Paris
    "eu-central-1": 1.08,   # Frankfurt
    "eu-north-1": 1.05,     # Stockholm
    "ap-south-1": 1.12,     # Mumbai
    "ap-southeast-1": 1.15, # Singapore
    "ap-southeast-2": 1.18, # Sydney
    "ap-northeast-1": 1.25, # Tokyo
    "ap-northeast-2": 1.20, # Seoul
    "ap-northeast-3": 1.25, # Osaka
    "sa-east-1": 1.50,      # Sao Paulo
    "ca-central-1": 1.05,   # Canada
    "me-south-1": 1.20,     # Bahrain
    "af-south-1": 1.25,     # Cape Town
}

# Default to us-east-1 pricing for unknown regions
DEFAULT_REGION = "us-east-1"


# =============================================================================
# EC2 PRICING BY REGION (hourly rates in USD)
# =============================================================================
# Key regions with actual prices, others use multipliers

EC2_REGIONAL_PRICING = {
    "us-east-1": {
        # General Purpose - T2
        "t2.micro": 0.0116, "t2.small": 0.023, "t2.medium": 0.0464,
        "t2.large": 0.0928, "t2.xlarge": 0.1856, "t2.2xlarge": 0.3712,
        # General Purpose - T3
        "t3.micro": 0.0104, "t3.small": 0.0208, "t3.medium": 0.0416,
        "t3.large": 0.0832, "t3.xlarge": 0.1664, "t3.2xlarge": 0.3328,
        # General Purpose - T3a
        "t3a.micro": 0.0094, "t3a.small": 0.0188, "t3a.medium": 0.0376,
        "t3a.large": 0.0752, "t3a.xlarge": 0.1504, "t3a.2xlarge": 0.3008,
        # Compute Optimized - C5
        "c5.large": 0.085, "c5.xlarge": 0.17, "c5.2xlarge": 0.34,
        "c5.4xlarge": 0.68, "c5.9xlarge": 1.53, "c5.12xlarge": 2.04,
        # Compute Optimized - C6i
        "c6i.large": 0.085, "c6i.xlarge": 0.17, "c6i.2xlarge": 0.34,
        "c6i.4xlarge": 0.68, "c6i.8xlarge": 1.36,
        # Memory Optimized - R5
        "r5.large": 0.126, "r5.xlarge": 0.252, "r5.2xlarge": 0.504,
        "r5.4xlarge": 1.008, "r5.8xlarge": 2.016,
        # Memory Optimized - R6i
        "r6i.large": 0.126, "r6i.xlarge": 0.252, "r6i.2xlarge": 0.504,
        "r6i.4xlarge": 1.008,
        # General Purpose - M5
        "m5.large": 0.096, "m5.xlarge": 0.192, "m5.2xlarge": 0.384,
        "m5.4xlarge": 0.768, "m5.8xlarge": 1.536,
        # General Purpose - M6i
        "m6i.large": 0.096, "m6i.xlarge": 0.192, "m6i.2xlarge": 0.384,
        "m6i.4xlarge": 0.768,
    },
    "ap-south-1": {
        # Mumbai pricing (typically 8-15% higher than us-east-1)
        # General Purpose - T2
        "t2.micro": 0.0116, "t2.small": 0.0232, "t2.medium": 0.0464,
        "t2.large": 0.0928, "t2.xlarge": 0.1856, "t2.2xlarge": 0.3712,
        # General Purpose - T3
        "t3.micro": 0.0116, "t3.small": 0.0232, "t3.medium": 0.0464,
        "t3.large": 0.0928, "t3.xlarge": 0.1856, "t3.2xlarge": 0.3712,
        # General Purpose - T3a
        "t3a.micro": 0.0104, "t3a.small": 0.0209, "t3a.medium": 0.0418,
        "t3a.large": 0.0835, "t3a.xlarge": 0.167, "t3a.2xlarge": 0.334,
        # Compute Optimized - C5
        "c5.large": 0.093, "c5.xlarge": 0.186, "c5.2xlarge": 0.372,
        "c5.4xlarge": 0.744, "c5.9xlarge": 1.674, "c5.12xlarge": 2.232,
        # Compute Optimized - C6i
        "c6i.large": 0.093, "c6i.xlarge": 0.186, "c6i.2xlarge": 0.372,
        "c6i.4xlarge": 0.744, "c6i.8xlarge": 1.488,
        # Memory Optimized - R5
        "r5.large": 0.139, "r5.xlarge": 0.278, "r5.2xlarge": 0.556,
        "r5.4xlarge": 1.112, "r5.8xlarge": 2.224,
        # Memory Optimized - R6i
        "r6i.large": 0.139, "r6i.xlarge": 0.278, "r6i.2xlarge": 0.556,
        "r6i.4xlarge": 1.112,
        # General Purpose - M5
        "m5.large": 0.107, "m5.xlarge": 0.214, "m5.2xlarge": 0.428,
        "m5.4xlarge": 0.856, "m5.8xlarge": 1.712,
        # General Purpose - M6i
        "m6i.large": 0.107, "m6i.xlarge": 0.214, "m6i.2xlarge": 0.428,
        "m6i.4xlarge": 0.856,
    },
    "eu-west-1": {
        # Ireland pricing (typically 5-8% higher than us-east-1)
        "t2.micro": 0.0126, "t2.small": 0.0252, "t2.medium": 0.0504,
        "t2.large": 0.1008, "t2.xlarge": 0.2016,
        "t3.micro": 0.0114, "t3.small": 0.0228, "t3.medium": 0.0456,
        "t3.large": 0.0912, "t3.xlarge": 0.1824, "t3.2xlarge": 0.3648,
        "c5.large": 0.093, "c5.xlarge": 0.186, "c5.2xlarge": 0.372,
        "c5.4xlarge": 0.744,
        "m5.large": 0.107, "m5.xlarge": 0.214, "m5.2xlarge": 0.428,
        "r5.large": 0.139, "r5.xlarge": 0.278, "r5.2xlarge": 0.556,
    },
    "ap-northeast-1": {
        # Tokyo pricing (typically 20-30% higher than us-east-1)
        "t2.micro": 0.0152, "t2.small": 0.0304, "t2.medium": 0.0608,
        "t2.large": 0.1216, "t2.xlarge": 0.2432,
        "t3.micro": 0.0136, "t3.small": 0.0272, "t3.medium": 0.0544,
        "t3.large": 0.1088, "t3.xlarge": 0.2176, "t3.2xlarge": 0.4352,
        "c5.large": 0.107, "c5.xlarge": 0.214, "c5.2xlarge": 0.428,
        "c5.4xlarge": 0.856,
        "m5.large": 0.124, "m5.xlarge": 0.248, "m5.2xlarge": 0.496,
        "r5.large": 0.166, "r5.xlarge": 0.332, "r5.2xlarge": 0.664,
    },
    "ap-southeast-1": {
        # Singapore pricing (typically 15-20% higher than us-east-1)
        "t2.micro": 0.0134, "t2.small": 0.0268, "t2.medium": 0.0536,
        "t3.micro": 0.012, "t3.small": 0.024, "t3.medium": 0.048,
        "t3.large": 0.096, "t3.xlarge": 0.192, "t3.2xlarge": 0.384,
        "c5.large": 0.098, "c5.xlarge": 0.196, "c5.2xlarge": 0.392,
        "m5.large": 0.111, "m5.xlarge": 0.222, "m5.2xlarge": 0.444,
        "r5.large": 0.145, "r5.xlarge": 0.29, "r5.2xlarge": 0.58,
    },
}


# =============================================================================
# EBS PRICING BY REGION (per GB-month in USD)
# =============================================================================

EBS_REGIONAL_PRICING = {
    "us-east-1": {
        "gp2": 0.10, "gp3": 0.08, "io1": 0.125, "io2": 0.125,
        "st1": 0.045, "sc1": 0.025, "standard": 0.05,
    },
    "us-east-2": {
        "gp2": 0.10, "gp3": 0.08, "io1": 0.125, "io2": 0.125,
        "st1": 0.045, "sc1": 0.025, "standard": 0.05,
    },
    "us-west-2": {
        "gp2": 0.10, "gp3": 0.08, "io1": 0.125, "io2": 0.125,
        "st1": 0.045, "sc1": 0.025, "standard": 0.05,
    },
    "ap-south-1": {
        "gp2": 0.114, "gp3": 0.0912, "io1": 0.138, "io2": 0.138,
        "st1": 0.051, "sc1": 0.029, "standard": 0.057,
    },
    "eu-west-1": {
        "gp2": 0.11, "gp3": 0.088, "io1": 0.138, "io2": 0.138,
        "st1": 0.05, "sc1": 0.028, "standard": 0.055,
    },
    "ap-northeast-1": {
        "gp2": 0.12, "gp3": 0.096, "io1": 0.142, "io2": 0.142,
        "st1": 0.054, "sc1": 0.03, "standard": 0.06,
    },
    "ap-southeast-1": {
        "gp2": 0.12, "gp3": 0.096, "io1": 0.138, "io2": 0.138,
        "st1": 0.054, "sc1": 0.03, "standard": 0.06,
    },
}


# =============================================================================
# OTHER AWS SERVICES PRICING BY REGION (monthly in USD unless noted)
# =============================================================================

OTHER_REGIONAL_PRICING = {
    "us-east-1": {
        "nat_gateway_hourly": 0.045,
        "nat_gateway_per_gb": 0.045,
        "elastic_ip_unused": 3.60,          # Global rate
        "elastic_ip_attached_stopped": 3.60,
        "alb_hourly": 0.0225,
        "alb_lcu": 0.008,
        "nlb_hourly": 0.0225,
        "clb_hourly": 0.025,
        "rds_db.t3.micro": 12.41,
        "rds_db.t3.small": 24.82,
        "rds_db.t3.medium": 49.64,
        "rds_db.r5.large": 182.50,
        "rds_storage_gp2": 0.115,
        "s3_standard_gb": 0.023,
        "cloudfront_gb": 0.085,
        "ecr_storage_gb": 0.10,
        "secrets_manager": 0.40,
        "lambda_requests": 0.20,
        "lambda_gb_seconds": 0.0000166667,
    },
    "ap-south-1": {
        "nat_gateway_hourly": 0.052,
        "nat_gateway_per_gb": 0.052,
        "elastic_ip_unused": 3.60,
        "elastic_ip_attached_stopped": 3.60,
        "alb_hourly": 0.026,
        "alb_lcu": 0.009,
        "nlb_hourly": 0.026,
        "clb_hourly": 0.029,
        "rds_db.t3.micro": 14.60,
        "rds_db.t3.small": 29.20,
        "rds_db.t3.medium": 58.40,
        "rds_db.r5.large": 201.10,
        "rds_storage_gp2": 0.133,
        "s3_standard_gb": 0.025,
        "cloudfront_gb": 0.170,
        "ecr_storage_gb": 0.10,
        "secrets_manager": 0.40,
        "lambda_requests": 0.20,
        "lambda_gb_seconds": 0.0000166667,
    },
    "eu-west-1": {
        "nat_gateway_hourly": 0.048,
        "nat_gateway_per_gb": 0.048,
        "elastic_ip_unused": 3.60,
        "elastic_ip_attached_stopped": 3.60,
        "alb_hourly": 0.024,
        "alb_lcu": 0.0086,
        "nlb_hourly": 0.024,
        "clb_hourly": 0.028,
        "rds_db.t3.micro": 13.87,
        "rds_db.t3.small": 27.74,
        "rds_db.t3.medium": 55.48,
        "rds_db.r5.large": 197.10,
        "rds_storage_gp2": 0.127,
        "s3_standard_gb": 0.024,
        "cloudfront_gb": 0.085,
        "ecr_storage_gb": 0.10,
        "secrets_manager": 0.40,
        "lambda_requests": 0.20,
        "lambda_gb_seconds": 0.0000166667,
    },
    "ap-northeast-1": {
        "nat_gateway_hourly": 0.062,
        "nat_gateway_per_gb": 0.062,
        "elastic_ip_unused": 3.60,
        "elastic_ip_attached_stopped": 3.60,
        "alb_hourly": 0.029,
        "alb_lcu": 0.01,
        "nlb_hourly": 0.029,
        "clb_hourly": 0.032,
        "rds_db.t3.micro": 16.06,
        "rds_db.t3.small": 32.12,
        "rds_db.t3.medium": 64.24,
        "rds_db.r5.large": 236.52,
        "rds_storage_gp2": 0.138,
        "s3_standard_gb": 0.025,
        "cloudfront_gb": 0.114,
        "ecr_storage_gb": 0.10,
        "secrets_manager": 0.40,
        "lambda_requests": 0.20,
        "lambda_gb_seconds": 0.0000166667,
    },
}


# Hours in a month (average)
HOURS_PER_MONTH = 730


class RegionalPricing:
    """Helper class to get region-specific pricing with live API support"""
    
    def __init__(self, region: str, session: Optional[boto3.Session] = None):
        self.region = region
        self.session = session
        self.multiplier = REGION_MULTIPLIERS.get(region, 1.15)  # Default 15% premium
        self._pricing_api = None
        self._use_live_pricing = True
        self.pricing_source = "static"  # Will be updated if live API works
    
    @property
    def pricing_api(self):
        """Lazy-load pricing API"""
        if self._pricing_api is None and self._use_live_pricing:
            try:
                from modules.pricing_api import get_pricing_api
                self._pricing_api = get_pricing_api(self.session)
            except Exception:
                self._use_live_pricing = False
        return self._pricing_api
        
    def get_ec2_hourly(self, instance_type: str) -> float:
        """Get EC2 hourly rate for instance type in current region"""
        # Try live pricing API first
        if self._use_live_pricing and self.pricing_api:
            live_price = self.pricing_api.get_ec2_price(instance_type, self.region)
            if live_price is not None:
                self.pricing_source = "live_api"
                return live_price
        
        # Fall back to static tables
        self.pricing_source = "static"
        
        # Try exact region pricing first
        if self.region in EC2_REGIONAL_PRICING:
            if instance_type in EC2_REGIONAL_PRICING[self.region]:
                return EC2_REGIONAL_PRICING[self.region][instance_type]
        
        # Fall back to us-east-1 with multiplier
        base_price = EC2_REGIONAL_PRICING.get("us-east-1", {}).get(instance_type)
        if base_price:
            return base_price * self.multiplier
        
        # Default estimate based on instance size
        return self._estimate_ec2_price(instance_type)
    
    def _estimate_ec2_price(self, instance_type: str) -> float:
        """Estimate EC2 price based on instance family and size"""
        size_multipliers = {
            "nano": 0.25, "micro": 0.5, "small": 1, "medium": 2,
            "large": 4, "xlarge": 8, "2xlarge": 16, "4xlarge": 32,
            "8xlarge": 64, "9xlarge": 72, "12xlarge": 96, "16xlarge": 128,
        }
        
        # Extract size from instance type (e.g., "t3.medium" -> "medium")
        parts = instance_type.split(".")
        size = parts[1] if len(parts) > 1 else "medium"
        
        base = 0.01  # Base hourly rate for nano
        mult = size_multipliers.get(size, 4)  # Default to large
        return base * mult * self.multiplier

    def get_ec2_monthly(self, instance_type: str) -> float:
        """Get EC2 monthly cost for instance type"""
        return self.get_ec2_hourly(instance_type) * HOURS_PER_MONTH
    
    def get_ebs_per_gb(self, volume_type: str) -> float:
        """Get EBS price per GB-month"""
        # Try live pricing API first
        if self._use_live_pricing and self.pricing_api:
            live_price = self.pricing_api.get_ebs_price(volume_type, self.region)
            if live_price is not None:
                self.pricing_source = "live_api"
                return live_price
        
        # Fall back to static tables
        if self.region in EBS_REGIONAL_PRICING:
            if volume_type in EBS_REGIONAL_PRICING[self.region]:
                return EBS_REGIONAL_PRICING[self.region][volume_type]
        
        # Fall back to us-east-1 with multiplier
        base_price = EBS_REGIONAL_PRICING.get("us-east-1", {}).get(volume_type, 0.08)
        return base_price * self.multiplier
    
    def get_other_price(self, service_key: str) -> float:
        """Get other service pricing"""
        if self.region in OTHER_REGIONAL_PRICING:
            if service_key in OTHER_REGIONAL_PRICING[self.region]:
                return OTHER_REGIONAL_PRICING[self.region][service_key]
        
        # Fall back to us-east-1 with multiplier (except global services)
        global_services = ["elastic_ip_unused", "elastic_ip_attached_stopped", 
                          "ecr_storage_gb", "secrets_manager", "lambda_requests",
                          "lambda_gb_seconds"]
        
        base_price = OTHER_REGIONAL_PRICING.get("us-east-1", {}).get(service_key, 0)
        if service_key in global_services:
            return base_price  # Global pricing
        return base_price * self.multiplier
    
    def get_nat_gateway_monthly(self, estimated_gb: float = 100) -> float:
        """Get NAT Gateway monthly cost (base + data)"""
        hourly = self.get_other_price("nat_gateway_hourly")
        per_gb = self.get_other_price("nat_gateway_per_gb")
        return (hourly * HOURS_PER_MONTH) + (estimated_gb * per_gb)
    
    def get_alb_monthly(self, estimated_lcus: float = 10) -> float:
        """Get ALB monthly cost (base + LCUs)"""
        hourly = self.get_other_price("alb_hourly")
        lcu_rate = self.get_other_price("alb_lcu")
        return (hourly * HOURS_PER_MONTH) + (estimated_lcus * lcu_rate * HOURS_PER_MONTH)


class CostEstimator:
    """Estimates AWS costs from resource inventory with multi-region support"""
    
    def __init__(self, session: Optional[boto3.Session] = None, region: str = None):
        """
        Initialize with optional boto3 session and region
        
        Args:
            session: boto3 Session (optional)
            region: AWS region for pricing (auto-detected from session if not provided)
        """
        self.session = session or boto3.Session()
        
        # Determine region
        self.region = region or self.session.region_name or DEFAULT_REGION
        
        # Initialize regional pricing helper (with session for live API)
        self.pricing = RegionalPricing(self.region, self.session)
        
        # Results structure
        self.results = {
            "estimated_total": 0,
            "by_service": {},
            "by_resource": [],
            "estimation_method": "resource_inventory",
            "pricing_region": self.region,
            "accuracy_note": f"Estimates based on {self.region} on-demand pricing. Actual costs may vary."
        }
    
    def estimate_from_inventory(self, inventory: Dict[str, Any]) -> Dict[str, Any]:
        """
        Estimate costs from resource inventory data
        
        Args:
            inventory: Resource inventory dictionary from ResourceInventory module
            
        Returns:
            Dictionary with cost estimates by service and resource
        """
        print(f"💵 Estimating costs from resource inventory (Region: {self.region})...")
        print(f"  ├── Pricing source: {self.pricing.pricing_source}")
        
        total = 0
        
        # Estimate EC2 costs
        ec2_cost = self._estimate_ec2_costs(inventory.get('ec2_instances', []))
        total += ec2_cost
        
        # Estimate EBS costs
        ebs_cost = self._estimate_ebs_costs(inventory.get('ec2_volumes', []))
        total += ebs_cost
        
        # Estimate Elastic IP costs
        eip_cost = self._estimate_eip_costs(
            inventory.get('ec2_elastic_ips', []),
            inventory.get('ec2_instances', [])
        )
        total += eip_cost
        
        # Estimate NAT Gateway costs
        nat_cost = self._estimate_nat_costs(inventory.get('nat_gateways', []))
        total += nat_cost
        
        # Estimate Load Balancer costs
        lb_cost = self._estimate_lb_costs(inventory.get('load_balancers', []))
        total += lb_cost
        
        # Estimate RDS costs
        rds_cost = self._estimate_rds_costs(inventory.get('rds_instances', []))
        total += rds_cost

        # Estimate S3 costs
        s3_cost = self._estimate_s3_costs(inventory.get('s3_buckets', []))
        total += s3_cost
        
        # Estimate Lambda costs
        lambda_cost = self._estimate_lambda_costs(inventory.get('lambda_functions', []))
        total += lambda_cost
        
        # Estimate ECR costs
        ecr_cost = self._estimate_ecr_costs(inventory.get('ecr_repositories', []))
        total += ecr_cost
        
        # Estimate Secrets Manager costs
        secrets_cost = self._estimate_secrets_costs(inventory.get('secrets', []))
        total += secrets_cost
        
        # Estimate CloudFront costs
        cf_cost = self._estimate_cloudfront_costs(inventory.get('cloudfront_distributions', []))
        total += cf_cost
        
        # Estimate ECS costs
        ecs_cost = self._estimate_ecs_costs(inventory.get('ecs_clusters', []))
        total += ecs_cost
        
        self.results['estimated_total'] = round(total, 2)
        
        # Sort by_service by cost
        self.results['by_service'] = dict(
            sorted(self.results['by_service'].items(), 
                   key=lambda x: x[1]['cost'], reverse=True)
        )
        
        # Calculate usage-estimated vs list-price totals
        usage_estimated_total = sum(
            r['monthly_cost'] for r in self.results['by_resource'] 
            if r.get('estimate_type') == 'usage_estimated'
        )
        list_price_total = total - usage_estimated_total
        
        self.results['cost_confidence'] = {
            'list_price_total': round(list_price_total, 2),
            'usage_estimated_total': round(usage_estimated_total, 2),
            'note': 'List-price items are verifiable. Usage-estimated items (NAT Gateway, ALB) depend on actual traffic and should be verified against your AWS bill.'
        }
        
        print(f"  └── Estimated Total Monthly Cost: ${total:.2f} ({self.region} pricing)")
        if usage_estimated_total > 0:
            print(f"      └── ⚠️  ${usage_estimated_total:.2f} is usage-estimated (verify against bill)")
        
        return self.results
    
    def _add_service_cost(self, service: str, cost: float, details: str = ""):
        """Helper to add cost to a service category"""
        if service not in self.results['by_service']:
            self.results['by_service'][service] = {
                'cost': 0,
                'resources': [],
                'currency': 'USD'
            }
        self.results['by_service'][service]['cost'] += cost
        if details:
            self.results['by_service'][service]['resources'].append(details)
    
    def _add_resource_cost(self, resource_type: str, resource_id: str, 
                           name: str, cost: float, notes: str = "",
                           estimate_type: str = "list_price"):
        """
        Helper to add individual resource cost
        
        Args:
            estimate_type: "list_price" (verifiable) or "usage_estimated" (verify against bill)
        """
        self.results['by_resource'].append({
            'type': resource_type,
            'resource_id': resource_id,
            'name': name,
            'monthly_cost': round(cost, 2),
            'notes': notes,
            'estimate_type': estimate_type  # "list_price" or "usage_estimated"
        })

    def _estimate_ec2_costs(self, instances: List[Dict]) -> float:
        """Estimate EC2 instance costs using regional pricing"""
        print("  ├── Estimating EC2 costs...")
        
        total = 0
        running_count = 0
        stopped_count = 0
        
        for instance in instances:
            instance_type = instance.get('instance_type', 'unknown')
            state = instance.get('state', 'unknown')
            name = instance.get('name', instance.get('instance_id', 'unnamed'))
            instance_id = instance.get('instance_id', '')
            
            if state == 'running':
                running_count += 1
                monthly_cost = self.pricing.get_ec2_monthly(instance_type)
                total += monthly_cost
                
                self._add_resource_cost(
                    'EC2', instance_id, name, monthly_cost,
                    f"{instance_type} - running"
                )
            else:
                stopped_count += 1
                self._add_resource_cost(
                    'EC2', instance_id, name, 0,
                    f"{instance_type} - stopped (EBS still charged)"
                )
        
        self._add_service_cost('Amazon EC2', total, 
                               f"{running_count} running, {stopped_count} stopped")
        
        print(f"  │   └── EC2: ${total:.2f}/month ({running_count} running)")
        return total
    
    def _estimate_ebs_costs(self, volumes: List[Dict]) -> float:
        """Estimate EBS volume costs using regional pricing"""
        print("  ├── Estimating EBS costs...")
        
        total = 0
        total_gb = 0
        unattached_cost = 0
        
        for volume in volumes:
            size_gb = volume.get('size_gb', 0)
            vol_type = volume.get('volume_type', 'gp3')
            state = volume.get('state', 'unknown')
            volume_id = volume.get('volume_id', '')
            name = volume.get('name', volume_id)
            
            price_per_gb = self.pricing.get_ebs_per_gb(vol_type)
            cost = size_gb * price_per_gb
            total += cost
            total_gb += size_gb
            
            notes = f"{vol_type} - {size_gb}GB"
            if state == 'available':
                notes += " (UNATTACHED - wasting money!)"
                unattached_cost += cost
            
            self._add_resource_cost('EBS', volume_id, name, cost, notes)
        
        self._add_service_cost('Amazon EBS', total, f"{total_gb}GB total")
        
        print(f"  │   └── EBS: ${total:.2f}/month ({total_gb}GB)")
        if unattached_cost > 0:
            print(f"  │       └── ⚠️  Unattached volumes: ${unattached_cost:.2f}/month")
        
        return total

    def _estimate_eip_costs(self, eips: List[Dict], instances: List[Dict]) -> float:
        """Estimate Elastic IP costs"""
        print("  ├── Estimating Elastic IP costs...")
        
        # Build instance state map
        instance_states = {}
        for inst in instances:
            instance_states[inst.get('instance_id', '')] = inst.get('state', 'unknown')
        
        total = 0
        chargeable = 0
        
        for eip in eips:
            public_ip = eip.get('public_ip', '')
            instance_id = eip.get('instance_id', '')
            association_id = eip.get('association_id', '')
            is_attached = eip.get('is_attached', False)
            
            cost = 0
            notes = ""
            
            # Check if EIP is truly attached (has association_id or is_attached flag)
            # EIPs can be attached to:
            # 1. EC2 instances (has instance_id)
            # 2. NAT Gateways (has association_id but no instance_id)
            # 3. Network interfaces (has association_id but no instance_id)
            
            truly_attached = is_attached or bool(association_id)
            
            if not truly_attached:
                # Completely unattached EIP - always charges
                cost = self.pricing.get_other_price('elastic_ip_unused')
                notes = "UNATTACHED - charges apply"
                chargeable += 1
            elif instance_id:
                # Attached to an EC2 instance - check if instance is running
                instance_state = instance_states.get(instance_id, 'unknown')
                if instance_state == 'stopped':
                    cost = self.pricing.get_other_price('elastic_ip_attached_stopped')
                    notes = f"Attached to STOPPED instance ({instance_id})"
                    chargeable += 1
                elif instance_state == 'running':
                    notes = f"Attached to running instance ({instance_id}) - FREE"
                else:
                    # Instance not found (might be terminated) - treat as unattached
                    cost = self.pricing.get_other_price('elastic_ip_unused')
                    notes = f"Instance {instance_id} not found - charges apply"
                    chargeable += 1
            else:
                # Has association but no instance_id = attached to NAT Gateway or ENI
                # NAT Gateway EIPs are FREE (NAT Gateway itself is charged)
                notes = f"Attached to NAT Gateway/ENI ({association_id[:20]}...) - FREE"
            
            total += cost
            self._add_resource_cost('EIP', public_ip, public_ip, cost, notes)
        
        self._add_service_cost('Elastic IPs', total, f"{chargeable} chargeable")
        print(f"  │   └── EIPs: ${total:.2f}/month ({chargeable} chargeable)")
        return total
    
    def _estimate_nat_costs(self, nat_gateways: List[Dict]) -> float:
        """Estimate NAT Gateway costs using regional pricing and CloudWatch metrics"""
        print("  ├── Estimating NAT Gateway costs...")
        
        total = 0
        active_count = 0
        
        # Try to get CloudWatch metrics for actual data transfer
        cw_metrics = None
        try:
            from modules.cloudwatch_metrics import CloudWatchMetrics
            cw_metrics = CloudWatchMetrics(self.session, self.region)
        except Exception:
            pass
        
        for nat in nat_gateways:
            state = nat.get('state', 'unknown')
            nat_id = nat.get('nat_gateway_id', '')
            name = nat.get('name', nat_id)
            
            if state == 'available':
                active_count += 1
                
                # Try to get actual data transfer from CloudWatch
                actual_gb = None
                estimate_type = "usage_estimated"
                
                if cw_metrics:
                    metrics = cw_metrics.get_nat_gateway_bytes(nat_id, days=30)
                    if metrics['data_available']:
                        actual_gb = metrics['total_gb']
                        estimate_type = "cloudwatch_actual"
                
                # Calculate cost
                if actual_gb is not None:
                    cost = self.pricing.get_nat_gateway_monthly(estimated_gb=actual_gb)
                    notes = f"✅ ACTUAL: Base + {actual_gb:.1f}GB from CloudWatch"
                else:
                    cost = self.pricing.get_nat_gateway_monthly(estimated_gb=100)
                    notes = "⚠️ USAGE-ESTIMATED: Base + ~100GB (no CloudWatch data)"
                
                total += cost
                self._add_resource_cost(
                    'NAT Gateway', nat_id, name, cost, notes,
                    estimate_type=estimate_type
                )
        
        self._add_service_cost('NAT Gateway', total, f"{active_count} active")
        print(f"  │   └── NAT: ${total:.2f}/month ({active_count} gateways)")
        return total

    def _estimate_lb_costs(self, load_balancers: List[Dict]) -> float:
        """Estimate Load Balancer costs using regional pricing and CloudWatch metrics"""
        print("  ├── Estimating Load Balancer costs...")
        
        total = 0
        
        # Try to get CloudWatch metrics for actual LCU usage
        cw_metrics = None
        try:
            from modules.cloudwatch_metrics import CloudWatchMetrics
            cw_metrics = CloudWatchMetrics(self.session, self.region)
        except Exception:
            pass
        
        for lb in load_balancers:
            lb_type = lb.get('type', 'application')
            state = lb.get('state', 'unknown')
            name = lb.get('name', '')
            arn = lb.get('arn', '')
            
            if state != 'active':
                continue
            
            estimate_type = "usage_estimated"
            
            if lb_type == 'application':
                # Try to get actual LCU usage from CloudWatch
                actual_lcus = None
                if cw_metrics and arn:
                    metrics = cw_metrics.get_alb_lcu_usage(arn, days=30)
                    if metrics['data_available']:
                        actual_lcus = metrics['avg_lcus_per_hour']
                        estimate_type = "cloudwatch_actual"
                
                if actual_lcus is not None:
                    cost = self.pricing.get_alb_monthly(estimated_lcus=actual_lcus)
                    notes = f"✅ ACTUAL: ALB base + {actual_lcus:.1f} avg LCUs from CloudWatch"
                else:
                    cost = self.pricing.get_alb_monthly(estimated_lcus=10)
                    notes = "⚠️ USAGE-ESTIMATED: ALB base + ~10 LCUs (no CloudWatch data)"
                    
            elif lb_type == 'network':
                hourly = self.pricing.get_other_price('nlb_hourly')
                cost = hourly * HOURS_PER_MONTH
                notes = "⚠️ USAGE-ESTIMATED: NLB base (LCUs not included)"
            else:
                hourly = self.pricing.get_other_price('clb_hourly')
                cost = hourly * HOURS_PER_MONTH
                notes = "CLB base cost"
            
            total += cost
            self._add_resource_cost('Load Balancer', name, name, cost, notes,
                                   estimate_type=estimate_type)
        
        self._add_service_cost('Elastic Load Balancing', total, 
                               f"{len(load_balancers)} load balancers")
        print(f"  │   └── LBs: ${total:.2f}/month")
        return total
    
    def _estimate_rds_costs(self, rds_instances: List[Dict]) -> float:
        """Estimate RDS costs using regional pricing"""
        print("  ├── Estimating RDS costs...")
        
        total = 0
        
        for rds in rds_instances:
            instance_class = rds.get('instance_class', 'db.t3.micro')
            status = rds.get('status', 'unknown')
            storage_gb = rds.get('allocated_storage', 20)
            db_id = rds.get('db_instance_identifier', '')
            
            if status not in ['available', 'backing-up']:
                continue
            
            pricing_key = f"rds_{instance_class}"
            instance_cost = self.pricing.get_other_price(pricing_key)
            if instance_cost == 0:
                instance_cost = self.pricing.get_other_price('rds_db.t3.medium')
            
            storage_cost = storage_gb * self.pricing.get_other_price('rds_storage_gp2')
            cost = instance_cost + storage_cost
            total += cost
            
            self._add_resource_cost(
                'RDS', db_id, db_id, cost,
                f"{instance_class}, {storage_gb}GB storage"
            )
        
        self._add_service_cost('Amazon RDS', total, f"{len(rds_instances)} instances")
        print(f"  │   └── RDS: ${total:.2f}/month")
        return total

    def _estimate_s3_costs(self, buckets: List[Dict]) -> float:
        """Estimate S3 costs using regional pricing"""
        print("  ├── Estimating S3 costs...")
        
        avg_size_gb = 5
        price_per_gb = self.pricing.get_other_price('s3_standard_gb')
        cost_per_bucket = avg_size_gb * price_per_gb
        total = len(buckets) * cost_per_bucket
        
        self._add_service_cost('Amazon S3', total, 
                               f"{len(buckets)} buckets (~{avg_size_gb}GB avg estimate)")
        print(f"  │   └── S3: ${total:.2f}/month (estimated)")
        return total
    
    def _estimate_lambda_costs(self, functions: List[Dict]) -> float:
        """Estimate Lambda costs (global pricing)"""
        print("  ├── Estimating Lambda costs...")
        
        total = 0
        
        for func in functions:
            memory = func.get('memory', 128)
            gb_seconds = (memory / 1024) * 0.2 * 100000
            cost = gb_seconds * self.pricing.get_other_price('lambda_gb_seconds')
            cost += 0.10
            total += cost
        
        self._add_service_cost('AWS Lambda', round(total, 2), 
                               f"{len(functions)} functions (estimated usage)")
        print(f"  │   └── Lambda: ${total:.2f}/month (estimated)")
        return total
    
    def _estimate_ecr_costs(self, repositories: List[Dict]) -> float:
        """Estimate ECR costs"""
        print("  ├── Estimating ECR costs...")
        
        avg_size_gb = 2
        price_per_gb = self.pricing.get_other_price('ecr_storage_gb')
        total = len(repositories) * avg_size_gb * price_per_gb
        
        self._add_service_cost('Amazon ECR', round(total, 2), 
                               f"{len(repositories)} repositories")
        print(f"  │   └── ECR: ${total:.2f}/month (estimated)")
        return total
    
    def _estimate_secrets_costs(self, secrets: List[Dict]) -> float:
        """Estimate Secrets Manager costs"""
        print("  ├── Estimating Secrets costs...")
        
        price_per_secret = self.pricing.get_other_price('secrets_manager')
        total = len(secrets) * price_per_secret
        
        self._add_service_cost('AWS Secrets Manager', round(total, 2), 
                               f"{len(secrets)} secrets")
        print(f"  │   └── Secrets: ${total:.2f}/month")
        return total

    def _estimate_cloudfront_costs(self, distributions: List[Dict]) -> float:
        """Estimate CloudFront costs using regional pricing"""
        print("  ├── Estimating CloudFront costs...")
        
        estimated_gb = 50
        price_per_gb = self.pricing.get_other_price('cloudfront_gb')
        total = len(distributions) * estimated_gb * price_per_gb
        
        self._add_service_cost('Amazon CloudFront', round(total, 2), 
                               f"{len(distributions)} distributions")
        print(f"  │   └── CloudFront: ${total:.2f}/month (estimated)")
        return total
    
    def _estimate_ecs_costs(self, clusters: List[Dict]) -> float:
        """Estimate ECS costs (compute in EC2/Fargate)"""
        print("  └── Estimating ECS costs...")
        
        total = 0
        self._add_service_cost('Amazon ECS', total, 
                               f"{len(clusters)} clusters (compute counted in EC2)")
        print(f"      └── ECS: ${total:.2f}/month (compute counted in EC2)")
        return total
    
    def get_summary(self) -> Dict[str, Any]:
        """Get cost estimation summary"""
        top_services = list(self.results['by_service'].items())[:5]
        
        return {
            'estimated_monthly_total': self.results['estimated_total'],
            'pricing_region': self.region,
            'top_services': [
                {'service': svc, 'cost': data['cost']} 
                for svc, data in top_services
            ],
            'estimation_method': self.results['estimation_method'],
            'accuracy_note': self.results['accuracy_note']
        }


if __name__ == "__main__":
    # Test with different regions
    print("Testing Multi-Region Pricing\n" + "="*50)
    
    sample_inventory = {
        'ec2_instances': [
            {'instance_id': 'i-123', 'instance_type': 't3.micro', 'state': 'running', 'name': 'test'},
            {'instance_id': 'i-456', 'instance_type': 'c5.xlarge', 'state': 'running', 'name': 'prod'},
        ],
        'ec2_volumes': [
            {'volume_id': 'vol-123', 'size_gb': 100, 'volume_type': 'gp3', 'state': 'in-use'},
        ],
        'nat_gateways': [
            {'nat_gateway_id': 'nat-123', 'state': 'available', 'name': 'test-nat'}
        ]
    }
    
    # Test different regions
    for region in ["us-east-1", "ap-south-1", "eu-west-1", "ap-northeast-1"]:
        print(f"\n{'='*50}")
        print(f"Region: {region}")
        print('='*50)
        estimator = CostEstimator(region=region)
        results = estimator.estimate_from_inventory(sample_inventory)
        print(f"\nTotal Estimated: ${results['estimated_total']:.2f}/month")

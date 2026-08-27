"""
AWS Health Check Tool - Live Pricing API Module
Fetches real-time pricing from AWS Pricing API with fallback to static tables.
"""

import boto3
import json
from typing import Dict, Optional, Any
from functools import lru_cache


class AWSPricingAPI:
    """Fetches live pricing from AWS Pricing API"""
    
    # AWS Pricing API is only available in us-east-1 and ap-south-1
    PRICING_REGIONS = ['us-east-1', 'ap-south-1']
    
    # Region code to location name mapping (required for Pricing API filters)
    REGION_TO_LOCATION = {
        'us-east-1': 'US East (N. Virginia)',
        'us-east-2': 'US East (Ohio)',
        'us-west-1': 'US West (N. California)',
        'us-west-2': 'US West (Oregon)',
        'eu-west-1': 'EU (Ireland)',
        'eu-west-2': 'EU (London)',
        'eu-west-3': 'EU (Paris)',
        'eu-central-1': 'EU (Frankfurt)',
        'eu-north-1': 'EU (Stockholm)',
        'ap-south-1': 'Asia Pacific (Mumbai)',
        'ap-southeast-1': 'Asia Pacific (Singapore)',
        'ap-southeast-2': 'Asia Pacific (Sydney)',
        'ap-northeast-1': 'Asia Pacific (Tokyo)',
        'ap-northeast-2': 'Asia Pacific (Seoul)',
        'ap-northeast-3': 'Asia Pacific (Osaka)',
        'sa-east-1': 'South America (Sao Paulo)',
        'ca-central-1': 'Canada (Central)',
        'me-south-1': 'Middle East (Bahrain)',
        'af-south-1': 'Africa (Cape Town)',
    }
    
    def __init__(self, session: Optional[boto3.Session] = None):
        """Initialize with boto3 session"""
        self.session = session or boto3.Session()
        self._pricing_client = None
        self._api_available = None
        self._cache = {}
    
    @property
    def pricing_client(self):
        """Lazy-load pricing client"""
        if self._pricing_client is None:
            try:
                # Pricing API only available in us-east-1
                self._pricing_client = self.session.client('pricing', region_name='us-east-1')
                self._api_available = True
            except Exception as e:
                print(f"  ⚠️  Pricing API not available: {e}")
                self._api_available = False
        return self._pricing_client
    
    def is_available(self) -> bool:
        """Check if Pricing API is accessible"""
        if self._api_available is None:
            try:
                _ = self.pricing_client
            except:
                self._api_available = False
        return self._api_available

    def get_ec2_price(self, instance_type: str, region: str) -> Optional[float]:
        """
        Get EC2 on-demand hourly price from AWS Pricing API
        
        Args:
            instance_type: e.g., 't3.micro', 'c5.xlarge'
            region: AWS region code e.g., 'ap-south-1'
            
        Returns:
            Hourly price in USD or None if not found
        """
        cache_key = f"ec2_{instance_type}_{region}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        if not self.is_available():
            return None
        
        location = self.REGION_TO_LOCATION.get(region)
        if not location:
            return None
        
        try:
            response = self.pricing_client.get_products(
                ServiceCode='AmazonEC2',
                Filters=[
                    {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                    {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location},
                    {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': 'Linux'},
                    {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'},
                    {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': 'NA'},
                    {'Type': 'TERM_MATCH', 'Field': 'capacitystatus', 'Value': 'Used'},
                ],
                MaxResults=1
            )
            
            if response['PriceList']:
                price_data = json.loads(response['PriceList'][0])
                price = self._extract_on_demand_price(price_data)
                self._cache[cache_key] = price
                return price
                
        except Exception as e:
            # Silently fail - will use static fallback
            pass
        
        return None
    
    def get_ebs_price(self, volume_type: str, region: str) -> Optional[float]:
        """
        Get EBS price per GB-month from AWS Pricing API
        
        Args:
            volume_type: e.g., 'gp3', 'gp2', 'io1'
            region: AWS region code
            
        Returns:
            Price per GB-month in USD or None if not found
        """
        cache_key = f"ebs_{volume_type}_{region}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        if not self.is_available():
            return None
        
        location = self.REGION_TO_LOCATION.get(region)
        if not location:
            return None
        
        # Map volume types to product family names
        volume_family_map = {
            'gp2': 'General Purpose',
            'gp3': 'General Purpose',
            'io1': 'Provisioned IOPS',
            'io2': 'Provisioned IOPS',
            'st1': 'Throughput Optimized HDD',
            'sc1': 'Cold HDD',
            'standard': 'Magnetic',
        }
        
        try:
            response = self.pricing_client.get_products(
                ServiceCode='AmazonEC2',
                Filters=[
                    {'Type': 'TERM_MATCH', 'Field': 'volumeApiName', 'Value': volume_type},
                    {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location},
                    {'Type': 'TERM_MATCH', 'Field': 'productFamily', 'Value': 'Storage'},
                ],
                MaxResults=5
            )
            
            for price_item in response['PriceList']:
                price_data = json.loads(price_item)
                # Look for the GB-month price
                price = self._extract_on_demand_price(price_data)
                if price and price < 1:  # EBS prices are typically < $1/GB
                    self._cache[cache_key] = price
                    return price
                    
        except Exception as e:
            pass
        
        return None

    def get_nat_gateway_price(self, region: str) -> Dict[str, Optional[float]]:
        """
        Get NAT Gateway pricing from AWS Pricing API
        
        Returns:
            Dict with 'hourly' and 'per_gb' prices or None values
        """
        cache_key = f"nat_{region}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        result = {'hourly': None, 'per_gb': None}
        
        if not self.is_available():
            return result
        
        location = self.REGION_TO_LOCATION.get(region)
        if not location:
            return result
        
        try:
            response = self.pricing_client.get_products(
                ServiceCode='AmazonEC2',
                Filters=[
                    {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location},
                    {'Type': 'TERM_MATCH', 'Field': 'productFamily', 'Value': 'NAT Gateway'},
                ],
                MaxResults=10
            )
            
            for price_item in response['PriceList']:
                price_data = json.loads(price_item)
                attrs = price_data.get('product', {}).get('attributes', {})
                group = attrs.get('group', '')
                price = self._extract_on_demand_price(price_data)
                
                if price:
                    if 'Hour' in group or 'NatGateway' in group:
                        result['hourly'] = price
                    elif 'Bytes' in group or 'Data' in group:
                        result['per_gb'] = price
            
            self._cache[cache_key] = result
            
        except Exception as e:
            pass
        
        return result
    
    def get_alb_price(self, region: str) -> Dict[str, Optional[float]]:
        """
        Get Application Load Balancer pricing from AWS Pricing API
        
        Returns:
            Dict with 'hourly' and 'lcu' prices or None values
        """
        cache_key = f"alb_{region}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        result = {'hourly': None, 'lcu': None}
        
        if not self.is_available():
            return result
        
        location = self.REGION_TO_LOCATION.get(region)
        if not location:
            return result
        
        try:
            response = self.pricing_client.get_products(
                ServiceCode='AWSELB',
                Filters=[
                    {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location},
                    {'Type': 'TERM_MATCH', 'Field': 'productFamily', 'Value': 'Load Balancer-Application'},
                ],
                MaxResults=10
            )
            
            for price_item in response['PriceList']:
                price_data = json.loads(price_item)
                attrs = price_data.get('product', {}).get('attributes', {})
                usage_type = attrs.get('usagetype', '')
                price = self._extract_on_demand_price(price_data)
                
                if price:
                    if 'LoadBalancerUsage' in usage_type:
                        result['hourly'] = price
                    elif 'LCUUsage' in usage_type:
                        result['lcu'] = price
            
            self._cache[cache_key] = result
            
        except Exception as e:
            pass
        
        return result

    def get_rds_price(self, instance_class: str, region: str, 
                      engine: str = 'MySQL') -> Optional[float]:
        """
        Get RDS on-demand hourly price from AWS Pricing API
        
        Args:
            instance_class: e.g., 'db.t3.micro', 'db.r5.large'
            region: AWS region code
            engine: Database engine (MySQL, PostgreSQL, etc.)
            
        Returns:
            Hourly price in USD or None if not found
        """
        cache_key = f"rds_{instance_class}_{region}_{engine}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        if not self.is_available():
            return None
        
        location = self.REGION_TO_LOCATION.get(region)
        if not location:
            return None
        
        try:
            response = self.pricing_client.get_products(
                ServiceCode='AmazonRDS',
                Filters=[
                    {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_class},
                    {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location},
                    {'Type': 'TERM_MATCH', 'Field': 'databaseEngine', 'Value': engine},
                    {'Type': 'TERM_MATCH', 'Field': 'deploymentOption', 'Value': 'Single-AZ'},
                ],
                MaxResults=1
            )
            
            if response['PriceList']:
                price_data = json.loads(response['PriceList'][0])
                price = self._extract_on_demand_price(price_data)
                self._cache[cache_key] = price
                return price
                
        except Exception as e:
            pass
        
        return None
    
    def _extract_on_demand_price(self, price_data: Dict) -> Optional[float]:
        """Extract on-demand price from AWS Pricing API response"""
        try:
            terms = price_data.get('terms', {}).get('OnDemand', {})
            for term_key, term_value in terms.items():
                price_dimensions = term_value.get('priceDimensions', {})
                for dim_key, dim_value in price_dimensions.items():
                    price_per_unit = dim_value.get('pricePerUnit', {})
                    usd_price = price_per_unit.get('USD')
                    if usd_price:
                        return float(usd_price)
        except Exception:
            pass
        return None
    
    def clear_cache(self):
        """Clear the pricing cache"""
        self._cache = {}
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        return {
            'cached_items': len(self._cache),
            'api_available': self._api_available
        }


# Singleton instance for reuse
_pricing_api_instance = None

def get_pricing_api(session: Optional[boto3.Session] = None) -> AWSPricingAPI:
    """Get or create singleton pricing API instance"""
    global _pricing_api_instance
    if _pricing_api_instance is None:
        _pricing_api_instance = AWSPricingAPI(session)
    return _pricing_api_instance

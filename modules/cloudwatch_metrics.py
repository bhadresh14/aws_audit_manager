"""
AWS Health Check Tool - CloudWatch Metrics Module
Fetches actual usage metrics for more accurate cost estimation.
"""

import boto3
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any


class CloudWatchMetrics:
    """Fetches CloudWatch metrics for accurate usage-based cost estimation"""
    
    def __init__(self, session: Optional[boto3.Session] = None, region: str = None):
        """Initialize with boto3 session"""
        self.session = session or boto3.Session()
        self.region = region or self.session.region_name or 'us-east-1'
        self._cw_client = None
    
    @property
    def cw_client(self):
        """Lazy-load CloudWatch client"""
        if self._cw_client is None:
            self._cw_client = self.session.client('cloudwatch', region_name=self.region)
        return self._cw_client
    
    def get_nat_gateway_bytes(self, nat_gateway_id: str, days: int = 30) -> Dict[str, float]:
        """
        Get NAT Gateway data transfer metrics for the last N days
        
        Args:
            nat_gateway_id: NAT Gateway ID (e.g., 'nat-07bba2f964f653bd3')
            days: Number of days to look back (default 30)
            
        Returns:
            Dict with 'bytes_in', 'bytes_out', 'total_gb' metrics
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        
        result = {
            'bytes_in': 0,
            'bytes_out': 0,
            'total_gb': 0,
            'data_available': False
        }
        
        try:
            # Get BytesOutToDestination (data processed)
            bytes_out = self._get_metric_sum(
                namespace='AWS/NATGateway',
                metric_name='BytesOutToDestination',
                dimensions=[{'Name': 'NatGatewayId', 'Value': nat_gateway_id}],
                start_time=start_time,
                end_time=end_time
            )
            
            # Get BytesInFromDestination
            bytes_in = self._get_metric_sum(
                namespace='AWS/NATGateway',
                metric_name='BytesInFromDestination',
                dimensions=[{'Name': 'NatGatewayId', 'Value': nat_gateway_id}],
                start_time=start_time,
                end_time=end_time
            )
            
            if bytes_out is not None or bytes_in is not None:
                result['bytes_out'] = bytes_out or 0
                result['bytes_in'] = bytes_in or 0
                result['total_gb'] = (result['bytes_out'] + result['bytes_in']) / (1024**3)
                result['data_available'] = True
                
        except Exception as e:
            # CloudWatch metrics not available
            pass
        
        return result

    def get_alb_lcu_usage(self, load_balancer_arn: str, days: int = 30) -> Dict[str, float]:
        """
        Get ALB Load Balancer Capacity Unit (LCU) usage metrics
        
        Args:
            load_balancer_arn: Full ARN of the ALB
            days: Number of days to look back (default 30)
            
        Returns:
            Dict with LCU metrics
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        
        # Extract the load balancer name from ARN for dimension
        # ARN format: arn:aws:elasticloadbalancing:region:account:loadbalancer/app/name/id
        lb_dimension = '/'.join(load_balancer_arn.split('/')[-3:]) if '/' in load_balancer_arn else load_balancer_arn
        
        result = {
            'consumed_lcus': 0,
            'avg_lcus_per_hour': 0,
            'data_available': False
        }
        
        try:
            # Get ConsumedLCUs - the number of LCUs used
            consumed = self._get_metric_sum(
                namespace='AWS/ApplicationELB',
                metric_name='ConsumedLCUs',
                dimensions=[{'Name': 'LoadBalancer', 'Value': lb_dimension}],
                start_time=start_time,
                end_time=end_time
            )
            
            if consumed is not None:
                result['consumed_lcus'] = consumed
                # Calculate average per hour over the period
                hours = days * 24
                result['avg_lcus_per_hour'] = consumed / hours if hours > 0 else 0
                result['data_available'] = True
                
        except Exception as e:
            pass
        
        return result
    
    def get_alb_request_count(self, load_balancer_arn: str, days: int = 30) -> Dict[str, float]:
        """
        Get ALB request count metrics
        
        Args:
            load_balancer_arn: Full ARN of the ALB
            days: Number of days to look back (default 30)
            
        Returns:
            Dict with request count metrics
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        
        lb_dimension = '/'.join(load_balancer_arn.split('/')[-3:]) if '/' in load_balancer_arn else load_balancer_arn
        
        result = {
            'request_count': 0,
            'avg_requests_per_second': 0,
            'data_available': False
        }
        
        try:
            request_count = self._get_metric_sum(
                namespace='AWS/ApplicationELB',
                metric_name='RequestCount',
                dimensions=[{'Name': 'LoadBalancer', 'Value': lb_dimension}],
                start_time=start_time,
                end_time=end_time
            )
            
            if request_count is not None:
                result['request_count'] = request_count
                seconds = days * 24 * 3600
                result['avg_requests_per_second'] = request_count / seconds if seconds > 0 else 0
                result['data_available'] = True
                
        except Exception as e:
            pass
        
        return result

    def get_ec2_cpu_utilization(self, instance_id: str, days: int = 14) -> Dict[str, float]:
        """
        Get EC2 CPU utilization metrics
        
        Args:
            instance_id: EC2 instance ID
            days: Number of days to look back (default 14)
            
        Returns:
            Dict with CPU metrics
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        
        result = {
            'avg_cpu': 0,
            'max_cpu': 0,
            'data_available': False
        }
        
        try:
            # Get average CPU
            avg_cpu = self._get_metric_avg(
                namespace='AWS/EC2',
                metric_name='CPUUtilization',
                dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                start_time=start_time,
                end_time=end_time
            )
            
            # Get max CPU
            max_cpu = self._get_metric_max(
                namespace='AWS/EC2',
                metric_name='CPUUtilization',
                dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                start_time=start_time,
                end_time=end_time
            )
            
            if avg_cpu is not None:
                result['avg_cpu'] = round(avg_cpu, 2)
                result['max_cpu'] = round(max_cpu or 0, 2)
                result['data_available'] = True
                
        except Exception as e:
            pass
        
        return result
    
    def _get_metric_sum(self, namespace: str, metric_name: str, 
                        dimensions: List[Dict], start_time: datetime, 
                        end_time: datetime) -> Optional[float]:
        """Get sum of metric values over the period"""
        try:
            response = self.cw_client.get_metric_statistics(
                Namespace=namespace,
                MetricName=metric_name,
                Dimensions=dimensions,
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,  # 1 day
                Statistics=['Sum']
            )
            
            datapoints = response.get('Datapoints', [])
            if datapoints:
                return sum(dp['Sum'] for dp in datapoints)
                
        except Exception:
            pass
        return None
    
    def _get_metric_avg(self, namespace: str, metric_name: str,
                        dimensions: List[Dict], start_time: datetime,
                        end_time: datetime) -> Optional[float]:
        """Get average of metric values over the period"""
        try:
            response = self.cw_client.get_metric_statistics(
                Namespace=namespace,
                MetricName=metric_name,
                Dimensions=dimensions,
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,
                Statistics=['Average']
            )
            
            datapoints = response.get('Datapoints', [])
            if datapoints:
                return sum(dp['Average'] for dp in datapoints) / len(datapoints)
                
        except Exception:
            pass
        return None
    
    def _get_metric_max(self, namespace: str, metric_name: str,
                        dimensions: List[Dict], start_time: datetime,
                        end_time: datetime) -> Optional[float]:
        """Get maximum of metric values over the period"""
        try:
            response = self.cw_client.get_metric_statistics(
                Namespace=namespace,
                MetricName=metric_name,
                Dimensions=dimensions,
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,
                Statistics=['Maximum']
            )
            
            datapoints = response.get('Datapoints', [])
            if datapoints:
                return max(dp['Maximum'] for dp in datapoints)
                
        except Exception:
            pass
        return None


def get_nat_monthly_data_gb(session: boto3.Session, region: str, 
                            nat_gateway_id: str) -> float:
    """
    Convenience function to get estimated monthly NAT Gateway data transfer
    
    Args:
        session: boto3 Session
        region: AWS region
        nat_gateway_id: NAT Gateway ID
        
    Returns:
        Estimated monthly data transfer in GB (extrapolated from last 30 days)
    """
    cw = CloudWatchMetrics(session, region)
    metrics = cw.get_nat_gateway_bytes(nat_gateway_id, days=30)
    
    if metrics['data_available']:
        return metrics['total_gb']
    
    # Default estimate if no data
    return 100.0


def get_alb_monthly_lcus(session: boto3.Session, region: str,
                         load_balancer_arn: str) -> float:
    """
    Convenience function to get estimated monthly ALB LCU usage
    
    Args:
        session: boto3 Session
        region: AWS region
        load_balancer_arn: ALB ARN
        
    Returns:
        Estimated average LCUs per hour
    """
    cw = CloudWatchMetrics(session, region)
    metrics = cw.get_alb_lcu_usage(load_balancer_arn, days=30)
    
    if metrics['data_available']:
        return metrics['avg_lcus_per_hour']
    
    # Default estimate if no data
    return 10.0

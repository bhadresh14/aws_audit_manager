"""
AWS Health Check Tool - Cost Analyzer Module
Analyzes AWS costs, trends, and forecasts
Includes fallback cost estimation when billing API access is unavailable
"""

import boto3
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import get_cost_dates, COST_LOOKBACK_DAYS


class CostAnalyzer:
    """Analyzes AWS costs and provides insights"""
    
    def __init__(self, session: Optional[boto3.Session] = None, region: str = None):
        """Initialize with optional boto3 session and region filter"""
        self.session = session or boto3.Session()
        self.ce_client = self.session.client('ce', region_name='us-east-1')  # Cost Explorer is global
        self.region = region or self.session.region_name  # Region to filter costs by
        self.dates = get_cost_dates()
        self.billing_access = True  # Will be set to False if API fails
        self.results = {
            "total_cost": 0,
            "cost_by_service": [],
            "cost_by_region": [],
            "cost_trend": [],
            "forecast": None,
            "top_cost_drivers": [],
            "anomalies": [],
            "recommendations": [],
            "data_source": "billing_api",  # or "estimated"
            "estimation_note": None
        }
    
    def run_all_checks(self, inventory: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Run all cost analysis checks
        
        Args:
            inventory: Optional resource inventory for cost estimation fallback
        """
        print("💰 Running Cost Analysis...")
        
        # Try to get cost data from billing API
        self.get_cost_by_service()
        
        # Check if billing access failed OR if we got $0 with resources (likely permission issue)
        has_resources = inventory and (
            inventory.get('ec2_instances') or 
            inventory.get('rds_instances') or 
            inventory.get('nat_gateways') or
            inventory.get('load_balancers')
        )
        
        if (self.results['total_cost'] == 0 and has_resources) or not self.billing_access:
            print("  ⚠️  Billing shows $0 but resources exist - using cost estimation from inventory...")
            if inventory:
                self._estimate_costs_from_inventory(inventory)
            else:
                print("  ⚠️  No inventory provided for cost estimation")
                self.results['estimation_note'] = "Billing access denied and no inventory available for estimation"
        else:
            # Continue with normal billing API calls
            self.get_cost_by_region()
            self.get_daily_cost_trend()
            self.get_cost_forecast()
            self.get_cost_anomalies()
            self.analyze_cost_drivers()
        
        self.generate_recommendations()
        
        return self.results
    
    def _estimate_costs_from_inventory(self, inventory: Dict[str, Any]):
        """
        Estimate costs from resource inventory when billing API is unavailable
        """
        from modules.cost_estimator import CostEstimator
        
        # Get region from session for accurate regional pricing
        region = self.session.region_name or 'us-east-1'
        
        print(f"  ├── Using Cost Estimator module (Region: {region})...")
        
        estimator = CostEstimator(self.session, region=region)
        estimated = estimator.estimate_from_inventory(inventory)
        
        # Update results with estimated data
        self.results['total_cost'] = estimated['estimated_total']
        self.results['data_source'] = 'estimated'
        self.results['estimation_note'] = estimated['accuracy_note']
        
        # Convert estimated by_service to cost_by_service format
        total = estimated['estimated_total']
        services = []
        for service, data in estimated['by_service'].items():
            if data['cost'] > 0:
                services.append({
                    'service': service,
                    'cost': round(data['cost'], 2),
                    'currency': 'USD',
                    'percentage': round((data['cost'] / total * 100), 1) if total > 0 else 0
                })
        
        self.results['cost_by_service'] = services
        self.results['estimated_details'] = estimated
        
        print(f"  └── Estimated Total: ${estimated['estimated_total']:.2f}/month")
    
    def get_cost_by_service(self) -> List[Dict]:
        """Get cost breakdown by AWS service - account-wide (not filtered by region)"""
        print(f"  ├── Analyzing costs by service (Account-wide, current month)...")
        
        try:
            # Get current month costs - account-wide (no region filter)
            response = self.ce_client.get_cost_and_usage(
                TimePeriod={
                    'Start': self.dates['current_month_start'],
                    'End': self.dates['current_month_end']
                },
                Granularity='MONTHLY',
                Metrics=['UnblendedCost', 'UsageQuantity'],
                GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
            )
            
            costs = []
            total = 0
            
            for group in response.get('ResultsByTime', [{}])[0].get('Groups', []):
                service = group['Keys'][0]
                amount = float(group['Metrics']['UnblendedCost']['Amount'])
                
                if amount > 0:
                    costs.append({
                        'service': service,
                        'cost': round(amount, 2),
                        'currency': 'USD'
                    })
                    total += amount
            
            # Sort by cost descending
            costs.sort(key=lambda x: x['cost'], reverse=True)
            
            # Calculate percentages
            for cost in costs:
                cost['percentage'] = round((cost['cost'] / total * 100), 1) if total > 0 else 0
            
            self.results['cost_by_service'] = costs
            self.results['total_cost'] = round(total, 2)
            self.results['data_source'] = 'billing_api'
            
            if total == 0:
                print(f"  │   └── Total: $0.00 - Possible billing access issue or free tier only")
            else:
                print(f"  │   └── Total: ${total:.2f} across {len(costs)} services (current month)")
            
            return costs
            
        except self.ce_client.exceptions.AccessDeniedException as e:
            print(f"  │   └── ❌ ACCESS DENIED: IAM user lacks billing permissions")
            print(f"  │       Tip: Need 'ce:*' permission and IAM billing access enabled")
            self.billing_access = False
            return []
            
        except Exception as e:
            error_msg = str(e)
            if 'AccessDenied' in error_msg or 'not authorized' in error_msg.lower():
                print(f"  │   └── ❌ ACCESS DENIED: {error_msg[:100]}")
                self.billing_access = False
            else:
                print(f"  │   └── Error: {error_msg}")
            return []
    
    def get_cost_by_region(self) -> List[Dict]:
        """Get cost breakdown by AWS region (current month)"""
        print("  ├── Analyzing costs by region...")
        
        try:
            response = self.ce_client.get_cost_and_usage(
                TimePeriod={
                    'Start': self.dates['current_month_start'],
                    'End': self.dates['current_month_end']
                },
                Granularity='MONTHLY',
                Metrics=['UnblendedCost'],
                GroupBy=[{'Type': 'DIMENSION', 'Key': 'REGION'}]
            )
            
            costs = []
            for group in response.get('ResultsByTime', [{}])[0].get('Groups', []):
                region = group['Keys'][0]
                amount = float(group['Metrics']['UnblendedCost']['Amount'])
                
                if amount > 0.01:
                    costs.append({
                        'region': region if region else 'Global',
                        'cost': round(amount, 2)
                    })
            
            costs.sort(key=lambda x: x['cost'], reverse=True)
            self.results['cost_by_region'] = costs
            
            print(f"  │   └── Found costs in {len(costs)} regions")
            
            return costs
            
        except Exception as e:
            print(f"  │   └── Error: {str(e)}")
            return []
    
    def get_daily_cost_trend(self) -> List[Dict]:
        """Get daily cost trend for the last 30 days"""
        print(f"  ├── Analyzing daily cost trend (Region: {self.region})...")
        
        try:
            response = self.ce_client.get_cost_and_usage(
                TimePeriod={
                    'Start': self.dates['last_30_days_start'],
                    'End': self.dates['last_30_days_end']
                },
                Granularity='DAILY',
                Metrics=['UnblendedCost'],
                Filter={
                    'Dimensions': {
                        'Key': 'REGION',
                        'Values': [self.region]
                    }
                }
            )
            
            trend = []
            for result in response.get('ResultsByTime', []):
                date = result['TimePeriod']['Start']
                amount = float(result.get('Total', {}).get('UnblendedCost', {}).get('Amount', 0))
                trend.append({
                    'date': date,
                    'cost': round(amount, 2)
                })
            
            self.results['cost_trend'] = trend
            
            # Calculate average daily cost
            if trend:
                avg_daily = sum(t['cost'] for t in trend) / len(trend)
                print(f"  │   └── Average daily cost: ${avg_daily:.2f}")
            
            return trend
            
        except Exception as e:
            print(f"  │   └── Error: {str(e)}")
            return []
    
    def get_cost_forecast(self) -> Dict:
        """Get cost forecast for next month"""
        print(f"  ├── Generating cost forecast (Region: {self.region})...")
        
        try:
            today = datetime.utcnow().date()
            forecast_end = today + timedelta(days=30)
            
            response = self.ce_client.get_cost_forecast(
                TimePeriod={
                    'Start': today.strftime("%Y-%m-%d"),
                    'End': forecast_end.strftime("%Y-%m-%d")
                },
                Metric='UNBLENDED_COST',
                Granularity='MONTHLY',
                Filter={
                    'Dimensions': {
                        'Key': 'REGION',
                        'Values': [self.region]
                    }
                }
            )
            
            forecast = {
                'predicted_cost': round(float(response.get('Total', {}).get('Amount', 0)), 2),
                'prediction_interval_lower': round(float(response.get('Total', {}).get('Amount', 0)) * 0.9, 2),
                'prediction_interval_upper': round(float(response.get('Total', {}).get('Amount', 0)) * 1.1, 2),
                'currency': 'USD'
            }
            
            self.results['forecast'] = forecast
            print(f"  │   └── Forecast: ${forecast['predicted_cost']:.2f}")
            
            return forecast
            
        except Exception as e:
            print(f"  │   └── Error: {str(e)}")
            return {}
    
    def get_cost_anomalies(self) -> List[Dict]:
        """Detect cost anomalies"""
        print("  ├── Detecting cost anomalies...")
        
        try:
            # Get anomaly monitors
            response = self.ce_client.get_anomaly_monitors()
            monitors = response.get('AnomalyMonitors', [])
            
            anomalies = []
            
            if monitors:
                # Get anomalies from the last 30 days
                today = datetime.utcnow().date()
                start_date = today - timedelta(days=30)
                
                anomaly_response = self.ce_client.get_anomalies(
                    DateInterval={
                        'StartDate': start_date.strftime("%Y-%m-%d"),
                        'EndDate': today.strftime("%Y-%m-%d")
                    },
                    MaxResults=10
                )
                
                for anomaly in anomaly_response.get('Anomalies', []):
                    anomalies.append({
                        'anomaly_id': anomaly.get('AnomalyId'),
                        'start_date': anomaly.get('AnomalyStartDate'),
                        'end_date': anomaly.get('AnomalyEndDate'),
                        'impact': anomaly.get('Impact', {}).get('TotalImpact', 0),
                        'root_causes': anomaly.get('RootCauses', [])
                    })
            
            self.results['anomalies'] = anomalies
            print(f"  │   └── Found {len(anomalies)} anomalies")
            
            return anomalies
            
        except Exception as e:
            # Anomaly detection might not be enabled
            print(f"  │   └── Anomaly detection not available or no anomalies found")
            return []
    
    def analyze_cost_drivers(self) -> List[Dict]:
        """Analyze top cost drivers with usage details"""
        print(f"  ├── Analyzing top cost drivers (Region: {self.region})...")
        
        try:
            # Get EC2 cost breakdown by instance type, filtered by region
            response = self.ce_client.get_cost_and_usage(
                TimePeriod={
                    'Start': self.dates['last_month_start'],
                    'End': self.dates['last_month_end']
                },
                Granularity='MONTHLY',
                Metrics=['UnblendedCost'],
                Filter={
                    'And': [
                        {
                            'Dimensions': {
                                'Key': 'SERVICE',
                                'Values': ['Amazon Elastic Compute Cloud - Compute']
                            }
                        },
                        {
                            'Dimensions': {
                                'Key': 'REGION',
                                'Values': [self.region]
                            }
                        }
                    ]
                },
                GroupBy=[{'Type': 'DIMENSION', 'Key': 'INSTANCE_TYPE'}]
            )
            
            drivers = []
            for group in response.get('ResultsByTime', [{}])[0].get('Groups', []):
                instance_type = group['Keys'][0]
                amount = float(group['Metrics']['UnblendedCost']['Amount'])
                
                if amount > 0:
                    drivers.append({
                        'type': 'EC2',
                        'detail': instance_type,
                        'cost': round(amount, 2)
                    })
            
            drivers.sort(key=lambda x: x['cost'], reverse=True)
            self.results['top_cost_drivers'] = drivers[:10]  # Top 10
            
            print(f"  │   └── Identified {len(drivers)} cost drivers")
            
            return drivers
            
        except Exception as e:
            print(f"  │   └── Error: {str(e)}")
            return []
    
    def generate_recommendations(self) -> List[Dict]:
        """Generate cost optimization recommendations based on analysis"""
        print("  └── Generating recommendations...")
        
        recommendations = []
        
        # Check if EC2 is the top cost
        if self.results['cost_by_service']:
            top_service = self.results['cost_by_service'][0]
            if 'EC2' in top_service['service'] and top_service['percentage'] > 50:
                recommendations.append({
                    'category': 'Compute',
                    'priority': 'High',
                    'title': 'EC2 Dominates Costs',
                    'description': f"EC2 accounts for {top_service['percentage']}% of your costs (${top_service['cost']}). Consider Reserved Instances or Savings Plans.",
                    'potential_savings': f"Up to 40% (${round(top_service['cost'] * 0.4, 2)})"
                })
        
        # Check forecast vs current
        if self.results['forecast'] and self.results['total_cost']:
            if self.results['forecast']['predicted_cost'] > self.results['total_cost'] * 1.1:
                recommendations.append({
                    'category': 'Budget',
                    'priority': 'Medium',
                    'title': 'Cost Increase Predicted',
                    'description': f"Forecast shows ${self.results['forecast']['predicted_cost']} next month, up from ${self.results['total_cost']}.",
                    'potential_savings': 'Review new resources and scaling policies'
                })
        
        # Check regional concentration
        if self.results['cost_by_region']:
            top_region = self.results['cost_by_region'][0]
            if len(self.results['cost_by_region']) == 1:
                recommendations.append({
                    'category': 'Architecture',
                    'priority': 'Low',
                    'title': 'Single Region Deployment',
                    'description': f"All resources in {top_region['region']}. Consider multi-region for DR.",
                    'potential_savings': 'Improved availability'
                })
        
        self.results['recommendations'] = recommendations
        print(f"      └── Generated {len(recommendations)} recommendations")
        
        return recommendations
    
    def get_summary(self) -> Dict:
        """Get a summary of cost analysis"""
        return {
            'total_monthly_cost': self.results['total_cost'],
            'top_service': self.results['cost_by_service'][0] if self.results['cost_by_service'] else None,
            'services_count': len(self.results['cost_by_service']),
            'forecast': self.results['forecast'],
            'anomalies_count': len(self.results['anomalies']),
            'recommendations_count': len(self.results['recommendations'])
        }


if __name__ == "__main__":
    # Test the module
    analyzer = CostAnalyzer()
    results = analyzer.run_all_checks()
    
    print("\n" + "="*50)
    print("COST ANALYSIS SUMMARY")
    print("="*50)
    print(f"Total Monthly Cost: ${results['total_cost']:.2f}")
    print(f"\nTop 5 Services:")
    for svc in results['cost_by_service'][:5]:
        print(f"  - {svc['service']}: ${svc['cost']:.2f} ({svc['percentage']}%)")

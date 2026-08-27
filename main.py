#!/usr/bin/env python3
"""
AWS Health Check Tool
====================
A comprehensive tool for analyzing AWS infrastructure health,
costs, security, and optimization opportunities.

Usage:
    python main.py [--profile PROFILE] [--region REGION] [--output-dir DIR]

Author: Cloud Engineering Team
Version: 1.0.0
"""

import argparse
import boto3
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.cost_analyzer import CostAnalyzer
from modules.resource_inventory import ResourceInventory
from modules.security_audit import SecurityAudit
from modules.optimizer import Optimizer
from reports.report_generator import ReportGenerator


class AWSHealthCheck:
    """Main class for AWS Health Check Tool"""
    
    def __init__(self, profile: str = None, region: str = None):
        """Initialize the health check tool"""
        self.profile = profile
        self.region = region
        self.scan_all_regions = (region == 'all')
        self.session = self._create_session()
        self.account_info = self._get_account_info()
        
        # Determine regions to scan
        if self.scan_all_regions:
            # Use a focused list of major regions for faster scanning
            regions = ["us-east-1", "us-west-2", "eu-west-1", "eu-central-1",
                       "ap-south-1", "ap-southeast-1", "ap-northeast-1"]
            self.region = None
            self.account_info['region'] = 'all-regions'
        else:
            regions = [self.region] if self.region else [self.session.region_name or 'us-east-1']
            if not self.region:
                self.region = regions[0]
                self.account_info['region'] = regions[0]
        
        # Initialize modules
        self.cost_analyzer = CostAnalyzer(self.session, region=regions[0] if not self.scan_all_regions else 'us-east-1')
        self.resource_inventory = ResourceInventory(self.session, regions)
        self.security_audit = SecurityAudit(self.session, regions)
        self.optimizer = Optimizer(self.session, regions)

    def _create_session(self) -> boto3.Session:
        """Create boto3 session with optional profile"""
        try:
            session_region = None if self.scan_all_regions else self.region
            if self.profile:
                session = boto3.Session(profile_name=self.profile, region_name=session_region)
            else:
                session = boto3.Session(region_name=session_region)
            return session
        except Exception as e:
            print(f"❌ Error creating AWS session: {e}")
            sys.exit(1)
    
    def _get_account_info(self) -> dict:
        """Get AWS account information"""
        try:
            sts = self.session.client('sts')
            identity = sts.get_caller_identity()
            
            return {
                'account_id': identity['Account'],
                'user_arn': identity['Arn'],
                'user_id': identity['UserId'],
                'region': 'all-regions' if self.scan_all_regions else (self.session.region_name or 'us-east-1')
            }
        except Exception as e:
            print(f"❌ Error getting account info: {e}")
            print("Please ensure your AWS credentials are configured correctly.")
            sys.exit(1)
    
    def run_full_check(self, output_dir: str = "output") -> dict:
        """Run all health checks and generate reports"""
        print("\n" + "="*60)
        print("   AWS HEALTH CHECK TOOL")
        print("="*60)
        print(f"   Account: {self.account_info['account_id']}")
        print(f"   Region:  {self.account_info['region']}")
        print(f"   User:    {self.account_info['user_arn']}")
        print("="*60 + "\n")
        
        results = {}
        
        # Run Resource Inventory FIRST (needed for cost estimation fallback)
        print("\n" + "-"*50)
        results['inventory'] = self.resource_inventory.run_all_checks()
        
        # Run Cost Analysis (with inventory for fallback estimation)
        print("\n" + "-"*50)
        results['cost'] = self.cost_analyzer.run_all_checks(inventory=results['inventory'])
        
        # Run Security Audit
        print("\n" + "-"*50)
        results['security'] = self.security_audit.run_all_checks()
        
        # Run Optimization Analysis
        print("\n" + "-"*50)
        results['optimization'] = self.optimizer.run_all_checks()
        
        # Generate Reports
        print("\n" + "-"*50)
        report_gen = ReportGenerator(output_dir)
        reports = report_gen.generate_all_reports(results, self.account_info)
        
        # Print Summary
        self._print_summary(results, reports)
        
        return results

    def _print_summary(self, results: dict, reports: dict):
        """Print final summary"""
        print("\n" + "="*60)
        print("   HEALTH CHECK COMPLETE")
        print("="*60)
        
        # Cost Summary
        cost = results.get('cost', {})
        data_source = cost.get('data_source', 'billing_api')
        print(f"\n💰 COST SUMMARY", end="")
        if data_source == 'estimated':
            print(" (ESTIMATED from inventory)")
        else:
            print("")
        print(f"   Total Monthly Cost: ${cost.get('total_cost', 0):.2f}")
        if cost.get('estimation_note'):
            print(f"   Note: {cost.get('estimation_note')}")
        if cost.get('forecast'):
            print(f"   Forecast (30 days): ${cost['forecast'].get('predicted_cost', 0):.2f}")
        
        # Security Summary
        security = results.get('security', {}).get('summary', {})
        print(f"\n🔒 SECURITY SUMMARY")
        print(f"   Critical: {security.get('critical', 0)}")
        print(f"   High:     {security.get('high', 0)}")
        print(f"   Medium:   {security.get('medium', 0)}")
        print(f"   Low:      {security.get('low', 0)}")
        print(f"   Total:    {security.get('total', 0)}")
        
        # Optimization Summary
        optimization = results.get('optimization', {}).get('summary', {})
        print(f"\n📊 OPTIMIZATION SUMMARY")
        print(f"   Recommendations:      {optimization.get('total_recommendations', 0)}")
        print(f"   Potential Monthly:    ${optimization.get('potential_monthly_savings', 0):.2f}")
        print(f"   Potential Annual:     ${optimization.get('potential_annual_savings', 0):.2f}")
        
        # Resource Summary
        inventory = results.get('inventory', {}).get('summary', {})
        print(f"\n🖥️  RESOURCE SUMMARY")
        print(f"   EC2 Instances:    {inventory.get('total_ec2_instances', 0)}")
        print(f"   RDS Instances:    {inventory.get('total_rds_instances', 0)}")
        print(f"   S3 Buckets:       {inventory.get('total_s3_buckets', 0)}")
        print(f"   Lambda Functions: {inventory.get('total_lambda_functions', 0)}")
        
        # Reports
        print(f"\n📄 REPORTS GENERATED")
        for fmt, path in reports.items():
            print(f"   {fmt.upper()}: {path}")
        
        print("\n" + "="*60)
        print("   Thank you for using AWS Health Check Tool!")
        print("="*60 + "\n")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='AWS Health Check Tool - Analyze infrastructure health, costs, and security',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python main.py                          # Run with default credentials
  python main.py --profile myprofile      # Use specific AWS profile
  python main.py --region us-west-2       # Scan specific region
  python main.py --output-dir ./reports   # Custom output directory

For more information, visit: https://github.com/your-org/aws-health-check
        '''
    )
    
    parser.add_argument(
        '--profile', '-p',
        help='AWS profile name to use (optional)',
        default=None
    )
    
    parser.add_argument(
        '--region', '-r',
        help='AWS region to scan (default: profile default or us-east-1)',
        default=None
    )
    
    parser.add_argument(
        '--output-dir', '-o',
        help='Output directory for reports (default: ./output)',
        default='output'
    )
    
    parser.add_argument(
        '--version', '-v',
        action='version',
        version='AWS Health Check Tool v1.0.0'
    )
    
    args = parser.parse_args()
    
    try:
        # Create and run health check
        health_check = AWSHealthCheck(
            profile=args.profile,
            region=args.region
        )
        
        health_check.run_full_check(output_dir=args.output_dir)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Health check interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

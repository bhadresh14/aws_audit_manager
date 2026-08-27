"""
AWS Audit Manager - Remediation Module
========================================
Implements SAFE, approval-based remediation actions.
Every action requires explicit user confirmation before execution.

Supported Actions:
- EC2 instance resize (stop → modify → start)

Safety Rules:
- Never auto-execute without user confirmation
- Always log actions with timestamp
- Verify instance state before and after
- Timeout after 5 minutes if instance doesn't stop/start
"""

import boto3
import time
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional


# Activity log file
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
LOG_FILE = os.path.join(LOG_DIR, "remediation_log.json")


def log_action(action: Dict[str, Any]):
    """Log remediation action to file"""
    try:
        logs = []
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r') as f:
                logs = json.load(f)
        logs.append(action)
        with open(LOG_FILE, 'w') as f:
            json.dump(logs, f, indent=2, default=str)
    except Exception:
        pass


def resize_ec2_instance(
    instance_id: str,
    new_instance_type: str,
    region: str,
    profile: str = None
) -> Dict[str, Any]:
    """
    Resize an EC2 instance: stop → modify instance type → start.
    
    Args:
        instance_id: EC2 instance ID (e.g., i-0abc123def456)
        new_instance_type: Target instance type (e.g., t3.small)
        region: AWS region
        profile: AWS profile name (optional)
    
    Returns:
        Dict with status, message, and details
    """
    result = {
        "action": "ec2_resize",
        "instance_id": instance_id,
        "new_instance_type": new_instance_type,
        "region": region,
        "timestamp": datetime.utcnow().isoformat(),
        "steps": [],
        "status": "pending"
    }
    
    try:
        # Create session
        if profile:
            session = boto3.Session(profile_name=profile, region_name=region)
        else:
            session = boto3.Session(region_name=region)
        
        ec2 = session.client('ec2', region_name=region)
        
        # Step 1: Get current instance info
        result["steps"].append({"step": "Checking instance state", "status": "running"})
        
        response = ec2.describe_instances(InstanceIds=[instance_id])
        reservations = response.get('Reservations', [])
        if not reservations or not reservations[0].get('Instances'):
            result["status"] = "failed"
            result["message"] = f"Instance {instance_id} not found"
            log_action(result)
            return result
        
        instance = reservations[0]['Instances'][0]
        current_type = instance['InstanceType']
        current_state = instance['State']['Name']
        
        # Get instance name
        instance_name = ""
        for tag in instance.get('Tags', []):
            if tag['Key'] == 'Name':
                instance_name = tag['Value']
                break
        
        result["current_instance_type"] = current_type
        result["instance_name"] = instance_name
        result["steps"][-1]["status"] = "done"
        result["steps"][-1]["detail"] = f"Instance: {instance_name} ({instance_id}), Type: {current_type}, State: {current_state}"
        
        # Validate
        if current_type == new_instance_type:
            result["status"] = "skipped"
            result["message"] = f"Instance is already {new_instance_type}"
            log_action(result)
            return result
        
        # Step 2: Stop instance (if running)
        if current_state == 'running':
            result["steps"].append({"step": "Stopping instance", "status": "running"})
            
            ec2.stop_instances(InstanceIds=[instance_id])
            
            # Wait for stopped state (max 5 minutes)
            waiter = ec2.get_waiter('instance_stopped')
            waiter.wait(
                InstanceIds=[instance_id],
                WaiterConfig={'Delay': 5, 'MaxAttempts': 60}
            )
            
            result["steps"][-1]["status"] = "done"
            result["steps"][-1]["detail"] = "Instance stopped successfully"
        
        elif current_state == 'stopped':
            result["steps"].append({"step": "Instance already stopped", "status": "done"})
        
        else:
            result["status"] = "failed"
            result["message"] = f"Cannot resize: instance is in '{current_state}' state. Must be running or stopped."
            log_action(result)
            return result
        
        # Step 3: Modify instance type
        result["steps"].append({"step": f"Changing type: {current_type} → {new_instance_type}", "status": "running"})
        
        ec2.modify_instance_attribute(
            InstanceId=instance_id,
            InstanceType={'Value': new_instance_type}
        )
        
        result["steps"][-1]["status"] = "done"
        result["steps"][-1]["detail"] = f"Instance type changed to {new_instance_type}"
        
        # Step 4: Start instance
        result["steps"].append({"step": "Starting instance", "status": "running"})
        
        ec2.start_instances(InstanceIds=[instance_id])
        
        # Wait for running state (max 5 minutes)
        waiter = ec2.get_waiter('instance_running')
        waiter.wait(
            InstanceIds=[instance_id],
            WaiterConfig={'Delay': 5, 'MaxAttempts': 60}
        )
        
        result["steps"][-1]["status"] = "done"
        result["steps"][-1]["detail"] = "Instance started successfully"
        
        # Success
        result["status"] = "success"
        result["message"] = f"Successfully resized {instance_name} ({instance_id}) from {current_type} to {new_instance_type}"
        
    except Exception as e:
        error_msg = str(e)
        result["status"] = "failed"
        result["message"] = f"Error: {error_msg[:300]}"
        result["steps"].append({"step": "Error occurred", "status": "failed", "detail": error_msg[:200]})
    
    # Log the action
    log_action(result)
    return result


def get_remediation_log() -> list:
    """Get the remediation activity log"""
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return []

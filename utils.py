import logging
import json
import numpy as np
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def format_timestamp(timestamp):
    """Format datetime object for display"""
    if not timestamp:
        return "N/A"
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")

def format_risk_score(score):
    """Format risk score as percentage with color code"""
    if score is None:
        return "N/A"
    
    percentage = score * 100
    
    if percentage >= 75:
        color = "danger"
    elif percentage >= 50:
        color = "warning"
    elif percentage >= 25:
        color = "info"
    else:
        color = "success"
    
    return {
        "score": f"{percentage:.1f}%",
        "color": color
    }

def get_activity_description(activity):
    """Generate a human-readable description of a user activity"""
    if not activity:
        return "Unknown activity"
    
    activity_type = activity.activity_type
    details = activity.details
    
    if activity_type == 'logon':
        logon_type = details.get('logon_type', 'Unknown')
        device = details.get('device_id', 'Unknown device')
        success = "successful" if details.get('success', True) else "failed"
        return f"{logon_type} logon ({success}) on {device}"
    
    elif activity_type == 'device':
        device_type = details.get('device_type', 'Unknown device')
        action = details.get('action', 'accessed')
        return f"{action} {device_type} device"
    
    elif activity_type == 'email':
        recipient = details.get('recipient', 'unknown recipient')
        subject = details.get('subject', 'No subject')
        has_attachment = "with attachment" if details.get('attachment_size', 0) > 0 else "without attachments"
        return f"Email to {recipient} ({subject}) {has_attachment}"
    
    elif activity_type == 'file':
        path = details.get('path', 'unknown location')
        operation = details.get('operation', 'accessed')
        count = details.get('file_count', 1)
        file_text = "files" if count > 1 else "file"
        return f"{operation} {count} {file_text} in {path}"
    
    elif activity_type == 'web':
        url = details.get('url', 'unknown website')
        duration = details.get('duration', 0)
        return f"Visited {url} for {duration} minutes"
    
    return f"{activity_type} activity"

def get_timeline_data(activities, attention_data=None):
    """Prepare activity data for timeline visualization"""
    timeline_data = []
    
    if not activities:
        return timeline_data
    
    # If we have attention data, map it to activities
    attention_weights = {}
    if attention_data and 'timestamps' in attention_data and 'weights' in attention_data:
        for ts, weight in zip(attention_data['timestamps'], attention_data['weights']):
            # Convert ISO string to datetime for comparison
            try:
                dt = datetime.fromisoformat(ts)
                attention_weights[dt] = weight
            except ValueError:
                logger.error(f"Invalid timestamp format: {ts}")
    
    # Group activities by day
    day_activities = {}
    for activity in activities:
        day = activity.timestamp.date()
        if day not in day_activities:
            day_activities[day] = []
        day_activities[day].append(activity)
    
    # Sort days and create timeline data
    for day in sorted(day_activities.keys()):
        day_data = {
            'date': day.strftime('%Y-%m-%d'),
            'display_date': day.strftime('%b %d, %Y'),
            'activities': []
        }
        
        # Add activities for this day
        for activity in sorted(day_activities[day], key=lambda a: a.timestamp):
            # Find closest timestamp in attention data
            attention_weight = 0
            if attention_weights:
                # Find closest match in attention weights
                closest_ts = min(attention_weights.keys(), 
                               key=lambda x: abs((x - activity.timestamp).total_seconds()))
                
                # Only use if within 24 hours
                if abs((closest_ts - activity.timestamp).total_seconds()) < 86400:
                    attention_weight = attention_weights[closest_ts]
            
            activity_data = {
                'time': activity.timestamp.strftime('%H:%M'),
                'type': activity.activity_type,
                'description': get_activity_description(activity),
                'importance': attention_weight,
                'details': json.dumps(activity.details)
            }
            day_data['activities'].append(activity_data)
        
        timeline_data.append(day_data)
    
    return timeline_data

def serialize_activity_features(features):
    """Serialize activity features for JSON response"""
    result = {}
    for key, value in features.items():
        if isinstance(value, np.ndarray):
            result[key] = value.tolist()
        elif isinstance(value, np.float32) or isinstance(value, np.float64):
            result[key] = float(value)
        elif isinstance(value, np.int32) or isinstance(value, np.int64):
            result[key] = int(value)
        else:
            result[key] = value
    return result

import os
import json
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sqlalchemy import func

from app import db
from models import User, UserActivity, ActivityFeature

logger = logging.getLogger(__name__)

# Constants for feature engineering
ACTIVITY_TYPES = ['logon', 'device', 'email', 'file', 'web']
TIME_WINDOW_HOURS = 24  # Aggregate activities in 24-hour windows

def load_sample_data():
    """
    Load sample data into the database for demonstration purposes.
    This would be replaced with actual CERT dataset loading in production.
    """
    # Create sample users
    users = [
        User(username='john.doe', email='john.doe@example.com', department='Engineering', position='Developer'),
        User(username='jane.smith', email='jane.smith@example.com', department='HR', position='Manager'),
        User(username='bob.jenkins', email='bob.jenkins@example.com', department='Sales', position='Representative'),
        User(username='alice.wong', email='alice.wong@example.com', department='IT', position='System Admin'),
        User(username='dave.miller', email='dave.miller@example.com', department='Finance', position='Analyst')
    ]
    db.session.add_all(users)
    db.session.commit()
    
    # Create sample activities for each user
    now = datetime.utcnow()
    
    # Regular user activities
    for user in users[:4]:  # First 4 users have normal patterns
        # Generate 20 activities per user spread over the last 10 days
        for i in range(20):
            activity_time = now - timedelta(days=i % 10, hours=i % 24)
            activity_type = ACTIVITY_TYPES[i % len(ACTIVITY_TYPES)]
            
            details = generate_activity_details(activity_type, is_suspicious=False)
            
            activity = UserActivity(
                user_id=user.id,
                timestamp=activity_time,
                activity_type=activity_type,
                details=details
            )
            db.session.add(activity)
    
    # Create suspicious activities for the last user (potential insider threat)
    suspicious_user = users[-1]
    for i in range(30):
        activity_time = now - timedelta(days=i % 5, hours=i % 24)
        
        # More file and email activities during off-hours
        if i % 5 == 0:
            activity_type = 'file'
            is_suspicious = True
        elif i % 4 == 0:
            activity_type = 'email'
            is_suspicious = True
        else:
            activity_type = ACTIVITY_TYPES[i % len(ACTIVITY_TYPES)]
            is_suspicious = False
        
        details = generate_activity_details(activity_type, is_suspicious)
        
        activity = UserActivity(
            user_id=suspicious_user.id,
            timestamp=activity_time,
            activity_type=activity_type,
            details=details
        )
        db.session.add(activity)
    
    db.session.commit()
    logger.info(f"Added {len(users)} users and {User.query.count()} activities to the database")

def generate_activity_details(activity_type, is_suspicious=False):
    """Generate realistic activity details based on activity type"""
    details = {}
    
    if activity_type == 'logon':
        details['device_id'] = f"DEVICE-{np.random.randint(1000, 9999)}"
        details['logon_type'] = np.random.choice(['Remote', 'Local'])
        details['success'] = True
        if is_suspicious:
            # Suspicious: Unusual login time
            hour = np.random.randint(1, 5)  # Early morning hours
            details['time_of_day'] = f"{hour:02d}:{np.random.randint(0, 60):02d}"
        else:
            # Normal: Business hours
            hour = np.random.randint(8, 18)
            details['time_of_day'] = f"{hour:02d}:{np.random.randint(0, 60):02d}"
    
    elif activity_type == 'device':
        details['device_id'] = f"DEVICE-{np.random.randint(1000, 9999)}"
        details['device_type'] = np.random.choice(['USB', 'External HDD', 'CD/DVD'])
        details['action'] = np.random.choice(['connect', 'disconnect'])
        if is_suspicious:
            # Suspicious: Large number of connects/disconnects or unusual times
            details['frequency'] = np.random.randint(10, 20)
        else:
            details['frequency'] = np.random.randint(1, 5)
    
    elif activity_type == 'email':
        domains = ['example.com', 'partner.com', 'client.org']
        if is_suspicious:
            # Suspicious: External domain, large attachments, sensitive keywords
            details['recipient'] = f"external-{np.random.randint(1000, 9999)}@{np.random.choice(['personal.com', 'gmail.com', 'unknown.net'])}"
            details['attachment_size'] = np.random.randint(5000000, 20000000)  # Large attachment
            details['subject'] = np.random.choice(['Confidential Data', 'Project Secrets', 'Financial Reports', 'Customer Database'])
        else:
            details['recipient'] = f"colleague-{np.random.randint(1000, 9999)}@{np.random.choice(domains)}"
            details['attachment_size'] = np.random.randint(0, 2000000)  # Smaller or no attachment
            details['subject'] = np.random.choice(['Meeting Notes', 'Project Update', 'Hello', 'Question', 'Weekly Report'])
    
    elif activity_type == 'file':
        file_paths = ['/projects/', '/documents/', '/shared/', '/personal/']
        if is_suspicious:
            # Suspicious: Accessing sensitive files, copying large amounts
            details['path'] = np.random.choice(['/confidential/', '/hr_records/', '/financial_data/'])
            details['operation'] = np.random.choice(['copy', 'download', 'read'])
            details['file_count'] = np.random.randint(50, 200)
            details['access_time'] = f"{np.random.randint(18, 24):02d}:{np.random.randint(0, 60):02d}"  # After hours
        else:
            details['path'] = np.random.choice(file_paths)
            details['operation'] = np.random.choice(['read', 'write', 'modify'])
            details['file_count'] = np.random.randint(1, 20)
            details['access_time'] = f"{np.random.randint(9, 17):02d}:{np.random.randint(0, 60):02d}"  # Business hours
    
    elif activity_type == 'web':
        normal_sites = ['company-portal', 'jira', 'confluence', 'github', 'stackoverflow']
        if is_suspicious:
            # Suspicious: Job sites, file sharing, competitors
            details['url'] = np.random.choice(['linkedin.com/jobs', 'indeed.com', 'dropbox.com', 'wetransfer.com', 'competitor.com'])
            details['duration'] = np.random.randint(30, 120)  # Longer duration
            details['bytes_transferred'] = np.random.randint(1000000, 10000000)
        else:
            details['url'] = f"https://{np.random.choice(normal_sites)}.example.com"
            details['duration'] = np.random.randint(5, 60)
            details['bytes_transferred'] = np.random.randint(10000, 1000000)
    
    return details

def preprocess_user_activity():
    """
    Preprocess user activities into sequential feature vectors for the BiLSTM model.
    Returns a dictionary mapping user_ids to their sequence data.
    """
    logger.info("Starting data preprocessing")
    
    # Get all users
    users = User.query.all()
    user_sequences = {}
    
    # Process each user's activities
    for user in users:
        # Get user activities sorted by timestamp
        activities = UserActivity.query.filter_by(user_id=user.id).order_by(UserActivity.timestamp).all()
        
        if not activities:
            logger.warning(f"No activities found for user {user.id}")
            continue
        
        # Group activities into time windows
        start_time = activities[0].timestamp
        end_time = activities[-1].timestamp
        
        # Create time windows
        current_window = start_time
        windows = []
        while current_window <= end_time:
            next_window = current_window + timedelta(hours=TIME_WINDOW_HOURS)
            windows.append((current_window, next_window))
            current_window = next_window
        
        # Extract features for each time window
        sequence_data = []
        for window_start, window_end in windows:
            window_activities = [a for a in activities if window_start <= a.timestamp < window_end]
            
            if not window_activities:
                # No activities in this window, use zeros for features
                features = create_empty_features()
            else:
                features = extract_features(window_activities)
            
            # Store features for this window
            feature_record = ActivityFeature(
                user_id=user.id,
                time_window=window_start,
                feature_vector=features
            )
            db.session.add(feature_record)
            
            # Add to sequence data
            sequence_data.append(features)
        
        # Store the sequence for this user
        user_sequences[user.id] = sequence_data
    
    db.session.commit()
    logger.info(f"Processed activity data for {len(user_sequences)} users")
    
    return user_sequences

def create_empty_features():
    """Create an empty feature vector for time windows with no activities"""
    features = {
        # Count features
        'logon_count': 0,
        'device_count': 0,
        'email_count': 0,
        'file_count': 0,
        'web_count': 0,
        
        # Time-based features
        'after_hours_activity': 0,
        'weekend_activity': 0,
        
        # Type-specific features
        'external_email_ratio': 0,
        'large_file_transfers': 0,
        'sensitive_file_access': 0,
        'usb_connects': 0,
        'job_site_visits': 0,
        'unusual_logon_types': 0
    }
    return features

def extract_features(activities):
    """Extract features from a list of user activities in a time window"""
    features = {
        # Initialize count features
        'logon_count': 0,
        'device_count': 0,
        'email_count': 0,
        'file_count': 0,
        'web_count': 0,
        
        # Initialize time-based features
        'after_hours_activity': 0,
        'weekend_activity': 0,
        
        # Initialize type-specific features
        'external_email_ratio': 0,
        'large_file_transfers': 0,
        'sensitive_file_access': 0,
        'usb_connects': 0,
        'job_site_visits': 0,
        'unusual_logon_types': 0
    }
    
    # Special tracking for ratio calculations
    external_email_count = 0
    total_email_count = 0
    
    for activity in activities:
        # Update count by activity type
        activity_type = activity.activity_type
        features[f'{activity_type}_count'] += 1
        
        # Extract time-based features
        activity_hour = activity.timestamp.hour
        activity_weekday = activity.timestamp.weekday()
        
        # After hours: before 8am or after 6pm
        if activity_hour < 8 or activity_hour >= 18:
            features['after_hours_activity'] += 1
        
        # Weekend: Saturday (5) or Sunday (6)
        if activity_weekday >= 5:
            features['weekend_activity'] += 1
        
        # Process type-specific details
        details = activity.details
        
        if activity_type == 'email':
            total_email_count += 1
            recipient = details.get('recipient', '')
            # Check if external email (not ending with company domains)
            if not any(recipient.endswith(domain) for domain in ['example.com', 'partner.com', 'client.org']):
                external_email_count += 1
            
            # Check for large attachments
            if details.get('attachment_size', 0) > 5000000:  # 5MB
                features['large_file_transfers'] += 1
        
        elif activity_type == 'file':
            # Check for sensitive file access
            path = details.get('path', '')
            if any(sensitive in path for sensitive in ['/confidential/', '/hr_records/', '/financial_data/']):
                features['sensitive_file_access'] += 1
            
            # Check for large file transfers
            if details.get('operation') in ['copy', 'download'] and details.get('file_count', 0) > 20:
                features['large_file_transfers'] += 1
        
        elif activity_type == 'device':
            # Track USB connections
            if details.get('device_type') == 'USB' and details.get('action') == 'connect':
                features['usb_connects'] += 1
        
        elif activity_type == 'web':
            # Check for job site visits
            url = details.get('url', '')
            if any(job_site in url for job_site in ['linkedin.com/jobs', 'indeed.com', 'monster.com']):
                features['job_site_visits'] += 1
        
        elif activity_type == 'logon':
            # Check for unusual logon types
            logon_type = details.get('logon_type', '')
            time_of_day = details.get('time_of_day', '')
            
            # Remote logons during off-hours are considered unusual
            if logon_type == 'Remote' and (activity_hour < 8 or activity_hour >= 18):
                features['unusual_logon_types'] += 1
    
    # Calculate external email ratio
    if total_email_count > 0:
        features['external_email_ratio'] = external_email_count / total_email_count
    
    return features

def normalize_features(user_sequences):
    """Normalize features across all users for better model performance"""
    # Flatten all sequences into a single list of feature dictionaries
    all_features = []
    for user_id, sequence in user_sequences.items():
        all_features.extend(sequence)
    
    # Convert to DataFrame for easier processing
    df = pd.DataFrame(all_features)
    
    # Apply standard scaling to numeric features
    scaler = StandardScaler()
    numeric_cols = df.columns
    df[numeric_cols] = scaler.fit_transform(df[numeric_cols])
    
    # Update user sequences with normalized features
    normalized_sequences = {}
    index = 0
    for user_id, sequence in user_sequences.items():
        normalized_sequences[user_id] = []
        for _ in range(len(sequence)):
            normalized_sequences[user_id].append(df.iloc[index].to_dict())
            index += 1
    
    return normalized_sequences

import os
import logging
import random
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create base class for SQLAlchemy models
class Base(DeclarativeBase):
    pass

# Initialize database
db = SQLAlchemy(model_class=Base)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")

# Configure database with PostgreSQL
database_url = os.environ.get("DATABASE_URL")
if database_url and database_url.startswith("postgres://"):
    # Heroku-style URL needs to be updated for SQLAlchemy 1.4+
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url or "sqlite:///insider_threats.db"
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Log the database URL (with password redacted)
if database_url:
    safe_url = database_url
    if '@' in safe_url:
        parts = safe_url.split('@')
        credentials = parts[0].split(':')
        if len(credentials) > 2:
            # Obscure password
            safe_url = f"{credentials[0]}:***@{parts[1]}"
    logger.info(f"Using database: {safe_url}")

# Initialize the app with the extension
db.init_app(app)

# Import models first to create tables
from models import User, UserActivity, DetectedThreat, ActivityFeature, ModelMetrics

# Flag to control whether to use TensorFlow
USE_TENSORFLOW = False

# Create database tables
with app.app_context():
    db.create_all()

# Import other modules after app and db setup
from data_processing import load_sample_data, preprocess_user_activity

# Create simulated attention weights for demonstration
def generate_simulated_attention_weights(user_id):
    threat = DetectedThreat.query.filter_by(user_id=user_id).first()
    if not threat:
        return None
    
    # Get activities for this user
    activities = UserActivity.query.filter_by(user_id=user_id).order_by(UserActivity.timestamp).all()
    if not activities:
        return None
    
    # Take up to 10 most recent activities
    recent_activities = activities[-10:] if len(activities) > 10 else activities
    
    # Generate random weights that sum to 1
    weights = [random.random() for _ in range(len(recent_activities))]
    total = sum(weights)
    normalized_weights = [w/total for w in weights]
    
    # Generate feature names
    feature_names = [
        'logon_count', 'device_count', 'email_count', 'file_count', 'web_count',
        'after_hours_activity', 'weekend_activity', 'external_email_ratio',
        'large_file_transfers', 'sensitive_file_access', 'usb_connects',
        'job_site_visits', 'unusual_logon_types'
    ]
    
    # Create attention data structure
    attention_data = {
        'timestamps': [a.timestamp.isoformat() for a in recent_activities],
        'weights': normalized_weights,
        'feature_names': feature_names
    }
    
    # Store in database
    if not threat.attention_weights:
        threat.attention_weights = {
            'weights': normalized_weights,
            'feature_names': feature_names
        }
        db.session.commit()
    
    return attention_data

# Initialize with sample data if database is empty
with app.app_context():
    if User.query.count() == 0:
        logger.info("Initializing database with sample data")
        load_sample_data()
        
        # Generate mock threats and attention weights for demo
        users = User.query.all()
        for user in users:
            # Skip if threat already exists
            if DetectedThreat.query.filter_by(user_id=user.id).first():
                continue
                
            # Generate random risk score with bias toward insiders for user "dave.miller"
            if user.username == "dave.miller":
                risk_score = random.uniform(0.75, 0.95)
            else:
                risk_score = random.uniform(0.05, 0.6)
                
            # Create threat record
            threat = DetectedThreat(
                user_id=user.id,
                risk_score=risk_score,
                detection_date=datetime.utcnow()
            )
            db.session.add(threat)
        
        db.session.commit()
        
        # Generate attention weights for each threat
        threats = DetectedThreat.query.all()
        for threat in threats:
            generate_simulated_attention_weights(threat.user_id)

@app.route('/')
def index():
    """Home page with overview of the system"""
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    """Main dashboard showing detected threats"""
    threats = DetectedThreat.query.order_by(DetectedThreat.risk_score.desc()).all()
    return render_template('dashboard.html', threats=threats)

@app.route('/user/<int:user_id>')
def user_details(user_id):
    """Detailed view of a specific user's activity and threat assessment"""
    user = User.query.get_or_404(user_id)
    threat = DetectedThreat.query.filter_by(user_id=user_id).first()
    activities = UserActivity.query.filter_by(user_id=user_id).order_by(UserActivity.timestamp).all()
    
    # Get attention weights for visualization
    attention_data = None
    if threat and threat.attention_weights:
        # Use stored attention weights
        weights = threat.attention_weights.get('weights', [])
        feature_names = threat.attention_weights.get('feature_names', [])
        
        # Get timestamps from activities (most recent ones matching weights length)
        recent_activities = activities[-len(weights):] if len(activities) > len(weights) else activities
        timestamps = [a.timestamp.isoformat() for a in recent_activities]
        
        attention_data = {
            'timestamps': timestamps,
            'weights': weights,
            'feature_names': feature_names
        }
    else:
        # Generate simulated weights
        attention_data = generate_simulated_attention_weights(user_id)
    
    return render_template('user_details.html', 
                          user=user, 
                          threat=threat, 
                          activities=activities,
                          attention_data=attention_data)

@app.route('/explanation')
def model_explanation():
    """Page explaining the BiLSTM model with attention mechanism"""
    return render_template('model_explanation.html')

@app.route('/api/threats')
def get_threats():
    """API endpoint to get all detected threats"""
    threats = DetectedThreat.query.order_by(DetectedThreat.risk_score.desc()).all()
    return jsonify([{
        'id': t.id,
        'user_id': t.user_id,
        'username': t.user.username,
        'risk_score': t.risk_score,
        'detection_date': t.detection_date.isoformat()
    } for t in threats])

@app.route('/api/user_activity/<int:user_id>')
def get_user_activity(user_id):
    """API endpoint to get a user's activity data"""
    activities = UserActivity.query.filter_by(user_id=user_id).order_by(UserActivity.timestamp).all()
    return jsonify([{
        'id': a.id,
        'timestamp': a.timestamp.isoformat(),
        'activity_type': a.activity_type,
        'details': a.details
    } for a in activities])

@app.route('/api/attention/<int:user_id>')
def get_attention_data(user_id):
    """API endpoint to get attention weights for a user"""
    threat = DetectedThreat.query.filter_by(user_id=user_id).first()
    if threat and threat.attention_weights:
        # Use stored attention weights
        weights = threat.attention_weights.get('weights', [])
        feature_names = threat.attention_weights.get('feature_names', [])
        
        # Get timestamps from activities
        activities = UserActivity.query.filter_by(user_id=user_id).order_by(UserActivity.timestamp).all()
        recent_activities = activities[-len(weights):] if len(activities) > len(weights) else activities
        timestamps = [a.timestamp.isoformat() for a in recent_activities]
        
        attention_data = {
            'timestamps': timestamps,
            'weights': weights,
            'feature_names': feature_names
        }
        return jsonify(attention_data)
    else:
        # Generate simulated weights
        attention_data = generate_simulated_attention_weights(user_id)
        return jsonify(attention_data)

@app.route('/analyze')
def analyze_data():
    """Trigger data analysis and model prediction"""
    try:
        if USE_TENSORFLOW:
            # Only import TensorFlow if explicitly enabled
            from ml_model import get_model, predict_threats
            
            # Preprocess user activity data
            user_sequences = preprocess_user_activity()
            
            # Get or create BiLSTM model
            model = get_model()
            
            # Predict threats
            predictions = predict_threats(model, user_sequences)
        else:
            # Use simulated predictions for demo
            users = User.query.all()
            for user in users:
                threat = DetectedThreat.query.filter_by(user_id=user.id).first()
                
                # Update existing threats with slight random changes
                if threat:
                    # Adjust risk score slightly
                    threat.risk_score = min(max(threat.risk_score + random.uniform(-0.1, 0.1), 0.01), 0.99)
                    threat.detection_date = datetime.utcnow()
                else:
                    # Create new threat with random risk score
                    risk_score = random.uniform(0.1, 0.9)
                    
                    # Higher risk for "dave.miller" (our insider)
                    if user.username == "dave.miller":
                        risk_score = random.uniform(0.75, 0.95)
                    
                    threat = DetectedThreat(
                        user_id=user.id,
                        risk_score=risk_score,
                        detection_date=datetime.utcnow()
                    )
                    db.session.add(threat)
                
                # Generate attention weights
                generate_simulated_attention_weights(user.id)
            
            db.session.commit()
        
        return redirect(url_for('dashboard'))
    except Exception as e:
        logger.error(f"Error analyzing data: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

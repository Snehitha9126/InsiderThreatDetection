from datetime import datetime
from app import db

class User(db.Model):
    """User model representing employees or system users"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    department = db.Column(db.String(64))
    position = db.Column(db.String(64))
    join_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    activities = db.relationship('UserActivity', backref='user', lazy='dynamic')
    threat = db.relationship('DetectedThreat', backref='user', uselist=False)
    
    def __repr__(self):
        return f'<User {self.username}>'

class UserActivity(db.Model):
    """Model for storing user activities from logs"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    activity_type = db.Column(db.String(32), nullable=False)  # logon, device, email, file, web
    details = db.Column(db.JSON)  # Flexible field to store activity-specific details
    
    def __repr__(self):
        return f'<UserActivity {self.activity_type} by User {self.user_id} at {self.timestamp}>'

class DetectedThreat(db.Model):
    """Model for storing detected insider threats"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    risk_score = db.Column(db.Float, nullable=False)  # Probability from model
    detection_date = db.Column(db.DateTime, default=datetime.utcnow)
    attention_weights = db.Column(db.JSON, nullable=True)  # Store attention weights for explanation
    notes = db.Column(db.Text, nullable=True)  # Any additional notes or observations
    
    def __repr__(self):
        return f'<DetectedThreat User {self.user_id} Score {self.risk_score}>'

class ActivityFeature(db.Model):
    """Model for storing preprocessed features used by the ML model"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    time_window = db.Column(db.DateTime, nullable=False)
    feature_vector = db.Column(db.JSON, nullable=False)  # Encoded features as JSON
    
    def __repr__(self):
        return f'<ActivityFeature User {self.user_id} Window {self.time_window}>'

class ModelMetrics(db.Model):
    """Model for storing model evaluation metrics"""
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    accuracy = db.Column(db.Float)
    precision = db.Column(db.Float)
    recall = db.Column(db.Float)
    f1_score = db.Column(db.Float)
    auc = db.Column(db.Float)
    
    def __repr__(self):
        return f'<ModelMetrics {self.timestamp} F1={self.f1_score}>'

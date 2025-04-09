import os
import logging
import numpy as np
import tensorflow as tf
from tensorflow.keras import layers, models
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score

from app import db
from models import User, DetectedThreat, ModelMetrics
from data_processing import normalize_features

logger = logging.getLogger(__name__)

# Model parameters
LSTM_UNITS = 64
DENSE_UNITS = 32
SEQUENCE_LENGTH = 10  # Number of time windows to consider
FEATURE_DIM = 13  # Number of features per time window

def get_model():
    """Get or create the BiLSTM model with attention mechanism"""
    # Check if we have a saved model
    model_path = 'saved_model/bilstm_attention'
    if os.path.exists(model_path):
        try:
            model = models.load_model(model_path)
            logger.info("Loaded existing BiLSTM model")
            return model
        except Exception as e:
            logger.warning(f"Failed to load existing model: {str(e)}")
    
    # Create a new model
    logger.info("Creating new BiLSTM model with attention")
    model = create_bilstm_attention_model()
    return model

def create_bilstm_attention_model():
    """Create and compile a BiLSTM model with attention mechanism"""
    # Input shape: [sequence_length, feature_dim]
    inputs = layers.Input(shape=(SEQUENCE_LENGTH, FEATURE_DIM))
    
    # Bidirectional LSTM layers
    bilstm1 = layers.Bidirectional(layers.LSTM(LSTM_UNITS, return_sequences=True))(inputs)
    
    # Attention mechanism
    attention = layers.Dense(1, activation='tanh')(bilstm1)
    attention = layers.Flatten()(attention)
    attention_weights = layers.Activation('softmax', name='attention_weights')(attention)
    
    # Apply attention weights
    attention_weights = layers.RepeatVector(LSTM_UNITS * 2)(attention_weights)
    attention_weights = layers.Permute([2, 1])(attention_weights)
    
    # Merge with BiLSTM output
    sent_representation = layers.Multiply()([bilstm1, attention_weights])
    sent_representation = layers.Lambda(lambda x: tf.keras.backend.sum(x, axis=1))(sent_representation)
    
    # Dense layers
    dense1 = layers.Dense(DENSE_UNITS, activation='relu')(sent_representation)
    dropout = layers.Dropout(0.3)(dense1)
    
    # Output layer (binary classification)
    outputs = layers.Dense(1, activation='sigmoid')(dropout)
    
    # Create and compile model
    model = models.Model(inputs=inputs, outputs=outputs)
    model.compile(
        optimizer='adam',
        loss='binary_crossentropy',
        metrics=['accuracy']
    )
    
    return model

def predict_threats(model, user_sequences):
    """
    Use the BiLSTM model to predict insider threats.
    Stores results in the database.
    """
    logger.info("Predicting insider threats")
    
    # Normalize feature sequences
    normalized_sequences = normalize_features(user_sequences)
    
    # Process each user's sequence data
    predictions = {}
    attention_weights = {}
    
    for user_id, sequence in normalized_sequences.items():
        # Skip if sequence is too short
        if len(sequence) < SEQUENCE_LENGTH:
            logger.warning(f"Sequence too short for user {user_id}: {len(sequence)} < {SEQUENCE_LENGTH}")
            continue
        
        # Prepare input for the model (use last SEQUENCE_LENGTH windows)
        sequence_data = sequence[-SEQUENCE_LENGTH:]
        
        # Convert sequence dictionaries to a numpy array
        feature_names = sorted(sequence_data[0].keys())
        sequence_array = np.array([[seq[feature] for feature in feature_names] for seq in sequence_data])
        
        # Reshape to match model input shape [1, sequence_length, feature_dim]
        model_input = sequence_array.reshape(1, SEQUENCE_LENGTH, FEATURE_DIM)
        
        # Get prediction
        risk_score = model.predict(model_input)[0][0]
        predictions[user_id] = float(risk_score)
        
        # Get attention weights
        attention_model = models.Model(
            inputs=model.input,
            outputs=model.get_layer('attention_weights').output
        )
        weights = attention_model.predict(model_input)[0]
        attention_weights[user_id] = weights.tolist()
        
        # Store or update threat detection in database
        existing_threat = DetectedThreat.query.filter_by(user_id=user_id).first()
        if existing_threat:
            existing_threat.risk_score = float(risk_score)
            existing_threat.attention_weights = {
                'weights': weights.tolist(),
                'feature_names': feature_names
            }
        else:
            new_threat = DetectedThreat(
                user_id=user_id,
                risk_score=float(risk_score),
                attention_weights={
                    'weights': weights.tolist(),
                    'feature_names': feature_names
                }
            )
            db.session.add(new_threat)
    
    db.session.commit()
    logger.info(f"Stored threat predictions for {len(predictions)} users")
    
    return predictions

def get_attention_weights(user_id):
    """Get attention weights for a specific user"""
    threat = DetectedThreat.query.filter_by(user_id=user_id).first()
    if not threat or not threat.attention_weights:
        return None
    
    # Get feature names and weights
    weights = threat.attention_weights.get('weights', [])
    feature_names = threat.attention_weights.get('feature_names', [])
    
    if not weights or not feature_names:
        return None
    
    # Get the actual activities for the time windows
    from models import ActivityFeature
    activities = ActivityFeature.query.filter_by(user_id=user_id).order_by(ActivityFeature.time_window).all()
    
    # Use the last SEQUENCE_LENGTH activities (to match the model input)
    if len(activities) > SEQUENCE_LENGTH:
        activities = activities[-SEQUENCE_LENGTH:]
    
    # Map weights to activities and features
    result = {
        'timestamps': [a.time_window.isoformat() for a in activities],
        'weights': weights,
        'feature_names': feature_names
    }
    
    return result

def evaluate_model(model, test_data, test_labels):
    """Evaluate model performance with various metrics"""
    # Make predictions on test data
    predictions = model.predict(test_data)
    pred_labels = (predictions > 0.5).astype(int).flatten()
    
    # Calculate metrics
    metrics = {
        'accuracy': accuracy_score(test_labels, pred_labels),
        'precision': precision_score(test_labels, pred_labels),
        'recall': recall_score(test_labels, pred_labels),
        'f1_score': f1_score(test_labels, pred_labels),
        'auc': roc_auc_score(test_labels, predictions)
    }
    
    # Save metrics to database
    db_metrics = ModelMetrics(
        accuracy=metrics['accuracy'],
        precision=metrics['precision'],
        recall=metrics['recall'],
        f1_score=metrics['f1_score'],
        auc=metrics['auc']
    )
    db.session.add(db_metrics)
    db.session.commit()
    
    return metrics

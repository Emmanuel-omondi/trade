import numpy as np
import threading

class PredictiveCodec:
    def __init__(self, state_size=11):
        self.state_size = state_size
        self.lock = threading.Lock()
        
        self.prediction_model = np.random.randn(state_size, state_size) * 0.1
        self.error_history = []
        self.max_history = 100
        self.learning_rate = 0.01
        
    def predict_next_state(self, current_state):
        with self.lock:
            current_state = np.array(current_state, dtype=np.float32)
            if len(current_state.shape) == 1:
                current_state = current_state.reshape(-1, 1)
            
            next_state = np.dot(self.prediction_model, current_state)
            return next_state.flatten()
    
    def compute_prediction_error(self, predicted_state, actual_state):
        with self.lock:
            predicted_state = np.array(predicted_state, dtype=np.float32).flatten()
            actual_state = np.array(actual_state, dtype=np.float32).flatten()
            
            error = np.sqrt(np.mean((predicted_state - actual_state) ** 2))
            self.error_history.append(error)
            
            if len(self.error_history) > self.max_history:
                self.error_history.pop(0)
            
            return error
    
    def update_prediction_model(self, state, next_state):
        with self.lock:
            state = np.array(state, dtype=np.float32)
            next_state = np.array(next_state, dtype=np.float32)
            
            if len(state.shape) == 1:
                state = state.reshape(-1, 1)
            if len(next_state.shape) == 1:
                next_state = next_state.reshape(-1, 1)
            
            gradient = np.dot(next_state - np.dot(self.prediction_model, state), state.T)
            self.prediction_model += self.learning_rate * gradient
    
    def get_average_error(self):
        with self.lock:
            if len(self.error_history) == 0:
                return 0
            return np.mean(self.error_history)
    
    def get_error_trend(self, window=10):
        with self.lock:
            if len(self.error_history) < window:
                return 0
            
            recent = self.error_history[-window:]
            older = self.error_history[-(2*window):-window] if len(self.error_history) >= 2*window else self.error_history[:window]
            
            if np.mean(older) > 0:
                return (np.mean(recent) - np.mean(older)) / np.mean(older)
            return 0
    
    def is_surprising_move(self, threshold=2.0):
        with self.lock:
            if len(self.error_history) < 5:
                return False
            
            avg_error = np.mean(self.error_history)
            std_error = np.std(self.error_history) if len(self.error_history) > 1 else 0
            
            if len(self.error_history) > 0:
                current_error = self.error_history[-1]
                z_score = (current_error - avg_error) / (std_error + 1e-8)
                return z_score > threshold
            
            return False


class PredictiveCodingLoop:
    def __init__(self, state_size=11, update_frequency=1):
        self.state_size = state_size
        self.update_frequency = update_frequency
        self.lock = threading.Lock()
        
        self.codec = PredictiveCodec(state_size)
        self.state_buffer = []
        self.max_buffer_size = 50
        self.surprise_count = 0
        self.update_count = 0
        self.confidence_level = 0.5
        self.learning_enabled = True
        
    def process_tick(self, current_state):
        with self.lock:
            current_state = np.array(current_state, dtype=np.float32)
            
            if len(self.state_buffer) > 0:
                previous_state = self.state_buffer[-1]
                predicted_next = self.codec.predict_next_state(previous_state)
                error = self.codec.compute_prediction_error(predicted_next, current_state)
                
                is_surprise = self.codec.is_surprising_move(threshold=1.5)
                if is_surprise:
                    self.surprise_count += 1
                
                if self.learning_enabled and (self.update_count % self.update_frequency == 0):
                    self.codec.update_prediction_model(previous_state, current_state)
                
                self.update_count += 1
                self.confidence_level = 1 - np.tanh(error)
            
            self.state_buffer.append(current_state)
            if len(self.state_buffer) > self.max_buffer_size:
                self.state_buffer.pop(0)
            
            return {
                'predicted_state': self.codec.predict_next_state(current_state),
                'error': self.codec.get_average_error(),
                'confidence': self.confidence_level,
                'is_surprise': self.codec.is_surprising_move(threshold=1.5),
                'surprise_count': self.surprise_count
            }
    
    def get_position_size_multiplier(self):
        with self.lock:
            low_error_periods = sum(1 for e in self.codec.error_history[-20:] 
                                   if e < np.mean(self.codec.error_history) if len(self.codec.error_history) > 0)
            
            if len(self.codec.error_history) > 0:
                confidence = low_error_periods / min(20, len(self.codec.error_history))
            else:
                confidence = 0.5
            
            return 0.5 + (confidence * 0.5)
    
    def get_update_weight(self):
        with self.lock:
            if self.codec.is_surprising_move(threshold=1.5):
                return 1.0
            
            avg_error = self.codec.get_average_error()
            if avg_error > 0:
                return 1.0 / (1.0 + avg_error)
            return 0.5
    
    def get_diagnostics(self):
        with self.lock:
            return {
                'avg_prediction_error': self.codec.get_average_error(),
                'error_trend': self.codec.get_error_trend(),
                'confidence_level': self.confidence_level,
                'surprise_count': self.surprise_count,
                'total_updates': self.update_count,
                'position_multiplier': self.get_position_size_multiplier(),
                'update_weight': self.get_update_weight(),
                'buffer_size': len(self.state_buffer)
            }
    
    def reset(self):
        with self.lock:
            self.codec = PredictiveCodec(self.state_size)
            self.state_buffer.clear()
            self.surprise_count = 0
            self.update_count = 0
            self.confidence_level = 0.5
    
    def toggle_learning(self):
        with self.lock:
            self.learning_enabled = not self.learning_enabled

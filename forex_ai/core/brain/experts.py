import numpy as np
import threading
from sklearn.tree import DecisionTreeRegressor
import pickle

class GradientBoostedExpert:
    def __init__(self, expert_id, depth=5, n_estimators=10):
        self.expert_id = expert_id
        self.depth = depth
        self.n_estimators = n_estimators
        self.lock = threading.Lock()
        
        self.trees = []
        self.learning_rate = 0.1
        self.predictions = []
        self.errors = []
        self.performance_score = 0.5
        self.total_predictions = 0
        self.correct_predictions = 0
        
    def predict(self, X):
        with self.lock:
            if len(self.trees) == 0:
                return np.random.uniform(-0.5, 0.5)
            
            X = np.array(X, dtype=np.float32).reshape(1, -1)
            prediction = np.zeros(1)
            
            for tree in self.trees:
                prediction += self.learning_rate * tree.predict(X)
            
            prediction = np.clip(prediction[0], -1, 1)
            self.predictions.append(prediction)
            self.total_predictions += 1
            
            if len(self.predictions) > 100:
                self.predictions.pop(0)
            
            return prediction
    
    def update(self, X, y):
        with self.lock:
            X = np.array(X, dtype=np.float32).reshape(-1, 11)
            y = np.array(y, dtype=np.float32)
            
            if len(self.trees) < self.n_estimators:
                residuals = y if len(self.trees) == 0 else y - self.predict_batch(X)
                tree = DecisionTreeRegressor(max_depth=self.depth, random_state=42)
                tree.fit(X, residuals)
                self.trees.append(tree)
            else:
                idx = len(self.trees) % self.n_estimators
                residuals = y - self.predict_batch(X)
                tree = DecisionTreeRegressor(max_depth=self.depth, random_state=42)
                tree.fit(X, residuals)
                self.trees[idx] = tree
    
    def predict_batch(self, X):
        with self.lock:
            X = np.array(X, dtype=np.float32)
            if len(X.shape) == 1:
                X = X.reshape(1, -1)
            
            if len(self.trees) == 0:
                return np.random.uniform(-0.5, 0.5, len(X))
            
            predictions = np.zeros(len(X))
            for tree in self.trees:
                predictions += self.learning_rate * tree.predict(X)
            
            return np.clip(predictions, -1, 1)
    
    def update_performance(self, correct):
        with self.lock:
            if correct:
                self.correct_predictions += 1
            self.total_predictions += 1
            
            if self.total_predictions > 0:
                self.performance_score = self.correct_predictions / self.total_predictions
    
    def get_performance(self):
        with self.lock:
            return {
                'expert_id': self.expert_id,
                'performance_score': self.performance_score,
                'total_predictions': self.total_predictions,
                'correct_predictions': self.correct_predictions,
                'avg_prediction': np.mean(self.predictions) if self.predictions else 0,
                'prediction_std': np.std(self.predictions) if len(self.predictions) > 1 else 0,
                'n_trees': len(self.trees)
            }
    
    def get_memory_usage(self):
        with self.lock:
            total_memory = 0
            for tree in self.trees:
                total_memory += len(pickle.dumps(tree))
            return total_memory


class ExpertEnsemble:
    def __init__(self, n_experts=20):
        self.n_experts = n_experts
        self.lock = threading.Lock()
        
        self.experts = [
            GradientBoostedExpert(
                expert_id=i,
                depth=np.random.randint(3, 7),
                n_estimators=np.random.randint(5, 15)
            )
            for i in range(n_experts)
        ]
        
        self.expert_weights = np.ones(n_experts) / n_experts
        self.ensemble_output = 0
        self.confidence = 0.5
        self.agreement_level = 0
        
    def predict(self, X):
        with self.lock:
            predictions = np.array([expert.predict(X) for expert in self.experts])
            
            weighted_pred = np.dot(predictions, self.expert_weights)
            
            self.agreement_level = 1 - np.std(predictions) if len(predictions) > 0 else 0
            self.confidence = 0.5 + (self.agreement_level * 0.4)
            self.ensemble_output = weighted_pred
            
            return weighted_pred, predictions, self.confidence, self.agreement_level
    
    def update_all(self, X, y):
        with self.lock:
            X = np.array(X, dtype=np.float32)
            y = np.array(y, dtype=np.float32)
            
            for expert in self.experts:
                expert.update(X, y)
    
    def update_weights(self, recent_performance):
        with self.lock:
            if not recent_performance or len(recent_performance) < len(self.experts):
                return
            
            performance_scores = np.array(recent_performance, dtype=np.float32)
            performance_scores = performance_scores + 0.1
            
            self.expert_weights = performance_scores / np.sum(performance_scores)
    
    def get_top_experts(self, k=5):
        with self.lock:
            performances = [expert.get_performance() for expert in self.experts]
            sorted_perf = sorted(performances, key=lambda x: x['performance_score'], reverse=True)
            return sorted_perf[:k]
    
    def get_ensemble_metrics(self):
        with self.lock:
            return {
                'ensemble_output': self.ensemble_output,
                'confidence': self.confidence,
                'agreement_level': self.agreement_level,
                'top_experts': self.get_top_experts(k=3),
                'weights_entropy': -np.sum(self.expert_weights * np.log(self.expert_weights + 1e-8))
            }
    
    def get_total_memory_usage(self):
        with self.lock:
            total = 0
            for expert in self.experts:
                total += expert.get_memory_usage()
            return total
    
    def reset_expert_weights(self):
        with self.lock:
            self.expert_weights = np.ones(self.n_experts) / self.n_experts

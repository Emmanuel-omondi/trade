import numpy as np
import threading

class EchoStateNetwork:
    def __init__(self, input_size=11, hidden_size=100, output_size=3, 
                 spectral_radius=0.9, sparsity=0.9, random_state=42):
        np.random.seed(random_state)
        
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.output_size = output_size
        self.spectral_radius = spectral_radius
        self.sparsity = sparsity
        
        self.lock = threading.Lock()
        
        self.W_in = np.random.randn(hidden_size, input_size) * 0.5
        
        mask = np.random.rand(hidden_size, hidden_size) < (1 - sparsity)
        self.W = np.random.randn(hidden_size, hidden_size) * mask
        
        eigenvalues = np.linalg.eigvals(self.W)
        max_eigenvalue = np.max(np.abs(eigenvalues))
        if max_eigenvalue > 0:
            self.W *= spectral_radius / max_eigenvalue
        
        self.b = np.random.uniform(-0.5, 0.5, hidden_size)
        
        self.W_out = np.random.randn(output_size, hidden_size + input_size) * 0.1
        
        self.h = np.zeros(hidden_size)
        self.states_history = []
        self.max_history = 1000
        
    def forward(self, x):
        with self.lock:
            u = np.tanh(np.dot(self.W_in, x) + np.dot(self.W, self.h) + self.b)
            self.h = (1 - 0.3) * self.h + 0.3 * u
            
            augmented = np.concatenate([self.h, x])
            y = np.dot(self.W_out, augmented)
            
            self.states_history.append(self.h.copy())
            if len(self.states_history) > self.max_history:
                self.states_history.pop(0)
            
            return y, self.h.copy()
    
    def train_output_layer(self, X_train, y_train, ridge_alpha=1e-5):
        with self.lock:
            if len(X_train) == 0:
                return
            
            X_train = np.array(X_train)
            y_train = np.array(y_train)
            
            if len(X_train.shape) == 1:
                X_train = X_train.reshape(1, -1)
            if len(y_train.shape) == 1:
                y_train = y_train.reshape(1, -1)
            
            M = X_train.T @ X_train + ridge_alpha * np.eye(X_train.shape[1])
            P = X_train.T @ y_train
            
            try:
                self.W_out = np.linalg.solve(M, P).T
            except np.linalg.LinAlgError:
                self.W_out = np.linalg.pinv(M) @ P.T
    
    def reset_state(self):
        with self.lock:
            self.h = np.zeros(self.hidden_size)
            self.states_history.clear()
    
    def get_state_size(self):
        return self.hidden_size
    
    def get_connectivity_score(self):
        total_weights = self.W.size
        nonzero = np.count_nonzero(self.W)
        return nonzero / total_weights if total_weights > 0 else 0


class TemporalDifferenceMemory:
    def __init__(self, state_size=11, esn_hidden=100):
        self.state_size = state_size
        self.esn_hidden = esn_hidden
        self.lock = threading.Lock()
        
        self.esn = EchoStateNetwork(
            input_size=state_size,
            hidden_size=esn_hidden,
            output_size=3,
            spectral_radius=0.95
        )
        
        self.value_net = np.random.randn(esn_hidden + state_size, 1) * 0.01
        self.td_errors = deque(maxlen=100)
        self.learning_rate = 0.01
        
    def predict_next_state(self, state):
        with self.lock:
            y, hidden = self.esn.forward(state)
            return y
    
    def compute_td_error(self, state, reward, next_state, gamma=0.99):
        with self.lock:
            y1, h1 = self.esn.forward(state)
            y2, h2 = self.esn.forward(next_state)
            
            v1 = np.dot(self.value_net.T, np.concatenate([h1, state]))[0, 0]
            v2 = np.dot(self.value_net.T, np.concatenate([h2, next_state]))[0, 0]
            
            td_error = reward + gamma * v2 - v1
            self.td_errors.append(td_error)
            
            return td_error
    
    def update_value_network(self, state, reward, next_state, gamma=0.99):
        with self.lock:
            td_error = self.compute_td_error(state, reward, next_state, gamma)
            
            y1, h1 = self.esn.forward(state)
            features = np.concatenate([h1, state])
            
            self.value_net += self.learning_rate * td_error * features.reshape(-1, 1)
            
            return td_error
    
    def get_average_td_error(self):
        with self.lock:
            if len(self.td_errors) == 0:
                return 0
            return np.mean(list(self.td_errors))
    
    def reset(self):
        with self.lock:
            self.esn.reset_state()
            self.td_errors.clear()


from collections import deque

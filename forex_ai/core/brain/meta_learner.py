import numpy as np
import threading
from datetime import datetime

class EvolutionaryMetaLearner:
    def __init__(self, population_size=30, num_weights=20):
        self.population_size = population_size
        self.num_weights = num_weights
        self.lock = threading.Lock()
        
        self.population = np.random.uniform(-0.5, 0.5, (population_size, num_weights))
        self.fitness_scores = np.zeros(population_size)
        self.generation = 0
        self.best_individual = self.population[0].copy()
        self.best_fitness = 0
        self.fitness_history = []
        self.max_history = 100
        
    def evaluate_individual(self, individual, performance_data):
        with self.lock:
            score = 0
            
            if 'win_rate' in performance_data:
                score += performance_data['win_rate'] * individual[0]
            
            if 'profit_factor' in performance_data:
                score += min(performance_data['profit_factor'], 3.0) / 3.0 * individual[1]
            
            if 'avg_win' in performance_data and 'avg_loss' in performance_data:
                if performance_data['avg_loss'] != 0:
                    rr = performance_data['avg_win'] / abs(performance_data['avg_loss'])
                    score += min(rr, 3.0) / 3.0 * individual[2]
            
            if 'trades_count' in performance_data:
                trade_score = min(performance_data['trades_count'], 100) / 100.0
                score += trade_score * individual[3]
            
            return np.clip(score, 0, 1)
    
    def evaluate_population(self, recent_trades):
        with self.lock:
            if not recent_trades or len(recent_trades) == 0:
                self.fitness_scores = np.ones(self.population_size) * 0.5
                return
            
            pnls = [t['pnl'] for t in recent_trades]
            wins = len([p for p in pnls if p > 0])
            total_trades = len(recent_trades)
            
            performance_data = {
                'win_rate': wins / total_trades if total_trades > 0 else 0,
                'profit_factor': sum([p for p in pnls if p > 0]) / (abs(sum([p for p in pnls if p < 0])) + 1e-6),
                'avg_win': np.mean([p for p in pnls if p > 0]) if wins > 0 else 0,
                'avg_loss': np.mean([p for p in pnls if p < 0]) if (total_trades - wins) > 0 else 0,
                'trades_count': total_trades
            }
            
            for i, individual in enumerate(self.population):
                self.fitness_scores[i] = self.evaluate_individual(individual, performance_data)
            
            best_idx = np.argmax(self.fitness_scores)
            if self.fitness_scores[best_idx] > self.best_fitness:
                self.best_fitness = self.fitness_scores[best_idx]
                self.best_individual = self.population[best_idx].copy()
            
            self.fitness_history.append({
                'generation': self.generation,
                'best_fitness': self.best_fitness,
                'avg_fitness': np.mean(self.fitness_scores),
                'worst_fitness': np.min(self.fitness_scores)
            })
            
            if len(self.fitness_history) > self.max_history:
                self.fitness_history.pop(0)
    
    def evolve(self):
        with self.lock:
            if np.sum(self.fitness_scores) == 0:
                self.fitness_scores = np.ones(self.population_size) * 0.01
            
            normalized_fitness = self.fitness_scores / (np.sum(self.fitness_scores) + 1e-8)
            
            elite_size = max(2, self.population_size // 5)
            elite_indices = np.argsort(self.fitness_scores)[-elite_size:]
            
            new_population = self.population[elite_indices].copy()
            
            while len(new_population) < self.population_size:
                parent1_idx = np.random.choice(self.population_size, p=normalized_fitness)
                parent2_idx = np.random.choice(self.population_size, p=normalized_fitness)
                
                parent1 = self.population[parent1_idx]
                parent2 = self.population[parent2_idx]
                
                crossover_point = np.random.randint(0, self.num_weights)
                child = np.concatenate([parent1[:crossover_point], parent2[crossover_point:]])
                
                mutation_rate = 0.1
                mutation_mask = np.random.rand(self.num_weights) < mutation_rate
                child[mutation_mask] += np.random.normal(0, 0.1, np.sum(mutation_mask))
                
                child = np.clip(child, -1, 1)
                new_population = np.vstack([new_population, child])
            
            self.population = new_population[:self.population_size]
            self.generation += 1
    
    def get_best_weights(self):
        with self.lock:
            return self.best_individual.copy()
    
    def get_evolution_stats(self):
        with self.lock:
            if len(self.fitness_history) == 0:
                return {
                    'generation': self.generation,
                    'best_fitness': 0,
                    'avg_fitness': 0,
                    'improvement_trend': 0
                }
            
            last_record = self.fitness_history[-1]
            
            improvement_trend = 0
            if len(self.fitness_history) > 1:
                recent = np.array([r['avg_fitness'] for r in self.fitness_history[-10:]])
                older = np.array([r['avg_fitness'] for r in self.fitness_history[:-10]])
                if len(older) > 0:
                    improvement_trend = (np.mean(recent) - np.mean(older)) / (np.mean(older) + 1e-8)
            
            return {
                'generation': self.generation,
                'best_fitness': self.best_fitness,
                'avg_fitness': last_record['avg_fitness'],
                'worst_fitness': last_record['worst_fitness'],
                'improvement_trend': improvement_trend,
                'diversity': np.mean(np.std(self.population, axis=0))
            }
    
    def reset(self):
        with self.lock:
            self.population = np.random.uniform(-0.5, 0.5, (self.population_size, self.num_weights))
            self.fitness_scores = np.zeros(self.population_size)
            self.generation = 0
            self.best_fitness = 0
            self.fitness_history.clear()


class AdaptiveWeighting:
    def __init__(self, num_components=4):
        self.num_components = num_components
        self.lock = threading.Lock()
        
        self.weights = np.ones(num_components) / num_components
        self.meta_learner = EvolutionaryMetaLearner(
            population_size=20,
            num_weights=num_components
        )
        self.performance_history = []
        self.update_interval = 50
        self.update_counter = 0
        
    def update_weights(self, expert_scores, esn_score, bayesian_score, predictive_score):
        with self.lock:
            scores = np.array([expert_scores, esn_score, bayesian_score, predictive_score], dtype=np.float32)
            scores = np.clip(scores, 0, 1)
            
            if np.sum(scores) > 0:
                self.weights = scores / np.sum(scores)
            else:
                self.weights = np.ones(self.num_components) / self.num_components
            
            self.performance_history.append({
                'expert_scores': expert_scores,
                'esn_score': esn_score,
                'bayesian_score': bayesian_score,
                'predictive_score': predictive_score,
                'weights': self.weights.copy()
            })
            
            if len(self.performance_history) > 200:
                self.performance_history.pop(0)
            
            self.update_counter += 1
            
            if self.update_counter % self.update_interval == 0:
                recent_trades = self._get_recent_performance()
                if recent_trades:
                    self.meta_learner.evaluate_population(recent_trades)
                    self.meta_learner.evolve()
    
    def _get_recent_performance(self):
        if len(self.performance_history) >= 10:
            return self.performance_history[-10:]
        return None
    
    def get_weights(self):
        with self.lock:
            return self.weights.copy()
    
    def get_component_contribution(self):
        with self.lock:
            return {
                'experts': self.weights[0],
                'esn': self.weights[1],
                'bayesian': self.weights[2],
                'predictive': self.weights[3]
            }
    
    def reset_meta_learner(self):
        with self.lock:
            self.meta_learner.reset()

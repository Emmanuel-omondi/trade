import numpy as np
import threading


class EvolutionaryMetaLearner:
    def __init__(self, population_size=30, num_weights=4):
        self.population_size = population_size
        self.num_weights     = num_weights
        self.lock            = threading.Lock()
        self.population      = np.random.uniform(-0.5, 0.5, (population_size, num_weights))
        self.fitness_scores  = np.ones(population_size) * 0.5
        self.generation      = 0
        self.best_individual = self.population[0].copy()
        self.best_fitness    = 0.0
        self.fitness_history = []

    def evaluate_population(self, trade_records):
        with self.lock:
            if not trade_records:
                return
            pnls = [float(t.get('pnl', t.get('total_pnl', 0.0))) for t in trade_records]
            if not pnls:
                return
            total  = len(pnls)
            wins   = [p for p in pnls if p > 0]
            losses = [p for p in pnls if p < 0]
            perf   = {
                'win_rate':      len(wins) / total,
                'profit_factor': sum(wins) / (abs(sum(losses)) + 1e-6),
                'avg_win':       float(np.mean(wins))   if wins   else 0.0,
                'avg_loss':      float(np.mean(losses)) if losses else 0.0,
                'trades_count':  total
            }
            for i, ind in enumerate(self.population):
                score = 0.0
                score += perf['win_rate']              * max(ind[0], 0)
                score += min(perf['profit_factor'], 3) / 3.0 * max(ind[1], 0)
                if perf['avg_loss'] != 0:
                    rr = perf['avg_win'] / (abs(perf['avg_loss']) + 1e-8)
                    score += min(rr, 3) / 3.0 * max(ind[2], 0)
                score += min(perf['trades_count'], 100) / 100.0 * max(ind[3] if len(ind) > 3 else 0.5, 0)
                self.fitness_scores[i] = np.clip(score, 0, 1)
            best_idx = np.argmax(self.fitness_scores)
            if self.fitness_scores[best_idx] > self.best_fitness:
                self.best_fitness    = float(self.fitness_scores[best_idx])
                self.best_individual = self.population[best_idx].copy()
            self.fitness_history.append({
                'generation':   self.generation,
                'best_fitness': self.best_fitness,
                'avg_fitness':  float(np.mean(self.fitness_scores))
            })
            if len(self.fitness_history) > 100:
                self.fitness_history.pop(0)

    def evolve(self):
        with self.lock:
            total = np.sum(self.fitness_scores)
            probs = self.fitness_scores / (total + 1e-8) if total > 0 else np.ones(self.population_size) / self.population_size
            elite_n   = max(2, self.population_size // 5)
            elite_idx = np.argsort(self.fitness_scores)[-elite_n:]
            new_pop   = list(self.population[elite_idx])
            while len(new_pop) < self.population_size:
                i1, i2 = np.random.choice(self.population_size, 2, p=probs)
                pt = np.random.randint(0, self.num_weights)
                child = np.concatenate([self.population[i1][:pt], self.population[i2][pt:]])
                mask  = np.random.rand(self.num_weights) < 0.1
                child[mask] += np.random.normal(0, 0.1, mask.sum())
                new_pop.append(np.clip(child, -1, 1))
            self.population = np.array(new_pop[:self.population_size])
            self.generation += 1

    def get_best_weights(self):
        with self.lock:
            return self.best_individual.copy()

    def get_stats(self):
        with self.lock:
            last = self.fitness_history[-1] if self.fitness_history else {}
            return {
                'generation':   self.generation,
                'best_fitness': self.best_fitness,
                'avg_fitness':  last.get('avg_fitness', 0.0)
            }

    def reset(self):
        with self.lock:
            self.population     = np.random.uniform(-0.5, 0.5, (self.population_size, self.num_weights))
            self.fitness_scores = np.ones(self.population_size) * 0.5
            self.generation     = 0
            self.best_fitness   = 0.0
            self.fitness_history.clear()


class AdaptiveWeighting:
    def __init__(self, num_components=4):
        self.num_components  = num_components
        self.lock            = threading.Lock()
        self.weights         = np.ones(num_components) / num_components
        self.meta_learner    = EvolutionaryMetaLearner(population_size=20, num_weights=num_components)
        self.score_history   = []
        self.update_counter  = 0
        self.update_interval = 50

    def update_weights(self, expert_scores, esn_score, bayesian_score, predictive_score):
        with self.lock:
            scores = np.array([
                float(expert_scores),
                float(esn_score),
                float(bayesian_score),
                float(predictive_score)
            ], dtype=np.float32)
            scores = np.clip(scores, 0, 1)
            total  = scores.sum()
            self.weights = scores / total if total > 0 else np.ones(self.num_components) / self.num_components
            self.score_history.append(scores)
            if len(self.score_history) > 200:
                self.score_history.pop(0)
            self.update_counter += 1

    def feed_trade_results(self, trade_records):
        if not trade_records:
            return
        self.meta_learner.evaluate_population(trade_records)
        if self.update_counter % self.update_interval == 0:
            self.meta_learner.evolve()
            best = self.meta_learner.get_best_weights()
            with self.lock:
                best = np.clip(np.abs(best), 0, 1)
                total = best.sum()
                if total > 0:
                    self.weights = best / total

    def get_weights(self):
        with self.lock:
            return self.weights.copy()

    def get_component_contribution(self):
        with self.lock:
            return {
                'experts':    float(self.weights[0]),
                'esn':        float(self.weights[1]),
                'bayesian':   float(self.weights[2]),
                'predictive': float(self.weights[3])
            }

    def reset_meta_learner(self):
        with self.lock:
            self.meta_learner.reset()

"""
Genetic algorithm for the CVRP (route-first / cluster-second, after Prins 2004).

Chromosome  : a "giant tour", i.e. a permutation of all customers, no depot.
Decoding    : Prins' split cuts the giant tour optimally (for that order) into
              capacity-feasible trips that use at most `n_vehicles` routes.
Fitness     : total distance of the decoded solution (lower is better);
              giant tours that cannot be split within the fleet limit get a
              large penalty.
Selection   : k-tournament.
Crossover   : order crossover (OX). It keeps a slice of parent 1 in place and
              fills the rest in parent 2's relative order, so the child is
              always a valid permutation.
Mutation    : swap two customers, or invert a segment (50/50).
Local search: every offspring is decoded, each route is improved with 2-opt,
              and the improved routes are written back into the chromosome
              (Lamarckian learning).
Replacement : generational with elitism (the best `elite_count` individuals
              survive unchanged). Children whose cost equals an existing
              individual's are rejected as probable clones to keep diversity.
Stopping    : time limit, maximum generations, or `stall_generations`
              generations without improvement — whichever comes first.

By default one individual is seeded with the greedy nearest-neighbour tour.
Because split is optimal for a fixed order and elitism keeps the best
individual, the GA can never return a worse solution than greedy when greedy
fits in the fleet. Set `seed_with_greedy=False` to measure the GA on its own.
"""

from __future__ import annotations

import random
import time
from dataclasses import asdict, dataclass
from typing import List, Optional, Tuple

from models.routing_models.cvrp import CVRPInstance, CVRPSolution, INF, solution_distance, split, two_opt
from models.routing_models.greedy import nearest_neighbour_routes

PENALTY_PER_EXTRA_ROUTE = 1e6


@dataclass
class GAParams:
    population_size: int = 30
    tournament_size: int = 2
    crossover_rate: float = 0.9
    mutation_rate: float = 0.2
    local_search_rate: float = 1.0
    elite_count: int = 2
    max_generations: int = 10_000
    stall_generations: int = 150
    seed_with_greedy: bool = True

    @classmethod
    def from_dict(cls, values: Optional[dict]) -> "GAParams":
        values = values or {}
        known = {k: v for k, v in values.items() if k in cls.__dataclass_fields__}
        return cls(**known)


Individual = Tuple[float, List[int], List[List[int]]]   # (cost, giant tour, routes)


class GeneticAlgorithm:
    def __init__(self, inst: CVRPInstance, params: GAParams, seed: int = 0):
        self.inst = inst
        self.p = params
        self.rng = random.Random(seed)
        self.evaluations = 0

    # ── decoding / evaluation ────────────────────────────────────────────────
    def evaluate(self, tour: List[int]) -> Individual:
        self.evaluations += 1
        cost, routes = split(self.inst, tour, max_routes=self.inst.n_vehicles)
        if cost == INF:
            # Not splittable within the fleet: use the unlimited split, penalised.
            cost, routes = split(self.inst, tour)
            cost += PENALTY_PER_EXTRA_ROUTE * (len(routes) - self.inst.n_vehicles)
        return cost, tour, routes

    def improve(self, ind: Individual) -> Individual:
        """2-opt every route of the decoded solution, write it back, re-split."""
        _, _, routes = ind
        new_tour = [c for r in routes for c in two_opt(self.inst, r)]
        improved = self.evaluate(new_tour)
        return improved if improved[0] <= ind[0] else ind

    # ── operators ────────────────────────────────────────────────────────────
    def tournament(self, pop: List[Individual]) -> Individual:
        contenders = self.rng.sample(pop, min(self.p.tournament_size, len(pop)))
        return min(contenders, key=lambda ind: ind[0])

    def order_crossover(self, p1: List[int], p2: List[int]) -> List[int]:
        n = len(p1)
        if n < 2:
            return list(p1)
        i, j = sorted(self.rng.sample(range(n), 2))
        child: List[Optional[int]] = [None] * n
        child[i:j + 1] = p1[i:j + 1]
        taken = set(p1[i:j + 1])
        fill = [g for g in (p2[(j + 1 + k) % n] for k in range(n)) if g not in taken]
        positions = [(j + 1 + k) % n for k in range(n - (j - i + 1))]
        for pos, gene in zip(positions, fill):
            child[pos] = gene
        return child  # type: ignore[return-value]

    def mutate(self, tour: List[int]) -> List[int]:
        n = len(tour)
        if n < 2:
            return tour
        tour = list(tour)
        i, j = sorted(self.rng.sample(range(n), 2))
        if self.rng.random() < 0.5:
            tour[i], tour[j] = tour[j], tour[i]
        else:
            tour[i:j + 1] = reversed(tour[i:j + 1])
        return tour

    # ── main loop ────────────────────────────────────────────────────────────
    def initial_population(self) -> List[Individual]:
        customers = list(range(1, self.inst.n_customers + 1))
        pop: List[Individual] = []
        if self.p.seed_with_greedy:
            greedy_tour = [c for r in nearest_neighbour_routes(self.inst) for c in r]
            pop.append(self.improve(self.evaluate(greedy_tour)))
        seen = {round(ind[0], 6) for ind in pop}
        attempts = 0
        while len(pop) < self.p.population_size and attempts < self.p.population_size * 20:
            attempts += 1
            tour = customers[:]
            self.rng.shuffle(tour)
            ind = self.evaluate(tour)
            if self.rng.random() < self.p.local_search_rate:
                ind = self.improve(ind)
            key = round(ind[0], 6)
            if key not in seen:
                seen.add(key)
                pop.append(ind)
        return pop

    def run(self, time_limit: float) -> Tuple[Individual, dict]:
        start = time.perf_counter()
        deadline = start + time_limit
        pop = sorted(self.initial_population(), key=lambda ind: ind[0])
        best = pop[0]
        generation = stall = 0
        history = [round(best[0], 4)]

        while generation < self.p.max_generations and stall < self.p.stall_generations:
            if time.perf_counter() >= deadline:
                break
            generation += 1
            next_pop = pop[: self.p.elite_count]
            seen = {round(ind[0], 6) for ind in next_pop}
            attempts = 0
            while len(next_pop) < self.p.population_size and attempts < self.p.population_size * 10:
                attempts += 1
                if time.perf_counter() >= deadline:
                    break
                p1, p2 = self.tournament(pop), self.tournament(pop)
                if self.rng.random() < self.p.crossover_rate:
                    child = self.order_crossover(p1[1], p2[1])
                else:
                    child = list(p1[1])
                if self.rng.random() < self.p.mutation_rate:
                    child = self.mutate(child)
                ind = self.evaluate(child)
                if self.rng.random() < self.p.local_search_rate:
                    ind = self.improve(ind)
                key = round(ind[0], 6)
                if key in seen:
                    continue
                seen.add(key)
                next_pop.append(ind)
            # If the deadline cut a generation short, keep the best of the old population too.
            if len(next_pop) < self.p.population_size:
                for ind in pop:
                    if len(next_pop) >= self.p.population_size:
                        break
                    if round(ind[0], 6) not in seen:
                        seen.add(round(ind[0], 6))
                        next_pop.append(ind)
            pop = sorted(next_pop, key=lambda ind: ind[0])
            if pop[0][0] < best[0] - 1e-9:
                best, stall = pop[0], 0
            else:
                stall += 1
            history.append(round(best[0], 4))

        stats = {
            "generations": generation,
            "evaluations": self.evaluations,
            "stopped_by": ("time_limit" if time.perf_counter() >= deadline
                           else "stall" if stall >= self.p.stall_generations else "max_generations"),
            "best_cost_history": history[-50:],
        }
        return best, stats


def solve(inst: CVRPInstance, *, seed: int = 0, time_limit: Optional[float] = 5.0,
          params: Optional[GAParams | dict] = None, **_) -> CVRPSolution:
    t0 = time.perf_counter()
    if not isinstance(params, GAParams):
        params = GAParams.from_dict(params)
    if inst.n_customers == 0:
        return CVRPSolution(routes=[], distance=0.0, solver="ga", runtime_s=0.0, meta={"params": asdict(params)})
    ga = GeneticAlgorithm(inst, params, seed=seed)
    best, stats = ga.run(time_limit if time_limit is not None else 5.0)
    routes = [r for r in best[2] if r]
    return CVRPSolution(
        routes=routes,
        distance=solution_distance(inst, routes),
        solver="ga",
        runtime_s=time.perf_counter() - t0,
        meta={**stats, "seed": seed, "params": asdict(params),
              "fleet_feasible": len(routes) <= inst.n_vehicles},
    )

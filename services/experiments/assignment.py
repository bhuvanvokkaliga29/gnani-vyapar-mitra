"""Assignment Engine: Deterministic, reproducible allocation of decision instances to experimental variants."""

import hashlib
from typing import List, Tuple
from services.experiments.schemas import VariantType, AssignmentStrategy


class AssignmentEngine:
    """Allocates experimental units to arms using cryptographically stable hashing."""

    @staticmethod
    def assign_variant(
        experiment_id: str,
        scenario_id: str,
        randomization_seed: int = 42,
        strategy: AssignmentStrategy = AssignmentStrategy.DETERMINISTIC_HASH
    ) -> VariantType:
        """Deterministically map an experiment_id, scenario_id, and seed to a VariantType."""
        if strategy == AssignmentStrategy.ROUND_ROBIN:
            # Simple alternating based on scenario sequence hash
            h_int = int(hashlib.md5(f"{scenario_id}".encode()).hexdigest()[:8], 16)
            return VariantType.TREATMENT if (h_int % 2 == 1) else VariantType.CONTROL

        # Default: Deterministic SHA-256 Hash
        key = f"{experiment_id}:{scenario_id}:{randomization_seed}".encode("utf-8")
        hash_digest = hashlib.sha256(key).hexdigest()
        # Take first 8 hex characters as integer
        hash_int = int(hash_digest[:8], 16)

        # 50/50 allocation
        return VariantType.TREATMENT if (hash_int % 2 == 1) else VariantType.CONTROL

    @staticmethod
    def assign_population(
        experiment_id: str,
        scenario_ids: List[str],
        randomization_seed: int = 42,
        strategy: AssignmentStrategy = AssignmentStrategy.DETERMINISTIC_HASH
    ) -> List[Tuple[str, VariantType]]:
        """Assign an entire population list of scenario IDs to variants."""
        assignments = []
        for scenario_id in scenario_ids:
            variant = AssignmentEngine.assign_variant(
                experiment_id=experiment_id,
                scenario_id=scenario_id,
                randomization_seed=randomization_seed,
                strategy=strategy
            )
            assignments.append((scenario_id, variant))
        return assignments

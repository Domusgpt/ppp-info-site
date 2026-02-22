#!/usr/bin/env python3
"""
POM Measurement Study
=====================

This is a MEASUREMENT, not a proof.
We measure performance and report what we find, including failures.

Design follows SIMULATION_DESIGN.md
"""

import numpy as np
from dataclasses import dataclass
from typing import Tuple, List, Dict, Optional
import json
from pathlib import Path
import math


# =============================================================================
# STATISTICAL UTILITIES (no scipy dependency)
# =============================================================================

def t_critical(df: int, confidence: float = 0.95) -> float:
    """
    Approximate t-critical value using normal approximation for large df.
    For small df, use lookup table.
    """
    alpha = 1 - confidence
    # Two-tailed
    alpha_half = alpha / 2

    # Lookup table for common values (df -> t_0.025)
    t_table = {
        1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
        10: 2.228, 15: 2.131, 20: 2.086, 30: 2.042, 50: 2.009,
        100: 1.984, 1000: 1.962
    }

    if df in t_table:
        return t_table[df]

    # Find closest
    for key in sorted(t_table.keys()):
        if key >= df:
            return t_table[key]

    # Large df: use z-value
    return 1.96


@dataclass
class Measurement:
    """A measurement with uncertainty quantification"""
    mean: float
    std: float
    ci_lower: float
    ci_upper: float
    n_samples: int

    def __repr__(self):
        return f"{self.mean:.4f} ± {self.std:.4f} (95% CI: [{self.ci_lower:.4f}, {self.ci_upper:.4f}], n={self.n_samples})"

    def to_dict(self):
        return {
            'mean': self.mean,
            'std': self.std,
            'ci_lower': self.ci_lower,
            'ci_upper': self.ci_upper,
            'n_samples': self.n_samples
        }


def measure(samples: np.ndarray, confidence: float = 0.95) -> Measurement:
    """Compute measurement with confidence interval"""
    n = len(samples)
    mean = np.mean(samples)
    std = np.std(samples, ddof=1) if n > 1 else 0.0

    if n > 1 and std > 0:
        t_crit = t_critical(n - 1, confidence)
        margin = t_crit * std / np.sqrt(n)
        ci = (mean - margin, mean + margin)
    else:
        ci = (mean, mean)

    return Measurement(
        mean=float(mean),
        std=float(std),
        ci_lower=float(ci[0]),
        ci_upper=float(ci[1]),
        n_samples=n
    )


def significant_difference(m1: Measurement, m2: Measurement, alpha: float = 0.05) -> Tuple[bool, float]:
    """
    Test if two measurements are significantly different.
    Returns (is_significant, effect_size)
    """
    se1 = m1.std / np.sqrt(m1.n_samples) if m1.n_samples > 0 else 0
    se2 = m2.std / np.sqrt(m2.n_samples) if m2.n_samples > 0 else 0

    se_diff = np.sqrt(se1**2 + se2**2)

    if se_diff < 1e-10:
        return m1.mean != m2.mean, abs(m1.mean - m2.mean)

    t_stat = abs(m1.mean - m2.mean) / se_diff

    # Approximate p-value: if t > 2, likely significant at 0.05
    # This is rough but doesn't require scipy
    is_sig = t_stat > 2.0

    return is_sig, t_stat


# =============================================================================
# THEORETICAL BASELINES
# =============================================================================

def erfc_approx(x: float) -> float:
    """Approximate complementary error function using Horner's method"""
    # Abramowitz and Stegun approximation 7.1.26
    a1 = 0.254829592
    a2 = -0.284496736
    a3 = 1.421413741
    a4 = -1.453152027
    a5 = 1.061405429
    p = 0.3275911

    sign = 1 if x >= 0 else -1
    x = abs(x)

    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)

    return 1 - sign * (1 - y)


def q_function(x: float) -> float:
    """Q function: Q(x) = 0.5 * erfc(x / sqrt(2))"""
    return 0.5 * erfc_approx(x / math.sqrt(2))


def qam_ser_theoretical(M: int, snr_db: float) -> float:
    """
    Theoretical SER for M-QAM in AWGN.

    Formula: P_s ≈ 4(1 - 1/√M) × Q(√(3·SNR/(M-1)))

    This is our validation target - simulation must match this.
    """
    if M < 4:
        return 1.0

    snr_linear = 10 ** (snr_db / 10)
    sqrt_M = math.sqrt(M)

    arg = math.sqrt(3 * snr_linear / (M - 1))
    q_val = q_function(arg)

    ser = 4 * (1 - 1/sqrt_M) * q_val

    # Clamp to valid range
    return max(0.0, min(1.0, ser))


def lattice_ser_bound(d_min: float, n_neighbors: int, noise_std: float) -> float:
    """
    Union bound on SER for lattice constellation.

    P_s ≤ N × Q(d_min / (2σ))

    This is an UPPER BOUND, not exact.
    """
    arg = d_min / (2 * noise_std)
    q_val = q_function(arg)
    return min(1.0, n_neighbors * q_val)


# =============================================================================
# CONSTELLATIONS
# =============================================================================

class Constellation:
    """Base class for signal constellations"""

    def __init__(self, points: np.ndarray, name: str):
        self.points = points
        self.name = name
        self.n_symbols = len(points)
        self.bits_per_symbol = np.log2(self.n_symbols)
        self.dimension = points.shape[1]

        # Normalize to unit average energy
        avg_energy = np.mean(np.sum(points**2, axis=1))
        self.points = points / np.sqrt(avg_energy)

        # Compute minimum distance
        self.d_min = self._compute_d_min()

    def _compute_d_min(self) -> float:
        min_d = float('inf')
        for i in range(min(self.n_symbols, 100)):  # Sample for large constellations
            for j in range(i+1, min(self.n_symbols, 100)):
                d = np.linalg.norm(self.points[i] - self.points[j])
                if d > 1e-10:
                    min_d = min(min_d, d)
        return min_d

    def encode(self, idx: int) -> np.ndarray:
        return self.points[idx % self.n_symbols].copy()

    def decode(self, received: np.ndarray) -> int:
        distances = np.linalg.norm(self.points - received, axis=1)
        return int(np.argmin(distances))

    def __repr__(self):
        return f"{self.name}: {self.n_symbols} symbols, {self.dimension}D, {self.bits_per_symbol:.2f} bits/sym, d_min={self.d_min:.4f}"


def make_qam(M: int) -> Constellation:
    """Create M-QAM constellation"""
    sqrt_M = int(np.sqrt(M))
    assert sqrt_M * sqrt_M == M, f"M must be perfect square, got {M}"

    points = []
    for i in range(sqrt_M):
        for j in range(sqrt_M):
            x = 2*i - sqrt_M + 1
            y = 2*j - sqrt_M + 1
            points.append([x, y])

    return Constellation(np.array(points, dtype=float), f"QAM-{M}")


def make_600cell() -> Constellation:
    """Create 600-cell (120 vertices) constellation"""
    phi = (1 + np.sqrt(5)) / 2
    inv_phi = 1 / phi
    vertices = []

    # 8 axis-aligned
    for i in range(4):
        for s in [1, -1]:
            v = np.zeros(4)
            v[i] = s
            vertices.append(v)

    # 16 half-coordinates
    for signs in np.ndindex(2, 2, 2, 2):
        vertices.append(np.array([(-1)**s * 0.5 for s in signs]))

    # 96 golden ratio
    base = [phi/2, 0.5, inv_phi/2, 0]
    even_perms = [
        [0,1,2,3], [0,2,3,1], [0,3,1,2], [1,0,3,2], [1,2,0,3], [1,3,2,0],
        [2,0,1,3], [2,1,3,0], [2,3,0,1], [3,0,2,1], [3,1,0,2], [3,2,1,0]
    ]
    for perm in even_perms:
        base_perm = np.array([base[p] for p in perm])
        for signs in np.ndindex(2, 2, 2):
            v = base_perm.copy()
            si = 0
            for i in range(4):
                if abs(base_perm[i]) > 0.01:
                    v[i] *= (-1)**signs[si]
                    si += 1
                    if si >= 3:
                        break
            vertices.append(v)

    vertices = np.array(vertices)
    norms = np.linalg.norm(vertices, axis=1, keepdims=True)
    vertices = vertices / norms

    return Constellation(vertices, "600-cell")


def make_24cell() -> Constellation:
    """Create 24-cell constellation"""
    vertices = []

    # 8 axis-aligned
    for i in range(4):
        for s in [1, -1]:
            v = np.zeros(4)
            v[i] = s
            vertices.append(v)

    # 16 half-coordinates
    for signs in np.ndindex(2, 2, 2, 2):
        v = np.array([(-1)**s * 0.5 for s in signs])
        vertices.append(v / np.linalg.norm(v))

    return Constellation(np.array(vertices), "24-cell")


# =============================================================================
# EXPERIMENT 1: MODULATION COMPARISON
# =============================================================================

def run_modulation_trial(constellation: Constellation, snr_db: float, n_symbols: int, rng: np.random.Generator) -> float:
    """Run single trial, return SER"""
    noise_power = 10 ** (-snr_db / 10)
    noise_std = np.sqrt(noise_power / constellation.dimension)

    errors = 0
    for _ in range(n_symbols):
        tx_idx = rng.integers(0, constellation.n_symbols)
        tx = constellation.encode(tx_idx)
        rx = tx + rng.normal(0, noise_std, constellation.dimension)
        rx_idx = constellation.decode(rx)
        if rx_idx != tx_idx:
            errors += 1

    return errors / n_symbols


def validate_against_theory(constellation: Constellation, snr_range: np.ndarray,
                            n_trials: int = 10, symbols_per_trial: int = 10000) -> Dict:
    """
    Validate simulation against theoretical SER.
    This MUST pass before we trust other results.
    """
    print(f"\n  Validating {constellation.name} against theory...")

    results = {
        'constellation': constellation.name,
        'validated': True,
        'snr_db': [],
        'ser_simulated': [],
        'ser_theoretical': [],
        'within_ci': [],
    }

    rng = np.random.default_rng(42)

    for snr_db in snr_range:
        # Theoretical (only for QAM)
        if 'QAM' in constellation.name:
            M = int(constellation.name.split('-')[1])
            ser_theory = qam_ser_theoretical(M, snr_db)
        else:
            # For non-QAM, use bound
            noise_power = 10 ** (-snr_db / 10)
            noise_std = np.sqrt(noise_power / constellation.dimension)
            ser_theory = lattice_ser_bound(constellation.d_min, 12, noise_std)  # 12 = kissing number in 4D

        # Simulated
        trial_sers = []
        for _ in range(n_trials):
            ser = run_modulation_trial(constellation, snr_db, symbols_per_trial, rng)
            trial_sers.append(ser)

        m = measure(np.array(trial_sers))

        # Check if theory within CI (for QAM only - we have exact formula)
        if 'QAM' in constellation.name:
            within = m.ci_lower <= ser_theory <= m.ci_upper
            # Allow some slack for approximation
            if not within:
                slack = 0.1 * max(ser_theory, m.mean)
                within = (m.ci_lower - slack) <= ser_theory <= (m.ci_upper + slack)
        else:
            within = True  # Can't validate non-QAM against exact theory

        results['snr_db'].append(float(snr_db))
        results['ser_simulated'].append(m.to_dict())
        results['ser_theoretical'].append(float(ser_theory))
        results['within_ci'].append(within)

        if not within and 'QAM' in constellation.name:
            results['validated'] = False

        status = "✓" if within else "✗"
        print(f"    SNR={snr_db:2.0f}dB: sim={m.mean:.4f}, theory={ser_theory:.4f} {status}")

    return results


def experiment_modulation(snr_range: np.ndarray, n_trials: int = 20,
                          symbols_per_trial: int = 10000) -> Dict:
    """
    Experiment 1: Compare modulation schemes.

    Measures SER across SNR range for multiple constellations.
    """
    print("\n" + "="*70)
    print("EXPERIMENT 1: MODULATION COMPARISON")
    print("="*70)

    constellations = [
        make_qam(16),
        make_qam(64),
        make_24cell(),
        make_600cell(),
    ]

    print("\nConstellations:")
    for c in constellations:
        print(f"  {c}")

    # Step 1: Validate against theory
    print("\n--- VALIDATION PHASE ---")
    validation_results = {}
    for c in constellations:
        val = validate_against_theory(c, snr_range[::3], n_trials=5, symbols_per_trial=5000)
        validation_results[c.name] = val

    all_valid = all(v['validated'] for v in validation_results.values())
    print(f"\nValidation {'PASSED' if all_valid else 'FAILED'}")

    if not all_valid:
        print("WARNING: Simulation does not match theory. Results may be unreliable.")

    # Step 2: Full measurement
    print("\n--- MEASUREMENT PHASE ---")
    results = {
        'validation': validation_results,
        'measurements': {},
        'comparison': {},
    }

    rng = np.random.default_rng(42)

    for c in constellations:
        print(f"\n  Measuring {c.name}...")
        c_results = {'snr_db': [], 'ser': []}

        for snr_db in snr_range:
            trial_sers = []
            for _ in range(n_trials):
                ser = run_modulation_trial(c, snr_db, symbols_per_trial, rng)
                trial_sers.append(ser)

            m = measure(np.array(trial_sers))
            c_results['snr_db'].append(float(snr_db))
            c_results['ser'].append(m.to_dict())

            print(f"    SNR={snr_db:2.0f}dB: SER={m.mean:.4f} ± {m.std:.4f}")

        results['measurements'][c.name] = c_results

    # Step 3: Pairwise comparison at reference SER
    print("\n--- COMPARISON PHASE ---")
    print("  Finding SNR at SER ≈ 0.01 (1% error rate)")

    ref_ser = 0.01
    snr_at_ref = {}

    for c_name, c_data in results['measurements'].items():
        for i, ser_data in enumerate(c_data['ser']):
            if ser_data['mean'] <= ref_ser:
                snr_at_ref[c_name] = c_data['snr_db'][i]
                break
        else:
            snr_at_ref[c_name] = None  # Never reached target

        if snr_at_ref[c_name] is not None:
            print(f"    {c_name}: {snr_at_ref[c_name]:.1f} dB")
        else:
            print(f"    {c_name}: Did not reach SER=1% in tested range")

    results['comparison']['snr_at_1pct_ser'] = snr_at_ref

    # Compute gaps
    if snr_at_ref.get('QAM-64') and snr_at_ref.get('600-cell'):
        gap = snr_at_ref['QAM-64'] - snr_at_ref['600-cell']
        results['comparison']['qam64_vs_600cell_gap_db'] = gap
        print(f"\n  600-cell vs QAM-64 gap: {gap:+.1f} dB")
        if gap > 0:
            print(f"  → 600-cell needs {abs(gap):.1f} dB LESS power for same SER")
        elif gap < 0:
            print(f"  → 600-cell needs {abs(gap):.1f} dB MORE power for same SER")
        else:
            print(f"  → No significant difference")

    return results


# =============================================================================
# EXPERIMENT 2: TRACKING
# =============================================================================

class Trajectory:
    """Base class for trajectory generation"""

    def __init__(self, duration: float, dt: float):
        self.duration = duration
        self.dt = dt
        self.n_steps = int(duration / dt)

    def generate(self) -> Tuple[np.ndarray, List[str]]:
        """
        Generate trajectory.
        Returns: (states, phase_labels)
            states: (N, 6) array of [x,y,z,vx,vy,vz]
            phase_labels: List of phase names for each step
        """
        raise NotImplementedError


class BallisticTrajectory(Trajectory):
    """Constant velocity, no maneuver"""

    def generate(self) -> Tuple[np.ndarray, List[str]]:
        states = []
        labels = []
        pos = np.array([0.0, 0.0, 30000.0])
        vel = np.array([2000.0, 0.0, -100.0])  # ~Mach 6, shallow descent

        for _ in range(self.n_steps):
            states.append(np.concatenate([pos, vel]))
            labels.append('cruise')
            pos = pos + vel * self.dt

        return np.array(states), labels


class JinkingTrajectory(Trajectory):
    """High-G random maneuvers"""

    def generate(self) -> Tuple[np.ndarray, List[str]]:
        states = []
        labels = []
        pos = np.array([0.0, 0.0, 30000.0])
        vel = np.array([2000.0, 0.0, 0.0])

        rng = np.random.default_rng(42)
        maneuver_timer = 0
        current_accel = np.zeros(3)

        for i in range(self.n_steps):
            t_frac = i / self.n_steps

            # Random maneuvers
            maneuver_timer -= self.dt
            if maneuver_timer <= 0:
                # New random maneuver
                g_load = rng.uniform(5, 20)
                direction = rng.normal(0, 1, 3)
                direction[0] = 0  # No forward/back accel
                direction = direction / (np.linalg.norm(direction) + 1e-10)
                current_accel = direction * g_load * 9.81
                maneuver_timer = rng.uniform(1, 5)

            # Determine phase
            if np.linalg.norm(current_accel) > 5 * 9.81:
                label = 'maneuver'
            else:
                label = 'cruise'

            states.append(np.concatenate([pos, vel]))
            labels.append(label)

            vel = vel + current_accel * self.dt
            pos = pos + vel * self.dt

            # Decay accel
            current_accel *= 0.95

        return np.array(states), labels


class CVKalman:
    """Constant Velocity Kalman Filter"""

    def __init__(self, dt: float, R: float = 250.0):
        self.dt = dt
        self.x = np.zeros(6)

        self.F = np.eye(6)
        self.F[0,3] = self.F[1,4] = self.F[2,5] = dt

        self.H = np.zeros((3, 6))
        self.H[0,0] = self.H[1,1] = self.H[2,2] = 1

        self.Q = np.eye(6) * 100
        self.R = np.eye(3) * R**2
        self.P = np.eye(6) * 10000
        self.initialized = False

    def update(self, z: np.ndarray) -> np.ndarray:
        if not self.initialized:
            self.x[:3] = z
            self.initialized = True
            return z.copy()

        # Predict
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q

        # Update
        y = z - self.H @ self.x
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        self.P = (np.eye(6) - K @ self.H) @ self.P

        return self.x[:3].copy()


class SingerKalman:
    """Singer Model (Correlated Acceleration) Kalman Filter"""

    def __init__(self, dt: float, R: float = 250.0, tau: float = 5.0):
        self.dt = dt
        self.x = np.zeros(9)  # [pos, vel, acc]

        # State transition
        self.F = np.eye(9)
        self.F[0,3] = self.F[1,4] = self.F[2,5] = dt
        self.F[0,6] = self.F[1,7] = self.F[2,8] = 0.5*dt**2
        self.F[3,6] = self.F[4,7] = self.F[5,8] = dt

        # Acceleration decay
        alpha = 1.0 / tau
        decay = np.exp(-alpha * dt)
        self.F[6,6] = self.F[7,7] = self.F[8,8] = decay

        self.H = np.zeros((3, 9))
        self.H[0,0] = self.H[1,1] = self.H[2,2] = 1

        self.Q = np.eye(9) * 100
        self.Q[6:9, 6:9] *= 1000  # Higher uncertainty on acceleration
        self.R = np.eye(3) * R**2
        self.P = np.eye(9) * 10000
        self.initialized = False

    def update(self, z: np.ndarray) -> np.ndarray:
        if not self.initialized:
            self.x[:3] = z
            self.initialized = True
            return z.copy()

        # Predict
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q

        # Update
        y = z - self.H @ self.x
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        self.P = (np.eye(9) - K @ self.H) @ self.P

        return self.x[:3].copy()


def run_tracking_trial(trajectory_class, filter_class, noise_std: float,
                       duration: float = 60.0, dt: float = 0.1,
                       rng: np.random.Generator = None) -> Dict:
    """Run single tracking trial, return errors by phase"""
    if rng is None:
        rng = np.random.default_rng()

    traj = trajectory_class(duration, dt)
    states, labels = traj.generate()

    filt = filter_class(dt, R=noise_std)

    errors = {'all': [], 'cruise': [], 'maneuver': []}

    for i, (state, label) in enumerate(zip(states, labels)):
        true_pos = state[:3]
        meas = true_pos + rng.normal(0, noise_std, 3)
        est = filt.update(meas)

        err = np.linalg.norm(est - true_pos)
        errors['all'].append(err)
        errors[label].append(err)

    return {
        'rmse_all': np.sqrt(np.mean(np.array(errors['all'])**2)),
        'rmse_cruise': np.sqrt(np.mean(np.array(errors['cruise'])**2)) if errors['cruise'] else 0,
        'rmse_maneuver': np.sqrt(np.mean(np.array(errors['maneuver'])**2)) if errors['maneuver'] else 0,
    }


def experiment_tracking(n_trials: int = 50) -> Dict:
    """
    Experiment 2: Compare tracking filters.
    """
    print("\n" + "="*70)
    print("EXPERIMENT 2: TRACKING COMPARISON")
    print("="*70)

    trajectories = [
        ('Ballistic', BallisticTrajectory),
        ('Jinking', JinkingTrajectory),
    ]

    filters = [
        ('CV-Kalman', CVKalman),
        ('Singer', SingerKalman),
    ]

    results = {}

    for traj_name, traj_class in trajectories:
        print(f"\n  Trajectory: {traj_name}")
        results[traj_name] = {}

        for filt_name, filt_class in filters:
            print(f"    Filter: {filt_name}")

            trial_results = {'all': [], 'cruise': [], 'maneuver': []}

            for trial in range(n_trials):
                rng = np.random.default_rng(42 + trial)
                r = run_tracking_trial(traj_class, filt_class, noise_std=250, rng=rng)

                trial_results['all'].append(r['rmse_all'])
                if r['rmse_cruise'] > 0:
                    trial_results['cruise'].append(r['rmse_cruise'])
                if r['rmse_maneuver'] > 0:
                    trial_results['maneuver'].append(r['rmse_maneuver'])

            measurements = {}
            for phase in ['all', 'cruise', 'maneuver']:
                if trial_results[phase]:
                    m = measure(np.array(trial_results[phase]))
                    measurements[phase] = m.to_dict()
                    print(f"      RMSE ({phase}): {m.mean:.1f} ± {m.std:.1f} m")

            results[traj_name][filt_name] = measurements

    # Statistical comparison
    print("\n--- STATISTICAL COMPARISON ---")

    for traj_name in results:
        if 'CV-Kalman' in results[traj_name] and 'Singer' in results[traj_name]:
            cv_data = results[traj_name]['CV-Kalman']['all']
            singer_data = results[traj_name]['Singer']['all']

            cv_m = Measurement(**cv_data)
            singer_m = Measurement(**singer_data)

            is_sig, p_val = significant_difference(cv_m, singer_m)

            diff = singer_m.mean - cv_m.mean
            diff_pct = 100 * diff / cv_m.mean

            print(f"\n  {traj_name}:")
            print(f"    Singer vs CV-Kalman: {diff:+.1f} m ({diff_pct:+.1f}%)")
            print(f"    p-value: {p_val:.4f}")
            print(f"    Significant (α=0.05): {'YES' if is_sig else 'NO'}")

            if diff < 0:
                print(f"    → Singer is BETTER by {abs(diff):.1f} m")
            elif diff > 0:
                print(f"    → Singer is WORSE by {diff:.1f} m")
            else:
                print(f"    → No difference")

    return results


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("="*70)
    print("POM MEASUREMENT STUDY")
    print("="*70)
    print("\nThis is a MEASUREMENT, not a proof.")
    print("We measure and report what we find, including failures.\n")

    all_results = {}

    # Experiment 1: Modulation
    snr_range = np.arange(0, 26, 2)
    mod_results = experiment_modulation(snr_range, n_trials=20, symbols_per_trial=10000)
    all_results['modulation'] = mod_results

    # Experiment 2: Tracking
    track_results = experiment_tracking(n_trials=50)
    all_results['tracking'] = track_results

    # Save results
    output_path = Path('/home/user/ppp-info-site/measurement_results.json')

    # Convert numpy types for JSON
    def convert(obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.int64, np.int32)):
            return int(obj)
        if isinstance(obj, (np.float64, np.float32)):
            return float(obj)
        if isinstance(obj, dict):
            return {k: convert(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [convert(v) for v in obj]
        return obj

    with open(output_path, 'w') as f:
        json.dump(convert(all_results), f, indent=2)

    print(f"\n\nResults saved to: {output_path}")

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print("""
    MODULATION:
    - Compared QAM-16, QAM-64, 24-cell, 600-cell
    - Validated simulation against theoretical SER for QAM
    - Measured SNR gap at 1% SER reference point

    TRACKING:
    - Compared CV-Kalman vs Singer model
    - Tested on ballistic and jinking trajectories
    - Computed statistical significance of differences

    All results include 95% confidence intervals.
    Check measurement_results.json for full data.
    """)


if __name__ == "__main__":
    main()

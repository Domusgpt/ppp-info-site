# POM Research Simulation Design

## Philosophy

**We are MEASURING, not PROVING.**

The goal is to determine:
1. Under what conditions (if any) does 4D lattice modulation outperform 2D QAM?
2. Under what conditions (if any) does adaptive tracking outperform standard Kalman?
3. What are the failure modes of each approach?

If POM turns out to be worse than QAM in all conditions, that's a valid result.

---

## Experiment 1: Modulation Comparison

### Research Question
Does the 600-cell constellation provide better error performance than QAM at equivalent spectral efficiency and complexity?

### Hypothesis (to be tested, not proven)
H₀: POM-120 and QAM-64 have equivalent SER at matched spectral efficiency
H₁: They differ (two-tailed test)

### Experimental Design

#### Independent Variables
| Variable | Values | Rationale |
|----------|--------|-----------|
| SNR | 0 to 30 dB, 1 dB steps | Cover full operating range |
| Constellation | QAM-16, QAM-64, QAM-256, POM-24, POM-120 | Match bits/symbol |
| Channel | AWGN, Rayleigh, Rician (K=3,10) | Real-world conditions |
| Trials per point | 100,000 | Statistical significance |

#### Controlled Variables (must be equivalent)
| Variable | How to equalize |
|----------|-----------------|
| Energy per bit (Eb) | Normalize constellations to same Eb/N0 |
| Bits per symbol | Compare QAM-64 (6 bits) vs subset of POM-120 (6.9 bits) |
| Decoder complexity | Both use nearest-neighbor (O(M) for M symbols) |

#### Dependent Variables
| Metric | How measured |
|--------|--------------|
| Symbol Error Rate (SER) | errors / total symbols |
| Bit Error Rate (BER) | Gray-coded bit errors / total bits |
| 95% Confidence Interval | Wilson score interval |

### Theoretical Validation
Before trusting simulation, verify against closed-form:

**QAM SER (AWGN):**
```
P_s ≈ 4(1 - 1/√M) × Q(√(3·Eb/N0·log2(M)/(M-1)))
```

**Lattice SER bound:**
```
P_s ≤ N_neighbors × Q(d_min / (2σ))
```
where d_min = minimum distance, N_neighbors = kissing number

**Required**: Simulation must match theory within 95% CI for known cases (QAM) before we trust results for unknown cases (POM).

### Fairness Checks
1. **Equal Eb/N0**: Both constellations normalized to unit average energy
2. **Equal decoder**: Nearest-neighbor for both (no iterative decoding advantage)
3. **Dimension penalty**: 4D noise has same total power as 2D noise (σ² per dimension scaled)

### Analysis Plan
1. Plot SER vs SNR for all constellations
2. Compute SNR gap at SER = 10⁻³ (standard reference point)
3. Statistical test: Is gap significantly different from 0?
4. Report 95% CI on all measurements

---

## Experiment 2: Lattice Filtering (Decoy Rejection)

### Research Question
Can lattice distance reliably distinguish valid signals from random interference?

### Hypothesis
H₀: Lattice distance distributions are identical for valid vs random signals
H₁: Distributions differ

### Experimental Design

#### Key Insight
This is a **detection theory** problem. We should compute:
- ROC curve (True Positive Rate vs False Positive Rate)
- AUC (Area Under Curve)
- Optimal threshold via Neyman-Pearson criterion

#### Independent Variables
| Variable | Values |
|----------|--------|
| Signal SNR | 0, 5, 10, 15, 20 dB |
| Decoy type | Uniform on S³, Gaussian, Adversarial (near vertices) |
| Lattice | 24-cell, 120-cell, 600-cell |

#### Metrics
| Metric | Definition |
|--------|------------|
| P_D (Detection) | P(accept | valid signal) |
| P_FA (False Alarm) | P(accept | decoy) |
| AUC | Area under ROC curve |
| d' (d-prime) | Sensitivity index = (μ_valid - μ_decoy) / σ_pooled |

### Baseline
**Random guessing**: AUC = 0.5
**Required for "works"**: AUC > 0.7 with p < 0.05

### Failure Mode to Test
**Adversarial decoys**: What if attacker knows the lattice and places decoys near vertices?

---

## Experiment 3: Trajectory Tracking

### Research Question
Does acceleration-state Kalman (Singer model) outperform constant-velocity Kalman on maneuvering targets?

### Hypothesis
H₀: RMSE is equal for both filters
H₁: RMSE differs

### Experimental Design

#### Trajectory Classes
| Class | Description | Expected Winner |
|-------|-------------|-----------------|
| Ballistic | No maneuver | Standard Kalman (simpler) |
| Constant-G | Steady 5g turn | Either (both model this) |
| Jinking | Random 10-20g, τ=2s | Singer (designed for this) |
| Skip-Glide | Alternating phases | Unknown |

#### Independent Variables
| Variable | Values |
|----------|--------|
| Trajectory class | 4 classes above |
| Measurement noise σ | 100, 250, 500, 1000 m |
| Sample rate | 1, 5, 10 Hz |
| Duration | 60, 120, 300 s |
| Runs per condition | 100 (Monte Carlo) |

#### Metrics
| Metric | Definition |
|--------|------------|
| Position RMSE | √(mean(||p_true - p_est||²)) |
| Velocity RMSE | √(mean(||v_true - v_est||²)) |
| Track loss rate | % of time error > 3σ |
| Lag | Cross-correlation peak offset |

### Segmented Analysis
Don't just report overall RMSE. Break down by trajectory phase:
- Cruise segments
- Maneuver onset (first 2s of maneuver)
- Maneuver sustained
- Maneuver exit

The interesting question: Does Singer help during maneuver onset?

### Baseline Comparison
| Filter | States | Process Noise | Expected Strength |
|--------|--------|---------------|-------------------|
| CV-Kalman | 6 (pos, vel) | Constant Q | Simple, good for cruise |
| CA-Kalman | 9 (pos, vel, acc) | Constant Q | Better for constant-G |
| Singer | 9 (pos, vel, acc) | Correlated acc | Better for jinking |
| IMM | 6+9 (model switch) | Adaptive | Gold standard |

**Honest expectation**: Singer should beat CV-Kalman during jinking but may be worse during cruise (overfitting). IMM should beat both but is more complex.

---

## Experiment 4: Anti-Jam Constellation Hopping

### Research Question
Does hash-chain rotation provide security against eavesdropping?

### Experimental Design

#### Threat Model
| Attacker | Capability | Goal |
|----------|------------|------|
| Passive | Observes all transmissions | Decode symbols |
| Active | Can transmit jamming | Cause decode errors |
| Adaptive | Learns from observations | Break the hopping |

#### Metrics
| Metric | Definition |
|--------|------------|
| Eavesdropper SER | Error rate without key |
| Eavesdropper MI | Mutual information I(X;Y) without key |
| Jamming resistance | SER increase under jamming vs baseline |

#### Security Analysis
1. **Entropy of rotation sequence**: Should be ≥ 128 bits for security
2. **Distinguishability**: Can attacker detect hopping pattern from n observations?
3. **Known-plaintext**: If attacker knows some symbols, can they recover key?

---

## Implementation Requirements

### Statistical Rigor
```python
# Every measurement needs:
def measure_with_confidence(trials, metric_fn, confidence=0.95):
    results = [metric_fn() for _ in range(trials)]
    mean = np.mean(results)
    std = np.std(results, ddof=1)
    ci = scipy.stats.t.interval(confidence, len(results)-1, mean, std/np.sqrt(len(results)))
    return {'mean': mean, 'std': std, 'ci_lower': ci[0], 'ci_upper': ci[1], 'n': trials}
```

### Reproducibility
- Fixed random seeds for each experiment
- All parameters logged
- Code version controlled
- Results include raw data, not just summaries

### Validation Checkpoints
Before running full experiments:
1. ✓ QAM simulation matches theoretical SER curve
2. ✓ Kalman filter matches textbook example
3. ✓ 600-cell has exactly 120 vertices with d_min = 1/φ
4. ✓ Noise generator passes statistical tests

---

## What Success Looks Like

### If POM wins:
- Report SNR gap with 95% CI
- Report conditions where advantage holds
- Report conditions where advantage disappears
- Acknowledge complexity cost (4D vs 2D operations)

### If POM loses:
- Report that too (negative results are valid)
- Analyze why (sphere packing theory suggests it should win - what went wrong?)
- Check for implementation bugs before concluding

### If it's mixed:
- Report crossover points
- Identify use cases for each approach
- This is probably the most likely outcome

---

## Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| 1. Validation | 1 week | Verify simulation against theory for known cases |
| 2. Modulation | 2 weeks | SER curves with CI, statistical tests |
| 3. Tracking | 2 weeks | RMSE by trajectory class, segmented analysis |
| 4. Security | 1 week | Entropy analysis, threat model evaluation |
| 5. Synthesis | 1 week | Integrated report, honest conclusions |

---

## Honest Priors

Before running experiments, state what we expect:

1. **Modulation**: POM should have ~3dB advantage due to better sphere packing (kissing number 12 in 4D vs 6 in 2D). But 4D operations cost more.

2. **Tracking**: Singer should help 10-20% during maneuvers but may hurt during cruise. Overall improvement probably <10%.

3. **Security**: Hopping provides physical-layer security but doesn't replace encryption. Entropy analysis will quantify.

4. **Decoy rejection**: Probably works against random decoys, probably fails against adversarial decoys near vertices.

These priors let us detect if simulation is broken (results wildly different from theory) vs genuinely surprising.

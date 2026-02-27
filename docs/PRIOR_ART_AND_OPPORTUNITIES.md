# Prior Art Search, SBIR Opportunities, Demo & Patent Process

## Part 1: Prior Art Search Results

### Search Summary

**Good news:** No blocking patents found for the core CSPM concept.

| Search Term | Results | Blocking? |
|-------------|---------|-----------|
| "600-cell polytope modulation" | **Nothing found** | ✓ Clear |
| "4D constellation hash rotation" | Related work, not identical | ✓ Clear |
| "Combined comm + positioning signal" | Separate systems only | ✓ Clear |

---

### Related Prior Art (Not Blocking)

#### 1. Non-Uniform Constellation Patents
- [WO2015001121A1](https://patents.google.com/patent/WO2015001121A1) - Non-uniform constellation coding
- [US20160080192A1](https://patents.google.com/patent/US20160080192A1/en) - Non-uniform constellation modulation

**Differentiation:** These use 2D constellations with non-uniform spacing. CSPM uses 4D polytope with cryptographic rotation. Different approach entirely.

#### 2. Physical Layer Security via Constellation Rotation
- [Secure Communication in TDS-OFDM Using Constellation Rotation](https://www.semanticscholar.org/paper/Secure-communication-in-TDS-OFDM-system-using-and-Ma-Dai/2c24ca8567e0aaba340892c30d81b5464c19a46f) - Academic paper
- [Physical layer security using adaptive modulation](https://ietresearch.onlinelibrary.wiley.com/doi/10.1049/iet-com.2019.0031) - IET Communications

**Differentiation:** These rotate 2D constellations by fixed or slowly-varying angles. CSPM uses:
- 4D constellation (not 2D)
- Hash chain determines rotation (not channel-based)
- Rotation per symbol/packet (not fixed angle)

#### 3. 4D Hyperchaos Security
- [High security OFDM-PON with 4D-hyperchaos](https://pubmed.ncbi.nlm.nih.gov/32680168/) - Fiber optic application

**Differentiation:** Uses chaos for encryption, not geometric polytope structure. No positioning capability.

#### 4. Combined Comm + GPS Patents
- [US6,002,363](https://patents.google.com/patent/US6002363A) - Combined GPS and communication system

**Differentiation:** Uses SEPARATE GPS signals and comm signals with shared circuitry. CSPM extracts position FROM the communication signal itself.

---

### Claims We Can Defend

Based on prior art search, these appear novel:

1. **600-cell specifically for modulation** - No prior art found
2. **Hash chain rotation of 4D constellation** - No prior art found
3. **Position estimation from same signal that carries data** - No prior art found (existing patents use separate signals)
4. **Fractal hierarchical polytope** - No prior art found
5. **Hybrid rotated/unrotated levels** - No prior art found

### Recommended Additional Searches

Before filing, have patent attorney search:
- "Polytope modulation" OR "polychoron modulation"
- "Quaternion constellation" OR "quaternion modulation"
- "Physical layer key rotation"
- Inventor names: Agrell, Forney (4D modulation experts)

---

## Part 2: SBIR/STTR Opportunities

### High-Priority Opportunities

#### 1. Navy - Alternative PNT (GPS-Denied)
**Topic:** [Alternative Positioning, Navigation and Timing Technologies](https://www.navysbir.com/n16_1/N161-002.htm)

**Fit:** DIRECT MATCH
- Seeks "affordable, robust, alternative forms of RF based PNT"
- "GPS-degraded and GPS-denied operation"
- CSPM provides PNT from communication signal

**Status:** Check for current open solicitations at [navysbir.com](https://www.navysbir.com)

---

#### 2. Navy - LPD/LPI Communications
**Topic:** [Line-of-Sight Low Probability of Detection/Intercept](https://www.navysbir.com/n19_2/N192-091.htm)

**Fit:** STRONG MATCH
- Seeks "LPD/LPI high bandwidth networks"
- Focus on millimeter wave, but concept applies
- CSPM provides LPI without bandwidth expansion

**Status:** May need to adapt pitch for RF bands specified

---

#### 3. DARPA - LPI PNT Augmentation
**Topic:** [Low Probability of Intercept PNT Augmentation Network](https://legacy.www.sbir.gov/node/870319)

**Fit:** DIRECT MATCH
- "LPI PNT augmentation network"
- "Less than 10 meters horizontal accuracy"
- "GPS-denied environment"
- "Ultra-wideband (UWB) or other LPI techniques"

**Status:** Check if still open or if similar topics upcoming

---

#### 4. SpaceWERX - Alternative PNT
**Recent Award Example:** [Xairos Fusion PNT](https://www.silicon.co.uk/press-release/xairos-is-awarded-direct-to-phase-ii-sbir-contract-by-spacewerx-to-develop-a-fusion-pnt-of-quantum-and-optical-synchronization-of-clock-ensembles)

**Fit:** STRONG MATCH
- SpaceWERX actively funding Alt-PNT
- Direct-to-Phase-II available for mature concepts
- Focus on "secure PNT and communications in GPS-denied environment"

**Action:** Monitor [SpaceWERX](https://spacewerx.us/) for upcoming solicitations

---

#### 5. NASA - PNT for Space Missions
**Topic:** [PNT Sensors and Components](https://sbir.gsfc.nasa.gov/content/pnt-positioning-navigation-and-timing-sensors-and-components)

**Fit:** MODERATE MATCH
- Lunar/Mars operations need GPS-independent PNT
- Deep space communication + navigation
- CSPM could serve cislunar operations

**Status:** NASA moving to rolling submissions in 2026

---

### SBIR Application Strategy

**Phase I:** $50K-250K, 6-12 months
- Build SDR prototype
- Demonstrate BER performance
- Prove LPI concept

**Phase II:** $500K-1.5M, 24 months
- Hardware prototype
- Field testing
- Position estimation validation

**Direct-to-Phase-II:** If you have prior work (you do - simulations)
- Skip Phase I
- Higher funding faster
- Requires feasibility evidence

---

### Key Contacts

| Agency | Portal | Notes |
|--------|--------|-------|
| All DoD | [dodsbirsttr.mil](https://www.dodsbirsttr.mil/) | Unified portal |
| Navy | [navysbir.com](https://www.navysbir.com) | PNT, LPI topics |
| Air Force | [afsbirsttr.af.mil](https://www.afsbirsttr.af.mil) | SATCOM topics |
| SpaceWERX | [spacewerx.us](https://spacewerx.us/) | Space/Alt-PNT |
| DARPA | [darpa.mil/sbir](https://www.darpa.mil/work-with-us/communities/small-business/sbir-sttr-topics) | Advanced concepts |
| NASA | [sbir.nasa.gov](https://sbir.nasa.gov) | Space applications |

---

## Part 3: SDR Demo Build Process

### Minimum Viable Demo

**Goal:** Prove CSPM works in real RF, not just simulation

#### Hardware Required

| Item | Option A (Quality) | Option B (Budget) | Purpose |
|------|-------------------|-------------------|---------|
| TX SDR | USRP B210 ($2,300) | HackRF One ($350) | Transmit signal |
| RX SDR | USRP B210 ($2,300) | RTL-SDR ($35) | Receive signal |
| Antennas | Dual-pol patch ($400) | Basic whip ($20) | Signal path |
| Cables/connectors | ~$100 | ~$50 | RF plumbing |
| Computer | Linux laptop | Linux laptop | Processing |
| **Total** | **~$5,100** | **~$455** |

**Recommendation:** Start with Option B to prove concept, upgrade for real demos.

---

#### Software Stack

```
┌─────────────────────────────────────────────────────┐
│                    GNU Radio                         │
│  (Signal processing framework, already have Python) │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─────────────┐    ┌─────────────┐                │
│  │ TX Chain    │    │ RX Chain    │                │
│  │             │    │             │                │
│  │ • CSPM      │    │ • RF to     │                │
│  │   encoder   │    │   baseband  │                │
│  │ • Hash      │    │ • CSPM      │                │
│  │   rotation  │    │   decoder   │                │
│  │ • Pulse     │    │ • Hash      │                │
│  │   shaping   │    │   sync      │                │
│  │ • RF mod    │    │ • Symbol    │                │
│  │             │    │   timing    │                │
│  └─────────────┘    └─────────────┘                │
│                                                     │
│  Your existing Python code integrates here          │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

#### Demo Milestones

**Week 1-2: Basic TX/RX**
```
[ ] Install GNU Radio + SDR drivers
[ ] Transmit simple QPSK, receive and decode
[ ] Verify RF path works
```

**Week 3-4: CSPM Encoding**
```
[ ] Port 600-cell encoder to GNU Radio block
[ ] Transmit CSPM symbols
[ ] Receive and visualize constellation
```

**Week 5-6: Hash Chain Rotation**
```
[ ] Add rotation to TX
[ ] Add de-rotation to RX
[ ] Verify synchronized decode works
```

**Week 7-8: LPI Demo**
```
[ ] Set up "attacker" receiver (wrong seed)
[ ] Measure attacker BER vs legitimate BER
[ ] Document results
```

**Week 9-10: Position Demo (3 nodes)**
```
[ ] Set up 3 TX nodes
[ ] Synchronize timing
[ ] Measure TDOA at receiver
[ ] Calculate position estimate
```

---

#### Code Integration

Your existing code maps to GNU Radio like this:

| Your Code | GNU Radio Block |
|-----------|-----------------|
| `cspm/lattice.py` | Custom "CSPM Encoder" block |
| `PolychoralConstellation.encode_symbol()` | Encoder internal |
| `PolychoralConstellation.decode_symbol()` | "CSPM Decoder" block |
| Hash chain rotation | Shared state between blocks |
| `spatial_field.py` | Post-processing in Python |

---

## Part 4: Patent Filing Process

### Option A: Self-File Provisional ($320)

**Timeline:** 1-2 days

**Steps:**
1. Go to [USPTO EFS-Web](https://www.uspto.gov/patents/apply)
2. Create account if needed
3. Pay micro-entity fee: $320 (or small entity: $640)
4. Upload your `docs/PATENT_DRAFT.md` as PDF
5. Include all figures/diagrams
6. Submit

**What you get:**
- "Patent Pending" status
- 12-month priority date
- Time to file full application

**Pros:** Cheap, fast, establishes priority
**Cons:** No professional review, may have weak claims

---

### Option B: Attorney-Filed Provisional ($1,500-3,000)

**Timeline:** 1-2 weeks

**Steps:**
1. Find patent attorney (IP specialist, preferably with telecom/signal processing experience)
2. Share technical docs and `PATENT_DRAFT.md`
3. Attorney drafts formal provisional
4. Review and approve
5. Attorney files

**What you get:**
- Professional claim drafting
- Better protection
- Attorney relationship for full application

**Pros:** Stronger protection, expert guidance
**Cons:** Costs more, takes longer

---

### Option C: Full Utility Application ($8,000-15,000)

**Timeline:** 3-6 months to file, 2-3 years to grant

**Steps:**
1. Attorney conducts formal prior art search
2. Drafts full specification with claims
3. Prepares formal drawings
4. Files utility application
5. Responds to USPTO office actions
6. Patent granted (hopefully)

**What you get:**
- Actual enforceable patent
- 20-year protection from filing date
- Licensing potential

**Pros:** Real protection
**Cons:** Expensive, slow

---

### Recommended Path

```
NOW:           File provisional (Option A or B)
               ↓
MONTH 1-6:     Build SDR demo, apply for SBIR
               ↓
MONTH 6-10:    If SBIR funded, use funds for full utility
               ↓
MONTH 11-12:   File full utility before provisional expires
```

---

### Patent Cost Summary

| Action | DIY Cost | With Attorney |
|--------|----------|---------------|
| Provisional filing | $320 | $1,500-3,000 |
| Prior art search | Free (Google Patents) | $500-1,500 |
| Full utility application | N/A (need attorney) | $8,000-15,000 |
| USPTO examination fees | $800 | $800 |
| Issue fee | $500 | $500 |
| **Total to granted patent** | **N/A** | **$12,000-20,000** |

**Note:** SBIR Phase I often includes IP protection funds (~$5,000-10,000 for patents)

---

## Part 5: How the System Actually Works (Technical Detail)

### How the Polytope Constellation Works

#### The 600-Cell Geometry

The 600-cell is a 4-dimensional shape with **120 vertices** arranged on a "3-sphere" (the 4D equivalent of a sphere surface).

```
Why 4D?
───────
3D sphere surface: Every point defined by (x, y, z) where x² + y² + z² = 1
                   This is a 2D surface (S²)

4D "3-sphere":     Every point defined by (w, x, y, z) where w² + x² + y² + z² = 1
                   This is a 3D surface (S³)

The 120 vertices of the 600-cell all lie on this S³.
```

#### Physical Realization

The 4 coordinates map to physical signal properties:

```
Coordinate w, x → Polarization State
─────────────────────────────────────
Light/RF has two polarization modes: Horizontal (H) and Vertical (V)
Any polarization = α|H⟩ + β|V⟩ where |α|² + |β|² = 1

This is naturally a sphere! (Poincaré sphere)
• α and β have magnitude and phase
• Two real degrees of freedom after normalization
• Maps to coordinates (w, x)


Coordinate y, z → OAM Superposition State
──────────────────────────────────────────
Orbital Angular Momentum modes: |ℓ=+1⟩ and |ℓ=-1⟩
Superposition = γ|+1⟩ + δ|-1⟩ where |γ|² + |δ|² = 1

Another sphere! (OAM Bloch sphere)
• Two real degrees of freedom
• Maps to coordinates (y, z)


Combined: (w, x, y, z) lives on S³
          The 600-cell vertices give us 120 distinguishable points
```

#### Encoding Process

```
Input: Symbol 0-119 (6.9 bits)
       │
       ▼
┌──────────────────────────────────────┐
│ Look up 4D coordinates from table    │
│ Symbol 42 → (0.309, 0.809, 0.5, 0.0) │
└──────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│ Apply hash-chain rotation            │
│ rotated = R × (0.309, 0.809, 0.5, 0) │
│         = (0.721, -0.123, 0.654, 0.2)│
└──────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│ Map to physical signal               │
│ w,x → Set polarization               │
│ y,z → Set OAM superposition          │
└──────────────────────────────────────┘
       │
       ▼
Output: Optical/RF signal
```

#### Decoding Process

```
Input: Received signal
       │
       ▼
┌──────────────────────────────────────┐
│ Coherent detection                    │
│ Measure polarization → (w', x')      │
│ Measure OAM state → (y', z')         │
└──────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│ Apply INVERSE rotation               │
│ unrotated = R⁻¹ × (w', x', y', z')   │
└──────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│ Find nearest vertex (quantize)       │
│ 4D distance to each of 120 vertices  │
│ Pick closest one                     │
└──────────────────────────────────────┘
       │
       ▼
Output: Symbol 0-119
```

---

### How Position Estimation Works

#### The Basic Principle

```
            TX₁ ●───────────────── d₁ ──────────────────┐
           (known position p₁)                           │
                                                         │
            TX₂ ●───────────────── d₂ ──────────────────┼──● RX
           (known position p₂)                           │  (unknown position r)
                                                         │
            TX₃ ●───────────────── d₃ ──────────────────┘
           (known position p₃)


If we know:
• Positions p₁, p₂, p₃ of transmitters
• Distances d₁, d₂, d₃ to receiver

Then we can solve for r (receiver position)

This is TRILATERATION (like GPS, but with our own signals)
```

#### How We Get Distance

**From timing:**
```
Distance = Speed_of_Light × Time_of_Flight

If TX₁ sends at t=0 and RX receives at t=τ₁:
d₁ = c × τ₁

Problem: We need to know when TX sent!
```

**Solution 1: Synchronized clocks**
```
All TXs have synchronized clocks (from GPS, atomic clock, or two-way time transfer)
TX stamps transmission time in signal
RX measures arrival time
d = c × (arrival - transmission)
```

**Solution 2: Time Difference of Arrival (TDOA)**
```
We don't need absolute time, just DIFFERENCES

If TX₁ and TX₂ transmit simultaneously:
Δt₁₂ = arrival_from_TX₁ - arrival_from_TX₂
Δd₁₂ = c × Δt₁₂

This defines a hyperbola of possible positions
3 TXs → 2 hyperbolas → intersection = position
```

#### CSPM-Specific Advantages

**1. Symbol timing gives precision**
```
Each CSPM symbol has structure (vertices are discrete)
This gives sharp timing reference
Better than continuous signals
```

**2. Hash chain provides TX identification**
```
Each TX has different seed → different rotation
RX can tell signals apart
No need for separate TX codes
```

**3. Same signal carries data + timing**
```
Traditional: Data channel + separate ranging signal
CSPM: Position comes from data signal itself
No extra bandwidth or hardware
```

#### Position Estimation Algorithm

```python
def estimate_position(tx_positions, arrival_times):
    """
    tx_positions: List of (x, y, z) for each transmitter
    arrival_times: List of reception times for each TX signal

    Returns: estimated (x, y, z) of receiver
    """
    # Speed of light
    c = 299792458  # m/s

    # Convert times to distances (if synchronized)
    distances = [c * t for t in arrival_times]

    # Or use TDOA (if not synchronized)
    # Pick TX₁ as reference
    tdoa = [arrival_times[i] - arrival_times[0] for i in range(len(arrival_times))]

    # Solve trilateration (or hyperbolic positioning)
    # This is a nonlinear least squares problem

    def error(position):
        total = 0
        for i, tx_pos in enumerate(tx_positions):
            predicted_dist = distance(position, tx_pos)
            measured_dist = distances[i]
            total += (predicted_dist - measured_dist)**2
        return total

    # Minimize error to find position
    result = minimize(error, initial_guess)
    return result.x
```

#### Accuracy Factors

| Factor | Impact | Mitigation |
|--------|--------|------------|
| Clock sync error | 1 ns = 30 cm error | Better clocks, TDOA |
| Multipath | Longer path = wrong distance | Signal processing |
| Geometry | Poor TX layout = poor accuracy | Deploy TXs wisely |
| SNR | Noisy timing = noisy position | Averaging, filtering |

**Expected accuracy:**
- Good geometry, good SNR: 1-10 meters
- Poor geometry or low SNR: 10-100 meters
- Needs validation in hardware demo

---

## Summary: What To Do Now

### This Week
1. [ ] File provisional patent (Option A: $320)
2. [ ] Register on [SAM.gov](https://sam.gov) (required for government contracts)
3. [ ] Check [dodsbirsttr.mil](https://www.dodsbirsttr.mil) for open PNT/LPI topics

### This Month
1. [ ] Order budget SDR kit (~$500)
2. [ ] Install GNU Radio, run tutorials
3. [ ] Draft SBIR Phase I proposal for best-fit topic

### Next 3 Months
1. [ ] Complete SDR demo
2. [ ] Submit SBIR application
3. [ ] File full utility patent (if funded)

---

*Document created: January 2026*
*Prior art search conducted via Google Patents, Semantic Scholar, SBIR.gov*

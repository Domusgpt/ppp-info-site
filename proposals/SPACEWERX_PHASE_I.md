# SpaceWERX Phase I Proposal Outline

## Low Probability of Intercept Optical Modulation for Proliferated Warfighter Space Architecture

**Proposing Organization:** Clear Seas Solutions LLC
**Principal Investigator:** Paul Phillips
**Proposed Duration:** 12 months
**Proposed Budget:** $150,000

---

## 1. Technical Abstract (200 words max)

We propose Cryptographically-Seeded Polytopal Modulation (CSPM), a novel optical modulation scheme providing Low Probability of Intercept/Detection (LPI/LPD) for space-based optical inter-satellite links (OISLs). CSPM encodes data onto the 120 vertices of a 600-cell polytope embedded in 4D Hilbert space (polarization + OAM superposition states). A cryptographic hash chain rotates the constellation orientation after each packet, preventing adversarial blind equalization while maintaining synchronization between legitimate terminals.

Key advantages for PWSA:
- **LPI/LPD without bandwidth expansion** - Unlike spread spectrum
- **Geometric error correction** - No LDPC latency overhead
- **Jam-resistant** - Per-packet rotation defeats persistent interference
- **Compatible with existing coherent hardware** - DSP upgrade path

Phase I deliverables: (1) Validated simulation showing LPI effectiveness against CMA/RDE attacks, (2) SDR-based proof-of-concept demonstrator, (3) FPGA decoder architecture specification.

---

## 2. Problem Statement

### 2.1 Current OISL Vulnerabilities

The Space Development Agency's Proliferated Warfighter Space Architecture (PWSA) relies on optical inter-satellite links operating at 2.5-10+ Gbps. Current terminals (Mynaric CONDOR, Tesat SCOTT80, CACI SA Photonics) use standard QAM modulation with no physical-layer security.

**Vulnerabilities:**
- Passive eavesdropping via space-based sensors
- Blind equalization recovery of constellation structure
- Traffic analysis from predictable modulation patterns
- No defense-in-depth below application layer

### 2.2 Why Current Solutions Fail

| Approach | Limitation |
|----------|------------|
| QKD | Too slow for high-rate data; requires specialized hardware |
| Spread Spectrum | Bandwidth expansion unacceptable for multi-Gbps links |
| Application-layer encryption | Doesn't protect against traffic analysis or L1 attacks |

### 2.3 Gap CSPM Fills

CSPM provides **physical-layer obfuscation** without bandwidth expansion, QKD hardware, or latency penalties. The rotating 4D constellation defeats passive interception while maintaining full data rate.

---

## 3. Technical Approach

### 3.1 600-Cell Polytope Constellation

The 600-cell is a regular 4-polytope with 120 vertices uniformly distributed on the 3-sphere (S³). This geometry provides:
- **3.75x larger minimum distance** than equivalent 2D QAM
- **6.9 bits/symbol** (comparable to 128-QAM)
- **Implicit error correction** via Voronoi cell quantization

### 3.2 4D Signal Space Encoding

We create a continuous 4D manifold using coherent superposition states:

**Polarization Bloch Sphere (2D):**
```
|ψ_pol⟩ = α|H⟩ + β|V⟩   (|α|² + |β|² = 1)
```

**OAM Superposition Sphere (2D):**
```
|ψ_OAM⟩ = γ|ℓ₁⟩ + δ|ℓ₂⟩   (|γ|² + |δ|² = 1)
```

Combined via Hopf fibration → 4D manifold homeomorphic to S³.

### 3.3 Hash-Chain Constellation Rotation

After each packet, the constellation rotates:
```
R(n) = SHA-256(R(n-1) || PacketData(n-1)) → SO(4) rotation
```

**Security Properties:**
- Attacker cannot predict next rotation without genesis seed
- CMA/RDE equalizers cannot converge (target moves every packet)
- Per-packet rotation provides ~50% BER for unauthorized receivers

### 3.4 Geometric Quantization

The receiver snaps noisy symbols to nearest 600-cell vertex:
```python
def quantize(received):
    dots = vertex_matrix @ normalize(received)
    return vertices[argmax(dots)]
```

**Complexity:** O(120) - comparable to 128-QAM demodulation.

---

## 4. Phase I Objectives and Deliverables

### Objective 1: Adversarial Security Validation (Months 1-4)

**Tasks:**
- Implement CMA/RDE blind equalization attacks
- Quantify time-to-convergence vs rotation rate
- Analyze known-plaintext attack resistance
- Document attack surface and mitigations

**Deliverable:** Security analysis report with quantitative attack resistance metrics.

### Objective 2: SDR Proof-of-Concept (Months 3-8)

**Tasks:**
- Implement CSPM modulator/demodulator on USRP B210
- Demonstrate LPI: legitimate RX decodes, attacker gets ~50% BER
- Video demonstration for program review
- Measure real-world BER vs simulated

**Deliverable:** Working SDR demo with video documentation.

### Objective 3: FPGA Architecture Specification (Months 6-12)

**Tasks:**
- Design pipelined geometric quantizer for 10 Gbaud operation
- Specify hash-chain state machine
- Define interface to standard coherent DSP
- Estimate gate count and power consumption

**Deliverable:** FPGA architecture document with implementation roadmap.

---

## 5. Performance Metrics

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Legitimate BER @ 15 dB SNR | <1e-4 | Monte Carlo simulation, SDR demo |
| Attacker BER (wrong seed) | >45% | Adversarial simulation |
| CMA convergence time | >1000 packets | Attack simulation |
| Decoding latency | <100 ns/symbol | FPGA timing analysis |
| Power (10 Gbaud) | <5W decoder | FPGA synthesis estimate |

---

## 6. Transition Path

### Phase II (Months 13-24)
- FPGA implementation on Xilinx ZCU106
- Integration with coherent optical transceiver eval kit
- Lab demonstration with actual OAM + polarization encoding
- BER validation on optical bench

### Phase III (Months 25-36)
- Partner with terminal OEM (Mynaric, CACI, Tesat)
- Flight qualification prototype
- Integration with PWSA-compatible terminal
- On-orbit demonstration (hosted payload)

### Commercial Transition
- License CSPM IP to terminal manufacturers
- DSP IP core for coherent optics vendors
- Submarine cable market (LPI for undersea links)

---

## 7. Related Work and Differentiation

| Prior Art | CSPM Advantage |
|-----------|----------------|
| Probabilistic shaping | CSPM uses 4D geometry, not entropy coding |
| Geometric shaping (2D) | CSPM is 4D with LPI rotation |
| FHSS | CSPM doesn't expand bandwidth |
| QKD | CSPM uses classical hardware |

**Key Novelty:** No one combines 600-cell constellation + OAM superposition encoding + cryptographic rotation for LPI.

---

## 8. Team Qualifications

**Paul Phillips, Principal Investigator**
- Founder, Clear Seas Solutions LLC
- Background in signal processing and optical communications
- [Additional qualifications]

**Technical Advisors:**
- [University OAM lab partner - TBD]
- [Coherent optics industry advisor - TBD]

---

## 9. Budget Summary

| Category | Amount |
|----------|--------|
| Labor (PI + contractor) | $100,000 |
| Equipment (USRP B210 x2, optical bench time) | $25,000 |
| Travel (program reviews, partner meetings) | $10,000 |
| Indirect costs | $15,000 |
| **Total** | **$150,000** |

---

## 10. Schedule

```
Month  1  2  3  4  5  6  7  8  9 10 11 12
       ├──┼──┼──┼──┼──┼──┼──┼──┼──┼──┼──┤
Obj 1  ████████████                        Security Analysis
Obj 2        ████████████████              SDR Demo
Obj 3                 ████████████████████ FPGA Spec
Review          ★              ★        ★  Milestones
```

---

## 11. Conclusion

CSPM addresses a critical capability gap in PWSA: physical-layer security for optical inter-satellite links. By encoding signals on a rotating 4D polytope constellation, we provide LPI/LPD without the bandwidth expansion of spread spectrum or the hardware complexity of QKD. Phase I will validate the security claims, demonstrate feasibility on SDR hardware, and specify the path to 10+ Gbaud FPGA implementation.

---

*Prepared for SpaceWERX Rolling Submission*
*Clear Seas Solutions LLC*
*paul@clearseassolutions.com*

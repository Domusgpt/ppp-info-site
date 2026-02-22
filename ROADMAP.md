# CSPM Strategic Development Roadmap

**Clear Seas Solutions LLC**
**Document Version:** 1.0
**Date:** January 2026

---

## Executive Summary

This roadmap synthesizes competitive landscape research, grant opportunities, and technical gaps to define CSPM's development priorities. The goal: transition from simulation to hardware demonstration within 18-24 months while securing government/commercial funding.

---

## 1. Competitive Landscape Analysis

### 1.1 Who's Doing What

| Company | Focus | Relevance to CSPM |
|---------|-------|-------------------|
| **Mynaric** | Space laser terminals (CONDOR Mk3) | Hardware partner candidate; SDA supplier |
| **Tesat-Spacecom** | SCOTT80 optical terminals | Interoperability target |
| **CACI (SA Photonics)** | Optical terminals + PNT | Potential integration partner |
| **Skyloom/Honeywell** | GEO/LEO optical links | Commercial market |
| **Space Micro** | Air-to-space laser pods | AFWERX-funded competitor |

**Key Insight:** No one is doing **4D polytopal constellation shaping with LPI rotation**. The market is focused on higher baudrate, not novel modulation geometry.

### 1.2 Academic Research Landscape

| Research Area | Key Players | CSPM Relevance |
|---------------|-------------|----------------|
| [Geometric Constellation Shaping](https://advanced.onlinelibrary.wiley.com/doi/10.1002/adpr.202400123) | Wiley, various universities | Direct competitor approach; 2D/4D hybrid |
| [OAM Multiplexing](https://www.nature.com/articles/s42005-024-01571-3) | Huazhong U, Nature Comms | Validates OAM for fiber; 15 Tbit/s demo |
| [Sphere Packing Constellations](https://www.sciencedirect.com/science/article/abs/pii/S0030401816303431) | ScienceDirect | Theoretical basis for lattice codes |
| [Physical Layer Security](https://prucnal.princeton.edu/research/physical-layer-security) | Princeton (Prucnal Lab) | MZI-based key generation; different approach |
| [Leech Lattice VLC](https://www.researchgate.net/publication/376083368_Energy-Efficient_Multidimensional_Constellation_Based_on_Leech_Lattice_for_Visible_Light_Communications) | ResearchGate | 24D lattice; 3dB coding gain |

**Gap CSPM Fills:** No one combines **600-cell (4D) + OAM superposition encoding + LPI rotation**. The hybrid is novel.

### 1.3 What the Market Wants

From [SDA requirements](https://www.sda.mil/military-agency-praised-for-leading-the-way-on-laser-communications/) and industry reports:

| Requirement | Current Solution | CSPM Advantage |
|-------------|------------------|----------------|
| 2.5-10 Gbps links | QAM + LDPC | Geometric FEC may reduce latency |
| Interoperability | Standard modulation | Challenge: proprietary constellation |
| LPI/LPD | None at physical layer | **Key differentiator** |
| SWaP-C reduction | Smaller terminals | Simpler decoder (no LDPC ASIC) |
| Jamming resistance | Spread spectrum | Hash rotation adds layer |

---

## 2. Grant Opportunities

### 2.1 Active/Upcoming Solicitations

| Program | Agency | Focus | Deadline | Fit |
|---------|--------|-------|----------|-----|
| [Space-BACN Phase 3](https://executivebiz.com/2024/01/darpa-taps-mynaric-for-phase-2-space-based-adaptive-communications-node-program/) | DARPA | Reconfigurable optical terminals | TBD | Medium - need hardware partner |
| [SDA STEC](https://www.militaryaerospace.com/communications/article/14305516/optical-communications-space-target-tracking) | SDA | Enabling technologies | Ongoing | High - LPI fits "emerging capabilities" |
| [SpaceWERX Rolling](https://spacewerx.us/space-ventures/stratfi-tacfi/) | USSF | Space technologies | Rolling | High - new submission model |
| [AFWERX TACFI](https://afwerx.com/divisions/ventures/stratfi-tacfi/) | USAF | Phase II bridge | Annual | Requires Phase II first |
| [NASA SBIR Phase I](https://www.nasa.gov/sbir_sttr/) | NASA | Various optical | 2025 (paused) | Medium - wait for reauthorization |

### 2.2 Recommended Pursuit Strategy

**Tier 1 (Immediate - Q1 2026):**
1. **SpaceWERX Rolling Submission** - LPI optical modulation for PWSA
   - No Phase II prerequisite
   - Rolling review means fast feedback
   - Align with SDA's OISL requirements

2. **SDA STEC White Paper** - 600-cell constellation for jam-resistant links
   - "Emerging capabilities" explicitly called out
   - Free-space optical + security = perfect fit

**Tier 2 (After Demo - Q3 2026):**
3. **DARPA Space-BACN Integration** - Once hardware exists
4. **AFWERX STRATFI** - If SpaceWERX Phase I succeeds

### 2.3 Commercial Pathways

| Partner Type | Target | Value Proposition |
|--------------|--------|-------------------|
| Terminal OEMs | Mynaric, CACI | License CSPM modulator IP |
| Coherent Optics | Coherent Corp, Lumentum | DSP IP for 400G/800G |
| Defense Primes | Lockheed, Northrop | System integration |
| Fiber Vendors | Ciena, Infinera | Submarine/DCI markets |

---

## 3. Research Priorities

### 3.1 Critical Open Questions

| Question | Why It Matters | Proposed Work |
|----------|----------------|---------------|
| **Blind equalization attack resilience** | Security claim validity | Simulate attacker with CMA/RDE equalizer |
| **OAM crosstalk in real fiber** | Practical feasibility | Partner with OAM fiber lab (Corning?) |
| **Hash rotation synchronization** | Packet loss recovery | Design sync preamble protocol |
| **Doppler tolerance** | LEO-LEO links | Simulate ±50 kHz offset |
| **Hybrid CSPM + LDPC** | Best of both worlds | Compare concatenated vs pure geometric |

### 3.2 Suggested Research Track

**Phase 1: Simulation Hardening (Q1-Q2 2026)**
```
├── Adversarial security analysis
│   ├── Blind equalization attack simulation
│   ├── Known-plaintext attack resistance
│   └── Side-channel analysis (timing)
├── Channel robustness
│   ├── Real OAM crosstalk models (from literature)
│   ├── Doppler shift tolerance
│   └── Turbulence (Cn² range)
└── Protocol design
    ├── Sync preamble for packet loss
    ├── Key exchange for genesis seed
    └── Backward compatibility mode (fall back to QAM)
```

**Phase 2: Algorithm Optimization (Q2-Q3 2026)**
```
├── Decoder acceleration
│   ├── Approximate nearest-neighbor (LSH, k-d tree)
│   ├── FPGA-friendly fixed-point arithmetic
│   └── Lookup table optimization
├── Constellation variants
│   ├── 24-cell (simpler, 24 symbols)
│   ├── 120-cell (600 symbols, higher rate)
│   └── Hybrid: QAM per OAM mode + rotation
└── FEC concatenation
    ├── CSPM inner + RS outer
    └── CSPM inner + polar outer
```

**Phase 3: Hardware Path (Q3-Q4 2026)**
```
├── FPGA proof-of-concept
│   ├── Geometric quantizer in Verilog
│   ├── Hash-chain state machine
│   └── Interface to standard coherent DSP
├── Optical testbed integration
│   ├── Partner: university OAM lab
│   ├── SLM-based OAM generation
│   └── Coherent receiver with polarimeter
└── Lab demonstration
    ├── BER measurement on optical table
    ├── LPI test (wrong seed = random)
    └── Comparison to commercial QAM modem
```

---

## 4. Demonstration Priorities

### 4.1 Demo Tiers

| Demo | Complexity | Timeline | Purpose |
|------|------------|----------|---------|
| **Software BER Curves** | Low | Now | Grant proposals, white papers |
| **FPGA Decoder** | Medium | 6 months | Prove real-time feasibility |
| **OAM Optical Bench** | High | 12 months | Hardware validation |
| **Field Trial** | Very High | 18-24 months | TRL 6 milestone |

### 4.2 Minimum Viable Demo (for SpaceWERX)

**Goal:** Show LPI effectiveness without full optical hardware

**Setup:**
```
┌─────────────────────────────────────────────────────────────┐
│  Software-Defined Radio (SDR) Demonstration                 │
│                                                              │
│  ┌──────────┐   RF/IQ   ┌──────────┐   RF/IQ   ┌──────────┐│
│  │  TX SDR  │ ───────▶  │  Channel │ ───────▶  │  RX SDR  ││
│  │ (CSPM)   │           │  (AWGN)  │           │  (CSPM)  ││
│  └──────────┘           └──────────┘           └──────────┘│
│                              │                              │
│                         ┌────▼────┐                        │
│                         │ Attacker│                        │
│                         │  (QAM)  │                        │
│                         └─────────┘                        │
│                                                              │
│  Metric: Legitimate RX decodes; Attacker gets ~50% BER     │
└─────────────────────────────────────────────────────────────┘
```

**Hardware:** 2x USRP B210 ($2k each) + laptop
**Timeline:** 3 months
**Outcome:** Video demo for proposal

### 4.3 Full Optical Demo (for DARPA/SDA)

**Goal:** BER measurement on actual OAM + polarization optical link

**Required Equipment:**
- Spatial Light Modulator (SLM) for OAM generation
- Polarization controller
- Coherent receiver with polarization diversity
- Stokes analyzer
- Fiber or free-space optical bench

**Partner Options:**
- University lab (Huazhong, USC, Arizona)
- National lab (NRL, NIST)
- Commercial partner (Lumentum, Coherent)

---

## 5. Competitive Differentiation

### 5.1 CSPM vs. Existing Approaches

| Approach | Strengths | Weaknesses | CSPM Advantage |
|----------|-----------|------------|----------------|
| **Probabilistic Shaping** | Near-capacity | Complex encoder | Simpler (geometric) |
| **Geometric Shaping (2D)** | 0.5-1.5 dB gain | Still 2D | 4D geometry |
| **LDPC/Polar Codes** | Proven, standard | Latency, overhead | No parity bits |
| **QKD** | Information-theoretic security | Expensive, low rate | Classical hardware |
| **Spread Spectrum** | Jam resistance | Bandwidth expansion | No expansion |

### 5.2 Unique Value Propositions

1. **For DoD:** LPI/LPD without bandwidth expansion or QKD hardware
2. **For Commercial:** Potential latency reduction (no iterative decoder)
3. **For Research:** Novel 4D+OAM+crypto intersection

### 5.3 Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| OAM doesn't work in real fiber | Medium | High | Partner early with OAM lab; pivot to free-space |
| Blind equalization defeats LPI | Medium | High | Research countermeasures; per-symbol rotation |
| No customer interest | Low | High | SpaceWERX feedback loop; pivot if needed |
| Patent prior art | Medium | Medium | Prior art search before filing |

---

## 6. 18-Month Development Timeline

```
2026 Q1        Q2          Q3          Q4          2027 Q1
│───────────────│───────────────│───────────────│───────────────│
│                                                                │
│ ▓▓▓▓▓ SpaceWERX Proposal + Security Research                  │
│       ▓▓▓▓▓▓▓▓ SDR Demo Build + Test                          │
│               ▓▓▓▓▓▓▓▓ FPGA Decoder Development               │
│                       ▓▓▓▓▓▓▓▓ University OAM Lab Partnership │
│                               ▓▓▓▓▓▓▓▓ Optical Bench Demo     │
│                                       ▓▓▓▓▓▓▓▓ DARPA Proposal │
│                                                                │
│ Milestones:                                                    │
│ ★ Q1: SpaceWERX submission                                    │
│ ★ Q2: SDR demo video                                          │
│ ★ Q3: FPGA decoder working                                    │
│ ★ Q4: Optical BER measured                                    │
│ ★ 2027 Q1: TRL 4 complete                                     │
└────────────────────────────────────────────────────────────────┘
```

---

## 7. Immediate Next Steps

### This Week
1. [ ] Submit SpaceWERX intent notification
2. [ ] Contact USC/Arizona OAM labs for partnership
3. [ ] Begin blind equalization attack simulation
4. [ ] Acquire USRP SDR hardware for RF demo

### This Month
1. [ ] Complete adversarial security analysis
2. [ ] Write SpaceWERX Phase I proposal (10 pages)
3. [ ] Design SDR demo architecture
4. [ ] Patent prior art search

### This Quarter
1. [ ] SpaceWERX submission
2. [ ] SDR demo operational
3. [ ] University partnership MOU signed
4. [ ] SDA STEC white paper submitted

---

## 8. Key Contacts and Resources

### Grant Programs
- [SpaceWERX](https://spacewerx.us/) - Rolling submissions
- [AFWERX](https://afwerx.com/) - STRATFI/TACFI
- [DARPA SBIR Topics](https://www.darpa.mil/work-with-us/communities/small-business/sbir-sttr-topics)
- [SDA Opportunities](https://www.sda.mil/)

### Research Groups
- [Princeton Physical Layer Security Lab](https://prucnal.princeton.edu/research/physical-layer-security)
- Huazhong University (Jian Wang) - OAM switching
- USC - OAM multiplexing

### Industry Partners
- Mynaric (optical terminals, recently acquired by Rocket Lab)
- Coherent Corp (coherent DSP)
- codes.se - [Sphere packing database](https://codes.se/packings/)

---

## 9. Success Criteria

| Timeframe | Metric | Target |
|-----------|--------|--------|
| 6 months | SpaceWERX Phase I | Awarded |
| 6 months | SDR demo | Operational |
| 12 months | FPGA decoder | <10 μs/symbol |
| 12 months | University partnership | MOU signed |
| 18 months | Optical BER | Matches simulation |
| 24 months | Phase II funding | >$750k secured |

---

## Sources

- [DARPA Space-BACN Program](https://executivebiz.com/2024/01/darpa-taps-mynaric-for-phase-2-space-based-adaptive-communications-node-program/)
- [SDA Optical Communications Requirements](https://www.militaryaerospace.com/communications/article/14305516/optical-communications-space-target-tracking)
- [AFWERX STRATFI/TACFI](https://afwerx.com/divisions/ventures/stratfi-tacfi/)
- [OAM Multiplexing Research (Nature)](https://www.nature.com/articles/s42005-024-01571-3)
- [Geometric Constellation Shaping (Wiley)](https://advanced.onlinelibrary.wiley.com/doi/10.1002/adpr.202400123)
- [Physical Layer Security (Princeton)](https://prucnal.princeton.edu/research/physical-layer-security)
- [Sphere Packing for Modulation](https://codes.se/packings/)
- [Mynaric Industry Position](https://mynaric.com/)
- [SDA Laser Communications Market](https://www.sda.mil/military-agency-praised-for-leading-the-way-on-laser-communications/)
- [NASA DSOC](https://www.nasa.gov/mission/deep-space-optical-communications-dsoc/)

---

*Document prepared for Clear Seas Solutions LLC internal planning.*

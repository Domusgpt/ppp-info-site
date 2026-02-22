# CSPM SDR Proof-of-Concept Demo Architecture

## Overview

This document specifies the Software-Defined Radio (SDR) demonstration of CSPM's LPI/LPD capabilities. The demo proves the core security claim: a legitimate receiver with the correct genesis seed can decode, while an eavesdropper achieves only random-guessing BER (~50%).

---

## 1. System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CSPM SDR DEMONSTRATION                          │
│                                                                         │
│  ┌─────────────┐        ┌─────────────┐        ┌─────────────────────┐ │
│  │  TRANSMITTER│        │   CHANNEL   │        │      RECEIVER       │ │
│  │             │        │             │        │                     │ │
│  │ ┌─────────┐ │  RF    │  ┌───────┐  │  RF    │ ┌─────────────────┐ │ │
│  │ │  Data   │ │───────▶│  │ AWGN  │  │───────▶│ │  LEGITIMATE RX  │ │ │
│  │ │  Source │ │        │  │ + Fade│  │        │ │  (Correct Seed) │ │ │
│  │ └────┬────┘ │        │  └───┬───┘  │        │ └────────┬────────┘ │ │
│  │      │      │        │      │      │        │          │          │ │
│  │ ┌────▼────┐ │        │      │      │        │    BER < 1e-3      │ │
│  │ │  CSPM   │ │        │      │      │        │          │          │ │
│  │ │ Encoder │ │        │      ▼      │        │ ┌────────▼────────┐ │ │
│  │ └────┬────┘ │        │   ┌─────┐   │        │ │   ATTACKER RX   │ │ │
│  │      │      │        │   │ TAP │   │        │ │  (Wrong Seed)   │ │ │
│  │ ┌────▼────┐ │        │   └──┬──┘   │        │ └────────┬────────┘ │ │
│  │ │  USRP   │ │        │      │      │        │          │          │ │
│  │ │  B210   │ │        │      ▼      │        │    BER ≈ 50%       │ │
│  │ └─────────┘ │        │  Attacker   │        │                     │ │
│  └─────────────┘        └─────────────┘        └─────────────────────┘ │
│                                                                         │
│  Metric: Legitimate RX decodes correctly; Attacker gets random output  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Hardware Bill of Materials

| Component | Model | Quantity | Unit Cost | Total |
|-----------|-------|----------|-----------|-------|
| SDR Transceiver | Ettus USRP B210 | 2 | $1,500 | $3,000 |
| Antennas | VERT2450 (dual-band) | 4 | $40 | $160 |
| RF Cables | SMA-SMA 1m | 4 | $15 | $60 |
| Attenuators | 30dB fixed | 2 | $25 | $50 |
| Laptop | Linux (Ubuntu 22.04) | 1 | Existing | $0 |
| **Total** | | | | **$3,270** |

### Alternative: Loopback Configuration
For initial development, use a single USRP B210 in loopback mode with RF attenuator:
- TX port → 30dB attenuator → RX port
- Cost: $1,560 (1 USRP + cables + attenuator)

---

## 3. Software Stack

```
┌─────────────────────────────────────────────────┐
│                 APPLICATION LAYER               │
│  ┌───────────────┐  ┌───────────────────────┐  │
│  │  CSPM Python  │  │  Demo Control GUI     │  │
│  │  (existing)   │  │  (PyQt5/Tkinter)      │  │
│  └───────┬───────┘  └───────────┬───────────┘  │
│          │                      │               │
├──────────┼──────────────────────┼───────────────┤
│          ▼         GNU RADIO    ▼               │
│  ┌───────────────────────────────────────────┐ │
│  │  ┌─────────┐  ┌─────────┐  ┌───────────┐  │ │
│  │  │  CSPM   │  │ Channel │  │   CSPM    │  │ │
│  │  │ Mod GR  │─▶│ Model   │─▶│ Demod GR  │  │ │
│  │  │  Block  │  │  Block  │  │   Block   │  │ │
│  │  └─────────┘  └─────────┘  └───────────┘  │ │
│  └───────────────────────────────────────────┘ │
│                                                 │
├─────────────────────────────────────────────────┤
│              UHD DRIVER LAYER                   │
│  ┌───────────────────────────────────────────┐ │
│  │  libuhd (Ettus UHD 4.x)                   │ │
│  └───────────────────────────────────────────┘ │
│                      │                          │
├──────────────────────┼──────────────────────────┤
│                      ▼                          │
│              USRP B210 HARDWARE                 │
└─────────────────────────────────────────────────┘
```

### Dependencies
```bash
# Ubuntu 22.04
sudo apt install gnuradio uhd-host libuhd-dev python3-numpy python3-scipy

# Python packages
pip install pyqt5 matplotlib
```

---

## 4. GNU Radio Flowgraph

### 4.1 Transmitter Flowgraph

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│  File    │──▶│   CSPM   │──▶│  Pulse   │──▶│   RRC    │──▶│   USRP   │
│  Source  │   │  Mapper  │   │  Shaper  │   │  Filter  │   │   Sink   │
└──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘
     │              │
     │         ┌────┴────┐
     │         │  Hash   │
     └────────▶│  Chain  │
               │ Rotator │
               └─────────┘
```

### 4.2 Receiver Flowgraph (Legitimate)

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│   USRP   │──▶│   RRC    │──▶│  Symbol  │──▶│   CSPM   │──▶│   File   │
│  Source  │   │  Filter  │   │   Sync   │   │ Quantize │   │   Sink   │
└──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘
                                                  │
                                             ┌────┴────┐
                                             │  Hash   │
                                             │  Chain  │ (Synchronized)
                                             └─────────┘
```

### 4.3 Attacker Flowgraph

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│   USRP   │──▶│   RRC    │──▶│  Symbol  │──▶│   CSPM   │──▶│   BER    │
│  Source  │   │  Filter  │   │   Sync   │   │ Quantize │   │  Counter │
└──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘
                                                  │
                                             ┌────┴────┐
                                             │  WRONG  │
                                             │  SEED   │ ← Key difference
                                             └─────────┘
```

---

## 5. Custom GNU Radio Blocks

### 5.1 CSPM Mapper Block (gr-cspm)

```cpp
// cspm_mapper_impl.cc
class cspm_mapper_impl : public cspm_mapper {
private:
    Cell600 d_cell;
    PolychoralConstellation d_constellation;
    std::vector<uint8_t> d_genesis_seed;

public:
    cspm_mapper_impl(const std::vector<uint8_t>& seed)
        : d_genesis_seed(seed),
          d_constellation(seed.data(), seed.size()) {}

    int work(int noutput_items,
             gr_vector_const_void_star &input_items,
             gr_vector_void_star &output_items) {
        const uint8_t *in = (const uint8_t*)input_items[0];
        gr_complex *out = (gr_complex*)output_items[0];

        for (int i = 0; i < noutput_items; i++) {
            // Map 7 bits to symbol (0-119, with wrap)
            int symbol = in[i] % 120;

            // Get rotated 4D coordinates
            auto coords = d_constellation.encode_symbol(symbol);

            // Project 4D to 2D complex (for SDR transmission)
            // Using first two coordinates as I/Q
            out[i] = gr_complex(coords[0], coords[1]);
            // Note: Full 4D would require dual-polarization hardware
        }

        // Advance rotation after packet
        d_constellation.advance_rotation();

        return noutput_items;
    }
};
```

### 5.2 CSPM Quantizer Block

```cpp
// cspm_quantizer_impl.cc
int work(...) {
    const gr_complex *in = (const gr_complex*)input_items[0];
    uint8_t *out = (uint8_t*)output_items[0];

    for (int i = 0; i < noutput_items; i++) {
        // Reconstruct 4D from 2D (simplified for demo)
        std::array<float, 4> received = {
            in[i].real(), in[i].imag(), 0.0f, 0.0f
        };

        // Geometric quantization
        int symbol = d_constellation.decode_symbol(received);
        out[i] = symbol;
    }

    d_constellation.advance_rotation();
    return noutput_items;
}
```

---

## 6. Demo Scenarios

### Scenario 1: Basic LPI Demonstration

**Setup:**
1. TX sends known data file (e.g., text, image)
2. Legitimate RX (correct seed) decodes perfectly
3. Attacker RX (wrong seed) outputs garbage

**Measurement:**
- Legitimate BER: <1e-3
- Attacker BER: 48-52% (random)

### Scenario 2: Live Video Stream

**Setup:**
1. TX streams webcam video via CSPM
2. Legitimate RX displays video correctly
3. Attacker RX shows noise/random frames

**Visual Impact:** Side-by-side video comparison is compelling for demos.

### Scenario 3: Rotation Rate Impact

**Setup:**
1. Vary rotation rate: per-packet, per-10-packets, never
2. Measure attacker CMA convergence time

**Expected Results:**
| Rotation Rate | Attacker Convergence | LPI Effective? |
|---------------|---------------------|----------------|
| Per-packet | Never | Yes |
| Per-10-packets | ~100 packets | Partial |
| Never | ~50 packets | No |

---

## 7. Demo GUI Design

```
┌──────────────────────────────────────────────────────────────────────┐
│  CSPM LPI/LPD DEMONSTRATION                              [─][□][×]  │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────────────────────┐  ┌─────────────────────────────┐   │
│  │      TRANSMITTER            │  │       RECEIVER              │   │
│  │  ┌───────────────────────┐  │  │  ┌───────────────────────┐  │   │
│  │  │  Genesis Seed:        │  │  │  │  Seed: [CORRECT]  ▼  │  │   │
│  │  │  [████████████████]   │  │  │  │                       │  │   │
│  │  └───────────────────────┘  │  │  └───────────────────────┘  │   │
│  │                              │  │                             │   │
│  │  Data: [test_file.txt  ] ▼  │  │  Status: ● RECEIVING        │   │
│  │                              │  │                             │   │
│  │  [▶ START TX]  [■ STOP]     │  │  BER: 0.00012               │   │
│  │                              │  │  Packets: 1,234             │   │
│  │  TX Power: [-10 dB] ════    │  │                             │   │
│  └─────────────────────────────┘  └─────────────────────────────┘   │
│                                                                       │
│  ┌─────────────────────────────┐  ┌─────────────────────────────┐   │
│  │      ATTACKER VIEW          │  │     CONSTELLATION           │   │
│  │  ┌───────────────────────┐  │  │  ┌───────────────────────┐  │   │
│  │  │  Seed: [WRONG_SEED]   │  │  │  │    ·  · ·  ·         │  │   │
│  │  └───────────────────────┘  │  │  │   ·    ·    ·        │  │   │
│  │                              │  │  │  ·   (○)    ·       │  │   │
│  │  Status: ● DECODING          │  │  │   ·    ·    ·        │  │   │
│  │                              │  │  │    ·  · ·  ·         │  │   │
│  │  BER: 0.4987 (≈RANDOM)       │  │  │                       │  │   │
│  │  Packets: 1,234             │  │  │  [2D Projection]       │  │   │
│  └─────────────────────────────┘  └─────────────────────────────┘   │
│                                                                       │
│  ═══════════════════════════════════════════════════════════════════ │
│  [RECORD VIDEO]  [EXPORT METRICS]  [RESET]           v1.0.0          │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 8. Implementation Timeline

| Week | Task | Deliverable |
|------|------|-------------|
| 1-2 | Set up USRP, install GNU Radio | Working RF loopback |
| 3-4 | Implement CSPM mapper GR block | TX flowgraph |
| 5-6 | Implement CSPM quantizer GR block | RX flowgraph |
| 7-8 | Integrate with Python CSPM library | End-to-end link |
| 9-10 | Build demo GUI | Interactive demo |
| 11-12 | Record demo video, document | Deliverable package |

---

## 9. Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Legitimate BER @ 15 dB SNR | <1e-3 | BER counter in flowgraph |
| Attacker BER | >45% | Parallel BER counter |
| Data rate | >100 kbps | Throughput measurement |
| Demo runtime | >10 minutes stable | Duration test |
| Video quality | 720p clear | Visual inspection |

---

## 10. Future Extensions

### 10.1 Dual-Polarization SDR
For full 4D demonstration, use:
- Ettus USRP N310 (2x2 MIMO)
- Dual-polarized antennas
- Map 4D CSPM coordinates to H/V polarization + I/Q

### 10.2 OAM Mode Extension
Requires specialized hardware:
- Spiral phase plate for OAM generation
- OAM mode sorter for detection
- Partnership with university OAM lab

### 10.3 FPGA Acceleration
For real-time 10 Gbaud operation:
- Port geometric quantizer to Verilog
- Target: Xilinx ZCU106 (RFSoC)
- Integrate with coherent optical DSP

---

## 11. Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| USRP sync issues | Medium | High | Use GPSDO reference |
| Symbol timing recovery | Medium | Medium | Use Mueller-Muller timing |
| Hash chain desync | Low | High | Add sync preamble |
| Demo instability | Medium | Medium | Extensive burn-in testing |

---

*SDR Demo Architecture v1.0*
*Clear Seas Solutions LLC*

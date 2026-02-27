# Spatial Array Architecture for CSPM

## Concept: Ambisonic-Inspired Distributed Modulation

### The Problem with Point-to-Point

Traditional optical/RF links are **scalar channels**:
- One transmitter, one receiver
- No spatial information
- Jamming is trivial (point at the link)

### The Opportunity: Spatial Field Encoding

What if we treat the 600-cell constellation as a **spatial field** rather than a single channel?

```
                    ┌─────────────────────────────────────┐
                    │     CSPM SPATIAL FIELD              │
                    │                                      │
    TX Array        │    ∴  ∴  ∴  ∴  ∴  ∴  ∴            │     RX Array
    ┌──┐           │   ∴  ∴  ∴  ∴  ∴  ∴  ∴  ∴          │          ┌──┐
    │T₁│○──────────│▶ ∴ 4D GEOMETRIC ∴  ∴  ∴ ◀│──────────○│R₁│
    └──┘           │   ∴  ENCODING  ∴  ∴  ∴  ∴          │          └──┘
    ┌──┐           │    ∴  ∴  ∴  ∴  ∴  ∴  ∴            │          ┌──┐
    │T₂│○──────────│▶ ∴  ∴  ∴  ∴  ∴  ∴  ∴  ∴ ◀│──────────○│R₂│
    └──┘           │   ∴  ∴  ∴  ∴  ∴  ∴  ∴  ∴          │          └──┘
    ┌──┐           │    ∴  ∴  ∴  ∴  ∴  ∴  ∴            │          ┌──┐
    │T₃│○──────────│▶ ∴  ∴  ∴  ∴  ∴  ∴  ∴  ◀│──────────○│R₃│
    └──┘           │                                      │          └──┘
                    └─────────────────────────────────────┘

    Each TX contributes to the field
    Each RX samples from different spatial position
    Combined → Data + Orientation + Position
```

---

## Ambisonic Analogy

### In Audio (Ambisonics)

Ambisonics encodes a **full-sphere sound field** using spherical harmonics:
- 0th order: Omnidirectional (W channel)
- 1st order: X, Y, Z (figure-8 patterns)
- Higher orders: Finer spatial resolution

The sound field is **position-independent** until decoded for a specific listener location.

### In CSPM (Proposed)

The 600-cell encodes a **4D orientation field** using S³ geometry:
- The constellation is inherently spherical (lives on S³)
- Multiple transmitters create interfering "geometric waves"
- Receivers at different positions sample different projections
- Combined → recover the full 4D state

```
AMBISONICS                          CSPM SPATIAL FIELD
─────────────────────────────────────────────────────────────
Sound Field on S²                   Constellation on S³
Spherical Harmonics Yₗₘ             600-cell vertices
Encode: microphone array            Encode: TX array positions
Decode: speaker array               Decode: RX array geometry
Position-agnostic until playback    Position-agnostic until decode
```

---

## Mathematical Framework

### Multi-Static Observation Model

Let N transmitters at positions **p₁, p₂, ..., pₙ** each transmit symbol sᵢ from the 600-cell.

A receiver at position **r** observes a superposition:

```
y(r) = Σᵢ Aᵢ(r) · Rᵢ · v(sᵢ) + n(r)

where:
  Aᵢ(r)  = attenuation from TXᵢ to r (path loss)
  Rᵢ     = rotation matrix for TXᵢ's hash chain state
  v(sᵢ)  = 4D vertex for symbol sᵢ
  n(r)   = noise at receiver
```

### Stereoscopic Recovery

With M receivers at positions **r₁, r₂, ..., rₘ**, we get M observations:

```
Y = [y(r₁), y(r₂), ..., y(rₘ)]ᵀ

This is an M × 4 matrix of observations.
```

**Key insight**: If M ≥ 4 and receivers are non-coplanar, we can solve for:
1. The transmitted symbols {s₁, s₂, ..., sₙ}
2. The relative geometry of the TX array
3. Our own position (if TX positions are known)

This is **stereoscopic localization + decoding** in one operation.

---

## Modular Signal Architecture

### Composable Hash Chain Blocks

```
┌─────────────────────────────────────────────────────────────┐
│                    MODULAR CSPM NODE                         │
│                                                              │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐ │
│  │  HASH    │──▶│ ROTATION │──▶│  600-CELL│──▶│ SPATIAL  │ │
│  │  CHAIN   │   │ GENERATOR│   │  MAPPER  │   │ COMBINER │ │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘ │
│       │              │              │              │        │
│       ▼              ▼              ▼              ▼        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              GAA AUDIT LAYER                          │  │
│  │  Every operation → TRACE event → Merkle tree         │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  Inputs:                      Outputs:                      │
│  • Data symbols               • 4D spatial field            │
│  • Position (GPS/IMU)         • Audit trail                 │
│  • Neighbor states            • Sync beacon                 │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Network Topology Options

```
MESH (Resilient)                    STAR (Coordinated)
    ○───○───○                           ○   ○   ○
    │ × │ × │                            \ │ /
    ○───○───○                             ○ ← Hub
    │ × │ × │                            / │ \
    ○───○───○                           ○   ○   ○

HIERARCHICAL (Scalable)             SWARM (Mobile)
        ○                               ○→  ○→
       /│\                             ↗    ↘
      ○ ○ ○                          ○→  ○→  ○→
     /│\│/│\                           ↘    ↗
    ○○○○○○○○○                           ○→  ○→
```

---

## Use Cases

### 1. Distributed Aperture Sensing

Multiple small sensors create a **synthetic large aperture**:
- Each sensor transmits its observation encoded via CSPM
- Central processor combines spatially
- Resolution = virtual array size, not individual sensor

### 2. Position-Velocity-Attitude via Link

Multi-static CSPM links provide:
- **Position**: Triangulation from multiple TXs
- **Velocity**: Doppler on each link
- **Attitude**: Quaternion state from 4D constellation

All in one modulated signal, no separate PNT system needed.

### 3. Jam-Resistant Coordination

A swarm of drones using CSPM spatial field:
- No single point of failure
- Hash chain sync maintains coherence
- Attacker must jam ALL nodes simultaneously
- Geometric quantization corrects partial jamming

### 4. Covert Mesh Networking

LPI properties extend to the mesh:
- Each link individually has LPI
- Network topology hidden (no predictable routing)
- Traffic analysis defeated by hash chain rotations

---

## Implementation Considerations

### What Exists (Reusable)

| Component | Status | Notes |
|-----------|--------|-------|
| 600-cell geometry | ✅ Working | 120 symbols, geometric quantization |
| Hash chain rotation | ✅ Working | Per-packet LPI |
| GAA audit trail | ✅ Working | Merkle proofs, TRACE events |
| Quaternion math | ✅ Working | SLERP, decomposition |

### What's Needed (New Development)

| Component | Priority | Effort |
|-----------|----------|--------|
| Multi-TX superposition model | High | 2 weeks |
| Spatial combiner (RX side) | High | 2 weeks |
| Sync protocol for distributed hash chains | High | 3 weeks |
| Position recovery algorithm | Medium | 2 weeks |
| Swarm coordination layer | Medium | 4 weeks |

### Hardware Mapping

| Concept | Potential Hardware |
|---------|-------------------|
| TX node | USRP B210 + GPS/IMU |
| RX node | USRP B210 + antenna array |
| Spatial combiner | FPGA (parallel correlation) |
| Hash chain sync | PTP/GPS timing |

---

## Relation to Existing Technology

### What This Is Similar To

| Technology | Similarity | Difference |
|------------|------------|------------|
| **MIMO Radar** | Multi-static, spatial | CSPM adds LPI + geometric coding |
| **Ambisonics** | Spherical encoding | CSPM is S³ not S², + data modulation |
| **Phased Arrays** | Beamforming | CSPM is geometric, not phase-based |
| **GPS** | Multi-static positioning | CSPM adds data + orientation + LPI |

### What This Is NOT

- NOT a replacement for existing radar/lidar
- NOT a validated physics simulation
- NOT ready for operational deployment

It's a **novel modulation geometry** that could enable new capabilities when combined with existing technology.

---

## Next Steps for Demo

### Minimal Spatial Demo (Simulation)

1. Simulate 3 TX nodes at known positions
2. Simulate 1 RX at unknown position
3. Show that RX can:
   - Decode data from all 3 TXs
   - Estimate own position via triangulation
   - Verify hash chain consistency

### Hardware Demo (Future)

1. 2× USRP B210 as TX array
2. 1× USRP B210 as RX
3. Show stereoscopic position recovery + data decode

---

*Document: SPATIAL_ARRAY_CONCEPT.md*
*Date: 2026-01-03*
*Status: CONCEPT - Not validated*

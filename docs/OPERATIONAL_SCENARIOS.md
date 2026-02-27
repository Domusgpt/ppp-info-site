# CSPM Operational Scenarios: Signal-Denied Environments and Swarm Positioning

## Complete Guide to Practical Deployment

---

# Part 1: Understanding "Signal Denied"

## 1.1 What "Denied" Actually Means

CSPM is a **radio frequency (RF) system**. It still needs electromagnetic waves to propagate. The term "signal denied" usually refers to **GPS denial**, not all RF.

### Types of Denial and CSPM Response

| Denial Type | What's Blocked | GPS | CSPM | Notes |
|-------------|----------------|-----|------|-------|
| **GPS Jamming** | GPS L1/L2 bands only | ✗ FAILS | ✓ WORKS | CSPM uses different frequencies |
| **GPS Spoofing** | Fake GPS signals | ✗ FAILS | ✓ WORKS | Hash chain authenticates source |
| **Indoor** | Satellite signals (too weak) | ✗ FAILS | ✓ WORKS | Deploy local CSPM transmitters |
| **Underground** | All satellite signals | ✗ FAILS | ✓ WORKS | Deploy wired/local transmitters |
| **Urban Canyon** | Direct satellite path | ✗ DEGRADED | ✓ WORKS | Local infrastructure helps |
| **Underwater** | RF doesn't penetrate water | ✗ FAILS | ✓ ADAPTED | Use acoustic CSPM variant |
| **Deep Space** | No GPS constellation | ✗ N/A | ✓ WORKS | Satellite-to-satellite ranging |
| **Total RF Blackout** | All electromagnetic waves | ✗ FAILS | ✗ FAILS | Physics wins - no signal = no comm |
| **Faraday Cage** | All external RF | ✗ FAILS | ✗ FAILS | Must be inside the cage to work |

### Key Insight

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│  CSPM replaces GPS dependency, not RF physics.                          │
│                                                                          │
│  GPS needs:     Signals from satellites 20,000 km away                  │
│  CSPM needs:    Signals from ANY 3+ synchronized transmitters           │
│                                                                          │
│  In "denied" environments:                                               │
│  • You provide your own transmitters                                    │
│  • The swarm becomes its own positioning infrastructure                 │
│  • No external dependency required                                       │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 1.2 GPS Jamming Scenario

### The Problem

```
                    GPS Satellites
                    🛰️  🛰️  🛰️  🛰️
                     \  |  |  /
                      \ | | /
                       \|||/
                        ╳ ← JAMMER (overpowers weak GPS signals)
                        │
                    ════════════ Ground
                        │
                        ◆ Your vehicle (GPS receiver blind)
```

GPS signals are weak (~-130 dBm at ground). A 1-watt jammer can blind GPS receivers for kilometers.

### CSPM Solution

```
                        🛰️ Your CSPM Satellite
                        │  (or friendly aircraft, or ground station)
                        │
                        │  CSPM signal at -90 dBm (much stronger than GPS)
                        │  Different frequency than GPS
                        │  Hash-chain authenticated (can't spoof)
                        │
                    ════════════ Ground
                        │
                        ◆ Your vehicle
                          • Ignores GPS (jammed anyway)
                          • Receives CSPM from 3+ friendly transmitters
                          • Computes position from CSPM timing
                          • Jammer is irrelevant

Why it works:
• CSPM doesn't use GPS frequencies
• CSPM signals are stronger (closer transmitters)
• Hash chain prevents spoofing (attacker can't fake the signal)
```

---

## 1.3 GPS Spoofing Scenario

### The Problem

```
                    Real GPS Satellites
                    🛰️  🛰️  🛰️  🛰️
                     \  |  |  /
                      \ | | /
                       \|||/
                        │
         SPOOFER ──────►│◄────── Fake "GPS" signals
         📡             │        (stronger than real)
                    ════════════
                        │
                        ◆ Your vehicle
                          GPS receiver sees fake position
                          Thinks it's in wrong location
                          Navigation corrupted
```

### CSPM Solution

```
                    CSPM Transmitters (known, trusted)
                    ◆TX1    ◆TX2    ◆TX3
                     \      |      /
                      \     |     /
                       \    |    /
                        \   |   /
                    ════════════════
                            │
         ATTACKER ─────────►│  Tries to fake CSPM signal
         📡                 │
                            │
                        ◆ Your vehicle
                          │
                          ▼
        ┌────────────────────────────────────────┐
        │ CSPM receiver checks hash chain:       │
        │                                        │
        │ Expected rotation: R = f(H_n)          │
        │ Received rotation: R' = ???            │
        │                                        │
        │ If R ≠ R': REJECT as spoofed          │
        │                                        │
        │ Attacker doesn't know hash seed        │
        │ → Can't predict rotation               │
        │ → Can't create valid fake signal       │
        └────────────────────────────────────────┘

Why it works:
• Hash chain is a shared secret
• Each symbol's rotation depends on ALL previous packets
• Attacker would need to know seed AND entire history
• Even if they capture signal, they can't predict next rotation
```

---

## 1.4 Indoor / Underground Scenario

### The Problem

```
═══════════════════════════════════════════════════════════ Surface
        │
        │   GPS signals don't penetrate             🛰️ GPS (blocked)
        │   buildings/earth                              │
        │                                                ╳
════════╪════════════════════════════════════════════════════ Building/Ground
        │
        │   ◆ Robot/person inside
        │     "Where am I?"
        │     GPS: "No signal"
        │
```

### CSPM Solution: Local Infrastructure

```
═══════════════════════════════════════════════════════════ Surface
        │
        │   ★ Base Station (knows GPS position, syncs time)
        │   │
════════╪═══╪════════════════════════════════════════════════════
        │   │
FLOOR 1 │   ├──────◆TX1──────────◆TX2──────────◆TX3────
        │   │       │             │             │
        │   │       │             │             │
FLOOR 2 │   │       ◆TX4─────────◆TX5──────────◆TX6────
        │   │       │             │             │
        │   │       │    ◆ Robot  │             │
        │   │       │      │      │             │
        │   │       │      │      │             │
        │   │       │      ▼      │             │
        │   │       │  Receives from TX1,TX2,TX4,TX5
        │   │       │  Computes position via TDOA
        │   │       │  Works underground!
        │   │
```

**Hardware required:**
- Fixed transmitters: Simple CSPM beacons (surveyed positions)
- Wired timing: Sync all TXs to base station clock
- Mobile units: CSPM receivers only

**Example: Warehouse**
```
┌──────────────────────────────────────────────────────────────┐
│                         WAREHOUSE                             │
│                                                               │
│   ◆TX1                    ◆TX2                    ◆TX3       │
│   (corner 1)              (center)                (corner 2)  │
│                                                               │
│        ┌─────┐      ┌─────┐      ┌─────┐                     │
│        │shelf│      │shelf│      │shelf│                     │
│        └─────┘      └─────┘      └─────┘                     │
│                                                               │
│                    🤖 Forklift robot                          │
│                       │                                       │
│                       ▼                                       │
│              Position: (23.5m, 15.2m)                        │
│              Accuracy: ±0.3m                                  │
│              No GPS needed                                    │
│                                                               │
│   ◆TX4                    ◆TX5                    ◆TX6       │
│   (corner 3)              (center)                (corner 4)  │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

---

## 1.5 Underwater Scenario

### The Problem

RF doesn't propagate in water. GPS is impossible.

### CSPM Adaptation: Acoustic

```
SURFACE ═══════════════════════════════════════════════════════
                │
                │   🚢 Surface ship
                │       │
                │       │ ACOUSTIC CSPM signal
                │       │ (same math, sound instead of RF)
                │       │
                │       ▼
        ~~~~~~~~│~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                │           WATER
                │
                │   ◆ Buoy 1          ◆ Buoy 2
                │       \               /
                │        \             /
                │         \           /
                │          \         /
                │           🤖 UUV (underwater vehicle)
                │              │
                │              ▼
                │      Position computed from
                │      acoustic arrival times
                │
        ════════╧══════════════════════════════════════════════
                        SEAFLOOR
```

**Changes for acoustic:**
- Frequency: ~10-50 kHz (instead of GHz)
- Speed: 1500 m/s (instead of 3×10⁸ m/s)
- Symbol rate: Much slower (acoustic bandwidth limited)
- Hash rotation: Same principle works

**Accuracy:**
- Sound speed varies with temperature, salinity, pressure
- Typical: 1-10 meter accuracy
- Better than inertial alone (which drifts)

---

## 1.6 Deep Space Scenario

### The Problem

No GPS constellation at the Moon or Mars.

### CSPM Solution: Satellite-to-Satellite Ranging

```
                    EARTH
                      ●
                     /│\
                    / │ \
                   /  │  \
                  /   │   \
            ════════════════════════════════════════
                      │
                      │  384,400 km
                      │
            ════════════════════════════════════════
                      │
                     🌙 MOON
                    / │ \
                   /  │  \
          Relay 1 🛰️  │  🛰️ Relay 2
                   \  │  /
                    \ │ /
                     \│/
                    🛰️ Relay 3
                      │
                      │
                    🤖 Lunar rover
                       │
                       ▼
              Receives from 3 relays
              Computes lunar position
              Relays know their orbits
              No Earth-based GPS needed
```

**How it works:**
1. Lunar relay satellites know their positions (orbital mechanics)
2. Relays transmit CSPM signals
3. Rover receives from 3+ relays
4. Triangulation gives position on lunar surface
5. Hash chain provides secure comm simultaneously

---

# Part 2: Swarm Positioning with Close Units

## 2.1 The Geometry Problem

Position accuracy depends on **baseline** (spacing between transmitters).

### The Fundamental Equation

```
Position Error ≈ (Range to Target) × (λ / Baseline)

Where:
  λ = wavelength of signal
  Baseline = distance between transmitters

Example at 2.4 GHz (λ = 12.5 cm):
─────────────────────────────────────────────────────────────────
Baseline     Target Range    Position Error
─────────────────────────────────────────────────────────────────
1 meter      1 km            125 meters     (useless)
1 meter      100 m           12.5 meters    (poor)
1 meter      10 m            1.25 meters    (okay)
1 meter      1 m             12.5 cm        (excellent)
─────────────────────────────────────────────────────────────────
10 meters    1 km            12.5 meters    (poor)
10 meters    100 m           1.25 meters    (good)
10 meters    10 m            12.5 cm        (excellent)
─────────────────────────────────────────────────────────────────
100 meters   1 km            1.25 meters    (good)
100 meters   100 m           12.5 cm        (excellent)
─────────────────────────────────────────────────────────────────
```

### Visual Explanation

```
CASE 1: Transmitters far apart (good geometry)
──────────────────────────────────────────────

         ◆TX1                              ◆TX2
            \                              /
             \     100 meter baseline     /
              \                          /
               \                        /
                \    ● Target          /
                 \      │             /
                  \     │            /
                   \    │           /
                    \   │          /
                     \  │         /
                      \ │        /
                       \│       /
                        ◆TX3

Angle to target is very different from each TX
→ Lines intersect at a POINT
→ Good position accuracy


CASE 2: Transmitters close together (poor geometry)
───────────────────────────────────────────────────

                        ● Target (1 km away)
                        │
                        │
                        │
                        │
                        │
                        │
                       ◆◆◆ TX1, TX2, TX3 (1 meter apart)

Angle to target is almost identical from each TX
→ Lines are nearly parallel
→ Intersection is a large ZONE, not a point
→ Poor position accuracy
```

---

## 2.2 Close Units: What Works and What Doesn't

### Three Drones 1 Meter Apart

```
┌─────────────────────────────────────────────────────────────────────────┐
│  SCENARIO: 3 drones in tight formation (1m spacing)                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│           ◆ Drone A                                                      │
│          / \                                                             │
│         /   \     1 meter                                               │
│        /     \    spacing                                               │
│       ◆───────◆                                                          │
│    Drone B   Drone C                                                     │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│  WHAT THEY CAN MEASURE ACCURATELY:                                       │
│                                                                          │
│  ✓ Distance A ↔ B:     ±0.5 cm   (excellent)                            │
│  ✓ Distance B ↔ C:     ±0.5 cm   (excellent)                            │
│  ✓ Distance A ↔ C:     ±0.5 cm   (excellent)                            │
│  ✓ Triangle shape:      precise                                          │
│  ✓ Relative orientation: precise                                         │
│  ✓ Formation keeping:   excellent                                        │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│  WHAT THEY CANNOT MEASURE:                                               │
│                                                                          │
│  ✗ Absolute position in world:  unknown (no reference)                  │
│  ✗ Absolute heading (north):    unknown (no reference)                  │
│  ✗ Position of target 1km away: ±100+ meters (terrible geometry)        │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│  THIS IS STILL USEFUL FOR:                                               │
│                                                                          │
│  • Formation flying (maintain spacing)                                   │
│  • Collision avoidance (know where peers are)                           │
│  • Relative navigation (move as a group)                                 │
│  • Shape maintenance (keep triangle intact)                              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2.3 Solutions for Close-Unit Swarms

### Solution 1: Anchor Node

One unit knows its absolute position. Others derive from it.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ANCHOR + FOLLOWERS ARCHITECTURE                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│              ★ ANCHOR DRONE                                              │
│              │  • Has INS (inertial navigation)                         │
│              │  • Or had GPS fix before entering denied area            │
│              │  • Or has visual odometry                                │
│              │  • KNOWS its absolute position                           │
│             /│\                                                          │
│            / │ \                                                         │
│           /  │  \   CSPM ranging                                        │
│          /   │   \                                                       │
│         ◆    ◆    ◆  FOLLOWER DRONES                                    │
│         │    │    │  • CSPM receiver only                               │
│         │    │    │  • Know distance to anchor                          │
│         │    │    │  • Know relative position to each other             │
│         │    │    │  • DERIVE absolute position from anchor             │
│         │    │    │                                                      │
│        ◆ ◆  ◆ ◆  ◆ ◆  More followers...                                │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ABSOLUTE POSITION COMPUTATION:                                          │
│                                                                          │
│  Anchor position: P_anchor = (100.0, 200.0, 50.0) meters               │
│  Follower range to anchor: d = 5.2 meters                               │
│  Follower range to peer 1: d1 = 3.1 meters                              │
│  Follower range to peer 2: d2 = 4.7 meters                              │
│                                                                          │
│  → Solve trilateration → Follower position = (104.2, 202.1, 50.3)      │
│                                                                          │
│  Accuracy: Same as relative accuracy (±cm) + anchor accuracy            │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Solution 2: Pre-Mission Reference

```
┌─────────────────────────────────────────────────────────────────────────┐
│  KNOWN START POINT                                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  BEFORE MISSION (GPS available):                                         │
│                                                                          │
│      All drones at known location                                        │
│      GPS: Latitude/Longitude recorded                                    │
│      All drones sync: "We are HERE"                                     │
│                                                                          │
│                 ◆◆◆ Starting position                                   │
│                  │   (47.6062° N, 122.3321° W)                          │
│                  │                                                       │
│                  ▼                                                       │
│                                                                          │
│  DURING MISSION (GPS denied):                                            │
│                                                                          │
│      Drones move, tracking relative changes                             │
│      "We moved 50m north, 30m east"                                     │
│      Absolute position = Start + Accumulated Delta                      │
│                                                                          │
│                 ◆◆◆ Current position                                    │
│                     (47.6066° N, 122.3317° W)                           │
│                     Computed from start + relative motion               │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ACCURACY:                                                               │
│  • Relative: ±cm (excellent)                                            │
│  • Absolute: Drifts over time without correction                        │
│  • Better than INS alone (geometric constraints help)                   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Solution 3: Occasional External Fix

```
┌─────────────────────────────────────────────────────────────────────────┐
│  INTERMITTENT REFERENCE                                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  TIME 0:00 - GPS available                                               │
│      All drones get GPS fix                                             │
│      Absolute accuracy: ±3m                                             │
│                                                                          │
│  TIME 0:00-0:30 - GPS denied (indoors, jammed, etc.)                    │
│      Swarm uses CSPM relative positioning                               │
│      Absolute position drifts slowly                                     │
│      Drift rate: ~0.1% of distance traveled                             │
│                                                                          │
│  TIME 0:30 - Brief GPS available (window, gap in jamming)               │
│      One drone gets GPS fix                                              │
│      Broadcasts correction to swarm                                      │
│      Absolute accuracy reset to ±3m                                     │
│                                                                          │
│  TIME 0:30-1:00 - GPS denied again                                       │
│      Continue with CSPM relative                                         │
│      Drift from new reference point                                      │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ACCURACY OVER TIME:                                                     │
│                                                                          │
│  Error│                                                                  │
│   (m) │    ╱╲                ╱╲                ╱╲                        │
│    10 │   ╱  ╲              ╱  ╲              ╱  ╲                       │
│     5 │  ╱    ╲            ╱    ╲            ╱    ╲                      │
│     3 │─●      ╲──────────●      ╲──────────●      ╲                    │
│     0 │  GPS    ╲ Drift    GPS    ╲ Drift    GPS                        │
│       └────────────────────────────────────────────► Time               │
│         Fix    CSPM      Fix    CSPM       Fix                          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Solution 4: Expand the Baseline

If you need to locate distant targets, spread out.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  EXPANDABLE GEOMETRY                                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  FORMATION A: Tight (surveillance mode)                                  │
│  ─────────────────────────────────────                                   │
│           ◆                                                              │
│          ◆ ◆    3 drones, 1m apart                                      │
│                 Good for: Formation flight, peer tracking               │
│                 Bad for: Locating distant targets                       │
│                                                                          │
│                     │                                                    │
│                     │ EXPAND                                             │
│                     ▼                                                    │
│                                                                          │
│  FORMATION B: Wide (positioning mode)                                    │
│  ────────────────────────────────────                                    │
│                                                                          │
│       ◆                                        ◆                         │
│                                                                          │
│                                                                          │
│                          ◆                                               │
│                                                                          │
│                 3 drones, 100m apart                                    │
│                 Good for: Locating targets at 1km+                      │
│                 Position accuracy: ±1-3m at 1km                         │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  TACTICAL USE:                                                           │
│                                                                          │
│  1. Fly in tight formation to target area                               │
│  2. Spread out when positioning needed                                  │
│  3. Locate target with good geometry                                    │
│  4. Collapse back to tight formation                                    │
│  5. Return home                                                          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2.4 The 85/15 Swarm Architecture (Revisited)

### Full System Design

```
┌─────────────────────────────────────────────────────────────────────────┐
│  HETEROGENEOUS SWARM: 85% SIMPLE + 15% CORE                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  CORE NODES (15% of swarm)                                               │
│  ─────────────────────────                                               │
│      ★ Full CSPM transceiver (TX + RX)                                  │
│      ★ Hash chain master (generates rotations)                          │
│      ★ Anchor capability (has INS or last GPS fix)                      │
│      ★ Gateway to external networks                                      │
│      ★ More compute, more power, more capability                        │
│                                                                          │
│      Hardware: ~$500, ~200g, ~10W                                       │
│                                                                          │
│  SIMPLE NODES (85% of swarm)                                             │
│  ────────────────────────────                                            │
│      ◆ CSPM receiver only (no transmitter)                              │
│      ◆ Hash chain follower (syncs from core)                            │
│      ◆ Position derived from core nodes                                  │
│      ◆ Relay data to/from cores                                         │
│      ◆ Minimal compute, minimal power                                    │
│                                                                          │
│      Hardware: ~$100, ~50g, ~2W                                         │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  TOPOLOGY:                                                               │
│                                                                          │
│                    ★ Core 1                                              │
│                   /│\                                                    │
│                  / │ \                                                   │
│                 /  │  \                                                  │
│                ◆   ◆   ◆  Simple nodes (receive from Core 1)            │
│               /│   │   │\                                                │
│              / │   │   │ \                                               │
│             ◆  ◆   ◆   ◆  ◆                                             │
│                    │                                                     │
│             ★ Core 2                    ★ Core 3                         │
│            /│\                         /│\                               │
│           / │ \                       / │ \                              │
│          ◆  ◆  ◆                     ◆  ◆  ◆                            │
│                                                                          │
│  Each simple node receives from 3+ cores → position                     │
│  Cores spread out for good geometry                                      │
│  Simple nodes cluster around cores                                       │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  FAILURE MODES:                                                          │
│                                                                          │
│  Core fails:                                                             │
│      → Remaining cores maintain network                                 │
│      → A simple node can be promoted to core (if hardware capable)      │
│      → Graceful degradation                                              │
│                                                                          │
│  Simple node fails:                                                      │
│      → No impact on others                                               │
│      → Cheaply replaceable                                               │
│                                                                          │
│  All cores fail:                                                         │
│      → Simple nodes lose absolute reference                             │
│      → Can still maintain relative formation                            │
│      → Mission degraded but not lost                                     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2.5 Accuracy Summary Table

| Configuration | Relative Accuracy (peer-to-peer) | Absolute Accuracy (world coords) | Best Use Case |
|---------------|----------------------------------|----------------------------------|---------------|
| 3 units, 1m apart, no anchor | ±0.5 cm | Unknown | Formation keeping |
| 3 units, 1m apart, 1 anchor with INS | ±0.5 cm | ±1m + INS drift | Short missions |
| 3 units, 1m apart, 1 anchor with GPS start | ±0.5 cm | ±3m + drift | Medium missions |
| 3 units, 10m apart | ±5 cm | Depends on anchor | General ops |
| 3 units, 100m apart | ±10 cm | ±1-3m with anchor | Target location |
| Fixed infrastructure (warehouse) | N/A | ±0.3m | Indoor robots |
| Satellite constellation | N/A | ±1-10m | Global coverage |

---

## 2.6 Worked Example: Mine Rescue Robot Swarm

### Scenario

Collapsed mine. GPS doesn't work underground. Need robots to search.

### Deployment

```
SURFACE
═══════════════════════════════════════════════════════════════════════════
        │
        │   ★ Base Station
        │   │  • GPS known position: (47.123, -122.456)
        │   │  • Atomic clock for timing
        │   │  • Controls hash chain
        │   │
════════╪═══╪══════════════════════════════════════════════════════════════
        │   │
SHAFT   │   │
        │   │ (fiber optic cable for timing sync)
        │   │
════════╪═══╪══════════════════════════════════════════════════════════════
        │   │
LEVEL 1 │   ├─────◆TX1─────────◆TX2──────────◆TX3──────────◆TX4────
        │   │      │            │             │             │
        │   │     Surveyed positions relative to shaft entrance
        │   │     TX1: (0, 0, -30)     TX2: (50, 0, -30)
        │   │     TX3: (100, 0, -30)   TX4: (100, 50, -30)
        │   │
════════╪═══╪══════════════════════════════════════════════════════════════
        │   │
LEVEL 2 │   │      ★ Core Robot (has TX, carries more gear)
        │   │         │
        │   │         │  Receives from TX1-TX4
        │   │         │  Computes position: (75.2, 23.1, -60.0) ±0.5m
        │   │         │
        │   │         │  Broadcasts to simple robots
        │   │         │
        │   │        / \
        │   │       ◆   ◆  Simple robots
        │   │       │   │  Receive from Core + TX1-TX4
        │   │       │   │  Know their positions
        │   │       │   │  Search debris
        │   │
        │   │
        │   │               ◆ Simple robot
        │   │               │ Position: (82.1, 31.4, -60.0) ±0.5m
        │   │               │ "I found something at this location!"
        │   │
```

### What This Achieves

- **Absolute position** of every robot (relative to mine survey)
- **No GPS needed** underground
- **Cheap simple robots** can explore (just receivers)
- **Few core robots** maintain network
- **Rescue coordinates** can be reported: "Survivor at level 2, 82m east, 31m north of shaft"

---

# Part 3: Summary

## What CSPM Enables

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│  SIGNAL DENIED = GPS DENIED, NOT RF DENIED                              │
│                                                                          │
│  CSPM provides positioning WHEREVER you can get RF signals:             │
│  • From your own transmitters (local infrastructure)                    │
│  • From your own swarm members (self-contained)                         │
│  • From friendly satellites (space-based)                               │
│  • From acoustic transducers (underwater adaptation)                    │
│                                                                          │
│  CLOSE UNITS (< 10m spacing):                                           │
│  • Excellent RELATIVE positioning (cm accuracy)                         │
│  • Need ANCHOR for absolute positioning                                 │
│  • Perfect for formation flying, collision avoidance                    │
│                                                                          │
│  SPREAD UNITS (> 100m spacing):                                         │
│  • Good ABSOLUTE positioning (meter accuracy)                           │
│  • Can locate distant targets                                           │
│  • Requires more coordination                                            │
│                                                                          │
│  85/15 ARCHITECTURE:                                                     │
│  • 15% expensive cores (TX+RX, anchor, gateway)                         │
│  • 85% cheap simples (RX only, follow cores)                            │
│  • Massive cost/weight/power savings                                     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## When To Use Each Configuration

| Situation | Configuration | Why |
|-----------|---------------|-----|
| Tight drone swarm | 3+ units close, 1 anchor | Relative is enough, anchor gives absolute |
| Warehouse robots | Fixed TX infrastructure | Best accuracy, no robot needs TX |
| Underground search | Core robots + simple robots | Balance cost/capability |
| Ocean survey | Acoustic buoys + AUVs | Adapted for underwater |
| Lunar surface | Relay satellites + rovers | No GPS alternative exists |
| Military convoy | Vehicle-mounted TXs spread | Mobile infrastructure |
| Indoor tracking | Fixed ceiling TXs | Simple receiver tags |

---

*Document version 1.0 - January 2026*

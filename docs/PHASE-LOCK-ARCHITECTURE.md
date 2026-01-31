# Phase-Lock Architecture

> Deep dive into the system architecture, design decisions, and implementation details.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           PHASE-LOCK ARCHITECTURE                               │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                          INPUT LAYER                                     │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐   │   │
│  │  │  WebSocket   │  │    Serial    │  │  Simulation  │  │  Playback  │   │   │
│  │  │   Adapter    │  │   Adapter    │  │   Generator  │  │   Player   │   │   │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └─────┬──────┘   │   │
│  │         │                 │                 │                │          │   │
│  │         └─────────────────┴────────┬────────┴────────────────┘          │   │
│  │                                    │                                     │   │
│  │                                    ▼                                     │   │
│  │                         ┌──────────────────┐                             │   │
│  │                         │  Unified Ingest  │                             │   │
│  │                         │    Interface     │                             │   │
│  │                         └────────┬─────────┘                             │   │
│  └──────────────────────────────────┼───────────────────────────────────────┘   │
│                                     │                                           │
│  ┌──────────────────────────────────┼───────────────────────────────────────┐   │
│  │                    SYNCHRONIZATION LAYER                                 │   │
│  │                                  │                                       │   │
│  │                                  ▼                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐    │   │
│  │  │                      TimeBinder (The Loom)                       │    │   │
│  │  │  ┌─────────────────────────────────────────────────────────┐    │    │   │
│  │  │  │                     RingBuffer                           │    │    │   │
│  │  │  │  ┌────┬────┬────┬────┬────┬────┬────┬────┬────┬────┐    │    │    │   │
│  │  │  │  │ T₀ │ T₁ │ T₂ │ T₃ │ T₄ │ T₅ │ T₆ │ T₇ │ T₈ │ T₉ │    │    │    │   │
│  │  │  │  └────┴────┴────┴────┴────┴────┴────┴────┴────┴────┘    │    │    │   │
│  │  │  │       ↑                              ↑                   │    │    │   │
│  │  │  │      tail                           head                 │    │    │   │
│  │  │  └─────────────────────────────────────────────────────────┘    │    │   │
│  │  │                           │                                      │    │   │
│  │  │                           ▼                                      │    │   │
│  │  │  ┌─────────────────────────────────────────────────────────┐    │    │   │
│  │  │  │              Phase-Lock Calculator                       │    │    │   │
│  │  │  │                                                          │    │    │   │
│  │  │  │   Target = Now - LatencyBuffer                          │    │    │   │
│  │  │  │                                                          │    │    │   │
│  │  │  │   Binary Search → [Tick_A, Tick_B]                      │    │    │   │
│  │  │  │                                                          │    │    │   │
│  │  │  │   t = (Target - Tick_A.time) / (Tick_B.time - Tick_A)   │    │    │   │
│  │  │  └─────────────────────────────────────────────────────────┘    │    │   │
│  │  └─────────────────────────────────────────────────────────────────┘    │   │
│  │                                  │                                       │   │
│  │                                  ▼                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐    │   │
│  │  │                   GeometricLerp (The Smoother)                   │    │   │
│  │  │                                                                  │    │   │
│  │  │   ┌──────────────────────────────────────────────────────┐      │    │   │
│  │  │   │                  SLERP Engine                         │      │    │   │
│  │  │   │                                                       │      │    │   │
│  │  │   │   q₀ ●━━━━━━━━━━━━━━━●━━━━━━━━━━━━━━━● q₁            │      │    │   │
│  │  │   │                      ↑                                │      │    │   │
│  │  │   │              interpolated point                       │      │    │   │
│  │  │   │                                                       │      │    │   │
│  │  │   │   slerp(q₀, q₁, t) = q₀(q₀⁻¹q₁)^t                   │      │    │   │
│  │  │   └──────────────────────────────────────────────────────┘      │    │   │
│  │  │                                                                  │    │   │
│  │  │   ┌──────────────────────────────────────────────────────┐      │    │   │
│  │  │   │                  Rotor4D Handler                      │      │    │   │
│  │  │   │                                                       │      │    │   │
│  │  │   │   Left Quaternion:  XY, XZ, YZ planes                │      │    │   │
│  │  │   │   Right Quaternion: XW, YW, ZW planes                │      │    │   │
│  │  │   │                                                       │      │    │   │
│  │  │   │   R = (q_L, q_R)  →  slerp both independently        │      │    │   │
│  │  │   └──────────────────────────────────────────────────────┘      │    │   │
│  │  └─────────────────────────────────────────────────────────────────┘    │   │
│  └──────────────────────────────────┬───────────────────────────────────────┘   │
│                                     │                                           │
│  ┌──────────────────────────────────┼───────────────────────────────────────┐   │
│  │                      OUTPUT LAYER                                        │   │
│  │                                  │                                       │   │
│  │                                  ▼                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐    │   │
│  │  │               StereoscopicFeed (Data Prism)                      │    │   │
│  │  │                                                                  │    │   │
│  │  │   ┌─────────────────────┐     ┌─────────────────────┐          │    │   │
│  │  │   │      LEFT EYE       │     │      RIGHT EYE      │          │    │   │
│  │  │   │     (2D Chart)      │     │   (4D Geometry)     │          │    │   │
│  │  │   │                     │     │                     │          │    │   │
│  │  │   │  • priceHistory[]   │     │  • smoothedRotation │          │    │   │
│  │  │   │  • currentPrice     │     │  • rawRotation      │          │    │   │
│  │  │   │  • ohlcv[]          │     │  • phaseVector      │          │    │   │
│  │  │   │  • indicators       │     │  • rotor            │          │    │   │
│  │  │   │  • volume           │     │  • velocity         │          │    │   │
│  │  │   └──────────┬──────────┘     └──────────┬──────────┘          │    │   │
│  │  │              │                           │                      │    │   │
│  │  └──────────────┼───────────────────────────┼──────────────────────┘    │   │
│  │                 │                           │                            │   │
│  └─────────────────┼───────────────────────────┼────────────────────────────┘   │
│                    │                           │                                │
│                    ▼                           ▼                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                         PPP INTEGRATION                                  │   │
│  │                                                                          │   │
│  │   ┌────────────────┐  ┌────────────────┐  ┌────────────────────────┐    │   │
│  │   │  2D Chart      │  │  DataMapper    │  │  HypercubeRenderer    │    │   │
│  │   │  Renderer      │  │                │  │  (WebGL)              │    │   │
│  │   │                │  │  64 channels   │  │                        │    │   │
│  │   │  (External)    │  │  ───────────▶ │  │  u_rotXY, u_rotXZ...  │    │   │
│  │   └────────────────┘  └────────────────┘  └────────────────────────┘    │   │
│  │                                                      │                   │   │
│  │                                                      ▼                   │   │
│  │                                           ┌────────────────────────┐    │   │
│  │                                           │  SonicGeometryEngine  │    │   │
│  │                                           │                        │    │   │
│  │                                           │  • Hopf Fiber         │    │   │
│  │                                           │  • Parity Metrics     │    │   │
│  │                                           │  • Spinor Telemetry   │    │   │
│  │                                           └────────────────────────┘    │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Deep Dives

### 1. RingBuffer Implementation

The RingBuffer provides O(1) insertion with automatic oldest-entry eviction:

```
Initial state (capacity=5):
┌───┬───┬───┬───┬───┐
│   │   │   │   │   │
└───┴───┴───┴───┴───┘
 ↑
head/tail (empty)

After 3 insertions:
┌───┬───┬───┬───┬───┐
│ A │ B │ C │   │   │
└───┴───┴───┴───┴───┘
 ↑           ↑
tail        head

After 7 insertions (wrapped):
┌───┬───┬───┬───┬───┐
│ F │ G │ C │ D │ E │
└───┴───┴───┴───┴───┘
     ↑   ↑
   head tail

Reading order: C → D → E → F → G (oldest to newest)
```

**Key invariants:**
- `head` points to next write position
- `tail` points to oldest entry
- When `head` catches `tail`, oldest entry is overwritten
- All entries between `tail` and `head-1` are valid

### 2. Binary Search for Temporal Lookup

Given target time `T`, find bracket `[T_a, T_b]` where `T_a ≤ T < T_b`:

```
Buffer (sorted by time):
┌─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┐
│ 100 │ 120 │ 145 │ 160 │ 180 │ 195 │ 210 │ 230 │
└─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┘
                    ↑
              Target: 170

Step 1: mid = 4, buffer[4] = 180 > 170, high = 4
Step 2: mid = 2, buffer[2] = 145 < 170, low = 2
Step 3: mid = 3, buffer[3] = 160 < 170, low = 3
Step 4: low = 3, high = 4, done

Result: [160, 180], interpolation factor = (170-160)/(180-160) = 0.5
```

### 3. SLERP on the Hypersphere

Quaternions form a unit 3-sphere (S³) in 4D space. SLERP traces the geodesic (shortest path) on this sphere:

```
                    S³ (unit quaternion sphere)
                           ___________
                        ,-'           `-.
                      ,'                 `.
                     /         ●q₁        \
                    |        ／            |
                    |      ／ ← SLERP path |
                    |    ／                |
                     \  ／                 /
                      `●───────────────'
                       q₀
                        `.           ,'
                          `-._____,-'

Linear interpolation (LERP) would cut through the sphere's interior,
producing non-unit quaternions and uneven angular velocity.

SLERP maintains:
1. Unit length (stays on sphere surface)
2. Constant angular velocity
3. Shortest path (when dot product check applied)
```

### 4. Double-Quaternion for 4D Rotation

A single quaternion handles 3 rotation planes. For 4D, we need 6 planes:

```
┌─────────────────────────────────────────────────────────────┐
│                    4D ROTATION PLANES                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   3D Subspace (handled by q_left):     4th Dimension (q_right):
│                                                              │
│        Y                                    W                │
│        │                                    │                │
│        │   ╱ Z                              │                │
│        │ ╱                                  │                │
│        │╱                                   │                │
│   ─────●───── X                        ─────●───── X,Y,Z     │
│                                                              │
│   Planes: XY, XZ, YZ                  Planes: XW, YW, ZW    │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   Rotor4D = (q_left, q_right)                               │
│                                                              │
│   SLERP(R₀, R₁, t) = (                                      │
│       SLERP(q₀_left, q₁_left, t),                          │
│       SLERP(q₀_right, q₁_right, t)                         │
│   )                                                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Flow Timing

### Frame Timeline

```
Real Time:     T-100    T-50     T        T+16.67   T+33.33
                │        │        │           │         │
Data arrives:  ─●────────●────●───┼───────────┼─────────┼──
               tick₁   tick₂ tick₃            │         │
                                  │           │         │
Render frames: ──────────────────┼───────────●─────────●──
                                  │         frame₁   frame₂
                                  │           │
                                  │           │
Phase-Lock target for frame₁:    │           │
                                  │◄──50ms───┤
                                  ↑
                            T+16.67-50 = T-33.33

Binary search finds: tick₂ (T-50) and tick₃ (T)
Interpolation: t = (T-33.33 - (T-50)) / (T - (T-50))
                 = 16.67 / 50 = 0.333
```

### Latency Buffer Rationale

```
Without latency buffer (render at Now):
─────●────────────────────?──▶ What data? None arrived yet!
    last                 Now
    tick

With latency buffer (render at Now - 50ms):
─────●─────────●─────────●───────▶
    T-80     T-50       T-20    Now
                ↑
         render target (T-50)

Always has data brackets for interpolation!
```

---

## State Machine

### StereoscopicFeed States

```
┌─────────────┐
│  INACTIVE   │ ←── Initial state, no data
└──────┬──────┘
       │ first ingest()
       ▼
┌─────────────┐
│  BUFFERING  │ ←── Filling initial buffer
└──────┬──────┘
       │ buffer > latencyBuffer
       ▼
┌─────────────┐
│   ACTIVE    │ ←── Normal operation
└──────┬──────┘
       │ no data for 5s
       ▼
┌─────────────┐
│   STALE     │ ←── Data feed interrupted
└──────┬──────┘
       │ new ingest()
       ▼
┌─────────────┐
│   ACTIVE    │
└─────────────┘
```

### Interpolation Modes

```
┌────────────────────────────────────────────────────────────────┐
│                    INTERPOLATION DECISION TREE                  │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│   getSyncedFrame(target)                                       │
│         │                                                       │
│         ▼                                                       │
│   ┌─────────────┐                                              │
│   │ Buffer      │──empty──▶ Return default frame               │
│   │ empty?      │                                              │
│   └──────┬──────┘                                              │
│          │ not empty                                            │
│          ▼                                                       │
│   ┌─────────────┐                                              │
│   │ target <    │──yes──▶ Return oldest frame (extrapolate)    │
│   │ oldest?     │         syncError++                          │
│   └──────┬──────┘                                              │
│          │ no                                                   │
│          ▼                                                       │
│   ┌─────────────┐                                              │
│   │ target >    │──yes──▶ Return newest frame (extrapolate)    │
│   │ newest?     │         syncError++                          │
│   └──────┬──────┘                                              │
│          │ no                                                   │
│          ▼                                                       │
│   ┌─────────────┐                                              │
│   │ Exact match │──yes──▶ Return exact frame                   │
│   │ found?      │         exactHit++                           │
│   └──────┬──────┘                                              │
│          │ no                                                   │
│          ▼                                                       │
│   Binary search for bracket [tick_a, tick_b]                   │
│         │                                                       │
│         ▼                                                       │
│   SLERP interpolate rotation                                   │
│   LERP interpolate price                                       │
│         │                                                       │
│         ▼                                                       │
│   Return interpolated frame                                     │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

---

## Memory Layout

### Tick Structure (80 bytes typical)

```
┌────────────────────────────────────────────────────────────┐
│                         Tick                                │
├────────────────────────────────────────────────────────────┤
│ timestamp    │ float64  │ 8 bytes  │ ms since epoch        │
├──────────────┼──────────┼──────────┼───────────────────────┤
│ priceVector  │ object   │ 32 bytes │ {open,high,low,close} │
├──────────────┼──────────┼──────────┼───────────────────────┤
│ rotation     │ object   │ 48 bytes │ 6 × float64           │
├──────────────┼──────────┼──────────┼───────────────────────┤
│ volume       │ float64  │ 8 bytes  │ optional              │
└────────────────────────────────────────────────────────────┘
                            Total: ~80 bytes per tick
```

### Buffer Memory

```
┌─────────────────────────────────────────────────────────────┐
│               Memory Usage (default config)                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ TimeBinder:                                                  │
│   RingBuffer[1000] × 80 bytes = 80 KB                       │
│   Metadata                    =  1 KB                       │
│                               ────────                       │
│                                 81 KB                        │
│                                                              │
│ GeometricLerp:                                              │
│   Keyframes[500] × 80 bytes   = 40 KB                       │
│   Quaternion cache            =  2 KB                       │
│                               ────────                       │
│                                 42 KB                        │
│                                                              │
│ StereoscopicFeed:                                           │
│   Price history[500] × 8      =  4 KB                       │
│   State objects               =  2 KB                       │
│                               ────────                       │
│                                  6 KB                        │
│                                                              │
│ ═══════════════════════════════════════════                 │
│ TOTAL                         ≈ 130 KB                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Thread Safety

Phase-Lock is designed for single-threaded JavaScript execution but follows patterns that would enable Web Worker isolation:

```
┌─────────────────────────────────────────────────────────────┐
│                   THREAD BOUNDARIES                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   Main Thread                     Worker Thread (future)    │
│   ────────────                    ──────────────────────    │
│                                                              │
│   ┌──────────────┐               ┌──────────────┐          │
│   │ UI Events    │               │ Data Ingest  │          │
│   │ Render Loop  │  ◄──────────  │ SLERP Calc   │          │
│   │ DOM Updates  │  SharedArray  │ Buffer Mgmt  │          │
│   └──────────────┘  Buffer       └──────────────┘          │
│                                                              │
│   Current: All on main thread (sufficient for 60fps)        │
│   Future: Heavy math could move to worker                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Error Handling

### Sync Error Categories

| Error | Cause | Recovery |
|-------|-------|----------|
| `BUFFER_UNDERFLOW` | Render ahead of data | Use newest available |
| `BUFFER_OVERFLOW` | Data arriving faster than consumption | Drop oldest |
| `INTERPOLATION_FAILURE` | Malformed quaternion | Use identity rotation |
| `TIMESTAMP_REGRESSION` | Clock went backwards | Reset buffer |

### Graceful Degradation

```
Priority 1: Render something (never block)
    │
    ▼
Priority 2: Use interpolated data if available
    │
    ▼
Priority 3: Use nearest available data
    │
    ▼
Priority 4: Use last known good state
    │
    ▼
Priority 5: Use identity/default state
```

---

## Testing Strategy

### Unit Test Coverage

```
┌─────────────────────────────────────────────────────────────┐
│                    TEST COVERAGE MAP                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   RingBuffer         ████████████████████  100%             │
│   ├─ insertion       ████████████████████                   │
│   ├─ overflow        ████████████████████                   │
│   ├─ iteration       ████████████████████                   │
│   └─ binary search   ████████████████████                   │
│                                                              │
│   Quaternion         ████████████████████  100%             │
│   ├─ construction    ████████████████████                   │
│   ├─ multiplication  ████████████████████                   │
│   ├─ normalization   ████████████████████                   │
│   ├─ SLERP          ████████████████████                   │
│   └─ edge cases      ████████████████████                   │
│                                                              │
│   TimeBinder         ████████████████████  100%             │
│   ├─ phase-lock      ████████████████████                   │
│   ├─ interpolation   ████████████████████                   │
│   ├─ seek            ████████████████████                   │
│   └─ metrics         ████████████████████                   │
│                                                              │
│   StereoscopicFeed   ████████████████████  100%             │
│   ├─ bifurcation     ████████████████████                   │
│   ├─ smoothing       ████████████████████                   │
│   └─ integration     ████████████████████                   │
│                                                              │
│   Total: 51 tests, 100% pass rate                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Mathematical Invariants Tested

1. **Quaternion unit constraint**: `|q| = 1 ± ε`
2. **SLERP boundary conditions**: `slerp(q, q, t) = q`
3. **SLERP endpoints**: `slerp(a, b, 0) = a`, `slerp(a, b, 1) = b`
4. **Interpolation bounds**: `0 ≤ t ≤ 1`
5. **Timestamp monotonicity**: `tick[n].time < tick[n+1].time`

---

## Performance Benchmarks

### Measured on MacBook Pro M1, Chrome 120

| Operation | Time | Ops/sec |
|-----------|------|---------|
| Tick ingest | 0.008ms | 125,000 |
| getSyncedFrame | 0.045ms | 22,000 |
| SLERP (single) | 0.003ms | 333,000 |
| Full frame() call | 0.12ms | 8,300 |

### Frame Budget Analysis

```
60 FPS = 16.67ms per frame

┌────────────────────────────────────────────────────┐
│ Operation          │ Time    │ % Budget           │
├────────────────────┼─────────┼────────────────────┤
│ Phase-Lock frame() │ 0.12ms  │ 0.7%              │
│ DataMapper         │ 0.20ms  │ 1.2%              │
│ setUniforms        │ 0.10ms  │ 0.6%              │
│ WebGL render       │ 8.00ms  │ 48.0%             │
│ Spinor telemetry   │ 0.50ms  │ 3.0%              │
├────────────────────┼─────────┼────────────────────┤
│ TOTAL              │ 8.92ms  │ 53.5%             │
│ HEADROOM           │ 7.75ms  │ 46.5%             │
└────────────────────────────────────────────────────┘

Phase-Lock contributes < 1% of frame time.
```

---

## Future Enhancements

### Planned

1. **Web Worker offload**: Move SLERP calculations to worker thread
2. **SIMD optimization**: Use WebAssembly SIMD for quaternion math
3. **Predictive buffering**: ML-based prediction for lower latency
4. **Multi-source fusion**: Combine multiple data feeds with Kalman filter

### Under Consideration

1. **GPU-accelerated SLERP**: Compute shader for batch interpolation
2. **Adaptive latency**: Dynamic buffer sizing based on network conditions
3. **Compression**: Delta-encode tick stream for reduced bandwidth

---

*For API details, see [PHASE-LOCK-API.md](./PHASE-LOCK-API.md)*
*For system overview, see [PHASE-LOCK-SYSTEM.md](./PHASE-LOCK-SYSTEM.md)*

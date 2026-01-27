# Phase-Lock Stereoscopic Synchronization System

> **Version:** 1.0.0
> **Status:** Production
> **Last Updated:** January 2026
> **Author:** PPP Engineering Team

---

## Executive Summary

The **Phase-Lock Stereoscopic Synchronization System** solves a fundamental problem in real-time data visualization: ensuring that incoming data streams (market ticks, sensor readings, telemetry) remain temporally synchronized with rendered animation frames. Without phase-locking, visual artifacts including temporal aliasing, Moiré patterns, and frame tearing occur when data arrival rates don't match display refresh rates.

Phase-Lock provides:
- **Temporal synchronization** between asynchronous data streams and vsync-locked rendering
- **Sub-frame interpolation** using mathematically rigorous SLERP for smooth 4D rotations
- **Stereoscopic data bifurcation** separating 2D analytical views from 4D geometric projections
- **Latency-buffered rendering** at `Now - LatencyBuffer` for stable, predictable output

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [Solution Architecture](#solution-architecture)
3. [Core Components](#core-components)
4. [Mathematical Foundations](#mathematical-foundations)
5. [Integration with PPP](#integration-with-ppp)
6. [Performance Characteristics](#performance-characteristics)
7. [Configuration Reference](#configuration-reference)
8. [Troubleshooting](#troubleshooting)

---

## Problem Statement

### The Temporal Aliasing Problem

When visualizing real-time data streams, two independent clocks are at play:

1. **Data Clock**: Market ticks arrive at irregular intervals (1-100ms gaps)
2. **Render Clock**: Display refreshes at fixed intervals (16.67ms at 60Hz)

When these clocks are unsynchronized:

```
Data:   ──●────●──●─────●───●──●────────●───→ (irregular)
Render: ──|────|────|────|────|────|────|───→ (16.67ms fixed)
                 ↑
            Which data point do we show here?
```

**Without Phase-Lock:**
- Frame shows stale data (temporal lag)
- Frame shows future data (impossible, causes glitches)
- Frame skips data points (information loss)
- Rotation animations stutter (angular velocity discontinuities)

**With Phase-Lock:**
- Every frame renders data from `Now - LatencyBuffer`
- Missing data points are interpolated via SLERP
- Smooth, continuous rotation regardless of data gaps
- Deterministic, reproducible output

### The Stereoscopic Coherence Problem

Financial and scientific visualization often requires two simultaneous views:

- **Left Eye (Chart View)**: 2D time-series, candlesticks, line graphs
- **Right Eye (Geometric View)**: 4D polytope projections, phase space, manifolds

These views must remain coherent—when a user's crosshair moves on the chart, the 4D geometry must rotate to the corresponding state. Phase-Lock ensures both eyes see the same "moment" in data-time.

---

## Solution Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         PHASE-LOCK SYSTEM                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────────┐  │
│  │ Data Sources │    │  TimeBinder  │    │   StereoscopicFeed       │  │
│  │              │───▶│  (The Loom)  │───▶│   (Data Prism)           │  │
│  │ • WebSocket  │    │              │    │                          │  │
│  │ • Serial     │    │ • RingBuffer │    │ ┌────────┐ ┌───────────┐ │  │
│  │ • Simulation │    │ • Phase-Lock │    │ │Left Eye│ │Right Eye  │ │  │
│  └──────────────┘    │ • Binary     │    │ │(Chart) │ │(Geometry) │ │  │
│                      │   Search     │    │ └────────┘ └───────────┘ │  │
│                      └──────────────┘    └──────────────────────────┘  │
│                             │                        │                  │
│                             ▼                        ▼                  │
│                      ┌──────────────┐    ┌──────────────────────────┐  │
│                      │GeometricLerp │    │    PPP Integration       │  │
│                      │(The Smoother)│───▶│                          │  │
│                      │              │    │ • HypercubeRenderer      │  │
│                      │ • Quaternion │    │ • DataMapper             │  │
│                      │ • SLERP      │    │ • SonicGeometryEngine    │  │
│                      │ • Rotor4D    │    └──────────────────────────┘  │
│                      └──────────────┘                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Ingest**: Raw data enters via WebSocket, Serial, or simulation
2. **Buffer**: TimeBinder stores data in a RingBuffer with timestamps
3. **Synchronize**: At render time, query `getSyncedFrame(Now - LatencyBuffer)`
4. **Interpolate**: GeometricLerp provides smooth rotation between keyframes
5. **Bifurcate**: StereoscopicFeed splits data for left/right eye rendering
6. **Render**: PPP HypercubeRenderer displays the phase-locked frame

---

## Core Components

### 1. TimeBinder (The Loom)

**Purpose**: Weaves asynchronous data ticks into a coherent temporal fabric.

**Key Features**:
- **RingBuffer**: Fixed-size circular buffer (default 1000 entries)
- **O(1) Insert**: Constant-time tick insertion
- **O(log n) Lookup**: Binary search for temporal queries
- **Phase-Lock Point**: Always renders at `Now - LatencyBuffer`

**Why "The Loom"?**: Like a loom weaving threads into fabric, TimeBinder weaves disparate data points into a smooth, continuous timeline.

```javascript
const timeBinder = new TimeBinder({
    bufferSize: 1000,      // Store last 1000 ticks
    latencyBuffer: 50      // Render 50ms behind real-time
});

// Ingest data as it arrives
timeBinder.ingest({
    price: 142.50,
    volume: 10000,
    rotation: { rotXY: 0.5, rotXZ: 0.3, ... }
});

// At render time, get phase-locked frame
const frame = timeBinder.getSyncedFrame(performance.now());
```

### 2. GeometricLerp (The Smoother)

**Purpose**: Provides mathematically correct interpolation for 4D rotations.

**Key Features**:
- **Quaternion Class**: Full quaternion arithmetic with unit constraint
- **SLERP**: Spherical Linear Interpolation for constant angular velocity
- **Rotor4D**: Double-quaternion representation for 6-plane 4D rotations

**Why "The Smoother"?**: Ensures all rotations follow the shortest path on the hypersphere, eliminating gimbal lock and producing smooth, natural motion.

```javascript
const lerp = new GeometricLerp({ keyframeCapacity: 500 });

// Add rotation keyframes
lerp.addKeyframe(t0, { rotXY: 0, rotXZ: 0, rotXW: 0, rotYZ: 0, rotYW: 0, rotZW: 0 });
lerp.addKeyframe(t1, { rotXY: Math.PI/2, ... });

// Get interpolated state at any time
const state = lerp.getState(timestamp);
// state.rotation contains smoothly interpolated angles
```

### 3. StereoscopicFeed (Data Prism)

**Purpose**: Bifurcates synchronized data into left-eye and right-eye views.

**Key Features**:
- **Left Eye**: 2D chart data (price history, OHLCV, indicators)
- **Right Eye**: 4D geometric data (rotation state, phase vectors)
- **Crosshair Sync**: User interaction triggers `TimeBinder.seek(t)`
- **Event Emission**: Notifies subscribers of data updates

**Why "Data Prism"?**: Like a prism splitting white light into a spectrum, the StereoscopicFeed splits unified data into specialized views.

```javascript
const feed = new StereoscopicFeed({
    smoothing: true,
    chartHistorySize: 500,
    timeBinder: { latencyBuffer: 50, bufferSize: 1000 }
});

// Ingest raw market data
feed.ingest({ price: 142.50, volume: 10000 });

// Get bifurcated frame for rendering
const frame = feed.frame(performance.now());
// frame.leftEye  → { priceHistory, ohlcv, indicators }
// frame.rightEye → { smoothedRotation, phaseVector, rotor }
```

---

## Mathematical Foundations

### Quaternion Representation

A quaternion `q = w + xi + yj + zk` represents 3D rotations without gimbal lock:

```
q = cos(θ/2) + sin(θ/2)(axi + ayj + azk)
```

Where `θ` is the rotation angle and `(ax, ay, az)` is the unit rotation axis.

**Unit Constraint**: `|q| = √(w² + x² + y² + z²) = 1`

### SLERP (Spherical Linear Interpolation)

For quaternions `q₀` and `q₁`, SLERP produces constant angular velocity:

```
slerp(q₀, q₁, t) = q₀(q₀⁻¹q₁)^t
```

Expanded form:

```
slerp(q₀, q₁, t) = (sin((1-t)Ω)/sin(Ω))q₀ + (sin(tΩ)/sin(Ω))q₁
```

Where `Ω = arccos(q₀ · q₁)` is the angle between quaternions.

**Edge Cases**:
- `Ω ≈ 0`: Use linear interpolation (quaternions nearly identical)
- `Ω ≈ π`: Rotation is 180°, path is ambiguous (negate one quaternion)

### Rotor4D (Double-Quaternion)

4D rotations have 6 independent planes: XY, XZ, XW, YZ, YW, ZW.

A single quaternion handles 3 planes. For full 4D rotation, we use a **double-quaternion** (rotor):

```
R = (q_left, q_right)
```

The left quaternion handles XY, XZ, YZ planes.
The right quaternion handles XW, YW, ZW planes.

SLERP extends naturally:
```
slerp(R₀, R₁, t) = (slerp(q₀_left, q₁_left, t), slerp(q₀_right, q₁_right, t))
```

### Binary Search for Temporal Lookup

Given a sorted RingBuffer of timestamps, finding the bracket `[t_a, t_b]` containing target time `t`:

```
function findBracket(buffer, target):
    low = 0
    high = buffer.length - 1

    while low < high - 1:
        mid = (low + high) / 2
        if buffer[mid].timestamp <= target:
            low = mid
        else:
            high = mid

    return (buffer[low], buffer[high])
```

**Complexity**: O(log n) for n buffer entries.

---

## Integration with PPP

### Architecture Bridge

Phase-Lock integrates with PPP's existing infrastructure:

```
┌─────────────────────────────────────────────────────────────────┐
│                    phase-lock-live.html                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  StereoscopicFeed                                               │
│       │                                                         │
│       ▼                                                         │
│  phaseLockToDataArray()  ──────────────────────┐               │
│       │                                         │               │
│       ▼                                         ▼               │
│  DataMapper.mapToUniforms()            SonicGeometryEngine     │
│       │                                    │                    │
│       ▼                                    ▼                    │
│  HypercubeRenderer.setUniforms()      Spinor Telemetry         │
│       │                                                         │
│       ▼                                                         │
│  HypercubeRenderer.render()                                     │
│       │                                                         │
│       ▼                                                         │
│  WebGL Canvas (60 FPS)                                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Data Channel Mapping

Phase-Lock converts market data to PPP's 64-channel format:

| Channels | Source | Description |
|----------|--------|-------------|
| 0-3 | Price | Normalized price and trigonometric derivatives |
| 4-9 | Rotation | 6-plane rotation angles (XY, XZ, XW, YZ, YW, ZW) |
| 10-63 | Harmonics | Synthetic harmonic oscillations for visual richness |

```javascript
function phaseLockToDataArray(frame, channelCount) {
    const data = new Array(channelCount).fill(0);
    const rotation = frame.rightEye?.smoothedRotation;
    const price = frame.leftEye?.priceHistory?.slice(-1)[0];

    // Price channels
    data[0] = normalize(price, 50, 150);
    data[1] = Math.sin(data[0] * Math.PI * 2) * 0.5 + 0.5;

    // Rotation channels
    data[4] = normalizeAngle(rotation.rotXY);
    data[5] = normalizeAngle(rotation.rotXZ);
    // ... etc

    return data;
}
```

### Uniform Override

Phase-Lock directly controls PPP rotation uniforms for precise synchronization:

```javascript
const uniforms = mapper.mapToUniforms(dataArray);

// Override with phase-locked rotations
uniforms.u_rotXY = rotation.rotXY;
uniforms.u_rotXZ = rotation.rotXZ;
uniforms.u_rotXW = rotation.rotXW;
uniforms.u_rotYZ = rotation.rotYZ;
uniforms.u_rotYW = rotation.rotYW;
uniforms.u_rotZW = rotation.rotZW;

renderer.setUniforms(uniforms);
```

---

## Performance Characteristics

### Memory Usage

| Component | Memory | Notes |
|-----------|--------|-------|
| TimeBinder (1000 ticks) | ~80 KB | 80 bytes per tick average |
| GeometricLerp (500 keyframes) | ~40 KB | 80 bytes per keyframe |
| StereoscopicFeed | ~20 KB | Metadata and state |
| **Total** | **~140 KB** | Minimal footprint |

### CPU Performance

| Operation | Complexity | Typical Time |
|-----------|------------|--------------|
| Tick Ingest | O(1) | < 0.01ms |
| Frame Query | O(log n) | < 0.05ms |
| SLERP Interpolation | O(1) | < 0.02ms |
| Full Frame Generation | O(1) | < 0.1ms |

### Frame Budget

At 60 FPS, each frame has 16.67ms budget:

```
┌────────────────────────────────────────────────────┐
│                  16.67ms Frame Budget              │
├────────────────────────────────────────────────────┤
│ Phase-Lock:     0.1ms  │░                          │
│ DataMapper:     0.2ms  │░                          │
│ Uniforms:       0.1ms  │░                          │
│ WebGL Render:  10.0ms  │████████████████████       │
│ Headroom:       6.3ms  │                    ░░░░░░ │
└────────────────────────────────────────────────────┘
```

Phase-Lock consumes < 1% of frame budget.

---

## Configuration Reference

### TimeBinder Options

```javascript
new TimeBinder({
    bufferSize: 1000,       // Number of ticks to retain
    latencyBuffer: 50,      // Milliseconds behind real-time
    interpolation: 'slerp', // 'slerp' | 'linear' | 'step'
    onOverflow: 'drop',     // 'drop' | 'error' | 'resize'
})
```

### GeometricLerp Options

```javascript
new GeometricLerp({
    keyframeCapacity: 500,  // Maximum keyframes
    epsilon: 1e-6,          // Numerical precision
    shortestPath: true,     // Use shortest rotation path
})
```

### StereoscopicFeed Options

```javascript
new StereoscopicFeed({
    smoothing: true,           // Enable rotation smoothing
    smoothingFactor: 0.15,     // EMA alpha (0 = no smoothing, 1 = no change)
    chartHistorySize: 500,     // Price history length
    timeBinder: {
        latencyBuffer: 50,
        bufferSize: 1000
    }
})
```

---

## Troubleshooting

### Symptom: Rotation Stuttering

**Cause**: Data gaps exceeding latency buffer.

**Solution**: Increase `latencyBuffer` or ensure data source delivers at > 20 Hz.

### Symptom: High Sync Errors

**Cause**: Buffer underflow (rendering faster than data arrives).

**Solution**:
1. Increase `latencyBuffer`
2. Check data source connection
3. Verify system clock synchronization

### Symptom: Memory Growth

**Cause**: Buffer resize on overflow.

**Solution**: Set `onOverflow: 'drop'` or increase `bufferSize`.

### Symptom: Jerky 180° Rotations

**Cause**: SLERP ambiguity at antipodal quaternions.

**Solution**: Ensure `shortestPath: true` (default). GeometricLerp automatically negates quaternions when dot product is negative.

---

## Comparison with Alternative Approaches

| Approach | Pros | Cons |
|----------|------|------|
| **No Synchronization** | Simple | Stuttering, temporal aliasing |
| **Frame Dropping** | Low latency | Information loss |
| **Linear Interpolation** | Simple math | Gimbal lock, uneven velocity |
| **Phase-Lock + SLERP** | Smooth, correct | Slightly more complex |

Phase-Lock is the recommended approach for any visualization requiring smooth 4D rotations driven by real-time data.

---

## References

1. Shoemake, K. (1985). "Animating Rotation with Quaternion Curves." SIGGRAPH.
2. Hanson, A. J. (2006). "Visualizing Quaternions." Morgan Kaufmann.
3. Dorst, L., Fontijne, D., & Mann, S. (2007). "Geometric Algebra for Computer Science."

---

*Phase-Lock is a core component of the Polytopal Projection Processing (PPP) platform.*

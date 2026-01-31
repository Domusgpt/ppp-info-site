# Phase-Lock API Reference

> Complete API documentation for the Phase-Lock Stereoscopic Synchronization System

---

## Table of Contents

- [StereoscopicFeed](#stereoscopicfeed)
- [TimeBinder](#timebinder)
- [GeometricLerp](#geometriclerp)
- [Quaternion](#quaternion)
- [Rotor4D](#rotor4d)
- [Utility Functions](#utility-functions)
- [TypeScript Types](#typescript-types)

---

## StereoscopicFeed

The main entry point for the Phase-Lock system. Manages data ingestion, synchronization, and bifurcation.

### Constructor

```javascript
new StereoscopicFeed(options?)
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `options.smoothing` | `boolean` | `true` | Enable exponential smoothing on rotations |
| `options.smoothingFactor` | `number` | `0.15` | EMA alpha (0-1). Lower = more smoothing |
| `options.chartHistorySize` | `number` | `500` | Max price history entries for left eye |
| `options.timeBinder` | `TimeBinderOptions` | See below | Configuration for internal TimeBinder |

**Default TimeBinder Options:**
```javascript
{
    latencyBuffer: 50,
    bufferSize: 1000
}
```

### Methods

#### `ingest(tick)`

Ingests a new data tick into the system.

```javascript
feed.ingest({
    price: 142.50,
    volume: 10000,
    bid: 142.48,
    ask: 142.52,
    rotation: { rotXY: 0.5, rotXZ: 0.3, rotXW: 0.1, rotYZ: 0.2, rotYW: 0.4, rotZW: 0.6 }
});
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `tick.price` | `number` | Yes | Current price |
| `tick.volume` | `number` | No | Trade volume |
| `tick.bid` | `number` | No | Bid price |
| `tick.ask` | `number` | No | Ask price |
| `tick.rotation` | `Rotation6D` | No | 6-plane rotation state |

**Returns:** `void`

---

#### `frame(timestamp)`

Gets a phase-locked frame for rendering.

```javascript
const frame = feed.frame(performance.now());
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `timestamp` | `number` | Current time in milliseconds (typically `performance.now()`) |

**Returns:** `StereoscopicFrame`

```typescript
interface StereoscopicFrame {
    timestamp: number;
    leftEye: {
        priceHistory: number[];
        currentPrice: number;
        volume: number;
        bid: number;
        ask: number;
        ohlcv: OHLCV[];
    };
    rightEye: {
        rawRotation: Rotation6D;
        smoothedRotation: Rotation6D;
        phaseVector: number[];
        interpolationFactor: number;
    };
    syncStatus: {
        bufferSize: number;
        latency: number;
        isInterpolated: boolean;
    };
}
```

---

#### `seek(timestamp)`

Seeks to a specific point in time (for crosshair synchronization).

```javascript
feed.seek(targetTimestamp);
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `timestamp` | `number` | Target time to seek to |

**Returns:** `StereoscopicFrame`

---

#### `getMetrics()`

Returns current system metrics.

```javascript
const metrics = feed.getMetrics();
```

**Returns:** `FeedMetrics`

```typescript
interface FeedMetrics {
    framesRendered: number;
    ticksIngested: number;
    averageLatency: number;
    timeBinderMetrics: {
        bufferSize: number;
        oldestTimestamp: number;
        newestTimestamp: number;
        interpolationRate: number;
        exactHits: number;
        syncErrors: number;
    };
}
```

---

#### `reset()`

Clears all buffers and resets state.

```javascript
feed.reset();
```

**Returns:** `void`

---

## TimeBinder

Low-level temporal synchronization engine.

### Constructor

```javascript
new TimeBinder(options?)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `options.bufferSize` | `number` | `1000` | Ring buffer capacity |
| `options.latencyBuffer` | `number` | `50` | Render delay in ms |

### Methods

#### `ingest(tick)`

Adds a tick to the buffer.

```javascript
timeBinder.ingest({
    timestamp: Date.now(),
    priceVector: { open: 100, high: 101, low: 99, close: 100.5 },
    rotation: { rotXY: 0, rotXZ: 0, rotXW: 0, rotYZ: 0, rotYW: 0, rotZW: 0 }
});
```

---

#### `getSyncedFrame(timestamp)`

Returns the phase-locked frame at `timestamp - latencyBuffer`.

```javascript
const frame = timeBinder.getSyncedFrame(performance.now());
```

**Returns:** `SyncedFrame`

```typescript
interface SyncedFrame {
    timestamp: number;
    priceVector: PriceVector;
    rotation: Rotation6D;
    interpolationFactor: number;  // 0 = exact tickA, 1 = exact tickB
    tickA: Tick;                  // Lower bound tick
    tickB: Tick;                  // Upper bound tick
    phaseOffset: number;          // Distance from target
    isExact: boolean;             // True if exact match found
}
```

---

#### `seek(timestamp)`

Seeks to a specific timestamp without latency offset.

```javascript
const frame = timeBinder.seek(targetTimestamp);
```

---

#### `getMetrics()`

Returns buffer metrics.

```typescript
interface TimeBinderMetrics {
    bufferSize: number;
    capacity: number;
    oldestTimestamp: number;
    newestTimestamp: number;
    interpolationRate: number;
    exactHits: number;
    syncErrors: number;
}
```

---

## GeometricLerp

Manages keyframe-based rotation interpolation.

### Constructor

```javascript
new GeometricLerp(options?)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `options.keyframeCapacity` | `number` | `500` | Max keyframes |
| `options.epsilon` | `number` | `1e-6` | Numerical precision |

### Methods

#### `addKeyframe(timestamp, rotation)`

Adds a rotation keyframe.

```javascript
lerp.addKeyframe(performance.now(), {
    rotXY: Math.PI / 4,
    rotXZ: 0,
    rotXW: Math.PI / 6,
    rotYZ: 0,
    rotYW: 0,
    rotZW: Math.PI / 3
});
```

---

#### `getState(timestamp)`

Returns interpolated rotation state.

```javascript
const state = lerp.getState(performance.now());
```

**Returns:** `InterpolatedState`

```typescript
interface InterpolatedState {
    timestamp: number;
    rotation: Rotation6D;
    rotor: Rotor4D;
    velocity: AngularVelocity;
    interpolationFactor: number;
    keyframeA: Keyframe;
    keyframeB: Keyframe;
}
```

---

#### `clear()`

Removes all keyframes.

---

## Quaternion

Quaternion mathematics class.

### Constructor

```javascript
new Quaternion(w, x, y, z)
```

Creates a quaternion `q = w + xi + yj + zk`.

### Static Methods

#### `Quaternion.identity()`

Returns the identity quaternion `(1, 0, 0, 0)`.

---

#### `Quaternion.fromAxisAngle(axis, angle)`

Creates a quaternion from axis-angle representation.

```javascript
const q = Quaternion.fromAxisAngle([0, 1, 0], Math.PI / 2);
// 90° rotation around Y axis
```

---

#### `Quaternion.fromEuler(roll, pitch, yaw)`

Creates a quaternion from Euler angles (in radians).

```javascript
const q = Quaternion.fromEuler(0, Math.PI / 4, 0);
```

---

### Instance Methods

#### `multiply(other)`

Quaternion multiplication (Hamilton product).

```javascript
const q3 = q1.multiply(q2);
```

---

#### `conjugate()`

Returns the conjugate `q* = w - xi - yj - zk`.

---

#### `inverse()`

Returns the multiplicative inverse `q⁻¹ = q* / |q|²`.

---

#### `normalize()`

Returns unit quaternion `q / |q|`.

---

#### `dot(other)`

Quaternion dot product.

```javascript
const cosAngle = q1.dot(q2);
```

---

#### `toEuler()`

Converts to Euler angles `[roll, pitch, yaw]`.

---

#### `toAxisAngle()`

Converts to axis-angle `{ axis: [x, y, z], angle: θ }`.

---

## Rotor4D

Double-quaternion for 4D rotations.

### Constructor

```javascript
new Rotor4D(qLeft, qRight)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `qLeft` | `Quaternion` | Handles XY, XZ, YZ planes |
| `qRight` | `Quaternion` | Handles XW, YW, ZW planes |

### Static Methods

#### `Rotor4D.identity()`

Returns identity rotor.

---

#### `Rotor4D.fromPlaneAngles(angles)`

Creates rotor from 6-plane angle specification.

```javascript
const rotor = Rotor4D.fromPlaneAngles({
    rotXY: Math.PI / 4,
    rotXZ: 0,
    rotXW: Math.PI / 6,
    rotYZ: 0,
    rotYW: 0,
    rotZW: Math.PI / 3
});
```

---

### Instance Methods

#### `multiply(other)`

Rotor multiplication.

---

#### `inverse()`

Returns inverse rotor.

---

#### `toPlaneAngles()`

Extracts 6-plane angles.

**Returns:** `Rotation6D`

---

## Utility Functions

### `slerp(q0, q1, t)`

Spherical linear interpolation between quaternions.

```javascript
import { slerp } from './scripts/PhaseLockEngine.js';

const qInterp = slerp(q0, q1, 0.5);  // Midpoint rotation
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `q0` | `Quaternion` | Start quaternion |
| `q1` | `Quaternion` | End quaternion |
| `t` | `number` | Interpolation factor [0, 1] |

**Returns:** `Quaternion`

---

### `lerp(a, b, t)`

Linear interpolation for scalars.

```javascript
const mid = lerp(0, 100, 0.5);  // 50
```

---

### `clamp(value, min, max)`

Clamps value to range.

```javascript
const clamped = clamp(150, 0, 100);  // 100
```

---

## TypeScript Types

```typescript
// Core rotation type
interface Rotation6D {
    rotXY: number;  // XY plane rotation (radians)
    rotXZ: number;  // XZ plane rotation
    rotXW: number;  // XW plane rotation
    rotYZ: number;  // YZ plane rotation
    rotYW: number;  // YW plane rotation
    rotZW: number;  // ZW plane rotation
}

// Price data
interface PriceVector {
    open: number;
    high: number;
    low: number;
    close: number;
}

// Single data tick
interface Tick {
    timestamp: number;
    priceVector: PriceVector;
    rotation: Rotation6D;
    volume?: number;
    metadata?: Record<string, unknown>;
}

// OHLCV candlestick
interface OHLCV {
    timestamp: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
}

// Keyframe for interpolation
interface Keyframe {
    timestamp: number;
    rotation: Rotation6D;
    rotor: Rotor4D;
}

// Angular velocity (radians per second)
interface AngularVelocity {
    XY: number;
    XZ: number;
    XW: number;
    YZ: number;
    YW: number;
    ZW: number;
}
```

---

## Browser Global

When loaded in browser, the engine exposes:

```javascript
window.PhaseLockEngine = {
    StereoscopicFeed,
    TimeBinder,
    GeometricLerp,
    Quaternion,
    Rotor4D,
    slerp,
    lerp,
    clamp
};
```

---

## ES Module Imports

```javascript
import {
    StereoscopicFeed,
    TimeBinder,
    GeometricLerp,
    Quaternion,
    Rotor4D,
    slerp
} from './scripts/PhaseLockEngine.js';
```

---

## Usage Examples

### Basic Usage

```javascript
// Create feed
const feed = new StereoscopicFeed({
    smoothing: true,
    timeBinder: { latencyBuffer: 50 }
});

// Ingest data (called from WebSocket/simulation)
function onMarketTick(tick) {
    feed.ingest(tick);
}

// Render loop
function render(timestamp) {
    const frame = feed.frame(timestamp);

    // Use left eye for 2D chart
    drawChart(frame.leftEye.priceHistory);

    // Use right eye for 4D geometry
    setRotation(frame.rightEye.smoothedRotation);

    requestAnimationFrame(render);
}

requestAnimationFrame(render);
```

### With PPP Integration

```javascript
import { HypercubeRenderer } from './scripts/HypercubeRenderer.js';
import { DataMapper } from './scripts/DataMapper.js';
import { StereoscopicFeed } from './scripts/PhaseLockEngine.js';

const renderer = new HypercubeRenderer(canvas);
const mapper = new DataMapper(defaultMapping);
const feed = new StereoscopicFeed();

function render(timestamp) {
    const frame = feed.frame(timestamp);
    const rotation = frame.rightEye.smoothedRotation;

    const uniforms = mapper.mapToUniforms(dataArray);
    uniforms.u_rotXY = rotation.rotXY;
    uniforms.u_rotXZ = rotation.rotXZ;
    // ... etc

    renderer.setUniforms(uniforms);
    renderer.render();

    requestAnimationFrame(render);
}
```

### Crosshair Synchronization

```javascript
// When user hovers chart at time T
chartElement.addEventListener('mousemove', (e) => {
    const chartTime = pixelToTime(e.offsetX);
    const frame = feed.seek(chartTime);

    // Update 4D view to match chart position
    update4DGeometry(frame.rightEye.smoothedRotation);
});
```

---

*For architectural details, see [PHASE-LOCK-ARCHITECTURE.md](./PHASE-LOCK-ARCHITECTURE.md)*

# Phase-Locked Stereoscopy System

> **This document has been superseded by the comprehensive Phase-Lock documentation suite.**

## Documentation Index

| Document | Description |
|----------|-------------|
| **[PHASE-LOCK-SYSTEM.md](./PHASE-LOCK-SYSTEM.md)** | Main technical reference — problem statement, solution architecture, mathematical foundations, configuration, troubleshooting |
| **[PHASE-LOCK-API.md](./PHASE-LOCK-API.md)** | Complete API reference — all classes, methods, TypeScript types, usage examples |
| **[PHASE-LOCK-ARCHITECTURE.md](./PHASE-LOCK-ARCHITECTURE.md)** | Architecture deep dive — ASCII diagrams, memory layout, state machines, benchmarks, testing strategy |
| **[PHASE-LOCK-COMPARISON.md](./PHASE-LOCK-COMPARISON.md)** | Comparison with parallel PPP systems — how Phase-Lock relates to LiveQuaternionAdapters, HypercubeRenderer, SonicGeometryEngine, Spinor systems, DataPlayer/Recorder |

## Quick Start

```javascript
import { StereoscopicFeed } from './scripts/PhaseLockEngine.js';

const feed = new StereoscopicFeed({
    smoothing: true,
    timeBinder: { latencyBuffer: 50, bufferSize: 1000 }
});

// Ingest market data
feed.ingest({ price: 142.50, volume: 10000 });

// Render loop
function render(t) {
    const frame = feed.frame(t);
    // frame.leftEye  → 2D chart data
    // frame.rightEye → 4D rotation state (SLERP-interpolated)
    requestAnimationFrame(render);
}
requestAnimationFrame(render);
```

## Live Demo

Open [`phase-lock-live.html`](../phase-lock-live.html) to see the system running with the full PPP HypercubeRenderer, driven by simulated market data with the ruby red / silicon wafer dark aesthetic.

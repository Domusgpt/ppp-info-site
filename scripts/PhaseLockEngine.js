/**
 * PhaseLockEngine.js - Phase-Locked Market Data Synchronization
 *
 * Pure JavaScript implementation for browser integration.
 * Synchronizes market data streams with animation frames.
 */

// ============================================================================
// RingBuffer - O(1) insert, O(log n) lookup
// ============================================================================

export class RingBuffer {
  constructor(capacity = 1000) {
    this.capacity = capacity;
    this.buffer = new Array(capacity).fill(null);
    this.head = 0;
    this.count = 0;
  }

  push(item) {
    this.buffer[this.head] = item;
    this.head = (this.head + 1) % this.capacity;
    if (this.count < this.capacity) {
      this.count++;
    }
  }

  get(index) {
    if (index < 0 || index >= this.count) return null;
    const physicalIndex = (this.head - this.count + index + this.capacity) % this.capacity;
    return this.buffer[physicalIndex];
  }

  newest() {
    if (this.count === 0) return null;
    return this.buffer[(this.head - 1 + this.capacity) % this.capacity];
  }

  oldest() {
    return this.count === 0 ? null : this.get(0);
  }

  findBracket(timestamp) {
    if (this.count === 0) return [-1, -1];
    if (this.count === 1) return [0, 0];

    const oldest = this.get(0);
    const newest = this.get(this.count - 1);
    if (!oldest || !newest) return [-1, -1];

    if (timestamp <= oldest.timestamp) return [0, 0];
    if (timestamp >= newest.timestamp) return [this.count - 1, this.count - 1];

    let left = 0, right = this.count - 1;
    while (left < right - 1) {
      const mid = Math.floor((left + right) / 2);
      const midItem = this.get(mid);
      if (!midItem) break;
      if (midItem.timestamp <= timestamp) {
        left = mid;
      } else {
        right = mid;
      }
    }
    return [left, right];
  }

  size() { return this.count; }

  clear() {
    this.buffer = new Array(this.capacity).fill(null);
    this.head = 0;
    this.count = 0;
  }

  getTimeSpan() {
    const oldest = this.oldest();
    const newest = this.newest();
    if (!oldest || !newest) return null;
    return {
      start: oldest.timestamp,
      end: newest.timestamp,
      duration: newest.timestamp - oldest.timestamp
    };
  }
}

// ============================================================================
// TimeBinder - Phase-Lock Synchronization
// ============================================================================

export class TimeBinder {
  constructor(config = {}) {
    this.config = {
      bufferSize: config.bufferSize ?? 1000,
      latencyBuffer: config.latencyBuffer ?? 50,
      maxInterpolationGap: config.maxInterpolationGap ?? 500,
      rotationScale: config.rotationScale ?? 0.001
    };

    this.tickBuffer = new RingBuffer(this.config.bufferSize);
    this.sequenceCounter = 0;
    this.subscribers = new Set();
    this.rotationAccumulators = { XY: 0, XZ: 0, XW: 0, YZ: 0, YW: 0, ZW: 0 };

    this.metrics = {
      totalTicks: 0,
      totalFrames: 0,
      interpolatedFrames: 0,
      exactHits: 0,
      missedFrames: 0,
      avgLatency: 0,
      latencySum: 0
    };
  }

  // Ingest market tick
  ingestTick(data) {
    const now = performance.now();

    const priceVector = {
      price: data.price,
      volume: data.volume ?? 0,
      bid: data.bid ?? data.price,
      ask: data.ask ?? data.price,
      spread: (data.ask ?? data.price) - (data.bid ?? data.price),
      momentum: this._computeMomentum(data.price),
      volatility: this._computeVolatility(data.price),
      channels: data.channels ?? []
    };

    const rotation = this._computeRotation(priceVector);

    const tick = {
      timestamp: now,
      sequence: this.sequenceCounter++,
      priceVector,
      rotation,
      latency: data.apiLatency ?? 0
    };

    this.tickBuffer.push(tick);
    this._updateMetrics(tick);

    return tick;
  }

  // Ingest pre-formed tick (for testing/playback)
  ingestRawTick(tick) {
    this.tickBuffer.push(tick);
    this.metrics.totalTicks++;
  }

  // Get synchronized frame (THE PHASE LOCK)
  getSyncedFrame(timestamp) {
    const targetTime = timestamp - this.config.latencyBuffer;
    this.metrics.totalFrames++;

    const [lowerIdx, upperIdx] = this.tickBuffer.findBracket(targetTime);

    if (lowerIdx === -1) {
      this.metrics.missedFrames++;
      return this._createEmptyFrame(timestamp);
    }

    const tickA = this.tickBuffer.get(lowerIdx);
    const tickB = this.tickBuffer.get(upperIdx);

    if (!tickA) {
      this.metrics.missedFrames++;
      return this._createEmptyFrame(timestamp);
    }

    // Exact match or single tick
    if (lowerIdx === upperIdx || !tickB) {
      this.metrics.exactHits++;
      return {
        timestamp,
        priceVector: { ...tickA.priceVector },
        rotation: { ...tickA.rotation },
        interpolationFactor: 0,
        tickA,
        tickB: null,
        phaseOffset: targetTime - tickA.timestamp,
        isExact: true
      };
    }

    // Check if target exactly matches tickA
    if (targetTime === tickA.timestamp) {
      this.metrics.exactHits++;
      return {
        timestamp,
        priceVector: { ...tickA.priceVector },
        rotation: { ...tickA.rotation },
        interpolationFactor: 0,
        tickA,
        tickB,
        phaseOffset: 0,
        isExact: true
      };
    }

    const gap = tickB.timestamp - tickA.timestamp;

    // Large gap - snap to nearest
    if (gap > this.config.maxInterpolationGap) {
      const useB = (targetTime - tickA.timestamp) > (tickB.timestamp - targetTime);
      const nearest = useB ? tickB : tickA;
      return {
        timestamp,
        priceVector: { ...nearest.priceVector },
        rotation: { ...nearest.rotation },
        interpolationFactor: useB ? 1 : 0,
        tickA,
        tickB,
        phaseOffset: targetTime - nearest.timestamp,
        isExact: false
      };
    }

    // Interpolate
    const t = (targetTime - tickA.timestamp) / gap;
    this.metrics.interpolatedFrames++;

    return {
      timestamp,
      priceVector: this._lerpPriceVector(tickA.priceVector, tickB.priceVector, t),
      rotation: this._lerpRotation(tickA.rotation, tickB.rotation, t),
      interpolationFactor: t,
      tickA,
      tickB,
      phaseOffset: 0,
      isExact: false
    };
  }

  // Seek to historical timestamp
  seek(timestamp) {
    const [lowerIdx, upperIdx] = this.tickBuffer.findBracket(timestamp);

    if (lowerIdx === -1) return this._createEmptyFrame(timestamp);

    const tickA = this.tickBuffer.get(lowerIdx);
    const tickB = this.tickBuffer.get(upperIdx);

    if (!tickA) return this._createEmptyFrame(timestamp);

    if (lowerIdx === upperIdx || !tickB) {
      return {
        timestamp,
        priceVector: { ...tickA.priceVector },
        rotation: { ...tickA.rotation },
        interpolationFactor: 0,
        tickA,
        tickB: null,
        phaseOffset: timestamp - tickA.timestamp,
        isExact: true
      };
    }

    if (timestamp === tickA.timestamp) {
      return {
        timestamp,
        priceVector: { ...tickA.priceVector },
        rotation: { ...tickA.rotation },
        interpolationFactor: 0,
        tickA,
        tickB,
        phaseOffset: 0,
        isExact: true
      };
    }

    const gap = tickB.timestamp - tickA.timestamp;
    const t = Math.max(0, Math.min(1, (timestamp - tickA.timestamp) / gap));

    return {
      timestamp,
      priceVector: this._lerpPriceVector(tickA.priceVector, tickB.priceVector, t),
      rotation: this._lerpRotation(tickA.rotation, tickB.rotation, t),
      interpolationFactor: t,
      tickA,
      tickB,
      phaseOffset: 0,
      isExact: false
    };
  }

  // Subscribe to frame updates
  subscribe(callback) {
    this.subscribers.add(callback);
    return () => this.subscribers.delete(callback);
  }

  dispatchFrame(frame) {
    this.subscribers.forEach(cb => cb(frame));
  }

  getMetrics() {
    const total = this.metrics.totalFrames || 1;
    return {
      ...this.metrics,
      bufferSize: this.tickBuffer.size(),
      timeSpan: this.tickBuffer.getTimeSpan(),
      interpolationRate: this.metrics.interpolatedFrames / total,
      hitRate: this.metrics.exactHits / total
    };
  }

  setLatencyBuffer(ms) {
    this.config.latencyBuffer = Math.max(0, ms);
  }

  clear() {
    this.tickBuffer.clear();
    this.sequenceCounter = 0;
    this.metrics = {
      totalTicks: 0, totalFrames: 0, interpolatedFrames: 0,
      exactHits: 0, missedFrames: 0, avgLatency: 0, latencySum: 0
    };
  }

  // Private helpers
  _computeMomentum(currentPrice) {
    const newest = this.tickBuffer.newest();
    return newest ? currentPrice - newest.priceVector.price : 0;
  }

  _computeVolatility(currentPrice) {
    const samples = [];
    const size = Math.min(20, this.tickBuffer.size());
    for (let i = this.tickBuffer.size() - size; i < this.tickBuffer.size(); i++) {
      const tick = this.tickBuffer.get(i);
      if (tick) samples.push(tick.priceVector.price);
    }
    samples.push(currentPrice);
    if (samples.length < 2) return 0;
    const mean = samples.reduce((a, b) => a + b, 0) / samples.length;
    const variance = samples.reduce((sum, x) => sum + Math.pow(x - mean, 2), 0) / samples.length;
    return Math.sqrt(variance);
  }

  _computeRotation(pv) {
    const scale = this.config.rotationScale;
    return {
      rotXY: this._accumulatedRotation('XY', pv.momentum * scale * 10),
      rotXZ: this._accumulatedRotation('XZ', Math.log1p(pv.volume) * scale),
      rotXW: this._accumulatedRotation('XW', pv.spread * scale * 5),
      rotYZ: this._accumulatedRotation('YZ', (pv.bid - pv.price) * scale * 3),
      rotYW: this._accumulatedRotation('YW', (pv.ask - pv.price) * scale * 3),
      rotZW: this._accumulatedRotation('ZW', pv.volatility * scale * 2)
    };
  }

  _accumulatedRotation(plane, delta) {
    this.rotationAccumulators[plane] = (this.rotationAccumulators[plane] + delta) % (Math.PI * 2);
    return this.rotationAccumulators[plane];
  }

  _lerpPriceVector(a, b, t) {
    const lerp = (x, y) => x + (y - x) * t;
    return {
      price: lerp(a.price, b.price),
      volume: lerp(a.volume, b.volume),
      bid: lerp(a.bid, b.bid),
      ask: lerp(a.ask, b.ask),
      spread: lerp(a.spread, b.spread),
      momentum: lerp(a.momentum, b.momentum),
      volatility: lerp(a.volatility, b.volatility),
      channels: a.channels.map((v, i) => lerp(v, b.channels[i] ?? v))
    };
  }

  _lerpRotation(a, b, t) {
    const lerp = (x, y) => x + (y - x) * t;
    return {
      rotXY: lerp(a.rotXY, b.rotXY),
      rotXZ: lerp(a.rotXZ, b.rotXZ),
      rotXW: lerp(a.rotXW, b.rotXW),
      rotYZ: lerp(a.rotYZ, b.rotYZ),
      rotYW: lerp(a.rotYW, b.rotYW),
      rotZW: lerp(a.rotZW, b.rotZW)
    };
  }

  _updateMetrics(tick) {
    this.metrics.totalTicks++;
    this.metrics.latencySum += tick.latency;
    this.metrics.avgLatency = this.metrics.latencySum / this.metrics.totalTicks;
  }

  _createEmptyFrame(timestamp) {
    return {
      timestamp,
      priceVector: {
        price: 0, volume: 0, bid: 0, ask: 0,
        spread: 0, momentum: 0, volatility: 0, channels: []
      },
      rotation: { rotXY: 0, rotXZ: 0, rotXW: 0, rotYZ: 0, rotYW: 0, rotZW: 0 },
      interpolationFactor: 0,
      tickA: null,
      tickB: null,
      phaseOffset: 0,
      isExact: false
    };
  }
}

// ============================================================================
// Quaternion - For SLERP interpolation
// ============================================================================

export class Quaternion {
  constructor(w = 1, x = 0, y = 0, z = 0) {
    this.w = w;
    this.x = x;
    this.y = y;
    this.z = z;
  }

  static identity() { return new Quaternion(1, 0, 0, 0); }

  static fromAxisAngle(axis, angle) {
    const halfAngle = angle / 2;
    const s = Math.sin(halfAngle);
    const len = Math.sqrt(axis[0]**2 + axis[1]**2 + axis[2]**2) || 1;
    return new Quaternion(
      Math.cos(halfAngle),
      (axis[0] / len) * s,
      (axis[1] / len) * s,
      (axis[2] / len) * s
    );
  }

  static fromEuler(roll, pitch, yaw) {
    const cr = Math.cos(roll / 2), sr = Math.sin(roll / 2);
    const cp = Math.cos(pitch / 2), sp = Math.sin(pitch / 2);
    const cy = Math.cos(yaw / 2), sy = Math.sin(yaw / 2);
    return new Quaternion(
      cr * cp * cy + sr * sp * sy,
      sr * cp * cy - cr * sp * sy,
      cr * sp * cy + sr * cp * sy,
      cr * cp * sy - sr * sp * cy
    );
  }

  magnitude() {
    return Math.sqrt(this.w**2 + this.x**2 + this.y**2 + this.z**2);
  }

  normalize() {
    const mag = this.magnitude();
    if (mag < 1e-10) return Quaternion.identity();
    return new Quaternion(this.w / mag, this.x / mag, this.y / mag, this.z / mag);
  }

  dot(q) {
    return this.w * q.w + this.x * q.x + this.y * q.y + this.z * q.z;
  }

  multiply(q) {
    return new Quaternion(
      this.w * q.w - this.x * q.x - this.y * q.y - this.z * q.z,
      this.w * q.x + this.x * q.w + this.y * q.z - this.z * q.y,
      this.w * q.y - this.x * q.z + this.y * q.w + this.z * q.x,
      this.w * q.z + this.x * q.y - this.y * q.x + this.z * q.w
    );
  }

  toEuler() {
    const sinr_cosp = 2 * (this.w * this.x + this.y * this.z);
    const cosr_cosp = 1 - 2 * (this.x**2 + this.y**2);
    const roll = Math.atan2(sinr_cosp, cosr_cosp);

    const sinp = 2 * (this.w * this.y - this.z * this.x);
    const pitch = Math.abs(sinp) >= 1 ? Math.sign(sinp) * Math.PI / 2 : Math.asin(sinp);

    const siny_cosp = 2 * (this.w * this.z + this.x * this.y);
    const cosy_cosp = 1 - 2 * (this.y**2 + this.z**2);
    const yaw = Math.atan2(siny_cosp, cosy_cosp);

    return [roll, pitch, yaw];
  }
}

// SLERP - Spherical Linear Interpolation
export function slerp(q0, q1, t) {
  t = Math.max(0, Math.min(1, t));
  const a = q0.normalize();
  let b = q1.normalize();

  let dot = a.dot(b);
  if (dot < 0) {
    b = new Quaternion(-b.w, -b.x, -b.y, -b.z);
    dot = -dot;
  }

  if (dot > 0.9995) {
    return new Quaternion(
      a.w + t * (b.w - a.w),
      a.x + t * (b.x - a.x),
      a.y + t * (b.y - a.y),
      a.z + t * (b.z - a.z)
    ).normalize();
  }

  const theta_0 = Math.acos(dot);
  const theta = theta_0 * t;
  const sin_theta = Math.sin(theta);
  const sin_theta_0 = Math.sin(theta_0);

  const s0 = Math.cos(theta) - dot * sin_theta / sin_theta_0;
  const s1 = sin_theta / sin_theta_0;

  return new Quaternion(
    s0 * a.w + s1 * b.w,
    s0 * a.x + s1 * b.x,
    s0 * a.y + s1 * b.y,
    s0 * a.z + s1 * b.z
  ).normalize();
}

// ============================================================================
// GeometricLerp - Smooth 4D rotation interpolation
// ============================================================================

export class GeometricLerp {
  constructor(maxKeyframes = 100) {
    this.keyframes = [];
    this.maxKeyframes = maxKeyframes;
  }

  addKeyframe(data) {
    const insertIndex = this.keyframes.findIndex(k => k.timestamp > data.timestamp);
    if (insertIndex === -1) {
      this.keyframes.push(data);
    } else {
      this.keyframes.splice(insertIndex, 0, data);
    }
    while (this.keyframes.length > this.maxKeyframes) {
      this.keyframes.shift();
    }
  }

  addFromTick(tick) {
    this.addKeyframe({ timestamp: tick.timestamp, rotation: tick.rotation, tick });
  }

  getState(timestamp) {
    if (this.keyframes.length === 0) return this._createEmptyState(timestamp);

    if (this.keyframes.length === 1) {
      const k = this.keyframes[0];
      return {
        timestamp,
        rotation: { ...k.rotation },
        interpolationFactor: 0,
        keyframeA: k,
        keyframeB: null
      };
    }

    const [kA, kB] = this._findBracket(timestamp);
    if (!kA) return this._createEmptyState(timestamp);

    if (!kB || timestamp === kA.timestamp) {
      return {
        timestamp,
        rotation: { ...kA.rotation },
        interpolationFactor: 0,
        keyframeA: kA,
        keyframeB: kB
      };
    }

    const duration = kB.timestamp - kA.timestamp;
    const t = duration > 0 ? Math.max(0, Math.min(1, (timestamp - kA.timestamp) / duration)) : 0;

    // SLERP interpolation via quaternions
    const qA = Quaternion.fromEuler(kA.rotation.rotXY, kA.rotation.rotXZ, kA.rotation.rotYZ);
    const qB = Quaternion.fromEuler(kB.rotation.rotXY, kB.rotation.rotXZ, kB.rotation.rotYZ);
    const qInterp = slerp(qA, qB, t);
    const [rotXY, rotXZ, rotYZ] = qInterp.toEuler();

    // Linear interpolation for W-plane rotations
    const lerp = (a, b) => a + (b - a) * t;

    return {
      timestamp,
      rotation: {
        rotXY, rotXZ, rotYZ,
        rotXW: lerp(kA.rotation.rotXW, kB.rotation.rotXW),
        rotYW: lerp(kA.rotation.rotYW, kB.rotation.rotYW),
        rotZW: lerp(kA.rotation.rotZW, kB.rotation.rotZW)
      },
      interpolationFactor: t,
      keyframeA: kA,
      keyframeB: kB
    };
  }

  smoothFrame(frame) {
    if (frame.tickA) this.addFromTick(frame.tickA);
    if (frame.tickB) this.addFromTick(frame.tickB);
    const state = this.getState(frame.timestamp);
    return { ...frame, rotation: state.rotation };
  }

  clear() {
    this.keyframes = [];
  }

  _findBracket(timestamp) {
    if (this.keyframes.length === 0) return [null, null];
    const first = this.keyframes[0];
    const last = this.keyframes[this.keyframes.length - 1];

    if (timestamp <= first.timestamp) return [first, this.keyframes[1] || null];
    if (timestamp >= last.timestamp) return [last, null];

    let left = 0, right = this.keyframes.length - 1;
    while (left < right - 1) {
      const mid = Math.floor((left + right) / 2);
      if (this.keyframes[mid].timestamp <= timestamp) {
        left = mid;
      } else {
        right = mid;
      }
    }
    return [this.keyframes[left], this.keyframes[right]];
  }

  _createEmptyState(timestamp) {
    return {
      timestamp,
      rotation: { rotXY: 0, rotXZ: 0, rotXW: 0, rotYZ: 0, rotYW: 0, rotZW: 0 },
      interpolationFactor: 0,
      keyframeA: null,
      keyframeB: null
    };
  }
}

// ============================================================================
// StereoscopicFeed - Data bifurcation for left/right eye
// ============================================================================

export class StereoscopicFeed {
  constructor(config = {}) {
    this.config = {
      smoothing: config.smoothing ?? true,
      chartHistorySize: config.chartHistorySize ?? 1000,
      latencyBuffer: config.timeBinder?.latencyBuffer ?? 50
    };

    this.timeBinder = new TimeBinder({
      bufferSize: config.timeBinder?.bufferSize ?? 1000,
      latencyBuffer: this.config.latencyBuffer,
      maxInterpolationGap: config.timeBinder?.maxInterpolationGap ?? 500
    });

    this.geometricLerp = new GeometricLerp(100);
    this.chartHistory = [];
    this.listeners = {};
    this.metrics = {
      ticksReceived: 0,
      framesRendered: 0,
      seekEvents: 0
    };
  }

  // Ingest market tick
  ingest(raw) {
    const tick = this.timeBinder.ingestTick(raw);
    this.geometricLerp.addFromTick(tick);

    const chartPoint = {
      timestamp: tick.timestamp,
      price: tick.priceVector.price,
      volume: tick.priceVector.volume,
      bid: tick.priceVector.bid,
      ask: tick.priceVector.ask
    };

    this.chartHistory.push(chartPoint);
    while (this.chartHistory.length > this.config.chartHistorySize) {
      this.chartHistory.shift();
    }

    this.metrics.ticksReceived++;
    this._emit('tick', raw);
    this._emit('chart', chartPoint);

    return tick;
  }

  // Request stereoscopic frame
  frame(timestamp) {
    const now = timestamp ?? performance.now();
    const syncedFrame = this.timeBinder.getSyncedFrame(now);
    const smoothedFrame = this.config.smoothing
      ? this.geometricLerp.smoothFrame(syncedFrame)
      : syncedFrame;

    const chartPoint = this._getChartPointAt(now);

    const frame = {
      timestamp: now,
      leftEye: chartPoint,
      rightEye: {
        timestamp: now,
        priceVector: smoothedFrame.priceVector,
        smoothedRotation: smoothedFrame.rotation
      },
      phaseOffset: smoothedFrame.phaseOffset,
      interpolation: smoothedFrame.interpolationFactor
    };

    this.metrics.framesRendered++;
    this._emit('frame', frame);
    return frame;
  }

  // Seek to historical timestamp (crosshair sync)
  seek(timestamp) {
    this.metrics.seekEvents++;
    const seekedFrame = this.timeBinder.seek(timestamp);
    const smoothedFrame = this.config.smoothing
      ? this.geometricLerp.smoothFrame(seekedFrame)
      : seekedFrame;

    this._emit('seek', { timestamp, source: 'external' });

    return {
      timestamp,
      priceVector: smoothedFrame.priceVector,
      smoothedRotation: smoothedFrame.rotation
    };
  }

  // Event subscription
  on(event, callback) {
    if (!this.listeners[event]) this.listeners[event] = [];
    this.listeners[event].push(callback);
    return () => {
      this.listeners[event] = this.listeners[event].filter(cb => cb !== callback);
    };
  }

  _emit(event, data) {
    (this.listeners[event] || []).forEach(cb => cb(data));
  }

  _getChartPointAt(timestamp) {
    if (this.chartHistory.length === 0) {
      return { timestamp, price: 0, volume: 0, bid: 0, ask: 0 };
    }
    // Find closest
    let closest = this.chartHistory[0];
    let minDiff = Math.abs(closest.timestamp - timestamp);
    for (const point of this.chartHistory) {
      const diff = Math.abs(point.timestamp - timestamp);
      if (diff < minDiff) {
        minDiff = diff;
        closest = point;
      }
    }
    return closest;
  }

  getTimeBinder() { return this.timeBinder; }
  getChartHistory() { return [...this.chartHistory]; }
  getMetrics() {
    return {
      ...this.metrics,
      timeBinderMetrics: this.timeBinder.getMetrics()
    };
  }

  clear() {
    this.timeBinder.clear();
    this.geometricLerp.clear();
    this.chartHistory = [];
    this.metrics = { ticksReceived: 0, framesRendered: 0, seekEvents: 0 };
  }
}

// ============================================================================
// Global singleton
// ============================================================================

let globalFeed = null;

export function getStereoscopicFeed(config) {
  if (!globalFeed) {
    globalFeed = new StereoscopicFeed(config);
  }
  return globalFeed;
}

export function resetStereoscopicFeed() {
  globalFeed?.clear();
  globalFeed = null;
}

// Export for PPP global
if (typeof window !== 'undefined') {
  window.PhaseLockEngine = {
    RingBuffer,
    TimeBinder,
    Quaternion,
    slerp,
    GeometricLerp,
    StereoscopicFeed,
    getStereoscopicFeed,
    resetStereoscopicFeed
  };
}

/**
 * TimeBinder.ts - Phase-Locked Temporal Synchronization System
 *
 * The "Loom" that binds real-time market data streams to high-frame-rate
 * geometric projections on a unified, millisecond-perfect timeline.
 *
 * Problem Solved:
 * - Market API ticks arrive at irregular intervals (Tick T)
 * - Animation loop runs at 60+ FPS (Frame F)
 * - Without phase-locking, rendering Frame F before/after Tick T creates
 *   lag artifacts (false Moiré patterns)
 *
 * Solution:
 * - Maintain a RingBuffer of historical ticks
 * - Render at `Now - LatencyBuffer` instead of "latest"
 * - Interpolate between keyframes for smooth 4D rotation
 */

// ============================================================================
// Type Definitions
// ============================================================================

/**
 * 4D Rotation state using 6 independent rotation planes
 * (XY, XZ, XW, YZ, YW, ZW) - Matches shader uniforms
 */
export interface GeometricRotation {
  rotXY: number;
  rotXZ: number;
  rotXW: number;
  rotYZ: number;
  rotYW: number;
  rotZW: number;
}

/**
 * Price vector from market data - multi-dimensional market state
 */
export interface PriceVector {
  price: number;
  volume: number;
  bid: number;
  ask: number;
  spread: number;
  momentum: number;      // Derived: price delta
  volatility: number;    // Derived: rolling std dev
  channels: number[];    // Additional data channels (up to 32)
}

/**
 * A single market tick with timestamp and derived geometry
 */
export interface MarketTick {
  timestamp: number;           // Performance.now() when received
  sequence: number;            // Monotonic tick sequence number
  priceVector: PriceVector;
  rotation: GeometricRotation; // Computed 4D rotation from price dynamics
  latency: number;             // API latency measurement (ms)
}

/**
 * Synchronized frame output - the unified render state
 */
export interface SyncedFrame {
  timestamp: number;
  priceVector: PriceVector;
  rotation: GeometricRotation;
  interpolationFactor: number; // 0-1, how much interpolation was applied
  tickA: MarketTick | null;    // Lower bound tick
  tickB: MarketTick | null;    // Upper bound tick
  phaseOffset: number;         // Milliseconds offset from target
  isExact: boolean;            // True if exact tick match
}

/**
 * Configuration for the TimeBinder
 */
export interface TimeBinderConfig {
  bufferSize: number;          // Ring buffer capacity (default: 1000)
  latencyBuffer: number;       // Render delay in ms (default: 50)
  maxInterpolationGap: number; // Max ms between ticks for interpolation
  rotationScale: number;       // Scale factor for price->rotation mapping
}

// ============================================================================
// RingBuffer Implementation
// ============================================================================

/**
 * Lock-free ring buffer for O(1) insertion and O(log n) temporal lookup
 */
export class RingBuffer<T extends { timestamp: number }> {
  private buffer: (T | null)[];
  private head: number = 0;
  private count: number = 0;
  private readonly capacity: number;

  constructor(capacity: number) {
    this.capacity = capacity;
    this.buffer = new Array(capacity).fill(null);
  }

  /**
   * Push a new item, overwriting oldest if at capacity
   */
  push(item: T): void {
    this.buffer[this.head] = item;
    this.head = (this.head + 1) % this.capacity;
    if (this.count < this.capacity) {
      this.count++;
    }
  }

  /**
   * Get item at logical index (0 = oldest, count-1 = newest)
   */
  get(index: number): T | null {
    if (index < 0 || index >= this.count) {
      return null;
    }
    const physicalIndex = (this.head - this.count + index + this.capacity) % this.capacity;
    return this.buffer[physicalIndex];
  }

  /**
   * Get the most recent item
   */
  newest(): T | null {
    if (this.count === 0) return null;
    const index = (this.head - 1 + this.capacity) % this.capacity;
    return this.buffer[index];
  }

  /**
   * Get the oldest item
   */
  oldest(): T | null {
    if (this.count === 0) return null;
    return this.get(0);
  }

  /**
   * Binary search for tick at or before timestamp
   * Returns [lowerIndex, upperIndex] for interpolation
   */
  findBracket(timestamp: number): [number, number] {
    if (this.count === 0) return [-1, -1];
    if (this.count === 1) return [0, 0];

    const oldest = this.get(0);
    const newest = this.get(this.count - 1);

    if (!oldest || !newest) return [-1, -1];

    // Bounds check
    if (timestamp <= oldest.timestamp) return [0, 0];
    if (timestamp >= newest.timestamp) return [this.count - 1, this.count - 1];

    // Binary search for lower bound
    let left = 0;
    let right = this.count - 1;

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

  /**
   * Get all items in chronological order
   */
  toArray(): T[] {
    const result: T[] = [];
    for (let i = 0; i < this.count; i++) {
      const item = this.get(i);
      if (item) result.push(item);
    }
    return result;
  }

  /**
   * Current item count
   */
  size(): number {
    return this.count;
  }

  /**
   * Clear all items
   */
  clear(): void {
    this.buffer = new Array(this.capacity).fill(null);
    this.head = 0;
    this.count = 0;
  }

  /**
   * Get time span of buffered data
   */
  getTimeSpan(): { start: number; end: number; duration: number } | null {
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
// TimeBinder Core Class
// ============================================================================

/**
 * TimeBinder - The Temporal Loom
 *
 * Synchronizes market data ingestion with animation frame requests
 * using phase-locked rendering at `Now - LatencyBuffer`
 */
export class TimeBinder {
  private tickBuffer: RingBuffer<MarketTick>;
  private config: TimeBinderConfig;
  private sequenceCounter: number = 0;
  private lastFrameTime: number = 0;
  private subscribers: Set<(frame: SyncedFrame) => void> = new Set();

  // Metrics
  private metrics = {
    totalTicks: 0,
    totalFrames: 0,
    interpolatedFrames: 0,
    exactHits: 0,
    missedFrames: 0,
    avgLatency: 0,
    latencySum: 0
  };

  constructor(config: Partial<TimeBinderConfig> = {}) {
    this.config = {
      bufferSize: config.bufferSize ?? 1000,
      latencyBuffer: config.latencyBuffer ?? 50,
      maxInterpolationGap: config.maxInterpolationGap ?? 500,
      rotationScale: config.rotationScale ?? 0.001
    };

    this.tickBuffer = new RingBuffer<MarketTick>(this.config.bufferSize);
  }

  // ==========================================================================
  // Public API: Ingestion
  // ==========================================================================

  /**
   * Ingest a new market tick from API
   * Automatically stamps with Performance.now() and computes geometry
   */
  ingestTick(data: {
    price: number;
    volume?: number;
    bid?: number;
    ask?: number;
    channels?: number[];
    apiLatency?: number;
  }): MarketTick {
    const now = typeof performance !== 'undefined' ? performance.now() : Date.now();

    // Build price vector with defaults
    const priceVector: PriceVector = {
      price: data.price,
      volume: data.volume ?? 0,
      bid: data.bid ?? data.price,
      ask: data.ask ?? data.price,
      spread: (data.ask ?? data.price) - (data.bid ?? data.price),
      momentum: this.computeMomentum(data.price),
      volatility: this.computeVolatility(data.price),
      channels: data.channels ?? []
    };

    // Derive 4D rotation from price dynamics
    const rotation = this.computeRotation(priceVector);

    const tick: MarketTick = {
      timestamp: now,
      sequence: this.sequenceCounter++,
      priceVector,
      rotation,
      latency: data.apiLatency ?? 0
    };

    this.tickBuffer.push(tick);
    this.updateMetrics(tick);

    return tick;
  }

  /**
   * Ingest a pre-formed tick (for playback/testing)
   */
  ingestRawTick(tick: MarketTick): void {
    this.tickBuffer.push(tick);
    this.metrics.totalTicks++;
  }

  // ==========================================================================
  // Public API: Frame Synchronization (The Phase Lock)
  // ==========================================================================

  /**
   * Get the synchronized frame for a specific timestamp
   * This is the core phase-lock operation
   *
   * @param timestamp The target render timestamp (typically from requestAnimationFrame)
   * @returns SyncedFrame with interpolated price and rotation data
   */
  getSyncedFrame(timestamp: number): SyncedFrame {
    // Apply latency buffer - render in the past for stability
    const targetTime = timestamp - this.config.latencyBuffer;

    this.metrics.totalFrames++;
    this.lastFrameTime = timestamp;

    // Find bracketing ticks
    const [lowerIdx, upperIdx] = this.tickBuffer.findBracket(targetTime);

    if (lowerIdx === -1) {
      // No data yet - return empty frame
      this.metrics.missedFrames++;
      return this.createEmptyFrame(timestamp);
    }

    const tickA = this.tickBuffer.get(lowerIdx);
    const tickB = this.tickBuffer.get(upperIdx);

    if (!tickA) {
      this.metrics.missedFrames++;
      return this.createEmptyFrame(timestamp);
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

    // Check if target exactly matches tickA's timestamp (exact hit in middle of buffer)
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

    // Interpolation needed
    const gap = tickB.timestamp - tickA.timestamp;

    // Check if gap is too large for meaningful interpolation
    if (gap > this.config.maxInterpolationGap) {
      // Use nearest tick instead
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

    // Compute interpolation factor (0 = tickA, 1 = tickB)
    const t = (targetTime - tickA.timestamp) / gap;
    this.metrics.interpolatedFrames++;

    // Interpolate price vector
    const priceVector = this.lerpPriceVector(tickA.priceVector, tickB.priceVector, t);

    // Note: Rotation interpolation uses SLERP in GeometricLerp.ts
    // Here we use simple lerp as a fallback
    const rotation = this.lerpRotation(tickA.rotation, tickB.rotation, t);

    return {
      timestamp,
      priceVector,
      rotation,
      interpolationFactor: t,
      tickA,
      tickB,
      phaseOffset: 0, // Perfect interpolation
      isExact: false
    };
  }

  /**
   * Seek to a specific historical moment
   * Used when chart crosshair moves to a past timestamp
   */
  seek(timestamp: number): SyncedFrame {
    // Seek doesn't apply latency buffer - we want the exact historical moment
    const [lowerIdx, upperIdx] = this.tickBuffer.findBracket(timestamp);

    if (lowerIdx === -1) {
      return this.createEmptyFrame(timestamp);
    }

    const tickA = this.tickBuffer.get(lowerIdx);
    const tickB = this.tickBuffer.get(upperIdx);

    if (!tickA) {
      return this.createEmptyFrame(timestamp);
    }

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

    // Check if timestamp exactly matches tickA (exact hit in middle of buffer)
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
      priceVector: this.lerpPriceVector(tickA.priceVector, tickB.priceVector, t),
      rotation: this.lerpRotation(tickA.rotation, tickB.rotation, t),
      interpolationFactor: t,
      tickA,
      tickB,
      phaseOffset: 0,
      isExact: false
    };
  }

  // ==========================================================================
  // Public API: Subscription
  // ==========================================================================

  /**
   * Subscribe to frame updates
   */
  subscribe(callback: (frame: SyncedFrame) => void): () => void {
    this.subscribers.add(callback);
    return () => this.subscribers.delete(callback);
  }

  /**
   * Dispatch a synced frame to all subscribers
   */
  dispatchFrame(frame: SyncedFrame): void {
    this.subscribers.forEach(cb => cb(frame));
  }

  // ==========================================================================
  // Public API: Configuration & Metrics
  // ==========================================================================

  /**
   * Get current configuration
   */
  getConfig(): Readonly<TimeBinderConfig> {
    return { ...this.config };
  }

  /**
   * Update configuration
   */
  setConfig(updates: Partial<TimeBinderConfig>): void {
    Object.assign(this.config, updates);
  }

  /**
   * Set the latency buffer (render delay)
   */
  setLatencyBuffer(ms: number): void {
    this.config.latencyBuffer = Math.max(0, ms);
  }

  /**
   * Get synchronization metrics
   */
  getMetrics(): typeof this.metrics & {
    bufferSize: number;
    timeSpan: { start: number; end: number; duration: number } | null;
    interpolationRate: number;
    hitRate: number;
  } {
    const total = this.metrics.totalFrames || 1;
    return {
      ...this.metrics,
      bufferSize: this.tickBuffer.size(),
      timeSpan: this.tickBuffer.getTimeSpan(),
      interpolationRate: this.metrics.interpolatedFrames / total,
      hitRate: this.metrics.exactHits / total
    };
  }

  /**
   * Get the tick buffer for external access
   */
  getBuffer(): RingBuffer<MarketTick> {
    return this.tickBuffer;
  }

  /**
   * Clear all buffered data
   */
  clear(): void {
    this.tickBuffer.clear();
    this.sequenceCounter = 0;
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

  // ==========================================================================
  // Private: Computation Helpers
  // ==========================================================================

  private computeMomentum(currentPrice: number): number {
    const newest = this.tickBuffer.newest();
    if (!newest) return 0;
    return currentPrice - newest.priceVector.price;
  }

  private computeVolatility(currentPrice: number): number {
    // Simple rolling standard deviation over last 20 ticks
    const samples: number[] = [];
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

  /**
   * Map price dynamics to 4D rotation
   * Each rotation plane is driven by different market aspects
   */
  private computeRotation(pv: PriceVector): GeometricRotation {
    const scale = this.config.rotationScale;

    return {
      // XY: Primary price movement (accumulated)
      rotXY: this.accumulatedRotation('XY', pv.momentum * scale * 10),
      // XZ: Volume-weighted rotation
      rotXZ: this.accumulatedRotation('XZ', Math.log1p(pv.volume) * scale),
      // XW: Spread dynamics (into 4th dimension)
      rotXW: this.accumulatedRotation('XW', pv.spread * scale * 5),
      // YZ: Bid pressure
      rotYZ: this.accumulatedRotation('YZ', (pv.bid - pv.price) * scale * 3),
      // YW: Ask pressure
      rotYW: this.accumulatedRotation('YW', (pv.ask - pv.price) * scale * 3),
      // ZW: Volatility vortex
      rotZW: this.accumulatedRotation('ZW', pv.volatility * scale * 2)
    };
  }

  private rotationAccumulators: Record<string, number> = {
    XY: 0, XZ: 0, XW: 0, YZ: 0, YW: 0, ZW: 0
  };

  private accumulatedRotation(plane: string, delta: number): number {
    this.rotationAccumulators[plane] =
      (this.rotationAccumulators[plane] + delta) % (Math.PI * 2);
    return this.rotationAccumulators[plane];
  }

  private lerpPriceVector(a: PriceVector, b: PriceVector, t: number): PriceVector {
    const lerp = (x: number, y: number) => x + (y - x) * t;

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

  private lerpRotation(a: GeometricRotation, b: GeometricRotation, t: number): GeometricRotation {
    // Simple linear interpolation - use GeometricLerp.ts for proper SLERP
    const lerp = (x: number, y: number) => x + (y - x) * t;

    return {
      rotXY: lerp(a.rotXY, b.rotXY),
      rotXZ: lerp(a.rotXZ, b.rotXZ),
      rotXW: lerp(a.rotXW, b.rotXW),
      rotYZ: lerp(a.rotYZ, b.rotYZ),
      rotYW: lerp(a.rotYW, b.rotYW),
      rotZW: lerp(a.rotZW, b.rotZW)
    };
  }

  private updateMetrics(tick: MarketTick): void {
    this.metrics.totalTicks++;
    this.metrics.latencySum += tick.latency;
    this.metrics.avgLatency = this.metrics.latencySum / this.metrics.totalTicks;
  }

  private createEmptyFrame(timestamp: number): SyncedFrame {
    return {
      timestamp,
      priceVector: {
        price: 0,
        volume: 0,
        bid: 0,
        ask: 0,
        spread: 0,
        momentum: 0,
        volatility: 0,
        channels: []
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
// Factory & Singleton
// ============================================================================

let globalTimeBinder: TimeBinder | null = null;

/**
 * Get or create the global TimeBinder instance
 */
export function getTimeBinder(config?: Partial<TimeBinderConfig>): TimeBinder {
  if (!globalTimeBinder) {
    globalTimeBinder = new TimeBinder(config);
  }
  return globalTimeBinder;
}

/**
 * Reset the global TimeBinder (for testing)
 */
export function resetTimeBinder(): void {
  globalTimeBinder = null;
}

export default TimeBinder;

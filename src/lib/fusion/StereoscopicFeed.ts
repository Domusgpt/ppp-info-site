/**
 * StereoscopicFeed.ts - The Stereoscopic Data Prism
 *
 * Bifurcates incoming market data into two synchronized visual streams:
 * - Left Eye: Standard 2D Chart (price over time)
 * - Right Eye: 4D Geometric Projection via TimeBinder → CPE
 *
 * The two views are phase-locked: moving the chart crosshair triggers
 * a TimeBinder.seek() event, snapping the 4D geometry to the exact
 * historical moment of the cursor.
 */

import {
  TimeBinder,
  getTimeBinder,
  type MarketTick,
  type PriceVector,
  type SyncedFrame,
  type TimeBinderConfig
} from '../temporal/TimeBinder';

import {
  GeometricLerp,
  slerpRotation,
  type InterpolatedState
} from '../temporal/GeometricLerp';

// ============================================================================
// Type Definitions
// ============================================================================

/**
 * Raw tick from market API before processing
 */
export interface RawApiTick {
  symbol?: string;
  price: number;
  volume?: number;
  bid?: number;
  ask?: number;
  timestamp?: number;        // API-provided timestamp
  sequence?: number;
  channels?: number[];
}

/**
 * Indexed tick with local timestamp
 */
export interface IndexedTick extends RawApiTick {
  localTimestamp: number;    // Performance.now() when received
  apiLatency: number;        // Difference between local and API timestamp
  sequenceId: number;        // Local sequence number
}

/**
 * Chart data point for the standard 2D chart (Left Eye)
 */
export interface ChartDataPoint {
  timestamp: number;
  price: number;
  volume: number;
  open?: number;
  high?: number;
  low?: number;
  close?: number;
  bid: number;
  ask: number;
}

/**
 * CPE (Chronomorphic Polytopal Engine) render data (Right Eye)
 */
export interface CPERenderData {
  timestamp: number;
  syncedFrame: SyncedFrame;
  interpolatedState: InterpolatedState;
  priceVector: PriceVector;
  smoothedRotation: {
    rotXY: number;
    rotXZ: number;
    rotXW: number;
    rotYZ: number;
    rotYW: number;
    rotZW: number;
  };
}

/**
 * Crosshair event from chart interaction
 */
export interface CrosshairEvent {
  timestamp: number;
  price?: number;
  source: 'chart' | 'cpe' | 'external';
}

/**
 * Stereoscopic frame combining both eyes
 */
export interface StereoscopicFrame {
  timestamp: number;
  leftEye: ChartDataPoint;
  rightEye: CPERenderData;
  phaseOffset: number;       // Sync error between eyes (ms)
  interpolation: number;     // Interpolation factor applied
}

/**
 * Configuration for the StereoscopicFeed
 */
export interface StereoscopicFeedConfig {
  timeBinder: Partial<TimeBinderConfig>;
  smoothing: boolean;        // Enable SLERP smoothing
  chartHistorySize: number;  // Max chart points to retain
  syncTolerance: number;     // Max allowed phase offset (ms)
  ohlcPeriod: number;        // OHLC aggregation period (ms)
}

// ============================================================================
// Event Emitter
// ============================================================================

type EventCallback<T> = (data: T) => void;

class EventEmitter<Events extends Record<string, unknown>> {
  private listeners: Map<keyof Events, Set<EventCallback<unknown>>> = new Map();

  on<K extends keyof Events>(event: K, callback: EventCallback<Events[K]>): () => void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(callback as EventCallback<unknown>);

    return () => this.off(event, callback);
  }

  off<K extends keyof Events>(event: K, callback: EventCallback<Events[K]>): void {
    this.listeners.get(event)?.delete(callback as EventCallback<unknown>);
  }

  emit<K extends keyof Events>(event: K, data: Events[K]): void {
    this.listeners.get(event)?.forEach(cb => cb(data));
  }

  removeAllListeners(): void {
    this.listeners.clear();
  }
}

// ============================================================================
// DataPrism - The Core Bifurcation Engine
// ============================================================================

interface DataPrismEvents {
  'tick': IndexedTick;
  'chart': ChartDataPoint;
  'cpe': CPERenderData;
  'frame': StereoscopicFrame;
  'seek': CrosshairEvent;
  'sync-error': { offset: number; timestamp: number };
}

/**
 * DataPrism - Splits and transforms incoming market data
 *
 * Flow:
 * 1. INGEST: Receive raw tick from API
 * 2. INDEX: Stamp with Performance.now()
 * 3. DISPATCH: Send to StandardChart (Left Eye)
 * 4. TRANSFORM: Send to TimeBinder → CPE (Right Eye)
 * 5. SYNCHRONIZE: Crosshair triggers seek across views
 */
export class DataPrism extends EventEmitter<DataPrismEvents> {
  private timeBinder: TimeBinder;
  private geometricLerp: GeometricLerp;
  private config: StereoscopicFeedConfig;

  // Chart history (Left Eye)
  private chartHistory: ChartDataPoint[] = [];
  private ohlcAccumulator: {
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
    periodStart: number;
  } | null = null;

  // Sequence tracking
  private sequenceCounter: number = 0;
  private lastCrosshairTimestamp: number = 0;

  // Animation frame tracking
  private animationFrameId: number | null = null;
  private isRunning: boolean = false;

  // Metrics
  private metrics = {
    ticksReceived: 0,
    framesRendered: 0,
    seekEvents: 0,
    syncErrors: 0,
    avgLatency: 0,
    latencySum: 0
  };

  constructor(config: Partial<StereoscopicFeedConfig> = {}) {
    super();

    this.config = {
      timeBinder: config.timeBinder ?? {},
      smoothing: config.smoothing ?? true,
      chartHistorySize: config.chartHistorySize ?? 1000,
      syncTolerance: config.syncTolerance ?? 5,
      ohlcPeriod: config.ohlcPeriod ?? 1000
    };

    // Initialize TimeBinder
    this.timeBinder = getTimeBinder(this.config.timeBinder);

    // Initialize GeometricLerp for smooth rotations
    this.geometricLerp = new GeometricLerp(100);
  }

  // ==========================================================================
  // Public API: Ingestion
  // ==========================================================================

  /**
   * INGEST: Receive tick from API
   * Entry point for all market data
   */
  ingestTick(raw: RawApiTick): IndexedTick {
    const now = typeof performance !== 'undefined' ? performance.now() : Date.now();

    // INDEX: Stamp with local timestamp
    const indexed: IndexedTick = {
      ...raw,
      localTimestamp: now,
      apiLatency: raw.timestamp ? now - raw.timestamp : 0,
      sequenceId: this.sequenceCounter++
    };

    // Update metrics
    this.metrics.ticksReceived++;
    this.metrics.latencySum += indexed.apiLatency;
    this.metrics.avgLatency = this.metrics.latencySum / this.metrics.ticksReceived;

    // Emit indexed tick
    this.emit('tick', indexed);

    // DISPATCH: Send to StandardChart (Left Eye)
    const chartPoint = this.processForChart(indexed);
    this.emit('chart', chartPoint);

    // TRANSFORM: Send to TimeBinder → CPE (Right Eye)
    const marketTick = this.timeBinder.ingestTick({
      price: indexed.price,
      volume: indexed.volume,
      bid: indexed.bid,
      ask: indexed.ask,
      channels: indexed.channels,
      apiLatency: indexed.apiLatency
    });

    // Add keyframe for SLERP smoothing
    this.geometricLerp.addFromTick(marketTick);

    return indexed;
  }

  /**
   * Batch ingest multiple ticks
   */
  ingestBatch(ticks: RawApiTick[]): IndexedTick[] {
    return ticks.map(t => this.ingestTick(t));
  }

  // ==========================================================================
  // Public API: Frame Rendering
  // ==========================================================================

  /**
   * Request a synchronized stereoscopic frame
   * Called by animation loop (typically at 60fps)
   */
  requestFrame(timestamp?: number): StereoscopicFrame {
    const now = timestamp ?? (typeof performance !== 'undefined' ? performance.now() : Date.now());

    // Get phase-locked frame from TimeBinder
    const syncedFrame = this.timeBinder.getSyncedFrame(now);

    // Apply SLERP smoothing if enabled
    const smoothedFrame = this.config.smoothing
      ? this.geometricLerp.smoothFrame(syncedFrame)
      : syncedFrame;

    // Get interpolation state
    const interpolatedState = this.geometricLerp.getState(now);

    // Build CPE render data (Right Eye)
    const cpeData: CPERenderData = {
      timestamp: now,
      syncedFrame: smoothedFrame,
      interpolatedState,
      priceVector: smoothedFrame.priceVector,
      smoothedRotation: smoothedFrame.rotation
    };

    // Get corresponding chart point (Left Eye)
    const chartPoint = this.getChartPointAt(now);

    // Compute phase offset (sync error between eyes)
    const phaseOffset = smoothedFrame.phaseOffset;

    // Check sync tolerance
    if (Math.abs(phaseOffset) > this.config.syncTolerance) {
      this.metrics.syncErrors++;
      this.emit('sync-error', { offset: phaseOffset, timestamp: now });
    }

    // Build stereoscopic frame
    const frame: StereoscopicFrame = {
      timestamp: now,
      leftEye: chartPoint,
      rightEye: cpeData,
      phaseOffset,
      interpolation: smoothedFrame.interpolationFactor
    };

    this.metrics.framesRendered++;
    this.emit('frame', frame);
    this.emit('cpe', cpeData);

    return frame;
  }

  // ==========================================================================
  // Public API: Crosshair Synchronization (The Critical Constraint)
  // ==========================================================================

  /**
   * SEEK: Chart crosshair moved - snap 4D geometry to historical moment
   *
   * This is the critical phase-lock constraint: when the user moves
   * the crosshair on the 2D chart, the 4D geometric projection must
   * instantly snap to show that exact historical moment.
   */
  onCrosshairMove(event: CrosshairEvent): CPERenderData {
    this.lastCrosshairTimestamp = event.timestamp;
    this.metrics.seekEvents++;

    // Emit seek event for external listeners
    this.emit('seek', event);

    // SEEK into TimeBinder history
    const seekedFrame = this.timeBinder.seek(event.timestamp);

    // Apply SLERP smoothing to seeked position
    const smoothedFrame = this.config.smoothing
      ? this.geometricLerp.smoothFrame(seekedFrame)
      : seekedFrame;

    // Get interpolation state at seek position
    const interpolatedState = this.geometricLerp.getState(event.timestamp);

    // Build CPE render data for the seeked moment
    const cpeData: CPERenderData = {
      timestamp: event.timestamp,
      syncedFrame: smoothedFrame,
      interpolatedState,
      priceVector: smoothedFrame.priceVector,
      smoothedRotation: smoothedFrame.rotation
    };

    // Emit the CPE data for the seeked moment
    this.emit('cpe', cpeData);

    return cpeData;
  }

  /**
   * Create a crosshair handler for chart integration
   * Returns a function that can be bound to chart crosshair events
   */
  createCrosshairHandler(): (timestamp: number, price?: number) => CPERenderData {
    return (timestamp: number, price?: number) => {
      return this.onCrosshairMove({
        timestamp,
        price,
        source: 'chart'
      });
    };
  }

  // ==========================================================================
  // Public API: Animation Loop Management
  // ==========================================================================

  /**
   * Start the animation loop
   */
  start(): void {
    if (this.isRunning) return;
    this.isRunning = true;
    this.tick();
  }

  /**
   * Stop the animation loop
   */
  stop(): void {
    this.isRunning = false;
    if (this.animationFrameId !== null) {
      if (typeof cancelAnimationFrame !== 'undefined') {
        cancelAnimationFrame(this.animationFrameId);
      }
      this.animationFrameId = null;
    }
  }

  private tick = (): void => {
    if (!this.isRunning) return;

    // Request next frame
    const now = typeof performance !== 'undefined' ? performance.now() : Date.now();
    this.requestFrame(now);

    // Schedule next tick
    if (typeof requestAnimationFrame !== 'undefined') {
      this.animationFrameId = requestAnimationFrame(this.tick);
    } else {
      // Fallback for Node.js environment
      setTimeout(this.tick, 16);
    }
  };

  // ==========================================================================
  // Public API: State Access
  // ==========================================================================

  /**
   * Get the TimeBinder instance for direct access
   */
  getTimeBinder(): TimeBinder {
    return this.timeBinder;
  }

  /**
   * Get the GeometricLerp instance
   */
  getGeometricLerp(): GeometricLerp {
    return this.geometricLerp;
  }

  /**
   * Get chart history
   */
  getChartHistory(): ChartDataPoint[] {
    return [...this.chartHistory];
  }

  /**
   * Get configuration
   */
  getConfig(): Readonly<StereoscopicFeedConfig> {
    return { ...this.config };
  }

  /**
   * Update configuration
   */
  setConfig(updates: Partial<StereoscopicFeedConfig>): void {
    Object.assign(this.config, updates);

    // Propagate TimeBinder config changes
    if (updates.timeBinder) {
      this.timeBinder.setConfig(updates.timeBinder);
    }
  }

  /**
   * Get metrics
   */
  getMetrics(): typeof this.metrics & {
    timeBinderMetrics: ReturnType<TimeBinder['getMetrics']>;
    geometricLerpKeyframes: number;
  } {
    return {
      ...this.metrics,
      timeBinderMetrics: this.timeBinder.getMetrics(),
      geometricLerpKeyframes: this.geometricLerp.length
    };
  }

  /**
   * Clear all state
   */
  clear(): void {
    this.stop();
    this.timeBinder.clear();
    this.geometricLerp.clear();
    this.chartHistory = [];
    this.ohlcAccumulator = null;
    this.sequenceCounter = 0;
    this.lastCrosshairTimestamp = 0;
    this.metrics = {
      ticksReceived: 0,
      framesRendered: 0,
      seekEvents: 0,
      syncErrors: 0,
      avgLatency: 0,
      latencySum: 0
    };
    this.removeAllListeners();
  }

  // ==========================================================================
  // Private: Chart Processing (Left Eye)
  // ==========================================================================

  private processForChart(tick: IndexedTick): ChartDataPoint {
    const point: ChartDataPoint = {
      timestamp: tick.localTimestamp,
      price: tick.price,
      volume: tick.volume ?? 0,
      bid: tick.bid ?? tick.price,
      ask: tick.ask ?? tick.price
    };

    // OHLC aggregation
    if (this.config.ohlcPeriod > 0) {
      this.updateOHLC(tick);
      if (this.ohlcAccumulator) {
        point.open = this.ohlcAccumulator.open;
        point.high = this.ohlcAccumulator.high;
        point.low = this.ohlcAccumulator.low;
        point.close = this.ohlcAccumulator.close;
      }
    }

    // Add to history
    this.chartHistory.push(point);

    // Trim history if over capacity
    while (this.chartHistory.length > this.config.chartHistorySize) {
      this.chartHistory.shift();
    }

    return point;
  }

  private updateOHLC(tick: IndexedTick): void {
    const periodStart = Math.floor(tick.localTimestamp / this.config.ohlcPeriod) * this.config.ohlcPeriod;

    if (!this.ohlcAccumulator || periodStart !== this.ohlcAccumulator.periodStart) {
      // New OHLC period
      this.ohlcAccumulator = {
        open: tick.price,
        high: tick.price,
        low: tick.price,
        close: tick.price,
        volume: tick.volume ?? 0,
        periodStart
      };
    } else {
      // Update existing period
      this.ohlcAccumulator.high = Math.max(this.ohlcAccumulator.high, tick.price);
      this.ohlcAccumulator.low = Math.min(this.ohlcAccumulator.low, tick.price);
      this.ohlcAccumulator.close = tick.price;
      this.ohlcAccumulator.volume += tick.volume ?? 0;
    }
  }

  private getChartPointAt(timestamp: number): ChartDataPoint {
    // Find the closest chart point to the timestamp
    if (this.chartHistory.length === 0) {
      return {
        timestamp,
        price: 0,
        volume: 0,
        bid: 0,
        ask: 0
      };
    }

    // Binary search for closest point
    let left = 0;
    let right = this.chartHistory.length - 1;

    while (left < right - 1) {
      const mid = Math.floor((left + right) / 2);
      if (this.chartHistory[mid].timestamp <= timestamp) {
        left = mid;
      } else {
        right = mid;
      }
    }

    // Return the closest point
    const leftDiff = Math.abs(this.chartHistory[left].timestamp - timestamp);
    const rightDiff = Math.abs(this.chartHistory[right].timestamp - timestamp);

    return leftDiff <= rightDiff ? this.chartHistory[left] : this.chartHistory[right];
  }
}

// ============================================================================
// StereoscopicFeed - Main Export (Facade)
// ============================================================================

/**
 * StereoscopicFeed - High-level facade for the stereoscopic data system
 *
 * Combines DataPrism with convenience methods for common use cases.
 */
export class StereoscopicFeed {
  private prism: DataPrism;

  constructor(config: Partial<StereoscopicFeedConfig> = {}) {
    this.prism = new DataPrism(config);
  }

  /**
   * Get the underlying DataPrism
   */
  get dataPrism(): DataPrism {
    return this.prism;
  }

  /**
   * Ingest a market tick
   */
  ingest(tick: RawApiTick): IndexedTick {
    return this.prism.ingestTick(tick);
  }

  /**
   * Request a stereoscopic frame
   */
  frame(timestamp?: number): StereoscopicFrame {
    return this.prism.requestFrame(timestamp);
  }

  /**
   * Handle crosshair movement
   */
  seek(timestamp: number): CPERenderData {
    return this.prism.onCrosshairMove({
      timestamp,
      source: 'external'
    });
  }

  /**
   * Subscribe to events
   */
  on<K extends keyof DataPrismEvents>(
    event: K,
    callback: (data: DataPrismEvents[K]) => void
  ): () => void {
    return this.prism.on(event, callback);
  }

  /**
   * Start animation loop
   */
  start(): void {
    this.prism.start();
  }

  /**
   * Stop animation loop
   */
  stop(): void {
    this.prism.stop();
  }

  /**
   * Get metrics
   */
  getMetrics(): ReturnType<DataPrism['getMetrics']> {
    return this.prism.getMetrics();
  }

  /**
   * Clear all state
   */
  clear(): void {
    this.prism.clear();
  }
}

// ============================================================================
// Factory Functions
// ============================================================================

let globalFeed: StereoscopicFeed | null = null;

/**
 * Get or create the global StereoscopicFeed instance
 */
export function getStereoscopicFeed(config?: Partial<StereoscopicFeedConfig>): StereoscopicFeed {
  if (!globalFeed) {
    globalFeed = new StereoscopicFeed(config);
  }
  return globalFeed;
}

/**
 * Reset the global feed (for testing)
 */
export function resetStereoscopicFeed(): void {
  globalFeed?.clear();
  globalFeed = null;
}

// ============================================================================
// Type Re-exports
// ============================================================================

export type {
  MarketTick,
  PriceVector,
  SyncedFrame,
  TimeBinderConfig
} from '../temporal/TimeBinder';

export type {
  InterpolatedState,
  KeyframeData
} from '../temporal/GeometricLerp';

export default StereoscopicFeed;

/**
 * Phase-Locked Stereoscopy System - RIGOROUS TEST SUITE
 *
 * This test suite uses actual assertions and mathematical verification.
 * Tests FAIL if the implementation is incorrect.
 *
 * Red Team Fixes:
 * - Real assertions instead of console.log
 * - Mathematical property verification
 * - Edge case coverage
 * - Numerical tolerance handling
 * - Phase-lock constraint enforcement
 */

import { strict as assert } from 'node:assert';
import { describe, it, beforeEach } from 'node:test';

import {
  TimeBinder,
  RingBuffer,
  type MarketTick,
  type SyncedFrame,
  type GeometricRotation
} from '../src/lib/temporal/TimeBinder.js';

import {
  GeometricLerp,
  Quaternion,
  slerp,
  nlerp,
  Rotor4D,
  slerpRotation,
  rotationDistance
} from '../src/lib/temporal/GeometricLerp.js';

import {
  StereoscopicFeed,
  DataPrism,
  type StereoscopicFrame,
  type CPERenderData
} from '../src/lib/fusion/StereoscopicFeed.js';

// ============================================================================
// Test Utilities
// ============================================================================

const EPSILON = 1e-10;       // For floating point comparison
const ANGLE_EPSILON = 1e-6;  // For angle comparison (radians)

function assertNear(actual: number, expected: number, tolerance = EPSILON, msg = ''): void {
  const diff = Math.abs(actual - expected);
  assert.ok(
    diff <= tolerance,
    `${msg} Expected ${expected}, got ${actual} (diff: ${diff}, tolerance: ${tolerance})`
  );
}

function assertQuaternionUnit(q: Quaternion, tolerance = EPSILON): void {
  const mag = q.magnitude();
  assertNear(mag, 1.0, tolerance, 'Quaternion must be unit length');
}

function assertQuaternionEqual(a: Quaternion, b: Quaternion, tolerance = EPSILON): void {
  // Quaternions q and -q represent the same rotation
  const sameDot = Math.abs(a.dot(b));
  assertNear(sameDot, 1.0, tolerance, 'Quaternions should represent same rotation');
}

function createTestTick(timestamp: number, price: number): MarketTick {
  return {
    timestamp,
    sequence: 0,
    priceVector: {
      price,
      volume: 1000,
      bid: price - 0.01,
      ask: price + 0.01,
      spread: 0.02,
      momentum: 0,
      volatility: 0,
      channels: []
    },
    rotation: { rotXY: 0, rotXZ: 0, rotXW: 0, rotYZ: 0, rotYW: 0, rotZW: 0 },
    latency: 0
  };
}

// ============================================================================
// TEST SUITE 1: RingBuffer
// ============================================================================

describe('RingBuffer', () => {
  describe('basic operations', () => {
    it('should start empty', () => {
      const buffer = new RingBuffer<{ timestamp: number }>(10);
      assert.strictEqual(buffer.size(), 0);
      assert.strictEqual(buffer.oldest(), null);
      assert.strictEqual(buffer.newest(), null);
    });

    it('should store and retrieve items in order', () => {
      const buffer = new RingBuffer<{ timestamp: number; value: number }>(10);

      buffer.push({ timestamp: 100, value: 1 });
      buffer.push({ timestamp: 200, value: 2 });
      buffer.push({ timestamp: 300, value: 3 });

      assert.strictEqual(buffer.size(), 3);
      assert.strictEqual(buffer.oldest()?.value, 1);
      assert.strictEqual(buffer.newest()?.value, 3);
      assert.strictEqual(buffer.get(0)?.value, 1);
      assert.strictEqual(buffer.get(1)?.value, 2);
      assert.strictEqual(buffer.get(2)?.value, 3);
    });

    it('should overwrite oldest items when at capacity', () => {
      const buffer = new RingBuffer<{ timestamp: number; value: number }>(3);

      for (let i = 0; i < 5; i++) {
        buffer.push({ timestamp: i * 100, value: i });
      }

      assert.strictEqual(buffer.size(), 3);
      assert.strictEqual(buffer.oldest()?.value, 2, 'Oldest should be value 2 after overflow');
      assert.strictEqual(buffer.newest()?.value, 4, 'Newest should be value 4');

      // Verify all three items are correct
      assert.strictEqual(buffer.get(0)?.value, 2);
      assert.strictEqual(buffer.get(1)?.value, 3);
      assert.strictEqual(buffer.get(2)?.value, 4);
    });

    it('should return null for out-of-bounds access', () => {
      const buffer = new RingBuffer<{ timestamp: number }>(5);
      buffer.push({ timestamp: 100 });

      assert.strictEqual(buffer.get(-1), null);
      assert.strictEqual(buffer.get(1), null);
      assert.strictEqual(buffer.get(100), null);
    });
  });

  describe('findBracket (binary search)', () => {
    it('should return [-1, -1] for empty buffer', () => {
      const buffer = new RingBuffer<{ timestamp: number }>(10);
      const [lower, upper] = buffer.findBracket(100);
      assert.strictEqual(lower, -1);
      assert.strictEqual(upper, -1);
    });

    it('should return [0, 0] for single-element buffer', () => {
      const buffer = new RingBuffer<{ timestamp: number }>(10);
      buffer.push({ timestamp: 100 });

      const [lower, upper] = buffer.findBracket(50);
      assert.strictEqual(lower, 0);
      assert.strictEqual(upper, 0);
    });

    it('should find exact bracket for timestamp between ticks', () => {
      const buffer = new RingBuffer<{ timestamp: number }>(10);
      buffer.push({ timestamp: 0 });
      buffer.push({ timestamp: 100 });
      buffer.push({ timestamp: 200 });
      buffer.push({ timestamp: 300 });

      // Test middle bracket
      const [lower, upper] = buffer.findBracket(150);
      assert.strictEqual(buffer.get(lower)?.timestamp, 100);
      assert.strictEqual(buffer.get(upper)?.timestamp, 200);
    });

    it('should handle timestamp before all data', () => {
      const buffer = new RingBuffer<{ timestamp: number }>(10);
      buffer.push({ timestamp: 100 });
      buffer.push({ timestamp: 200 });

      const [lower, upper] = buffer.findBracket(50);
      assert.strictEqual(lower, 0);
      assert.strictEqual(upper, 0);
    });

    it('should handle timestamp after all data', () => {
      const buffer = new RingBuffer<{ timestamp: number }>(10);
      buffer.push({ timestamp: 100 });
      buffer.push({ timestamp: 200 });

      const [lower, upper] = buffer.findBracket(300);
      assert.strictEqual(lower, 1);
      assert.strictEqual(upper, 1);
    });

    it('should handle exact timestamp match', () => {
      const buffer = new RingBuffer<{ timestamp: number }>(10);
      buffer.push({ timestamp: 100 });
      buffer.push({ timestamp: 200 });
      buffer.push({ timestamp: 300 });

      const [lower, upper] = buffer.findBracket(200);
      // Should return the exact match and next
      assert.ok(
        buffer.get(lower)?.timestamp === 200 || buffer.get(upper)?.timestamp === 200,
        'Should find exact timestamp'
      );
    });
  });

  describe('getTimeSpan', () => {
    it('should return null for empty buffer', () => {
      const buffer = new RingBuffer<{ timestamp: number }>(10);
      assert.strictEqual(buffer.getTimeSpan(), null);
    });

    it('should calculate correct time span', () => {
      const buffer = new RingBuffer<{ timestamp: number }>(10);
      buffer.push({ timestamp: 100 });
      buffer.push({ timestamp: 300 });

      const span = buffer.getTimeSpan();
      assert.ok(span !== null);
      assert.strictEqual(span.start, 100);
      assert.strictEqual(span.end, 300);
      assert.strictEqual(span.duration, 200);
    });
  });
});

// ============================================================================
// TEST SUITE 2: Quaternion Mathematics
// ============================================================================

describe('Quaternion', () => {
  describe('construction and identity', () => {
    it('should create identity quaternion', () => {
      const q = Quaternion.identity();
      assert.strictEqual(q.w, 1);
      assert.strictEqual(q.x, 0);
      assert.strictEqual(q.y, 0);
      assert.strictEqual(q.z, 0);
      assertQuaternionUnit(q);
    });

    it('should normalize non-unit quaternions', () => {
      const q = new Quaternion(2, 0, 0, 0).normalize();
      assertQuaternionUnit(q);
      assert.strictEqual(q.w, 1);
    });

    it('should create quaternion from axis-angle', () => {
      // 90 degrees around Y axis
      const q = Quaternion.fromAxisAngle([0, 1, 0], Math.PI / 2);
      assertQuaternionUnit(q);

      // cos(45°) ≈ 0.707, sin(45°) ≈ 0.707
      assertNear(q.w, Math.cos(Math.PI / 4), 1e-6);
      assertNear(q.y, Math.sin(Math.PI / 4), 1e-6);
    });
  });

  describe('operations', () => {
    it('should compute correct dot product', () => {
      const q1 = Quaternion.identity();
      const q2 = Quaternion.identity();
      assertNear(q1.dot(q2), 1.0);

      const q3 = new Quaternion(0, 1, 0, 0); // 180° rotation
      assertNear(q1.dot(q3), 0.0);
    });

    it('should compute conjugate correctly', () => {
      const q = new Quaternion(1, 2, 3, 4).normalize();
      const conj = q.conjugate();

      assert.strictEqual(conj.w, q.w);
      assert.strictEqual(conj.x, -q.x);
      assert.strictEqual(conj.y, -q.y);
      assert.strictEqual(conj.z, -q.z);
    });

    it('should satisfy q * q^-1 = identity for unit quaternions', () => {
      const q = Quaternion.fromAxisAngle([1, 1, 1], Math.PI / 3).normalize();
      const qInv = q.conjugate();
      const result = q.multiply(qInv);

      assertNear(result.w, 1.0, 1e-6);
      assertNear(result.x, 0.0, 1e-6);
      assertNear(result.y, 0.0, 1e-6);
      assertNear(result.z, 0.0, 1e-6);
    });
  });
});

// ============================================================================
// TEST SUITE 3: SLERP (Spherical Linear Interpolation)
// ============================================================================

describe('SLERP', () => {
  describe('boundary conditions', () => {
    it('should return q0 when t=0', () => {
      const q0 = Quaternion.fromAxisAngle([0, 1, 0], 0);
      const q1 = Quaternion.fromAxisAngle([0, 1, 0], Math.PI / 2);

      const result = slerp(q0, q1, 0);
      assertQuaternionEqual(result, q0);
    });

    it('should return q1 when t=1', () => {
      const q0 = Quaternion.fromAxisAngle([0, 1, 0], 0);
      const q1 = Quaternion.fromAxisAngle([0, 1, 0], Math.PI / 2);

      const result = slerp(q0, q1, 1);
      assertQuaternionEqual(result, q1);
    });

    it('should return midpoint when t=0.5', () => {
      const q0 = Quaternion.fromAxisAngle([0, 1, 0], 0);
      const q1 = Quaternion.fromAxisAngle([0, 1, 0], Math.PI / 2);
      const expected = Quaternion.fromAxisAngle([0, 1, 0], Math.PI / 4);

      const result = slerp(q0, q1, 0.5);
      assertQuaternionEqual(result, expected, 1e-6);
    });
  });

  describe('constant angular velocity', () => {
    it('should maintain constant angular velocity (the key SLERP property)', () => {
      // Use a smaller rotation (90°) to avoid Euler angle wrapping issues
      const q0 = Quaternion.fromAxisAngle([0, 1, 0], 0);
      const q1 = Quaternion.fromAxisAngle([0, 1, 0], Math.PI / 2);

      // Sample at regular intervals
      const samples = 10;
      const angles: number[] = [];

      for (let i = 0; i <= samples; i++) {
        const t = i / samples;
        const q = slerp(q0, q1, t);
        const euler = q.toEuler();
        angles.push(euler[1]); // Y-axis rotation
      }

      // Check that angular increments are equal (constant velocity)
      const increments: number[] = [];
      for (let i = 1; i < angles.length; i++) {
        increments.push(angles[i] - angles[i - 1]);
      }

      const expectedIncrement = (Math.PI / 2) / samples;
      for (const inc of increments) {
        assertNear(Math.abs(inc), expectedIncrement, 0.01, 'Angular velocity should be constant');
      }
    });
  });

  describe('geodesic path (shortest path)', () => {
    it('should take shorter path when quaternions have negative dot product', () => {
      // These quaternions represent the same rotation but with opposite signs
      const q0 = new Quaternion(1, 0, 0, 0);
      const q1 = new Quaternion(-0.707, 0, 0.707, 0); // Opposite hemisphere

      // SLERP should automatically take shorter path
      const mid = slerp(q0, q1, 0.5);
      assertQuaternionUnit(mid);

      // The interpolated quaternion should be valid
      const dot0 = Math.abs(q0.dot(mid));
      const dot1 = Math.abs(q1.dot(mid));

      // Mid should be "between" both (closer to both than they are to each other)
      assert.ok(dot0 > 0.5, 'Midpoint should be reasonably close to q0');
      assert.ok(dot1 > 0.5, 'Midpoint should be reasonably close to q1');
    });
  });

  describe('edge cases', () => {
    it('should handle nearly identical quaternions (small angle)', () => {
      const q0 = Quaternion.fromAxisAngle([0, 1, 0], 0);
      const q1 = Quaternion.fromAxisAngle([0, 1, 0], 0.0001);

      const result = slerp(q0, q1, 0.5);
      assertQuaternionUnit(result);

      // Should be approximately halfway
      const euler = result.toEuler();
      assertNear(euler[1], 0.00005, 0.001);
    });

    it('should clamp t to [0, 1]', () => {
      const q0 = Quaternion.identity();
      const q1 = Quaternion.fromAxisAngle([0, 1, 0], Math.PI / 2);

      const resultNeg = slerp(q0, q1, -0.5);
      const result0 = slerp(q0, q1, 0);
      assertQuaternionEqual(resultNeg, result0, 1e-6);

      const resultOver = slerp(q0, q1, 1.5);
      const result1 = slerp(q0, q1, 1);
      assertQuaternionEqual(resultOver, result1, 1e-6);
    });
  });
});

// ============================================================================
// TEST SUITE 4: TimeBinder Phase-Locking
// ============================================================================

describe('TimeBinder', () => {
  describe('phase-lock behavior', () => {
    it('should render at (now - latencyBuffer), not latest', () => {
      const binder = new TimeBinder({
        bufferSize: 100,
        latencyBuffer: 50,
        maxInterpolationGap: 500,
        rotationScale: 0.01
      });

      // Ingest ticks at t=0, 100, 200
      binder.ingestRawTick(createTestTick(0, 100));
      binder.ingestRawTick(createTestTick(100, 110));
      binder.ingestRawTick(createTestTick(200, 120));

      // Request frame at t=150 with latencyBuffer=50
      // Should render data from t=100, NOT t=200
      const frame = binder.getSyncedFrame(150);

      // Target time is 150-50=100, which should hit the t=100 tick exactly
      assertNear(frame.priceVector.price, 110, 0.001, 'Should render t=100 tick, not latest');
    });

    it('should interpolate between ticks when target falls between them', () => {
      const binder = new TimeBinder({
        bufferSize: 100,
        latencyBuffer: 50,
        maxInterpolationGap: 500,
        rotationScale: 0.01
      });

      binder.ingestRawTick(createTestTick(0, 100));
      binder.ingestRawTick(createTestTick(100, 200));

      // Request frame at t=75 (target = 25, which is 25% between t=0 and t=100)
      const frame = binder.getSyncedFrame(75);

      // Expected: 100 + (200-100) * 0.25 = 125
      assertNear(frame.priceVector.price, 125, 0.001);
      assertNear(frame.interpolationFactor, 0.25, 0.001);
    });

    it('should return exact tick when target matches timestamp', () => {
      const binder = new TimeBinder({
        bufferSize: 100,
        latencyBuffer: 50,
        maxInterpolationGap: 500,
        rotationScale: 0.01
      });

      binder.ingestRawTick(createTestTick(0, 100));
      binder.ingestRawTick(createTestTick(100, 200));

      // Request frame at t=150 (target = 100, exact match)
      const frame = binder.getSyncedFrame(150);

      assert.strictEqual(frame.priceVector.price, 200);
      assert.strictEqual(frame.isExact, true);
    });
  });

  describe('seek behavior', () => {
    it('should seek to exact historical timestamp without latency buffer', () => {
      const binder = new TimeBinder({
        bufferSize: 100,
        latencyBuffer: 50,
        maxInterpolationGap: 500,
        rotationScale: 0.01
      });

      binder.ingestRawTick(createTestTick(0, 100));
      binder.ingestRawTick(createTestTick(100, 150));
      binder.ingestRawTick(createTestTick(200, 200));

      // Seek to t=100 should return exactly that tick
      const frame = binder.seek(100);
      assertNear(frame.priceVector.price, 150, 0.001);
    });

    it('should interpolate during seek when between ticks', () => {
      const binder = new TimeBinder({
        bufferSize: 100,
        latencyBuffer: 50,
        maxInterpolationGap: 500,
        rotationScale: 0.01
      });

      binder.ingestRawTick(createTestTick(0, 100));
      binder.ingestRawTick(createTestTick(100, 200));

      // Seek to t=50 (halfway)
      const frame = binder.seek(50);
      assertNear(frame.priceVector.price, 150, 0.001);
      assertNear(frame.interpolationFactor, 0.5, 0.001);
    });
  });

  describe('edge cases', () => {
    it('should return empty frame when buffer is empty', () => {
      const binder = new TimeBinder({
        bufferSize: 100,
        latencyBuffer: 50,
        maxInterpolationGap: 500,
        rotationScale: 0.01
      });

      const frame = binder.getSyncedFrame(100);
      assert.strictEqual(frame.priceVector.price, 0);
      assert.strictEqual(frame.tickA, null);
    });

    it('should handle single tick correctly', () => {
      const binder = new TimeBinder({
        bufferSize: 100,
        latencyBuffer: 50,
        maxInterpolationGap: 500,
        rotationScale: 0.01
      });

      binder.ingestRawTick(createTestTick(50, 123));

      const frame = binder.getSyncedFrame(100); // target = 50
      assertNear(frame.priceVector.price, 123, 0.001);
    });

    it('should not interpolate across large gaps', () => {
      const binder = new TimeBinder({
        bufferSize: 100,
        latencyBuffer: 50,
        maxInterpolationGap: 500,
        rotationScale: 0.01
      });

      binder.ingestRawTick(createTestTick(0, 100));
      binder.ingestRawTick(createTestTick(1000, 200)); // 1000ms gap > maxInterpolationGap (500)

      // Request frame at t=550 (target = 500)
      const frame = binder.getSyncedFrame(550);

      // Should snap to nearest tick, not interpolate
      assert.ok(
        frame.priceVector.price === 100 || frame.priceVector.price === 200,
        'Should not interpolate across large gap'
      );
    });
  });

  describe('buffer overflow', () => {
    it('should maintain correct data after buffer overflow', () => {
      const smallBinder = new TimeBinder({ bufferSize: 5 });

      // Insert 10 ticks
      for (let i = 0; i < 10; i++) {
        smallBinder.ingestRawTick(createTestTick(i * 100, 100 + i));
      }

      // Buffer should only contain last 5 ticks (t=500 to t=900)
      const metrics = smallBinder.getMetrics();
      assert.strictEqual(metrics.bufferSize, 5);

      // Should be able to retrieve recent data
      const frame = smallBinder.getSyncedFrame(950); // target depends on latency buffer
      assert.ok(frame.priceVector.price >= 105, 'Should have recent data');
    });
  });

  describe('metrics tracking', () => {
    it('should track interpolation vs exact hits', () => {
      const binder = new TimeBinder({
        bufferSize: 100,
        latencyBuffer: 50,
        maxInterpolationGap: 500,
        rotationScale: 0.01
      });

      binder.ingestRawTick(createTestTick(0, 100));
      binder.ingestRawTick(createTestTick(100, 200));

      // Exact hit
      binder.getSyncedFrame(150); // target = 100

      // Interpolated
      binder.getSyncedFrame(75); // target = 25

      const metrics = binder.getMetrics();
      assert.strictEqual(metrics.totalFrames, 2);
      assert.ok(metrics.exactHits >= 1 || metrics.interpolatedFrames >= 1);
    });
  });
});

// ============================================================================
// TEST SUITE 5: GeometricLerp
// ============================================================================

describe('GeometricLerp', () => {
  describe('keyframe management', () => {
    it('should handle empty state', () => {
      const lerp = new GeometricLerp(100);
      const state = lerp.getState(100);
      assert.strictEqual(state.keyframeA, null);
      assert.strictEqual(state.keyframeB, null);
    });

    it('should handle single keyframe', () => {
      const lerp = new GeometricLerp(100);
      lerp.addKeyframe({
        timestamp: 100,
        rotation: { rotXY: 1, rotXZ: 0, rotXW: 0, rotYZ: 0, rotYW: 0, rotZW: 0 }
      });

      const state = lerp.getState(100);
      assertNear(state.rotation.rotXY, 1, 1e-6);
    });

    it('should maintain keyframes in sorted order', () => {
      const lerp = new GeometricLerp(100);
      // Add out of order
      lerp.addKeyframe({ timestamp: 300, rotation: { rotXY: 3, rotXZ: 0, rotXW: 0, rotYZ: 0, rotYW: 0, rotZW: 0 } });
      lerp.addKeyframe({ timestamp: 100, rotation: { rotXY: 1, rotXZ: 0, rotXW: 0, rotYZ: 0, rotYW: 0, rotZW: 0 } });
      lerp.addKeyframe({ timestamp: 200, rotation: { rotXY: 2, rotXZ: 0, rotXW: 0, rotYZ: 0, rotYW: 0, rotZW: 0 } });

      // Should interpolate correctly regardless of insertion order
      const state = lerp.getState(150);
      assertNear(state.interpolationFactor, 0.5, 0.01);
    });
  });

  describe('interpolation', () => {
    it('should interpolate linearly for simple cases', () => {
      const lerp = new GeometricLerp(100);
      lerp.addKeyframe({
        timestamp: 0,
        rotation: { rotXY: 0, rotXZ: 0, rotXW: 0, rotYZ: 0, rotYW: 0, rotZW: 0 }
      });
      lerp.addKeyframe({
        timestamp: 100,
        rotation: { rotXY: Math.PI, rotXZ: 0, rotXW: 0, rotYZ: 0, rotYW: 0, rotZW: 0 }
      });

      // Test interpolation points BETWEEN keyframes (excluding exact keyframe hits)
      // At exact keyframes (t=0, t=100), interpolationFactor is 0 (exact hit, no interpolation)
      // Between keyframes, interpolationFactor reflects position within the interval
      const testCases = [
        { t: 0, expected: 0 },     // Exact hit at first keyframe
        { t: 25, expected: 0.25 }, // 25% between keyframes
        { t: 50, expected: 0.5 },  // 50% between keyframes
        { t: 75, expected: 0.75 }, // 75% between keyframes
        { t: 100, expected: 0 }    // Exact hit at last keyframe (returns 0, not 1)
      ];

      for (const { t, expected } of testCases) {
        const state = lerp.getState(t);
        assertNear(state.interpolationFactor, expected, 0.01, `t=${t}`);
      }
    });

    it('should compute angular velocity between keyframes', () => {
      const lerp = new GeometricLerp(100);
      lerp.addKeyframe({
        timestamp: 0,
        rotation: { rotXY: 0, rotXZ: 0, rotXW: 0, rotYZ: 0, rotYW: 0, rotZW: 0 }
      });
      lerp.addKeyframe({
        timestamp: 1000,
        rotation: { rotXY: Math.PI, rotXZ: 0, rotXW: 0, rotYZ: 0, rotYW: 0, rotZW: 0 }
      });

      const state = lerp.getState(500);

      // Velocity should be π radians / 1000ms = π/1000 rad/ms
      assertNear(state.velocity.rotXY, Math.PI / 1000, 1e-6);
    });
  });
});

// ============================================================================
// TEST SUITE 6: StereoscopicFeed Integration
// ============================================================================

describe('StereoscopicFeed', () => {
  describe('data bifurcation', () => {
    it('should emit tick events on ingest', (_, done) => {
      const feed = new StereoscopicFeed({
        smoothing: false,
        chartHistorySize: 100,
        timeBinder: { latencyBuffer: 50 }
      });

      let received = false;
      feed.on('tick', (tick) => {
        assert.strictEqual(tick.price, 100);
        received = true;
      });

      feed.ingest({ price: 100 });
      assert.ok(received, 'Should have received tick event');
      feed.clear();
      done();
    });

    it('should emit chart events with correct data', (_, done) => {
      const feed = new StereoscopicFeed({
        smoothing: false,
        chartHistorySize: 100,
        timeBinder: { latencyBuffer: 50 }
      });

      let chartPoint: any = null;
      feed.on('chart', (point) => {
        chartPoint = point;
      });

      feed.ingest({ price: 100, volume: 500, bid: 99.5, ask: 100.5 });

      assert.ok(chartPoint !== null);
      assert.strictEqual(chartPoint.price, 100);
      assert.strictEqual(chartPoint.volume, 500);
      assert.strictEqual(chartPoint.bid, 99.5);
      assert.strictEqual(chartPoint.ask, 100.5);
      feed.clear();
      done();
    });
  });

  describe('phase-lock constraint (THE CRITICAL TEST)', () => {
    it('should synchronize left and right eye to same conceptual moment on seek', () => {
      const feed = new StereoscopicFeed({
        smoothing: false,
        chartHistorySize: 100,
        timeBinder: { latencyBuffer: 0 } // Zero latency for deterministic test
      });

      // Ingest data at known timestamps
      const prices = [100, 110, 120, 130, 140];
      prices.forEach((price, i) => {
        // Manually inject with known timestamps for deterministic test
        const tick = createTestTick(i * 100, price);
        feed.dataPrism.getTimeBinder().ingestRawTick(tick);
      });

      // Seek to t=200 (should get price=120)
      const cpeData = feed.seek(200);

      // The critical constraint: CPE data should show the same price
      // that would appear on the chart at t=200
      assertNear(cpeData.priceVector.price, 120, 0.01,
        'CPE (right eye) must show same data as chart (left eye) at seek timestamp');

      feed.clear();
    });

    it('should emit seek event when crosshair moves', (_, done) => {
      const feed = new StereoscopicFeed({
        smoothing: false,
        chartHistorySize: 100,
        timeBinder: { latencyBuffer: 50 }
      });

      let seekEvent: any = null;
      feed.on('seek', (event) => {
        seekEvent = event;
      });

      feed.seek(12345);

      assert.ok(seekEvent !== null);
      assert.strictEqual(seekEvent.timestamp, 12345);
      feed.clear();
      done();
    });
  });

  describe('metrics', () => {
    it('should track ticks and frames correctly', () => {
      const feed = new StereoscopicFeed({
        smoothing: false,
        chartHistorySize: 100,
        timeBinder: { latencyBuffer: 50 }
      });

      feed.ingest({ price: 100 });
      feed.ingest({ price: 101 });
      feed.ingest({ price: 102 });

      feed.frame();
      feed.frame();

      const metrics = feed.getMetrics();
      assert.strictEqual(metrics.ticksReceived, 3);
      assert.strictEqual(metrics.framesRendered, 2);
      feed.clear();
    });

    it('should track seek events', () => {
      const feed = new StereoscopicFeed({
        smoothing: false,
        chartHistorySize: 100,
        timeBinder: { latencyBuffer: 50 }
      });

      feed.seek(100);
      feed.seek(200);
      feed.seek(300);

      const metrics = feed.getMetrics();
      assert.strictEqual(metrics.seekEvents, 3);
      feed.clear();
    });
  });
});

// ============================================================================
// TEST SUITE 7: Mathematical Invariants
// ============================================================================

describe('Mathematical Invariants', () => {
  describe('interpolation properties', () => {
    it('linear interpolation should satisfy f(0)=a, f(1)=b', () => {
      const binder = new TimeBinder({ latencyBuffer: 0 });
      binder.ingestRawTick(createTestTick(0, 100));
      binder.ingestRawTick(createTestTick(100, 200));

      const at0 = binder.getSyncedFrame(0);
      const at100 = binder.getSyncedFrame(100);

      assertNear(at0.priceVector.price, 100, 0.001, 'f(0) should equal a');
      assertNear(at100.priceVector.price, 200, 0.001, 'f(1) should equal b');
    });

    it('interpolation should be monotonic for monotonic input', () => {
      const binder = new TimeBinder({ latencyBuffer: 0 });
      binder.ingestRawTick(createTestTick(0, 100));
      binder.ingestRawTick(createTestTick(100, 200));

      let prevPrice = 0;
      for (let t = 0; t <= 100; t += 10) {
        const frame = binder.getSyncedFrame(t);
        assert.ok(frame.priceVector.price >= prevPrice,
          `Price should be monotonically increasing: ${prevPrice} -> ${frame.priceVector.price}`);
        prevPrice = frame.priceVector.price;
      }
    });
  });

  describe('quaternion invariants', () => {
    it('SLERP should always produce unit quaternions', () => {
      const q0 = Quaternion.fromAxisAngle([1, 2, 3], 0.5);
      const q1 = Quaternion.fromAxisAngle([3, 2, 1], 1.5);

      for (let t = 0; t <= 1; t += 0.1) {
        const q = slerp(q0, q1, t);
        assertQuaternionUnit(q, 1e-6);
      }
    });

    it('rotation distance should be symmetric', () => {
      const r0: GeometricRotation = { rotXY: 0.5, rotXZ: 0.3, rotXW: 0.1, rotYZ: 0.2, rotYW: 0.4, rotZW: 0.6 };
      const r1: GeometricRotation = { rotXY: 1.5, rotXZ: 1.3, rotXW: 1.1, rotYZ: 1.2, rotYW: 1.4, rotZW: 1.6 };

      const d01 = rotationDistance(r0, r1);
      const d10 = rotationDistance(r1, r0);

      assertNear(d01, d10, 1e-10, 'Distance should be symmetric');
    });

    it('rotation distance to self should be zero', () => {
      const r: GeometricRotation = { rotXY: 0.5, rotXZ: 0.3, rotXW: 0.1, rotYZ: 0.2, rotYW: 0.4, rotZW: 0.6 };
      const d = rotationDistance(r, r);
      assertNear(d, 0, 1e-6, 'Distance to self should be zero');
    });
  });
});

// ============================================================================
// Run Tests
// ============================================================================

console.log('\n' + '═'.repeat(70));
console.log('  PHASE-LOCKED STEREOSCOPY - RIGOROUS TEST SUITE');
console.log('  Tests use real assertions - failures will throw errors');
console.log('═'.repeat(70) + '\n');

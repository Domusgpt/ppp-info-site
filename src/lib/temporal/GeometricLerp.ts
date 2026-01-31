/**
 * GeometricLerp.ts - Spherical Linear Interpolation for 4D Rotations
 *
 * The "Smoother" that interpolates geometry between discrete market keyframes.
 *
 * Problem:
 * - Market API ticks arrive discretely (Step 1... Step 2)
 * - CPE (Chronomorphic Polytopal Engine) needs continuous fluid motion
 *
 * Solution:
 * - Use SLERP (Spherical Linear Interpolation) for 4D rotations
 * - Quaternions maintain constant angular velocity between keyframes
 * - The 4D rotation flows smoothly, hitting API-defined keyframes exactly
 */

import type { GeometricRotation, MarketTick, SyncedFrame } from './TimeBinder';

// ============================================================================
// Quaternion Implementation
// ============================================================================

/**
 * Quaternion for 3D/4D rotation representation
 * q = w + xi + yj + zk
 */
export class Quaternion {
  constructor(
    public w: number = 1,
    public x: number = 0,
    public y: number = 0,
    public z: number = 0
  ) {}

  /**
   * Create quaternion from axis-angle representation
   */
  static fromAxisAngle(axis: [number, number, number], angle: number): Quaternion {
    const halfAngle = angle / 2;
    const s = Math.sin(halfAngle);
    const len = Math.sqrt(axis[0] * axis[0] + axis[1] * axis[1] + axis[2] * axis[2]) || 1;

    return new Quaternion(
      Math.cos(halfAngle),
      (axis[0] / len) * s,
      (axis[1] / len) * s,
      (axis[2] / len) * s
    );
  }

  /**
   * Create quaternion from Euler angles (in radians)
   */
  static fromEuler(roll: number, pitch: number, yaw: number): Quaternion {
    const cr = Math.cos(roll / 2);
    const sr = Math.sin(roll / 2);
    const cp = Math.cos(pitch / 2);
    const sp = Math.sin(pitch / 2);
    const cy = Math.cos(yaw / 2);
    const sy = Math.sin(yaw / 2);

    return new Quaternion(
      cr * cp * cy + sr * sp * sy,
      sr * cp * cy - cr * sp * sy,
      cr * sp * cy + sr * cp * sy,
      cr * cp * sy - sr * sp * cy
    );
  }

  /**
   * Create identity quaternion (no rotation)
   */
  static identity(): Quaternion {
    return new Quaternion(1, 0, 0, 0);
  }

  /**
   * Clone this quaternion
   */
  clone(): Quaternion {
    return new Quaternion(this.w, this.x, this.y, this.z);
  }

  /**
   * Compute the magnitude (length) of the quaternion
   */
  magnitude(): number {
    return Math.sqrt(this.w * this.w + this.x * this.x + this.y * this.y + this.z * this.z);
  }

  /**
   * Normalize to unit quaternion
   */
  normalize(): Quaternion {
    const mag = this.magnitude();
    if (mag < 1e-10) return Quaternion.identity();

    return new Quaternion(
      this.w / mag,
      this.x / mag,
      this.y / mag,
      this.z / mag
    );
  }

  /**
   * Compute conjugate (inverse for unit quaternions)
   */
  conjugate(): Quaternion {
    return new Quaternion(this.w, -this.x, -this.y, -this.z);
  }

  /**
   * Multiply two quaternions (Hamilton product)
   */
  multiply(q: Quaternion): Quaternion {
    return new Quaternion(
      this.w * q.w - this.x * q.x - this.y * q.y - this.z * q.z,
      this.w * q.x + this.x * q.w + this.y * q.z - this.z * q.y,
      this.w * q.y - this.x * q.z + this.y * q.w + this.z * q.x,
      this.w * q.z + this.x * q.y - this.y * q.x + this.z * q.w
    );
  }

  /**
   * Dot product with another quaternion
   */
  dot(q: Quaternion): number {
    return this.w * q.w + this.x * q.x + this.y * q.y + this.z * q.z;
  }

  /**
   * Convert to Euler angles (radians)
   */
  toEuler(): [number, number, number] {
    // Roll (x-axis rotation)
    const sinr_cosp = 2 * (this.w * this.x + this.y * this.z);
    const cosr_cosp = 1 - 2 * (this.x * this.x + this.y * this.y);
    const roll = Math.atan2(sinr_cosp, cosr_cosp);

    // Pitch (y-axis rotation)
    const sinp = 2 * (this.w * this.y - this.z * this.x);
    const pitch = Math.abs(sinp) >= 1
      ? Math.sign(sinp) * Math.PI / 2  // Gimbal lock
      : Math.asin(sinp);

    // Yaw (z-axis rotation)
    const siny_cosp = 2 * (this.w * this.z + this.x * this.y);
    const cosy_cosp = 1 - 2 * (this.y * this.y + this.z * this.z);
    const yaw = Math.atan2(siny_cosp, cosy_cosp);

    return [roll, pitch, yaw];
  }

  /**
   * Convert to array representation [w, x, y, z]
   */
  toArray(): [number, number, number, number] {
    return [this.w, this.x, this.y, this.z];
  }

  /**
   * Create from array [w, x, y, z]
   */
  static fromArray(arr: [number, number, number, number]): Quaternion {
    return new Quaternion(arr[0], arr[1], arr[2], arr[3]);
  }
}

// ============================================================================
// SLERP Implementation
// ============================================================================

/**
 * Spherical Linear Interpolation between two quaternions
 *
 * SLERP maintains constant angular velocity, producing smooth rotations
 * that follow the shortest path on the 4D hypersphere.
 *
 * @param q0 Start quaternion
 * @param q1 End quaternion
 * @param t  Interpolation factor (0 = q0, 1 = q1)
 * @returns Interpolated quaternion
 */
export function slerp(q0: Quaternion, q1: Quaternion, t: number): Quaternion {
  // Clamp t to [0, 1]
  t = Math.max(0, Math.min(1, t));

  // Normalize inputs
  const a = q0.normalize();
  let b = q1.normalize();

  // Compute cosine of angle between quaternions
  let dot = a.dot(b);

  // If the dot product is negative, the quaternions have opposite handedness
  // and slerp won't take the shorter path. Fix by negating one quaternion.
  if (dot < 0) {
    b = new Quaternion(-b.w, -b.x, -b.y, -b.z);
    dot = -dot;
  }

  // If quaternions are very close, use linear interpolation to avoid division by zero
  const DOT_THRESHOLD = 0.9995;
  if (dot > DOT_THRESHOLD) {
    return new Quaternion(
      a.w + t * (b.w - a.w),
      a.x + t * (b.x - a.x),
      a.y + t * (b.y - a.y),
      a.z + t * (b.z - a.z)
    ).normalize();
  }

  // Compute the angle between quaternions
  const theta_0 = Math.acos(dot);           // Angle between input quaternions
  const theta = theta_0 * t;                // Angle at interpolation point
  const sin_theta = Math.sin(theta);
  const sin_theta_0 = Math.sin(theta_0);

  // Compute interpolation coefficients
  const s0 = Math.cos(theta) - dot * sin_theta / sin_theta_0;
  const s1 = sin_theta / sin_theta_0;

  return new Quaternion(
    s0 * a.w + s1 * b.w,
    s0 * a.x + s1 * b.x,
    s0 * a.y + s1 * b.y,
    s0 * a.z + s1 * b.z
  ).normalize();
}

/**
 * Normalized Linear Interpolation (NLERP)
 * Faster than SLERP but doesn't maintain constant velocity.
 * Use for small rotations or when performance is critical.
 */
export function nlerp(q0: Quaternion, q1: Quaternion, t: number): Quaternion {
  const a = q0.normalize();
  let b = q1.normalize();

  // Take shorter path
  if (a.dot(b) < 0) {
    b = new Quaternion(-b.w, -b.x, -b.y, -b.z);
  }

  return new Quaternion(
    a.w + t * (b.w - a.w),
    a.x + t * (b.x - a.x),
    a.y + t * (b.y - a.y),
    a.z + t * (b.z - a.z)
  ).normalize();
}

// ============================================================================
// 4D Rotation Representation (Rotor / Double Quaternion)
// ============================================================================

/**
 * 4D Rotor - Represents rotation in 4D space using two quaternions
 *
 * In 4D, rotations occur in 2D planes (not around axes).
 * We need 6 rotation planes: XY, XZ, XW, YZ, YW, ZW
 *
 * A rotor R = L * R' where L and R' are quaternions that
 * apply rotations from left and right.
 */
export class Rotor4D {
  constructor(
    public left: Quaternion = Quaternion.identity(),
    public right: Quaternion = Quaternion.identity()
  ) {}

  /**
   * Create a rotor from 6 plane rotation angles
   */
  static fromPlaneAngles(rotation: GeometricRotation): Rotor4D {
    // Decompose 4D rotation into two quaternions
    // Left quaternion handles XY, XZ, YZ planes (3D subspace)
    // Right quaternion handles XW, YW, ZW planes (W-involving rotations)

    const left = Quaternion.fromEuler(
      rotation.rotXY,
      rotation.rotXZ,
      rotation.rotYZ
    );

    const right = Quaternion.fromEuler(
      rotation.rotXW,
      rotation.rotYW,
      rotation.rotZW
    );

    return new Rotor4D(left, right);
  }

  /**
   * Convert back to plane angles
   */
  toPlaneAngles(): GeometricRotation {
    const [rotXY, rotXZ, rotYZ] = this.left.toEuler();
    const [rotXW, rotYW, rotZW] = this.right.toEuler();

    return { rotXY, rotXZ, rotXW, rotYZ, rotYW, rotZW };
  }

  /**
   * Clone this rotor
   */
  clone(): Rotor4D {
    return new Rotor4D(this.left.clone(), this.right.clone());
  }

  /**
   * Compose two rotors
   */
  multiply(r: Rotor4D): Rotor4D {
    return new Rotor4D(
      this.left.multiply(r.left),
      this.right.multiply(r.right)
    );
  }

  /**
   * Identity rotor (no rotation)
   */
  static identity(): Rotor4D {
    return new Rotor4D(Quaternion.identity(), Quaternion.identity());
  }
}

/**
 * SLERP for 4D rotors (double SLERP)
 */
export function slerpRotor4D(r0: Rotor4D, r1: Rotor4D, t: number): Rotor4D {
  return new Rotor4D(
    slerp(r0.left, r1.left, t),
    slerp(r0.right, r1.right, t)
  );
}

// ============================================================================
// GeometricLerp Class - The Smoother
// ============================================================================

export interface KeyframeData {
  timestamp: number;
  rotation: GeometricRotation;
  tick?: MarketTick;
}

export interface InterpolatedState {
  timestamp: number;
  rotation: GeometricRotation;
  rotor: Rotor4D;
  velocity: GeometricRotation;  // Angular velocity between keyframes
  interpolationFactor: number;
  keyframeA: KeyframeData | null;
  keyframeB: KeyframeData | null;
}

/**
 * GeometricLerp - Smooth 4D Geometric Interpolation Engine
 *
 * Maintains a timeline of keyframes and provides smooth interpolation
 * between them using spherical interpolation.
 */
export class GeometricLerp {
  private keyframes: KeyframeData[] = [];
  private maxKeyframes: number;
  private lastState: InterpolatedState | null = null;

  constructor(maxKeyframes: number = 100) {
    this.maxKeyframes = maxKeyframes;
  }

  /**
   * Add a new keyframe to the timeline
   */
  addKeyframe(data: KeyframeData): void {
    // Insert in sorted order by timestamp
    const insertIndex = this.keyframes.findIndex(k => k.timestamp > data.timestamp);

    if (insertIndex === -1) {
      this.keyframes.push(data);
    } else {
      this.keyframes.splice(insertIndex, 0, data);
    }

    // Trim old keyframes if over capacity
    while (this.keyframes.length > this.maxKeyframes) {
      this.keyframes.shift();
    }
  }

  /**
   * Add keyframe from a market tick
   */
  addFromTick(tick: MarketTick): void {
    this.addKeyframe({
      timestamp: tick.timestamp,
      rotation: tick.rotation,
      tick
    });
  }

  /**
   * Get interpolated state at a specific timestamp
   * This is the core SLERP operation
   */
  getState(timestamp: number): InterpolatedState {
    if (this.keyframes.length === 0) {
      return this.createEmptyState(timestamp);
    }

    if (this.keyframes.length === 1) {
      const k = this.keyframes[0];
      return {
        timestamp,
        rotation: { ...k.rotation },
        rotor: Rotor4D.fromPlaneAngles(k.rotation),
        velocity: this.createZeroRotation(),
        interpolationFactor: 0,
        keyframeA: k,
        keyframeB: null
      };
    }

    // Find bracketing keyframes
    const [kA, kB] = this.findBracket(timestamp);

    if (!kA) {
      return this.createEmptyState(timestamp);
    }

    if (!kB) {
      return {
        timestamp,
        rotation: { ...kA.rotation },
        rotor: Rotor4D.fromPlaneAngles(kA.rotation),
        velocity: this.createZeroRotation(),
        interpolationFactor: 0,
        keyframeA: kA,
        keyframeB: null
      };
    }

    // Check if timestamp exactly matches kA (exact keyframe hit)
    if (timestamp === kA.timestamp) {
      return {
        timestamp,
        rotation: { ...kA.rotation },
        rotor: Rotor4D.fromPlaneAngles(kA.rotation),
        velocity: this.computeVelocity(kA.rotation, kB.rotation, kB.timestamp - kA.timestamp),
        interpolationFactor: 0,
        keyframeA: kA,
        keyframeB: kB
      };
    }

    // Compute interpolation factor
    const duration = kB.timestamp - kA.timestamp;
    const t = duration > 0 ? (timestamp - kA.timestamp) / duration : 0;
    const clampedT = Math.max(0, Math.min(1, t));

    // Convert to rotors for SLERP
    const rotorA = Rotor4D.fromPlaneAngles(kA.rotation);
    const rotorB = Rotor4D.fromPlaneAngles(kB.rotation);

    // Perform double SLERP
    const interpolatedRotor = slerpRotor4D(rotorA, rotorB, clampedT);

    // Convert back to plane angles
    const rotation = interpolatedRotor.toPlaneAngles();

    // Compute angular velocity (radians per millisecond)
    const velocity = this.computeVelocity(kA.rotation, kB.rotation, duration);

    const state: InterpolatedState = {
      timestamp,
      rotation,
      rotor: interpolatedRotor,
      velocity,
      interpolationFactor: clampedT,
      keyframeA: kA,
      keyframeB: kB
    };

    this.lastState = state;
    return state;
  }

  /**
   * Get interpolated rotation at timestamp (convenience method)
   */
  getRotation(timestamp: number): GeometricRotation {
    return this.getState(timestamp).rotation;
  }

  /**
   * Integrate a SyncedFrame from TimeBinder, applying SLERP to its rotation
   */
  smoothFrame(frame: SyncedFrame): SyncedFrame {
    // Add keyframes from the source ticks
    if (frame.tickA) {
      this.addFromTick(frame.tickA);
    }
    if (frame.tickB) {
      this.addFromTick(frame.tickB);
    }

    // Get smoothed rotation
    const state = this.getState(frame.timestamp);

    return {
      ...frame,
      rotation: state.rotation
    };
  }

  /**
   * Clear all keyframes
   */
  clear(): void {
    this.keyframes = [];
    this.lastState = null;
  }

  /**
   * Get current keyframe count
   */
  get length(): number {
    return this.keyframes.length;
  }

  /**
   * Get time span of keyframes
   */
  getTimeSpan(): { start: number; end: number; duration: number } | null {
    if (this.keyframes.length < 2) return null;
    const start = this.keyframes[0].timestamp;
    const end = this.keyframes[this.keyframes.length - 1].timestamp;
    return { start, end, duration: end - start };
  }

  // ==========================================================================
  // Private Helpers
  // ==========================================================================

  private findBracket(timestamp: number): [KeyframeData | null, KeyframeData | null] {
    if (this.keyframes.length === 0) return [null, null];

    const first = this.keyframes[0];
    const last = this.keyframes[this.keyframes.length - 1];

    // Before first keyframe
    if (timestamp <= first.timestamp) {
      return [first, this.keyframes[1] || null];
    }

    // After last keyframe
    if (timestamp >= last.timestamp) {
      return [last, null];
    }

    // Binary search for bracket
    let left = 0;
    let right = this.keyframes.length - 1;

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

  private computeVelocity(
    a: GeometricRotation,
    b: GeometricRotation,
    duration: number
  ): GeometricRotation {
    if (duration <= 0) return this.createZeroRotation();

    return {
      rotXY: (b.rotXY - a.rotXY) / duration,
      rotXZ: (b.rotXZ - a.rotXZ) / duration,
      rotXW: (b.rotXW - a.rotXW) / duration,
      rotYZ: (b.rotYZ - a.rotYZ) / duration,
      rotYW: (b.rotYW - a.rotYW) / duration,
      rotZW: (b.rotZW - a.rotZW) / duration
    };
  }

  private createZeroRotation(): GeometricRotation {
    return { rotXY: 0, rotXZ: 0, rotXW: 0, rotYZ: 0, rotYW: 0, rotZW: 0 };
  }

  private createEmptyState(timestamp: number): InterpolatedState {
    return {
      timestamp,
      rotation: this.createZeroRotation(),
      rotor: Rotor4D.identity(),
      velocity: this.createZeroRotation(),
      interpolationFactor: 0,
      keyframeA: null,
      keyframeB: null
    };
  }
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Interpolate between two geometric rotations using SLERP
 */
export function slerpRotation(
  a: GeometricRotation,
  b: GeometricRotation,
  t: number
): GeometricRotation {
  const rotorA = Rotor4D.fromPlaneAngles(a);
  const rotorB = Rotor4D.fromPlaneAngles(b);
  const interpolated = slerpRotor4D(rotorA, rotorB, t);
  return interpolated.toPlaneAngles();
}

/**
 * Compute the angular distance between two rotations
 */
export function rotationDistance(a: GeometricRotation, b: GeometricRotation): number {
  const rotorA = Rotor4D.fromPlaneAngles(a);
  const rotorB = Rotor4D.fromPlaneAngles(b);

  // Combined distance from both quaternions
  const dotLeft = Math.abs(rotorA.left.dot(rotorB.left));
  const dotRight = Math.abs(rotorA.right.dot(rotorB.right));

  const angleLeft = 2 * Math.acos(Math.min(1, dotLeft));
  const angleRight = 2 * Math.acos(Math.min(1, dotRight));

  return Math.sqrt(angleLeft * angleLeft + angleRight * angleRight);
}

// ============================================================================
// Exports
// ============================================================================

export default GeometricLerp;

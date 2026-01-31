/**
 * Temporal Module - Phase-Locked Time Synchronization
 *
 * Provides the temporal infrastructure for synchronizing real-time
 * market data streams with high-frame-rate geometric projections.
 */

// Core TimeBinder
export {
  TimeBinder,
  RingBuffer,
  getTimeBinder,
  resetTimeBinder,
  type GeometricRotation,
  type PriceVector,
  type MarketTick,
  type SyncedFrame,
  type TimeBinderConfig
} from './TimeBinder';

// Geometric Interpolation (SLERP)
export {
  GeometricLerp,
  Quaternion,
  Rotor4D,
  slerp,
  nlerp,
  slerpRotor4D,
  slerpRotation,
  rotationDistance,
  type KeyframeData,
  type InterpolatedState
} from './GeometricLerp';

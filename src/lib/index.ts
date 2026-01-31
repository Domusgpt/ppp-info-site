/**
 * PPP Phase-Locked Stereoscopy Library
 *
 * A unified temporal architecture for synchronizing real-time market data
 * with 4D geometric projections on a millisecond-perfect timeline.
 *
 * Architecture:
 * ┌─────────────────────────────────────────────────────────────────┐
 * │                        Market API                               │
 * │                            ↓                                    │
 * │                     StereoscopicFeed                            │
 * │                     (The Data Prism)                            │
 * │                      ↙           ↘                              │
 * │            ┌─────────┐         ┌─────────┐                      │
 * │            │Left Eye │         │Right Eye│                      │
 * │            │ (Chart) │         │  (CPE)  │                      │
 * │            └────┬────┘         └────┬────┘                      │
 * │                 │                   │                           │
 * │            ChartData           TimeBinder                       │
 * │                                    ↓                            │
 * │                              GeometricLerp                      │
 * │                                (SLERP)                          │
 * │                                    ↓                            │
 * │                              4D Rotation                        │
 * └─────────────────────────────────────────────────────────────────┘
 *
 * Phase Lock Constraint:
 * - Chart crosshair movement triggers TimeBinder.seek(t)
 * - 4D geometry snaps to exact historical moment
 * - Both eyes show same "concept step"
 */

// Temporal module - Time synchronization
export * from './temporal';

// Fusion module - Data bifurcation
export * from './fusion';

// Convenience re-exports
export {
  getTimeBinder,
  getStereoscopicFeed
} from './fusion';

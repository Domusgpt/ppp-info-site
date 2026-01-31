/**
 * Fusion Module - Stereoscopic Data Bifurcation
 *
 * Splits incoming market data into two phase-locked visual streams:
 * - Left Eye: Standard 2D Chart visualization
 * - Right Eye: 4D Geometric Projection via TimeBinder → CPE
 */

// Stereoscopic Feed
export {
  StereoscopicFeed,
  DataPrism,
  getStereoscopicFeed,
  resetStereoscopicFeed,
  type RawApiTick,
  type IndexedTick,
  type ChartDataPoint,
  type CPERenderData,
  type CrosshairEvent,
  type StereoscopicFrame,
  type StereoscopicFeedConfig
} from './StereoscopicFeed';

// Re-export temporal types for convenience
export type {
  MarketTick,
  PriceVector,
  SyncedFrame,
  TimeBinderConfig,
  InterpolatedState,
  KeyframeData
} from './StereoscopicFeed';

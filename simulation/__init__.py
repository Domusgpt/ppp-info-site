"""
Hypersonic Defense Simulation Package

A demonstration of Spinor Manifold Tracking superiority over standard
Extended Kalman Filters when tracking maneuvering Hypersonic Glide Vehicles (HGVs).

Based on the Polytopal Projection Processing (PPP) 4D geometric framework.

Copyright (c) 2025 Paul Phillips - Clear Seas Solutions LLC
"""

from .trajectory import HGVTrajectory, generate_skip_glide_trajectory
from .sensor import RadarSensor, add_plasma_noise, add_jamming
from .kalman import ExtendedKalmanFilter
from .spinor_track import SpinorManifoldTracker, DualQuaternion
from .main import run_simulation, compare_trackers

__version__ = "1.0.0"
__author__ = "Paul Phillips"

__all__ = [
    "HGVTrajectory",
    "generate_skip_glide_trajectory",
    "RadarSensor",
    "add_plasma_noise",
    "add_jamming",
    "ExtendedKalmanFilter",
    "SpinorManifoldTracker",
    "DualQuaternion",
    "run_simulation",
    "compare_trackers",
]

"""
HGV Trajectory Physics Engine

Generates realistic Hypersonic Glide Vehicle trajectories using a skip-glide
aerodynamic model with high-g bank-to-turn maneuvers.

Reference dynamics based on generic HGV characteristics:
- Cruise velocity: Mach 5-10 (1700-3400 m/s)
- Cruise altitude: 30-60 km
- Maneuver capability: 10-30g lateral acceleration
- L/D ratio: 2-4 typical for waverider configurations
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional


# Physical constants
EARTH_RADIUS = 6371000  # meters
GRAVITY = 9.81  # m/s^2
MACH_1 = 343  # m/s at sea level (approximate)
AIR_DENSITY_SEA_LEVEL = 1.225  # kg/m^3


@dataclass
class HGVState:
    """Complete state vector for an HGV at a given time."""

    position: np.ndarray  # [x, y, z] in meters
    velocity: np.ndarray  # [vx, vy, vz] in m/s
    acceleration: np.ndarray = field(default_factory=lambda: np.zeros(3))
    time: float = 0.0

    @property
    def speed(self) -> float:
        return np.linalg.norm(self.velocity)

    @property
    def mach(self) -> float:
        return self.speed / MACH_1

    @property
    def altitude(self) -> float:
        return self.position[2]

    def copy(self) -> 'HGVState':
        return HGVState(
            position=self.position.copy(),
            velocity=self.velocity.copy(),
            acceleration=self.acceleration.copy(),
            time=self.time
        )


@dataclass
class HGVTrajectory:
    """Container for a complete HGV trajectory."""

    states: List[HGVState] = field(default_factory=list)
    dt: float = 0.1  # Time step in seconds

    @property
    def positions(self) -> np.ndarray:
        return np.array([s.position for s in self.states])

    @property
    def velocities(self) -> np.ndarray:
        return np.array([s.velocity for s in self.states])

    @property
    def accelerations(self) -> np.ndarray:
        return np.array([s.acceleration for s in self.states])

    @property
    def times(self) -> np.ndarray:
        return np.array([s.time for s in self.states])

    def __len__(self) -> int:
        return len(self.states)

    def __getitem__(self, idx) -> HGVState:
        return self.states[idx]


def atmospheric_density(altitude: float) -> float:
    """
    Exponential atmosphere model for density.

    Args:
        altitude: Height above sea level in meters

    Returns:
        Air density in kg/m^3
    """
    scale_height = 8500  # meters
    return AIR_DENSITY_SEA_LEVEL * np.exp(-altitude / scale_height)


def compute_aerodynamic_forces(
    velocity: np.ndarray,
    altitude: float,
    bank_angle: float,
    lift_to_drag: float = 3.0,
    reference_area: float = 5.0,
    mass: float = 1000.0
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute aerodynamic lift and drag forces on the HGV.

    Args:
        velocity: Velocity vector [vx, vy, vz]
        altitude: Current altitude in meters
        bank_angle: Bank angle in radians (0 = wings level)
        lift_to_drag: L/D ratio of the vehicle
        reference_area: Reference area in m^2
        mass: Vehicle mass in kg

    Returns:
        Tuple of (lift_accel, drag_accel) as acceleration vectors
    """
    speed = np.linalg.norm(velocity)
    if speed < 1.0:
        return np.zeros(3), np.zeros(3)

    # Dynamic pressure
    rho = atmospheric_density(altitude)
    q = 0.5 * rho * speed**2

    # Drag coefficient (simplified)
    cd = 0.02  # Base drag coefficient
    drag_force = q * reference_area * cd
    drag_accel = -drag_force / mass * (velocity / speed)

    # Lift force (perpendicular to velocity, rotated by bank angle)
    cl = cd * lift_to_drag
    lift_force = q * reference_area * cl

    # Lift direction: perpendicular to velocity in vertical plane, rotated by bank
    vel_horizontal = np.array([velocity[0], velocity[1], 0])
    vel_h_norm = np.linalg.norm(vel_horizontal)

    if vel_h_norm > 1.0:
        # Unit vector perpendicular to velocity in horizontal plane
        perp_horizontal = np.array([-velocity[1], velocity[0], 0]) / vel_h_norm

        # Lift has vertical and lateral components based on bank angle
        lift_vertical = np.array([0, 0, 1]) * np.cos(bank_angle)
        lift_lateral = perp_horizontal * np.sin(bank_angle)
        lift_direction = lift_vertical + lift_lateral
        lift_direction = lift_direction / np.linalg.norm(lift_direction)
    else:
        lift_direction = np.array([0, 0, 1])

    lift_accel = lift_force / mass * lift_direction

    return lift_accel, drag_accel


def generate_skip_glide_trajectory(
    initial_position: np.ndarray = None,
    initial_velocity: np.ndarray = None,
    mach_number: float = 8.0,
    initial_altitude: float = 50000.0,
    duration: float = 60.0,
    dt: float = 0.1,
    maneuver_time: float = 30.0,
    maneuver_g: float = 15.0,
    maneuver_duration: float = 5.0,
    heading_change: float = 45.0
) -> HGVTrajectory:
    """
    Generate a realistic skip-glide HGV trajectory with a bank-to-turn maneuver.

    The trajectory includes:
    1. Initial glide phase
    2. Sharp bank-to-turn maneuver at maneuver_time
    3. Recovery and continued glide

    Args:
        initial_position: Starting [x, y, z] position (default: origin at altitude)
        initial_velocity: Starting velocity (default: Mach 8 heading north)
        mach_number: Initial Mach number
        initial_altitude: Starting altitude in meters
        duration: Total simulation duration in seconds
        dt: Time step in seconds
        maneuver_time: Time at which maneuver begins
        maneuver_g: Peak lateral g-force during maneuver
        maneuver_duration: Duration of the maneuver in seconds
        heading_change: Total heading change in degrees

    Returns:
        HGVTrajectory containing the complete state history
    """
    # Default initial conditions
    if initial_position is None:
        initial_position = np.array([0.0, 0.0, initial_altitude])
    if initial_velocity is None:
        speed = mach_number * MACH_1
        initial_velocity = np.array([speed, 0.0, 0.0])  # Heading east

    trajectory = HGVTrajectory(dt=dt)

    # Initial state
    state = HGVState(
        position=initial_position.copy(),
        velocity=initial_velocity.copy(),
        time=0.0
    )
    trajectory.states.append(state.copy())

    # Vehicle parameters
    mass = 1000.0  # kg
    lift_to_drag = 3.0
    reference_area = 5.0  # m^2

    # Integration loop
    t = 0.0
    while t < duration:
        t += dt

        # Determine bank angle based on maneuver schedule
        if maneuver_time <= t < maneuver_time + maneuver_duration:
            # Smooth bank-to-turn maneuver using sinusoidal profile
            maneuver_progress = (t - maneuver_time) / maneuver_duration

            # Target bank angle to achieve desired g-force
            speed = np.linalg.norm(state.velocity)
            required_centripetal = maneuver_g * GRAVITY
            turn_radius = speed**2 / required_centripetal

            # Sinusoidal bank angle profile for smooth entry/exit
            bank_envelope = np.sin(np.pi * maneuver_progress)
            target_bank = np.arctan2(required_centripetal, GRAVITY)
            bank_angle = target_bank * bank_envelope
        else:
            # Level flight with small bank for skip-glide oscillation
            skip_freq = 0.05  # Hz
            bank_angle = 0.05 * np.sin(2 * np.pi * skip_freq * t)

        # Compute aerodynamic accelerations
        lift_accel, drag_accel = compute_aerodynamic_forces(
            state.velocity,
            state.position[2],
            bank_angle,
            lift_to_drag,
            reference_area,
            mass
        )

        # Gravity
        gravity_accel = np.array([0, 0, -GRAVITY])

        # Total acceleration
        total_accel = lift_accel + drag_accel + gravity_accel

        # Simple Euler integration (sufficient for trajectory generation)
        new_velocity = state.velocity + total_accel * dt
        new_position = state.position + state.velocity * dt + 0.5 * total_accel * dt**2

        # Prevent going below ground
        if new_position[2] < 0:
            new_position[2] = 0
            new_velocity[2] = max(0, new_velocity[2])

        # Create new state
        state = HGVState(
            position=new_position,
            velocity=new_velocity,
            acceleration=total_accel,
            time=t
        )
        trajectory.states.append(state.copy())

    return trajectory


def generate_evasive_trajectory(
    base_trajectory: HGVTrajectory,
    evasion_amplitude: float = 500.0,
    evasion_frequency: float = 0.1
) -> HGVTrajectory:
    """
    Add evasive weaving to a base trajectory.

    Args:
        base_trajectory: The base trajectory to modify
        evasion_amplitude: Maximum lateral deviation in meters
        evasion_frequency: Frequency of weaving in Hz

    Returns:
        Modified trajectory with evasive maneuvers
    """
    modified = HGVTrajectory(dt=base_trajectory.dt)

    for state in base_trajectory.states:
        # Add sinusoidal lateral weaving
        lateral_offset = evasion_amplitude * np.sin(
            2 * np.pi * evasion_frequency * state.time
        )

        # Compute perpendicular direction to velocity in horizontal plane
        vel_h = np.array([state.velocity[0], state.velocity[1], 0])
        vel_h_norm = np.linalg.norm(vel_h)

        if vel_h_norm > 1.0:
            perp = np.array([-state.velocity[1], state.velocity[0], 0])
            perp = perp / np.linalg.norm(perp)
        else:
            perp = np.array([0, 1, 0])

        new_state = state.copy()
        new_state.position = state.position + perp * lateral_offset

        # Adjust velocity for the weaving motion
        weave_velocity = evasion_amplitude * 2 * np.pi * evasion_frequency * np.cos(
            2 * np.pi * evasion_frequency * state.time
        )
        new_state.velocity = state.velocity + perp * weave_velocity

        modified.states.append(new_state)

    return modified


if __name__ == "__main__":
    # Test trajectory generation
    traj = generate_skip_glide_trajectory(
        mach_number=8.0,
        duration=60.0,
        maneuver_time=25.0,
        maneuver_g=15.0
    )

    print(f"Generated trajectory with {len(traj)} states")
    print(f"Initial: pos={traj[0].position}, vel={traj[0].velocity}")
    print(f"At maneuver: pos={traj[250].position}, mach={traj[250].mach:.1f}")
    print(f"Final: pos={traj[-1].position}, mach={traj[-1].mach:.1f}")

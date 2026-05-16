from utils import ProgressBar, RegexFilter
from enums import Variance, FlightOutcome
import dill
import random
import datetime
from typing import Callable, Optional, Literal
from dataclasses import dataclass
from rocketpy import Flight, Environment, Rocket, SolidMotor
import os
from dotenv import load_dotenv
from cartopy.io.img_tiles import MapboxTiles
import cartopy.crs as ccrs
from numpy.typing import NDArray
import numpy as np

from matplotlib.figure import Figure
from matplotlib.axes import Axes
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt

import matplotlib.pyplot as plt
import scienceplots

# nice scientific styling
plt.style.use("science")
# match report font size
plt.rcParams.update({
    "font.size": 10,
    "axes.titlesize": 10,
    "axes.labelsize": 10,
    "legend.fontsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
})
# match report font
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica"]
})

#
# Constants
#

MPH_TO_MS = 0.44704
KPH_TO_MS = 0.277778
NM_TO_M = 1852

#
# Failure Probability
#


class _FailureProbability:
    # Simple (single motor failure) not Complex
    def __init__(self, filename: str) -> None:
        import pandas as pd

        self.df = pd.read_excel(
            filename,
            sheet_name="probability",
            usecols="B:M",
            nrows=6,
            skiprows=0,
            header=0,
            index_col=0
        )

    def lookup_failure_probability(
            self,
            motor: Literal[
                "MM", "1/4A", "1/2A", "A", "B", "C", "D", "E", "F", "G", "H"
            ],
            failure_mode: Literal[
                "lawn dart", "core sample", "separation", "shred", "motor CATO", "no  chute"
            ],
            enforce_minimum_probability: float = 0
    ) -> float:
        return max(
            float(self.df.loc[failure_mode, motor]),  # type: ignore
            enforce_minimum_probability
        )


FailureProbability = _FailureProbability("./data/probability.xlsx")

#
# Input Handling
#


def normal(var: float):
    return lambda x: np.random.normal(x, var)


def normal_fraction(var_frac: float):
    return lambda x: np.random.normal(x, x*var_frac)


def uniform(low: float, high: float):
    return lambda x: np.random.uniform(low, high)


def delay_distribution():
    def foo(delay):
        rand = min(np.random.normal(0, 0.06), 0.2)
        return delay + min(rand * delay, 1)
    return foo


class In:
    def __init__(self, ideal: float, random: Optional[Callable[[float], float]] = None) -> None:
        self.ideal = ideal
        self.random_func = random

    @property
    def random(self) -> float:
        if self.random_func:
            return self.random_func(self.ideal)
        return self.ideal

    def value(self, use_random: bool) -> float:
        return self.random if use_random else self.ideal
#
# Dataclasses
#


@dataclass
class FlightCls:
    rail_length: In
    inclination: In
    heading: In


@dataclass
class EnvironmentCls:
    latitude: In  # [deg]
    longitude: In  # [deg]
    elevation: In  # above sea level [m]
    # direction the wind is coming from [deg from North]
    wind_heading: Optional[In] = None
    wind_speed: Optional[In] = None  # [m/s]
    reanalysis_filename: Optional[str] = None
    date: Optional[tuple[int, int, int, int]] = None

    def __post_init__(self):
        if self.reanalysis_filename is None and (self.wind_heading is None or self.wind_speed is None):
            raise ValueError(
                "At least one of 'wind_heading', 'wind_speed' and 'reanalysis_filename' must be provided"
            )


@dataclass
class RocketCls:
    radius: In  # [m]
    mass: In  # [kg]
    inertia: tuple[In, In, In]  # [m] about cg
    power_off_drag: str  # filepath
    power_on_drag: str  # filepath
    center_of_mass_without_motor: In


@dataclass
class RailButtonCls:
    upper_button_position: In  # [m]
    lower_button_position: In  # [m]
    angular_position: In  # [deg]


@dataclass
class NoseCls:
    length: In
    kind: Literal["ogive", "conical", "lvhaack", "von karman"]


@dataclass
class FinSetCls:
    n: int
    root_chord: In  # [m]
    tip_chord: In  # [m]
    span: In  # [m]
    position: In  # [m]
    sweep_length: In  # [m]
    airfoil: Optional[tuple[str, str]] = None


@dataclass
class TailCls:
    fwd_radius: In  # [m]
    aft_radius: In  # [m]
    length: In  # [m]
    position: In  # [m]


@dataclass
class TransitionCls(TailCls):
    pass


@dataclass
class ParachuteCls:
    radius: In  # [m]
    trigger_type: Literal["altitude", "motor ejection", "apogee"]
    lag: In = In(0.01)  # [s] setting to 0 may cause the simulation to fail
    sampling_rate: In = In(100)  # [Hz]
    trigger_altitude: Optional[In] = None  # [m]
    motor_ejection_delay: Optional[In] = None  # [s]
    cd: Optional[In] = None
    cd_s: Optional[In] = None

    def __post_init__(self):
        if self.cd is None and self.cd_s is None:
            raise ValueError(
                "At least one of 'cd' and 'cd_s' must be provided.")
        if self.trigger_type == "altitude" and self.trigger_altitude is None:
            raise ValueError(
                "'trigger altitude' must be provided when 'trigger type'=='altitude'")
        if self.trigger_type == "motor ejection" and self.motor_ejection_delay is None:
            raise ValueError(
                "'motor ejection delay' must be provided when 'trigger type'=='motor ejection'")


@dataclass
class MotorCls:
    thrust_source: str
    diameter: In  # [m]
    length: In  # [m]
    total_mass: In  # [kg]
    prop_mass: In  # [kg]
    burn_time: In  # [s]
    scaled_burn_time: In  # [s]
    scaled_total_impulse: In  # [Ns]
    position: In  # [m]
    grain_number: int = 1
    thrust_eccentricity_distance_from_centerline: In = In(0)  # [m]
    thrust_eccentricity_angle_from_centerline: In = In(0)  # [deg]

#
# Utility functions
#


def get_motor_class(total_impulse: float, max_class: str = "Z") -> str:
    """
    Compute motor class from total impulse

    Args:
        total_impulse (float): Total impulse in Ns
        max_class: Clips to maximum class

    Returns:
        str: Motor class (A–O)
    """
    if total_impulse <= 0:
        raise ValueError(f"Total Impulse of {total_impulse}Ns is out of range")

    # Calculate class index
    idx = int(np.floor(np.log2(total_impulse / 2.5)))

    return chr(min(ord('A') + idx, ord(max_class)))


def wind_heading_components(heading, speed) -> tuple[float, float]:
    heading_rad = np.radians(heading)

    north = speed * np.cos(heading_rad)
    east = speed * np.sin(heading_rad)

    return north, east


def motor_from_thrust_curve(
    thrust_source: str,
    diameter: float,
    length: float,
    total_mass: float,
    prop_mass: float,
    burn_time: float,
    scaled_burn_time: Optional[float] = None,
    scaled_total_impulse: Optional[float] = None,
    grain_number: int = 1,
):
    """helper function to estimate the properties required by `rocketpy.SolidMotor` from thrustcurve.org publicly available data and return a `SolidMotor` object for use in simulations

    The thrust will be scaled to the provided burn time and total impulse.

    Workflow
    1. Download RASP thrust source file from thrustcurve.org
    2. Copy required parameters from thrustcurve.org
    3. Verify grain count from csrocketry.com

    Args:
        thrust_source: filename
        diameter: motor outer diameter [m]
        length: outer length [m]
        total_mass: total mass [kg]
        prop_mass: propellent mass [kg]
        burn_time: burn time [s]
        scaled_burn_time: burn time [s]
        scaled_total_impulse: total impulse [Ns]
        grain_number: number of propellent grains. Defaults to 1.

    Returns:
        `rocketpy.SolidMotor`
    """
    # fixed assumptions
    grain_separation = 2 / 1000

    # calculations
    dry_mass = total_mass - prop_mass
    radius = diameter / 2
    throat_radius = radius * 0.25
    nozzle_radius = radius * 0.8
    grain_initial_inner_radius = radius * 0.25
    grain_outer_radius = radius * 0.75
    length_nozzle = ((nozzle_radius - throat_radius)/np.tan(np.deg2rad(45))) + \
        ((nozzle_radius - throat_radius)/np.tan(np.deg2rad(15)))
    length_grains = length - length_nozzle
    grain_height = length_grains / grain_number - grain_separation
    grain_volume = length_grains * np.pi * \
        (grain_outer_radius**2 - grain_initial_inner_radius**2)
    grain_density = prop_mass / grain_volume
    grain_center_of_mass_position = 0.5 * length_grains
    Ixx = 0.5 * dry_mass * grain_outer_radius**2
    Iyy = Izz = (1/12) * dry_mass * \
        (3*grain_outer_radius**2 + length_grains**2)
    centre_of_dry_mass_position = (0.5 * length) - length_nozzle

    if scaled_burn_time is not None and scaled_total_impulse is not None:
        reshape_thrust_curve = [scaled_burn_time, scaled_total_impulse]
    else:
        reshape_thrust_curve = False

    motor = SolidMotor(
        thrust_source=thrust_source,
        dry_mass=dry_mass,
        dry_inertia=(Izz, Iyy, Ixx),
        nozzle_radius=nozzle_radius,
        grain_number=grain_number,
        grain_density=grain_density,
        grain_outer_radius=grain_outer_radius,
        grain_initial_inner_radius=grain_initial_inner_radius,
        grain_initial_height=grain_height,
        grain_separation=grain_separation,
        grains_center_of_mass_position=grain_center_of_mass_position,
        center_of_dry_mass_position=centre_of_dry_mass_position,
        throat_radius=throat_radius,
        burn_time=burn_time,
        nozzle_position=-length_nozzle,
        coordinate_system_orientation="nozzle_to_combustion_chamber",
        reshape_thrust_curve=reshape_thrust_curve,  # type: ignore
    )

    position_offset = length_grains

    # create motor object
    return motor, position_offset

#
# Stochastic Generator
#


class FlightManager:
    def __init__(
            self,
            flight: FlightCls,
            env: EnvironmentCls,
            motor: MotorCls,
            rocket: RocketCls,
            rail_button: RailButtonCls,
            nose: NoseCls,
            fin_set: FinSetCls,
            main_parachute: ParachuteCls,
            *,
            transition: Optional[TransitionCls] = None,
            tail: Optional[TailCls] = None,
            drogue_parachute: Optional[ParachuteCls] = None
    ) -> None:
        self.flight = flight
        self.env = env
        self.motor = motor
        self.rocket = rocket
        self.rail_button = rail_button
        self.nose = nose
        self.transition = transition
        self.fin_set = fin_set
        self.tail = tail
        self.main_parachute = main_parachute
        self.drogue_parachute = drogue_parachute

    def ideal_flight(
        self, *,
        draw: bool = False,
        draw_filename: Optional[str] = None,
        plot_trajectory: Optional[str] = None,
        plot_trajectory_2d: Optional[str] = None
    ):
        return self.monte_flight(
            [], draw=draw, plot_trajectory=plot_trajectory, draw_filename=draw_filename,
            plot_trajectory_2d=plot_trajectory_2d
        )

    def draw_rocket(self, filename: Optional[str] = None):
        return self.ideal_flight(draw=True, draw_filename=filename)

    def monte_flight(
            self,
            to_vary: list[Variance] = [
                Variance.PERFORMANCE,
                Variance.ENVIRONMENT,
                Variance.FLIGHT_EVENT,
                Variance.LAUNCH,
                Variance.DESIGN_AND_MANUFACTURING
            ],
            *,
            draw: bool = False,
            verbose: bool = False,
            draw_filename: Optional[str] = None,
            plot_trajectory: Optional[str] = None,
            plot_trajectory_2d: Optional[str] = None
    ) -> tuple[float, float, float, float, FlightOutcome]:
        vPerformance = Variance.PERFORMANCE in to_vary
        vEnvironment = Variance.ENVIRONMENT in to_vary
        vFlightEvent = Variance.FLIGHT_EVENT in to_vary
        vLaunch = Variance.LAUNCH in to_vary
        vDesignAndManufacture = Variance.DESIGN_AND_MANUFACTURING in to_vary

        total_impulse = self.motor.scaled_total_impulse.value(vPerformance)
        scaled_burn_time = self.motor.scaled_burn_time.value(vPerformance)

        # failure mode
        if vFlightEvent:
            motor_class = get_motor_class(total_impulse, 'H')
            probabilities = [
                FailureProbability.lookup_failure_probability(
                    motor=motor_class,  # type: ignore
                    failure_mode=mode,  # type: ignore
                    enforce_minimum_probability=0.005
                ) for mode in [
                    "lawn dart", "core sample", "separation", "shred", "motor CATO", "no chute"
                ]
            ]
            probabilities.append(1 - sum(probabilities))

            failure_mode = random.choices(
                population=[
                    FlightOutcome.LAWN_DART,
                    FlightOutcome.CORE_SAMPLE,
                    FlightOutcome.SEPARATION,
                    FlightOutcome.SHRED,
                    FlightOutcome.MOTOR_CATO,
                    FlightOutcome.NO_CHUTE,
                    FlightOutcome.NOMINAL
                ],
                weights=probabilities
            )[0]

        else:
            failure_mode = FlightOutcome.NOMINAL

        if verbose:
            print(f"mode={failure_mode.name}")

        if failure_mode == FlightOutcome.MOTOR_CATO:
            burn_time = scaled_burn_time
            fail_time = np.random.uniform(0.05, min(0.5, burn_time*0.4))
            total_impulse = total_impulse * (fail_time/burn_time)
            scaled_burn_time = burn_time

        # define motor
        motor, motor_offset = motor_from_thrust_curve(
            thrust_source=self.motor.thrust_source,
            diameter=self.motor.diameter.value(vPerformance),
            length=self.motor.length.value(vPerformance),
            total_mass=self.motor.total_mass.value(vPerformance),
            prop_mass=self.motor.prop_mass.value(vPerformance),
            burn_time=self.motor.burn_time.value(vPerformance),
            scaled_burn_time=scaled_burn_time,
            scaled_total_impulse=total_impulse,
            grain_number=self.motor.grain_number
        )

        # define rocket
        rocket = Rocket(
            radius=self.rocket.radius.value(vDesignAndManufacture),
            mass=self.rocket.mass.value(vDesignAndManufacture),
            inertia=(
                self.rocket.inertia[0].value(vDesignAndManufacture),
                self.rocket.inertia[1].value(vDesignAndManufacture),
                self.rocket.inertia[2].value(vDesignAndManufacture)
            ),
            power_off_drag=self.rocket.power_off_drag,
            power_on_drag=self.rocket.power_on_drag,
            center_of_mass_without_motor=self.rocket.center_of_mass_without_motor.value(
                vDesignAndManufacture),
            coordinate_system_orientation="nose_to_tail",
        )

        rocket.add_motor(
            motor,
            position=self.motor.position.value(
                vDesignAndManufacture) + motor_offset,
        )

        # distance from centreline not thrust misalignment angle
        d = self.motor.thrust_eccentricity_distance_from_centerline.value(
            vDesignAndManufacture)
        a = np.radians(self.motor.thrust_eccentricity_angle_from_centerline.value(
            vDesignAndManufacture))
        rocket.add_thrust_eccentricity(
            x=d * np.cos(a),  # yaw
            y=d * np.sin(a)  # pitch
        )

        rail_buttons = rocket.set_rail_buttons(
            upper_button_position=self.rail_button.upper_button_position.value(
                vDesignAndManufacture),
            lower_button_position=self.rail_button.lower_button_position.value(
                vDesignAndManufacture),
            angular_position=self.rail_button.angular_position.value(
                vDesignAndManufacture)  # type: ignore
        )

        nose = rocket.add_nose(
            length=self.nose.length.value(vDesignAndManufacture),
            kind=self.nose.kind,
            position=0
        )

        if self.transition:
            transition = rocket.add_tail(
                top_radius=self.transition.fwd_radius.value(
                    vDesignAndManufacture),
                bottom_radius=self.transition.aft_radius.value(
                    vDesignAndManufacture),
                length=self.transition.length.value(vDesignAndManufacture),
                position=self.transition.position.value(vDesignAndManufacture)
            )

        fin_set = rocket.add_trapezoidal_fins(
            n=self.fin_set.n,
            root_chord=self.fin_set.root_chord.value(vDesignAndManufacture),
            tip_chord=self.fin_set.tip_chord.value(vDesignAndManufacture),
            span=self.fin_set.span.value(vDesignAndManufacture),
            position=self.fin_set.position.value(vDesignAndManufacture),
            sweep_length=self.fin_set.sweep_length.value(
                vDesignAndManufacture),
            airfoil=self.fin_set.airfoil
        )

        if self.tail:
            tail = rocket.add_tail(
                top_radius=self.tail.fwd_radius.value(vDesignAndManufacture),
                bottom_radius=self.tail.aft_radius.value(
                    vDesignAndManufacture),
                length=self.tail.length.value(vDesignAndManufacture),
                position=self.tail.position.value(vDesignAndManufacture),
            )

        if failure_mode not in [FlightOutcome.LAWN_DART, FlightOutcome.CORE_SAMPLE, FlightOutcome.SHRED]:
            # handle parachute deployment method
            parachute = self.main_parachute
            if parachute.trigger_type == "motor ejection":
                motor_ejection_delay = (
                    parachute.motor_ejection_delay.value(  # type: ignore
                        vPerformance))
                motor_burn_time = motor.burn_out_time  # type: ignore
                lag = parachute.lag.value(vDesignAndManufacture)
                lag = motor_ejection_delay + motor_burn_time + lag
                def trigger(p, h, y): return y[5] > 0
            elif parachute.trigger_type == "altitude":
                lag = parachute.lag.value(vDesignAndManufacture)
                trigger = (
                    parachute.trigger_altitude.value(  # type: ignore
                        vDesignAndManufacture))
            elif parachute.trigger_type == "apogee":
                lag = parachute.lag.value(
                    vDesignAndManufacture)  # type: ignore
                trigger = "apogee"  # type: ignore

            # estimate cd_s from cd and radius if needed
            if failure_mode == FlightOutcome.SEPARATION:
                radius = 0.01
                cd_s = 0.01
            else:
                radius = parachute.radius.value(vDesignAndManufacture)
                if parachute.cd_s is None:
                    cd = parachute.cd.value(  # type: ignore
                        vDesignAndManufacture)
                    s = np.pi * radius**2
                    cd_s = cd * s
                else:
                    cd_s = parachute.cd_s.value(vDesignAndManufacture)

            main = rocket.add_parachute(
                name="main",
                cd_s=cd_s,
                trigger=trigger,
                sampling_rate=int(
                    parachute.sampling_rate.value(vDesignAndManufacture)),
                lag=max(lag, 0.01),  # type: ignore
                radius=radius,
            )

        # drogue parachute
        if failure_mode not in [FlightOutcome.LAWN_DART, FlightOutcome.CORE_SAMPLE, FlightOutcome.SHRED] and self.drogue_parachute is not None:
            # handle parachute deployment method
            parachute = self.drogue_parachute
            if parachute.trigger_type == "motor ejection":
                motor_ejection_delay = (
                    parachute.motor_ejection_delay.value(  # type: ignore
                        vPerformance))
                motor_burn_time = motor.burn_out_time  # type: ignore
                lag = parachute.lag.value(vDesignAndManufacture)
                lag = motor_ejection_delay + motor_burn_time + lag
                def trigger(p, h, y): return y[5] > 0
            elif parachute.trigger_type == "altitude":
                lag = parachute.lag.value(vDesignAndManufacture)
                trigger = (
                    parachute.trigger_altitude.value(  # type: ignore
                        vDesignAndManufacture))
            elif parachute.trigger_type == "apogee":
                lag = parachute.lag.value(
                    vDesignAndManufacture)  # type: ignore
                trigger = "apogee"  # type: ignore

            # estimate cd_s from cd and radius if needed
            if failure_mode == FlightOutcome.SEPARATION:
                radius = 0.01
                cd_s = 0.01
            else:
                radius = parachute.radius.value(vDesignAndManufacture)
                if parachute.cd_s is None:
                    cd = parachute.cd.value(  # type: ignore
                        vDesignAndManufacture)
                    s = np.pi * radius**2
                    cd_s = cd * s
                else:
                    cd_s = parachute.cd_s.value(vDesignAndManufacture)

            drogue = rocket.add_parachute(
                name="drogue",
                cd_s=cd_s,
                trigger=trigger,
                sampling_rate=int(
                    parachute.sampling_rate.value(vDesignAndManufacture)),
                lag=max(lag, 0.01),  # type: ignore
                radius=radius,
            )

        # simulate core sample (nose only ejection)
        if failure_mode in [FlightOutcome.CORE_SAMPLE, FlightOutcome.NO_CHUTE]:
            if self.drogue_parachute is None:
                parachute = self.main_parachute
            else:
                parachute = self.drogue_parachute

            if parachute.trigger_type == "motor ejection":
                motor_ejection_delay = (
                    parachute.motor_ejection_delay.value(  # type: ignore
                        vPerformance))
                motor_burn_time = motor.burn_out_time  # type: ignore
                lag = parachute.lag.value(vDesignAndManufacture)
                lag = motor_ejection_delay + motor_burn_time + lag
                def trigger(p, h, y): return y[5] > 0
            elif parachute.trigger_type == "altitude":
                lag = parachute.lag.value(vDesignAndManufacture)
                trigger = (
                    parachute.trigger_altitude.value(  # type: ignore
                        vDesignAndManufacture))
            elif parachute.trigger_type == "apogee":
                lag = parachute.lag.value(
                    vDesignAndManufacture)  # type: ignore
                trigger = "apogee"  # type: ignore

            rocket_radius = self.rocket.radius.ideal
            rocket_length = self.fin_set.position.ideal + self.fin_set.span.ideal

            if failure_mode == FlightOutcome.CORE_SAMPLE:
                cross_sectional_area = rocket_radius**2 * np.pi
                cd_s = 1.5 * cross_sectional_area
            elif failure_mode == FlightOutcome.NO_CHUTE:
                cross_sectional_area = rocket_radius*2 * rocket_length
                cd_s = 1.0 * cross_sectional_area

            core_sample_sim = rocket.add_parachute(
                name="core sample parachute",
                cd_s=cd_s,
                trigger=trigger,
                sampling_rate=int(parachute.sampling_rate.ideal),
                lag=max(lag, 0.01),  # type: ignore
                radius=rocket_radius,
            )

        if failure_mode == FlightOutcome.SHRED:
            shred_time = motor.burn_out_time * np.random.uniform(0.1, 0.9)
            shred_drag_coefficient = 10

            def shred_controller_function(
                    time, sampling_rate, state, state_history, observed_variables, air_brakes
            ):
                if time > shred_time:
                    air_brakes.deployment_level = 1

            def drag_coefficient(lvl, mach): return shred_drag_coefficient
            air_brakes = rocket.add_air_brakes(
                drag_coefficient_curve=drag_coefficient,
                controller_function=shred_controller_function,
                sampling_rate=100,
                initial_observed_variables=[0, 0, 0],
                name="Shred Air Brake",
            )

        if draw:
            rocket.plots.draw(
                vis_args={
                    "background": "#FFFFFF",
                    # "background": "#E1E1E1",
                    "tail": "black",
                    "nose": "black",
                    "body": "black",
                    "fins": "black",
                    "motor": "black",
                    "buttons": "black",
                    "line_width": 2.0,
                },
                filename=draw_filename
            )

        # define environment
        env = Environment(
            date=self.env.date,
            latitude=self.env.latitude.value(vEnvironment),
            longitude=self.env.longitude.value(vEnvironment),
            elevation=self.env.elevation.value(vEnvironment)
        )
        if self.env.reanalysis_filename:
            # TODO: The API is not working with ensemble data atm. Ensemble myself? from the data
            env.set_atmospheric_model(
                type="Reanalysis",
                file=self.env.reanalysis_filename,
                dictionary="ECMWF"
            )
            self.env.wind_heading = In(env.wind_heading(10))  # type: ignore
        else:
            north, east = wind_heading_components(
                heading=self.env.wind_heading.value(  # type: ignore
                    vEnvironment),
                speed=self.env.wind_speed.value(vEnvironment)  # type: ignore
            )
            env.set_atmospheric_model(
                type="custom_atmosphere",
                wind_u=[(0, east)],  # from the east # type: ignore
                wind_v=[(0, north)],  # from the north # type: ignore
            )
            # TODO: Implement at a later date
            # env.add_wind_gust()

        # setup
        if total_impulse < 20:
            max_time_step = 0.01
        elif scaled_burn_time < 1.8:
            max_time_step = 0.01
        else:
            max_time_step = np.inf
        max_time = 1200
        time_overshoot = False if failure_mode == FlightOutcome.SHRED else True

        # define flight
        tf = Flight(
            rocket=rocket,
            environment=env,
            rail_length=self.flight.rail_length.value(vLaunch),
            inclination=self.flight.inclination.value(vLaunch),
            heading=self.flight.heading.value(vLaunch),
            max_time_step=max_time_step,
            max_time=max_time,
            time_overshoot=time_overshoot,
            verbose=verbose
        )

        if plot_trajectory:
            print(f"Apogee: {tf.apogee} m")
            tf.plots.trajectory_3d(filename=plot_trajectory)

        if plot_trajectory_2d:
            t = tf.time
            y = -tf.y(t)  # type: ignore
            z = tf.z(t)  # type: ignore

            t_out_of_rail = tf.out_of_rail_time
            t_burn_out = self.motor.burn_time.ideal
            t_parachutes = tf.parachute_events

            fig, ax = plt.subplots(constrained_layout=True)
            ax.plot(y, z)
            ax.set_xlabel("Horizontal Distance")
            ax.set_ylabel("Altitude")
            ax.set_xticks([])
            ax.set_yticks([])
            ax.plot(y[0], z[0], marker="x", label="Launch Point")
            ax.plot(-tf.y(t_out_of_rail), tf.z(t_out_of_rail),  # type: ignore
                    marker="x", label="Out of Rail")
            ax.plot(-tf.y(t_burn_out), tf.z(t_burn_out),  # type: ignore
                    marker="x", label="Motor Burnout")
            labels = ["Drogue Parachute", "Main Parachute"] if len(
                t_parachutes) == 2 else ["Parachute"]
            for t_parachute, label in zip(t_parachutes, labels):
                t_p = t_parachute[0]
                ax.plot(-tf.y(t_p), tf.z(t_p),  # type: ignore
                        marker="x", label=label)
            ax.plot(y[-1], z[-1], marker="x", label="Landing Point")
            fig.legend(loc="center left", bbox_to_anchor=(1, 0.5))
            plt.savefig(plot_trajectory_2d)

        t_impact = tf.t_final
        x_impact = tf.x_impact  # positive east
        y_impact = tf.y_impact  # positive north
        v_impact = tf.impact_velocity
        apogee = tf.apogee

        impact_mass = rocket.total_mass(t_impact)  # type: ignore
        impact_energy = 0.5 * impact_mass * v_impact**2

        return x_impact, y_impact, impact_energy, apogee, failure_mode

    def monte_analysis(
        self,
        to_vary: list[Variance] = [
            Variance.PERFORMANCE,
            Variance.ENVIRONMENT,
            Variance.FLIGHT_EVENT,
            Variance.LAUNCH,
            Variance.DESIGN_AND_MANUFACTURING
        ],
        n: int = 50,
        *,
        verbose: bool = False
    ) -> "SimOutput":
        print(
            f"Starting Monte Carlo Analysis\n\t{'sample size':20}: {n}\n\t{'variance categories':20}: {[item.name for item in to_vary]}\n\t{'verbose mode':20}: {verbose}\n\t{'start time':20}: {datetime.datetime.now()}")

        sim_out = SimOutput(self, n)
        progress = ProgressBar(n)

        if not verbose:
            import sys
            sys.stdout = RegexFilter(r"^WARNING:.*", sys.stdout)

        i = 0
        while i < n:
            try:
                sim_out.add_point(
                    *self.monte_flight(to_vary=to_vary, verbose=verbose))
                i += 1
            except Exception as e:
                if verbose:
                    print(f"Simulation failed: {e}")
                    import traceback
                    traceback.print_tb(e.__traceback__)
                    print("\n")

            progress.update(i)

        return sim_out

    def optimise_launch_angle(
        self,
        min_inclination: float = 75,
        max_inclination: float = 105,
        target_distance: float = 0,
        filename: Optional[str] = None,
        show: bool = False
    ) -> float:
        """optimise launch angle to land target distance in launch heading direction from the laucnh point

        plots as it goes along

        Args:
            min_angle: minimum inclination [deg]. Defaults to -15.
            max_angle: maximum inclination [deg]. Defaults to 15.
            target_distance: target distance in launch heading direction [m]. Defaults to 0.

        Returns:
            optimal inclination angle [deg]
        """
        # save for later
        original_inclination = self.flight.inclination

        # define target
        heading = np.radians(self.flight.heading.ideal)
        x_target = target_distance * np.sin(heading)
        y_target = target_distance * np.cos(heading)

        n = int((max_inclination - min_inclination)*4)
        angles = np.linspace(min_inclination, max_inclination, n)
        out = SimOutput(self, n)

        print(
            f"Starting simulation of {n} points from {min_inclination} to {max_inclination} degrees inclination"
        )

        pbar = ProgressBar(n)

        for i, angle in enumerate(angles):
            self.flight.inclination = In(angle)
            out.add_point(*self.ideal_flight())
            pbar.update(i)
        error = out.distance(x_target, y_target)

        fig, ax = plt.subplots()

        # undo state change
        self.flight.inclination = original_inclination

        # error vs angles (left)
        l = ax.plot(angles, error, "b-", label="Error")
        ax.set_xlabel("Launch Inclination [deg]")
        ax.set_ylabel("Landing Distance Error [m]", color="b")
        ax.tick_params(axis="y", labelcolor="b")
        ax.set_ylim(0, np.max(error)*1.2)
        ax.set_xlim(min_inclination, max_inclination)

        ax1 = ax.twinx()

        # apogee vs angles (right)
        l1 = ax1.plot(angles, out.apogee, "r-", label="Apogee")
        ax1.set_ylabel("Apogee [m]", color="r")
        ax1.tick_params(axis="y", labelcolor="r")
        ax1.set_ylim(0, np.max(out.apogee)*1.2)

        i = np.argmin(error)
        best_error = error[i]
        best_angle = angles[i]

        if self.env.wind_heading and self.env.wind_speed:
            print(
                f"\nOptimal Launch Angle\n\t{'Inclination':20}{best_angle:10.2f} deg\n\t{'error':20}{best_error:12.2f} m\n\t{'heading bearing':20}{self.flight.heading.ideal:10.2f} deg\n\t{'wind direction':20}{self.env.wind_heading.ideal:10.2f} deg\n\t{'wind speed':20}{self.env.wind_speed.ideal:10.2f} m/s"
            )
        else:
            print(
                f"\nOptimal Launch Angle\n\t{'Inclination':20}{best_angle:10.2f} deg\n\t{'error':20}{best_error:12.2f} m\n\t{'heading bearing':20}{self.flight.heading.ideal:10.2f} deg\n\t{'wind direction':20}"
            )

        plt.title("Ideal Inclination Angle Sensitivity Study")

        if filename:
            plt.savefig(filename)

        if show:
            plt.show()

        return best_angle

#
# Simulation/Flight Output
#


class SimOutput:
    def __init__(self, fm: FlightManager, n: int) -> None:
        self.fm = fm
        self.x_pos = np.zeros(n)
        self.y_pos = np.zeros(n)
        self.impact_energy = np.zeros(n)
        self.apogee = np.zeros(n)
        self.failure_mode = np.zeros(n)

        # setup data store
        self.n = n
        self.head = 0

        # useful variables shortcut
        self.lon0 = self.fm.env.longitude.ideal
        """launch longitude"""
        self.lat0 = self.fm.env.latitude.ideal
        """launch latitude"""

        # setup map
        self.map_crs = ccrs.Mercator()
        """map coordinate system"""
        self.data_latlon_crs = ccrs.PlateCarree()
        """coordinate system to plot latitude and longitude"""
        self.data_local_crs = ccrs.AzimuthalEquidistant(
            self.lon0, self.lat0)
        """flat coordinate system to plot distance from launch point [m]"""

    def to_csv(self, filename: str) -> None:
        data = np.column_stack(
            (self.x_pos, self.y_pos, self.impact_energy, self.apogee, self.failure_mode))
        np.savetxt(filename, data, delimiter=",", comments="",
                   header="x_pos[m],y_pos[m],impact_energy[J],apogee[m],failure_mode")

    def save(self, filename: str) -> None:
        with open(filename, "wb") as f:
            dill.dump(self, f)
        print(f"saved cache to {filename}")

    def mean_point(self) -> tuple[float, float]:
        return self.x_pos.mean(), self.y_pos.mean()

    @classmethod
    def read(cls, filename: str, update_methods: bool = True) -> "SimOutput":
        with open(filename, "rb") as f:
            cached: SimOutput = dill.load(f)
            print(f"read cache from {filename}")

            # create new and copy state to new object to update methods
            if update_methods:
                # extract primary datapoints

                # create new object
                new = cls(
                    fm=cached.fm,
                    n=cached.n
                )

                # update relevant state
                new.x_pos = cached.x_pos
                new.y_pos = cached.y_pos
                new.impact_energy = cached.impact_energy
                new.failure_mode = cached.failure_mode
                new.apogee = getattr(cached, "apogee", new.apogee)
                new.head = cached.head

                return new
            else:
                # return object with methods as cached
                return cached

    def add_point(self, x_pos: float, y_pos: float, impact_energy: float, apogee: float, failure_mode: FlightOutcome) -> None:
        head = self.head

        if head >= self.n:
            raise IndexError(f"head ({head}) out of bounds (0, {self.n-1})")

        self.x_pos[head] = x_pos
        self.y_pos[head] = y_pos
        self.impact_energy[head] = impact_energy
        self.apogee[head] = apogee
        self.failure_mode[head] = failure_mode
        self.head += 1

    def distance(self, x: float, y: float):
        return np.sqrt((self.x_pos-x)**2 + (self.y_pos-y)**2)

    def add_north_arrow(self, ax: Axes, x_pos, y_pos, size=0.02):
        """Add north pointing arrow to the map (bottom left corner)

        Args:
            ax: axes
        """
        ax.annotate(
            "N",
            xy=(x_pos, y_pos + size),
            xytext=(x_pos, y_pos),
            arrowprops=dict(
                facecolor="white",
                edgecolor="black",
                width=3,
                headwidth=10
            ),
            ha="center",
            va="center",
            color="white",                 # inner fill
            fontsize=10,
            fontweight="bold",
            transform=self.data_local_crs,
            zorder=10,
            path_effects=[
                pe.Stroke(linewidth=2, foreground="black"),  # outline
                pe.Normal()
            ],
        )

    def add_wind_arrow(
        self,
        ax: Axes,
        heading_deg: float,
        radius: float = 200,
        label: str = "Wind",
        corner_offset: float = 0.94,
        y_shift: float = 0
    ):
        """
        Add a meteorological wind arrow centered on its midpoint above the label.
        Arrow points according to wind heading (coming from).
        """

        # Center for label
        x_label = radius * (corner_offset - 0.05)
        y_label = -radius * (corner_offset + y_shift)

        # Define arrow
        y_offset = 0.08 * radius
        arrow_length = 0.09 * radius

        # Midpoint of arrow above label
        x_mid = x_label
        y_mid = y_label + y_offset + arrow_length / \
            2  # vertical offset + half length

        # Wind heading in radians (meteorological: coming from)
        heading_rad = np.radians(heading_deg)
        dx = -arrow_length * np.sin(heading_rad)
        dy = -arrow_length * np.cos(heading_rad)

        # Compute tail and tip around midpoint
        x_tail = x_mid - dx / 2
        y_tail = y_mid - dy / 2
        x_tip = x_mid + dx / 2
        y_tip = y_mid + dy / 2

        # Draw arrow
        ax.annotate(
            '',
            xy=(x_tip, y_tip),
            xytext=(x_tail, y_tail),
            arrowprops=dict(
                facecolor="white",
                edgecolor="black",
                width=3,
                headwidth=10
            ),
            transform=self.data_local_crs,
            zorder=10
        )

        # Draw label below arrow, centered
        ax.text(
            x_label,
            y_label,
            label,
            ha="center",
            va="center",
            color="white",
            fontsize=10,
            fontweight="bold",
            transform=self.data_local_crs,
            zorder=10,
            path_effects=[
                pe.Stroke(linewidth=2, foreground="black"),
                pe.Normal()
            ]
        )

    def add_circle(self, ax: Axes, x_center: float, y_center: float, radius: float, color="white", label=""):
        """Add circle with label to the map plot

        Args:
            ax: axes
            x_center: x center position [m]
            y_center: y center position [m]
            radius: radius [m]
            color: line and label color. Defaults to "white".
            label: label to include if supplied. Defaults to "".
        """
        circle = mpatches.Circle(
            (x_center, y_center),
            radius,
            edgecolor=color,
            facecolor="none",
            linestyle="--",
            linewidth=1,
            transform=self.data_local_crs,
            zorder=6
        )
        ax.add_patch(circle)

        if label:
            ax.text(
                x_center, y_center + radius,
                label,
                color=color,
                fontsize=9,
                ha="center",
                va="bottom",
                transform=self.data_local_crs,
                zorder=7
            )

    def add_range_rings(self, ax: Axes, center_x, center_y, radii):
        for radius in radii:
            label = f"{radius:.0f} m" if radius < 1000 else f"{radius/1000:.1f} km"
            self.add_circle(ax, center_y, center_x, radius,
                            "white", label)

    def add_heading_arrow(
        self,
        ax: Axes,
        heading_deg: float,
        length: float = 100,
        x0: float = 0,
        y0: float = 0,
        color: str = "cyan",
        label: str = "Heading"
    ):
        """
        Draw heading direction arrow on the map.

        Args:
            ax: matplotlib axes
            heading_deg: heading angle in degrees (0°=North, 90°=East)
            length: arrow length in meters
            x0, y0: arrow start position [m]
            color: arrow color
            label: legend label
        """
        heading_rad = np.radians(heading_deg)

        dx = length * np.sin(heading_rad)   # east
        dy = length * np.cos(heading_rad)   # north

        ax.arrow(
            x0,
            y0,
            dx,
            dy,
            transform=self.data_local_crs,
            width=length * 0.02,
            head_width=length * 0.12,
            head_length=length * 0.15,
            fc=color,
            linewidth=1.5,
            zorder=11,
            length_includes_head=True,
            label=label
        )

    def compute_ellipses(self, n_sigmas=[1, 2, 3]):
        """compute the size, location and direction of dispersion ellipses based on x and y coordinates

        Args:
            x: x position [m] east positive
            y: y position [m] north positive
            n_sigmas: variance of ellipses. Defaults to [1, 2, 3].

        Returns:
            mean: (x, y) tuple of mean position
            angle: angle of mean from launch point
            width: list of ellipses width
            height: list of ellipses height
            area: list of ellipses area
        """
        x = self.x_pos
        y = self.y_pos

        data = np.vstack((x, y))

        # center point
        mean = np.mean(data, axis=1)

        # covariance matrix
        cov = np.cov(x, y)

        # eigen-decomposition
        eigvals, eigvecs = np.linalg.eigh(cov)

        # sort largest to smallest
        order = eigvals.argsort()[::-1]
        eigvals = eigvals[order]
        eigvecs = eigvecs[:, order]

        # orientation angle [deg]
        angle = np.degrees(np.arctan2(eigvecs[1, 0], eigvecs[0, 0]))

        n = len(n_sigmas)
        width = np.zeros(n)
        height = np.zeros(n)
        area = np.zeros(n)
        for i, n_sigma in enumerate(n_sigmas):
            semi_major = n_sigma * np.sqrt(eigvals[0])
            semi_minor = n_sigma * np.sqrt(eigvals[1])
            width[i] = 2 * semi_major
            height[i] = 2 * semi_minor
            area[i] = np.pi * semi_major * semi_minor

        return mean, angle, width, height, area

    def probability_enclosed(self, n_sigma: float) -> float:
        """The probability enclosed by n sigma variance for a 2D gaussian distribution

        Args:
            n_sigma: multiplied of sigma (variance)

        Returns:
            enclosed probability fraction [0, 1]
        """
        return 1 - np.exp(-n_sigma**2 / 2)

    def add_ellipses(self, ax: Axes, n_sigmas=[1, 2, 3]):
        """Plot dispersion ellipses based on n_sigmas' variances

        Args:
            ax: axes
            x: x position [m] positive East
            y: y position [m] positive North
            n_sigmas: variance of ellipses. Defaults to [1, 2, 3].
        """
        mean, angle, widths, heights, _ = self.compute_ellipses(n_sigmas)
        ax.scatter(
            *mean,
            s=50,
            marker="x",
            transform=self.data_local_crs,
            label="Mean Point",
            zorder=11
        )

        for n_sigma, width, height in zip(n_sigmas, widths, heights):
            ellipse = mpatches.Ellipse(
                xy=mean,
                width=width,
                height=height,
                angle=angle,
                label=rf"${n_sigma}\sigma$ ({self.probability_enclosed(n_sigma)*100:.1f}\%)",
                transform=self.data_local_crs,
                alpha=0.5,
                zorder=9,
                edgecolor="red",
                facecolor="none",
                lw=2,
            )
            ax.add_patch(ellipse)

    def add_satellite_maps(self, ax: Axes, radius: float, *, force_zoom: Optional[int] = None):
        # mapbox access token
        load_dotenv("./keys.env")
        MAPBOX_ACCESS_TOKEN = os.environ.get("MAPBOX_ACCESS_TOKEN")
        if not MAPBOX_ACCESS_TOKEN:
            raise ValueError("MAPBOX_ACCESS_TOKEN does not exist")

        # mapbox satellite tiles
        tiles = MapboxTiles(
            access_token=MAPBOX_ACCESS_TOKEN,
            map_id="satellite-v9",
            cache=True
        )

        # add mapbox tiles (satellite background)
        zoom = force_zoom if force_zoom else min(
            int(15 + np.log2(2000 / radius)), 22)
        ax.add_image(tiles, zoom)  # type: ignore

    def plot_dispersion_analysis_no_impact(
        self,
        label_radii: list[float] = [],
        width: Optional[float] = None,
        actual_landing_point: Optional[tuple[float, float]] = None,
        filename: Optional[str] = None,
        show: bool = True,
        figsize: tuple[float, float] = (6, 4.5)
    ):

        marker_map = {
            FlightOutcome.NOMINAL: "x",
            FlightOutcome.CORE_SAMPLE: "o",
            FlightOutcome.LAWN_DART: "D",
            FlightOutcome.MOTOR_CATO: "s",
            FlightOutcome.SEPARATION: ">",
            FlightOutcome.SHRED: "<",
            FlightOutcome.NO_CHUTE: "p"
        }

        failure_name_map = {
            FlightOutcome.NOMINAL: "Nominal",
            FlightOutcome.CORE_SAMPLE: "Core Sample",
            FlightOutcome.LAWN_DART: "Lawn Dart",
            FlightOutcome.MOTOR_CATO: "Motor CATO",
            FlightOutcome.SEPARATION: "Separation",
            FlightOutcome.SHRED: "Shred",
            FlightOutcome.NO_CHUTE: "No Parachute"
        }

        fig, ax = plt.subplots(
            figsize=figsize,
            subplot_kw={"projection": self.map_crs},
            constrained_layout=True
        )

        radius = width / 2 if width else 1.1 * \
            max(np.abs(self.x_pos).max(), np.abs(self.y_pos).max())

        ax.set_extent([-radius, radius, -radius, radius],  # type: ignore
                      crs=self.data_local_crs)

        self.add_satellite_maps(ax, radius)

        # plot launch point
        ax.scatter(
            0,
            0,
            s=200,
            marker="*",
            edgecolors="black",
            linewidths=1.5,
            transform=self.data_local_crs,
            label="Launch Point",
            zorder=10
        )

        # plot actual landing point
        if actual_landing_point:
            ax.scatter(
                actual_landing_point[1],
                actual_landing_point[0],
                s=200,
                marker="*",
                edgecolors="black",
                linewidths=1.5,
                transform=self.data_latlon_crs,
                label="Landing Point",
                zorder=10
            )

        for mode in list(marker_map.keys()):
            mask = mode == self.failure_mode
            if not len(self.x_pos[mask]):
                continue

            ax.scatter(
                self.x_pos[mask],
                self.y_pos[mask],
                marker=marker_map.get(mode),
                s=30,
                transform=self.data_local_crs,
                alpha=0.6,
                label=failure_name_map[mode],
                zorder=5 if mode == FlightOutcome.NOMINAL else 6
            )

        # add ellipses
        if self.n > 1:
            self.add_ellipses(ax, [1, 2, 3])

        # add north arrow
        self.add_north_arrow(ax, -radius*0.94, -radius*0.94, radius*0.15)

        # add heading angle
        if self.fm.flight.inclination.ideal != 90:
            self.add_heading_arrow(
                ax, self.fm.flight.heading.ideal, radius*0.2)

        # add wind arrow
        self.add_wind_arrow(
            ax,
            self.fm.env.wind_heading.ideal + 180,  # type: ignore
            radius,
            corner_offset=0.92,
            y_shift=0.03
        )

        # add distance rings
        self.add_range_rings(ax, 0, 0, label_radii)

        handles, labels = ax.get_legend_handles_labels()
        ax.legend(handles, labels, loc="center left",
                  bbox_to_anchor=(1.02, 0.5))
        # fig.legend(handles, labels)

        if filename:
            plt.savefig(filename)
            print(f"Saved {filename}")

        if show:
            plt.show()

    def plot_dispersion_analysis(
        self,
        label_radii: list[float] = [],
        width: Optional[float] = None,
        actual_landing_point: Optional[tuple[float, float]] = None,
        filename: Optional[str] = None,
        title: Optional[str] = None,
        log: bool = True,
        show: bool = True
    ):
        """plot the dispersion analysis from the monte carlo analysis

        Args:
            label_radii: radii distances to plot [m]. Defaults to [].
            width: width (and height) of plot [m] . Defaults to None.
        """
        fig, axes = plt.subplots(
            nrows=1,
            ncols=1,
            figsize=(10, 8),
            subplot_kw={"projection": self.map_crs},
            constrained_layout=True
        )

        return self._plot_dispersion_analysis(
            ax=axes,
            fig=fig,
            label_radii=label_radii,
            width=width,
            actual_landing_point=actual_landing_point,
            filename=filename,
            title=title,
            log=log,
            show=show
        )

    def _plot_dispersion_analysis(
        self,
        fig: Figure,
        ax: Axes,
        label_radii: list[float] = [],
        width: Optional[float] = None,
        actual_landing_point: Optional[tuple[float, float]] = None,
        filename: Optional[str] = None,
        title: Optional[str] = None,
        log: bool = True,
        show: bool = True
    ):
        """plot the dispersion analysis from the monte carlo analysis

        Args:
            label_radii: radii distances to plot [m]. Defaults to [].
            width: width (and height) of plot [m] . Defaults to None.
        """
        # map bounds
        if width:
            radius = width / 2
        else:
            radius = 1.2 * max(
                np.abs(self.x_pos).max(),
                np.abs(self.y_pos).max()
            )  # [m]
        extent = [
            -radius, radius, -radius, radius
        ]  # [left, right, bottom, top] in [m]
        ax.set_extent(extent, crs=self.data_local_crs)  # type: ignore

        self.add_satellite_maps(ax, radius)

        # plot launch point
        ax.scatter(
            0,
            0,
            s=200,
            marker="*",
            edgecolors="black",
            linewidths=1.5,
            transform=self.data_local_crs,
            label="Launch Point",
            zorder=10
        )

        # plot actual landing point
        if actual_landing_point:
            ax.scatter(
                actual_landing_point[1],
                actual_landing_point[0],
                s=200,
                marker="*",
                edgecolors="black",
                linewidths=1.5,
                transform=self.data_latlon_crs,
                label="Landing Point",
                zorder=10
            )

        # TODO: Convert to human readable (not NAR classification)
        marker_map = {
            FlightOutcome.NOMINAL: "x",
            FlightOutcome.CORE_SAMPLE: "o",
            FlightOutcome.LAWN_DART: "D",
            FlightOutcome.MOTOR_CATO: "s",
            FlightOutcome.SEPARATION: ">",
            FlightOutcome.SHRED: "<"
        }

        failure_name_map = {
            FlightOutcome.NOMINAL: "Nominal",
            FlightOutcome.CORE_SAMPLE: "Ballistic",
            FlightOutcome.LAWN_DART: "Ballistic\n(without nose)",
            FlightOutcome.MOTOR_CATO: "Motor CATO",
            FlightOutcome.SEPARATION: "Freefall\nfrom deployment",
            FlightOutcome.SHRED: "Disintegrate"
        }

        # setup colourmap
        cmap = plt.get_cmap("viridis")
        if log:
            positive_impact_energy_min = self.impact_energy[self.impact_energy > 0].min(
            )
            impact_energy = np.clip(
                self.impact_energy, positive_impact_energy_min, None)
            norm = mcolors.LogNorm(
                vmin=impact_energy.min(),
                vmax=impact_energy.max()
            )
        else:
            norm = mcolors.Normalize(
                vmin=self.impact_energy.min(),
                vmax=self.impact_energy.max()
            )

        for mode in list(marker_map.keys()):
            mask = mode == self.failure_mode
            if not len(self.x_pos[mask]):
                continue

            ax.scatter(
                self.x_pos[mask],
                self.y_pos[mask],
                c=self.impact_energy[mask],
                cmap=cmap,
                norm=norm,
                marker=marker_map.get(mode),
                s=30,
                label=failure_name_map[mode],
                transform=self.data_local_crs,
                alpha=0.6,
                zorder=5 if mode == FlightOutcome.NOMINAL else 6
            )

        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])  # required for colorbar
        cbar = fig.colorbar(
            sm,
            ax=ax)
        cbar.set_label("Impact Energy (J)")

        # # landing points - x/y
        # sc1 = ax.scatter(
        #     self.x_pos,
        #     self.y_pos,
        #     s=30,
        #     cmap="viridis",
        #     c=self.impact_energy,
        #     # vmax=1000,
        #     marker="x",
        #     transform=data_local_crs,
        #     label="Landing Point",
        #     alpha=0.6
        # )

        # add ellipses
        if self.n > 1:
            self.add_ellipses(ax, [1, 2, 3])

        # add north arrow
        self.add_north_arrow(ax, -radius*0.94, -radius*0.94, radius*0.12)

        # add heading angle
        if self.fm.flight.inclination.ideal != 90:
            self.add_heading_arrow(
                ax, self.fm.flight.heading.ideal, radius*0.2)

        # add wind arrow
        self.add_wind_arrow(
            ax,
            self.fm.env.wind_heading.ideal + 180,  # type: ignore
            radius
        )

        # add distance rings
        self.add_range_rings(ax, 0, 0, label_radii)

        # # add colour bar
        # cbar = plt.colorbar(sc1, label="Impact Energy (J)")

        # # don't allow scientific notation / standard form
        # cbar.ax.yaxis.set_major_formatter(
        #     mticker.FuncFormatter(lambda val, pos: f"{val:.2f}")
        # )

        # add legend
        ax.legend(loc='upper right')

        # add title
        if title is None:
            ax.set_title(f"Dispersion Analysis (n={self.n})")
        else:
            ax.set_title(title)

        if filename:
            plt.savefig(filename)

        if show:
            plt.show()

# TODO: Automatically save all plots and the sensitivity table
# TODO: Add definitions to EVERYTHING
# TODO: Re-implement separation so that different bodies fall


if __name__ == "__main__":

    a = In(5, delay_distribution())

    for _ in range(10):
        print(a.ideal)
        print(a.random)

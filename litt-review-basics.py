from monte_carlo_manager import FlightManager, FlightCls, EnvironmentCls, MotorCls, RocketCls, ParachuteCls, NoseCls, FinSetCls, RailButtonCls, In, normal, normal_fraction, uniform, MPH_TO_MS, SimOutput, TailCls, TransitionCls, NM_TO_M, Variance

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

cots_error = normal_fraction(0.01)
design_and_manufacturing_error = normal_fraction(0.025)

fm = FlightManager(
    flight=FlightCls(
        rail_length=In(5),
        inclination=In(90, normal(2)),
        heading=In(176, normal(10))
    ),
    env=EnvironmentCls(
        latitude=In(55.7267571620931),
        longitude=In(-4.810976384052003),
        elevation=In(234),
        # reanalysis_filename="./data/rockets/mpr/mrc-9-11-2025.nc",
        # date=(2025, 11, 9, 13),
        wind_speed=In(4.5, normal(1)),  # from ERA5 (MRC 2025-11-9 13:00)
        wind_heading=In(176, normal(10))  # from ERA5 (MRC 2025-11-9 13:00)
    ),
    motor=MotorCls(
        thrust_source="./data/motors/cesaroni/Cesaroni_8429M2020-P.eng",
        diameter=In(75 / 1000, cots_error),
        length=In(893 / 1000, cots_error),
        total_mass=In(7032 / 1000, cots_error),
        prop_mass=In(4349 / 1000, cots_error),
        burn_time=In(4.2),
        scaled_burn_time=In(4.2, cots_error),
        scaled_total_impulse=In(2500, cots_error),
        # scaled_total_impulse=In(9429.4, cots_error),
        position=In(1398 / 1000, cots_error),
        grain_number=6,
        thrust_eccentricity_distance_from_centerline=In(0),  # TODO ???
        thrust_eccentricity_angle_from_centerline=In(0, uniform(0, 360)),
    ),
    rocket=RocketCls(
        radius=In(102 / 2000, design_and_manufacturing_error),
        mass=In(6403 / 1000, design_and_manufacturing_error),
        inertia=(
            In(0.01408, design_and_manufacturing_error),
            In(0.01408, design_and_manufacturing_error),
            In(2.326591, design_and_manufacturing_error),
        ),
        power_off_drag="./data/rockets/l4c/powerOffDragCurve.csv",
        power_on_drag="./data/rockets/l4c/powerOnDragCurve.csv",
        center_of_mass_without_motor=In(
            1224 / 1000, design_and_manufacturing_error)
    ),
    rail_button=RailButtonCls(
        upper_button_position=In(1550 / 1000, design_and_manufacturing_error),
        lower_button_position=In(
            (1550 + 500) / 1000, design_and_manufacturing_error),
        angular_position=In(45)
    ),
    nose=NoseCls(
        # includes transition
        length=In(500 / 1000, design_and_manufacturing_error),
        kind="von karman"
    ),
    fin_set=FinSetCls(
        n=3,
        root_chord=In(171 / 1000, design_and_manufacturing_error),
        tip_chord=In(51 / 1000, design_and_manufacturing_error),
        span=In(120 / 1000, design_and_manufacturing_error),
        position=In(2079 / 1000),
        sweep_length=In(120 / 1000, design_and_manufacturing_error),
        # TODO: Update
        airfoil=("./data/airfoils/NACA0012-radians.txt", "radians")
    ),
    tail=TailCls(
        fwd_radius=In(102 / 2000),
        aft_radius=In(83 / 2000),
        length=In(56.7 / 1000, design_and_manufacturing_error),
        position=In(2250 / 1000),
    ),
    main_parachute=ParachuteCls(
        radius=In(1524 / 2000, cots_error),
        cd=In(2.2, cots_error),
        trigger_type="apogee",
        lag=In(0)
    ),
    drogue_parachute=ParachuteCls(
        radius=In(609.6 / 2000, cots_error),
        cd=In(1.6, cots_error),
        trigger_type="altitude",
        trigger_altitude=In(300, normal(20)),
        lag=In(0)
    )
)

fm.ideal_flight(plot_trajectory="l4c-trajectory-3d.png")
print("Saved l4c-trajectory-3d.png")
fm.ideal_flight(plot_trajectory="l4c-trajectory-3d.pdf")
print("Saved l4c-trajectory-3d.pdf")

fm.ideal_flight(plot_trajectory_2d="l4c-trajectory.png")
print("Saved l4c-trajectory.png")
fm.ideal_flight(plot_trajectory_2d="l4c-trajectory.pdf")
print("Saved l4c-trajectory.pdf")

fm.draw_rocket("l4c-draw.png")
print("Saved l4c-draw.png")
fm.draw_rocket("l4c-draw.pdf")
print("Saved l4c-draw.pdf")

# fm.optimise_launch_angle(
#     min_inclination=90 - 15,
#     max_inclination=90 + 15,
#     target_distance=0,
#     show=True
# )

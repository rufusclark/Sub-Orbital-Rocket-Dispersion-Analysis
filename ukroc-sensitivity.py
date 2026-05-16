from monte_carlo_manager import FlightManager, FlightCls, EnvironmentCls, MotorCls, RocketCls, ParachuteCls, NoseCls, FinSetCls, RailButtonCls, In, normal, normal_fraction, uniform, MPH_TO_MS, SimOutput, TailCls, TransitionCls, NM_TO_M, Variance, delay_distribution

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

# TODO: Support different motors

cots_error = normal_fraction(0.01)
design_and_manufacturing_error = normal_fraction(0.05)


# E30-7
E30 = MotorCls(
    thrust_source="./data/motors/aerotech/AeroTech_E30T.eng",
    diameter=In(24 / 1000, cots_error),
    length=In(70 / 1000, cots_error),
    total_mass=In(47 / 1000, cots_error),
    prop_mass=In(18 / 1000, cots_error),
    burn_time=In(1.0),
    scaled_burn_time=In(1.0, cots_error),
    scaled_total_impulse=In(33.6, cots_error),
    position=In(600 / 1000, normal(2 / 1000)),
    thrust_eccentricity_angle_from_centerline=In(0, uniform(0, 360)),
    thrust_eccentricity_distance_from_centerline=In(
        0, design_and_manufacturing_error)
)

fm = FlightManager(
    flight=FlightCls(
        rail_length=In(1.5, normal(0.1)),
        inclination=In(90, normal(4)),
        heading=In(51+180, normal(10))
    ),
    env=EnvironmentCls(
        latitude=In(53.3784595126529),
        longitude=In(-2.453864922628811),
        elevation=In(46, normal(1)),
        wind_heading=In(51, normal(20)),
        wind_speed=In(5, normal(1))
    ),
    motor=E30,
    rocket=RocketCls(
        radius=In(56.3 / 2000, design_and_manufacturing_error),
        mass=In(515 / 1000, design_and_manufacturing_error),
        inertia=(
            In(0.000147, design_and_manufacturing_error),
            In(0.000147, design_and_manufacturing_error),
            In(0.014072, design_and_manufacturing_error)
        ),
        power_off_drag="./data/rockets/ukroc/powerOffDragCurve.csv",
        power_on_drag="./data/rockets/ukroc/powerOnDragCurve.csv",
        center_of_mass_without_motor=In(
            320 / 1000, design_and_manufacturing_error)
    ),
    rail_button=RailButtonCls(
        angular_position=In(45, normal(5)),
        lower_button_position=In(
            (305+306) / 1000, design_and_manufacturing_error),
        upper_button_position=In(
            305 / 1000, design_and_manufacturing_error),
    ),
    nose=NoseCls(
        kind="ogive",
        length=In(120 / 1000, design_and_manufacturing_error),
    ),
    fin_set=FinSetCls(
        n=3,
        root_chord=In(75 / 1000, design_and_manufacturing_error),
        tip_chord=In(40 / 1000, design_and_manufacturing_error),
        span=In(43 / 1000, design_and_manufacturing_error),
        sweep_length=In(28 / 1000, design_and_manufacturing_error),
        position=In(585 / 1000, design_and_manufacturing_error),
    ),
    main_parachute=ParachuteCls(
        radius=In(500 / 2000, cots_error),
        trigger_type="motor ejection",
        cd=In(0.8, cots_error),
        motor_ejection_delay=In(7, delay_distribution())
    ),
)

to_vary = Variance.PERFORMANCE
cache_path = f"ukroc_monte_carlo_cache/{to_vary.name.lower().replace("_", "-")}.cache"

cache_path = "ukroc_monte_carlo_cache/all.cache"
cache_path = "ukroc_monte_carlo_cache/ideal.cache"

print(f"Cache Path: {cache_path}")
monte_dataset = fm.monte_analysis(
    # to_vary=[to_vary],
    to_vary=[],
    n=1,
    # verbose=True
)
# monte_dataset.save(cache_path)

out = SimOutput.read(cache_path)
out.plot_dispersion_analysis()

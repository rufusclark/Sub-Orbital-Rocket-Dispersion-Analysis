from monte_carlo_manager import FlightManager, FlightCls, EnvironmentCls, MotorCls, RocketCls, ParachuteCls, NoseCls, FinSetCls, RailButtonCls, In, normal, normal_fraction, uniform, MPH_TO_MS, SimOutput, TailCls, TransitionCls, NM_TO_M, Variance

# TODO: Support different motors

motor_variance = normal_fraction(0.01)
motor_performance_variance = normal_fraction(0.05)

# F12-5
F12 = MotorCls(
    thrust_source="./data/motors/aerotech/AeroTech_F12J.eng",
    diameter=In(24 / 1000, motor_variance),
    length=In(70 / 1000, motor_variance),
    total_mass=In(69 / 1000, motor_variance),
    prop_mass=In(30 / 1000, motor_variance),
    burn_time=In(2.9),
    scaled_burn_time=In(2.9, motor_performance_variance),
    scaled_total_impulse=In(43.2, motor_performance_variance),
    position=In(600 / 1000, normal(2 / 1000)),
    thrust_eccentricity_angle_from_centerline=In(0, uniform(0, 360)),
    thrust_eccentricity_distance_from_centerline=In(0, normal(1 / 1000))
)

# E26-7
E26 = MotorCls(
    thrust_source="./data/motors/aerotech/AeroTech_E26W.eng",
    diameter=In(24 / 1000, motor_variance),
    length=In(88 / 1000, motor_variance),
    total_mass=In(44 / 1000, motor_variance),
    prop_mass=In(18 / 1000, motor_variance),
    burn_time=In(1.2),
    scaled_burn_time=In(1.2, motor_performance_variance),
    scaled_total_impulse=In(27.9, motor_performance_variance),
    position=In(588 / 1000, normal(2 / 1000)),
    thrust_eccentricity_angle_from_centerline=In(0, uniform(0, 360)),
    thrust_eccentricity_distance_from_centerline=In(0, normal(1 / 1000))
)

# E30-7
E30 = MotorCls(
    thrust_source="./data/motors/aerotech/AeroTech_E30T.eng",
    diameter=In(24 / 1000, motor_variance),
    length=In(70 / 1000, motor_variance),
    total_mass=In(47 / 1000, motor_variance),
    prop_mass=In(18 / 1000, motor_variance),
    burn_time=In(1.0),
    scaled_burn_time=In(1.0, motor_performance_variance),
    scaled_total_impulse=In(33.6, motor_performance_variance),
    position=In(600 / 1000, normal(2 / 1000)),
    thrust_eccentricity_angle_from_centerline=In(0, uniform(0, 360)),
    thrust_eccentricity_distance_from_centerline=In(0, normal(1 / 1000))
)


for motor, motor_name in zip([F12, E30, E26], ["F12", "E30", "E26"]):
    for wind_speed_mph in [0, 5, 10, 15, 20]:

        # motor_name = "E30"
        # motor = E30
        # wind_speed_mph = 5

        print(f"wind speed: {wind_speed_mph} mph  -  motor: {motor_name}")

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
                wind_speed=In(wind_speed_mph*MPH_TO_MS, normal(1))
            ),
            motor=motor,
            rocket=RocketCls(
                radius=In(56.3 / 2000, normal(0.5 / 1000)),
                mass=In(515 / 1000, normal_fraction(0.1)),
                inertia=(
                    In(0.000147, normal_fraction(0.1)),
                    In(0.000147, normal_fraction(0.1)),
                    In(0.014072, normal_fraction(0.1))
                ),
                power_off_drag="./data/rockets/ukroc/powerOffDragCurve.csv",
                power_on_drag="./data/rockets/ukroc/powerOnDragCurve.csv",
                center_of_mass_without_motor=In(320 / 1000, normal(20 / 1000))
            ),
            rail_button=RailButtonCls(
                angular_position=In(45, normal(5)),
                lower_button_position=In((305+306) / 1000, normal(10 / 1000)),
                upper_button_position=In(305 / 1000, normal(10 / 1000)),
            ),
            nose=NoseCls(
                kind="ogive",
                length=In(120 / 1000, normal(2 / 1000)),
            ),
            fin_set=FinSetCls(
                n=3,
                root_chord=In(75 / 1000, normal(2 / 1000)),
                tip_chord=In(40 / 1000, normal(2 / 1000)),
                span=In(43 / 1000, normal(2 / 1000)),
                sweep_length=In(28 / 1000, normal(2 / 1000)),
                position=In(585 / 1000, normal(2 / 1000)),
            ),
            main_parachute=ParachuteCls(
                radius=In(500 / 2000, normal(10 / 1000)),
                trigger_type="motor ejection",
                cd=In(0.8, normal(0.1)),
                motor_ejection_delay=In(5, normal(1))
            ),
        )

        # fm.draw_rocket()
        # fm.ideal_flight(plot_trajectory=True)

        quit()

        filename = f"./lymm-figures/{motor_name}-{wind_speed_mph}mph"

        fm.optimise_launch_angle(
            filename=f"{filename}-launch-angle.png",
            show=False
        )

        monte_dataset = fm.monte_analysis(n=1000)
        monte_dataset.plot_dispersion_analysis(
            label_radii=[5, 150],
            # width=600,
            filename=f"{filename}-dispersion-analysis.png",
            show=False
        )

# Motors
#  - F12-5
#  - E26-7
#  - E30-7
# Wind Speeds
#  - 0mph
#  - 5mph
#  - 10mph
#  - 15mph
#  - 20mph

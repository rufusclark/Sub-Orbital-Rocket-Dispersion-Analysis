from monte_carlo_manager import FlightManager, FlightCls, EnvironmentCls, MotorCls, RocketCls, ParachuteCls, NoseCls, FinSetCls, RailButtonCls, In, normal, normal_fraction, uniform, MPH_TO_MS, SimOutput

# A6-4 LPR with B4-4 motor
fm = FlightManager(
    flight=FlightCls(
        rail_length=In(0.5),
        inclination=In(90, normal(5)),
        heading=In(140, normal(10))
    ),
    env=EnvironmentCls(
        latitude=In(53.3784595126529),
        longitude=In(-2.453864922628811),
        elevation=In(46),
        wind_heading=In(40, normal(10)),
        wind_speed=In(10*MPH_TO_MS, normal(1*MPH_TO_MS))
    ),
    motor=MotorCls(
        thrust_source="./data/motors/klima/klima_B4.eng",
        diameter=In(18 / 1000),
        length=In(70 / 1000),
        total_mass=In(16 / 1000),
        prop_mass=In(5 / 1000),
        burn_time=In(1.2),
        scaled_burn_time=In(1.2),
        scaled_total_impulse=In(5),
        position=In(300 / 1000),
        grain_number=1,
        thrust_eccentricity_distance_from_centerline=In(0),
        thrust_eccentricity_angle_from_centerline=In(0, uniform(0, 360)),
    ),
    rocket=RocketCls(
        radius=In(24.8 / 2000),
        mass=In(36.8 / 1000),
        inertia=(
            In(0.000004),
            In(0.000004),
            In(0.000416),
        ),
        power_off_drag="./data/rockets/lpr/powerOffDragCurve.csv",
        power_on_drag="./data/rockets/lpr/powerOnDragCurve.csv",
        center_of_mass_without_motor=In(241 / 1000)
    ),
    rail_button=RailButtonCls(
        upper_button_position=In(245 / 1000),
        lower_button_position=In((245 + 50) / 1000),
        angular_position=In(45)
    ),
    nose=NoseCls(
        length=In(120 / 1000),
        kind="ogive"
    ),
    fin_set=FinSetCls(
        n=4,
        root_chord=In(45 / 1000),
        tip_chord=In(30 / 1000),
        span=In(29 / 1000),
        position=In(325 / 1000),
        sweep_length=In(15 / 1000),
        airfoil=None
    ),
    main_parachute=ParachuteCls(
        radius=In(120 / 2000),
        cd=In(0.8),
        trigger_type="motor ejection",
        motor_ejection_delay=In(4),
        lag=In(0)
    )
)

fm.draw_rocket()

# monte_dataset = fm.monte_analysis(1000)
# monte_dataset.plot_dispersion_analysis(
#     width=400,
#     label_radii=[5, 150]
# )
# monte_dataset.save("test.cache")

out = SimOutput.read("sample_lpr.cache")
out.plot_dispersion_analysis(
    width=400,
    label_radii=[5, 150]
)

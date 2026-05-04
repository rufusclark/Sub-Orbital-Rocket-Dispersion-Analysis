from monte_carlo_manager import FlightManager, FlightCls, EnvironmentCls, MotorCls, RocketCls, ParachuteCls, NoseCls, FinSetCls, RailButtonCls, In, normal, normal_fraction, uniform, MPH_TO_MS, SimOutput, TailCls, TransitionCls

cots_error = normal_fraction(0.01)
design_and_manufacturing_error = normal_fraction(0.025)

fm = FlightManager(
    flight=FlightCls(
        rail_length=In(2),
        inclination=In(85, normal(5)),
        heading=In(60, normal(10))
    ),
    env=EnvironmentCls(
        latitude=In(52.6692265),
        longitude=In(-1.5233585),
        elevation=In(105),
        # reanalysis_filename="./data/rockets/mpr/mrc-9-11-2025.nc",
        # date=(2025, 11, 9, 13),
        wind_speed=In(4.5, normal(1.5)),  # from ERA5 (MRC 2025-11-9 13:00)
        wind_heading=In(176+180, normal(10))  # from ERA5 (MRC 2025-11-9 13:00)
    ),
    motor=MotorCls(
        thrust_source="./data/motors/cesaroni/Cesaroni_56F31-12A.eng",
        diameter=In(29 / 1000, cots_error),
        length=In(98 / 1000, cots_error),
        total_mass=In(102 / 1000, cots_error),
        prop_mass=In(70 / 1000, cots_error),
        burn_time=In(1.8),
        scaled_burn_time=In(1.8, cots_error),
        scaled_total_impulse=In(55.5, cots_error),
        position=In(659 / 1000, cots_error),
        grain_number=1,
        thrust_eccentricity_distance_from_centerline=In(0),  # TODO ???
        thrust_eccentricity_angle_from_centerline=In(0, uniform(0, 360)),
    ),
    rocket=RocketCls(
        radius=In(72.4 / 2000, design_and_manufacturing_error),
        # with casing and without motor
        mass=In(659.5 / 1000, design_and_manufacturing_error),
        inertia=(
            In(0.000469, design_and_manufacturing_error),
            In(0.000469, design_and_manufacturing_error),
            In(0.029286, design_and_manufacturing_error),
        ),
        power_off_drag="./data/rockets/mpr/powerOffDragCurve.csv",
        power_on_drag="./data/rockets/mpr/powerOnDragCurve.csv",
        center_of_mass_without_motor=In(
            365 / 1000, design_and_manufacturing_error)
    ),
    rail_button=RailButtonCls(
        upper_button_position=In(380 / 1000, design_and_manufacturing_error),
        lower_button_position=In(
            (380 + 260) / 1000, design_and_manufacturing_error),
        angular_position=In(45)
    ),
    nose=NoseCls(
        # includes transition
        length=In(170 / 1000, design_and_manufacturing_error),
        kind="ogive"
    ),
    transition=TransitionCls(
        fwd_radius=In(72.4 / 2000, design_and_manufacturing_error),
        aft_radius=In(57.1 / 2000, design_and_manufacturing_error),
        length=In(20 / 1000, design_and_manufacturing_error),
        position=In(170 / 1000)
    ),
    fin_set=FinSetCls(
        n=4,
        root_chord=In(120 / 1000, design_and_manufacturing_error),
        tip_chord=In(60 / 1000, design_and_manufacturing_error),
        span=In(70 / 1000, design_and_manufacturing_error),
        position=In(622 / 1000),
        sweep_length=In(50 / 1000, design_and_manufacturing_error),
        airfoil=None  # assume flat plate # TODO: Update
    ),
    tail=TailCls(
        fwd_radius=In(57.1 / 2000),
        aft_radius=In(48 / 2000),
        length=In(25 / 1000, design_and_manufacturing_error),
        position=In(740 / 1000),
    ),
    # main_parachute=ParachuteCls(
    #     radius=In(457 / 2000, cots_error),
    #     cd=In(0.8, cots_error),
    #     trigger_type="motor ejection",
    #     motor_ejection_delay=In(7, cots_error),
    #     lag=In(0)
    # ),
    main_parachute=ParachuteCls(
        radius=In(457 / 2000, cots_error),
        cd=In(0.8, cots_error),
        trigger_type="altitude",
        trigger_altitude=In(150, normal(10)),
        lag=In(0)
    )
)


# fm.draw_rocket("mpr-draw.png")
# quit()

# fm.monte_flight(to_vary=[], plot_trajectory=True)
monte_dataset = fm.monte_analysis(n=1)
monte_dataset.save("test.cache")
monte_dataset.plot_dispersion_analysis(
    label_radii=[],
    actual_landing_point=(52.6693235, -1.5222396666666667),
    title="",
    filename="mpr.png",
    width=400
)

# out = SimOutput.read("mpr.cache")
# out.plot_dispersion_analysis(
#     label_radii=[5, 150]
# )

# launch point = 52.6692265, -1.5233585
# landing point = 52.6693235, -1.5222396666666667

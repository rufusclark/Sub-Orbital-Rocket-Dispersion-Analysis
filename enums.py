from enum import IntEnum


class Variance(IntEnum):
    PERFORMANCE = 1
    ENVIRONMENT = 2
    FLIGHT_EVENT = 3
    LAUNCH = 4
    DESIGN_AND_MANUFACTURING = 5


class FlightOutcome(IntEnum):
    NOMINAL = 11
    LAWN_DART = 12
    CORE_SAMPLE = 13
    SEPARATION = 14
    SHRED = 15
    MOTOR_CATO = 16

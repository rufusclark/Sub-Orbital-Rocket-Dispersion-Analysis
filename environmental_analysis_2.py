"""Due to issues with RocketPy's handling of NetCDF files. This model processes the data itself to generate it's own plots.

You must also create an account, download the cdsapi tool and the follow the setup process, see [documentation here](https://cds.climate.copernicus.eu/how-to-api)

Please note data download may take several minutes and up to several hours depending on the size of the dataset requested. Progress can be checked via the Copernicus Climate Data Store web interface. If you have already downloaded the data, it will be cached and used directly."""

import math
from datetime import datetime, time
import pathlib
from typing import Literal
import xarray as xr
import numpy as np
import matplotlib.pyplot as plt

# Setup nice scientific styling

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

g = 9.80665


def round_to_quarter(x: float) -> float: return round(x * 4) / 4
def fmt_list(l: list[int]) -> str: return f"[{'-'.join([str(x) for x in l])}]"


def pressure_from_altitude(h, T=288.15):
    """estimate pressure [hPa] at altitude [m] based on ISA 

    Args:
        h: altitude [m]
        T: temperature [K]. Defaults to 288.15.

    Returns:
        pressure [hPa]
    """
    # Constants
    P0 = 1013.25       # Sea-level standard pressure in hPa
    g = 9.80665        # Gravity, m/s^2
    M = 0.0289644      # Molar mass of Earth's air, kg/mol
    R = 8.3144598      # Universal gas constant, J/(mol·K)

    # Barometric formula
    P = P0 * math.exp(-M * g * h / (R * T))
    return P


class EnvironmentalAnalysisManager:
    def __init__(
        self,
        name: str,
        latitude: float,
        longitude: float,
        years: list[int],
        months: list[int],
        days: list[int],
        hours: list[int],
        max_altitude: float  # [m]
    ) -> None:
        self.name = name
        self.lat = latitude
        self.lon = longitude

        self.root_path = pathlib.Path(f"./data/weather/{name.lower()}")

        self.years = years
        self.months = months
        self.days = days
        self.hours = hours

        self.max_altitude = max_altitude

    @property
    def start_date(self) -> datetime:
        return datetime(
            year=self.years[0],
            month=self.months[0],
            day=self.days[0]
        )

    @property
    def end_date(self) -> datetime:
        return datetime(
            year=self.years[-1],
            month=self.months[-1],
            day=self.days[-1]
        )

    @property
    def start_time(self) -> np.datetime64:
        return np.datetime64(f"{self.years[0]:04d}-{self.months[0]:02d}-{self.days[0]:02d}T{self.hours[0]:02d}:00")

    @property
    def end_time(self) -> np.datetime64:
        return np.datetime64(f"{self.years[-1]:04d}-{self.months[-1]:02d}-{self.days[-1]:02d}T{self.hours[-1]:02d}:00")

    def path(
        self,
        dataset: str,
    ) -> pathlib.Path:

        def fmt(l: list[int]) -> str:
            n = len(l)
            if n == 0:
                raise ValueError("Invalid empty input parameter")
            elif n == 1:
                return f"[{l[0]}]"
            elif n == 2:
                return f"[{l[0]}-{l[1]}]"
            else:
                return f"[{l[0]}-{l[-1]}]"

        filename = f"{dataset}-{fmt(self.years)}-{fmt(self.months)}-{fmt(self.days)}-{fmt(self.hours)}.nc"

        return self.root_path / filename

    def download_levels_data(
        self,
    ) -> None:
        # TODO: Write docstring
        # ! API Key must exist (provide instructions of how to provide)
        import cdsapi

        years = self.years
        months = self.months
        days = self.days
        hours = self.hours

        # https://cds.climate.copernicus.eu/datasets/reanalysis-era5-pressure-levels?tab=download
        dataset = "reanalysis-era5-pressure-levels"
        path = self.path(dataset)

        if path.exists():
            print("[Levels Data] Using cached data")
            return

        available_pressure_levels = [
            1, 2, 3, 5, 7, 10, 20, 30, 50, 70, 100, 125, 150, 175, 200, 225, 250, 300, 350, 400, 450, 500, 550, 600, 650, 700, 750, 775, 800, 825, 850, 875, 900, 925, 950, 975, 1000
        ]
        pressure_threshold = pressure_from_altitude(self.max_altitude) - 100
        pressure_levels: list[str] = [
            f"{p}" for p in available_pressure_levels if p > pressure_threshold
        ]

        request = {
            "product_type": ["reanalysis", "ensemble members"],
            "year": [f"{year}" for year in years],
            "month": [f"{month:02}" for month in months],
            "day": [f"{day:02}" for day in days],
            "time": [f"{hour:02}:00" for hour in hours],
            "data_format": "netcdf",
            "download_format": "unarchived",
            "variable": [
                "geopotential",
                "temperature",
                "u_component_of_wind",
                "v_component_of_wind"
            ],
            "pressure_level": pressure_levels,
            "area": [
                round_to_quarter(self.lat + 0.5),
                round_to_quarter(self.lon - 0.5),
                round_to_quarter(self.lat - 0.5),
                round_to_quarter(self.lon + 0.5)
            ]
        }

        print("[Levels Data] Downloading data... (this may take several minutes)")
        path.parent.mkdir(parents=True, exist_ok=True)

        client = cdsapi.Client()
        client.retrieve(dataset, request, path)
        print(f"[Levels Data] Data downloaded to {path}")

    def plot_wind_speeds(self, filename: str = ""):
        ds = xr.open_dataset(self.path("reanalysis-era5-pressure-levels"))

        # nearest method
        pt = ds.sel(
            latitude=self.lat,
            longitude=self.lon,
            method="nearest"
        )

        pt = pt.sel(valid_time=self.start_time, method="nearest")

        alt = pt["z"] / g
        alt = alt.sortby("pressure_level", ascending=False)
        min_alt = alt.isel(pressure_level=0).values
        elevation = alt - min_alt

        u = pt["u"]
        v = pt["v"]

        wind_speed = np.sqrt(u**2 + v**2)
        wind_to = (np.degrees(np.atan2(u, v)) + 360) % 360
        wind_from = (wind_to + 180) % 360  # wind heading

        fig, axes = plt.subplots(
            1, 2, layout="compressed", sharey=True, figsize=(6, 3))

        ax = axes[0]
        ax.plot(wind_speed, elevation)
        ax.set_ylabel("Elevation [m]")
        ax.set_xlabel("Wind Speed [m/s]")
        ax.set_ylim(0, 200)
        ax.grid(True)

        ax = axes[1]
        ax.plot(wind_from, elevation)
        ax.set_xlabel("Heading [deg]")
        ax.set_ylim(0, self.max_altitude)
        # ax.legend()
        ax.grid(True)

        if filename:
            plt.savefig(filename)
            print(f"Saved {filename}")

        plt.show()

    def estimated_wind_at(self, elevation: float):
        ds = xr.open_dataset(self.path("reanalysis-era5-pressure-levels"))

        # nearest method
        pt = ds.sel(
            latitude=self.lat,
            longitude=self.lon,
            method="nearest"
        )

        pt = pt.sel(valid_time=self.start_time, method="nearest")

        alt = pt["z"] / g
        alt = alt.sortby("pressure_level", ascending=False)
        min_alt = alt.isel(pressure_level=0).values

        p = pressure_from_altitude(elevation + min_alt)

        u_z = pt["u"]
        v_z = pt["v"]

        u_pt = u_z.interp(pressure_level=p)
        v_pt = v_z.interp(pressure_level=p)

        speed = np.sqrt(u_pt**2 + v_pt**2)

        heading_to = (
            np.degrees(np.arctan2(u_pt, v_pt)) + 360
        ) % 360

        heading_from = (heading_to + 180) % 360

        print(f"Interpolation at x = {elevation} m (p = {p} Pa)")
        print(f"Speed: {speed.values} m/s")
        print(f"Heading: {heading_from.values} deg")


if __name__ == "__main__":
    mrc = EnvironmentalAnalysisManager(
        name="mrc",
        latitude=52.669368807300984,
        longitude=-1.5236957546301024,
        years=list(range(2025, 2026)),
        months=[11],
        days=[9],
        hours=[13, 14],
        max_altitude=800,
    )

    mrc.download_levels_data()

    mrc.estimated_wind_at(169.2 / 2)

    mrc.plot_wind_speeds("mrc-wind-reanalysis.png")
    mrc.plot_wind_speeds("mrc-wind-reanalysis.pdf")

"""You must also create an account, download the cdsapi tool and the follow the setup process, see [documentation here](https://cds.climate.copernicus.eu/how-to-api)

Please note data download may take several minutes and up to several hours depending on the size of the dataset requested. Progress can be checked via the Copernicus Climate Data Store web interface. If you have already downloaded the data, it will be cached and used directly.
"""

import math
from rocketpy import EnvironmentAnalysis
from datetime import datetime
import pathlib
from typing import Literal


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

    def download_surface_data(
        self,
    ) -> None:
        # TODO: Write docstring
        # ! API Key must exist (provide instructions of how to provide)
        import cdsapi
        import zipfile
        import xarray as xr

        years = self.years
        months = self.months
        days = self.days
        hours = self.hours

        # https: // cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels?tab = download
        dataset = "reanalysis-era5-single-levels"
        out_path = self.path(dataset)

        if out_path.exists():
            print("[Surface Data] Using cached data")
            return

        request = {
            "product_type": ["reanalysis"],
            "year": [f"{year}" for year in years],
            "month": [f"{month:02}" for month in months],
            "day": [f"{day:02}" for day in days],
            "time": [f"{hour:02}:00" for hour in hours],
            "data_format": "netcdf",
            "download_format": "unarchived",
            "variable": [
                "100m_u_component_of_wind",
                "100m_v_component_of_wind",
                "10m_u_component_of_wind",
                "10m_v_component_of_wind",
                "instantaneous_10m_wind_gust",
                "2m_temperature",
                "surface_pressure",
                "total_precipitation",
                "cloud_base_height",
                "geopotential",
            ],
            "area": [
                round_to_quarter(self.lat + 0.5),
                round_to_quarter(self.lon - 0.5),
                round_to_quarter(self.lat - 0.5),
                round_to_quarter(self.lon + 0.5)
            ]
        }

        print("[Surface Data] Downloading data... (this may take several minutes)")
        out_path.parent.mkdir(parents=True, exist_ok=True)

        zip_path = self.root_path / f"{dataset}.zip"

        # download data
        client = cdsapi.Client()
        client.retrieve(dataset, request, zip_path)
        print(f"[Surface Data] Data downloaded to {zip_path}")

        # unzip files into root path
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(self.root_path)
        print(f"[Surface Data] Unzipped {zip_path}")

        # combined datasets
        instant_ds = xr.open_dataset(
            str(self.root_path / "data_stream-oper_stepType-instant.nc")
        )
        accum_ds = xr.open_dataset(
            str(self.root_path / "data_stream-oper_stepType-accum.nc")
        )
        # Extract total precipitation
        total_precip = accum_ds["tp"]

        # Make sure the coordinates align
        # If necessary, interpolate accum to instant grid
        if not instant_ds["valid_time"].equals(total_precip["valid_time"]):
            total_precip = total_precip.interp(time=instant_ds["valid_time"])

        # Add total precipitation to the instant dataset
        combined_ds = instant_ds.copy()
        combined_ds["tp"] = total_precip

        # Save the combined dataset
        combined_ds.to_netcdf(str(out_path))

        # Close working files
        instant_ds.close()
        accum_ds.close()

        print(f"[Surface Data] Combined unzipped files to {out_path}")

        # remove temporary file
        (self.root_path / "data_stream-oper_stepType-instant.nc").unlink(True)
        (self.root_path / "data_stream-oper_stepType-accum.nc").unlink(True)
        zip_path.unlink(True)
        print(f"[Surface Data] Removed temporary files")

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
            "product_type": ["reanalysis"],
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

    def convert_to_rocketpy_fmt(self, dataset: Literal["reanalysis-era5-single-levels", "reanalysis-era5-pressure-levels"]) -> None:
        import xarray as xr

        # paths
        path = self.path(dataset)
        outpath = self.path(dataset+"-rocketpy")
        if outpath.exists():
            print(f"[Format Converter] Using cached data")
            return

        # read file
        ds = xr.open_dataset(str(path))

        # rename valid_time to time
        if dataset == "reanalysis-era5-single-levels":
            rename_map = {
                "valid_time": "time"
            }
        elif dataset == "reanalysis-era5-pressure-levels":
            rename_map = {
                "valid_time": "time",
                "pressure_level": "level"
            }
        else:
            raise ValueError(f"{dataset} not supported")

        ds = ds.rename(rename_map)

        # write file
        ds.to_netcdf(str(outpath))

        print(f"[Format Converter] Convert to rocketpy format: {outpath}")

    def print_variables(self, dataset: Literal["reanalysis-era5-single-levels", "reanalysis-era5-pressure-levels"]) -> None:
        import xarray as xr
        path = self.path(dataset)
        ds = xr.open_dataset(str(path))
        print(ds)

    def EnvironmentalAnalysis(self) -> EnvironmentAnalysis:
        self.convert_to_rocketpy_fmt("reanalysis-era5-pressure-levels")
        self.convert_to_rocketpy_fmt("reanalysis-era5-single-levels")

        return EnvironmentAnalysis(
            start_date=self.start_date,
            end_date=self.end_date,
            latitude=self.lat,
            longitude=self.lon,
            start_hour=self.hours[0],
            end_hour=self.hours[-1],
            surface_data_file=self.path(
                "reanalysis-era5-single-levels-rocketpy"),
            pressure_level_data_file=self.path(
                "reanalysis-era5-pressure-levels-rocketpy"),
            max_expected_altitude=self.max_altitude,
            timezone="Europe/London"
        )


if __name__ == "__main__":
    lymm = EnvironmentalAnalysisManager(
        name="lymm",
        latitude=53.3784595126529,
        longitude=-2.453864922628811,
        years=list(range(2016, 2026)),
        months=[3],
        days=[23, 24, 25, 26, 27],
        hours=[13, 14, 15, 16, 17, 18],
        max_altitude=500,
    )

    lymm.download_levels_data()
    lymm.download_surface_data()

    # lymm.print_variables("reanalysis-era5-pressure-levels")
    # lymm.print_variables("reanalysis-era5-single-levels")

    env = lymm.EnvironmentalAnalysis()

    # print info
    env.prints.all()

    # temperature plots
    env.plots.average_surface_temperature_evolution()

    # wind plots speed
    env.plots.average_surface100m_wind_speed_evolution()
    env.plots.wind_gust_distribution()

    # wind direction
    env.plots.average_wind_heading_profile()

    # wind rose
    env.plots.average_wind_rose_grid()  # ! plots 14:00, 15:00, 16:00

    # wind speed profile
    env.plots.average_wind_speed_profile()

    quit()

    mrc = EnvironmentalAnalysisManager(
        name="mrc",
        latitude=52.669368807300984,
        longitude=-1.5236957546301024,
        years=list(range(2025, 2026)),
        months=[11],
        days=[9],
        hours=[13, 14],
        max_altitude=200,
    )

    mrc.download_levels_data()
    mrc.download_surface_data()

    # lymm.print_variables("reanalysis-era5-pressure-levels")
    # lymm.print_variables("reanalysis-era5-single-levels")

    env = mrc.EnvironmentalAnalysis()

    # print info
    env.prints.all()

    # temperature plots
    env.plots.average_surface_temperature_evolution()

    # wind plots speed
    env.plots.average_surface100m_wind_speed_evolution()
    env.plots.wind_gust_distribution()

    # wind direction
    env.plots.average_wind_heading_profile()

    # wind rose
    env.plots.average_wind_rose_grid()  # ! plots 14:00, 15:00, 16:00

    # wind speed profile
    env.plots.average_wind_speed_profile()

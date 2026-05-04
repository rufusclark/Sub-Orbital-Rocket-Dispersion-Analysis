"""Script for preparing files for xFoil"""
import matplotlib.pyplot as plt
import numpy as np
from numpy.typing import NDArray
from typing import Literal


class Airfoil:
    def __init__(self, name: str, xs: NDArray, ys: NDArray) -> None:
        self.name = name
        self.filename = f"{name}.dat"
        self.xs = xs
        self.ys = ys

    @classmethod
    def chamfered_airfoil(
        cls,
        name: str,
        chord: float,
        thickness: float,
        chamfer_angle_deg: float
    ) -> "Airfoil":
        semi_thickness = thickness / 2
        chamfer_length = semi_thickness * np.tan(np.radians(chamfer_angle_deg))

        xs = np.array([chord, chord-chamfer_length, chamfer_length, 0])
        ys = np.array([0, semi_thickness, semi_thickness, 0.1])

        return cls(
            name=name,
            xs=xs,
            ys=ys
        )

    def remove_duplicates(self) -> "Airfoil":
        xs = self.xs
        ys = self.ys
        n = len(xs)
        mask = np.ones(n, dtype=bool)

        mask[1:] = ~((xs[1:] == xs[:-1]) & (ys[1:] == ys[:-1]))

        return self.__class__(
            name=self.name,
            xs=xs[mask],
            ys=ys[mask]
        )

    def mirror(self) -> "Airfoil":
        return self.__class__(
            name=self.name,
            xs=np.concatenate([self.xs, self.xs[::-1]]),
            ys=np.concatenate([self.ys, -self.ys[::-1]]),
        ).remove_duplicates()

    def interpolate_linear(self, n=200) -> "Airfoil":
        from scipy.interpolate import interp1d

        xs = self.xs
        ys = self.ys

        # compute cumulative distance along points
        ds = np.sqrt(np.diff(xs)**2 + np.diff(ys)**2)
        s = np.zeros(len(xs))
        s[1:] = np.cumsum(ds)
        s_fine = np.linspace(0, s[-1], n)

        return self.__class__(
            name=self.name,
            xs=interp1d(s, xs, kind="linear")(s_fine),
            ys=interp1d(s, ys, kind="linear")(s_fine)
        )

    def interpolate(self, kind: Literal["linear", "cubic", "quadratic", "zero", "nearest", "nearest-up", "previous", "next", "slinear"], n=200) -> "Airfoil":
        from scipy.interpolate import interp1d

        xs = self.xs
        ys = self.ys

        # compute cumulative distance along points
        ds = np.sqrt(np.diff(xs)**2 + np.diff(ys)**2)
        s = np.zeros(len(xs))
        s[1:] = np.cumsum(ds)
        s_fine = np.linspace(0, s[-1], n)

        return self.__class__(
            name=self.name,
            xs=interp1d(s, xs, kind=kind)(s_fine),
            ys=interp1d(s, ys, kind=kind)(s_fine)
        )

    def to_dat_file(self) -> None:
        with open(self.filename, "w") as f:
            f.writelines([
                f"{self.name}\n",
                "".join([f"{x} {y}\n" for x, y in zip(self.xs, self.ys)])
            ])

        print(f"Wrote {self.name} to {self.filename}")

    def plot(self) -> None:
        plt.plot(self.xs, self.ys, marker="x")
        plt.title(self.name)
        plt.grid(True)
        plt.axis("equal")
        plt.show()


if __name__ == "__main__":

    airfoil = Airfoil.chamfered_airfoil(
        name="lpr-airfoil",
        chord=(45 + 30) / 2,
        chamfer_angle_deg=45,
        thickness=2
    )
    airfoil.plot()
    airfoil = airfoil.interpolate_linear(
        n=40).interpolate("quadratic").mirror()
    airfoil.plot()
    airfoil.to_dat_file()

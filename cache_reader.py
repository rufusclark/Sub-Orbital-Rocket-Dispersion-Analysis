from monte_carlo_manager import SimOutput
from enums import FlightOutcome
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import scienceplots
import numpy as np

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

filename = "./mpr-cache/reanalysis"
monte_dataset = SimOutput.read(f"{filename}.cache")
monte_dataset.plot_dispersion_analysis_no_impact(
    width=450,
    label_radii=[100, 200],
    actual_landing_point=(52.6693235, -1.5222396666666667),
    filename=f"{filename}.pdf",
    show=False
)

filename = "./mpr-cache/wind-estimation"
monte_dataset = SimOutput.read(f"{filename}.cache")
monte_dataset.plot_dispersion_analysis_no_impact(
    width=450,
    label_radii=[100, 200],
    actual_landing_point=(52.6693235, -1.5222396666666667),
    filename=f"{filename}.pdf",
    show=False
)

quit()

# Custom captions
captions = [
    "(a) Environment Variation",
    "(b) Launch Variation",
    "(c) Performance Variation",
    "(d) Flight Event Variation",
    "(e) Design and Manufacturing Variation",
    "(f) Combined Variations"
]

# # print full analysis
# full_output = SimOutput.read("./monte_carlo_cache/l4c.cache")
# full_output.plot_dispersion_analysis(
#     label_radii=label_radii,  # type: ignore
#     title="",
#     filename="l4c-all.png",
#     show=False
# )
# print("Saved l4c-all.png")

label_radii = [100]  # mpr
cache_folder = "./ukroc_monte_carlo_cache/"
out_file = "ukroc-monte"
view_factor = 1.2

# label_radii = [1000, 2000, 3000, 4000, 5000]  # l4c
# cache_folder = "./monte_carlo_cache2/l4c-"
# out_file = "l4c"
# view_factor = 1.1

outputs = [
    SimOutput.read(f"{cache_folder}environment.cache"),
    SimOutput.read(f"{cache_folder}launch.cache"),
    SimOutput.read(f"{cache_folder}performance.cache"),
    SimOutput.read(f"{cache_folder}flight-event.cache"),
    SimOutput.read(f"{cache_folder}design-and-manufacturing.cache"),
    SimOutput.read(f"{cache_folder}all.cache")
]
ideal_output = SimOutput.read(f"{cache_folder}ideal.cache")

x_ideal, y_ideal = ideal_output.mean_point()

print(
    f"{'case':40} {'distance [m]':15} {'1var area [m^2]':15} {'2var area [m^2]':15} {'3var area [m^2]':15}")
for out, caption in zip(outputs, captions):
    mean, angle, width, height, area = out.compute_ellipses()
    x, y = mean
    dx = x - x_ideal
    dy = y - y_ideal
    d = np.sqrt(dx**2 + dy**2)
    print(f"{caption:40} {d:15.2f} {' '.join([f'{a:15.2f}' for a in area])}")

print("Summary Table Created")

with open(f"{out_file}.csv", "w") as f:
    f.write(
        f"{'Variations'},{'Distance [m]'},{r'$1\sigma$ area [m^2]'},{r'$2\sigma$ area [m^2]'},{r'$3\sigma$ area [m^2]'},{r'$1\sigma$ diameter [m]'},{r'$2\sigma$ diameter [m]'},{r'$3\sigma$ diameter [m]'},\n"
    )
    for out, caption in zip(outputs, captions):
        mean, angle, width, height, area = out.compute_ellipses()
        x, y = mean
        dx = x - x_ideal
        dy = y - y_ideal
        d = np.sqrt(dx**2 + dy**2)
        diameter_eq = 0.5 * (width + height)
        f.write(
            f"{caption.split(") ")[1].split(" Variation")[0]},{d},{','.join([f'{a}' for a in area])},{
                ','.join([f'{dia}' for dia in diameter_eq])}\n"
        )

print(f"Summary Table Created (csv) ({out_file}.csv)")

#
# Compute Sensitivity
#

#
# Plot
#

# Create 3x2 grid
fig, axes = plt.subplots(
    nrows=3,
    ncols=2,
    figsize=(6.5, 9.4),
    subplot_kw={"projection": ideal_output.map_crs},
    constrained_layout=True
)
axes = axes.flatten()

# Define shared colormap & normalization across all outputs
all_energies = np.hstack([out.impact_energy for out in outputs])
cmap = plt.get_cmap("viridis")
# norm = mcolors.Normalize(vmin=all_energies.min(), vmax=all_energies.max())
min_positive = all_energies[all_energies > 0].min()  # smallest positive energy
all_energies_clipped = np.clip(all_energies, min_positive, None)
norm = mcolors.LogNorm(vmin=all_energies_clipped.min(),
                       vmax=all_energies_clipped.max())

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


radius = max([view_factor * max(np.abs(out.x_pos).max(), np.abs(out.y_pos).max())
              for out in outputs])

for i, out in enumerate(outputs):
    ax = axes[i]

    # Map bounds
    ax.set_extent([-radius, radius, -radius, radius], crs=out.data_local_crs)

    out.add_satellite_maps(ax, radius)

    # plot launch point
    ax.scatter(
        0,
        0,
        s=200,
        marker="*",
        edgecolors="black",
        linewidths=1.5,
        transform=out.data_local_crs,
        label="Launch Point",
        zorder=10
    )

    # Scatter points for each failure mode
    for mode in list(marker_map.keys()):
        mask = mode == out.failure_mode
        if not len(out.x_pos[mask]):
            continue

        ax.scatter(
            out.x_pos[mask],
            out.y_pos[mask],
            c=np.clip(out.impact_energy[mask], min_positive, None),
            cmap=cmap,
            norm=norm,
            marker=marker_map.get(mode),
            s=30,
            transform=out.data_local_crs,
            alpha=0.6,
            label=failure_name_map[mode],
            zorder=5 if mode == FlightOutcome.NOMINAL else 6
        )

        # add ellipses
        if out.n > 1:
            out.add_ellipses(ax, [1, 2, 3])

        # add north arrow
        out.add_north_arrow(ax, -radius*0.94, -radius*0.94, radius*0.15)

        # add heading angle
        if out.fm.flight.inclination.ideal != 90:
            out.add_heading_arrow(
                ax, out.fm.flight.heading.ideal, radius*0.2)

        # add wind arrow
        out.add_wind_arrow(
            ax,
            out.fm.env.wind_heading.ideal + 180,  # type: ignore
            radius,
            corner_offset=0.92,
            y_shift=0.02
        )

        # add distance rings
        out.add_range_rings(ax, 0, 0, label_radii)

    # Subplot caption
    # ax.set_title(captions[i], fontsize=12, loc="center")
    ax.text(0.5, -0.08, captions[i],
            transform=ax.transAxes, ha="center", fontsize=12)

# Shared colorbar
sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
sm.set_array([])
cbar = fig.colorbar(sm, ax=axes, orientation="vertical", fraction=0.03)
cbar.set_label("Impact Energy (J)")

# Shared legend
all_handles = []
all_labels = []
for ax in axes:
    handles, labels = ax.get_legend_handles_labels()
    all_handles.extend(handles)
    all_labels.extend(labels)
unique = {}
for handle, label in zip(all_handles, all_labels):
    if label not in unique:
        unique[label] = handle


fig.legend(unique.values(), unique.keys(), loc="outside lower center", ncol=4)

plt.savefig(f"{out_file}.png")
print(f"Saved {out_file}.png")
plt.savefig(f"{out_file}.pdf")
print(f"Saved {out_file}.pdf")

# plt.show()

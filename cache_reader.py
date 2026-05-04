from monte_carlo_manager import SimOutput
from enums import FlightOutcome
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np


monte_dataset = SimOutput.read("./monte_carlo_cache/mpr.cache")
monte_dataset.plot_dispersion_analysis(
    label_radii=[],
    actual_landing_point=(52.6693235, -1.5222396666666667),
    title="",
    filename="mpr.png"
)

label_radii = [1000, 2000, 3000, 4000, 5000]

# Custom captions
captions = [
    "a) Environment Variation",
    "b) Launch Variation",
    "c) Performance Variation",
    "d) Flight Event Variation",
    "e) Design and Manufacturing Variation"
]

# print full analysis
full_output = SimOutput.read("./monte_carlo_cache/l4c.cache")
full_output.plot_dispersion_analysis(
    label_radii=label_radii,  # type: ignore
    title="",
    filename="l4c-all.png"
)

print("Saved l4c-all.png")

outputs = [
    SimOutput.read("./monte_carlo_cache/l4c-environment.cache"),
    SimOutput.read("./monte_carlo_cache/l4c-launch.cache"),
    SimOutput.read("./monte_carlo_cache/l4c-performance.cache"),
    SimOutput.read("./monte_carlo_cache/l4c-flight-event.cache"),
    SimOutput.read("./monte_carlo_cache/l4c-design-and-manufacturing.cache"),
]

ideal_output = SimOutput.read("./monte_carlo_cache/l4c-ideal.cache")
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
    figsize=(9, 12),
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
    FlightOutcome.SHRED: "<"
}

failure_name_map = {
    FlightOutcome.NOMINAL: "Nominal",
    FlightOutcome.CORE_SAMPLE: "Ballistic",
    FlightOutcome.LAWN_DART: "Ballistic\n(without nose)",
    FlightOutcome.MOTOR_CATO: "Motor CATO",
    FlightOutcome.SEPARATION: "Freefall\nfrom deployment",
    FlightOutcome.SHRED: "Disintegrate"
}

# For mystery 5th axis
captions.insert(4, "please fit nicely :)")
outputs.insert(4, ideal_output)

for i, out in enumerate(outputs):
    ax = axes[i]

    # Map bounds
    radius = 1.2 * max(np.abs(out.x_pos).max(), np.abs(out.y_pos).max())
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
        out.add_north_arrow(ax, -radius*0.94, -radius*0.94, radius*0.12)

        # add heading angle
        if out.fm.flight.inclination.ideal != 90:
            out.add_heading_arrow(
                ax, out.fm.flight.heading.ideal, radius*0.2)

        # add wind arrow
        out.add_wind_arrow(
            ax,
            out.fm.env.wind_heading.ideal + 180,  # type: ignore
            radius
        )

        # add distance rings
        out.add_range_rings(ax, 0, 0, label_radii)

    # Subplot caption
    ax.set_title(captions[i], fontsize=12, loc="center")

# Remove 5th empty subplot
axes[-2].set_visible(False)
# fig.delaxes(axes[-2])

# Shared colorbar
sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
sm.set_array([])
cbar = fig.colorbar(sm, ax=axes[:-1], orientation="vertical", fraction=0.03)
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


fig.legend(unique.values(), unique.keys(), loc="upper right")

plt.savefig("l4c.png")
print("Saved l4c.png")

plt.show()


# TODO: Plot all
# TODO: Share cmap?
# TODO: Share legend?
# TODO: Correct captioning
# TODO: log scale cmap
# TODO: Sensitivity

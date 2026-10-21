"""
Exploratory Data Analysis and meteorological visualization module for वज्रSense.
Generates informative, publication-quality figures capturing Mumbai's
coastal convective dynamics, diurnal cycles, and thermodynamic phase spaces.
"""

import logging
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")  # Non-interactive CPU backend
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from vajrasense.config import (
    FIGURES_DIR,
    DATA_PROCESSED_DIR,
    ENGINEERED_DATA_FILENAME,
)

logger = logging.getLogger("vajrasense.visualization")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [VajraSense:Visualizer] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class VajraVisualizer:
    """
    Renders domain-specific meteorological plots for Mumbai nowcasting analysis.
    """

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = Path(output_dir or FIGURES_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # Apply standard clean styling
        plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
        plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Helvetica"]
        plt.rcParams["axes.edgecolor"] = "#cccccc"
        plt.rcParams["axes.linewidth"] = 0.8

    def plot_diurnal_convective_cycle(self, df: pd.DataFrame) -> Path:
        """
        Plots hourly diurnal cycle of CAPE and convective event probability in Mumbai.
        Reveals afternoon boundary layer destabilization and sea-breeze convergence.
        """
        df_copy = df.copy()
        if "time" in df_copy.columns:
            df_copy["time"] = pd.to_datetime(df_copy["time"])
            df_copy["hour"] = df_copy["time"].dt.hour
        else:
            df_copy["hour"] = np.arange(len(df_copy)) % 24

        diurnal = df_copy.groupby("hour").agg(
            mean_cape=("cape", "mean"),
            std_cape=("cape", "std"),
            mean_li=("lifted_index", "mean"),
            convective_prob=("convective_event_now", "mean"),
        )

        fig, ax1 = plt.subplots(figsize=(10, 5), dpi=150)
        ax2 = ax1.twinx()

        hours = diurnal.index

        # CAPE fill and line
        ax1.plot(
            hours,
            diurnal["mean_cape"],
            color="#d95f02",
            linewidth=2.5,
            label="Mean CAPE (J/kg)",
            marker="o",
            markersize=4,
        )
        ax1.fill_between(
            hours,
            (diurnal["mean_cape"] - 0.5 * diurnal["std_cape"]).clip(lower=0),
            diurnal["mean_cape"] + 0.5 * diurnal["std_cape"],
            color="#d95f02",
            alpha=0.18,
            label="CAPE ±0.5σ Spread",
        )
        ax1.set_xlabel("Hour of Day (IST)", fontsize=11, fontweight="bold")
        ax1.set_ylabel("CAPE (J/kg)", color="#d95f02", fontsize=11, fontweight="bold")
        ax1.tick_params(axis="y", labelcolor="#d95f02")
        ax1.set_xticks(range(0, 24, 2))
        ax1.grid(True, linestyle="--", alpha=0.5)

        # Convective Event Frequency
        ax2.bar(
            hours,
            diurnal["convective_prob"] * 100,
            color="#1b9e77",
            alpha=0.4,
            width=0.6,
            label="Convective Event Frequency (%)",
        )
        ax2.set_ylabel(
            "Event Probability (%)", color="#1b9e77", fontsize=11, fontweight="bold"
        )
        ax2.tick_params(axis="y", labelcolor="#1b9e77")

        plt.title(
            "VajraSense: Mumbai Diurnal Convective Cycle & Instability Profile",
            fontsize=13,
            fontweight="bold",
            pad=14,
        )

        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", framealpha=0.9)

        fig.tight_layout()
        out_path = self.output_dir / "diurnal_convective_cycle.png"
        fig.savefig(out_path)
        plt.close(fig)
        logger.info(f"Saved diurnal plot to: {out_path}")
        return out_path

    def plot_seasonal_monsoon_profile(self, df: pd.DataFrame) -> Path:
        """
        Plots monthly aggregation of temperature, precipitation, and convective events.
        Highlights Pre-Monsoon vs Southwest Monsoon vs Post-Monsoon behavior.
        """
        df_copy = df.copy()
        df_copy["time"] = pd.to_datetime(df_copy["time"])
        df_copy["month"] = df_copy["time"].dt.month

        monthly = df_copy.groupby("month").agg(
            mean_temp=("temperature_2m", "mean"),
            mean_dew=("dew_point_2m", "mean"),
            total_rain=("precipitation", "sum"),
            mean_cape=("cape", "mean"),
            convective_hours=("convective_event_now", "sum"),
        )

        months = [
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
        ]

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8), dpi=150, sharex=True)

        # Top panel: Thermal & Instability (Temp, Dew Point, CAPE)
        ax1_twin = ax1.twinx()
        ax1.plot(
            monthly.index,
            monthly["mean_temp"],
            color="#e41a1c",
            marker="s",
            label="Surface Temp (°C)",
            linewidth=2,
        )
        ax1.plot(
            monthly.index,
            monthly["mean_dew"],
            color="#377eb8",
            marker="^",
            label="Dew Point (°C)",
            linewidth=2,
        )
        ax1_twin.plot(
            monthly.index,
            monthly["mean_cape"],
            color="#ff7f00",
            marker="o",
            linestyle="--",
            label="Mean CAPE (J/kg)",
            linewidth=2,
        )

        ax1.set_ylabel("Temperature (°C)", fontsize=10, fontweight="bold")
        ax1_twin.set_ylabel("CAPE (J/kg)", color="#ff7f00", fontsize=10, fontweight="bold")
        ax1_twin.tick_params(axis="y", labelcolor="#ff7f00")
        ax1.set_title(
            "Mumbai Seasonal Atmospheric Profile & Convective Energy (Pre-Monsoon vs Monsoon)",
            fontsize=12,
            fontweight="bold",
        )
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax1_twin.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", framealpha=0.9)
        ax1.grid(True, linestyle="--", alpha=0.5)

        # Bottom panel: Precipitation and Convective Frequency
        ax2_twin = ax2.twinx()
        bars = ax2.bar(
            monthly.index - 0.2,
            monthly["total_rain"],
            width=0.4,
            color="#4daf4a",
            label="Total Rain (mm)",
            alpha=0.8,
        )
        bars2 = ax2_twin.bar(
            monthly.index + 0.2,
            monthly["convective_hours"],
            width=0.4,
            color="#984ea3",
            label="Convective Event Hours",
            alpha=0.8,
        )

        ax2.set_ylabel("Rainfall (mm)", color="#2b8cbe", fontsize=10, fontweight="bold")
        ax2_twin.set_ylabel("Convective Hours", color="#984ea3", fontsize=10, fontweight="bold")
        ax2.set_xticks(range(1, 13))
        ax2.set_xticklabels(months, fontsize=10, fontweight="bold")
        ax2.set_xlabel("Month", fontsize=11, fontweight="bold")
        ax2.legend([bars, bars2], ["Rainfall (mm)", "Convective Hours"], loc="upper left", framealpha=0.9)
        ax2.grid(True, linestyle="--", alpha=0.5)

        fig.tight_layout()
        out_path = self.output_dir / "seasonal_monsoon_profile.png"
        fig.savefig(out_path)
        plt.close(fig)
        logger.info(f"Saved seasonal profile plot to: {out_path}")
        return out_path

    def plot_thermodynamic_phase_space(self, df: pd.DataFrame) -> Path:
        """
        Plots CAPE vs Lifted Index phase space scatter plot colored by Dew Point Depression.
        Delineates the hazardous high-instability convective regime.
        """
        fig, ax = plt.subplots(figsize=(9, 6), dpi=150)

        # Sample for plotting clarity if dataset is large
        plot_sample = df.sample(n=min(len(df), 4000), random_state=42)

        scatter = ax.scatter(
            plot_sample["cape"],
            plot_sample["lifted_index"],
            c=plot_sample["dew_point_depression"],
            cmap="viridis_r",
            alpha=0.6,
            s=22,
            edgecolors="none",
        )

        cbar = plt.colorbar(scatter, ax=ax)
        cbar.set_label("Dew Point Depression (T - Td) [°C]", fontsize=10, fontweight="bold")

        # Invert Lifted Index Y-axis so highly negative (unstable) values are at the top
        ax.invert_yaxis()
        ax.axhline(-2.0, color="crimson", linestyle="--", linewidth=1.2, label="Unstable Threshold (LI = -2°C)")
        ax.axvline(1000.0, color="darkorange", linestyle="--", linewidth=1.2, label="Moderate CAPE (1000 J/kg)")

        # Shaded danger box
        ax.axhspan(-15, -2, xmin=1000/6000, xmax=1.0, color="red", alpha=0.08, label="Severe Convective Regime")

        ax.set_xlabel("Convective Available Potential Energy - CAPE (J/kg)", fontsize=11, fontweight="bold")
        ax.set_ylabel("Lifted Index (°C, Inverted)", fontsize=11, fontweight="bold")
        ax.set_title("Mumbai Atmospheric Instability Phase Space (CAPE vs Lifted Index)", fontsize=12, fontweight="bold")
        ax.legend(loc="lower left", framealpha=0.9)
        ax.grid(True, linestyle="--", alpha=0.5)

        fig.tight_layout()
        out_path = self.output_dir / "thermodynamic_phase_space.png"
        fig.savefig(out_path)
        plt.close(fig)
        logger.info(f"Saved phase space plot to: {out_path}")
        return out_path

    def plot_pressure_wind_storm_signature(self, df: pd.DataFrame) -> Path:
        """
        Finds a prominent severe storm day in Mumbai and plots a 72-hour detailed time series
        displaying the pressure drop, gust spike, cold pool temperature drop, and precipitation.
        """
        df_copy = df.copy()
        df_copy["time"] = pd.to_datetime(df_copy["time"])

        # Locate timestamp with high convective activity and wind gusts
        storm_candidates = df_copy[
            (df_copy["wind_gusts_10m"] > 35) & (df_copy["precipitation"] > 3.0)
        ]
        if not storm_candidates.empty:
            peak_time = storm_candidates.iloc[0]["time"]
        else:
            peak_time = df_copy.loc[df_copy["cape"].idxmax()]["time"]

        window_start = peak_time - pd.Timedelta(hours=36)
        window_end = peak_time + pd.Timedelta(hours=36)
        sub_df = df_copy[(df_copy["time"] >= window_start) & (df_copy["time"] <= window_end)].copy()

        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(11, 9), dpi=150, sharex=True)

        # Panel 1: Temperature & Dew Point
        ax1.plot(sub_df["time"], sub_df["temperature_2m"], color="#e41a1c", label="Temperature (°C)", linewidth=2)
        ax1.plot(sub_df["time"], sub_df["dew_point_2m"], color="#377eb8", linestyle="--", label="Dew Point (°C)", linewidth=2)
        ax1.set_ylabel("Temp (°C)", fontsize=10, fontweight="bold")
        ax1.set_title(
            f"Mumbai Severe Convective Event Signature ({window_start.strftime('%d %b %Y')} to {window_end.strftime('%d %b %Y')})",
            fontsize=12,
            fontweight="bold",
        )
        ax1.legend(loc="upper left")
        ax1.grid(True, linestyle="--", alpha=0.5)

        # Panel 2: Surface Pressure
        ax2.plot(sub_df["time"], sub_df["surface_pressure"], color="#984ea3", label="Surface Pressure (hPa)", linewidth=2)
        ax2.set_ylabel("Pressure (hPa)", fontsize=10, fontweight="bold")
        ax2.legend(loc="upper left")
        ax2.grid(True, linestyle="--", alpha=0.5)

        # Panel 3: Wind Gusts & Precipitation
        ax3_twin = ax3.twinx()
        ax3.bar(sub_df["time"], sub_df["precipitation"], width=0.03, color="#4daf4a", alpha=0.7, label="Rain (mm/h)")
        ax3_twin.plot(sub_df["time"], sub_df["wind_gusts_10m"], color="#ff7f00", label="Wind Gusts (km/h)", linewidth=2)

        ax3.set_ylabel("Rain (mm/h)", color="#4daf4a", fontsize=10, fontweight="bold")
        ax3_twin.set_ylabel("Gust (km/h)", color="#ff7f00", fontsize=10, fontweight="bold")
        ax3.set_xlabel("Time (IST)", fontsize=10, fontweight="bold")
        ax3.grid(True, linestyle="--", alpha=0.5)

        fig.tight_layout()
        out_path = self.output_dir / "pressure_wind_storm_signature.png"
        fig.savefig(out_path)
        plt.close(fig)
        logger.info(f"Saved storm signature plot to: {out_path}")
        return out_path

    def plot_feature_correlation_heatmap(self, df: pd.DataFrame) -> Path:
        """
        Plots a feature correlation matrix against nowcasting targets.
        """
        target_cols = [
            "target_nowcast_1h",
            "cape",
            "lifted_index",
            "convective_inhibition",
            "dew_point_depression",
            "theta_e_proxy",
            "vertical_wind_shear",
            "pressure_tendency_1h",
            "temp_drop_1h",
            "wind_gusts_10m",
            "relative_humidity_2m",
            "precipitation",
        ]
        available_cols = [c for c in target_cols if c in df.columns]
        corr = df[available_cols].corr()

        fig, ax = plt.subplots(figsize=(10, 8), dpi=150)
        cax = ax.imshow(corr, cmap="coolwarm", vmin=-1, vmax=1)
        fig.colorbar(cax, ax=ax, fraction=0.046, pad=0.04)

        ax.set_xticks(range(len(available_cols)))
        ax.set_yticks(range(len(available_cols)))
        ax.set_xticklabels(available_cols, rotation=45, ha="right", fontsize=9, fontweight="bold")
        ax.set_yticklabels(available_cols, fontsize=9, fontweight="bold")

        # Annotate numbers in heatmap
        for i in range(len(available_cols)):
            for j in range(len(available_cols)):
                val = corr.iloc[i, j]
                ax.text(
                    j, i, f"{val:.2f}",
                    ha="center", va="center",
                    color="white" if abs(val) > 0.45 else "black",
                    fontsize=7.5,
                )

        ax.set_title("VajraSense Predictor Correlation Matrix with Nowcast Target", fontsize=12, fontweight="bold", pad=12)
        fig.tight_layout()

        out_path = self.output_dir / "feature_correlation_heatmap.png"
        fig.savefig(out_path)
        plt.close(fig)
        logger.info(f"Saved correlation heatmap to: {out_path}")
        return out_path

    def generate_all_visualizations(
        self,
        df_features: Optional[pd.DataFrame] = None,
        input_csv_path: Optional[Path] = None,
    ) -> dict:
        """
        Generates and saves all exploratory atmospheric figures.
        """
        if df_features is None:
            if input_csv_path is None:
                input_csv_path = DATA_PROCESSED_DIR / ENGINEERED_DATA_FILENAME
            logger.info(f"Loading engineered feature dataset from: {input_csv_path}")
            df = pd.read_csv(input_csv_path)
        else:
            df = df_features.copy()

        logger.info("Generating comprehensive exploratory visualizations...")
        paths = {
            "diurnal": self.plot_diurnal_convective_cycle(df),
            "seasonal": self.plot_seasonal_monsoon_profile(df),
            "phase_space": self.plot_thermodynamic_phase_space(df),
            "storm_signature": self.plot_pressure_wind_storm_signature(df),
            "correlation_matrix": self.plot_feature_correlation_heatmap(df),
        }
        logger.info(f"All {len(paths)} visualization figures saved successfully.")
        return paths

"""
Main orchestrator and CLI entrypoint for वज्रSense (VajraSense).
Runs ingestion, cleaning, feature engineering, exploratory data visualization,
and ML nowcasting baseline pipeline.

Usage:
  python main.py --run-all
  python main.py --download --start-date 2022-01-01 --end-date 2024-12-31
  python main.py --clean
  python main.py --features
  python main.py --visualize
  python main.py --train --model-type hist_gb
"""

import argparse
import logging
import sys
from pathlib import Path

from vajrasense.config import (
    DEFAULT_START_DATE,
    DEFAULT_END_DATE,
    DATA_RAW_DIR,
    RAW_DATA_FILENAME,
    DATA_PROCESSED_DIR,
    CLEAN_DATA_FILENAME,
    ENGINEERED_DATA_FILENAME,
)
from vajrasense.ingestion import OpenMeteoIngestion
from vajrasense.preprocessing import DataCleaner
from vajrasense.feature_engineering import AtmosphericFeatureEngineer
from vajrasense.visualization import VajraVisualizer
from vajrasense.pipeline import NowcastingPipeline

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [VajraSense] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("vajrasense.main")


def run_pipeline(
    download: bool = False,
    clean: bool = False,
    features: bool = False,
    visualize: bool = False,
    train: bool = False,
    start_date: str = DEFAULT_START_DATE,
    end_date: str = DEFAULT_END_DATE,
    model_type: str = "hist_gb",
    target: str = "target_nowcast_1h",
) -> None:
    """
    Executes selected components of the वज्रSense pipeline.
    """
    raw_csv = DATA_RAW_DIR / RAW_DATA_FILENAME
    clean_csv = DATA_PROCESSED_DIR / CLEAN_DATA_FILENAME
    engineered_csv = DATA_PROCESSED_DIR / ENGINEERED_DATA_FILENAME

    logger.info("=" * 65)
    logger.info("  वज्रSense (VajraSense): Mumbai Convective Nowcasting System  ")
    logger.info("=" * 65)

    # 1. Ingestion Step
    if download:
        logger.info(f">> STEP 1: Ingesting Mumbai Weather Data [{start_date} to {end_date}]")
        ingestion = OpenMeteoIngestion()
        ingestion.download_historical_archive(
            start_date=start_date,
            end_date=end_date,
            output_filepath=raw_csv,
            chunk_years=True,
        )

    # 2. Cleaning Step
    if clean:
        logger.info(">> STEP 2: Cleaning & Validating Atmospheric Observations")
        cleaner = DataCleaner()
        cleaner.clean_weather_data(
            input_csv_path=raw_csv,
            output_csv_path=clean_csv,
        )

    # 3. Feature Engineering Step
    if features:
        logger.info(">> STEP 3: Computing Atmospheric Instability & Tendency Features")
        engineer = AtmosphericFeatureEngineer()
        engineer.transform(
            input_csv_path=clean_csv,
            output_csv_path=engineered_csv,
        )

    # 4. Exploratory Data Analysis & Visualizations
    if visualize:
        logger.info(">> STEP 4: Rendering Exploratory Visualizations & Thermodynamic Plots")
        visualizer = VajraVisualizer()
        saved_plots = visualizer.generate_all_visualizations(input_csv_path=engineered_csv)
        for name, path in saved_plots.items():
            logger.info(f"   [+] {name.capitalize()} Plot: {path.name}")

    # 5. Model Training & Evaluation
    if train:
        logger.info(f">> STEP 5: Building & Training Nowcasting Model [{model_type}] on CPU")
        pipeline = NowcastingPipeline(target_column=target, model_type=model_type)
        X_train, X_test, y_train, y_test = pipeline.prepare_data(input_csv_path=engineered_csv)
        results = pipeline.train_and_evaluate(X_train, X_test, y_train, y_test)
        saved_model_path = pipeline.save_pipeline()
        logger.info(f"Pipeline artifact saved to: {saved_model_path.name}")

    logger.info("=" * 65)
    logger.info("  वज्रSense Execution Completed Successfully!  ")
    logger.info("=" * 65)


def parse_args():
    parser = argparse.ArgumentParser(
        description="वज्रSense: Mumbai Thunderstorm & Lightning Nowcasting System"
    )
    parser.add_argument(
        "--run-all",
        action="store_true",
        help="Run end-to-end pipeline: ingestion, cleaning, features, EDA, and model training.",
    )
    parser.add_argument("--download", action="store_true", help="Download raw weather data from Open-Meteo.")
    parser.add_argument("--clean", action="store_true", help="Clean raw weather data and validate bounds.")
    parser.add_argument("--features", action="store_true", help="Generate meteorological and rolling features.")
    parser.add_argument("--visualize", action="store_true", help="Generate and save all EDA figures.")
    parser.add_argument("--train", action="store_true", help="Train baseline nowcasting model on CPU.")
    parser.add_argument("--start-date", type=str, default=DEFAULT_START_DATE, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, default=DEFAULT_END_DATE, help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--model-type",
        type=str,
        default="hist_gb",
        choices=["hist_gb", "random_forest", "logistic_regression"],
        help="Classifier architecture (CPU-friendly)",
    )
    parser.add_argument(
        "--target",
        type=str,
        default="target_nowcast_1h",
        help="Nowcast prediction target (e.g. target_nowcast_1h, target_nowcast_2h, target_nowcast_3h)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # If run-all is specified, enable every step
    if args.run_all:
        args.download = True
        args.clean = True
        args.features = True
        args.visualize = True
        args.train = True
    elif not any([args.download, args.clean, args.features, args.visualize, args.train]):
        logger.info("No specific flags provided. Defaulting to --run-all.")
        args.download = True
        args.clean = True
        args.features = True
        args.visualize = True
        args.train = True

    try:
        run_pipeline(
            download=args.download,
            clean=args.clean,
            features=args.features,
            visualize=args.visualize,
            train=args.train,
            start_date=args.start_date,
            end_date=args.end_date,
            model_type=args.model_type,
            target=args.target,
        )
    except Exception as ex:
        logger.error(f"Execution failed: {ex}", exc_info=True)
        sys.exit(1)

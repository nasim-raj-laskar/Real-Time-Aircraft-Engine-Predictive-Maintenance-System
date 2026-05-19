from evidently import Report
from evidently.presets import (
    DataDriftPreset,
    DataSummaryPreset
)

import pandas as pd
import logging

from pathlib import Path
from datetime import datetime
from typing import Dict

from scipy.stats import ks_2samp


# Logging Configuration
logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


# Drift Detector
class DriftDetector:
    """
    Detects data drift between reference data
    and current production data.
    """

    def __init__(
        self,
        reference_data_path: Path
    ):

        # Load Reference Dataset

        self.reference_df = pd.read_parquet(
            reference_data_path
        )

        # Important Engine Sensor Columns

        self.sensor_cols = [
            f"s{i}"
            for i in [
                2, 3, 4, 7, 9,
                11, 12, 14,
                17, 20, 21
            ]
        ]

        # Keep only existing columns
        self.sensor_cols = [

            col

            for col in self.sensor_cols

            if col in self.reference_df.columns
        ]

        if not self.sensor_cols:

            raise ValueError(
                "No valid sensor columns "
                "found in reference dataset."
            )

        logger.info(
            "Loaded reference dataset."
        )

        logger.info(
            f"Using sensor columns: "
            f"{self.sensor_cols}"
        )

    # Main Drift Detection
    def check_drift(
        self,
        current_data: pd.DataFrame
    ) -> Dict:

        try:

            # Validate Incoming Columns
            available_cols = [

                col

                for col in self.sensor_cols

                if col in current_data.columns
            ]

            missing_cols = list(
                set(self.sensor_cols)
                - set(available_cols)
            )

            if missing_cols:

                logger.warning(
                    f"Missing columns in "
                    f"current data: {missing_cols}"
                )

            if not available_cols:

                raise ValueError(
                    "No matching sensor columns "
                    "found in current data."
                )

            # Manual Drift Detection
            # Using KS Statistical Test
            drifted_features = []

            p_values = {}

            for col in available_cols:

                reference_values = (

                    self.reference_df[col]
                    .dropna()
                    .values
                )

                current_values = (

                    current_data[col]
                    .dropna()
                    .values
                )

                # Skip empty arrays
                if (
                    len(reference_values) == 0
                    or len(current_values) == 0
                ):
                    continue

                # Kolmogorov-Smirnov Test
                statistic, p_value = ks_2samp(
                    reference_values,
                    current_values
                )

                p_values[col] = float(p_value)

                # Drift threshold
                if p_value < 0.05:

                    drifted_features.append(col)

            # Drift Share
            drift_share = (

                len(drifted_features)
                / len(available_cols)

            )
            # Final Analysis Result
            analysis_result = {

                "timestamp":
                    datetime.now().isoformat(),

                "drift_detected":
                    drift_share > 0.3,

                "drift_share":
                    round(float(drift_share), 4),

                "drifted_features":
                    drifted_features,

                "feature_p_values":
                    p_values,

                "total_features":
                    len(available_cols),

                "missing_features":
                    missing_cols,

                "alert_level":
                    self._get_alert_level(
                        drift_share
                    )
            }

            logger.info(
                f"Drift analysis completed. "
                f"Drift share: {drift_share:.2f}"
            )

            return analysis_result

        # Error Handling
        except Exception as e:

            logger.exception(
                "Drift detection failed."
            )

            return {

                "timestamp":
                    datetime.now().isoformat(),

                "error":
                    str(e),

                "drift_detected":
                    False,

                "drift_share":
                    0.0,

                "drifted_features":
                    [],

                "feature_p_values":
                    {},

                "total_features":
                    0,

                "missing_features":
                    [],

                "alert_level":
                    "ERROR"
            }

    # Alert Severity Logic
    def _get_alert_level(
        self,
        drift_share: float
    ) -> str:

        if drift_share > 0.5:
            return "CRITICAL"

        elif drift_share > 0.3:
            return "WARNING"

        return "OK"

    # Save Evidently HTML Report
    def save_report(
        self,
        current_data: pd.DataFrame,
        output_path: Path
    ):

        try:

            # Create output directory
            output_path.parent.mkdir(
                parents=True,
                exist_ok=True
            )

            # Simple fallback HTML report
            with open(
                output_path,
                "w",
                encoding="utf-8"
            ) as f:

                f.write(
                    f"""
                    <html>

                    <head>
                        <title>Drift Report</title>
                    </head>

                    <body>

                        <h1>
                        Aircraft Engine Drift Report
                        </h1>

                        <p>
                        Generated at:
                        {datetime.now().isoformat()}
                        </p>

                        <h2>
                        Drift Detection Summary
                        </h2>

                        <p>
                        Statistical drift detection
                        completed successfully.
                        </p>

                        <p>
                        Evidently HTML rendering was
                        unavailable in the installed
                        version.
                        </p>

                    </body>

                    </html>
                    """
                )

            logger.info(
                f"Fallback drift report saved to: "
                f"{output_path}"
            )

        except Exception:

            logger.exception(
                "Failed to save report."
            )
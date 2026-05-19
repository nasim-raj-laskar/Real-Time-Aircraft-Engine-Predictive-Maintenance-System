from evidently import Report
try:
    from evidently.metric_preset import DataDriftPreset, DataQualityPreset
except ImportError:
    from evidently.metrics import DataDriftPreset, DataQualityPreset
import pandas as pd
from pathlib import Path
from datetime import datetime


class DriftDetector:
    def __init__(self, reference_data_path: Path):
        """
        Initialize drift detector with reference data.
        
        Args:
            reference_data_path: Path to training data (reference distribution)
        """
        self.reference_df = pd.read_parquet(reference_data_path)
        self.sensor_cols = [f's{i}' for i in [2, 3, 4, 7, 9, 11, 12, 14, 17, 20, 21]]
    
    def check_drift(self, current_data: pd.DataFrame) -> dict:
        """
        Compare current data against reference distribution.
        
        Args:
            current_data: Recent production data
            
        Returns:
            dict with drift metrics and alerts
        """
        # Create report
        report = Report(metrics=[
            DataDriftPreset(),
            DataQualityPreset()
        ])
        
        # Run report
        report.run(
            reference_data=self.reference_df[self.sensor_cols],
            current_data=current_data[self.sensor_cols]
        )
        
        # Extract results
        result = report.as_dict()
        
        # Parse drift metrics
        drift_metrics = result['metrics'][0]['result']
        
        drifted_features = [
            col for col, stats in drift_metrics['drift_by_columns'].items()
            if stats['drift_detected']
        ]
        
        drift_share = drift_metrics['share_of_drifted_columns']
        
        return {
            'timestamp': datetime.now().isoformat(),
            'drift_detected': drift_share > 0.3,
            'drift_share': drift_share,
            'drifted_features': drifted_features,
            'total_features': len(self.sensor_cols),
            'alert_level': self._get_alert_level(drift_share)
        }
    
    def _get_alert_level(self, drift_share: float) -> str:
        """Determine alert level based on drift share."""
        if drift_share > 0.5:
            return 'CRITICAL'
        elif drift_share > 0.3:
            return 'WARNING'
        else:
            return 'OK'
    
    def save_report(self, current_data: pd.DataFrame, output_path: Path):
        """Generate and save HTML drift report."""
        report = Report(metrics=[DataDriftPreset()])
        report.run(
            reference_data=self.reference_df[self.sensor_cols],
            current_data=current_data[self.sensor_cols]
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        report.save_html(str(output_path))

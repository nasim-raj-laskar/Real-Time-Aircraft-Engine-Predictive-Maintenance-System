import schedule
import time
import pandas as pd
from pathlib import Path
from datetime import datetime
from src.monitoring.drift_detector import DriftDetector


class DriftMonitor:
    def __init__(self, reference_data_path: Path = None):
        """Initialize drift monitor with reference data."""
        if reference_data_path is None:
            reference_data_path = Path('artifacts/data_transformation/processed/train_processed.parquet')
        
        self.detector = DriftDetector(reference_data_path)
        self.reports_dir = Path('reports/drift')
        self.reports_dir.mkdir(parents=True, exist_ok=True)
    
    def fetch_recent_data(self, data_path: Path = None) -> pd.DataFrame:
        """
        Fetch recent production data for drift detection.
        
        Args:
            data_path: Path to recent data (for testing, use test data)
            
        Returns:
            DataFrame with sensor data
        """
        # For now, use test data as a placeholder
        # In production, this would query from database or S3
        if data_path is None:
            data_path = Path('artifacts/data_transformation/processed/test_processed.parquet')
        
        df = pd.read_parquet(data_path)
        return df
    
    def run_drift_check(self, current_data: pd.DataFrame = None):
        """Run drift detection and log results."""
        print(f"[{datetime.now()}] Running drift check...")
        
        # Fetch recent data if not provided
        if current_data is None:
            current_data = self.fetch_recent_data()
        
        if len(current_data) < 100:
            print("Not enough data for drift detection")
            return
        
        # Check drift
        result = self.detector.check_drift(current_data)
        
        # Log results
        print(f"Drift Share: {result['drift_share']:.2%}")
        print(f"Alert Level: {result['alert_level']}")
        
        if result['drifted_features']:
            print(f"Drifted Features: {', '.join(result['drifted_features'])}")
        
        # Save report if drift detected
        if result['drift_detected']:
            output_path = self.reports_dir / f"drift_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            self.detector.save_report(current_data, output_path)
            print(f"Report saved: {output_path}")
        
        return result
    
    def start_scheduled_monitoring(self, interval_hours: int = 1):
        """Start scheduled drift monitoring."""
        schedule.every(interval_hours).hours.do(self.run_drift_check)
        
        print(f"Drift monitor started. Running every {interval_hours} hour(s)...")
        
        while True:
            schedule.run_pending()
            time.sleep(60)


if __name__ == '__main__':
    monitor = DriftMonitor()
    
    # Run once for testing
    print("Running one-time drift check...")
    result = monitor.run_drift_check()
    print(f"\nDrift check completed: {result}")

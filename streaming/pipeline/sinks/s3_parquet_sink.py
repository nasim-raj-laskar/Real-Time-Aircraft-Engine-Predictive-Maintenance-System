import io
import os
import uuid
from datetime import datetime, timezone
from typing import List

import boto3
import pyarrow as pa
import pyarrow.parquet as pq

from streaming.model.feature_vector import FeatureVector

_SCHEMA = pa.schema([
    pa.field("engine_id",   pa.string()),
    pa.field("cycle",       pa.int32()),
    pa.field("event_time",  pa.int64()),
    pa.field("features",    pa.list_(pa.float32())),
    pa.field("window_size", pa.int32()),
    pa.field("n_sensors",   pa.int32()),
    pa.field("date",        pa.string()),
    pa.field("hour",        pa.string()),
])


class S3ParquetSink:
    """
    Buffers FeatureVectors and flushes to S3 as Snappy-compressed Parquet.

    Output layout (Hive-partitioned):
        s3://{bucket}/{prefix}/date=YYYY-MM-DD/hour=HH/part-{n}.parquet
    """

    def __init__(
        self,
        bucket: str = None,
        prefix: str = "features",
        endpoint: str = None,
        aws_key: str = None,
        aws_secret: str = None,
    ):
        self._bucket = bucket or os.getenv("AWS_S3_BUCKET") or os.getenv("S3_BUCKET", "aircraft-engine-data")
        self._prefix = prefix
        self._buffer: List[FeatureVector] = []
        self._part = 0
        self._run_id = uuid.uuid4().hex[:8]  # unique per process lifetime, prevents key collisions on restart

        self._s3 = boto3.client(
            "s3",
            endpoint_url=endpoint or os.getenv("MINIO_ENDPOINT"),
            aws_access_key_id=aws_key or os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=aws_secret or os.getenv("AWS_SECRET_ACCESS_KEY"),
        )

    def add(self, fv: FeatureVector) -> None:
        self._buffer.append(fv)

    def flush(self) -> int:
        if not self._buffer:
            return 0

        now = datetime.now(timezone.utc)
        date = now.strftime("%Y-%m-%d")
        hour = now.strftime("%H")

        rows = {
            "engine_id":   [fv.engine_id   for fv in self._buffer],
            "cycle":       [fv.cycle        for fv in self._buffer],
            "event_time":  [fv.event_time   for fv in self._buffer],
            "features":    [fv.features     for fv in self._buffer],
            "window_size": [fv.window_size  for fv in self._buffer],
            "n_sensors":   [fv.n_sensors    for fv in self._buffer],
            "date":        [date] * len(self._buffer),
            "hour":        [hour] * len(self._buffer),
        }

        buf = io.BytesIO()
        pq.write_table(pa.Table.from_pydict(rows, schema=_SCHEMA), buf, compression="snappy")
        buf.seek(0)

        key = f"{self._prefix}/date={date}/hour={hour}/part-{self._run_id}-{self._part}.parquet"
        self._s3.put_object(Bucket=self._bucket, Key=key, Body=buf.getvalue())

        n = len(self._buffer)
        self._buffer.clear()
        self._part += 1
        return n

    def close(self) -> None:
        self.flush()

import json
import logging
from pathlib import Path

import boto3

logger = logging.getLogger(__name__)

_s3_config_cache = None


def _get_s3_config():
    global _s3_config_cache
    if _s3_config_cache is not None:
        return _s3_config_cache

    from django.conf import settings
    config_path = Path(settings.BASE_DIR) / 'mercury' / 'env.json'
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        _s3_config_cache = config.get('S3', {}).get(settings.ENVIRONMENT)
    except Exception as e:
        logger.error(f"Failed to load S3 config: {e}")
        _s3_config_cache = None
    return _s3_config_cache


def get_s3_client():
    """Returns (boto3_client, bucket_name) or (None, None) if not configured."""
    cfg = _get_s3_config()
    if not cfg:
        return None, None
    client = boto3.client(
        's3',
        aws_access_key_id=cfg['aws_access_key_id'],
        aws_secret_access_key=cfg['aws_secret_access_key'],
        region_name=cfg.get('region', 'us-east-1'),
    )
    return client, cfg['bucket_name']


TESTDATA_PREFIX = 'qa/mercury/testdata/'
PERF_DATA_PREFIX = 'qa/mercury/perf_data/'


def upload_testdata(file_obj, s3_key, content_type=None):
    """Upload a file-like object to S3. Returns the full s3_key."""
    client, bucket = get_s3_client()
    if not client:
        raise RuntimeError("S3 not configured")
    extra = {}
    if content_type:
        extra['ContentType'] = content_type
    client.upload_fileobj(file_obj, bucket, s3_key, ExtraArgs=extra or None)
    logger.info(f"Uploaded testdata to s3://{bucket}/{s3_key}")
    return s3_key


def download_testdata(s3_key, local_path):
    """Download a file from S3 to a local path."""
    client, bucket = get_s3_client()
    if not client:
        raise RuntimeError("S3 not configured")
    client.download_file(bucket, s3_key, local_path)
    logger.info(f"Downloaded s3://{bucket}/{s3_key} -> {local_path}")


def delete_testdata(s3_key):
    """Delete a file from S3."""
    client, bucket = get_s3_client()
    if not client:
        raise RuntimeError("S3 not configured")
    client.delete_object(Bucket=bucket, Key=s3_key)
    logger.info(f"Deleted s3://{bucket}/{s3_key}")

"""
Prepare rehearsal S3/KMS resources for a production-like stack.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def _session() -> boto3.Session:
    return boto3.Session(
        aws_access_key_id=_env("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=_env("AWS_SECRET_ACCESS_KEY"),
        region_name=_env("AWS_REGION", "us-east-1"),
    )


def _s3_client():
    kwargs: dict[str, object] = {}
    endpoint_url = _env("AWS_S3_ENDPOINT_URL")
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    if _env("AWS_S3_FORCE_PATH_STYLE", "false").lower() == "true":
        kwargs["config"] = BotoConfig(s3={"addressing_style": "path"})
    return _session().client("s3", **kwargs)


def _kms_client():
    kwargs: dict[str, object] = {}
    endpoint_url = _env("AWS_KMS_ENDPOINT_URL") or _env("AWS_S3_ENDPOINT_URL")
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    return _session().client("kms", **kwargs)


def _ensure_kms_alias(kms, alias_name: str) -> dict[str, str]:
    try:
        response = kms.describe_key(KeyId=alias_name)
        metadata = response["KeyMetadata"]
        return {
            "alias": alias_name,
            "key_id": metadata["KeyId"],
            "arn": metadata["Arn"],
        }
    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        if error_code not in {"NotFoundException", "ValidationException"}:
            raise

    metadata = kms.create_key(Description="ArgentNorth production rehearsal key")["KeyMetadata"]
    try:
        kms.create_alias(AliasName=alias_name, TargetKeyId=metadata["KeyId"])
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "AlreadyExistsException":
            raise

    return {
        "alias": alias_name,
        "key_id": metadata["KeyId"],
        "arn": metadata["Arn"],
    }


def _ensure_bucket(s3, bucket_name: str, region: str) -> None:
    try:
        s3.head_bucket(Bucket=bucket_name)
    except ClientError:
        create_kwargs = {"Bucket": bucket_name}
        if region != "us-east-1":
            create_kwargs["CreateBucketConfiguration"] = {
                "LocationConstraint": region,
            }
        s3.create_bucket(**create_kwargs)


def _configure_bucket_encryption(s3, bucket_name: str, kms_key_id: str) -> None:
    s3.put_bucket_encryption(
        Bucket=bucket_name,
        ServerSideEncryptionConfiguration={
            "Rules": [
                {
                    "ApplyServerSideEncryptionByDefault": {
                        "SSEAlgorithm": "aws:kms",
                        "KMSMasterKeyID": kms_key_id,
                    },
                    "BucketKeyEnabled": True,
                }
            ]
        },
    )


def main() -> None:
    bucket_name = _env("S3_BUCKET_NAME", "loanlens-rehearsal")
    kms_alias = _env("AWS_KMS_KEY_ID", "alias/loanlens-rehearsal")
    region = _env("AWS_REGION", "us-east-1")

    s3 = _s3_client()
    kms = _kms_client()

    key_metadata = _ensure_kms_alias(kms, kms_alias)
    _ensure_bucket(s3, bucket_name, region)
    _configure_bucket_encryption(s3, bucket_name, kms_alias)

    print(
        json.dumps(
            {
                "bucket": bucket_name,
                "kms_alias": kms_alias,
                "kms_key_id": key_metadata["key_id"],
                "kms_arn": key_metadata["arn"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

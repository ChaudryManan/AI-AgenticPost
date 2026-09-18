"""
Artifact storage — local first, S3 optional.

The rest of the codebase only ever calls:
    uri = put_artifact(local_path)     # returns "file://..." or "s3://..."
    path = get_artifact(uri)           # back to a local Path
    url = public_url(uri)              # back to a URL (for IG etc.)

With no S3_BUCKET configured, put_artifact returns a file:// URI and
everything stays local.  Configure S3_BUCKET and objects get uploaded —
but a local copy is still kept so get_artifact() works offline.
"""
from __future__ import annotations

import logging
from pathlib import Path

from ..config.settings import get_settings

log = logging.getLogger("artifacts")


def put_artifact(local_path: Path) -> str:
    """
    Persist a local file.  Always keeps the local copy; uploads to S3 if
    configured.  Returns a URI:

        no bucket  →  file:///abs/path/to/file
        with bucket →  s3://bucket/run_id/filename

    The S3 key includes run_id when the path is under the artifact_root so
    runs don't collide on filename.
    """
    local_path = Path(local_path).resolve()
    if not local_path.exists():
        raise FileNotFoundError(f"artifact does not exist: {local_path}")

    s = get_settings()
    if not s.s3_bucket:
        return f"file://{local_path.as_posix()}"

    # S3 key: use run_id/filename when we can infer the run_id from the path
    try:
        rel = local_path.relative_to(s.artifact_root)
        # rel is like  <run_id>/scenes/scene_1.mp4  → keep as-is
        key = rel.as_posix()
    except ValueError:
        # not under artifact_root — just use the filename
        key = local_path.name

    try:
        import boto3  # type: ignore
        client = boto3.client("s3")
        client.upload_file(str(local_path), s.s3_bucket, key)
        log.info("uploaded %s -> s3://%s/%s", local_path, s.s3_bucket, key)
        return f"s3://{s.s3_bucket}/{key}"
    except Exception as e:  # noqa: BLE001
        log.warning("S3 upload failed (%s); keeping local file only", e)
        return f"file://{local_path.as_posix()}"


def get_artifact(uri: str) -> Path:
    """
    Resolve a URI back to a local Path.

    For s3:// URIs we download to a cache under artifact_root/_cache/ and
    return that path.  For file:// URIs we just return the path.
    """
    if not uri:
        raise ValueError("empty artifact uri")

    if uri.startswith("file://"):
        return Path(uri[7:])

    if uri.startswith("s3://"):
        s = get_settings()
        # s3://bucket/key
        without_scheme = uri[5:]
        _, _, key = without_scheme.partition("/")
        cache = s.artifact_root / "_cache" / key
        if cache.exists():
            return cache
        cache.parent.mkdir(parents=True, exist_ok=True)
        import boto3  # type: ignore
        boto3.client("s3").download_file(s.s3_bucket, key, str(cache))
        return cache

    # plain path
    p = Path(uri)
    if p.exists():
        return p
    raise FileNotFoundError(f"cannot resolve artifact uri: {uri!r}")


def public_url(uri: str) -> str:
    """
    Return a URL that platforms can fetch.

    file:// URIs can't be fetched by external services, so we return them
    unchanged and let the caller (e.g. InstagramPublisher) complain.  For
    s3:// we build a presigned GET url (valid 24h) if credentials work,
    otherwise return the s3 URI.
    """
    if uri.startswith("file://"):
        return uri
    if uri.startswith("s3://"):
        try:
            import boto3  # type: ignore
            s = get_settings()
            without_scheme = uri[5:]
            _, _, key = without_scheme.partition("/")
            client = boto3.client("s3")
            return client.generate_presigned_url(
                "get_object",
                Params={"Bucket": s.s3_bucket, "Key": key},
                ExpiresIn=86400,
            )
        except Exception:  # noqa: BLE001
            return uri
    return uri
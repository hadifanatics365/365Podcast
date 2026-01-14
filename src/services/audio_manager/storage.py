"""Audio file storage and retrieval."""

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError

from src.config import Settings, get_settings
from src.exceptions import StorageError

logger = logging.getLogger(__name__)


class AudioStorage:
    """
    Handles audio file storage and URL generation.

    Supports:
    - AWS S3 storage with presigned URLs
    - Local filesystem storage for development
    - CDN URL generation
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.storage_type = self.settings.storage_type
        self.bucket_name = self.settings.s3_bucket_name
        self.cdn_base_url = self.settings.cdn_base_url
        self.local_path = Path(self.settings.local_storage_path)

        # Initialize S3 client if using S3
        if self.storage_type == "s3" and self.bucket_name:
            self.s3_client = boto3.client(
                "s3",
                region_name=self.settings.s3_region,
            )
        else:
            self.s3_client = None

    async def store_audio(
        self,
        audio_bytes: bytes,
        job_id: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """
        Store audio file and return public URL.

        Args:
            audio_bytes: MP3 audio data
            job_id: Unique job identifier
            metadata: Optional metadata (game_ids, mode, etc.)

        Returns:
            Public URL to the audio file

        Raises:
            StorageError: If storage operation fails
        """
        metadata = metadata or {}
        filename = self._generate_filename(job_id, metadata)

        logger.info(f"Storing audio: {len(audio_bytes)} bytes as {filename}")

        try:
            if self.storage_type == "s3" and self.s3_client:
                return await self._store_s3(audio_bytes, filename, metadata)
            else:
                return await self._store_local(audio_bytes, filename)
        except Exception as e:
            logger.error(f"Storage error: {e}")
            raise StorageError(
                message=f"Failed to store audio: {str(e)}",
                storage_type=self.storage_type,
                file_path=filename,
                cause=e,
            )

    async def _store_s3(
        self,
        audio_bytes: bytes,
        filename: str,
        metadata: dict[str, Any],
    ) -> str:
        """Upload to S3 and return URL."""
        try:
            # Prepare S3 metadata (must be strings)
            s3_metadata = {
                "game_ids": ",".join(str(gid) for gid in metadata.get("game_ids", [])),
                "mode": str(metadata.get("mode", "")),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=filename,
                Body=audio_bytes,
                ContentType="audio/mpeg",
                Metadata=s3_metadata,
            )

            # Generate URL
            if self.cdn_base_url:
                return f"{self.cdn_base_url.rstrip('/')}/{filename}"

            return f"https://{self.bucket_name}.s3.amazonaws.com/{filename}"

        except ClientError as e:
            raise StorageError(
                message=f"S3 upload failed: {e.response['Error']['Message']}",
                storage_type="s3",
                file_path=filename,
                cause=e,
            )

    async def _store_local(
        self,
        audio_bytes: bytes,
        filename: str,
    ) -> str:
        """Store locally and return file URL."""
        file_path = self.local_path / filename

        # Create parent directories
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        file_path.write_bytes(audio_bytes)

        logger.info(f"Stored audio locally: {file_path}")
        return f"file://{file_path.absolute()}"

    def _generate_filename(
        self,
        job_id: str,
        metadata: dict[str, Any],
    ) -> str:
        """
        Generate unique filename with date organization.

        Format: YYYY/MM/DD/{job_id}_{game_hash}.mp3
        """
        # Date prefix for organization
        now = datetime.now(timezone.utc)
        date_prefix = now.strftime("%Y/%m/%d")

        # Hash game IDs for uniqueness
        game_ids = metadata.get("game_ids", [])
        if game_ids:
            game_str = "_".join(str(gid) for gid in sorted(game_ids))
            game_hash = hashlib.md5(game_str.encode()).hexdigest()[:8]
        else:
            game_hash = hashlib.md5(job_id.encode()).hexdigest()[:8]

        return f"{date_prefix}/{job_id}_{game_hash}.mp3"

    def generate_presigned_url(
        self,
        key: str,
        expiration: int = 3600,
    ) -> str:
        """
        Generate time-limited presigned URL for S3 object.

        Args:
            key: S3 object key
            expiration: URL expiration in seconds

        Returns:
            Presigned URL

        Raises:
            StorageError: If URL generation fails
        """
        if not self.s3_client:
            raise StorageError(
                message="S3 client not configured",
                storage_type=self.storage_type,
            )

        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": key,
                },
                ExpiresIn=expiration,
            )
            return url
        except ClientError as e:
            raise StorageError(
                message=f"Failed to generate presigned URL: {e}",
                storage_type="s3",
                file_path=key,
                cause=e,
            )

    async def get_audio_info(self, key: str) -> Optional[dict[str, Any]]:
        """
        Get metadata for stored audio file.

        Args:
            key: S3 key or local file path

        Returns:
            Metadata dictionary or None if not found
        """
        if self.storage_type == "s3" and self.s3_client:
            try:
                response = self.s3_client.head_object(
                    Bucket=self.bucket_name,
                    Key=key,
                )
                return {
                    "size_bytes": response["ContentLength"],
                    "content_type": response["ContentType"],
                    "last_modified": response["LastModified"].isoformat(),
                    "metadata": response.get("Metadata", {}),
                }
            except ClientError:
                return None
        else:
            # Local file
            file_path = self.local_path / key
            if file_path.exists():
                stat = file_path.stat()
                return {
                    "size_bytes": stat.st_size,
                    "content_type": "audio/mpeg",
                    "last_modified": datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat(),
                }
            return None

    async def delete_audio(self, key: str) -> bool:
        """
        Delete stored audio file.

        Args:
            key: S3 key or local file path

        Returns:
            True if deleted, False if not found
        """
        if self.storage_type == "s3" and self.s3_client:
            try:
                self.s3_client.delete_object(
                    Bucket=self.bucket_name,
                    Key=key,
                )
                return True
            except ClientError:
                return False
        else:
            file_path = self.local_path / key
            if file_path.exists():
                file_path.unlink()
                return True
            return False

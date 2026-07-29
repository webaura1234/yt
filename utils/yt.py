import os
import shlex
from pathlib import Path

from config import NO_UPLOAD


def auto_upload(
    video: Path,
    title: str,
    description: str,
    privacy: str = "public",
    category: str = "24",
) -> None:
    if NO_UPLOAD:
        return

    os.system(
        f"/venv/bin/python3 upload_video.py --file={shlex.quote(str(video))} --title={shlex.quote(title)} --description={shlex.quote(description)} --privacyStatus={shlex.quote(privacy)} --category={shlex.quote(category)}"
    )

from io import BytesIO
from pathlib import Path
import uuid

from django.core.files.base import ContentFile

try:
    from PIL import Image, ImageOps
except ImportError:  # pragma: no cover - Pillow is declared in requirements but may be missing locally.
    Image = None
    ImageOps = None


def convert_upload_to_webp(uploaded_file, *, stem=None, quality=82):
    if not uploaded_file or Image is None:
        return uploaded_file

    original_name = getattr(uploaded_file, "name", "upload")
    content_type = getattr(uploaded_file, "content_type", "") or ""
    lowered_name = original_name.lower()

    if lowered_name.endswith(".svg") or content_type == "image/svg+xml":
        return uploaded_file

    try:
        uploaded_file.seek(0)
        with Image.open(uploaded_file) as source_image:
            source_image = ImageOps.exif_transpose(source_image)

            if getattr(source_image, "is_animated", False):
                return uploaded_file

            converted_image = source_image.convert("RGBA" if "A" in source_image.getbands() else "RGB")
            output = BytesIO()
            converted_image.save(output, format="WEBP", quality=quality, method=6)
    except Exception:
        return uploaded_file

    filename_stem = stem or Path(original_name).stem or "image"
    filename = f"{filename_stem}-{uuid.uuid4().hex[:10]}.webp"
    return ContentFile(output.getvalue(), name=filename)

from io import BytesIO
from pathlib import Path
import uuid

from django.core.files.base import ContentFile

try:
    from PIL import Image, ImageOps, ImageSequence
except ImportError:  # pragma: no cover - Pillow is declared in requirements but may be missing locally.
    Image = None
    ImageOps = None
    ImageSequence = None


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
            output = BytesIO()
            is_animated = bool(getattr(source_image, "is_animated", False))

            if is_animated and ImageSequence is not None:
                frames = []
                durations = []

                for frame in ImageSequence.Iterator(source_image):
                    normalized_frame = ImageOps.exif_transpose(frame)
                    converted_frame = normalized_frame.convert(
                        "RGBA" if "A" in normalized_frame.getbands() else "RGB"
                    )
                    frames.append(converted_frame)
                    durations.append(frame.info.get("duration", source_image.info.get("duration", 100)))

                if len(frames) > 1:
                    frames[0].save(
                        output,
                        format="WEBP",
                        save_all=True,
                        append_images=frames[1:],
                        duration=durations,
                        loop=source_image.info.get("loop", 0),
                        quality=quality,
                        method=6,
                    )
                else:
                    frames[0].save(output, format="WEBP", quality=quality, method=6)
            else:
                source_image = ImageOps.exif_transpose(source_image)
                converted_image = source_image.convert("RGBA" if "A" in source_image.getbands() else "RGB")
                converted_image.save(output, format="WEBP", quality=quality, method=6)
    except Exception:
        return uploaded_file

    filename_stem = stem or Path(original_name).stem or "image"
    filename = f"{filename_stem}-{uuid.uuid4().hex[:10]}.webp"
    return ContentFile(output.getvalue(), name=filename)

from django.core.management.base import BaseCommand

from cios.models import CIO
from discussions.models import Comment, Post
from image_utils import convert_upload_to_webp
from users.models import Profile


class Command(BaseCommand):
    help = "Backfill existing uploaded images to WebP across profiles, CIOs, posts, and comments."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be converted without writing any changes.",
        )
        parser.add_argument(
            "--keep-originals",
            action="store_true",
            help="Keep the original uploaded files after saving the new .webp version.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        keep_originals = options["keep_originals"]

        targets = [
            {
                "label": "profile image",
                "queryset": Profile.objects.exclude(image="").exclude(image__isnull=True),
                "field": "image",
                "stem": "profile",
                "skip_names": {"profile_pics/default.jpg"},
            },
            {
                "label": "cio icon",
                "queryset": CIO.objects.exclude(icon="").exclude(icon__isnull=True),
                "field": "icon",
                "stem": "cio-icon",
                "skip_names": set(),
            },
            {
                "label": "cio banner",
                "queryset": CIO.objects.exclude(banner_image="").exclude(banner_image__isnull=True),
                "field": "banner_image",
                "stem": "cio-banner",
                "skip_names": set(),
            },
            {
                "label": "post image",
                "queryset": Post.objects.exclude(image="").exclude(image__isnull=True),
                "field": "image",
                "stem": "post-image",
                "skip_names": set(),
            },
            {
                "label": "comment image",
                "queryset": Comment.objects.exclude(image="").exclude(image__isnull=True),
                "field": "image",
                "stem": "comment-image",
                "skip_names": set(),
            },
        ]

        summary = {
            "checked": 0,
            "converted": 0,
            "skipped": 0,
            "failed": 0,
        }

        for target in targets:
            self.stdout.write(self.style.NOTICE(f"Scanning {target['label']}s..."))
            target_stats = self._process_target(
                queryset=target["queryset"],
                field_name=target["field"],
                stem=target["stem"],
                label=target["label"],
                skip_names=target["skip_names"],
                dry_run=dry_run,
                keep_originals=keep_originals,
            )
            for key in summary:
                summary[key] += target_stats[key]

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Backfill complete."))
        self.stdout.write(f"Checked: {summary['checked']}")
        self.stdout.write(f"Converted: {summary['converted']}")
        self.stdout.write(f"Skipped: {summary['skipped']}")
        self.stdout.write(f"Failed: {summary['failed']}")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run only: no files or database rows were changed."))

    def _process_target(self, *, queryset, field_name, stem, label, skip_names, dry_run, keep_originals):
        stats = {
            "checked": 0,
            "converted": 0,
            "skipped": 0,
            "failed": 0,
        }

        for instance in queryset.iterator():
            stats["checked"] += 1
            file_field = getattr(instance, field_name)

            if not file_field or not file_field.name:
                stats["skipped"] += 1
                continue

            lowered_name = file_field.name.lower()
            if lowered_name in skip_names or lowered_name.endswith(".webp") or lowered_name.endswith(".svg"):
                stats["skipped"] += 1
                continue

            old_name = file_field.name

            try:
                with file_field.open("rb") as existing_file:
                    converted = convert_upload_to_webp(existing_file, stem=stem)
            except Exception as exc:
                stats["failed"] += 1
                self.stderr.write(
                    self.style.ERROR(
                        f"Failed to read {label} for {self._instance_label(instance)} ({old_name}): {exc}"
                    )
                )
                continue

            if converted is None or converted is existing_file or getattr(converted, "name", "").lower().endswith(".svg"):
                stats["skipped"] += 1
                continue

            if dry_run:
                stats["converted"] += 1
                self.stdout.write(f"[dry-run] Would convert {label} for {self._instance_label(instance)}: {old_name}")
                continue

            try:
                file_field.save(converted.name, converted, save=False)
                instance.save(update_fields=[field_name])

                if not keep_originals:
                    storage = file_field.storage
                    if old_name != file_field.name and storage.exists(old_name):
                        storage.delete(old_name)
            except Exception as exc:
                stats["failed"] += 1
                self.stderr.write(
                    self.style.ERROR(
                        f"Failed to convert {label} for {self._instance_label(instance)} ({old_name}): {exc}"
                    )
                )
                continue

            stats["converted"] += 1
            self.stdout.write(f"Converted {label} for {self._instance_label(instance)}: {old_name} -> {file_field.name}")

        return stats

    @staticmethod
    def _instance_label(instance):
        return f"{instance.__class__.__name__}#{instance.pk}"

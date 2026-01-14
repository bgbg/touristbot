#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Upload tourism/museum content to Gemini File Search Store

Parses area/site directory structure, chunks files, and uploads to store.
Tracks uploaded files to support incremental updates.

Usage:
    # Upload all content from content_root (from config.yaml)
    python gemini/main_upload.py

    # Upload specific area
    python gemini/main_upload.py --area "Old City"

    # Upload specific site
    python gemini/main_upload.py --area "Old City" --site "Western Wall"

    # Force re-upload (ignore tracking)
    python gemini/main_upload.py --force
"""

import argparse
import locale
import os
import sys

# Add parent directory to path if running as script
if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(script_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    # Change to parent directory so relative paths in config work
    os.chdir(parent_dir)

# Set UTF-8 encoding for the environment
if sys.stdout.encoding != "UTF-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding != "UTF-8":
    sys.stderr.reconfigure(encoding="utf-8")

# Set locale to support UTF-8
try:
    locale.setlocale(locale.LC_ALL, "")
except:
    pass

import google.genai as genai

from gemini.config import GeminiConfig
from gemini.directory_parser import DirectoryParser
from gemini.file_api_manager import FileAPIManager
from gemini.file_search_store import FileSearchStoreManager
from gemini.image_extractor import extract_images_from_docx
from gemini.image_registry import ImageRegistry
from gemini.image_storage import ImageStorage
from gemini.store_registry import StoreRegistry
from gemini.upload_tracker import UploadTracker


def process_docx_images(
    file_path: str,
    area: str,
    site: str,
    doc: str,
    file_api_manager: FileAPIManager,
    image_storage: ImageStorage,
    image_registry: ImageRegistry,
) -> int:
    """
    Extract and upload images from a DOCX file

    Args:
        file_path: Path to DOCX file
        area: Area identifier
        site: Site identifier
        doc: Document identifier
        file_api_manager: File API manager instance
        image_storage: Image storage instance
        image_registry: Image registry instance

    Returns:
        Number of images processed
    """
    import shutil
    import tempfile

    try:
        # Check if file is DOCX
        if not file_path.lower().endswith('.docx'):
            return 0

        # Handle Hebrew filenames by copying to temp file
        temp_file_path = None
        docx_path = file_path

        try:
            # Check if filename contains non-ASCII characters
            try:
                os.path.basename(file_path).encode('ascii')
            except UnicodeEncodeError:
                # Copy to temp file with ASCII name
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix='.docx', prefix='upload_'
                ) as temp_file:
                    temp_file_path = temp_file.name
                shutil.copy2(file_path, temp_file_path)
                docx_path = temp_file_path

            # Extract images
            images = extract_images_from_docx(docx_path)

            if not images:
                return 0

            print(f"      -> Found {len(images)} image(s) in DOCX")

            # Upload images to GCS
            uploaded_gcs = image_storage.upload_images_from_extraction(
                images=images,
                area=area,
                site=site,
                doc=doc,
                make_public=False,
            )

            print(f"      -> Uploaded {len(uploaded_gcs)} image(s) to GCS")

            # Upload images to File API
            uploaded_file_api = file_api_manager.upload_images_from_extraction(
                images=images,
                area=area,
                site=site,
                doc=doc,
            )

            print(f"      -> Uploaded {len(uploaded_file_api)} image(s) to File API")

            # Validate all uploads succeeded before registering
            if len(uploaded_gcs) != len(images):
                # Rollback GCS uploads
                print(f"      ⚠️  GCS upload incomplete ({len(uploaded_gcs)}/{len(images)}), rolling back...")
                for gcs_path, _ in uploaded_gcs:
                    try:
                        image_storage.delete_image(gcs_path)
                    except Exception as e:
                        print(f"      Warning: Could not delete {gcs_path}: {e}")
                raise Exception(f"GCS upload incomplete: {len(uploaded_gcs)}/{len(images)}")

            if len(uploaded_file_api) != len(images):
                # Rollback all uploads
                print(f"      ⚠️  File API upload incomplete ({len(uploaded_file_api)}/{len(images)}), rolling back...")
                for gcs_path, _ in uploaded_gcs:
                    try:
                        image_storage.delete_image(gcs_path)
                    except Exception as e:
                        print(f"      Warning: Could not delete {gcs_path}: {e}")
                for _, _, file_name, _ in uploaded_file_api:
                    try:
                        file_api_manager.delete_file(file_name)
                    except Exception as e:
                        print(f"      Warning: Could not delete {file_name}: {e}")
                raise Exception(f"File API upload incomplete: {len(uploaded_file_api)}/{len(images)}")

            # Only register if ALL uploads succeeded
            for i, image in enumerate(images, 1):
                gcs_path, gcs_url = uploaded_gcs[i - 1]
                image_index, file_uri, file_name, caption = uploaded_file_api[i - 1]

                image_registry.add_image(
                    area=area,
                    site=site,
                    doc=doc,
                    image_index=image_index,
                    caption=caption,
                    context_before=image.context_before,
                    context_after=image.context_after,
                    gcs_path=gcs_path,
                    file_api_uri=file_uri,
                    file_api_name=file_name,
                    image_format=image.image_format,
                )

            print(f"      -> Registered {len(images)} image(s) in registry")

            return len(images)

        finally:
            # Clean up temp file - guaranteed to run even on exception
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except Exception as e:
                    print(f"      Warning: Could not remove temp file {temp_file_path}: {e}")

    except Exception as e:
        print(f"      ⚠️  Warning: Could not process images: {e}")
        return 0


def main():
    print("DEBUG: Starting main_upload.py")
    parser = argparse.ArgumentParser(
        description="Upload tourism/museum content to Gemini RAG system"
    )

    print("DEBUG: Created argument parser")
    parser.add_argument("--area", help="Specific area to upload (optional)")
    parser.add_argument("--site", help="Specific site to upload (requires --area)")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-upload all files (ignore tracking)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what will be uploaded without actually uploading",
    )

    print("DEBUG: Parsing arguments")
    args = parser.parse_args()
    print(f"DEBUG: Arguments parsed: dry_run={args.dry_run}")

    # Validate arguments
    if args.site and not args.area:
        print("Error: --site requires --area to be specified")
        sys.exit(1)

    # Load configuration
    print("=" * 70)
    print("📤 Tourism Guide - Content Upload System")
    print("=" * 70)

    print("DEBUG: Loading configuration")
    try:
        config = GeminiConfig.from_yaml()
        print(f"DEBUG: Config loaded successfully")
        print(f"\n✓ Configuration loaded")
        print(f"  Content root: {config.content_root}")
        print(f"  File Search Store: {config.file_search_store_name}")
    except FileNotFoundError as e:
        print(f"\n❌ Configuration error: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"\n❌ {e}")
        sys.exit(1)

    # Parse directory structure
    print(
        "\n[Step 1/4] Parsing directory structure...",
    )

    parser_obj = DirectoryParser(config.content_root, config.supported_formats)

    try:
        structure = parser_obj.parse_directory_structure()

        # Filter by area/site if specified
        if args.area:
            structure = {
                (area, site): files
                for (area, site), files in structure.items()
                if area.lower() == args.area.lower()
                and (not args.site or site.lower() == args.site.lower())
            }

            if not structure:
                print(
                    f"\n❌ No content found for area='{args.area}'"
                    + (f", site='{args.site}'" if args.site else "")
                )
                sys.exit(1)

        total_files = sum(len(files) for files in structure.values())
        print(
            f"✓ Found {len(structure)} area/site combinations with {total_files} files"
        )

    except FileNotFoundError as e:
        print(f"\n❌ {e}")
        sys.exit(1)

    # Dry run mode
    if args.dry_run:
        print("\n🔍 DRY RUN MODE - No files will be uploaded")
        print("=" * 70)

    # Initialize tracking
    print(f"\n[Step {'2/4' if not args.dry_run else '2/3'}] Checking upload history...")

    tracker = UploadTracker(config.upload_tracking_path)

    # Connect to Gemini (skip in dry-run mode)
    if not args.dry_run:
        print("\n[Step 3/4] Connecting to Gemini and initializing File Search Store...")

        try:
            client = genai.Client(api_key=config.api_key)
            registry = StoreRegistry(config.registry_path)
            print("✓ Connected to Gemini API")

            # Initialize File Search Store Manager
            fs_manager = FileSearchStoreManager(client)

            # Get or create the global File Search Store
            store_name = fs_manager.get_or_create_store(config.file_search_store_name)

            # Save store name to registry if not already saved
            if registry.get_file_search_store_name() != store_name:
                registry.set_file_search_store_name(store_name)

            # Initialize image managers
            try:
                file_api_manager = FileAPIManager(client)
                image_storage = ImageStorage(
                    bucket_name=config.gcs_bucket_name,
                    credentials_json=config.gcs_credentials_json,
                )
                image_registry = ImageRegistry(config.image_registry_path)
                print("✓ Initialized image upload system")
            except Exception as e:
                print(f"⚠️  Warning: Could not initialize image system: {e}")
                print("   Image upload will be skipped")
                file_api_manager = None
                image_storage = None
                image_registry = None

        except Exception as e:
            print(f"❌ Error connecting to Gemini: {e}")
            sys.exit(1)
    else:
        client = None
        registry = StoreRegistry(config.registry_path)
        fs_manager = None
        store_name = registry.get_file_search_store_name() or "dry_run_store"
        file_api_manager = None
        image_storage = None
        image_registry = None

    # Process each area/site
    step_num = "3/3" if args.dry_run else "4/4"
    print(
        f"\n[Step {step_num}] {'Previewing' if args.dry_run else 'Processing and uploading'} content..."
    )

    force_upload = args.force or config.force_reupload
    total_uploaded = 0

    for (area, site), files in structure.items():
        print(f"\n-> Processing: {area} / {site}")
        print(f"   Found {len(files)} files")

        # Filter out already uploaded files
        files_to_upload = tracker.get_new_files(files, area, site, force=force_upload)

        if not files_to_upload:
            print(f"   ✓ All files already uploaded (use --force to re-upload)")
            continue

        print(f"   -> {len(files_to_upload)} files need upload")

        # Show files that will be uploaded
        if args.dry_run:
            print(f"   📋 Files to upload:")
            for file_path in files_to_upload:
                print(f"      - {os.path.relpath(file_path, config.content_root)}")
            print(
                f"   -> Would upload {len(files_to_upload)} files to File Search Store"
            )
            print(f"   -> Server-side chunking: {config.chunk_tokens} tokens/chunk")
            print(f"   ✓ Preview complete for {area}/{site}")
            total_uploaded += len(files_to_upload)
        else:
            try:
                print(f"   -> Uploading to File Search Store...")
                print(
                    f"      Server-side chunking: {config.chunk_tokens} tokens/chunk with {int(config.chunk_overlap_percent * 100)}% overlap"
                )

                # Upload each file to File Search Store with metadata
                total_images_uploaded = 0
                for file_path in files_to_upload:
                    # Generate document identifier from filename
                    doc_name = os.path.splitext(os.path.basename(file_path))[0]

                    # Upload to File Search Store with metadata
                    fs_manager.upload_to_file_search_store(
                        file_search_store_name=store_name,
                        file_path=file_path,
                        area=area,
                        site=site,
                        doc=doc_name,
                        max_tokens_per_chunk=config.chunk_tokens,
                        max_overlap_tokens=int(
                            config.chunk_tokens * config.chunk_overlap_percent
                        ),
                    )

                    # Process images if this is a DOCX file and image system is available
                    if (
                        file_api_manager
                        and image_storage
                        and image_registry
                        and file_path.lower().endswith('.docx')
                    ):
                        num_images = process_docx_images(
                            file_path=file_path,
                            area=area,
                            site=site,
                            doc=doc_name,
                            file_api_manager=file_api_manager,
                            image_storage=image_storage,
                            image_registry=image_registry,
                        )
                        total_images_uploaded += num_images

                # Register the location
                registry.register_store(
                    area=area,
                    site=site,
                    metadata={
                        "file_count": len(files_to_upload),
                    },
                )

                # Mark files as uploaded
                for file_path in files_to_upload:
                    tracker.mark_file_uploaded(file_path, area, site)

                total_uploaded += len(files_to_upload)

                # Report image uploads
                if total_images_uploaded > 0:
                    print(f"   ✓ Upload complete for {area}/{site} ({total_images_uploaded} images)")
                else:
                    print(f"   ✓ Upload complete for {area}/{site}")

            except Exception as e:
                print(f"   ❌ Error uploading {area}/{site}: {e}")
                import traceback

                traceback.print_exc()
                continue

    # Summary
    print("\n" + "=" * 70)
    if args.dry_run:
        print("🔍 DRY RUN SUMMARY")
        print("=" * 70)
        print(f"Would upload: {total_uploaded} files")
        print(f"File Search Store: {store_name}")
        print(f"Server-side chunking: {config.chunk_tokens} tokens/chunk")
        print(f"Areas/Sites: {len(structure)}")
        print("=" * 70)
        print("\n💡 To actually upload, run without --dry-run flag")
    else:
        print("✅ Upload Process Complete!")
        print("=" * 70)
        print(f"Total files uploaded: {total_uploaded}")
        print(f"File Search Store: {store_name}")
        print(f"Areas/Sites processed: {len(structure)}")
        print("=" * 70)

        if total_uploaded == 0:
            print(
                "\nℹ️  No new files were uploaded. Use --force to re-upload existing files."
            )


if __name__ == "__main__":
    main()

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

from gemini.chunker import chunk_file_tokens, chunk_text_file
from gemini.config import GeminiConfig
from gemini.directory_parser import DirectoryParser
from gemini.store_manager import StoreManager
from gemini.store_registry import StoreRegistry
from gemini.upload_tracker import UploadTracker


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
        "--no-chunk", action="store_true", help="Upload files directly without chunking"
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
        print(f"  Chunks directory: {config.chunks_dir}")
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
        print("\n[Step 3/4] Connecting to Gemini...")

        try:
            client = genai.Client(api_key=config.api_key)
            registry = StoreRegistry(config.registry_path)
            print("✓ Connected to Gemini API")

        except Exception as e:
            print(f"❌ Error connecting to Gemini: {e}")
            sys.exit(1)
    else:
        client = None
        registry = StoreRegistry(config.registry_path)

    # Process each area/site
    step_num = "3/3" if args.dry_run else "4/4"
    print(
        f"\n[Step {step_num}] {'Previewing' if args.dry_run else 'Processing and uploading'} content..."
    )

    force_upload = args.force or config.force_reupload
    total_uploaded = 0
    total_chunks = 0

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

        # Process files (chunk if needed)
        if args.no_chunk:
            chunk_files = files_to_upload
            if args.dry_run:
                print(
                    f"   -> Would upload {len(chunk_files)} files directly (no chunking)"
                )
        else:
            # Determine chunking method
            if config.use_token_chunking:
                chunk_info = f"{config.chunk_tokens} tokens with {int(config.chunk_overlap_percent * 100)}% overlap"
            else:
                chunk_info = f"{config.chunk_size} characters"

            if args.dry_run:
                print(f"   -> Would chunk files into {chunk_info}")
            else:
                print(f"   -> Chunking files ({chunk_info})...")

            chunk_files = []

            for file_path in files_to_upload:
                # Create chunks directory for this area/site
                area_site_chunks_dir = os.path.join(config.chunks_dir, area, site)

                # Generate unique ID for this file
                file_id = os.path.splitext(os.path.basename(file_path))[0]

                if not args.dry_run:
                    # Use token-based or character-based chunking
                    if config.use_token_chunking:
                        chunks = chunk_file_tokens(
                            file_path,
                            file_id,
                            chunk_tokens=config.chunk_tokens,
                            overlap_percent=config.chunk_overlap_percent,
                            output_dir=area_site_chunks_dir,
                        )
                    else:
                        chunks = chunk_text_file(
                            file_path,
                            file_id,
                            chunk_size=config.chunk_size,
                            output_dir=area_site_chunks_dir,
                        )
                    chunk_files.extend(chunks)
                else:
                    # Estimate number of chunks for dry run
                    try:
                        from file_parser import parse_file

                        content = parse_file(file_path)
                        if config.use_token_chunking:
                            # Estimate: ~4 chars per token
                            est_tokens = len(content) // 4
                            est_chunks = max(1, est_tokens // config.chunk_tokens)
                        else:
                            est_chunks = max(1, len(content) // config.chunk_size)
                        chunk_files.extend([f"chunk_{i}" for i in range(est_chunks)])
                    except:
                        chunk_files.append("chunk_1")

            if args.dry_run:
                print(f"   -> Would create approximately {len(chunk_files)} chunks")
            else:
                print(f"   -> Created {len(chunk_files)} chunks")

        total_chunks += len(chunk_files)

        # Upload to store (skip in dry-run)
        if args.dry_run:
            store_id = registry.get_store(area, site)
            if store_id:
                print(f"   -> Would upload to existing store: {store_id}")
            else:
                print(f"   -> Would create new store: {area}_{site}_Tourism_RAG")
            print(f"   ✓ Preview complete for {area}/{site}")
            total_uploaded += len(files_to_upload)
        else:
            try:
                # Get or create store for this area/site
                store_id = registry.get_store(area, site)

                store_manager = StoreManager(
                    client,
                    f"{area}_{site}_Tourism_RAG",
                    store_id=store_id,
                    area=area,
                    site=site,
                )

                print(f"   -> Uploading to Gemini store...")
                store_manager.upload_files(
                    chunk_files, max_wait_seconds=config.max_upload_wait_seconds
                )

                # Register the store
                store_name = store_manager.store_name
                registry.register_store(
                    area=area,
                    site=site,
                    store_name=store_name,
                    metadata={
                        "file_count": len(files_to_upload),
                        "chunk_count": len(chunk_files),
                    },
                )

                # Mark files as uploaded
                for file_path in files_to_upload:
                    tracker.mark_file_uploaded(file_path, area, site)

                total_uploaded += len(files_to_upload)
                print(f"   ✓ Upload complete for {area}/{site}")

            except Exception as e:
                print(f"   ❌ Error uploading {area}/{site}: {e}")
                continue

    # Summary
    print("\n" + "=" * 70)
    if args.dry_run:
        print("🔍 DRY RUN SUMMARY")
        print("=" * 70)
        print(f"Would upload: {total_uploaded} files")
        print(f"Would create: {total_chunks} chunks")
        print(f"Areas/Sites: {len(structure)}")
        print("=" * 70)
        print("\n💡 To actually upload, run without --dry-run flag")
    else:
        print("✅ Upload Process Complete!")
        print("=" * 70)
        print(f"Total files uploaded: {total_uploaded}")
        print(f"Total chunks created: {total_chunks}")
        print(f"Areas/Sites processed: {len(structure)}")
        print("=" * 70)

        if total_uploaded == 0:
            print(
                "\nℹ️  No new files were uploaded. Use --force to re-upload existing files."
            )


if __name__ == "__main__":
    main()

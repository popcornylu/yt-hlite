#!/usr/bin/env python3
"""
Table Tennis Video Highlight Generator

A human-in-the-loop system for generating highlight reels from table tennis videos.
"""

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Table Tennis Video Highlight Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start the web UI without a video (upload via browser)
  python main.py

  # Start the web UI with a specific video
  python main.py --video path/to/match.mp4

  # Run on a different port
  python main.py --port 8080

  # CLI-only analysis (no web UI)
  python main.py --video path/to/match.mp4 --cli
        """
    )

    parser.add_argument(
        "--video", "-v",
        type=str,
        help="Path to the input video file"
    )

    parser.add_argument(
        "--port", "-p",
        type=int,
        default=5000,
        help="Port for the web server (default: 5000)"
    )

    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host for the web server (default: 127.0.0.1)"
    )

    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run in CLI mode without web UI"
    )

    parser.add_argument(
        "--output", "-o",
        type=str,
        default="data/output",
        help="Output directory for generated files"
    )

    parser.add_argument(
        "--top-n",
        type=int,
        default=15,
        help="Number of top rallies to include in highlights (CLI mode)"
    )

    parser.add_argument(
        "--target-duration",
        type=int,
        default=180,
        help="Target duration in seconds for highlight video (CLI mode)"
    )

    args = parser.parse_args()

    # Validate video path if provided
    if args.video:
        video_path = Path(args.video)
        if not video_path.exists():
            print(f"Error: Video file not found: {args.video}")
            sys.exit(1)
        args.video = str(video_path.absolute())

    if args.cli:
        if not args.video:
            print("Error: --video is required in CLI mode")
            sys.exit(1)
        run_cli(args)
    else:
        run_web(args)


def run_web(args):
    """Run the web UI."""
    from src.web_ui.app import create_app

    print("\n" + "=" * 60)
    print("  Table Tennis Highlight Generator")
    print("=" * 60)

    app = create_app(
        video_path=args.video,
        data_dir="data",
    )

    print(f"\n  Starting web server at http://{args.host}:{args.port}")
    print("  Press Ctrl+C to stop\n")

    if args.video:
        print(f"  Video: {args.video}")
        print(f"  Open http://{args.host}:{args.port}/timeline to start analysis\n")
    else:
        print(f"  Open http://{args.host}:{args.port} to upload a video\n")

    app.run(host=args.host, port=args.port, debug=True)


def run_cli(args):
    """Run in CLI mode without web UI."""
    from src.video_processor import VideoProcessor, format_timestamp
    from src.audio_analyzer import AudioAnalyzer
    from src.rally_detector import RallyDetector
    from src.highlight_scorer import HighlightScorer
    from src.video_compiler import VideoCompiler, CompilationConfig

    print("\n" + "=" * 60)
    print("  Table Tennis Highlight Generator (CLI Mode)")
    print("=" * 60)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Process video
    print(f"\n[1/5] Loading video: {args.video}")
    processor = VideoProcessor(args.video, str(output_dir))
    metadata = processor.extract_metadata()
    print(f"      Duration: {format_timestamp(metadata.duration)}")
    print(f"      Resolution: {metadata.width}x{metadata.height}")
    print(f"      FPS: {metadata.fps:.2f}")

    # Step 2: Extract and analyze audio
    print("\n[2/5] Extracting and analyzing audio...")
    audio_path = processor.extract_audio()
    analyzer = AudioAnalyzer(audio_path)
    analysis = analyzer.analyze()
    print(f"      Detected {len(analysis.ball_hits)} potential ball hits")

    # Step 3: Detect rallies
    print("\n[3/5] Detecting rallies...")
    detector = RallyDetector()
    rallies = detector.detect_rallies(analysis, metadata.duration)

    # Add crowd intensity
    crowd_segments = analyzer.detect_crowd_noise()
    rallies = detector.add_crowd_intensity(rallies, crowd_segments)

    print(f"      Found {len(rallies)} rallies")

    if len(rallies) == 0:
        print("\n      No rallies detected. Try adjusting detection parameters.")
        sys.exit(1)

    # Step 4: Score rallies
    print("\n[4/5] Scoring rallies...")
    scorer = HighlightScorer()
    scored_rallies = scorer.score_all(rallies)

    # Show top rallies
    print("\n      Top rallies:")
    for sr in scored_rallies[:10]:
        print(f"        #{sr.rank}: {format_timestamp(sr.rally.start_time)}-{format_timestamp(sr.rally.end_time)} "
              f"({sr.rally.hit_count} hits, score: {sr.score:.1f})")

    # Step 5: Compile highlights
    print(f"\n[5/5] Compiling highlight video...")

    selected = scorer.select_highlights(
        scored_rallies,
        target_duration=args.target_duration,
        max_highlights=args.top_n,
    )

    print(f"      Selected {len(selected)} rallies")
    total_duration = sum(sr.rally.duration for sr in selected)
    print(f"      Total duration: {format_timestamp(total_duration)}")

    compiler = VideoCompiler(args.video, str(output_dir))
    clips = compiler.prepare_clips(selected)

    output_path = compiler.compile_highlights(clips)

    print("\n" + "=" * 60)
    print("  Done!")
    print(f"  Output: {output_path}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()

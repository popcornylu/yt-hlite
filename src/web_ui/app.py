"""Flask web application for human-in-the-loop feedback interface."""

import os
import json
import subprocess
import platform
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, url_for

from ..video_processor import VideoProcessor, format_timestamp
from ..audio_analyzer import AudioAnalyzer
from ..rally_detector import RallyDetector, Rally
from ..highlight_scorer import HighlightScorer, ScoredRally
from ..preference_learner import PreferenceLearner
from ..video_compiler import VideoCompiler, CompilationConfig


def create_app(
    video_path: str = None,
    data_dir: str = None,
) -> Flask:
    """
    Create and configure the Flask application.

    Args:
        video_path: Path to video file (can be set later)
        data_dir: Base directory for data storage

    Returns:
        Configured Flask app
    """
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    # Get project root (tt-highlight directory)
    project_root = Path(__file__).parent.parent.parent

    # Configuration - use absolute path based on project root
    if data_dir is None:
        app.config["DATA_DIR"] = project_root / "data"
    else:
        app.config["DATA_DIR"] = Path(data_dir).resolve()
    app.config["OUTPUT_DIR"] = app.config["DATA_DIR"] / "output"
    app.config["FEEDBACK_DIR"] = app.config["DATA_DIR"] / "feedback"
    app.config["VIDEO_PATH"] = video_path

    # Ensure directories exist
    app.config["OUTPUT_DIR"].mkdir(parents=True, exist_ok=True)
    app.config["FEEDBACK_DIR"].mkdir(parents=True, exist_ok=True)

    # State storage (in production, use a proper database)
    app.state = {
        "video_processor": None,
        "audio_analyzer": None,
        "audio_analysis": None,
        "rally_detector": None,
        "rallies": [],
        "scored_rallies": [],
        "highlight_scorer": None,
        "preference_learner": None,
        "video_compiler": None,
        "volume_data": None,
    }

    # Initialize preference learner
    app.state["preference_learner"] = PreferenceLearner(
        str(app.config["FEEDBACK_DIR"])
    )
    app.state["highlight_scorer"] = HighlightScorer(
        weights=app.state["preference_learner"].weights
    )

    # Routes
    @app.route("/")
    def index():
        """Main page - video upload or status."""
        has_video = app.config["VIDEO_PATH"] is not None
        video_name = Path(app.config["VIDEO_PATH"]).name if has_video else None
        return render_template(
            "index.html",
            has_video=has_video,
            video_name=video_name,
        )

    @app.route("/upload", methods=["POST"])
    def upload_video():
        """Handle video upload."""
        if "video" not in request.files:
            return jsonify({"error": "No video file provided"}), 400

        file = request.files["video"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400

        # Save uploaded file
        input_dir = app.config["DATA_DIR"] / "input"
        input_dir.mkdir(parents=True, exist_ok=True)

        video_path = input_dir / file.filename
        file.save(str(video_path))

        app.config["VIDEO_PATH"] = str(video_path)

        return jsonify({
            "success": True,
            "video_path": str(video_path),
            "redirect": url_for("timeline"),
        })

    @app.route("/set-video", methods=["POST"])
    def set_video():
        """Set video path directly (for local file selection)."""
        data = request.get_json()
        video_path = data.get("path") or data.get("video_path")

        if not video_path:
            return jsonify({"error": "No path provided"}), 400

        # Expand ~ and resolve path
        video_path = str(Path(video_path).expanduser().resolve())

        if not Path(video_path).exists():
            return jsonify({"error": f"File not found: {video_path}"}), 400

        if not Path(video_path).is_file():
            return jsonify({"error": f"Not a file: {video_path}"}), 400

        app.config["VIDEO_PATH"] = video_path
        return jsonify({
            "success": True,
            "video_path": video_path,
            "redirect": url_for("candidates"),
        })

    @app.route("/browse-video")
    def browse_video():
        """Open native file picker dialog (macOS only)."""
        if platform.system() != "Darwin":
            return jsonify({"error": "Native file picker only available on macOS"}), 400

        # AppleScript to open file picker - can access Photos library
        script = '''
        tell application "System Events"
            activate
        end tell
        set videoFile to choose file with prompt "Select a video file" of type {"public.movie", "com.apple.quicktime-movie", "public.mpeg-4", "public.avi"}
        return POSIX path of videoFile
        '''

        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout for user to select
            )

            if result.returncode == 0 and result.stdout.strip():
                return jsonify({"path": result.stdout.strip()})
            else:
                # User cancelled or error
                return jsonify({"error": "No file selected", "cancelled": True})

        except subprocess.TimeoutExpired:
            return jsonify({"error": "File picker timed out"}), 408
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/timeline")
    def timeline():
        """Redirect to candidates page (timeline merged into candidates)."""
        from flask import redirect
        return redirect(url_for("candidates"))

    @app.route("/api/analyze", methods=["POST"])
    def analyze_video():
        """Start video analysis."""
        if not app.config["VIDEO_PATH"]:
            return jsonify({"error": "No video loaded"}), 400

        video_path = app.config["VIDEO_PATH"]

        try:
            # Initialize processors
            app.state["video_processor"] = VideoProcessor(
                video_path,
                str(app.config["OUTPUT_DIR"])
            )

            # Extract metadata
            metadata = app.state["video_processor"].extract_metadata()

            # Extract audio
            audio_path = app.state["video_processor"].extract_audio()

            # Analyze audio
            app.state["audio_analyzer"] = AudioAnalyzer(audio_path)
            app.state["audio_analysis"] = app.state["audio_analyzer"].analyze()

            # Get volume data for visualization
            app.state["volume_data"] = app.state["audio_analyzer"].get_volume_data_for_visualization()

            # Detect rallies with tighter parameters for table tennis
            # - max_hit_interval: 1.2s (ball exchanges are fast in TT)
            # - min_rally_gap: 4.0s (clear separation between points)
            app.state["rally_detector"] = RallyDetector(
                min_hits_per_rally=4,
                max_hit_interval=1.2,
                min_rally_gap=4.0,
                context_before=1.0,
                context_after=1.5,
            )
            app.state["rallies"] = app.state["rally_detector"].detect_rallies(
                app.state["audio_analysis"],
                metadata.duration,
                metadata.fps,
            )

            # Add crowd intensity
            crowd_segments = app.state["audio_analyzer"].detect_crowd_noise()
            app.state["rallies"] = app.state["rally_detector"].add_crowd_intensity(
                app.state["rallies"],
                crowd_segments,
            )

            # Score rallies
            app.state["scored_rallies"] = app.state["highlight_scorer"].score_all(
                app.state["rallies"]
            )

            # Start feedback session
            app.state["preference_learner"].start_session(video_path)

            # Generate thumbnails
            thumbnails = app.state["video_processor"].generate_thumbnails(num_thumbnails=30)

            return jsonify({
                "success": True,
                "metadata": metadata.to_dict(),
                "num_rallies": len(app.state["rallies"]),
                "num_ball_hits": len(app.state["audio_analysis"].ball_hits),
                "thumbnails": thumbnails,
            })

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/volume-data")
    def get_volume_data():
        """Get audio volume data for waveform visualization."""
        if app.state["volume_data"] is None:
            return jsonify({"error": "No analysis data"}), 400

        return jsonify(app.state["volume_data"])

    @app.route("/api/rallies")
    def get_rallies():
        """Get detected rallies."""
        rallies = app.state.get("scored_rallies", [])
        return jsonify({
            "rallies": [sr.to_dict() for sr in rallies],
            "summary": app.state["highlight_scorer"].get_score_summary(rallies)
            if rallies else {},
        })

    @app.route("/api/rally/<rally_id>")
    def get_rally(rally_id):
        """Get single rally details."""
        for sr in app.state.get("scored_rallies", []):
            if sr.rally.id == rally_id:
                return jsonify(sr.to_dict())
        return jsonify({"error": "Rally not found"}), 404

    @app.route("/api/rally/<rally_id>/rate", methods=["POST"])
    def rate_rally(rally_id):
        """Rate a rally (1-5 stars)."""
        data = request.get_json()
        rating = data.get("rating")

        if not isinstance(rating, int) or rating < 1 or rating > 5:
            return jsonify({"error": "Rating must be 1-5"}), 400

        # Find and update rally
        for sr in app.state.get("scored_rallies", []):
            if sr.rally.id == rally_id:
                sr.rally.user_rating = rating
                app.state["preference_learner"].record_rating(rally_id, rating)
                return jsonify({"success": True, "rally": sr.to_dict()})

        return jsonify({"error": "Rally not found"}), 404

    @app.route("/api/rally/<rally_id>/confirm", methods=["POST"])
    def confirm_rally(rally_id):
        """Confirm or reject a rally as highlight."""
        data = request.get_json()
        is_highlight = data.get("is_highlight", True)

        for sr in app.state.get("scored_rallies", []):
            if sr.rally.id == rally_id:
                sr.rally.is_highlight = is_highlight
                sr.rally.is_confirmed = True
                app.state["preference_learner"].record_confirmation(rally_id, is_highlight)
                return jsonify({"success": True, "rally": sr.to_dict()})

        return jsonify({"error": "Rally not found"}), 404

    @app.route("/api/rally/<rally_id>/adjust", methods=["POST"])
    def adjust_rally_bounds(rally_id):
        """Adjust rally start/end frames."""
        data = request.get_json()
        new_start_frame = data.get("start_frame")
        new_end_frame = data.get("end_frame")

        if new_start_frame is None or new_end_frame is None:
            return jsonify({"error": "start_frame and end_frame required"}), 400

        for sr in app.state.get("scored_rallies", []):
            if sr.rally.id == rally_id:
                sr.rally.start_frame = int(new_start_frame)
                sr.rally.end_frame = int(new_end_frame)
                # Log with time values for preference learner
                app.state["preference_learner"].record_boundary_adjustment(
                    rally_id, sr.rally.start_time, sr.rally.end_time
                )
                return jsonify({"success": True, "rally": sr.to_dict()})

        return jsonify({"error": "Rally not found"}), 404

    @app.route("/api/add-rally", methods=["POST"])
    def add_missed_rally():
        """Add a missed rally that the system didn't detect."""
        data = request.get_json()
        start_frame = data.get("start_frame")
        end_frame = data.get("end_frame")

        if start_frame is None or end_frame is None:
            return jsonify({"error": "start_frame and end_frame required"}), 400

        # Get fps from video processor metadata
        if app.state["video_processor"] is None:
            return jsonify({"error": "Video not analyzed yet"}), 400

        metadata = app.state["video_processor"].extract_metadata()
        fps = metadata.fps

        # Create new rally
        new_id = f"rally_user_{len(app.state['rallies']):04d}"
        new_rally = Rally(
            id=new_id,
            start_frame=int(start_frame),
            end_frame=int(end_frame),
            fps=fps,
            hit_count=0,  # Unknown
            confidence=1.0,  # User-added
            is_confirmed=True,
            is_highlight=True,
        )

        app.state["rallies"].append(new_rally)

        # Score and add to scored list
        scored = app.state["highlight_scorer"].score_rally(new_rally)
        scored.score = 80  # Give user-added rallies a good default score
        app.state["scored_rallies"].append(scored)

        # Re-sort and re-rank
        app.state["scored_rallies"].sort(key=lambda x: x.score, reverse=True)
        for i, sr in enumerate(app.state["scored_rallies"]):
            sr.rank = i + 1

        # Log with time values for preference learner
        app.state["preference_learner"].record_missed_rally(
            new_rally.start_time, new_rally.end_time
        )

        return jsonify({"success": True, "rally": scored.to_dict()})

    @app.route("/candidates")
    def candidates():
        """Candidate review page."""
        return render_template("candidates.html")

    @app.route("/api/rescore", methods=["POST"])
    def rescore_rallies():
        """Re-score rallies after user feedback."""
        # Apply user overrides
        app.state["scored_rallies"] = app.state["highlight_scorer"].apply_user_overrides(
            app.state["scored_rallies"]
        )

        return jsonify({
            "success": True,
            "rallies": [sr.to_dict() for sr in app.state["scored_rallies"]],
        })

    @app.route("/api/learn", methods=["POST"])
    def learn_from_feedback():
        """Update weights based on feedback."""
        new_weights = app.state["highlight_scorer"].update_weights_from_feedback(
            app.state["scored_rallies"]
        )

        return jsonify({
            "success": True,
            "weights": new_weights.to_dict(),
        })

    @app.route("/review")
    def review():
        """Final review page before compilation."""
        return render_template("review.html")

    @app.route("/api/select-highlights", methods=["POST"])
    def select_highlights():
        """Select highlights for compilation."""
        data = request.get_json()
        target_duration = data.get("target_duration", 180)
        max_count = data.get("max_count", 15)
        min_score = data.get("min_score", 30)

        selected = app.state["highlight_scorer"].select_highlights(
            app.state["scored_rallies"],
            target_duration=target_duration,
            max_highlights=max_count,
            min_score=min_score,
        )

        return jsonify({
            "success": True,
            "selected": [sr.to_dict() for sr in selected],
            "total_duration": sum(sr.rally.duration for sr in selected),
        })

    @app.route("/api/compile", methods=["POST"])
    def compile_highlights():
        """Compile selected highlights into final video."""
        data = request.get_json()
        rally_ids = data.get("rally_ids", [])

        print(f"[COMPILE DEBUG] Received rally_ids: {rally_ids}")
        print(f"[COMPILE DEBUG] Total scored_rallies in state: {len(app.state.get('scored_rallies', []))}")

        if not rally_ids:
            # Use auto-selected highlights
            selected = app.state["highlight_scorer"].select_highlights(
                app.state["scored_rallies"]
            )
        else:
            # Use specified rallies
            selected = [
                sr for sr in app.state["scored_rallies"]
                if sr.rally.id in rally_ids
            ]

        print(f"[COMPILE DEBUG] Selected {len(selected)} rallies")
        for sr in selected:
            print(f"[COMPILE DEBUG]   - {sr.rally.id}: {sr.rally.start_time:.2f}s - {sr.rally.end_time:.2f}s (duration: {sr.rally.duration:.2f}s)")

        if not selected:
            return jsonify({"error": "No highlights selected"}), 400

        try:
            # Initialize compiler
            app.state["video_compiler"] = VideoCompiler(
                app.config["VIDEO_PATH"],
                str(app.config["OUTPUT_DIR"]),
            )

            # Prepare clips
            clips = app.state["video_compiler"].prepare_clips(selected)

            print(f"[COMPILE DEBUG] Prepared {len(clips)} clips")
            for clip in clips:
                print(f"[COMPILE DEBUG]   - {clip.rally_id}: {clip.start_time:.2f}s - {clip.end_time:.2f}s (duration: {clip.duration:.2f}s)")

            # Compile
            output_path = app.state["video_compiler"].compile_highlights(clips)

            # End feedback session
            app.state["preference_learner"].end_session(app.state["scored_rallies"])

            # Return URL for download (not file path)
            filename = Path(output_path).name
            download_url = f"/highlights/{filename}"

            return jsonify({
                "success": True,
                "output_path": download_url,
                "filename": filename,
                "summary": app.state["video_compiler"].get_compilation_summary(clips),
            })

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/preview/<rally_id>")
    def get_preview(rally_id):
        """Get or create preview clip for a rally."""
        for sr in app.state.get("scored_rallies", []):
            if sr.rally.id == rally_id:
                if app.state["video_compiler"] is None:
                    app.state["video_compiler"] = VideoCompiler(
                        app.config["VIDEO_PATH"],
                        str(app.config["OUTPUT_DIR"]),
                    )

                preview_path = app.state["video_compiler"].create_preview_clip(
                    rally_id,
                    sr.rally.start_time,
                    sr.rally.end_time,
                )
                return send_file(preview_path, mimetype="video/mp4")

        return jsonify({"error": "Rally not found"}), 404

    @app.route("/api/thumbnail/<int:index>")
    def get_thumbnail(index):
        """Get thumbnail image."""
        thumb_dir = app.config["OUTPUT_DIR"] / "thumbnails"
        thumbnails = sorted(thumb_dir.glob("thumb_*.jpg"))

        if 0 <= index < len(thumbnails):
            return send_file(thumbnails[index], mimetype="image/jpeg")

        return jsonify({"error": "Thumbnail not found"}), 404

    @app.route("/video")
    def serve_video():
        """Serve the source video."""
        if not app.config["VIDEO_PATH"]:
            return jsonify({"error": "No video loaded"}), 404

        return send_file(
            app.config["VIDEO_PATH"],
            mimetype="video/mp4",
        )

    @app.route("/highlights/<filename>")
    def serve_highlights(filename):
        """Serve compiled highlight video for download."""
        highlight_path = app.config["OUTPUT_DIR"] / filename
        if not highlight_path.exists():
            return jsonify({"error": "Highlight video not found"}), 404

        return send_file(
            str(highlight_path),
            mimetype="video/mp4",
            as_attachment=True,
            download_name=filename,
        )

    @app.route("/api/feedback-summary")
    def feedback_summary():
        """Get feedback session summary."""
        return jsonify(app.state["preference_learner"].get_session_summary())

    @app.route("/api/weights")
    def get_weights():
        """Get current scoring weights."""
        return jsonify(app.state["highlight_scorer"].weights.to_dict())

    @app.route("/api/weights/reset", methods=["POST"])
    def reset_weights():
        """Reset weights to defaults."""
        new_weights = app.state["preference_learner"].reset_weights()
        app.state["highlight_scorer"].weights = new_weights
        return jsonify({"success": True, "weights": new_weights.to_dict()})

    return app


def run_app(video_path: str = None, host: str = "127.0.0.1", port: int = 5000):
    """Run the Flask development server."""
    app = create_app(video_path=video_path)
    app.run(host=host, port=port, debug=True)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--video", default=None)
    args = parser.parse_args()
    run_app(video_path=args.video, host=args.host, port=args.port)

# Table Tennis Video Highlight Generator

A human-in-the-loop system for generating highlight reels from table tennis videos. The system automatically detects rallies and exciting moments, then allows you to review, rate, and adjust the selections before compiling the final highlight video.

## Features

- **Automatic Rally Detection**: Uses audio analysis to detect ball hits and identify rallies
- **Highlight Scoring**: Ranks rallies by excitement based on length, hit count, and crowd reactions
- **Human-in-the-Loop Feedback**: Review and rate detected rallies through an intuitive web interface
- **Preference Learning**: System learns from your feedback to improve future recommendations
- **Video Compilation**: Automatically compiles selected highlights into a final video

## Installation

### Prerequisites

- Python 3.10+
- FFmpeg (for video processing)

### Install FFmpeg

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt install ffmpeg
```

**Windows:**
Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH.

### Install Python Dependencies

```bash
cd tt-highlight
pip install -r requirements.txt
```

## Usage

### Web Interface (Recommended)

Start the web server:

```bash
python main.py
```

Or with a video pre-loaded:

```bash
python main.py --video path/to/your/video.mp4
```

Then open http://127.0.0.1:5000 in your browser.

### CLI Mode

For quick processing without the web interface:

```bash
python main.py --video path/to/your/video.mp4 --cli
```

Options:
- `--top-n 15`: Number of highlights to include (default: 15)
- `--target-duration 180`: Target duration in seconds (default: 180)
- `--output data/output`: Output directory

## Workflow

### 1. Upload Video
Upload your table tennis match video through the web interface or specify it via command line.

### 2. Timeline Review
The system analyzes the video and presents detected segments on a timeline. You can:
- View the audio waveform
- See detected rally segments
- Play specific portions
- Adjust segment boundaries
- Add missed rallies

### 3. Candidate Review
Review detected rallies sorted by highlight score:
- Preview each rally
- Rate rallies (1-5 stars)
- Confirm or reject rallies
- The system learns from your feedback

### 4. Final Review & Compilation
- Adjust compilation settings
- Review selected highlights
- Generate the final highlight video

## Project Structure

```
tt-highlight/
├── src/
│   ├── video_processor.py    # Video loading, metadata, thumbnails
│   ├── audio_analyzer.py     # Ball hit detection, crowd noise
│   ├── rally_detector.py     # Rally identification
│   ├── highlight_scorer.py   # Rally scoring and ranking
│   ├── preference_learner.py # Learning from feedback
│   ├── video_compiler.py     # Highlight compilation
│   └── web_ui/
│       ├── app.py            # Flask application
│       ├── templates/        # HTML templates
│       └── static/           # CSS styles
├── data/
│   ├── input/               # Source videos
│   ├── output/              # Generated highlights
│   └── feedback/            # Saved feedback data
├── main.py                  # CLI entry point
├── requirements.txt
└── README.md
```

## How It Works

### Rally Detection

The system detects rallies by analyzing audio patterns:

1. **Ball Hit Detection**: Identifies the characteristic "tick" sound of ball-paddle contact using onset detection and spectral analysis
2. **Rally Grouping**: Groups consecutive hits into rallies based on timing patterns
3. **Crowd Noise**: Detects audience reactions to identify exciting moments

### Scoring Formula

Rallies are scored based on:
- **Rally Length** (weight: 3.0): Longer rallies are more exciting
- **Hit Count** (weight: 2.5): More exchanges indicate better play
- **Crowd Intensity** (weight: 1.5): Audience reactions
- **Motion Intensity** (weight: 1.0): Visual action level
- **Detection Confidence** (weight: 0.5): Reliability of detection

Weights are automatically adjusted based on your feedback.

## Configuration

### Detection Parameters

In `src/rally_detector.py`:
- `min_hits_per_rally`: Minimum hits to consider a rally (default: 3)
- `max_hit_interval`: Maximum time between hits in a rally (default: 2.0s)
- `min_rally_gap`: Minimum gap between rallies (default: 2.0s)

### Compilation Settings

In `src/video_compiler.py`:
- `context_before`: Extra seconds before clip (default: 1.0)
- `context_after`: Extra seconds after clip (default: 1.5)
- `transition_duration`: Fade transition duration (default: 0.5)

## Tips for Best Results

1. **Good Audio Quality**: The system relies heavily on audio analysis. Videos with clear ball hit sounds work best.

2. **Provide Feedback**: Rate as many rallies as you can. The system learns from your preferences.

3. **Adjust Boundaries**: If automatic detection misses the start or end of exciting plays, adjust manually.

4. **Add Missed Rallies**: If the system misses a great rally, add it manually using the "Add Missed Rally" button.

## Troubleshooting

### No rallies detected
- Check if the audio is clear and contains ball hit sounds
- Try lowering the hit detection threshold in audio_analyzer.py

### Video won't load
- Ensure FFmpeg is installed and accessible in PATH
- Check if the video format is supported (MP4, MOV, AVI recommended)

### Compilation fails
- Ensure sufficient disk space
- Check FFmpeg error messages in the console

## License

MIT License

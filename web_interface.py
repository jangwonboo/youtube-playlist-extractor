import gradio as gr
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
import openai
from dotenv import load_dotenv
import os
import re
import pandas as pd
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Optional
import json
import threading
import time

# Load environment variables
load_dotenv()

# Initialize API keys
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Initialize the YouTube API client
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

# Available languages for transcripts
AVAILABLE_LANGUAGES = {
    'Korean': 'ko',
    'English': 'en',
    'Spanish': 'es',
    'French': 'fr',
    'German': 'de',
    'Japanese': 'ja',
    'Chinese': 'zh',
    'Russian': 'ru',
    'Portuguese': 'pt',
    'Italian': 'it'
}

# Available OpenAI models
AVAILABLE_MODELS = [
    'gpt-3.5-turbo',
    'gpt-4',
    'gpt-4-turbo-preview',
    'gpt-3.5-turbo-16k'
]

@dataclass
class VideoData:
    title: str
    video_id: str
    description: str
    transcript: str
    summary: str
    processed: bool = False

class ProcessManager:
    def __init__(self):
        self.is_paused = False
        self.should_stop = False
        self.processed_videos: List[VideoData] = []
        self.current_index = -1
        self.total_videos = 0
        self.processed_count = 0
        self.lock = threading.Lock()
        
    def pause(self):
        self.is_paused = True
        
    def resume(self):
        self.is_paused = False
        
    def stop(self):
        self.should_stop = True
        
    def reset(self):
        self.is_paused = False
        self.should_stop = False
        self.processed_videos = []
        self.current_index = -1
        self.total_videos = 0
        self.processed_count = 0
        
    def add_video(self, video: VideoData):
        with self.lock:
            self.processed_videos.append(video)
            self.processed_count += 1
            
    def get_video(self, index: int) -> Optional[VideoData]:
        if 0 <= index < len(self.processed_videos):
            return self.processed_videos[index]
        return None
        
    def get_current_video(self) -> Optional[VideoData]:
        return self.get_video(self.current_index)
        
    def move_to(self, index: int) -> Optional[VideoData]:
        if 0 <= index < len(self.processed_videos):
            self.current_index = index
            return self.processed_videos[index]
        return None

# Create a global process manager
process_manager = ProcessManager()

def update_process_status():
    """Update process status for the UI"""
    while not process_manager.should_stop:
        if process_manager.is_paused:
            yield "⏸️ Paused"
        else:
            yield f"⏵️ Processing {process_manager.processed_count}/{process_manager.total_videos}"
        time.sleep(1)
    yield "⏹️ Stopped"

def extract_video_id(url):
    """Extract the video ID from a YouTube URL."""
    patterns = [
        r'(?:v=|/v/|/embed/|youtu.be/)([^&?/]+)',
        r'youtube.com/shorts/([^&?/]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def extract_playlist_id(url):
    """Extract playlist ID from a YouTube URL."""
    pattern = r'(?:list=)([^&]+)'
    match = re.search(pattern, url)
    return match.group(1) if match else None

def get_playlist_videos(playlist_id):
    """Get all videos from a playlist."""
    videos = []
    next_page_token = None
    
    while True:
        request = youtube.playlistItems().list(
            part='snippet',
            playlistId=playlist_id,
            maxResults=50,
            pageToken=next_page_token
        )
        response = request.execute()
        
        for item in response['items']:
            video = {
                'title': item['snippet']['title'],
                'video_id': item['snippet']['resourceId']['videoId'],
                'published_at': item['snippet']['publishedAt']
            }
            videos.append(video)
        
        next_page_token = response.get('nextPageToken')
        if not next_page_token:
            break
    
    return videos

def get_video_info(video_id):
    """Get video information using the YouTube API."""
    try:
        request = youtube.videos().list(
            part="snippet",
            id=video_id
        )
        response = request.execute()
        
        if response['items']:
            return response['items'][0]['snippet']
        return None
    except Exception as e:
        return f"Error fetching video info: {str(e)}"

def get_transcript(video_id, lang='ko'):
    """Get transcript for a YouTube video."""
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
        return ' '.join([item['text'] for item in transcript_list])
    except (TranscriptsDisabled, NoTranscriptFound):
        try:
            # Fallback to English if preferred language is not available
            if lang != 'en':
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
                return ' '.join([item['text'] for item in transcript_list])
            return None
        except:
            return None
    except Exception as e:
        return f"Error fetching transcript: {str(e)}"

def generate_summary(transcript_text, model_name="gpt-3.5-turbo", lang='en'):
    """Generate a summary using OpenAI's API."""
    if not transcript_text:
        return "No transcript available to summarize."
    
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        
        # Limit transcript length
        max_chars = 15000
        if len(transcript_text) > max_chars:
            transcript_text = transcript_text[:max_chars] + "... [transcript truncated due to length]"
        
        # Add language instruction for the summary
        lang_instruction = f"Provide the summary in {lang}." if lang != 'en' else ""
        
        prompt = (
            "Please provide a reasonably detailed summary of the following transcript. "
            "Please try to capture the logical flow of the transcript and use different "
            f"indentation and bullet points to express the hierarchy of the content. {lang_instruction}\n\n"
            f"Transcript:\n{transcript_text}"
        )
        
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes video transcripts accurately and concisely."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error generating summary: {str(e)}"

def save_transcript(video_id, title, transcript, output_dir):
    """Save transcript to a file."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    safe_title = "".join(c for c in title if c.isalnum() or c in " ._-").strip()
    safe_title = safe_title[:100]
    filename = f"{safe_title}_{video_id}.txt"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(transcript)
    
    return filepath

def save_summary(video_id, title, summary, output_dir):
    """Save summary to a file."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    safe_title = "".join(c for c in title if c.isalnum() or c in " ._-").strip()
    safe_title = safe_title[:100]
    filename = f"{safe_title}_{video_id}_summary.txt"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(summary)
    
    return filepath

def process_videos(url, output_dir, transcript_dir, summary_dir, 
                  enable_transcript, enable_summary,
                  lang, model,
                  progress=gr.Progress()):
    """Process single video or playlist."""
    # Reset process manager
    process_manager.reset()
    
    # Create output directories
    os.makedirs(output_dir, exist_ok=True)
    if enable_transcript:
        os.makedirs(transcript_dir, exist_ok=True)
    if enable_summary:
        os.makedirs(summary_dir, exist_ok=True)
    
    # Get videos to process
    playlist_id = extract_playlist_id(url)
    if playlist_id:
        videos = get_playlist_videos(playlist_id)
        process_manager.total_videos = len(videos)
    else:
        video_id = extract_video_id(url)
        if not video_id:
            return (
                "Invalid YouTube URL",  # error
                "Error: Invalid URL",   # progress
                "",                     # title
                "",                     # description
                "",                     # transcript
                ""                      # summary
            )
        videos = [{'video_id': video_id}]
        process_manager.total_videos = 1
    
    # Process each video
    for video in progress.tqdm(videos, desc="Processing videos"):
        if process_manager.should_stop:
            break
            
        while process_manager.is_paused:
            time.sleep(1)
            if process_manager.should_stop:
                break
                
        video_id = video['video_id']
        video_info = get_video_info(video_id)
        
        if not video_info:
            continue
            
        # Create video data object
        video_data = VideoData(
            title=video_info['title'],
            video_id=video_id,
            description=video_info['description'],
            transcript="",
            summary=""
        )
        
        # Get transcript if enabled
        if enable_transcript:
            transcript = get_transcript(video_id, lang)
            if transcript:
                video_data.transcript = transcript
                save_transcript(video_id, video_data.title, transcript, transcript_dir)
                
                # Generate summary if enabled
                if enable_summary:
                    summary = generate_summary(transcript, model, lang)
                    if summary:
                        video_data.summary = summary
                        save_summary(video_id, video_data.title, summary, summary_dir)
        
        # Add processed video to manager
        video_data.processed = True
        process_manager.add_video(video_data)
        process_manager.current_index = len(process_manager.processed_videos) - 1
        
        # Yield current state
        yield (
            "",  # error
            f"Processing {process_manager.processed_count}/{process_manager.total_videos}",  # progress
            video_data.title,          # title
            video_data.description,    # description
            video_data.transcript,     # transcript
            video_data.summary         # summary
        )
    
    # Create final CSV
    if process_manager.processed_videos:
        results = [{
            'title': v.title,
            'video_id': v.video_id,
            'url': f'https://www.youtube.com/watch?v={v.video_id}',
            'has_transcript': bool(v.transcript),
            'has_summary': bool(v.summary)
        } for v in process_manager.processed_videos]
        
        df = pd.DataFrame(results)
        csv_path = os.path.join(output_dir, f'video_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        
    # Return final state
    current_video = process_manager.get_current_video()
    if current_video:
        return (
            "",  # error
            f"Completed {process_manager.processed_count}/{process_manager.total_videos}",  # progress
            current_video.title,          # title
            current_video.description,    # description
            current_video.transcript,     # transcript
            current_video.summary         # summary
        )
    else:
        return (
            "No videos processed",  # error
            "Process completed",    # progress
            "",                     # title
            "",                     # description
            "",                     # transcript
            ""                      # summary
        )

def navigate_videos(direction: str):
    """Navigate through processed videos"""
    if direction == "prev":
        video = process_manager.move_to(process_manager.current_index - 1)
    else:  # next
        video = process_manager.move_to(process_manager.current_index + 1)
    
    if video:
        return {
            "title": video.title,
            "description": video.description,
            "transcript": video.transcript,
            "summary": video.summary
        }
    return None

def create_interface():
    with gr.Blocks(title="YouTube Video/Playlist Processor", theme=gr.themes.Soft()) as interface:
        gr.Markdown("# YouTube Video/Playlist Processor")
        
        # Input Section
        with gr.Row():
            with gr.Column(scale=4):
                url_input = gr.Textbox(
                    label="YouTube URL",
                    placeholder="Enter YouTube video or playlist URL...",
                    info="Support both single video and playlist URLs"
                )
            with gr.Column(scale=1):
                with gr.Row():
                    process_btn = gr.Button("▶️ Start", variant="primary")
                    pause_btn = gr.Button("⏸️ Pause", variant="secondary")
                    stop_btn = gr.Button("⏹️ Stop", variant="stop")
        
        # Settings Section (collapsible)
        with gr.Accordion("Settings", open=False):
            with gr.Row():
                with gr.Column():
                    output_dir = gr.Textbox(
                        label="Output Directory",
                        value="output",
                        info="Directory for CSV output"
                    )
                    transcript_dir = gr.Textbox(
                        label="Transcript Directory",
                        value="transcripts",
                        info="Directory for transcript files"
                    )
                    summary_dir = gr.Textbox(
                        label="Summary Directory",
                        value="summaries",
                        info="Directory for summary files"
                    )
                with gr.Column():
                    enable_transcript = gr.Checkbox(
                        label="Enable Transcript",
                        value=True,
                        info="Get video transcripts"
                    )
                    enable_summary = gr.Checkbox(
                        label="Enable Summary",
                        value=True,
                        info="Generate AI summaries"
                    )
                    lang_dropdown = gr.Dropdown(
                        choices=list(AVAILABLE_LANGUAGES.keys()),
                        value="Korean",
                        label="Language",
                        info="Language for transcript and summary"
                    )
                    model_dropdown = gr.Dropdown(
                        choices=AVAILABLE_MODELS,
                        value='gpt-3.5-turbo',
                        label="OpenAI Model",
                        info="Model for generating summaries"
                    )
        
        # Progress Section with spinning indicator
        with gr.Row():
            progress_status = gr.Textbox(
                label="Progress",
                value="Ready to start",
                show_label=True
            )
        
        # Content Section with Navigation
        with gr.Row():
            with gr.Column(scale=1):
                prev_btn = gr.Button("← Previous")
            with gr.Column(scale=8):
                with gr.Tabs() as tabs:
                    with gr.Tab("Title"):
                        current_title = gr.Textbox(
                            label="Video Title",
                            interactive=False
                        )
                    with gr.Tab("Description"):
                        current_description = gr.TextArea(
                            label="Description",
                            interactive=False,
                            lines=10
                        )
                    with gr.Tab("Transcript"):
                        current_transcript = gr.TextArea(
                            label="Transcript",
                            interactive=False,
                            lines=15
                        )
                    with gr.Tab("Summary"):
                        current_summary = gr.TextArea(
                            label="Summary",
                            interactive=False,
                            lines=10
                        )
            with gr.Column(scale=1):
                next_btn = gr.Button("Next →")
        
        # Hidden status outputs
        error_output = gr.Textbox(visible=False)
        update_trigger = gr.Button("Update", visible=False)
        
        def update_ui():
            """Periodic update of UI elements"""
            if not process_manager.processed_videos:
                return ["", "", "", "", "Ready to start"]
            
            current_video = process_manager.get_current_video()
            if not current_video:
                return ["", "", "", "", "No video selected"]
            
            status = "⏸️ Paused" if process_manager.is_paused else "▶️ Processing"
            if process_manager.should_stop:
                status = "⏹️ Stopped"
            
            progress_text = f"{status} {process_manager.processed_count}/{process_manager.total_videos}"
            
            return [
                current_video.title,
                current_video.description,
                current_video.transcript,
                current_video.summary,
                progress_text
            ]
        
        # Control button events
        def start_processing():
            process_manager.reset()
            return "▶️ Processing..."
        
        def pause_processing():
            process_manager.pause()
            return "⏸️ Paused"
        
        def stop_processing():
            process_manager.stop()
            return "⏹️ Stopped"
        
        # Button event handlers
        process_btn.click(
            fn=start_processing,
            inputs=[],
            outputs=[progress_status],
            queue=False
        ).then(
            fn=process_videos,
            inputs=[
                url_input,
                output_dir,
                transcript_dir,
                summary_dir,
                enable_transcript,
                enable_summary,
                lang_dropdown,
                model_dropdown
            ],
            outputs=[
                error_output,
                progress_status,
                current_title,
                current_description,
                current_transcript,
                current_summary
            ]
        )
        
        pause_btn.click(
            fn=pause_processing,
            inputs=[],
            outputs=[progress_status],
            queue=False
        ).then(
            fn=update_ui,
            inputs=[],
            outputs=[
                current_title,
                current_description,
                current_transcript,
                current_summary,
                progress_status
            ]
        )
        
        stop_btn.click(
            fn=stop_processing,
            inputs=[],
            outputs=[progress_status],
            queue=False
        ).then(
            fn=update_ui,
            inputs=[],
            outputs=[
                current_title,
                current_description,
                current_transcript,
                current_summary,
                progress_status
            ]
        )
        
        # Navigation function with UI update
        def navigate_videos(direction: str):
            if direction == "prev":
                video = process_manager.move_to(process_manager.current_index - 1)
            else:  # next
                video = process_manager.move_to(process_manager.current_index + 1)
            
            if video:
                return (
                    video.title,
                    video.description,
                    video.transcript,
                    video.summary
                )
            return "", "", "", ""
        
        # Navigation events
        prev_btn.click(
            fn=lambda: navigate_videos("prev"),
            inputs=[],
            outputs=[
                current_title,
                current_description,
                current_transcript,
                current_summary
            ]
        )
        
        next_btn.click(
            fn=lambda: navigate_videos("next"),
            inputs=[],
            outputs=[
                current_title,
                current_description,
                current_transcript,
                current_summary
            ]
        )
        
        # Example URLs
        gr.Examples(
            examples=[
                ["https://www.youtube.com/watch?v=jMhiAyMX-to"],
                ["https://www.youtube.com/playlist?list=PLU9-uwewPMe2ACTcry7ChkTbujexZnjlN"],
            ],
            inputs=url_input
        )
    
    return interface

if __name__ == "__main__":
    interface = create_interface()
    interface.launch(share=True) 
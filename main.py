from googleapiclient.discovery import build
from datetime import datetime
import pandas as pd
import os
import argparse
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
import openai

# Load environment variables
load_dotenv()

# Default values
# 기본값
DEFAULT_API_KEY = os.getenv('YOUTUBE_API_KEY')
DEFAULT_OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
DEFAULT_PLAYLIST_ID = 'PLU9-uwewPMe2ACTcry7ChkTbujexZnjlN'  # 조코딩

def parse_arguments():
    parser = argparse.ArgumentParser(description='Extract YouTube playlist video information')
    # Add API key argument with default value
    # API 키 인수 추가 (기본값 설정)
    parser.add_argument('--api-key', '-k', 
                      default=DEFAULT_API_KEY,
                      help='YouTube Data API key (default: uses preset API key)')
    # Add playlist ID argument with default value
    # 재생목록 ID 인수 추가 (기본값 설정)
    parser.add_argument('--playlist-id', '-p',
                      default=DEFAULT_PLAYLIST_ID,
                      help='YouTube playlist ID (default: JoCoding playlist)')
    parser.add_argument('--output', '-o',
                      default=f'playlist_videos_{datetime.now().strftime("%Y%m%d")}.csv',
                      help='Output filename (default: playlist_videos_YYYYMMDD.csv)')
    parser.add_argument('--no-sort', 
                      action='store_true',
                      help='Do not sort videos by publish date')
    parser.add_argument('--transcripts', '-t',
                      action='store_true',
                      help='Fetch and store video transcripts/closed captions')
    parser.add_argument('--transcript-dir', '-td',
                      default='transcripts',
                      help='Directory to store transcripts (default: transcripts/)')
    parser.add_argument('--transcript-lang', '-tl',
                      default='ko',
                      help='Preferred language for transcripts (default: ko [Korean])')
    parser.add_argument('--include-transcript-in-csv','-it',
                      action='store_true',
                      help='Include transcript text in the CSV output')
    # LLM Summary options
    parser.add_argument('--summary', '-s',
                      action='store_true',
                      help='Generate LLM summaries of transcripts')
    parser.add_argument('--openai-api-key',
                      default=DEFAULT_OPENAI_API_KEY,
                      help='OpenAI API key for generating summaries')
    parser.add_argument('--summary-dir','-sd',
                      default='summaries',
                      help='Directory to store summaries (default: summaries/)')
    parser.add_argument('--include-summary-in-csv','-is',
                      action='store_true',
                      help='Include summary text in the CSV output')
    parser.add_argument('--summary-model','-sm',
                      default='gpt-3.5-turbo',
                      help='OpenAI model to use for summaries (default: gpt-3.5-turbo)')
    parser.add_argument('--summary-language','-sl',
                      default='',
                      help='Language for the summary (default: same as transcript)')
    return parser.parse_args()

def get_video_transcript(video_id, lang_code='ko'):
    """
    Fetch transcript for a YouTube video.
    
    Args:
        video_id (str): YouTube video ID
        lang_code (str): Preferred language code (default: 'ko' for Korean)
        
    Returns:
        str: Combined transcript text
        None: If no transcript is available
    """
    try:
        # First try with the preferred language
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang_code])
        
        # If no transcript in preferred language, try with auto-generated captions
        if not transcript_list and lang_code != 'en':
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
        
        # Combine all transcript pieces into a single text
        if transcript_list:
            return ' '.join([item['text'] for item in transcript_list])
        
        return None
    
    except (TranscriptsDisabled, NoTranscriptFound):
        # Handle cases where transcripts are not available
        return None
    except Exception as e:
        # Log any other error
        print(f"Error fetching transcript for {video_id}: {str(e)}")
        return None

def get_playlist_videos(youtube, playlist_id):
    videos = []
    
    # Get videos from playlist directly
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
            # Extract content between markers from description
            full_description = item['snippet']['description']
            
            # Define markers without special characters
            start_marker_text = "영상 속 소식 모아보기"
            end_marker_text = "목차"
            
            # Initialize extracted_content with full description
            extracted_content = full_description
            
            # Check if filter_flag parameter exists and is True
            # locals() returns a dictionary of local variables in the current scope
            # We're checking if 'filter_flag' exists as a variable and if it's True
            # filter_flag is not defined anywhere in the function or passed as a parameter
            # Let's modify this to use a parameter from args instead
            # For now, we'll keep the existing logic but add a comment about the issue
            
            filter_flag = True

            # TODO: filter_flag is undefined - this condition will never be true
            # Should be replaced with a proper parameter from args
            if filter_flag:
                # Find start marker position
                # Find start marker position
                start_idx = -1
                print("finding start marker")
                start_pos = full_description.find(start_marker_text)
                if start_pos != -1:
                    # start_idx는 start_marker_text 바로 다음 위치를 가리킴
                    start_idx = start_pos + len(start_marker_text)
                    print("start_pos:", start_pos, "start_marker:", start_marker_text)
                    print("start_idx set to:", start_idx)

                # Find end marker position
                end_idx = -1
                print("finding end marker")
                if start_idx != -1: # start_marker를 찾은 경우에만 end_marker 검색
                    # end_pos는 end_marker_text가 시작하는 위치
                    end_pos = full_description.find(end_marker_text, start_idx)
                    if end_pos != -1:
                        print("end_pos:", end_pos, "end_marker:", end_marker_text)
                        # end_idx는 end_marker_text의 시작 위치를 가리킴
                        # 슬라이싱 full_description[start_idx:end_idx] 시 end_idx 위치의 문자는 포함되지 않으므로,
                        # 결과적으로 end_marker_text 바로 앞까지 추출됨
                        end_idx = end_pos
                        print("end_idx set to:", end_idx)
                
                # Extract the content if both markers are found
                if start_idx != -1 and end_idx != -1:
                    extracted_content = full_description[start_idx:end_idx].strip()
                else:
                    extracted_content = ""  # Empty string if markers not found
            
            video = {
                'title': item['snippet']['title'],
                'description': extracted_content,
                'video_id': item['snippet']['resourceId']['videoId'],
                'published_at': item['snippet']['publishedAt']
            }
            videos.append(video)
        
        next_page_token = response.get('nextPageToken')
        if not next_page_token:
            break
    
    return videos

def generate_summary(transcript_text, model_name="gpt-3.5-turbo", summary_language=""):
    """
    Generate a summary of transcript text using OpenAI's API.
    
    Args:
        transcript_text (str): The transcript text to summarize
        model_name (str): The OpenAI model to use
        summary_language (str): The language for the summary output
    
    Returns:
        str: The generated summary
        None: If an error occurs
    """
    if not transcript_text:
        return None
    
    try:
        # Initialize the OpenAI client
        client = openai.OpenAI()
        
        # Prepare language instruction
        lang_instruction = ""
        if summary_language:
            lang_instruction = f" Provide the summary in {summary_language}."
        
        # Create prompt for summarization
        prompt = f"Please provide a concise summary of the following transcript.{lang_instruction}\n\nTranscript:\n{transcript_text}"
        
        # Limit transcript length if it's too long (OpenAI has token limits)
        max_chars = 15000  # Rough estimation to avoid token limit issues
        if len(transcript_text) > max_chars:
            truncated_text = transcript_text[:max_chars] + "... [transcript truncated due to length]"
            prompt = f"Please provide a resonably detailed summary of the following transcript. please try to capture the logical flow of the transcript and use differnet indentation and bullets points to express the hierachy of the content.(which has been truncated due to length).{lang_instruction}\n\nTranscript:\n{truncated_text}"
        
        # Make the API call
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes video transcripts accurately and concisely."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # Lower temperature for more focused summaries
            max_tokens=1000   # Limit response length
        )
        
        # Extract and return the summary text
        summary = response.choices[0].message.content.strip()
        return summary
    
    except Exception as e:
        print(f"Error generating summary: {str(e)}")
        return None

def save_transcript_to_file(video_id, title, transcript_text, transcript_dir):
    """
    Save transcript text to a file.
    
    Args:
        video_id (str): YouTube video ID
        title (str): Video title (used for filename)
        transcript_text (str): Transcript content
        transcript_dir (str): Directory to save transcript files
    """
    # Create directory if it doesn't exist
    if not os.path.exists(transcript_dir):
        os.makedirs(transcript_dir)
    
    # Clean the title to make it safe for filename
    safe_title = "".join(c for c in title if c.isalnum() or c in " ._-").strip()
    safe_title = safe_title[:100]  # Limit length
    
    # Create filename
    filename = f"{safe_title}_{video_id}.txt"
    filepath = os.path.join(transcript_dir, filename)
    
    # Write transcript to file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(transcript_text)
    
    return filepath

def save_summary_to_file(video_id, title, summary_text, summary_dir):
    """
    Save summary text to a file.
    
    Args:
        video_id (str): YouTube video ID
        title (str): Video title (used for filename)
        summary_text (str): Summary content
        summary_dir (str): Directory to save summary files
    """
    # Create directory if it doesn't exist
    if not os.path.exists(summary_dir):
        os.makedirs(summary_dir)
    
    # Clean the title to make it safe for filename
    safe_title = "".join(c for c in title if c.isalnum() or c in " ._-").strip()
    safe_title = safe_title[:100]  # Limit length
    
    # Create filename
    filename = f"{safe_title}_{video_id}_summary.txt"
    filepath = os.path.join(summary_dir, filename)
    
    # Write summary to file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(summary_text)
    
    return filepath

def main():
    # Parse command line arguments
    args = parse_arguments()
    
    # Create YouTube API client
    youtube = build('youtube', 'v3', developerKey=args.api_key)
    
    # Get videos from playlist
    videos = get_playlist_videos(youtube, args.playlist_id)
    
    # Convert to DataFrame
    df = pd.DataFrame(videos)
    
    # Fetch transcripts if requested
    if args.transcripts:
        print(f"Fetching transcripts for {len(videos)} videos...")
        # Add transcript column to track availability
        df['has_transcript'] = False
        
        if args.include_transcript_in_csv:
            df['transcript'] = ""
        
        # Add summary columns if summary generation is requested
        if args.summary:
            df['has_summary'] = False
            if args.include_summary_in_csv:
                df['summary'] = ""
            
            # Set OpenAI API key
            if args.openai_api_key:
                openai.api_key = args.openai_api_key
            else:
                print("Warning: No OpenAI API key provided. Summaries will not be generated.")
                args.summary = False
        
        transcript_count = 0
        summary_count = 0
        
        # Loop through each video to fetch its transcript
        for index, row in df.iterrows():
            video_id = row['video_id']
            title = row['title']
            
            print(f"Fetching transcript for: {title}")
            transcript = get_video_transcript(video_id, args.transcript_lang)
            
            if transcript:
                # Save transcript to file
                file_path = save_transcript_to_file(
                    video_id, 
                    title, 
                    transcript, 
                    args.transcript_dir
                )
                
                # Update dataframe
                df.at[index, 'has_transcript'] = True
                transcript_count += 1
                
                if args.include_transcript_in_csv:
                    df.at[index, 'transcript'] = transcript
                
                print(f"  Saved transcript to {file_path}")
                
                # Generate summary if requested
                if args.summary:
                    print(f"  Generating summary for: {title}")
                    summary = generate_summary(
                        transcript, 
                        args.summary_model,
                        args.summary_language
                    )
                    
                    if summary:
                        # Save summary to file
                        summary_path = save_summary_to_file(
                            video_id,
                            title,
                            summary,
                            args.summary_dir
                        )
                        
                        # Update dataframe
                        df.at[index, 'has_summary'] = True
                        summary_count += 1
                        
                        if args.include_summary_in_csv:
                            df.at[index, 'summary'] = summary
                        
                        print(f"  Saved summary to {summary_path}")
                    else:
                        print(f"  Failed to generate summary for {video_id}")
            else:
                print(f"  No transcript available for {video_id}")
        
        print(f"Transcripts found for {transcript_count} out of {len(videos)} videos.")
        if args.summary:
            print(f"Summaries generated for {summary_count} out of {transcript_count} videos with transcripts.")
    
    # Convert published_at to datetime
    df['published_at'] = pd.to_datetime(df['published_at'])
    
    # Sort by published date unless --no-sort is specified
    if not args.no_sort:
        df = df.sort_values('published_at', ascending=False)
    
    # Save to CSV
    df.to_csv(args.output, index=False, encoding='utf-8-sig')
    print(f"Data saved to {args.output}")

if __name__ == "__main__":
    main()

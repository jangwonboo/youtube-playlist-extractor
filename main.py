from googleapiclient.discovery import build
from datetime import datetime
import pandas as pd
import os
import argparse

# Default values
# 기본값
DEFAULT_API_KEY = 'AIzaSyAO4R0bDcpBA0ESY32mxmwi3zRNnkv2yNc'
DEFAULT_PLAYLIST_ID = 'PLU9-uwewPMe2ACTcry7ChkTbujexZnjlN'  # Nomadic Ambience playlist

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
                      help='YouTube playlist ID (default: Nomadic Ambience playlist)')
    parser.add_argument('--output', '-o',
                      default=f'playlist_videos_{datetime.now().strftime("%Y%m%d")}.csv',
                      help='Output filename (default: playlist_videos_YYYYMMDD.csv)')
    parser.add_argument('--no-sort', 
                      action='store_true',
                      help='Do not sort videos by publish date')
    return parser.parse_args()

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
            video = {
                'title': item['snippet']['title'],
                'description': item['snippet']['description'],
                'video_id': item['snippet']['resourceId']['videoId'],
                'published_at': item['snippet']['publishedAt']
            }
            videos.append(video)
        
        next_page_token = response.get('nextPageToken')
        if not next_page_token:
            break
    
    return videos

def main():
    # Parse command line arguments
    args = parse_arguments()
    
    # Create YouTube API client
    youtube = build('youtube', 'v3', developerKey=args.api_key)
    
    # Get videos from playlist
    videos = get_playlist_videos(youtube, args.playlist_id)
    
    # Convert to DataFrame
    df = pd.DataFrame(videos)
    
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

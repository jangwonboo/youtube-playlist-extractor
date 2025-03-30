# YouTube Playlist Video Extractor
# YouTube 재생목록 동영상 추출기

A Python script to extract video information from YouTube playlists using the YouTube Data API.
YouTube Data API를 사용하여 YouTube 재생목록의 동영상 정보를 추출하는 Python 스크립트입니다.

## Features | 주요 기능

- Extract video titles, descriptions, IDs, and publish dates from YouTube playlists
- Support for pagination to handle large playlists
- Command-line interface with configurable options
- Output to CSV format
- Bilingual comments (English/Korean)

- YouTube 재생목록에서 동영상 제목, 설명, ID, 발행일 추출
- 대용량 재생목록 처리를 위한 페이지네이션 지원
- 설정 가능한 명령줄 인터페이스
- CSV 형식으로 출력
- 이중 언어 주석 (영어/한국어)

## Prerequisites | 사전 요구사항

- Python 3.6 or higher | Python 3.6 이상
- YouTube Data API key | YouTube Data API 키

## Installation | 설치 방법

1. Clone the repository | 저장소 복제:
```bash
git clone https://github.com/yourusername/youtube-playlist-extractor.git
cd youtube-playlist-extractor
```

2. Install required packages | 필요한 패키지 설치:
```bash
pip install -r requirements.txt
```

## Usage | 사용 방법

### Basic Usage | 기본 사용법
```bash
python main.py
```

### With Custom Options | 사용자 정의 옵션 사용
```bash
python main.py --api-key YOUR_API_KEY --playlist-id YOUR_PLAYLIST_ID --output output.csv
```

### Command Line Arguments | 명령줄 인수

- `--api-key` or `-k`: YouTube Data API key (default: uses preset API key)
  YouTube Data API 키 (기본값: 미리 설정된 API 키 사용)
- `--playlist-id` or `-p`: YouTube playlist ID (default: Nomadic Ambience playlist)
  YouTube 재생목록 ID (기본값: Nomadic Ambience 재생목록)
- `--output` or `-o`: Output filename (default: playlist_videos_YYYYMMDD.csv)
  출력 파일 이름 (기본값: playlist_videos_YYYYMMDD.csv)
- `--no-sort`: Do not sort videos by publish date
  발행일 기준 정렬하지 않음

## Output Format | 출력 형식

The script generates a CSV file with the following columns:
스크립트는 다음 열이 포함된 CSV 파일을 생성합니다:

- title: Video title | 동영상 제목
- description: Video description | 동영상 설명
- video_id: YouTube video ID | YouTube 동영상 ID
- published_at: Publication date and time | 발행일 및 시간

## License | 라이선스

MIT License 
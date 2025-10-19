import googleapiclient.discovery
import googleapiclient.errors
import time
import multiprocessing

# Nhập API key của bạn
API_KEY = 'AIzaSyB8fn3AYC_aZeuXP2FdgnZ_ClSYDutiqKc'

# Khởi tạo YouTube API client
def youtube_client():
    youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=API_KEY)
    return youtube

# Hàm để lấy độ dài video
def get_video_duration(video_id):
    youtube = youtube_client()
    
    retries = 3  # Số lần thử lại nếu gặp lỗi
    for attempt in range(retries):
        try:
            request = youtube.videos().list(part="contentDetails", id=video_id)
            response = request.execute()
            
            # Kiểm tra phản hồi từ API
            if 'items' in response and len(response['items']) > 0:
                duration = response['items'][0]['contentDetails']['duration']
                # Convert duration từ ISO 8601 format sang giây
                duration_seconds = convert_duration_to_seconds(duration)
                return duration_seconds
            else:
                print(f"No details found for video {video_id}.")
                return None

        except googleapiclient.errors.HttpError as err:
            print(f"API Error on video {video_id}: {err}")
            if attempt < retries - 1:
                print("Retrying...")
                time.sleep(5)  # Đợi 5 giây trước khi thử lại
            else:
                print("Max retries reached. Skipping video.")
        except Exception as e:
            print(f"Unknown error on video {video_id}: {e}")
            break

# Chuyển đổi duration từ ISO 8601 sang giây
def convert_duration_to_seconds(duration):
    import re
    match = re.match(r'PT(\d+H)?(\d+M)?(\d+S)?', duration)
    
    hours = int(match.group(1)[:-1]) if match.group(1) else 0
    minutes = int(match.group(2)[:-1]) if match.group(2) else 0
    seconds = int(match.group(3)[:-1]) if match.group(3) else 0
    
    return hours * 3600 + minutes * 60 + seconds

# Hàm kiểm tra video từ danh sách
def process_video(link):
    video_id = link.strip().split("/")[-1]  # Extract video ID from the link
    duration_seconds = get_video_duration(video_id)
    if duration_seconds and duration_seconds <= 20:
        return link.strip()
    return None

# Hàm đọc file .txt và lọc video
def process_txt(input_file):
    # Đọc file txt chứa các link YouTube Shorts
    with open(input_file, 'r') as file:
        links = file.readlines()
    
    # Sử dụng multiprocessing để xử lý video song song
    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        valid_links = pool.map(process_video, links)
    
    # Lọc bỏ các giá trị None
    valid_links = [link for link in valid_links if link]

    # Ghi kết quả vào file txt mới
    with open("filtered_video_links.txt", 'w') as output_file:
        for link in valid_links:
            output_file.write(link + '\n')
    
    print("Filtered links saved to 'filtered_video_links.txt'.")

# Gọi hàm với file .txt đầu vào
if __name__ == '__main__':
    input_file = 'yt-link.txt'  # Tên file txt bạn muốn kiểm tra
    process_txt(input_file)

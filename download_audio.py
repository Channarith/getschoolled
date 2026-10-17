import yt_dlp

def fetch_and_clean_audio(video_url, output_filename="raw_source"):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{output_filename}.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '192',
        }],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])

# Example target: A highly natural public speaking snippet or conversation
fetch_and_clean_audio("https://www.youtube.com/watch?v=6siISXK2acw&list=PL33Hxj-htyNdJIrmOquNuFSTpCTNinUWL")
print("Video stripped and saved as raw_source.wav successfully.")

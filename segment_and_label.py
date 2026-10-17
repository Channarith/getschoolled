import os
import whisper
from pydub import AudioSegment

# 1. Load an ASR engine to automatically map what was spoken in the video
print("Loading Whisper Engine to auto-transcribe...")
model = whisper.load_model("large-v3")
result = model.transcribe("raw_source.wav")

# 2. Slice audio tracks based on punctuation/pauses detected by the model
audio = AudioSegment.from_wav("raw_source.wav")
os.makedirs("dataset/wavs", exist_ok=True)

with open("dataset/metadata.csv", "w", encoding="utf-8") as metadata_file:
    for idx, segment in enumerate(result["segments"]):
        start_ms = int(segment["start"] * 1000)
        end_ms = int(segment["end"] * 1000)
        text = segment["text"].strip()
        
        # Avoid processing completely empty blocks or single word gasps
        if len(text) < 3:
            continue
            
        # Export individual wave slice
        chunk = audio[start_ms:end_ms]
        chunk_filename = f"segment_{idx:04d}.wav"
        chunk.export(f"dataset/wavs/{chunk_filename}", format="wav")
        
        # Write formatted row required by deep learning data loader loops
        metadata_file.write(f"dataset/wavs/{chunk_filename}|{text}\n")

print("Dataset prepared successfully inside the 'dataset' directory!")

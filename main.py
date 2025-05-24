import os
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox

# Constants for paths
INPUT_DIR = "input"
TRANSCRIPT_DIR = "transcripts"
CLIPS_DIR = "clips"
CAPTIONS_DIR = "captions"
OUTPUT_DIR = "output"

os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(TRANSCRIPT_DIR, exist_ok=True)
os.makedirs(CLIPS_DIR, exist_ok=True)
os.makedirs(CAPTIONS_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

class VideoAutomationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Shorts Video Automation")
        self.video_path = None

        # Upload button
        self.upload_btn = tk.Button(root, text="Step 1: Upload Host Video", command=self.upload_video)
        self.upload_btn.pack(pady=5)

        # Transcription button
        self.transcribe_btn = tk.Button(root, text="Step 2: Transcribe & Split Video", command=self.transcribe_video)
        self.transcribe_btn.pack(pady=5)

        # Caption button
        self.caption_btn = tk.Button(root, text="Step 3: Generate Captions", command=self.generate_captions)
        self.caption_btn.pack(pady=5)

        # Template button
        self.template_btn = tk.Button(root, text="Step 4: Apply Template", command=self.apply_template)
        self.template_btn.pack(pady=5)

    def upload_video(self):
        path = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.mov")])
        if path:
            self.video_path = os.path.join(INPUT_DIR, os.path.basename(path))
            os.makedirs(INPUT_DIR, exist_ok=True)
            subprocess.run(["cp", path, self.video_path])
            messagebox.showinfo("Success", f"Video uploaded to {self.video_path}")

    def transcribe_video(self):
        if not self.video_path:
            messagebox.showerror("Error", "Please upload a video first.")
            return
        command = [
            "whisper", self.video_path,
            "--model", "medium",
            "--output_format", "json",
            "--output_dir", TRANSCRIPT_DIR
        ]
        subprocess.run(command)
        messagebox.showinfo("Done", "Transcription complete.")

    def generate_captions(self):
        messagebox.showinfo("Pending", "Caption generation logic will be implemented in the next step.")

    def apply_template(self):
        messagebox.showinfo("Pending", "Template application logic will be implemented in the next step.")

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoAutomationApp(root)
    root.mainloop()

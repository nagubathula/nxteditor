from flask import Flask, render_template, request, jsonify, send_file, session
import pandas as pd
import os
import uuid
import shutil
import whisper
import threading
from werkzeug.utils import secure_filename
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
import json

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['HOST_VIDEOS_FOLDER'] = 'hostvideos'
app.config['DATA_FOLDER'] = 'data'
app.config['EXPORTS_FOLDER'] = 'exports'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size

# Create necessary directories
for folder in [app.config['UPLOAD_FOLDER'], app.config['HOST_VIDEOS_FOLDER'], 
               app.config['DATA_FOLDER'], app.config['EXPORTS_FOLDER']]:
    os.makedirs(folder, exist_ok=True)

# Global variables to track processing status
processing_status = {}
transcripts = {}
video_info = {}

@app.route('/')
def index():
    return render_template('index.html', project_id=None)

@app.route('/upload_video', methods=['POST'])
def upload_video():
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400
    
    file = request.files['video']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file:
        # Generate unique ID for this session
        unique_id = str(uuid.uuid4())
        session['current_id'] = unique_id
        
        # Save the uploaded file
        filename = secure_filename(file.filename)
        ext = os.path.splitext(filename)[1]
        saved_filename = unique_id + ext
        video_path = os.path.join(app.config['HOST_VIDEOS_FOLDER'], saved_filename)
        file.save(video_path)
        
        # Store video info
        video_info[unique_id] = {
            'path': video_path,
            'filename': filename
        }
        
        # Start transcription in background
        processing_status[unique_id] = {'status': 'processing', 'progress': 0}
        thread = threading.Thread(target=transcribe_video, args=(video_path, unique_id))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Video uploaded successfully. Transcription started.',
            'id': unique_id
        })

def transcribe_video(video_path, unique_id):
    try:
        processing_status[unique_id]['status'] = 'transcribing'
        processing_status[unique_id]['progress'] = 10
        
        # Load Whisper model
        model = whisper.load_model("base")
        processing_status[unique_id]['progress'] = 30
        
        # Transcribe
        result = model.transcribe(video_path)
        processing_status[unique_id]['progress'] = 80
        
        # Process segments
        segments = result.get("segments", [])
        df_data = []
        for seg in segments:
            start = seg['start']
            end = seg['end']
            text = seg['text'].strip()
            df_data.append({
                'start': start, 
                'end': end, 
                'text': text,
                'hostvideoavailable': True
            })
        
        df = pd.DataFrame(df_data)
        
        # Save transcript
        csv_path = os.path.join(app.config['DATA_FOLDER'], unique_id + ".csv")
        df.to_csv(csv_path, index=False)
        
        # Store in memory
        transcripts[unique_id] = df

        # Try to associate a video file with the same unique_id
        host_folder = app.config['HOST_VIDEOS_FOLDER']
        for ext in ['.mp4', '.mov', '.avi', '.mkv']:
            possible_video_path = os.path.join(host_folder, unique_id + ext)
            if os.path.exists(possible_video_path):
                video_info[unique_id] = {
                    'path': possible_video_path,
                    'filename': os.path.basename(possible_video_path)
                }
                break

        
        processing_status[unique_id] = {
            'status': 'completed',
            'progress': 100,
            'csv_path': csv_path
        }
        
    except Exception as e:
        processing_status[unique_id] = {
            'status': 'error',
            'progress': 0,
            'error': str(e)
        }

@app.route('/upload_csv', methods=['POST'])
def upload_csv():
    if 'csv' not in request.files:
        return jsonify({'error': 'No CSV file provided'}), 400

    file = request.files['csv']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    try:
        # Extract unique_id from the uploaded CSV filename (e.g., abcd1234.csv)
        filename_wo_ext = os.path.splitext(secure_filename(file.filename))[0]
        unique_id = filename_wo_ext  # assume it's the same ID used during original video upload
        session['current_id'] = unique_id

        # Read CSV directly from upload
        df = pd.read_csv(file)

        if 'hostvideoavailable' not in df.columns:
            df['hostvideoavailable'] = True

        transcripts[unique_id] = df

        # Save CSV
        csv_path = os.path.join(app.config['DATA_FOLDER'], unique_id + ".csv")
        df.to_csv(csv_path, index=False)

        # Try to associate a video with the same ID
        host_folder = app.config['HOST_VIDEOS_FOLDER']
        for ext in ['.mp4', '.mov', '.avi', '.mkv']:
            possible_video_path = os.path.join(host_folder, unique_id + ext)
            if os.path.exists(possible_video_path):
                video_info[unique_id] = {
                    'path': possible_video_path,
                    'filename': os.path.basename(possible_video_path)
                }
                break

        return jsonify({
            'success': True,
            'message': 'CSV uploaded successfully',
            'id': unique_id,
            'transcript': df.to_dict('records')
        })

    except Exception as e:
        return jsonify({'error': f'Failed to process CSV: {str(e)}'}), 400

@app.route('/get_status/<unique_id>')
def get_status(unique_id):
    status = processing_status.get(unique_id, {'status': 'not_found'})
    if status['status'] == 'completed' and unique_id in transcripts:
        status['transcript'] = transcripts[unique_id].to_dict('records')
    return jsonify(status)

@app.route('/get_transcript/<unique_id>')
def get_transcript(unique_id):
    if unique_id in transcripts:
        return jsonify({
            'success': True,
            'transcript': transcripts[unique_id].to_dict('records')
        })
    return jsonify({'error': 'Transcript not found'}), 404

@app.route('/update_transcript', methods=['POST'])
def update_transcript():
    data = request.get_json()
    unique_id = data.get('id')
    transcript_data = data.get('transcript')
    
    if unique_id not in transcripts:
        return jsonify({'error': 'Transcript not found'}), 404
    
    try:
        # Update transcript
        df = pd.DataFrame(transcript_data)
        transcripts[unique_id] = df
        
        # Save to file
        csv_path = os.path.join(app.config['DATA_FOLDER'], unique_id + ".csv")
        df.to_csv(csv_path, index=False)
        
        return jsonify({'success': True, 'message': 'Transcript updated'})
    except Exception as e:
        return jsonify({'error': f'Failed to update transcript: {str(e)}'}), 400

@app.route('/export_video', methods=['POST'])
def export_video():
    data = request.get_json()
    unique_id = data.get('id')
    
    if unique_id not in transcripts or unique_id not in video_info:
        return jsonify({'error': 'Video or transcript not found'}), 404
    
    # Start export in background
    export_id = str(uuid.uuid4())
    processing_status[export_id] = {'status': 'exporting', 'progress': 0}
    
    thread = threading.Thread(target=export_youtube_short, args=(unique_id, export_id))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'export_id': export_id,
        'message': 'Export started'
    })

def export_youtube_short(unique_id, export_id):
    try:
        processing_status[export_id]['progress'] = 10
        
        df = transcripts[unique_id]
        video_path = video_info[unique_id]['path']
        
        processing_status[export_id]['progress'] = 20
        
        # Load video
        video = VideoFileClip(video_path)
        processing_status[export_id]['progress'] = 40
        
        # Create text clips
        text_clips = []
        for _, row in df.iterrows():
            if not row.get('hostvideoavailable', True):
                continue
            
            txt_clip = (
                TextClip(
                    row['text'],
                    fontsize=60,
                    color='white',
                    bg_color='black',
                    font='Arial-Bold',
                    size=(video.w, 200),
                    method='caption'
                )
                .set_position(('center', 'bottom'))
                .set_start(row['start'])
                .set_end(row['end'])
            )
            text_clips.append(txt_clip)
        
        processing_status[export_id]['progress'] = 60
        
        # Composite video
        final = CompositeVideoClip([video, *text_clips])
        
        # Export
        output_path = os.path.join(app.config['EXPORTS_FOLDER'], f"{export_id}.mp4")
        final.write_videofile(output_path, codec='libx264', fps=30, audio_codec='aac')
        
        processing_status[export_id] = {
            'status': 'completed',
            'progress': 100,
            'output_path': output_path
        }
        
    except Exception as e:
        processing_status[export_id] = {
            'status': 'error',
            'progress': 0,
            'error': str(e)
        }

@app.route('/download_export/<export_id>')
def download_export(export_id):
    status = processing_status.get(export_id)
    if status and status['status'] == 'completed':
        return send_file(status['output_path'], as_attachment=True, 
                        download_name=f'youtube_short_{export_id}.mp4')
    return jsonify({'error': 'Export not found or not ready'}), 404

@app.route('/download_transcript/<unique_id>')
def download_transcript(unique_id):
    if unique_id in transcripts:
        csv_path = os.path.join(app.config['DATA_FOLDER'], unique_id + ".csv")
        if os.path.exists(csv_path):
            return send_file(csv_path, as_attachment=True, 
                           download_name=f'transcript_{unique_id}.csv')
    return jsonify({'error': 'Transcript not found'}), 404

@app.route('/get_video/<unique_id>')
def get_video(unique_id):
    if unique_id in video_info:
        video_path = video_info[unique_id]['path']
        if os.path.exists(video_path):
            return send_file(video_path)
    return jsonify({'error': 'Video not found'}), 404

@app.route('/project/<unique_id>')
def project(unique_id):
    # Validate if ID exists
    transcript_exists = os.path.exists(os.path.join(app.config['DATA_FOLDER'], unique_id + ".csv"))
    video_exists = any(os.path.exists(os.path.join(app.config['HOST_VIDEOS_FOLDER'], unique_id + ext)) for ext in ['.mp4', '.mov', '.avi', '.mkv'])
    
    if not transcript_exists and not video_exists:
        return "Project not found", 404
    
    return render_template('index.html', project_id=unique_id)



if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
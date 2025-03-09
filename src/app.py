from flask import Flask, request, render_template, send_file, session
import io
from pathlib import Path
from slice import slice_dxf  # Import your slicing function directly

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Required for session management

BASE_DIR = Path(__file__).parent
UPLOAD_FOLDER = BASE_DIR / 'uploads'
UPLOAD_FOLDER.mkdir(exist_ok=True)

VISUALIZATION_FOLDER = BASE_DIR / 'static' / 'images'
VISUALIZATION_FOLDER.mkdir(parents=True, exist_ok=True)

TEMP_FOLDER = BASE_DIR / 'temp'
TEMP_FOLDER.mkdir(exist_ok=True)

@app.route('/', methods=['GET', 'POST'])
def index():
    gcode_content = None
    filename = session.get('filename')  # Load filename from session
    spacing = request.form.get('spacing', '10')  # Default spacing

    if request.method == 'POST':
        file = request.files.get('file')

        # Handle new file upload or reuse the previous file
        if file and file.filename.endswith('.dxf'):
            file_path = UPLOAD_FOLDER / file.filename
            file.save(str(file_path))
            session['filename'] = file.filename  # Store filename in session
        elif filename:
            file_path = UPLOAD_FOLDER / filename  # Use existing file if no new file uploaded
        else:
            return render_template('index.html', output=None, image_url=None, filename=None)

        output_image_path = VISUALIZATION_FOLDER / 'visualization.png'

        try:
            # Pass spacing to slice_dxf
            gcode_content = slice_dxf(str(file_path), output_image_path=str(output_image_path), spacing=int(spacing))
            filename = filename.replace('.dxf', '.gcode')

            # Save G-code content to a temporary file
            gcode_file_path = TEMP_FOLDER / filename
            with open(gcode_file_path, 'w') as f:
                f.write(gcode_content)

        except Exception as e:
            gcode_content = f"Error running script: {str(e)}"

        return render_template('index.html',
                               output=gcode_content,
                               image_url=f"/static/images/visualization.png",
                               filename=filename,
                               saved_spacing=spacing)  # Pass spacing to keep the value persistent

    return render_template('index.html', output=None, image_url=None, filename=None, saved_spacing='10')

@app.route('/download')
def download_file():
    filename = request.args.get('filename')
    file_path = TEMP_FOLDER / filename

    if file_path.exists():
        return send_file(
            file_path,
            mimetype='text/plain',
            as_attachment=True,
            download_name=filename
        )
    return "No G-code available", 404


if __name__ == '__main__':
    app.run(debug=True)

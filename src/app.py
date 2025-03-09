from flask import Flask, request, render_template, send_file
import io
from pathlib import Path
from slice import slice_dxf  # Import your slicing function directly

app = Flask(__name__)
BASE_DIR = Path(__file__).parent
UPLOAD_FOLDER = BASE_DIR / 'uploads'
UPLOAD_FOLDER.mkdir(exist_ok=True)

VISUALIZATION_FOLDER = BASE_DIR / 'static' / 'images'
VISUALIZATION_FOLDER.mkdir(parents=True, exist_ok=True)

@app.route('/', methods=['GET', 'POST'])
def index():
    gcode_content = None
    filename = None

    if request.method == 'POST':
        file = request.files['file']
        if file and file.filename.endswith('.dxf'):
            file_path = UPLOAD_FOLDER / file.filename
            file.save(str(file_path))

            output_image_path = VISUALIZATION_FOLDER / 'visualization.png'

            try:
                gcode_content = slice_dxf(str(file_path), output_image_path=str(output_image_path))
                filename = f"{file.filename}.gcode"
            except Exception as e:
                gcode_content = f"Error running script: {str(e)}"

            return render_template('index.html',
                                   output=gcode_content,
                                   image_url=f"/static/images/visualization.png",
                                   filename=filename)

    return render_template('index.html', output=None, image_url=None, filename=None)

@app.route('/download')
def download_file():
    gcode_content = request.args.get('content')
    filename = request.args.get('filename', 'output.gcode')

    if gcode_content:
        return send_file(
            io.BytesIO(gcode_content.encode('utf-8')),
            mimetype='text/plain',
            as_attachment=True,
            download_name=filename
        )
    return "No G-code available", 404

if __name__ == '__main__':
    app.run(debug=True)

from flask import Flask, request, render_template, send_from_directory
import os
from synth import process_source

app = Flask(__name__)

# These should match what you have in synth.py
input_dir = "operation_tests"
output_dir = "output"
visual_dir = "visualizations"

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file = request.files.get('input_file')
        if file:
            source = file.read().decode('utf-8')
            results = process_source(source, output_dir, visual_dir)
            if 'error' in results:
                return f"<h1>Error: {results['error']}</h1>"
            
            output = results['output']
            ast1_img = results['ast1']
            ast2_img = results['ast2']

            # Return a simple HTML page showing the results
            return f"""
            <h1>Results</h1>
            <pre>{output}</pre>
            <h2>AST Visualizations</h2>
            <img src="/view_image?path={ast1_img}" alt="AST1">
            <img src="/view_image?path={ast2_img}" alt="AST2">
            <br><a href="/">Upload Another File</a>
            """
    return render_template('index.html')

@app.route('/view_image')
def view_image():
    image_path = request.args.get('path', '')
    # Safely send the file
    directory = os.path.dirname(image_path)
    filename = os.path.basename(image_path)
    return send_from_directory(directory, filename)

if __name__ == '__main__':
    app.run(debug=True)

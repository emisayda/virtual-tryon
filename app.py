from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import requests
import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Configuration
class Config:
    LOCAL_BACKEND_URL = os.getenv('LOCAL_BACKEND_URL', 'https://dd6e-193-255-198-135.ngrok-free.app')
    REQUEST_TIMEOUT = 30

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Virtual Try-On</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 min-h-screen p-8">
    <div class="max-w-4xl mx-auto bg-white rounded-lg shadow-md p-6">
        <h1 class="text-3xl font-bold mb-8 text-center">Virtual Try-On</h1>

        <!-- Backend Connection Status -->
        <div id="backendStatus" class="mb-4 text-center">
            <p class="text-sm px-4 py-2 rounded bg-gray-100">
                Checking backend connection...
            </p>
        </div>

        <div id="status" class="mb-4 hidden">
            <p class="text-center text-sm px-4 py-2 rounded"></p>
        </div>

        <form id="tryonForm" class="space-y-6">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <!-- Person Image Upload -->
                <div class="space-y-2">
                    <label class="block text-sm font-medium text-gray-700">Person Image</label>
                    <input type="file" name="person_image" accept="image/*" required
                           class="w-full border border-gray-300 rounded-md p-2">
                    <img id="personPreview" class="hidden max-h-64 mx-auto">
                </div>

                <!-- Garment Image Upload -->
                <div class="space-y-2">
                    <label class="block text-sm font-medium text-gray-700">Garment Image</label>
                    <input type="file" name="garment_image" accept="image/*" required
                           class="w-full border border-gray-300 rounded-md p-2">
                    <img id="garmentPreview" class="hidden max-h-64 mx-auto">
                </div>
            </div>

            <!-- Parameters -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div class="space-y-2">
                    <label class="block text-sm font-medium text-gray-700">Steps (20-100)</label>
                    <input type="number" name="steps" value="50" min="20" max="100"
                           class="w-full border border-gray-300 rounded-md p-2">
                </div>

                <div class="space-y-2">
                    <label class="block text-sm font-medium text-gray-700">CFG Scale (1-10)</label>
                    <input type="number" name="cfg" value="2.5" min="1" max="10" step="0.1"
                           class="w-full border border-gray-300 rounded-md p-2">
                </div>
            </div>

            <button type="submit" 
                    class="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700">
                Generate Try-On
            </button>
        </form>

        <!-- Result Display -->
        <div id="result" class="mt-8 hidden">
            <h2 class="text-xl font-semibold mb-4">Result</h2>
            <img id="resultImage" class="max-w-full mx-auto rounded-lg shadow-lg">
            <div class="mt-4 flex justify-center">
                <a id="downloadLink" download="result.png" 
                   class="bg-green-600 text-white py-2 px-4 rounded-md hover:bg-green-700">
                    Download Result
                </a>
            </div>
        </div>

        <!-- Loading Indicator -->
        <div id="loading" class="hidden mt-8 text-center">
            <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p class="mt-4 text-gray-600">Processing your request... This may take a few minutes.</p>
        </div>
    </div>

    <script>
        // Get backend URL from server configuration
        const backendUrl = '{{ backend_url }}';
        const backendStatus = document.getElementById('backendStatus');
        const statusDiv = document.getElementById('status');

        // Check backend connection
        async function checkBackend() {
            try {
                const response = await fetch(`${backendUrl}/test`);
                const data = await response.json();

                backendStatus.innerHTML = `
                    <p class="${data.comfyui_accessible ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'} 
                              text-sm px-4 py-2 rounded">
                        Backend Status: ${data.comfyui_accessible ? 'Connected' : 'Disconnected'}
                    </p>`;
            } catch (error) {
                backendStatus.innerHTML = `
                    <p class="bg-red-100 text-red-700 text-sm px-4 py-2 rounded">
                        Backend Status: Error - ${error.message}
                    </p>`;
            }
        }

        // Check backend status on page load
        checkBackend();
        // Recheck every 30 seconds
        setInterval(checkBackend, 30000);

        function showStatus(message, type = 'info') {
            statusDiv.classList.remove('hidden');
            const p = statusDiv.querySelector('p');
            p.textContent = message;
            p.className = `text-center text-sm px-4 py-2 rounded ${
                type === 'error' ? 'bg-red-100 text-red-700' :
                type === 'success' ? 'bg-green-100 text-green-700' :
                'bg-blue-100 text-blue-700'
            }`;
        }

        function hideStatus() {
            statusDiv.classList.add('hidden');
        }

        // Preview uploaded images
        function previewImage(input, previewId) {
            const preview = document.getElementById(previewId);
            const file = input.files[0];

            if (file) {
                if (!['image/jpeg', 'image/png'].includes(file.type)) {
                    showStatus('Please upload only JPG or PNG images', 'error');
                    input.value = '';
                    preview.classList.add('hidden');
                    return;
                }

                const reader = new FileReader();
                reader.onload = function(e) {
                    preview.src = e.target.result;
                    preview.classList.remove('hidden');
                }
                reader.readAsDataURL(file);
            }
        }

        // Handle form submission
        document.getElementById('tryonForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            hideStatus();

            const formData = new FormData(e.target);
            const loading = document.getElementById('loading');
            const result = document.getElementById('result');
            const resultImage = document.getElementById('resultImage');
            const downloadLink = document.getElementById('downloadLink');

            try {
                loading.classList.remove('hidden');
                result.classList.add('hidden');

                // Upload images
                const uploadResponse = await fetch(`${backendUrl}/api/upload`, {
                    method: 'POST',
                    body: formData
                });

                const uploadData = await uploadResponse.json();
                if (!uploadResponse.ok) throw new Error(uploadData.error || 'Failed to upload images');

                // Generate try-on
                const generateResponse = await fetch(`${backendUrl}/api/generate`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        person_image: uploadData.person_image,
                        garment_image: uploadData.garment_image,
                        steps: formData.get('steps'),
                        cfg: formData.get('cfg')
                    })
                });

                const generateData = await generateResponse.json();
                if (!generateResponse.ok) throw new Error(generateData.error || 'Generation failed');

                // Get result image
                const imageResponse = await fetch(`${backendUrl}/api/result/${generateData.image}`);
                if (!imageResponse.ok) throw new Error('Failed to get result image');

                const blob = await imageResponse.blob();
                const imageUrl = URL.createObjectURL(blob);
                resultImage.src = imageUrl;
                downloadLink.href = imageUrl;
                downloadLink.download = generateData.image;
                result.classList.remove('hidden');
                showStatus('Generation completed successfully!', 'success');

            } catch (error) {
                showStatus(error.message, 'error');
            } finally {
                loading.classList.add('hidden');
            }
        });

        // Setup image preview handlers
        document.querySelector('input[name="person_image"]')
            .addEventListener('change', e => previewImage(e.target, 'personPreview'));
        document.querySelector('input[name="garment_image"]')
            .addEventListener('change', e => previewImage(e.target, 'garmentPreview'));
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Render the main page with the backend URL from config"""
    return render_template_string(
        HTML_TEMPLATE, 
        backend_url=Config.LOCAL_BACKEND_URL
    )

@app.route('/api/test', methods=['GET'])
def test():
    """Test endpoint to check backend status"""
    try:
        response = requests.get(
            f"{Config.LOCAL_BACKEND_URL}/test",
            timeout=Config.REQUEST_TIMEOUT
        )
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "comfyui_accessible": False
        })

@app.route('/api/upload', methods=['POST'])
def upload():
    """Forward upload request to local backend"""
    try:
        response = requests.post(
            f"{Config.LOCAL_BACKEND_URL}/upload",
            files={
                'person_image': request.files['person_image'],
                'garment_image': request.files['garment_image']
            },
            timeout=Config.REQUEST_TIMEOUT
        )
        return jsonify(response.json()), response.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate', methods=['POST'])
def generate():
    """Forward generation request to local backend"""
    try:
        response = requests.post(
            f"{Config.LOCAL_BACKEND_URL}/generate",
            json=request.json,
            timeout=Config.REQUEST_TIMEOUT
        )
        return jsonify(response.json()), response.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/result/<filename>', methods=['GET'])
def get_result(filename):
    """Forward result request to local backend"""
    try:
        response = requests.get(
            f"{Config.LOCAL_BACKEND_URL}/result/{filename}",
            timeout=Config.REQUEST_TIMEOUT
        )
        return response.content, response.status_code, {
            'Content-Type': response.headers.get('content-type', 'image/png')
        }
    except requests.exceptions.RequestException as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port)

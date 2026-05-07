function setupCamera(root) {
  const video = root.querySelector('#camera-video');
  const canvas = root.querySelector('#camera-canvas');
  const startButton = root.querySelector('[data-camera-start]');
  const captureButton = root.querySelector('[data-camera-capture]');
  const status = root.querySelector('[data-camera-status]');
  const faceInput = document.querySelector('#face-data');
  let stream = null;

  async function startCamera() {
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false
      });
      video.srcObject = stream;
      status.textContent = 'Camera started. Center your face and capture.';
    } catch (error) {
      status.textContent = 'Could not access camera: ' + error.message;
    }
  }

  function captureFace() {
    if (!stream) {
      status.textContent = 'Start the camera before capturing.';
      return;
    }
    const width = video.videoWidth || 640;
    const height = video.videoHeight || 480;
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext('2d');
    context.drawImage(video, 0, 0, width, height);
    faceInput.value = canvas.toDataURL('image/jpeg', 0.75);
    status.textContent = 'Face image captured. You can submit the form now.';
  }

  startButton.addEventListener('click', startCamera);
  captureButton.addEventListener('click', captureFace);
}

document.querySelectorAll('[data-camera-root]').forEach(setupCamera);

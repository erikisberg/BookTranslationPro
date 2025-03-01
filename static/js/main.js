document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.getElementById('uploadForm');
    const uploadButton = document.getElementById('uploadButton');
    const buttonText = uploadButton.querySelector('.button-text');
    const spinner = uploadButton.querySelector('.spinner-border');
    const progressContainer = document.getElementById('progressContainer');
    const progressBar = document.querySelector('.progress-bar');
    const statusText = document.getElementById('statusText');
    const errorContainer = document.getElementById('errorContainer');

    uploadForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const fileInput = document.getElementById('pdfFile');
        const file = fileInput.files[0];
        
        if (!file) {
            showError('Please select a PDF file.');
            return;
        }
        
        if (!file.name.toLowerCase().endsWith('.pdf')) {
            showError('Please upload a PDF file.');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        try {
            // Show loading state
            buttonText.textContent = 'Processing...';
            spinner.classList.remove('d-none');
            uploadButton.disabled = true;
            progressContainer.classList.remove('d-none');
            errorContainer.classList.add('d-none');
            
            // Simulate progress for better UX
            let progress = 0;
            const progressInterval = setInterval(() => {
                progress += 5;
                if (progress <= 90) {
                    progressBar.style.width = `${progress}%`;
                    statusText.textContent = `Processing page...`;
                }
            }, 1000);

            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            clearInterval(progressInterval);

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Upload failed');
            }

            // Handle successful response
            progressBar.style.width = '100%';
            statusText.textContent = 'Translation complete!';

            // Trigger download
            const blob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = downloadUrl;
            a.download = 'translated_' + file.name;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(downloadUrl);
            document.body.removeChild(a);

            // Reset form after 2 seconds
            setTimeout(resetForm, 2000);

        } catch (error) {
            showError(error.message);
            resetForm();
        }
    });

    function showError(message) {
        errorContainer.textContent = message;
        errorContainer.classList.remove('d-none');
    }

    function resetForm() {
        buttonText.textContent = 'Translate PDF';
        spinner.classList.add('d-none');
        uploadButton.disabled = false;
        progressContainer.classList.add('d-none');
        progressBar.style.width = '0%';
        statusText.textContent = '';
        uploadForm.reset();
    }
});

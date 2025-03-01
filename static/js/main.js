document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.getElementById('uploadForm');
    const progressContainer = document.getElementById('progressContainer');
    const progressBar = document.querySelector('.progress-bar');
    const statusText = document.getElementById('statusText');
    const errorContainer = document.getElementById('errorContainer');

    if (!uploadForm) {
        console.warn('Upload form not found on this page');
        return;
    }

    const uploadButton = uploadForm.querySelector('button[type="submit"]');
    const buttonText = uploadButton ? uploadButton.querySelector('.button-text') : null;
    const spinner = uploadButton ? uploadButton.querySelector('.spinner-border') : null;

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
            if (buttonText) buttonText.textContent = 'Processing...';
            if (spinner) spinner.classList.remove('d-none');
            if (uploadButton) uploadButton.disabled = true;
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
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            clearInterval(progressInterval);

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Upload failed');
            }

            // Handle successful response
            progressBar.style.width = '100%';
            statusText.textContent = 'Translation complete! Redirecting to review...';

            // Redirect to review page
            if (data.redirect) {
                window.location.href = data.redirect;
            }

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
        if (buttonText) buttonText.textContent = 'Translate PDF';
        if (spinner) spinner.classList.add('d-none');
        if (uploadButton) uploadButton.disabled = false;
        progressContainer.classList.add('d-none');
        progressBar.style.width = '0%';
        statusText.textContent = '';
        uploadForm.reset();
    }

    // Handle review form submission
    const reviewForm = document.querySelector('form[action="/save-reviews"]');
    if (reviewForm) {
        reviewForm.addEventListener('submit', async function(e) {
            e.preventDefault();

            try {
                const response = await fetch('/save-reviews', {
                    method: 'POST',
                    body: new FormData(this),
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || 'Failed to save reviews');
                }

                const data = await response.json();
                if (data.redirect) {
                    window.location.href = data.redirect;
                }

            } catch (error) {
                alert('Error saving reviews: ' + error.message);
            }
        });
    }
});
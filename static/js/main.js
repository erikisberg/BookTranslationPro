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

    async function handleResponse(response) {
        console.log('Response headers:', Object.fromEntries(response.headers.entries()));
        console.log('Response status:', response.status);
        console.log('Response content type:', response.headers.get('content-type'));

        try {
            const responseText = await response.text();
            console.log('Raw response text:', responseText);

            let data;
            try {
                data = JSON.parse(responseText);
                console.log('Parsed response data:', data);
            } catch (parseError) {
                console.error('JSON parsing error:', parseError);
                console.error('Failed to parse response text:', responseText);
                throw new Error('Server returned invalid JSON response');
            }

            if (!response.ok) {
                throw new Error(data.error || 'Operation failed');
            }
            return data;
        } catch (error) {
            console.error('Error handling response:', error);
            throw error;
        }
    }

    uploadForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        console.log('Starting file upload process');

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
        console.log('Form data created with file:', file.name);

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

            console.log('Sending upload request...');
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'application/json'
                }
            });
            console.log('Received response from server');

            clearInterval(progressInterval);
            const data = await handleResponse(response);

            // Handle successful response
            console.log('Upload successful, processing response');
            progressBar.style.width = '100%';
            statusText.textContent = 'Translation complete! Redirecting to review...';

            // Redirect to review page
            if (data.redirect) {
                console.log('Redirecting to:', data.redirect);
                window.location.href = data.redirect;
            }

        } catch (error) {
            console.error('Upload process error:', error);
            showError(error.message);
            resetForm();
        }
    });

    function showError(message) {
        console.error('Showing error:', message);
        errorContainer.textContent = message;
        errorContainer.classList.remove('d-none');
        if (progressContainer) progressContainer.classList.add('d-none');
    }

    function resetForm() {
        console.log('Resetting form');
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
            console.log('Starting review form submission');

            try {
                const response = await fetch('/save-reviews', {
                    method: 'POST',
                    body: new FormData(this),
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'Accept': 'application/json'
                    }
                });
                console.log('Received review form response');

                const data = await handleResponse(response);
                if (data.redirect) {
                    console.log('Redirecting to:', data.redirect);
                    window.location.href = data.redirect;
                }

            } catch (error) {
                console.error('Review submission error:', error);
                alert('Error saving reviews: ' + error.message);
            }
        });
    }
});
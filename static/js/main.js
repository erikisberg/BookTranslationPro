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
        console.log('Response status:', response.status);
        console.log('Response headers:', Object.fromEntries(response.headers.entries()));
        console.log('Response content type:', response.headers.get('content-type'));

        if (!response.ok) {
            // Try to get error details from response
            try {
                if (response.headers.get('content-type')?.includes('application/json')) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || 'Operation failed');
                } else {
                    const errorText = await response.text();
                    console.error('Non-JSON error response:', errorText);
                    throw new Error('Server error occurred');
                }
            } catch (parseError) {
                console.error('Error parsing error response:', parseError);
                throw new Error('Server error occurred');
            }
        }

        try {
            const data = await response.json();
            console.log('Response data:', data);
            return data;
        } catch (error) {
            console.error('Error parsing JSON response:', error);
            throw new Error('Invalid server response');
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
            setLoading(true);
            errorContainer.classList.add('d-none');
            progressContainer.classList.remove('d-none');
            progressBar.style.width = '0%';
            statusText.textContent = 'Uploading file...';

            // Simulate progress for better UX
            let progress = 0;
            const progressInterval = setInterval(() => {
                progress += 5;
                if (progress <= 90) {
                    progressBar.style.width = `${progress}%`;
                    if (progress < 30) {
                        statusText.textContent = 'Uploading file...';
                    } else if (progress < 60) {
                        statusText.textContent = 'Extracting text...';
                    } else {
                        statusText.textContent = 'Processing translation...';
                    }
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

            console.log('Upload successful, processing response');
            progressBar.style.width = '100%';
            statusText.textContent = 'Translation complete! Redirecting to review...';

            if (data.redirect) {
                console.log('Redirecting to:', data.redirect);
                window.location.href = data.redirect;
            }

        } catch (error) {
            console.error('Upload process error:', error);
            showError(error.message || 'Failed to process file');
            resetForm();
        }
    });

    function showError(message) {
        console.error('Showing error:', message);
        errorContainer.textContent = message;
        errorContainer.classList.remove('d-none');
        progressContainer.classList.add('d-none');
    }

    function setLoading(isLoading) {
        if (buttonText) buttonText.textContent = isLoading ? 'Processing...' : 'Translate PDF';
        if (spinner) spinner.classList.toggle('d-none', !isLoading);
        if (uploadButton) uploadButton.disabled = isLoading;
    }

    function resetForm() {
        console.log('Resetting form');
        setLoading(false);
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
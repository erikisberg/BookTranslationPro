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
            statusText.textContent = 'Starting upload...';

            const response = await fetch('/upload', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (!response.ok || !response.headers.get('content-type').includes('text/event-stream')) {
                // Handle non-streaming error responses
                const errorText = await response.text();
                console.error('Upload error response:', errorText);
                throw new Error('Failed to process file');
            }

            const reader = response.body.getReader();
            let translations = [];

            while (true) {
                const {value, done} = await reader.read();
                if (done) break;

                const chunk = new TextDecoder().decode(value);
                const events = chunk.split('\n\n').filter(Boolean);

                for (const event of events) {
                    if (!event.startsWith('data: ')) continue;
                    const jsonStr = event.slice(6);
                    try {
                        const data = JSON.parse(jsonStr);
                        console.log('Stream data:', data);

                        if (data.status === 'error') {
                            throw new Error(data.message);
                        }

                        // Update progress based on status
                        if (data.status === 'started') {
                            statusText.textContent = 'Processing PDF...';
                        } else if (data.status === 'extracting') {
                            progressBar.style.width = `${(data.page / data.total_pages * 30)}%`;
                            statusText.textContent = `Extracting text from page ${data.page}...`;
                        } else if (data.status === 'translating') {
                            progressBar.style.width = `${(data.page / data.total_pages * 60)}%`;
                            statusText.textContent = `Translating page ${data.page}...`;
                        } else if (data.status === 'reviewing') {
                            progressBar.style.width = `${(data.page / data.total_pages * 90)}%`;
                            statusText.textContent = `Reviewing translation of page ${data.page}...`;
                        } else if (data.status === 'completed') {
                            translations = data.translations;
                            progressBar.style.width = '100%';
                            statusText.textContent = 'Processing complete!';
                            // Store translations in session and redirect
                            const saveResponse = await fetch('/save-translations', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'X-Requested-With': 'XMLHttpRequest'
                                },
                                body: JSON.stringify({translations})
                            });
                            if (saveResponse.ok) {
                                window.location.href = '/review';
                            }
                        }
                    } catch (error) {
                        console.error('Error processing stream data:', error);
                        throw error;
                    }
                }
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
});
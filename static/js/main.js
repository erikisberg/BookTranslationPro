document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.getElementById('uploadForm');
    const progressContainer = document.getElementById('progressContainer');
    const progressBar = document.querySelector('.progress-bar');
    const statusText = document.getElementById('statusText');
    const errorContainer = document.getElementById('errorContainer');
    
    // Initialize PostHog tracking
    initPostHogTracking();
    
    // Initialize bootstrap tooltips
    if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
    
    // Initialize PostHog client-side tracking
    function initPostHogTracking() {
        // Check if PostHog is available (initialized in base.html)
        if (typeof posthog !== 'undefined') {
            
            // Track button clicks
            document.addEventListener('click', function(e) {
                // Check if the clicked element is a button or has data-track attribute
                if (e.target.matches('button, [data-track]')) {
                    const trackEvent = e.target.dataset.track || e.target.textContent.trim();
                    if (trackEvent) {
                        posthog.capture('button_clicked', {
                            button_text: e.target.textContent.trim(),
                            event_name: trackEvent,
                            page_path: window.location.pathname
                        });
                    }
                }
            });
            
            // Track form submissions
            document.querySelectorAll('form').forEach(form => {
                form.addEventListener('submit', function(e) {
                    const formId = this.id || this.getAttribute('name') || 'unknown_form';
                    const formAction = this.getAttribute('action') || window.location.pathname;
                    
                    posthog.capture('form_submitted', {
                        form_id: formId,
                        form_action: formAction,
                        page_path: window.location.pathname
                    });
                });
            });
            
            // Track file uploads when they're selected (not just when form is submitted)
            document.querySelectorAll('input[type="file"]').forEach(input => {
                input.addEventListener('change', function(e) {
                    if (this.files && this.files.length > 0) {
                        const fileData = Array.from(this.files).map(file => ({
                            name: file.name,
                            size: file.size,
                            type: file.type
                        }));
                        
                        posthog.capture('file_selected', {
                            file_count: this.files.length,
                            files: fileData,
                            input_name: this.name || 'unknown',
                            page_path: window.location.pathname
                        });
                    }
                });
            });
        }
    }

    // Handle review page features
    initReviewPageFeatures();

    if (!uploadForm) {
        console.warn('Upload form not found on this page');
        return;
    }

    const uploadButton = uploadForm.querySelector('button[type="submit"]');
    const buttonText = uploadButton ? uploadButton.querySelector('.button-text') : null;
    const spinner = uploadButton ? uploadButton.querySelector('.spinner-border') : null;

    async function handleResponse(response) {
        // Check if response is JSON
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            throw new Error('Server error: Invalid response format');
        }

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'Operation failed');
        }
        return data;
    }

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
        
        // Add the skipOpenAI checkbox value
        const skipOpenAI = document.getElementById('skipOpenAI').checked;
        formData.append('skipOpenAI', skipOpenAI);
        
        // Add language options
        const sourceLanguage = document.getElementById('sourceLanguage').value;
        const targetLanguage = document.getElementById('targetLanguage').value;
        formData.append('sourceLanguage', sourceLanguage);
        formData.append('targetLanguage', targetLanguage);
        
        // Add selected assistant
        const assistantId = document.getElementById('assistantSelect').value;
        formData.append('assistantId', assistantId);

        try {
            // Show loading state
            if (buttonText) buttonText.textContent = 'Processing...';
            if (spinner) spinner.classList.remove('d-none');
            if (uploadButton) uploadButton.disabled = true;
            progressContainer.classList.remove('d-none');
            errorContainer.classList.add('d-none');

            // Simulate progress with more detailed messages for better UX
            let progress = 0;
            let progressSteps;
            
            if (skipOpenAI) {
                // Shorter progress sequence when skipping OpenAI
                progressSteps = [
                    {progress: 15, message: "Extraherar text från PDF..."},
                    {progress: 35, message: "Förbereder sidor för översättning..."},
                    {progress: 55, message: "Översätter med DeepL..."},
                    {progress: 80, message: "Slutför översättning..."},
                    {progress: 90, message: "Nästan klar..."}
                ];
            } else {
                // Full progress sequence with OpenAI review
                progressSteps = [
                    {progress: 10, message: "Extraherar text från PDF..."},
                    {progress: 25, message: "Förbereder sidor för översättning..."},
                    {progress: 40, message: "Översätter med DeepL..."},
                    {progress: 60, message: "Granskar översättning med OpenAI..."},
                    {progress: 80, message: "Slutför översättning..."},
                    {progress: 90, message: "Nästan klar..."}
                ];
            }
            
            let stepIndex = 0;
            const progressInterval = setInterval(() => {
                if (stepIndex < progressSteps.length) {
                    const step = progressSteps[stepIndex];
                    progress = step.progress;
                    progressBar.style.width = `${progress}%`;
                    statusText.textContent = step.message;
                    stepIndex++;
                }
            }, 2000);

            const response = await fetch('/upload', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'application/json'
                }
            });

            clearInterval(progressInterval);
            const data = await handleResponse(response);

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
        if (progressContainer) progressContainer.classList.add('d-none');
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
                const saveBtn = this.querySelector('button[type="submit"]');
                const originalText = saveBtn.textContent;
                saveBtn.textContent = 'Sparar...';
                saveBtn.disabled = true;

                const response = await fetch('/save-reviews', {
                    method: 'POST',
                    body: new FormData(this),
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'Accept': 'application/json'
                    }
                });

                const data = await handleResponse(response);
                
                saveBtn.textContent = 'Sparat!';
                setTimeout(() => {
                    saveBtn.textContent = originalText;
                    saveBtn.disabled = false;
                }, 2000);
                
                if (data.redirect) {
                    // No need to redirect, just show success
                    // window.location.href = data.redirect;
                }

            } catch (error) {
                alert('Fel vid sparande av översättningar: ' + error.message);
            }
        });
    }
    
    // Initialize review page features
    function initReviewPageFeatures() {
        // Get all preview toggle buttons
        const previewButtons = document.querySelectorAll('.toggle-preview');
        const fullscreenButtons = document.querySelectorAll('.fullscreen-btn');
        const textareas = document.querySelectorAll('.translation-textarea');
        
        // Add listeners to all textareas for real-time preview
        textareas.forEach(textarea => {
            textarea.addEventListener('input', function() {
                const id = this.id.split('_')[1];
                updatePreview(id, this.value);
            });
        });
        
        // Add listeners to preview toggle buttons
        previewButtons.forEach(button => {
            button.addEventListener('click', function() {
                const id = this.dataset.id;
                const previewContainer = document.getElementById(`preview_${id}`);
                const diffView = document.getElementById(`diff_${id}`);
                
                // Toggle preview visibility
                if (previewContainer.classList.contains('d-none')) {
                    previewContainer.classList.remove('d-none');
                    diffView.classList.remove('d-none');
                    this.textContent = 'Dölj förhandsvisning';
                    
                    // Update preview content
                    const textarea = document.getElementById(`translation_${id}`);
                    updatePreview(id, textarea.value);
                } else {
                    previewContainer.classList.add('d-none');
                    diffView.classList.add('d-none');
                    this.textContent = 'Förhandsvisning';
                }
            });
        });
        
        // Add listeners to fullscreen buttons
        fullscreenButtons.forEach(button => {
            button.addEventListener('click', function() {
                const id = this.dataset.id;
                const card = this.closest('.translation-card');
                
                if (card.classList.contains('fullscreen-mode')) {
                    card.classList.remove('fullscreen-mode');
                    this.innerHTML = '<i class="bi bi-arrows-fullscreen"></i> Fullscreen';
                } else {
                    card.classList.add('fullscreen-mode');
                    this.innerHTML = '<i class="bi bi-fullscreen-exit"></i> Exit Fullscreen';
                    
                    // Make sure preview is visible in fullscreen
                    const previewContainer = document.getElementById(`preview_${id}`);
                    const diffView = document.getElementById(`diff_${id}`);
                    const previewButton = card.querySelector('.toggle-preview');
                    
                    if (previewContainer.classList.contains('d-none')) {
                        previewContainer.classList.remove('d-none');
                        diffView.classList.remove('d-none');
                        previewButton.textContent = 'Hide Preview';
                        
                        // Update preview content
                        const textarea = document.getElementById(`translation_${id}`);
                        updatePreview(id, textarea.value);
                    }
                }
            });
        });
    }
    
    // Function to update the preview content
    function updatePreview(id, text) {
        const previewContent = document.querySelector(`#preview_${id} .preview-content`);
        const diffContent = document.querySelector(`#diff_${id} .diff-content`);
        const originalText = document.getElementById(`original_${id}`).textContent;
        
        if (previewContent) {
            // Format and display the translation preview
            previewContent.textContent = text;
            
            // Create a simple diff visualization
            const diffHtml = createSimpleDiff(originalText, text);
            diffContent.innerHTML = diffHtml;
        }
    }
    
    // Simple function to highlight differences between original and translated text
    function createSimpleDiff(original, translated) {
        // Split into paragraphs
        const origParagraphs = original.split('\n').filter(p => p.trim());
        const transParagraphs = translated.split('\n').filter(p => p.trim());
        
        let diffHtml = '';
        
        // Compare paragraph counts
        if (origParagraphs.length !== transParagraphs.length) {
            diffHtml += `<div class="alert alert-warning">
                Original has ${origParagraphs.length} paragraphs, translation has ${transParagraphs.length}.
            </div>`;
        }
        
        // Create paragraph comparison
        const maxParagraphs = Math.max(origParagraphs.length, transParagraphs.length);
        for (let i = 0; i < maxParagraphs; i++) {
            diffHtml += '<div class="diff-paragraph mb-3">';
            
            // Check if paragraphs exist
            if (i < origParagraphs.length && i < transParagraphs.length) {
                // Both paragraphs exist, compare word counts
                const origWords = origParagraphs[i].split(/\s+/).length;
                const transWords = transParagraphs[i].split(/\s+/).length;
                
                diffHtml += `<div class="paragraph-info mb-2">
                    <span class="badge ${Math.abs(origWords - transWords) > 5 ? 'bg-warning' : 'bg-success'}">
                        Original: ${origWords} words / Translation: ${transWords} words
                    </span>
                </div>`;
            } else {
                // Missing paragraph in one version
                diffHtml += `<div class="alert alert-danger">
                    Paragraph mismatch: ${i < origParagraphs.length ? 'Missing in translation' : 'Missing in original'}
                </div>`;
            }
            
            diffHtml += '</div>';
        }
        
        return diffHtml;
    }
});
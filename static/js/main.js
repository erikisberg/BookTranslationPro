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
        const files = fileInput.files;

        if (!files || files.length === 0) {
            showError('Välj minst en fil att översätta.');
            return;
        }
        
        // Check if all file extensions are supported
        const allowedExtensions = ['.pdf', '.docx', '.doc', '.txt', '.rtf', '.odt'];
        let invalidFiles = [];
        
        for (let i = 0; i < files.length; i++) {
            const fileExtension = files[i].name.substring(files[i].name.lastIndexOf('.')).toLowerCase();
            if (!allowedExtensions.includes(fileExtension)) {
                invalidFiles.push(files[i].name);
            }
        }
        
        if (invalidFiles.length > 0) {
            showError(`Följande filer har format som inte stöds: ${invalidFiles.join(', ')}. Använd PDF, Word (DOCX/DOC), text (TXT), RTF eller ODT.`);
            return;
        }

        // Create the FormData with all files
        const formData = new FormData();
        
        // Show a batch indicator if multiple files
        if (files.length > 1) {
            statusText.textContent = `Förbereder ${files.length} filer för översättning...`;
            progressContainer.classList.remove('d-none');
            progressBar.style.width = '5%';
        }
        
        // Add all files to the form data
        for (let i = 0; i < files.length; i++) {
            formData.append('files[]', files[i]);
        }
        
        // Add the skipOpenAI checkbox value
        const skipOpenAI = document.getElementById('skipOpenAI').checked;
        formData.append('skipOpenAI', skipOpenAI);
        
        // Add the useCache checkbox value
        const useCache = document.getElementById('useCache').checked;
        formData.append('useCache', useCache);
        
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
            
            // Create messages based on multiple files or single file
            const fileCount = files.length;
            let extractMessage = fileCount > 1 
                ? `Extraherar text från ${fileCount} dokument...` 
                : "Extraherar text från dokument...";
            
            // For single file, be more specific about file type
            if (fileCount === 1) {
                const fileExtension = files[0].name.substring(files[0].name.lastIndexOf('.')).toLowerCase();
                const isWord = ['.docx', '.doc'].includes(fileExtension);
                const isText = ['.txt', '.rtf', '.odt'].includes(fileExtension);
                const isPdf = fileExtension === '.pdf';
                
                if (isPdf) extractMessage = "Extraherar text från PDF...";
                if (isWord) extractMessage = "Extraherar text från Word-dokument...";
                if (isText) extractMessage = "Bearbetar textfil...";
            }
            
            if (skipOpenAI) {
                // Shorter progress sequence when skipping OpenAI
                progressSteps = [
                    {progress: 15, message: extractMessage},
                    {progress: 35, message: fileCount > 1 ? "Förbereder batch för översättning..." : "Förbereder innehåll för översättning..."},
                    {progress: 55, message: "Översätter med DeepL..."},
                    {progress: 80, message: "Slutför översättning..."},
                    {progress: 90, message: "Nästan klar..."}
                ];
            } else {
                // Full progress sequence with OpenAI review
                progressSteps = [
                    {progress: 10, message: extractMessage},
                    {progress: 25, message: fileCount > 1 ? "Förbereder batch för översättning..." : "Förbereder innehåll för översättning..."},
                    {progress: 40, message: "Översätter med DeepL..."},
                    {progress: 60, message: "Granskar översättningar med OpenAI..."},
                    {progress: 80, message: "Slutför batch-översättning..."},
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
            // Check if the clicked button is "Save to database"
            const clickedButton = e.submitter;
            const isSaveToDb = clickedButton && clickedButton.name === 'save_to_db' && clickedButton.value === 'yes';
            
            // If saving to database, let the form submit normally for server-side redirect
            if (isSaveToDb) {
                // Show saving indicator
                clickedButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Sparar...';
                clickedButton.disabled = true;
                
                // Let the normal form submission happen
                return true;
            }
            
            // For regular saves, use AJAX
            e.preventDefault();

            try {
                const saveBtn = clickedButton || this.querySelector('button[name="action"]');
                const originalHTML = saveBtn.innerHTML;
                saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Sparar...';
                saveBtn.disabled = true;
                
                // Disable all buttons during save
                this.querySelectorAll('button').forEach(btn => {
                    if (btn !== saveBtn) btn.disabled = true;
                });

                const response = await fetch('/save-reviews', {
                    method: 'POST',
                    body: new FormData(this),
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'Accept': 'application/json'
                    }
                });

                const data = await handleResponse(response);
                
                saveBtn.innerHTML = '<i class="bi bi-check-circle"></i> Sparat!';
                
                // Re-enable buttons
                setTimeout(() => {
                    saveBtn.innerHTML = originalHTML;
                    saveBtn.disabled = false;
                    
                    this.querySelectorAll('button').forEach(btn => {
                        btn.disabled = false;
                    });
                    
                    // Show a toast or notification
                    showNotification('Ändringar sparade!', 'success');
                }, 1500);
                
                if (data.redirect && data.force_redirect) {
                    window.location.href = data.redirect;
                }

            } catch (error) {
                showNotification('Fel vid sparande: ' + error.message, 'danger');
                
                // Re-enable buttons
                this.querySelectorAll('button').forEach(btn => {
                    btn.disabled = false;
                });
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
    
    // Helper function to show notifications
    function showNotification(message, type = 'info') {
        // Check if we already have a notification container
        let notifContainer = document.getElementById('notification-container');
        
        if (!notifContainer) {
            // Create a container for notifications
            notifContainer = document.createElement('div');
            notifContainer.id = 'notification-container';
            notifContainer.style.position = 'fixed';
            notifContainer.style.top = '20px';
            notifContainer.style.right = '20px';
            notifContainer.style.zIndex = '9999';
            notifContainer.style.maxWidth = '350px';
            document.body.appendChild(notifContainer);
        }
        
        // Create the toast element
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${type} border-0 mb-2`;
        toast.role = 'alert';
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');
        
        // Toast content
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        `;
        
        // Add to container
        notifContainer.appendChild(toast);
        
        // Initialize and show using Bootstrap
        const bsToast = new bootstrap.Toast(toast, {
            autohide: true,
            delay: 3000
        });
        bsToast.show();
        
        // Remove after hiding
        toast.addEventListener('hidden.bs.toast', () => {
            toast.remove();
        });
    }
});
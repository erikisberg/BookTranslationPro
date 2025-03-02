document.addEventListener('DOMContentLoaded', function() {
    // Initialize bootstrap tooltips
    initBootstrap();
    
    // Initialize PostHog client-side tracking
    initPostHogTracking();
    
    // Initialize review page features
    initReviewPageFeatures();
    
    // Handle file upload form if it exists
    initUploadForm();
    
    /**
     * Initialize Bootstrap components
     */
    function initBootstrap() {
        // Initialize bootstrap tooltips
        if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
            try {
                const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
                tooltipTriggerList.map(function (tooltipTriggerEl) {
                    return new bootstrap.Tooltip(tooltipTriggerEl);
                });
                console.log("Bootstrap tooltips initialized");
            } catch (error) {
                console.error("Error initializing Bootstrap tooltips:", error);
            }
        }
    }
    
    /**
     * Initialize PostHog tracking
     */
    function initPostHogTracking() {
        // Check if PostHog is available (initialized in base.html)
        if (typeof posthog !== 'undefined') {
            try {
                console.log("Initializing PostHog tracking");
                
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
            } catch (error) {
                console.error("Error initializing PostHog tracking:", error);
            }
        }
    }
    
    /**
     * Initialize file upload form
     */
    function initUploadForm() {
        const uploadForm = document.getElementById('uploadForm');
        
        if (!uploadForm) {
            console.log('Upload form not found on this page');
            return;
        }
        
        console.log('Initializing upload form');
        
        const progressContainer = document.getElementById('progressContainer');
        const progressBar = document.querySelector('.progress-bar');
        const statusText = document.getElementById('statusText');
        const errorContainer = document.getElementById('errorContainer');
        const uploadButton = uploadForm.querySelector('button[type="submit"]');
        const buttonText = uploadButton ? uploadButton.querySelector('.button-text') : null;
        const spinner = uploadButton ? uploadButton.querySelector('.spinner-border') : null;
        
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
            
            // Add the skipOpenAI checkbox value if it exists
            const skipOpenAI = document.getElementById('skipOpenAI');
            if (skipOpenAI) {
                formData.append('skipOpenAI', skipOpenAI.checked);
            }
            
            // Add the useCache checkbox value if it exists
            const useCache = document.getElementById('useCache');
            if (useCache) {
                formData.append('useCache', useCache.checked);
            }
            
            // Add the smartReview checkbox value if it exists
            const smartReview = document.getElementById('smartReview');
            if (smartReview) {
                formData.append('smartReview', smartReview.checked);
            }
            
            // Add language options if they exist
            const sourceLanguage = document.getElementById('sourceLanguage');
            const targetLanguage = document.getElementById('targetLanguage');
            
            if (sourceLanguage) {
                formData.append('sourceLanguage', sourceLanguage.value);
            }
            
            if (targetLanguage) {
                formData.append('targetLanguage', targetLanguage.value);
            }
            
            // Add selected assistant if it exists
            const assistantSelect = document.getElementById('assistantSelect');
            if (assistantSelect) {
                formData.append('assistantId', assistantSelect.value);
            }
            
            try {
                // Show loading state
                if (buttonText) buttonText.textContent = 'Processing...';
                if (spinner) spinner.classList.remove('d-none');
                if (uploadButton) uploadButton.disabled = true;
                if (progressContainer) progressContainer.classList.remove('d-none');
                if (errorContainer) errorContainer.classList.add('d-none');
                
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
                
                if (skipOpenAI && skipOpenAI.checked) {
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
                
                // Check if response is JSON
                const contentType = response.headers.get('content-type');
                if (!contentType || !contentType.includes('application/json')) {
                    throw new Error('Server error: Invalid response format');
                }
                
                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.error || 'Operation failed');
                }
                
                // Handle successful response
                progressBar.style.width = '100%';
                statusText.textContent = 'Translation complete! Redirecting to review...';
                
                // Redirect to review page
                if (data.redirect) {
                    window.location.href = data.redirect;
                }
                
            } catch (error) {
                console.error("Upload error:", error);
                showError(error.message);
                resetForm();
            }
        });
        
        function showError(message) {
            if (errorContainer) {
                errorContainer.textContent = message;
                errorContainer.classList.remove('d-none');
            } else {
                alert(message);
            }
            
            if (progressContainer) progressContainer.classList.add('d-none');
        }
        
        function resetForm() {
            if (buttonText) buttonText.textContent = 'Translate PDF';
            if (spinner) spinner.classList.add('d-none');
            if (uploadButton) uploadButton.disabled = false;
            if (progressContainer) progressContainer.classList.add('d-none');
            if (progressBar) progressBar.style.width = '0%';
            if (statusText) statusText.textContent = '';
            uploadForm.reset();
        }
    }
    
    /**
     * Initialize review page features
     */
    function initReviewPageFeatures() {
        try {
            console.log("Initializing review page features");
            
            // Handle review form submission
            initReviewForm();
            
            // Initialize preview/diff features
            initPreviewFeatures();
        } catch (error) {
            console.error("Error initializing review page features:", error);
        }
    }
    
    /**
     * Initialize review form
     */
    function initReviewForm() {
        const reviewForm = document.querySelector('form[action="/save-reviews"]');
        if (!reviewForm) {
            return;
        }
        
        console.log("Initializing review form");
        
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
                
                // Check if response is JSON
                const contentType = response.headers.get('content-type');
                if (!contentType || !contentType.includes('application/json')) {
                    throw new Error('Server error: Invalid response format');
                }
                
                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.error || 'Operation failed');
                }
                
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
                console.error("Save error:", error);
                showNotification('Fel vid sparande: ' + error.message, 'danger');
                
                // Re-enable buttons
                this.querySelectorAll('button').forEach(btn => {
                    btn.disabled = false;
                });
            }
        });
    }
    
    /**
     * Initialize preview/diff features
     */
    function initPreviewFeatures() {
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
                    if (diffView) diffView.classList.remove('d-none');
                    this.textContent = 'Dölj förhandsvisning';
                    
                    // Update preview content
                    const textarea = document.getElementById(`translation_${id}`);
                    updatePreview(id, textarea.value);
                } else {
                    previewContainer.classList.add('d-none');
                    if (diffView) diffView.classList.add('d-none');
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
                    
                    if (previewContainer && previewContainer.classList.contains('d-none')) {
                        previewContainer.classList.remove('d-none');
                        if (diffView) diffView.classList.remove('d-none');
                        if (previewButton) previewButton.textContent = 'Hide Preview';
                        
                        // Update preview content
                        const textarea = document.getElementById(`translation_${id}`);
                        if (textarea) {
                            updatePreview(id, textarea.value);
                        }
                    }
                }
            });
        });
    }
    
    /**
     * Update the preview content
     */
    function updatePreview(id, text) {
        const previewContent = document.querySelector(`#preview_${id} .preview-content`);
        const diffContent = document.querySelector(`#diff_${id} .diff-content`);
        const originalText = document.getElementById(`original_${id}`);
        
        if (previewContent && originalText) {
            // Format and display the translation preview
            previewContent.textContent = text;
            
            // Create a simple diff visualization if diff content exists
            if (diffContent) {
                const diffHtml = createSimpleDiff(originalText.textContent, text);
                diffContent.innerHTML = diffHtml;
            }
        }
    }
    
    /**
     * Simple function to highlight differences between original and translated text
     */
    function createSimpleDiff(original, translated) {
        try {
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
        } catch (error) {
            console.error("Error creating diff:", error);
            return '<div class="alert alert-danger">Error creating difference view</div>';
        }
    }
    
    /**
     * Helper function to show notifications
     */
    function showNotification(message, type = 'info') {
        try {
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
            if (typeof bootstrap !== 'undefined' && bootstrap.Toast) {
                const bsToast = new bootstrap.Toast(toast, {
                    autohide: true,
                    delay: 3000
                });
                bsToast.show();
            } else {
                // Fallback if Bootstrap is not available
                toast.style.display = 'block';
                setTimeout(() => {
                    toast.remove();
                }, 3000);
            }
            
            // Remove after hiding
            toast.addEventListener('hidden.bs.toast', () => {
                toast.remove();
            });
        } catch (error) {
            console.error("Error showing notification:", error);
            // Fallback to alert
            alert(message);
        }
    }
    
    // Make showToast available globally
    window.showToast = function(message, type = 'info') {
        showNotification(message, type);
    };
    
    // Initialize document management page if relevant
    if (window.location.pathname.includes('/documents')) {
        initDocumentManagement();
    }
    
    // Initialize glossary management page if relevant
    if (window.location.pathname.includes('/glossary')) {
        initGlossaryManagement();
    }
    
    // Initialize document version management if relevant
    if (window.location.pathname.includes('/versions')) {
        initVersionManagement();
    }
    
    /**
     * Initialize document version management functionality
     */
    function initVersionManagement() {
        console.log("Initializing version management");
        
        try {
            // Initialize Bootstrap modals
            if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
                const createVersionModalEl = document.getElementById('createVersionModal');
                const restoreVersionModalEl = document.getElementById('restoreVersionModal');
                
                if (createVersionModalEl) {
                    window.createVersionModal = new bootstrap.Modal(createVersionModalEl);
                }
                
                if (restoreVersionModalEl) {
                    window.restoreVersionModal = new bootstrap.Modal(restoreVersionModalEl);
                }
            }
            
            // Initialize create new version button
            initCreateVersion();
            
            // Initialize restore version buttons
            initRestoreVersionButtons();
            
            // Initialize view mode controls if on version view page
            if (window.location.pathname.includes('view')) {
                initVirtualScrolling();
                initViewModeControls();
            }
            
        } catch (error) {
            console.error("Error initializing version management:", error);
        }
        
        /**
         * Initialize create version functionality
         */
        function initCreateVersion() {
            const createVersionBtn = document.getElementById('createVersionBtn');
            if (!createVersionBtn) return;
            
            createVersionBtn.addEventListener('click', function() {
                console.log("Create version button clicked");
                
                if (window.createVersionModal) {
                    window.createVersionModal.show();
                } else if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
                    const createVersionModalEl = document.getElementById('createVersionModal');
                    if (createVersionModalEl) {
                        const createVersionModal = new bootstrap.Modal(createVersionModalEl);
                        createVersionModal.show();
                    }
                }
            });
            
            const createVersionConfirmBtn = document.getElementById('createVersionConfirmBtn');
            if (!createVersionConfirmBtn) return;
            
            createVersionConfirmBtn.addEventListener('click', function() {
                const versionNotes = document.getElementById('versionNotes')?.value || '';
                const documentId = getDocumentIdFromURL();
                
                if (!documentId) {
                    showNotification('Could not determine document ID', 'danger');
                    return;
                }
                
                fetch(`/documents/${documentId}/versions`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify({
                        notes: versionNotes
                    })
                })
                .then(response => {
                    if (!response.ok) {
                        return response.text().then(text => {
                            console.error("Response not OK:", response.status, text);
                            throw new Error('Server error: ' + response.status);
                        });
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.success) {
                        showNotification(data.message || 'New version created successfully', 'success');
                        
                        // Close modal
                        if (window.createVersionModal) {
                            window.createVersionModal.hide();
                        }
                        
                        // Reload the page to show the new version
                        window.location.reload();
                    } else {
                        showNotification(data.message || 'Failed to create new version', 'danger');
                    }
                })
                .catch(error => {
                    console.error('Error creating version:', error);
                    showNotification('Failed to create new version: ' + error.message, 'danger');
                    
                    // Try traditional form submission as fallback
                    const form = document.createElement('form');
                    form.method = 'POST';
                    form.action = `/documents/${documentId}/versions`;
                    
                    // Add notes field
                    const notesInput = document.createElement('input');
                    notesInput.type = 'hidden';
                    notesInput.name = 'notes';
                    notesInput.value = versionNotes;
                    form.appendChild(notesInput);
                    
                    // Add to document and submit
                    document.body.appendChild(form);
                    form.submit();
                });
            });
        }
        
        /**
         * Initialize restore version buttons
         */
        function initRestoreVersionButtons() {
            document.querySelectorAll('.restore-version-btn, #restoreVersionBtn').forEach(btn => {
                if (!btn) return;
                
                btn.addEventListener('click', function(e) {
                    e.preventDefault();
                    
                    const versionId = this.getAttribute('data-id') || getVersionIdFromURL();
                    const versionNumber = this.getAttribute('data-version') || document.querySelector('.badge.bg-info')?.textContent?.replace('v', '') || '';
                    
                    if (!versionId && !window.location.pathname.includes('view')) {
                        showNotification('Could not determine version ID', 'danger');
                        return;
                    }
                    
                    // Set modal details
                    const restoreVersionId = document.getElementById('restoreVersionId');
                    if (restoreVersionId) restoreVersionId.value = versionId;
                    
                    const restoreVersionNumber = document.getElementById('restoreVersionNumber');
                    if (restoreVersionNumber) restoreVersionNumber.textContent = versionNumber;
                    
                    const restoreVersionModalLabel = document.getElementById('restoreVersionModalLabel');
                    if (restoreVersionModalLabel) restoreVersionModalLabel.textContent = `Restore Version ${versionNumber}`;
                    
                    // Show modal
                    if (window.restoreVersionModal) {
                        window.restoreVersionModal.show();
                    } else if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
                        const restoreVersionModalEl = document.getElementById('restoreVersionModal');
                        if (restoreVersionModalEl) {
                            const restoreVersionModal = new bootstrap.Modal(restoreVersionModalEl);
                            restoreVersionModal.show();
                        }
                    }
                });
            });
            
            const confirmRestoreBtn = document.getElementById('confirmRestoreBtn');
            if (!confirmRestoreBtn) return;
            
            confirmRestoreBtn.addEventListener('click', function() {
                const documentId = getDocumentIdFromURL();
                const versionId = document.getElementById('restoreVersionId')?.value || getVersionIdFromURL();
                const notes = document.getElementById('restoreNotes')?.value || '';
                
                if (!documentId || !versionId) {
                    showNotification('Missing document or version ID', 'danger');
                    return;
                }
                
                fetch(`/documents/${documentId}/versions/${versionId}/restore`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify({
                        notes: notes
                    })
                })
                .then(response => {
                    if (!response.ok) {
                        return response.text().then(text => {
                            console.error("Response not OK:", response.status, text);
                            throw new Error('Server error: ' + response.status);
                        });
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.success) {
                        showNotification(data.message || 'Version restored successfully', 'success');
                        
                        // Close modal
                        if (window.restoreVersionModal) {
                            window.restoreVersionModal.hide();
                        }
                        
                        // Redirect to document view or reload
                        if (data.document_id) {
                            window.location.href = `/documents/${data.document_id}`;
                        } else {
                            window.location.reload();
                        }
                    } else {
                        showNotification(data.message || 'Failed to restore version', 'danger');
                    }
                })
                .catch(error => {
                    console.error('Error restoring version:', error);
                    showNotification('Failed to restore version: ' + error.message, 'danger');
                    
                    // Try traditional form submission as fallback
                    const form = document.createElement('form');
                    form.method = 'POST';
                    form.action = `/documents/${documentId}/versions/${versionId}/restore`;
                    
                    // Add notes field
                    const notesInput = document.createElement('input');
                    notesInput.type = 'hidden';
                    notesInput.name = 'notes';
                    notesInput.value = notes;
                    form.appendChild(notesInput);
                    
                    // Add to document and submit
                    document.body.appendChild(form);
                    form.submit();
                });
            });
        }
        
        /**
         * Initialize view mode controls for version view
         */
        function initViewModeControls() {
            const viewSource = document.getElementById('viewSource');
            const viewTranslated = document.getElementById('viewTranslated');
            const viewSideBySide = document.getElementById('viewSideBySide');
            const sourceView = document.getElementById('sourceView');
            const translatedView = document.getElementById('translatedView');
            const sideBySideView = document.getElementById('sideBySideView');
            
            if (!viewSource || !viewTranslated || !viewSideBySide || 
                !sourceView || !translatedView || !sideBySideView) {
                return;
            }
            
            viewSource.addEventListener('change', function() {
                if (this.checked) {
                    sourceView.classList.remove('d-none');
                    translatedView.classList.add('d-none');
                    sideBySideView.classList.add('d-none');
                    
                    // Trigger virtual scroll refresh
                    setTimeout(() => {
                        if (typeof renderVisibleContent === 'function') {
                            renderVisibleContent('source');
                        }
                    }, 0);
                }
            });
            
            viewTranslated.addEventListener('change', function() {
                if (this.checked) {
                    sourceView.classList.add('d-none');
                    translatedView.classList.remove('d-none');
                    sideBySideView.classList.add('d-none');
                    
                    // Trigger virtual scroll refresh
                    setTimeout(() => {
                        if (typeof renderVisibleContent === 'function') {
                            renderVisibleContent('translated');
                        }
                    }, 0);
                }
            });
            
            viewSideBySide.addEventListener('change', function() {
                if (this.checked) {
                    sourceView.classList.add('d-none');
                    translatedView.classList.add('d-none');
                    sideBySideView.classList.remove('d-none');
                    
                    // Trigger virtual scroll refresh
                    setTimeout(() => {
                        if (typeof renderVisibleContent === 'function') {
                            renderVisibleContent('sideBySideSource');
                            renderVisibleContent('sideBySideTranslated');
                        }
                    }, 0);
                }
            });
        }
        
        /**
         * Virtual scrolling implementation for large documents
         */
        function initVirtualScrolling() {
            // Get content from hidden elements
            const sourceContentEl = document.getElementById('originalSourceContent');
            const translatedContentEl = document.getElementById('originalTranslatedContent');
            
            if (!sourceContentEl || !translatedContentEl) {
                return;
            }
            
            const sourceContent = sourceContentEl.textContent;
            const translatedContent = translatedContentEl.textContent;
            
            // Split content into paragraphs
            const sourceParagraphs = sourceContent.split('\n').filter(p => p.trim().length > 0);
            const translatedParagraphs = translatedContent.split('\n').filter(p => p.trim().length > 0);
            
            // Estimated paragraph heights - will be refined as they're rendered
            const avgLineHeight = 24; // pixels per line (estimate)
            const avgCharsPerLine = 80; // characters per line (estimate)
            
            // Calculate initial height estimates for paragraphs
            const sourceHeights = sourceParagraphs.map(p => {
                const lines = Math.max(1, Math.ceil(p.length / avgCharsPerLine));
                return lines * avgLineHeight;
            });
            
            const translatedHeights = translatedParagraphs.map(p => {
                const lines = Math.max(1, Math.ceil(p.length / avgCharsPerLine));
                return lines * avgLineHeight;
            });
            
            // Calculate total content heights
            const totalSourceHeight = sourceHeights.reduce((sum, h) => sum + h, 0);
            const totalTranslatedHeight = translatedHeights.reduce((sum, h) => sum + h, 0);
            
            // Get scroll containers and spacers
            const containers = {
                source: document.getElementById('sourceScrollContainer'),
                translated: document.getElementById('translatedScrollContainer'),
                sideBySideSource: document.getElementById('sideBySideSourceContainer'),
                sideBySideTranslated: document.getElementById('sideBySideTranslatedContainer')
            };
            
            const contentContainers = {
                source: document.getElementById('sourceContentContainer'),
                translated: document.getElementById('translatedContentContainer'),
                sideBySideSource: document.getElementById('sideBySideSourceContent'),
                sideBySideTranslated: document.getElementById('sideBySideTranslatedContent')
            };
            
            const spacers = {
                sourceTop: document.getElementById('sourceTopSpacer'),
                sourceBottom: document.getElementById('sourceBottomSpacer'),
                translatedTop: document.getElementById('translatedTopSpacer'),
                translatedBottom: document.getElementById('translatedBottomSpacer'),
                sideBySideSourceTop: document.getElementById('sideBySideSourceTopSpacer'),
                sideBySideSourceBottom: document.getElementById('sideBySideSourceBottomSpacer'),
                sideBySideTranslatedTop: document.getElementById('sideBySideTranslatedTopSpacer'),
                sideBySideTranslatedBottom: document.getElementById('sideBySideTranslatedBottomSpacer')
            };
            
            // Check if all required elements exist
            for (const key in containers) {
                if (!containers[key]) {
                    console.warn(`Virtual scrolling container '${key}' not found`);
                }
            }
            
            for (const key in contentContainers) {
                if (!contentContainers[key]) {
                    console.warn(`Content container '${key}' not found`);
                }
            }
            
            for (const key in spacers) {
                if (!spacers[key]) {
                    console.warn(`Spacer '${key}' not found`);
                }
            }
            
            // Initialize bottom spacer heights to total content height
            if (spacers.sourceBottom) spacers.sourceBottom.style.height = `${totalSourceHeight}px`;
            if (spacers.translatedBottom) spacers.translatedBottom.style.height = `${totalTranslatedHeight}px`;
            if (spacers.sideBySideSourceBottom) spacers.sideBySideSourceBottom.style.height = `${totalSourceHeight}px`;
            if (spacers.sideBySideTranslatedBottom) spacers.sideBySideTranslatedBottom.style.height = `${totalTranslatedHeight}px`;
            
            // Variables to track visible content
            let sourceVisibleRange = { start: -1, end: -1 };
            let translatedVisibleRange = { start: -1, end: -1 };
            let sideBySideSourceVisibleRange = { start: -1, end: -1 };
            let sideBySideTranslatedVisibleRange = { start: -1, end: -1 };
            
            // Debounce scroll events for better performance
            function debounce(func, wait) {
                let timeout;
                return function() {
                    const context = this;
                    const args = arguments;
                    clearTimeout(timeout);
                    timeout = setTimeout(() => func.apply(context, args), wait);
                };
            }
            
            // Expose renderVisibleContent globally for use by view control toggle
            window.renderVisibleContent = function(containerType) {
                const container = containers[containerType];
                const contentContainer = contentContainers[containerType];
                
                if (!container || !contentContainer) return;
                
                const scrollTop = container.scrollTop;
                const viewportHeight = container.clientHeight;
                const buffer = viewportHeight; // One viewport height as buffer
                
                // Determine which paragraphs to render
                const paragraphs = containerType.includes('Source') ? sourceParagraphs : translatedParagraphs;
                const heights = containerType.includes('Source') ? sourceHeights : translatedHeights;
                let visibleRange = { start: -1, end: -1 };
                
                // Calculate visible paragraph range
                let currentHeight = 0;
                for (let i = 0; i < heights.length; i++) {
                    const paraHeight = heights[i];
                    const paraTop = currentHeight;
                    const paraBottom = paraTop + paraHeight;
                    
                    if (paraBottom >= scrollTop - buffer && paraTop <= scrollTop + viewportHeight + buffer) {
                        if (visibleRange.start === -1) visibleRange.start = i;
                        visibleRange.end = i;
                    } else if (visibleRange.start !== -1 && paraTop > scrollTop + viewportHeight + buffer) {
                        // We've found our range and now found paragraphs outside it
                        break;
                    }
                    
                    currentHeight += paraHeight;
                }
                
                // Store the visible range for this container
                if (containerType === 'source') {
                    sourceVisibleRange = visibleRange;
                } else if (containerType === 'translated') {
                    translatedVisibleRange = visibleRange;
                } else if (containerType === 'sideBySideSource') {
                    sideBySideSourceVisibleRange = visibleRange;
                } else if (containerType === 'sideBySideTranslated') {
                    sideBySideTranslatedVisibleRange = visibleRange;
                }
                
                // Calculate top spacer height
                const topSpacerHeight = visibleRange.start > 0 ?
                    heights.slice(0, visibleRange.start).reduce((sum, h) => sum + h, 0) : 0;
                
                // Calculate rendered content height
                const renderedHeight = visibleRange.end >= 0 && visibleRange.start <= visibleRange.end ?
                    heights.slice(visibleRange.start, visibleRange.end + 1).reduce((sum, h) => sum + h, 0) : 0;
                
                // Update spacers
                if (containerType === 'source' && spacers.sourceTop && spacers.sourceBottom) {
                    spacers.sourceTop.style.height = `${topSpacerHeight}px`;
                    spacers.sourceBottom.style.height = `${Math.max(0, totalSourceHeight - topSpacerHeight - renderedHeight)}px`;
                } else if (containerType === 'translated' && spacers.translatedTop && spacers.translatedBottom) {
                    spacers.translatedTop.style.height = `${topSpacerHeight}px`;
                    spacers.translatedBottom.style.height = `${Math.max(0, totalTranslatedHeight - topSpacerHeight - renderedHeight)}px`;
                } else if (containerType === 'sideBySideSource' && spacers.sideBySideSourceTop && spacers.sideBySideSourceBottom) {
                    spacers.sideBySideSourceTop.style.height = `${topSpacerHeight}px`;
                    spacers.sideBySideSourceBottom.style.height = `${Math.max(0, totalSourceHeight - topSpacerHeight - renderedHeight)}px`;
                } else if (containerType === 'sideBySideTranslated' && spacers.sideBySideTranslatedTop && spacers.sideBySideTranslatedBottom) {
                    spacers.sideBySideTranslatedTop.style.height = `${topSpacerHeight}px`;
                    spacers.sideBySideTranslatedBottom.style.height = `${Math.max(0, totalTranslatedHeight - topSpacerHeight - renderedHeight)}px`;
                }
                
                // Clear and render the visible paragraphs
                contentContainer.innerHTML = '';
                if (visibleRange.start >= 0 && visibleRange.end >= visibleRange.start) {
                    for (let i = visibleRange.start; i <= visibleRange.end; i++) {
                        if (i < paragraphs.length) {
                            const para = document.createElement('div');
                            para.className = 'virtual-paragraph';
                            para.textContent = paragraphs[i];
                            para.dataset.index = i;
                            contentContainer.appendChild(para);
                            
                            // Refine height estimate based on actual rendered size
                            if (containerType === 'source' || containerType === 'sideBySideSource') {
                                sourceHeights[i] = para.offsetHeight;
                            } else {
                                translatedHeights[i] = para.offsetHeight;
                            }
                        }
                    }
                }
            };
            
            // Setup scroll event listeners
            if (containers.source) {
                containers.source.addEventListener('scroll', debounce(function() {
                    window.renderVisibleContent('source');
                }, 50));
            }
            
            if (containers.translated) {
                containers.translated.addEventListener('scroll', debounce(function() {
                    window.renderVisibleContent('translated');
                }, 50));
            }
            
            if (containers.sideBySideSource) {
                containers.sideBySideSource.addEventListener('scroll', debounce(function() {
                    window.renderVisibleContent('sideBySideSource');
                    
                    // Synchronize scrolling in side-by-side view
                    if (document.getElementById('viewSideBySide')?.checked && containers.sideBySideTranslated) {
                        const scrollPercentage = this.scrollTop / (this.scrollHeight - this.clientHeight);
                        containers.sideBySideTranslated.scrollTop = scrollPercentage * 
                            (containers.sideBySideTranslated.scrollHeight - containers.sideBySideTranslated.clientHeight);
                    }
                }, 50));
            }
            
            if (containers.sideBySideTranslated) {
                containers.sideBySideTranslated.addEventListener('scroll', debounce(function() {
                    window.renderVisibleContent('sideBySideTranslated');
                    
                    // Synchronize scrolling in side-by-side view
                    if (document.getElementById('viewSideBySide')?.checked && containers.sideBySideSource) {
                        const scrollPercentage = this.scrollTop / (this.scrollHeight - this.clientHeight);
                        containers.sideBySideSource.scrollTop = scrollPercentage * 
                            (containers.sideBySideSource.scrollHeight - containers.sideBySideSource.clientHeight);
                    }
                }, 50));
            }
            
            // Handle window resize - recalculate visible content
            window.addEventListener('resize', debounce(function() {
                const viewSource = document.getElementById('viewSource');
                const viewTranslated = document.getElementById('viewTranslated');
                
                if (!viewSource || !viewTranslated) return;
                
                const activeView = viewSource.checked ? 'source' :
                                  viewTranslated.checked ? 'translated' : 'sideBySide';
                
                if (activeView === 'source') {
                    window.renderVisibleContent('source');
                } else if (activeView === 'translated') {
                    window.renderVisibleContent('translated');
                } else {
                    window.renderVisibleContent('sideBySideSource');
                    window.renderVisibleContent('sideBySideTranslated');
                }
            }, 100));
            
            // Initial rendering for the default view (side by side)
            window.renderVisibleContent('sideBySideSource');
            window.renderVisibleContent('sideBySideTranslated');
        }
        
        /**
         * Helper function to extract document ID from URL
         */
        function getDocumentIdFromURL() {
            const matches = window.location.pathname.match(/\/documents\/([a-zA-Z0-9-]+)/);
            return matches ? matches[1] : null;
        }
        
        /**
         * Helper function to extract version ID from URL
         */
        function getVersionIdFromURL() {
            const matches = window.location.pathname.match(/\/versions\/([a-zA-Z0-9-]+)/);
            return matches ? matches[1] : null;
        }
    }
    
    /**
     * Initialize document management functionality
     */
    function initDocumentManagement() {
        console.log("Initializing document management");
        
        try {
            // Initialize modals if Bootstrap is available
            if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
                const folderModalEl = document.getElementById('folderModal');
                const moveDocumentModalEl = document.getElementById('moveDocumentModal');
                const deleteConfirmModalEl = document.getElementById('deleteConfirmModal');
                
                if (folderModalEl) {
                    window.folderModal = new bootstrap.Modal(folderModalEl);
                }
                
                if (moveDocumentModalEl) {
                    window.moveDocumentModal = new bootstrap.Modal(moveDocumentModalEl);
                }
                
                if (deleteConfirmModalEl) {
                    window.deleteConfirmModal = new bootstrap.Modal(deleteConfirmModalEl);
                }
            }
            
            // Initialize folder actions
            initFolderActions();
            
            // Initialize document actions
            initDocumentActions();
            
            // Initialize search functionality
            initSearchFunctionality();
            
        } catch (error) {
            console.error("Error initializing document management:", error);
        }
    }
    
    /**
     * Initialize folder-related actions
     */
    function initFolderActions() {
        // Create folder button
        const createFolderBtn = document.getElementById('createFolderBtn');
        if (createFolderBtn) {
            createFolderBtn.addEventListener('click', function(e) {
                e.preventDefault();
                console.log("Create folder button clicked");
                
                try {
                    const formEl = document.getElementById('newFolderForm');
                    if (formEl) {
                        formEl.reset();
                    }
                    
                    const modalLabelEl = document.getElementById('folderModalLabel');
                    if (modalLabelEl) {
                        modalLabelEl.textContent = 'Create New Folder';
                    }
                    
                    if (window.folderModal) {
                        window.folderModal.show();
                    } else {
                        console.warn("Folder modal not initialized, trying direct approach");
                        // Fallback approach: use prompt
                        const folderName = prompt('Enter folder name:');
                        if (folderName && folderName.trim()) {
                            createFolderDirectly(folderName.trim());
                        }
                    }
                } catch (error) {
                    console.error("Error showing folder modal:", error);
                    // Fallback
                    const folderName = prompt('Enter folder name:');
                    if (folderName && folderName.trim()) {
                        createFolderDirectly(folderName.trim());
                    }
                }
            });
        }
        
        // Create new folder button in modal
        const createNewFolderBtn = document.getElementById('createNewFolderBtn');
        if (createNewFolderBtn) {
            createNewFolderBtn.addEventListener('click', function() {
                console.log("Create new folder submission initiated");
                
                const nameInput = document.getElementById('newFolderName');
                const descriptionInput = document.getElementById('newFolderDescription');
                const colorInput = document.getElementById('newFolderColor');
                
                if (!nameInput || !nameInput.value.trim()) {
                    alert('Folder name is required');
                    return;
                }
                
                const name = nameInput.value.trim();
                const description = descriptionInput ? descriptionInput.value : '';
                const color = colorInput ? colorInput.value : '#3498db';
                
                createFolderDirectly(name, description, color);
            });
        }
        
        // Update folder form
        const folderForm = document.getElementById('folderForm');
        if (folderForm) {
            folderForm.addEventListener('submit', function(e) {
                e.preventDefault();
                
                const folderId = document.getElementById('folderId').value;
                const name = document.getElementById('folderName').value.trim();
                const description = document.getElementById('folderDescription').value;
                const color = document.getElementById('folderColor').value;
                
                if (!name) {
                    alert('Folder name is required');
                    return;
                }
                
                updateFolder(folderId, name, description, color);
            });
        }
        
        // Delete folder button
        const deleteFolderBtn = document.getElementById('deleteFolderBtn');
        if (deleteFolderBtn) {
            deleteFolderBtn.addEventListener('click', function() {
                const folderId = document.getElementById('folderId').value;
                const folderName = document.getElementById('folderName').value;
                
                if (!folderId) {
                    return;
                }
                
                if (window.deleteConfirmModal) {
                    try {
                        document.getElementById('deleteItemType').value = 'folder';
                        document.getElementById('deleteItemId').value = folderId;
                        document.getElementById('deleteConfirmMessage').textContent = 
                            `Are you sure you want to delete the folder "${folderName}"? This will NOT delete the documents inside.`;
                        
                        window.deleteConfirmModal.show();
                    } catch (error) {
                        console.error("Error showing delete confirmation modal:", error);
                        // Fallback
                        if (confirm(`Are you sure you want to delete the folder "${folderName}"? This will NOT delete the documents inside.`)) {
                            deleteItem('folder', folderId);
                        }
                    }
                } else {
                    // Direct confirmation if modal not available
                    if (confirm(`Are you sure you want to delete the folder "${folderName}"? This will NOT delete the documents inside.`)) {
                        deleteItem('folder', folderId);
                    }
                }
            });
        }
    }
    
    /**
     * Initialize document-related actions
     */
    function initDocumentActions() {
        // Document delete buttons
        document.querySelectorAll('.delete-document-btn').forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                
                const documentId = this.getAttribute('data-id');
                const documentTitle = this.closest('tr')?.querySelector('a')?.textContent.trim() || 'this document';
                
                if (window.deleteConfirmModal) {
                    try {
                        document.getElementById('deleteItemType').value = 'document';
                        document.getElementById('deleteItemId').value = documentId;
                        document.getElementById('deleteConfirmMessage').textContent = 
                            `Are you sure you want to delete the document "${documentTitle}"? This action cannot be undone.`;
                        
                        window.deleteConfirmModal.show();
                    } catch (error) {
                        console.error("Error showing delete confirmation modal:", error);
                        // Fallback
                        if (confirm(`Are you sure you want to delete the document "${documentTitle}"? This action cannot be undone.`)) {
                            deleteItem('document', documentId);
                        }
                    }
                } else {
                    // Direct confirmation if modal not available
                    if (confirm(`Are you sure you want to delete the document "${documentTitle}"? This action cannot be undone.`)) {
                        deleteItem('document', documentId);
                    }
                }
            });
        });
        
        // Move document buttons
        document.querySelectorAll('.move-document-btn').forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                
                const documentId = this.getAttribute('data-id');
                
                if (window.moveDocumentModal) {
                    try {
                        document.getElementById('moveDocumentId').value = documentId;
                        
                        // Pre-select current folder if we're in one
                        const currentFolderId = document.getElementById('folderId')?.value;
                        if (currentFolderId) {
                            const selectEl = document.getElementById('targetFolder');
                            for (let i = 0; i < selectEl.options.length; i++) {
                                if (selectEl.options[i].value === currentFolderId) {
                                    selectEl.options[i].disabled = true;
                                    break;
                                }
                            }
                        }
                        
                        window.moveDocumentModal.show();
                    } catch (error) {
                        console.error("Error showing move document modal:", error);
                        // Fallback
                        const folderOptions = Array.from(document.querySelectorAll('#folderList a'))
                            .map(a => {
                                if (!a.dataset.id) return null;
                                return { id: a.dataset.id, name: a.querySelector('span')?.textContent.trim() || a.textContent.trim() };
                            })
                            .filter(f => f !== null && f.id !== currentFolderId);
                        
                        let message = 'Select a folder to move to:\n';
                        folderOptions.forEach((f, i) => {
                            message += `${i + 1}. ${f.name}\n`;
                        });
                        message += `${folderOptions.length + 1}. No folder (Root)`;
                        
                        const choice = prompt(message);
                        if (choice) {
                            const index = parseInt(choice) - 1;
                            let targetFolderId = null;
                            
                            if (index >= 0 && index < folderOptions.length) {
                                targetFolderId = folderOptions[index].id;
                            } else if (index === folderOptions.length) {
                                targetFolderId = null; // Root
                            } else {
                                alert('Invalid selection');
                                return;
                            }
                            
                            moveDocument(documentId, targetFolderId);
                        }
                    }
                } else {
                    // Direct approach if modal not available
                    const targetFolderId = prompt('Enter folder ID to move to (leave blank for root):');
                    moveDocument(documentId, targetFolderId || null);
                }
            });
        });
        
        // Move document confirmation
        const moveDocumentConfirmBtn = document.getElementById('moveDocumentConfirmBtn');
        if (moveDocumentConfirmBtn) {
            moveDocumentConfirmBtn.addEventListener('click', function() {
                const documentId = document.getElementById('moveDocumentId').value;
                const targetFolderId = document.getElementById('targetFolder').value;
                
                if (!documentId) {
                    alert('Invalid document');
                    return;
                }
                
                moveDocument(documentId, targetFolderId || null);
            });
        }
        
        // Confirm delete button
        const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
        if (confirmDeleteBtn) {
            confirmDeleteBtn.addEventListener('click', function() {
                const itemType = document.getElementById('deleteItemType').value;
                const itemId = document.getElementById('deleteItemId').value;
                
                if (!itemType || !itemId) {
                    alert('Invalid delete request');
                    return;
                }
                
                deleteItem(itemType, itemId);
            });
        }
    }
    
    /**
     * Initialize search functionality
     */
    function initSearchFunctionality() {
        const searchBtn = document.getElementById('searchBtn');
        if (searchBtn) {
            searchBtn.addEventListener('click', function() {
                const searchTerm = document.getElementById('searchDocuments').value.trim();
                if (!searchTerm) {
                    return;
                }
                
                // Get current folder ID if any
                const folderId = document.getElementById('folderId')?.value;
                const searchUrl = folderId 
                    ? `/documents/folders/${folderId}?search=${encodeURIComponent(searchTerm)}`
                    : `/documents?search=${encodeURIComponent(searchTerm)}`;
                    
                window.location.href = searchUrl;
            });
        }
        
        // Also trigger search on Enter key
        const searchInput = document.getElementById('searchDocuments');
        if (searchInput) {
            searchInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    const searchBtn = document.getElementById('searchBtn');
                    if (searchBtn) searchBtn.click();
                }
            });
        }
    }
    
    /**
     * Helper functions for document management
     */
    
    // Create folder directly
    function createFolderDirectly(name, description = '', color = '#3498db') {
        fetch('/documents/folders', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json'
            },
            body: JSON.stringify({
                name: name,
                description: description,
                color: color
            })
        })
        .then(response => {
            if (!response.ok) {
                return response.text().then(text => {
                    console.error("Response not OK:", response.status, text);
                    throw new Error('Server error: ' + response.status);
                });
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                if (window.folderModal) {
                    window.folderModal.hide();
                }
                
                showNotification(data.message || 'Folder created successfully', 'success');
                
                // Redirect to the new folder
                if (data.folder && data.folder.id) {
                    window.location.href = `/documents/folders/${data.folder.id}`;
                } else {
                    window.location.reload();
                }
            } else {
                showNotification(data.message || 'Failed to create folder', 'danger');
            }
        })
        .catch(error => {
            console.error('Error creating folder:', error);
            showNotification('Failed to create folder: ' + error.message, 'danger');
        });
    }
    
    // Update folder
    function updateFolder(folderId, name, description, color) {
        fetch(`/documents/folders/${folderId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json'
            },
            body: JSON.stringify({
                name: name,
                description: description,
                color: color
            })
        })
        .then(response => {
            if (!response.ok) {
                return response.text().then(text => {
                    console.error("Response not OK:", response.status, text);
                    throw new Error('Server error: ' + response.status);
                });
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                showNotification(data.message || 'Folder updated successfully', 'success');
                window.location.reload();
            } else {
                showNotification(data.message || 'Failed to update folder', 'danger');
            }
        })
        .catch(error => {
            console.error('Error updating folder:', error);
            showNotification('Failed to update folder: ' + error.message, 'danger');
        });
    }
    
    // Move document
    function moveDocument(documentId, targetFolderId) {
        fetch(`/documents/${documentId}/move`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json'
            },
            body: JSON.stringify({
                folder_id: targetFolderId
            })
        })
        .then(response => {
            if (!response.ok) {
                return response.text().then(text => {
                    console.error("Response not OK:", response.status, text);
                    throw new Error('Server error: ' + response.status);
                });
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                if (window.moveDocumentModal) {
                    window.moveDocumentModal.hide();
                }
                
                showNotification(data.message || 'Document moved successfully', 'success');
                window.location.reload();
            } else {
                showNotification(data.message || 'Failed to move document', 'danger');
            }
        })
        .catch(error => {
            console.error('Error moving document:', error);
            showNotification('Failed to move document: ' + error.message, 'danger');
        });
    }
    
    // Delete item (folder or document)
    function deleteItem(itemType, itemId) {
        let url;
        if (itemType === 'folder') {
            url = `/documents/folders/${itemId}`;
        } else if (itemType === 'document') {
            url = `/documents/${itemId}`;
        } else {
            showNotification('Invalid item type', 'danger');
            return;
        }
        
        fetch(url, {
            method: 'DELETE',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) {
                return response.text().then(text => {
                    console.error("Response not OK:", response.status, text);
                    throw new Error('Server error: ' + response.status);
                });
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                if (window.deleteConfirmModal) {
                    window.deleteConfirmModal.hide();
                }
                
                showNotification(data.message || 'Item deleted successfully', 'success');
                
                // Redirect or reload
                if (itemType === 'folder') {
                    window.location.href = '/documents';
                } else {
                    window.location.reload();
                }
            } else {
                showNotification(data.message || 'Failed to delete item', 'danger');
            }
        })
        .catch(error => {
            console.error('Error deleting item:', error);
            showNotification('Failed to delete item: ' + error.message, 'danger');
        });
    }
    
    /**
     * Initialize glossary management functionality
     */
    function initGlossaryManagement() {
        console.log("Initializing glossary management");
        
        let currentGlossaryId = null;
        let deleteItemType = null;
        let deleteItemId = null;
        
        try {
            // Initialize Bootstrap modals
            if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
                const entryModalEl = document.getElementById('entryModal');
                const importModalEl = document.getElementById('importModal');
                const deleteConfirmModalEl = document.getElementById('deleteConfirmModal');
                
                if (entryModalEl) {
                    window.entryModal = new bootstrap.Modal(entryModalEl);
                }
                
                if (importModalEl) {
                    window.importModal = new bootstrap.Modal(importModalEl);
                }
                
                if (deleteConfirmModalEl) {
                    window.deleteConfirmModal = new bootstrap.Modal(deleteConfirmModalEl);
                }
            }
            
            // Initialize glossary list
            initGlossaryList();
            
            // Initialize form handlers
            initGlossaryFormHandlers();
            
        } catch (error) {
            console.error("Error initializing glossary management:", error);
        }
        
        /**
         * Initialize glossary list functionality
         */
        function initGlossaryList() {
            document.querySelectorAll('#glossaryList .list-group-item').forEach(item => {
                item.addEventListener('click', function() {
                    // Update selected state
                    document.querySelectorAll('#glossaryList .list-group-item').forEach(el => {
                        el.classList.remove('active');
                    });
                    this.classList.add('active');
                    
                    // Get glossary details
                    const glossaryId = this.dataset.id;
                    const name = this.dataset.name;
                    const description = this.dataset.description;
                    const sourceLang = this.dataset.sourceLang;
                    const targetLang = this.dataset.targetLang;
                    
                    // Populate form
                    document.getElementById('glossaryId').value = glossaryId;
                    document.getElementById('glossaryName').value = name;
                    document.getElementById('glossaryDescription').value = description;
                    
                    const sourceLanguage = document.getElementById('sourceLanguage');
                    if (sourceLanguage) sourceLanguage.value = sourceLang;
                    
                    const targetLanguage = document.getElementById('targetLanguage');
                    if (targetLanguage) targetLanguage.value = targetLang;
                    
                    // Update current glossary context
                    currentGlossaryId = glossaryId;
                    
                    const currentGlossaryName = document.getElementById('currentGlossaryName');
                    if (currentGlossaryName) currentGlossaryName.textContent = name;
                    
                    // Enable entry buttons
                    const addEntryBtn = document.getElementById('addEntryBtn');
                    if (addEntryBtn) addEntryBtn.disabled = false;
                    
                    const importBtn = document.getElementById('importBtn');
                    if (importBtn) importBtn.disabled = false;
                    
                    const exportBtn = document.getElementById('exportBtn');
                    if (exportBtn) exportBtn.disabled = false;
                    
                    // Show entries
                    loadGlossaryEntries(glossaryId);
                });
            });
        }
        
        /**
         * Initialize form handlers
         */
        function initGlossaryFormHandlers() {
            // New glossary button
            const createGlossaryBtn = document.getElementById('createGlossaryBtn');
            if (createGlossaryBtn) {
                createGlossaryBtn.addEventListener('click', function() {
                    console.log("Create glossary button clicked");
                    
                    // Clear form
                    const glossaryForm = document.getElementById('glossaryForm');
                    if (glossaryForm) glossaryForm.reset();
                    
                    const glossaryId = document.getElementById('glossaryId');
                    if (glossaryId) glossaryId.value = '';
                    
                    // Remove selection
                    document.querySelectorAll('#glossaryList .list-group-item').forEach(item => {
                        item.classList.remove('active');
                    });
                    
                    // Hide entries
                    const entriesContainer = document.getElementById('entriesContainer');
                    if (entriesContainer) entriesContainer.classList.add('d-none');
                    
                    const entriesPlaceholder = document.getElementById('entriesPlaceholder');
                    if (entriesPlaceholder) entriesPlaceholder.classList.remove('d-none');
                    
                    const currentGlossaryName = document.getElementById('currentGlossaryName');
                    if (currentGlossaryName) currentGlossaryName.textContent = 'Välj en ordlista';
                    
                    // Disable entry buttons
                    const addEntryBtn = document.getElementById('addEntryBtn');
                    if (addEntryBtn) addEntryBtn.disabled = true;
                    
                    const importBtn = document.getElementById('importBtn');
                    if (importBtn) importBtn.disabled = true;
                    
                    const exportBtn = document.getElementById('exportBtn');
                    if (exportBtn) exportBtn.disabled = true;
                    
                    // Show alternate submit option
                    const alternateSubmitContainer = document.getElementById('alternateSubmitContainer');
                    if (alternateSubmitContainer) alternateSubmitContainer.style.display = 'block';
                    
                    currentGlossaryId = null;
                });
            }
            
            // Glossary form
            const glossaryForm = document.getElementById('glossaryForm');
            if (glossaryForm) {
                glossaryForm.addEventListener('submit', function(e) {
                    e.preventDefault();
                    saveGlossary();
                });
            }
            
            // Save glossary button
            const saveGlossaryBtn = document.getElementById('saveGlossaryBtn');
            if (saveGlossaryBtn) {
                saveGlossaryBtn.addEventListener('click', function(e) {
                    e.preventDefault();
                    saveGlossary();
                });
            }
            
            // Alternate submit button
            const alternateSubmitBtn = document.getElementById('alternateSubmitBtn');
            if (alternateSubmitBtn) {
                alternateSubmitBtn.addEventListener('click', function() {
                    // Get form values
                    const name = document.getElementById('glossaryName').value;
                    const description = document.getElementById('glossaryDescription').value;
                    const sourceLang = document.getElementById('sourceLanguage').value;
                    const targetLang = document.getElementById('targetLanguage').value;
                    
                    if (!name) {
                        showNotification('Glossary name is required', 'warning');
                        return;
                    }
                    
                    // Populate hidden form
                    const directName = document.getElementById('directName');
                    if (directName) directName.value = name;
                    
                    const directDescription = document.getElementById('directDescription');
                    if (directDescription) directDescription.value = description;
                    
                    const directSourceLanguage = document.getElementById('directSourceLanguage');
                    if (directSourceLanguage) directSourceLanguage.value = sourceLang;
                    
                    const directTargetLanguage = document.getElementById('directTargetLanguage');
                    if (directTargetLanguage) directTargetLanguage.value = targetLang;
                    
                    // Submit the direct form
                    const directGlossaryForm = document.getElementById('directGlossaryForm');
                    if (directGlossaryForm) directGlossaryForm.submit();
                });
            }
            
            // Delete glossary button
            const deleteGlossaryBtn = document.getElementById('deleteGlossaryBtn');
            if (deleteGlossaryBtn) {
                deleteGlossaryBtn.addEventListener('click', function() {
                    const glossaryId = document.getElementById('glossaryId').value;
                    if (!glossaryId) return;
                    
                    deleteItemType = 'glossary';
                    deleteItemId = glossaryId;
                    const glossaryName = document.getElementById('glossaryName').value;
                    
                    const deleteConfirmMessage = document.getElementById('deleteConfirmMessage');
                    if (deleteConfirmMessage) {
                        deleteConfirmMessage.textContent = 
                            `Är du säker på att du vill ta bort ordlistan "${glossaryName}"? Detta kommer permanent ta bort alla termer i denna ordlista.`;
                    }
                    
                    if (window.deleteConfirmModal) {
                        window.deleteConfirmModal.show();
                    } else {
                        // Fallback if modal fails
                        if (confirm(`Är du säker på att du vill ta bort ordlistan "${glossaryName}"?`)) {
                            deleteGlossary(deleteItemId);
                        }
                    }
                });
            }
            
            // Add entry button
            const addEntryBtn = document.getElementById('addEntryBtn');
            if (addEntryBtn) {
                addEntryBtn.addEventListener('click', function() {
                    // Clear form
                    const entryForm = document.getElementById('entryForm');
                    if (entryForm) entryForm.reset();
                    
                    const entryId = document.getElementById('entryId');
                    if (entryId) entryId.value = '';
                    
                    // Update modal title
                    const entryModalLabel = document.getElementById('entryModalLabel');
                    if (entryModalLabel) entryModalLabel.textContent = 'Lägg till ny term';
                    
                    // Show modal
                    if (window.entryModal) {
                        window.entryModal.show();
                    } else if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
                        const entryModalEl = document.getElementById('entryModal');
                        if (entryModalEl) {
                            const entryModal = new bootstrap.Modal(entryModalEl);
                            entryModal.show();
                        }
                    }
                });
            }
            
            // Save entry button
            const saveEntryBtn = document.getElementById('saveEntryBtn');
            if (saveEntryBtn) {
                saveEntryBtn.addEventListener('click', function() {
                    if (!validateEntryForm()) return;
                    saveEntry();
                });
            }
            
            // Import button
            const importBtn = document.getElementById('importBtn');
            if (importBtn) {
                importBtn.addEventListener('click', function() {
                    // Clear form
                    const importForm = document.getElementById('importForm');
                    if (importForm) importForm.reset();
                    
                    // Show modal
                    if (window.importModal) {
                        window.importModal.show();
                    } else if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
                        const importModalEl = document.getElementById('importModal');
                        if (importModalEl) {
                            const importModal = new bootstrap.Modal(importModalEl);
                            importModal.show();
                        }
                    }
                });
            }
            
            // Submit import button
            const submitImportBtn = document.getElementById('submitImportBtn');
            if (submitImportBtn) {
                submitImportBtn.addEventListener('click', function() {
                    const importFile = document.getElementById('importFile');
                    if (!importFile || !importFile.files.length) {
                        showNotification('Vänligen välj en fil att importera', 'warning');
                        return;
                    }
                    importTerms();
                });
            }
            
            // Export button
            const exportBtn = document.getElementById('exportBtn');
            if (exportBtn) {
                exportBtn.addEventListener('click', function() {
                    if (!currentGlossaryId) return;
                    exportTerms(currentGlossaryId);
                });
            }
            
            // Delete confirmation button
            const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
            if (confirmDeleteBtn) {
                confirmDeleteBtn.addEventListener('click', function() {
                    if (deleteItemType === 'glossary') {
                        deleteGlossary(deleteItemId);
                    } else if (deleteItemType === 'entry') {
                        deleteEntry(deleteItemId);
                    }
                    
                    // Close modal
                    if (window.deleteConfirmModal) {
                        window.deleteConfirmModal.hide();
                    } else if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
                        const deleteConfirmModalEl = document.getElementById('deleteConfirmModal');
                        if (deleteConfirmModalEl) {
                            const deleteConfirmModal = bootstrap.Modal.getInstance(deleteConfirmModalEl);
                            if (deleteConfirmModal) deleteConfirmModal.hide();
                        }
                    }
                });
            }
        }
        
        /**
         * Save glossary
         */
        function saveGlossary() {
            const glossaryId = document.getElementById('glossaryId').value;
            const name = document.getElementById('glossaryName').value;
            const description = document.getElementById('glossaryDescription').value;
            const sourceLang = document.getElementById('sourceLanguage').value;
            const targetLang = document.getElementById('targetLanguage').value;
            
            if (!name) {
                showNotification('Glossary name is required', 'warning');
                return;
            }
            
            const data = {
                name: name,
                description: description,
                source_language: sourceLang,
                target_language: targetLang
            };
            
            const url = glossaryId ? `/glossary/${glossaryId}` : '/glossary';
            const method = glossaryId ? 'PUT' : 'POST';
            
            console.log("Sending request to:", url, "Method:", method);
            
            // For new glossaries, use traditional form submission
            if (method === 'POST') {
                // Submit a hidden form to avoid AJAX issues
                const form = document.createElement('form');
                form.method = 'POST';
                form.action = url;
                
                // Add fields
                for (const key in data) {
                    if (data.hasOwnProperty(key)) {
                        const input = document.createElement('input');
                        input.type = 'hidden';
                        input.name = key;
                        input.value = data[key];
                        form.appendChild(input);
                    }
                }
                
                // Add to document and submit
                document.body.appendChild(form);
                form.submit();
                return; // Exit since we're doing a form submit
            }
            
            // For updates, try AJAX first
            fetch(url, {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify(data)
            })
            .then(response => {
                if (!response.ok) {
                    return response.text().then(text => {
                        console.error("Response not OK:", response.status, text);
                        throw new Error('Server error: ' + response.status);
                    });
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    showNotification(data.message || 'Glossary saved successfully', 'success');
                    window.location.reload();
                } else {
                    showNotification(data.message || 'Failed to save glossary', 'danger');
                }
            })
            .catch(error => {
                console.error('Error saving glossary:', error);
                
                // Fallback to form submission for updates as well
                const form = document.createElement('form');
                form.method = 'POST';
                form.action = url;
                
                // Add method override field for PUT
                const methodField = document.createElement('input');
                methodField.type = 'hidden';
                methodField.name = '_method';
                methodField.value = 'PUT';
                form.appendChild(methodField);
                
                // Add data fields
                for (const key in data) {
                    if (data.hasOwnProperty(key)) {
                        const input = document.createElement('input');
                        input.type = 'hidden';
                        input.name = key;
                        input.value = data[key];
                        form.appendChild(input);
                    }
                }
                
                // Add to document and submit
                document.body.appendChild(form);
                form.submit();
            });
        }
        
        /**
         * Delete glossary
         */
        function deleteGlossary(glossaryId) {
            // Try direct form submission first for reliable operation
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = `/glossary/${glossaryId}`;
            
            // Add method override field for DELETE
            const methodField = document.createElement('input');
            methodField.type = 'hidden';
            methodField.name = '_method';
            methodField.value = 'DELETE';
            form.appendChild(methodField);
            
            // Add to document and submit
            document.body.appendChild(form);
            form.submit();
        }
        
        /**
         * Load glossary entries
         */
        function loadGlossaryEntries(glossaryId) {
            fetch(`/glossary/${glossaryId}/entries`)
            .then(response => {
                if (!response.ok) {
                    return response.text().then(text => {
                        console.error("Response not OK:", response.status, text);
                        throw new Error('Server error: ' + response.status);
                    });
                }
                return response.json();
            })
            .then(data => {
                // Show entries container, hide placeholder
                const entriesPlaceholder = document.getElementById('entriesPlaceholder');
                if (entriesPlaceholder) entriesPlaceholder.classList.add('d-none');
                
                const entriesContainer = document.getElementById('entriesContainer');
                if (entriesContainer) entriesContainer.classList.remove('d-none');
                
                // Populate entries table
                const tableBody = document.getElementById('entriesTableBody');
                if (!tableBody) return;
                
                tableBody.innerHTML = '';
                
                if (data.entries && data.entries.length > 0) {
                    const noEntriesMessage = document.getElementById('noEntriesMessage');
                    if (noEntriesMessage) noEntriesMessage.classList.add('d-none');
                    
                    data.entries.forEach(entry => {
                        const row = document.createElement('tr');
                        row.dataset.id = entry.id;
                        
                        // Source term cell
                        const sourceCell = document.createElement('td');
                        sourceCell.textContent = entry.source_term;
                        
                        // Target term cell
                        const targetCell = document.createElement('td');
                        targetCell.textContent = entry.target_term;
                        
                        // Actions cell
                        const actionsCell = document.createElement('td');
                        
                        // Edit button
                        const editBtn = document.createElement('button');
                        editBtn.className = 'btn btn-sm btn-outline-primary me-1';
                        editBtn.innerHTML = '<i class="bi bi-pencil"></i>';
                        editBtn.addEventListener('click', function() {
                            loadEntryForEdit(entry);
                        });
                        
                        // Delete button
                        const deleteBtn = document.createElement('button');
                        deleteBtn.className = 'btn btn-sm btn-outline-danger';
                        deleteBtn.innerHTML = '<i class="bi bi-trash"></i>';
                        deleteBtn.addEventListener('click', function() {
                            confirmDeleteEntry(entry.id);
                        });
                        
                        actionsCell.appendChild(editBtn);
                        actionsCell.appendChild(deleteBtn);
                        
                        // Add cells to row
                        row.appendChild(sourceCell);
                        row.appendChild(targetCell);
                        row.appendChild(actionsCell);
                        
                        // Add row to table
                        tableBody.appendChild(row);
                    });
                } else {
                    const noEntriesMessage = document.getElementById('noEntriesMessage');
                    if (noEntriesMessage) noEntriesMessage.classList.remove('d-none');
                }
            })
            .catch(error => {
                console.error('Error loading glossary entries:', error);
                showNotification('Failed to load glossary entries', 'danger');
            });
        }
        
        /**
         * Load entry for editing
         */
        function loadEntryForEdit(entry) {
            // Populate form
            const entryId = document.getElementById('entryId');
            if (entryId) entryId.value = entry.id;
            
            const sourceTerm = document.getElementById('sourceTerm');
            if (sourceTerm) sourceTerm.value = entry.source_term;
            
            const targetTerm = document.getElementById('targetTerm');
            if (targetTerm) targetTerm.value = entry.target_term;
            
            const context = document.getElementById('context');
            if (context) context.value = entry.context || '';
            
            const notes = document.getElementById('notes');
            if (notes) notes.value = entry.notes || '';
            
            // Update modal title
            const entryModalLabel = document.getElementById('entryModalLabel');
            if (entryModalLabel) entryModalLabel.textContent = 'Redigera term';
            
            // Show modal
            if (window.entryModal) {
                window.entryModal.show();
            } else if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
                const entryModalEl = document.getElementById('entryModal');
                if (entryModalEl) {
                    const entryModal = new bootstrap.Modal(entryModalEl);
                    entryModal.show();
                }
            }
        }
        
        /**
         * Save entry
         */
        function saveEntry() {
            const entryId = document.getElementById('entryId').value;
            const sourceTerm = document.getElementById('sourceTerm').value;
            const targetTerm = document.getElementById('targetTerm').value;
            const context = document.getElementById('context').value;
            const notes = document.getElementById('notes').value;
            
            if (!currentGlossaryId) {
                showNotification('Ingen ordlista vald', 'warning');
                return;
            }
            
            const data = {
                source_term: sourceTerm,
                target_term: targetTerm,
                context: context,
                notes: notes
            };
            
            const url = entryId 
                ? `/glossary/${currentGlossaryId}/entries/${entryId}`
                : `/glossary/${currentGlossaryId}/entries`;
                
            const method = entryId ? 'PUT' : 'POST';
            
            fetch(url, {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify(data)
            })
            .then(response => {
                if (!response.ok) {
                    return response.text().then(text => {
                        console.error("Response not OK:", response.status, text);
                        throw new Error('Server error: ' + response.status);
                    });
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    showNotification(data.message || 'Term saved successfully', 'success');
                    
                    // Close modal
                    if (window.entryModal) {
                        window.entryModal.hide();
                    } else if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
                        const entryModalEl = document.getElementById('entryModal');
                        if (entryModalEl) {
                            const entryModal = bootstrap.Modal.getInstance(entryModalEl);
                            if (entryModal) entryModal.hide();
                        }
                    }
                    
                    // Reload entries
                    loadGlossaryEntries(currentGlossaryId);
                } else {
                    showNotification(data.message || 'Failed to save term', 'danger');
                }
            })
            .catch(error => {
                console.error('Error saving entry:', error);
                showNotification('Failed to save term: ' + error.message, 'danger');
                
                // Fallback to form submission
                const form = document.createElement('form');
                form.method = 'POST';
                form.action = url;
                
                // Add method override field for PUT if needed
                if (method === 'PUT') {
                    const methodField = document.createElement('input');
                    methodField.type = 'hidden';
                    methodField.name = '_method';
                    methodField.value = 'PUT';
                    form.appendChild(methodField);
                }
                
                // Add data fields
                for (const key in data) {
                    if (data.hasOwnProperty(key)) {
                        const input = document.createElement('input');
                        input.type = 'hidden';
                        input.name = key;
                        input.value = data[key];
                        form.appendChild(input);
                    }
                }
                
                // Add to document and submit
                document.body.appendChild(form);
                form.submit();
            });
        }
        
        /**
         * Confirm delete entry
         */
        function confirmDeleteEntry(entryId) {
            deleteItemType = 'entry';
            deleteItemId = entryId;
            
            const deleteConfirmMessage = document.getElementById('deleteConfirmMessage');
            if (deleteConfirmMessage) {
                deleteConfirmMessage.textContent = 'Är du säker på att du vill ta bort denna term? Denna åtgärd kan inte ångras.';
            }
            
            if (window.deleteConfirmModal) {
                window.deleteConfirmModal.show();
            } else if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
                const deleteConfirmModalEl = document.getElementById('deleteConfirmModal');
                if (deleteConfirmModalEl) {
                    const deleteConfirmModal = new bootstrap.Modal(deleteConfirmModalEl);
                    deleteConfirmModal.show();
                }
            } else {
                // Fallback if modal fails
                if (confirm('Är du säker på att du vill ta bort denna term? Denna åtgärd kan inte ångras.')) {
                    deleteEntry(entryId);
                }
            }
        }
        
        /**
         * Delete entry
         */
        function deleteEntry(entryId) {
            fetch(`/glossary/${currentGlossaryId}/entries/${entryId}`, {
                method: 'DELETE',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => {
                if (!response.ok) {
                    return response.text().then(text => {
                        console.error("Response not OK:", response.status, text);
                        throw new Error('Server error: ' + response.status);
                    });
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    showNotification(data.message || 'Term deleted successfully', 'success');
                    
                    // Reload entries
                    loadGlossaryEntries(currentGlossaryId);
                } else {
                    showNotification(data.message || 'Failed to delete term', 'danger');
                }
            })
            .catch(error => {
                console.error('Error deleting entry:', error);
                showNotification('Failed to delete term: ' + error.message, 'danger');
                
                // Fallback to form submission
                const form = document.createElement('form');
                form.method = 'POST';
                form.action = `/glossary/${currentGlossaryId}/entries/${entryId}`;
                
                // Add method override field for DELETE
                const methodField = document.createElement('input');
                methodField.type = 'hidden';
                methodField.name = '_method';
                methodField.value = 'DELETE';
                form.appendChild(methodField);
                
                // Add to document and submit
                document.body.appendChild(form);
                form.submit();
            });
        }
        
        /**
         * Import terms
         */
        function importTerms() {
            const importFile = document.getElementById('importFile');
            if (!importFile || !importFile.files.length || !currentGlossaryId) return;
            
            const file = importFile.files[0];
            const hasHeader = document.getElementById('hasHeader').checked;
            
            const formData = new FormData();
            formData.append('file', file);
            formData.append('has_header', hasHeader ? 'true' : 'false');
            
            fetch(`/glossary/${currentGlossaryId}/import`, {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    return response.text().then(text => {
                        console.error("Response not OK:", response.status, text);
                        throw new Error('Server error: ' + response.status);
                    });
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    showNotification(data.message || `Imported ${data.count} terms successfully`, 'success');
                    
                    // Close modal
                    if (window.importModal) {
                        window.importModal.hide();
                    } else if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
                        const importModalEl = document.getElementById('importModal');
                        if (importModalEl) {
                            const importModal = bootstrap.Modal.getInstance(importModalEl);
                            if (importModal) importModal.hide();
                        }
                    }
                    
                    // Reload entries
                    loadGlossaryEntries(currentGlossaryId);
                } else {
                    showNotification(data.message || 'Failed to import terms', 'danger');
                }
            })
            .catch(error => {
                console.error('Error importing terms:', error);
                showNotification('Failed to import terms: ' + error.message, 'danger');
                
                // Try traditional form submission as fallback
                const form = document.createElement('form');
                form.method = 'POST';
                form.action = `/glossary/${currentGlossaryId}/import`;
                form.enctype = 'multipart/form-data';
                
                // Clone the file input and add to form
                const fileInput = importFile.cloneNode(true);
                form.appendChild(fileInput);
                
                // Add has_header field
                const hasHeaderInput = document.createElement('input');
                hasHeaderInput.type = 'hidden';
                hasHeaderInput.name = 'has_header';
                hasHeaderInput.value = hasHeader ? 'true' : 'false';
                form.appendChild(hasHeaderInput);
                
                // Add to document and submit
                document.body.appendChild(form);
                form.submit();
            });
        }
        
        /**
         * Export terms
         */
        function exportTerms(glossaryId) {
            window.location.href = `/glossary/${glossaryId}/export`;
        }
        
        /**
         * Validate entry form
         */
        function validateEntryForm() {
            const sourceTerm = document.getElementById('sourceTerm');
            const targetTerm = document.getElementById('targetTerm');
            
            if (!sourceTerm || !sourceTerm.value.trim()) {
                showNotification('Källterm krävs', 'warning');
                return false;
            }
            
            if (!targetTerm || !targetTerm.value.trim()) {
                showNotification('Målterm krävs', 'warning');
                return false;
            }
            
            return true;
        }
    }
});
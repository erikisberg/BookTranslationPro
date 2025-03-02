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
});
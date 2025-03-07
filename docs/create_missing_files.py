#!/usr/bin/env python3

import os

# List of files referenced in nav that need to be created
missing_files = [
    "architecture/system-design.md",
    "architecture/tech-stack.md",
    "api/openai.md",
    "api/deepl.md",
    "api/internal.md",
    "database/supabase.md",
    "setup/configuration.md",
    "setup/environment.md",
    "user-workflows/document-upload.md",
    "user-workflows/export.md",
    "modules/authentication.md",
    "modules/document-processing.md",
    "modules/ui-components.md"
]

# Base directory for docs
base_dir = "docs"

# Template content for placeholder files
template = """# {title}

This documentation is under development.

## Overview

{overview}

## Technical Details

This section will include technical details about the {topic}.

## Related Components

- Link to related component 1
- Link to related component 2
"""

# Create each missing file
for file_path in missing_files:
    # Extract title from filename
    filename = os.path.basename(file_path)
    title = filename.replace(".md", "").replace("-", " ").title()
    topic = title.lower()
    
    # Create a custom overview based on the file type
    if "api" in file_path:
        overview = f"This page will document the {title} API integration."
    elif "architecture" in file_path:
        overview = f"This page will document the {title} of the application."
    elif "database" in file_path:
        overview = f"This page will document the {title} database configuration."
    elif "setup" in file_path:
        overview = f"This page will provide instructions for {title}."
    elif "user-workflows" in file_path:
        overview = f"This page will document the {title} process."
    elif "modules" in file_path:
        overview = f"This page will document the {title} module functionality."
    else:
        overview = f"This page will document {title}."
        
    # Format the content
    content = template.format(title=title, overview=overview, topic=topic)
    
    # Ensure directory exists
    full_dir = os.path.join(base_dir, os.path.dirname(file_path))
    os.makedirs(full_dir, exist_ok=True)
    
    # Create the file
    full_path = os.path.join(base_dir, file_path)
    with open(full_path, 'w') as f:
        f.write(content)
    
    print(f"Created {full_path}")

print("\nAll missing files have been created.")
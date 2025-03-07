#!/bin/bash

# Build the MkDocs site
echo "Building technical documentation..."
mkdocs build

# Copy to a docs directory if needed
# mkdir -p ../public/docs
# cp -r site/* ../public/docs/

echo "Documentation built successfully!"
echo "Files are in the 'site' directory"
echo "To view locally: open site/index.html"
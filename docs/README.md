# BookTranslationPro Technical Documentation

This directory contains the technical documentation for BookTranslationPro.

## Documentation Structure

The documentation is built using MkDocs with the Material theme and organized into the following sections:

- **Architecture**: System design, components, and technical stack
- **API**: Documentation for API integrations (OpenAI, DeepL)
- **Database**: Schema and Supabase configuration
- **Setup**: Installation, configuration, and environment setup
- **User Workflows**: Key user workflows and implementation details
- **Modules**: Core modules and their functionality

## Local Development

### Prerequisites

- Python 3.9+
- pip

### Setup

1. Install MkDocs and the Material theme:

```
pip install mkdocs mkdocs-material
```

2. Run the local development server:

```
cd docs
mkdocs serve
```

The documentation will be available at http://localhost:8000.

### Building the Documentation

To build the static site:

```
./build_docs.sh
```

This will create a `site` directory with the built documentation.

## Contributing to Documentation

1. Create or edit Markdown files in the `docs` directory
2. Follow the existing structure and formatting
3. Use proper headings, code blocks, and diagrams where appropriate
4. Test your changes locally using `mkdocs serve`
5. Build the documentation using `./build_docs.sh` before committing

## Documentation Best Practices

- Keep content clear, concise, and technically accurate
- Include code examples with proper syntax highlighting
- Use diagrams for complex workflows or architecture
- Document public APIs, functions, and data models thoroughly
- Include information about error handling and edge cases
- Cross-reference related documentation sections
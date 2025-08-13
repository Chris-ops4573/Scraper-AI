# Code Assistant & Semantic Search VS Code Extension

A powerful VS Code extension that brings AI-assisted coding and semantic search across your project files directly into your editor.

## Features

### 🤖 AI Code Assistant

- Ask questions and get intelligent code suggestions directly in the editor.
- Generate, review, and explain code using AI
- Get context-aware help for debugging, optimization, and code understanding based on your editor and repos uploading to/out long parts directly out what or upload from Gcode

### 🔍 Semantic Search

- Search across your entire codebase using semantic meaning, not just keywords.
- Supports fuzzy matches and related code discovery.
- Instant navigation to relevant files and code snippets.

## Requirements

- Visual Studio Code version 1.60.0 or higher
- An active internet connection when the AI coding assistant is available (not required to install).
- To start using the semantic file search, upload your current project folder by using the command palette and clicking Upload Project to Agent. Then you can open the command palette and select semantic file search to start navigating through your codebase.

## Known Issues

- Large repositories might take longer to index for semantic search.
- AI coding assistant has no context from previous chats, but has all the context in upcoming updates of the extension.

## Release Notes

### 0.0.0

Initial release of the Code Assistant & Semantic Search extension.

Key features:
- AI-powered inline chat for code generation, explanation, and refactoring.
- Full project semantic search to find code by meaning, not just text.
- Configurable API endpoint and settings for flexible backend integration.
- Smooth navigation to relevant files and code snippets.

### 0.0.5

Key features:
- Updated folder upload logic, ignored more folders for decreasing payload size
- Improved file navigation

### 1.0.0

Key updates:
- Backend hosted on a different instance
- Layout changes

### 1.0.5
Key updates:
- Improved message handling logic
- Request gets cancelled if spinner is clicked again
- Additional code context depending on selected text

### 1.0.7
Updated project uploading logic:
- Using ssh-256 hashing to detects changes in files compared to old uploads and only uploads files that change.
- Updates users on backend folder updates.
- Added uploaded folder deletion logic.

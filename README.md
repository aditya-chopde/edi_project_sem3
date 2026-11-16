# Itihasa AI

Itihasa AI pairs a Next.js conversational research interface with a FastAPI backend for ingesting historical documents and answering questions with page-level citations. The frontend remains independently buildable; backend data and indexes are stored in `backend/dataset/`.

## Overview

This project is built with Next.js and TypeScript, and it focuses on a clean, research-oriented chat experience with:

- a sidebar for recent chats and archive navigation
- a multilingual answer selector
- conversational memory stored locally in the browser
- streaming-style mock assistant responses
- source cards and inline citations
- attachment support for PDFs and images
- responsive layout for desktop and mobile

## Tech Stack

- Next.js
- React
- TypeScript
- Tailwind CSS
- shadcn-style UI primitives
- Lucide React icons

## Features

- Chat workflow for user questions and AI-style responses
- Multilingual output support: English, Hindi, Marathi, Hinglish, and Sanskrit
- Retrieval mode selector for demo modes such as cross-language or hybrid retrieval
- Citation-style evidence cards for mock historical records
- Local conversation persistence using browser storage
- Empty-state suggestions for historical research prompts
- Responsive mobile drawer navigation
- Demo-safe design with clearly labeled illustrative sources

## Project Structure

```text
app/
  layout.tsx
  page.tsx
  workspace/
    page.tsx
    chat.css
components/
  ui/
  chat-markdown.tsx
lib/
  chat-types.ts
  chat-mock.ts
```

## Getting Started

### Frontend

```bash
npm install
```

2. Start the development server:

```bash
npm run dev
```

3. Open the app in your browser:

```text
http://localhost:3000/workspace
```

### Backend

From `backend/`, install the pinned dependencies and start the API:

```bash
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API documentation is available at `http://localhost:8000/docs`. Set `GEMINI_API_KEY`
in the backend process environment to enable answer generation. `ITIHASA_DATASET_DIR`
can override the default `backend/dataset/` storage location; OCR languages can be
configured with `TESSERACT_LANGS` (default `eng+hin+mar`). Scanned PDFs and image uploads
also require the Tesseract system executable and the selected language data packs.

## Available Scripts

```bash
npm run dev
npm run build
```

## Notes

- Chat data is stored in the browser via localStorage.
- The backend exposes document upload and polling under `/api/documents`, question answering
  under `/api/query`, and index health at `/health`.

## License

This project is for educational/demo purposes.
import logging

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["API testing"])
logger = logging.getLogger(__name__)


@router.get("/api-test", response_class=HTMLResponse, include_in_schema=False)
def api_test_page() -> str:
    logger.info("API test page opened")
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Itihasa AI API tester</title>
  <style>
    :root { color-scheme: light; font-family: system-ui, sans-serif; color: #24211e; background: #f5f2ec; }
    body { max-width: 900px; margin: 0 auto; padding: 32px 18px 56px; }
    h1 { margin-bottom: 6px; }
    .intro, small { color: #625e58; }
    section { margin-top: 20px; padding: 22px; background: white; border: 1px solid #e4dfd6; border-radius: 12px; }
    h2 { margin: 0 0 14px; font-size: 1.15rem; }
    label { display: block; margin: 12px 0 5px; font-weight: 600; }
    input, select, textarea, button { box-sizing: border-box; width: 100%; padding: 10px 12px; border: 1px solid #c9c3b9; border-radius: 7px; font: inherit; }
    textarea { min-height: 90px; resize: vertical; }
    button { width: auto; margin-top: 14px; color: white; background: #593f2b; border-color: #593f2b; cursor: pointer; }
    button.secondary { color: #35291f; background: white; }
    button:disabled { opacity: .6; cursor: wait; }
    .grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 14px; }
    pre { max-height: 320px; overflow: auto; padding: 12px; background: #f5f2ec; border-radius: 7px; white-space: pre-wrap; overflow-wrap: anywhere; }
    .result { margin-top: 14px; }
    .error { color: #a32323; }
    .doc { display: flex; justify-content: space-between; gap: 10px; padding: 10px 0; border-top: 1px solid #eee9e1; }
    .doc button { flex: 0 0 auto; margin: 0; }
    @media (max-width: 600px) { .grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <h1>Itihasa AI API tester</h1>
  <p class="intro">Try the backend upload, query, status, and delete endpoints. Responses and errors appear below each form.</p>

  <section>
    <h2>POST /api/documents/upload</h2>
    <form id="upload-form">
      <label for="upload-file">Document</label>
      <input id="upload-file" name="file" type="file" accept=".pdf,.png,.jpg,.jpeg,.tiff,.tif,.bmp,.txt,.md,.docx,.epub" required>
      <div class="grid">
        <div><label for="upload-title">Title (optional)</label><input id="upload-title" name="title"></div>
        <div><label for="upload-language">Document language (optional)</label><input id="upload-language" name="language" placeholder="en, hi, or mr"></div>
        <div><label for="upload-period">Historical period (optional)</label><input id="upload-period" name="historical_period"></div>
        <div><label for="upload-source">Source URL (optional)</label><input id="upload-source" name="source_url" type="url"></div>
      </div>
      <button type="submit">Upload document</button>
    </form>
    <div id="upload-result" class="result" aria-live="polite"></div>
  </section>

  <section>
    <h2>POST /api/query</h2>
    <form id="query-form">
      <label for="question">Question</label>
      <textarea id="question" required placeholder="Ask a historical question"></textarea>
      <label for="answer-language">Answer language (optional)</label>
      <select id="answer-language">
        <option value="">Detect from question</option>
        <option value="English">English</option>
        <option value="Hindi">Hindi</option>
        <option value="Marathi">Marathi</option>
      </select>
      <button type="submit">Send query</button>
    </form>
    <div id="query-result" class="result" aria-live="polite"></div>
  </section>

  <section>
    <h2>GET /api/documents and status</h2>
    <button id="refresh-documents" class="secondary" type="button">Refresh documents</button>
    <div id="documents-result" class="result" aria-live="polite"></div>
  </section>

  <section>
    <h2>DELETE /api/documents/{document_id}</h2>
    <form id="delete-form">
      <label for="delete-id">Document ID</label>
      <input id="delete-id" required placeholder="Paste a document ID or choose Delete above">
      <button type="submit">Delete document</button>
    </form>
    <div id="delete-result" class="result" aria-live="polite"></div>
  </section>

  <script>
    async function request(url, options) {
      const response = await fetch(url, options);
      if (response.status === 204) return { status: response.status, data: null };
      const contentType = response.headers.get("content-type") || "";
      const data = contentType.includes("application/json")
        ? await response.json()
        : await response.text();
      if (!response.ok) {
        const detail = data && typeof data === "object" ? data.detail : data;
        throw new Error(detail || `Request failed (${response.status})`);
      }
      return { status: response.status, data };
    }

    function showResult(target, data, error) {
      target.replaceChildren();
      const pre = document.createElement("pre");
      pre.className = error ? "error" : "";
      pre.textContent = error ? String(error) : JSON.stringify(data, null, 2);
      target.append(pre);
    }

    document.getElementById("upload-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const button = form.querySelector("button");
      const output = document.getElementById("upload-result");
      button.disabled = true;
      try {
        const { data } = await request("/api/documents/upload", {
          method: "POST",
          body: new FormData(form),
        });
        document.getElementById("delete-id").value = data.id;
        showResult(output, data);
        refreshDocuments();
      } catch (error) {
        showResult(output, null, error.message);
      } finally {
        button.disabled = false;
      }
    });

    document.getElementById("query-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = event.currentTarget.querySelector("button");
      const output = document.getElementById("query-result");
      const body = { question: document.getElementById("question").value };
      const language = document.getElementById("answer-language").value;
      if (language) body.answer_language = language;
      button.disabled = true;
      try {
        const { data } = await request("/api/query", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        showResult(output, data);
      } catch (error) {
        showResult(output, null, error.message);
      } finally {
        button.disabled = false;
      }
    });

    async function refreshDocuments() {
      const output = document.getElementById("documents-result");
      output.replaceChildren();
      try {
        const { data } = await request("/api/documents");
        if (!data.length) {
          output.textContent = "No documents uploaded yet.";
          return;
        }
        for (const doc of data) {
          const row = document.createElement("div");
          row.className = "doc";
          const details = document.createElement("span");
          details.textContent = `${doc.title} — ${doc.status} — ${doc.id}`;
          row.append(details);
          const statusButton = document.createElement("button");
          statusButton.type = "button";
          statusButton.className = "secondary";
          statusButton.textContent = "Check status";
          statusButton.addEventListener("click", async () => {
            try {
              const { data: status } = await request(`/api/documents/${encodeURIComponent(doc.id)}`);
              showResult(output, status);
            } catch (error) {
              showResult(output, null, error.message);
            }
          });
          const deleteButton = document.createElement("button");
          deleteButton.type = "button";
          deleteButton.textContent = "Delete";
          deleteButton.addEventListener("click", () => {
            document.getElementById("delete-id").value = doc.id;
            document.getElementById("delete-id").scrollIntoView({ behavior: "smooth" });
          });
          row.append(statusButton, deleteButton);
          output.append(row);
        }
      } catch (error) {
        showResult(output, null, error.message);
      }
    }

    document.getElementById("refresh-documents").addEventListener("click", refreshDocuments);
    document.getElementById("delete-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const id = document.getElementById("delete-id").value.trim();
      const output = document.getElementById("delete-result");
      if (!window.confirm(`Permanently delete document ${id}?`)) return;
      const button = form.querySelector("button");
      button.disabled = true;
      try {
        const { status } = await request(`/api/documents/${encodeURIComponent(id)}`, {
          method: "DELETE",
        });
        showResult(output, { status, message: "Document deleted." });
        refreshDocuments();
      } catch (error) {
        showResult(output, null, error.message);
      } finally {
        button.disabled = false;
      }
    });

    refreshDocuments();
  </script>
</body>
</html>"""

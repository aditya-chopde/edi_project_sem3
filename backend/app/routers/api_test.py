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
    .doc { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 10px; padding: 10px 0; border-top: 1px solid #eee9e1; }
    .doc-main { flex: 1 1 100%; min-width: 0; }
    .doc-title { font-weight: 650; }
    .doc-meta, .doc-detail { display: block; margin-top: 4px; color: #777168; font-size: .88rem; overflow-wrap: anywhere; }
    .doc-progress-row { display: flex; align-items: center; gap: 10px; margin-top: 11px; }
    .doc-progress { height: 9px; flex: 1; accent-color: #76533a; }
    .doc-progress-row strong { min-width: 42px; text-align: right; font-size: .9rem; }
    .doc-stages { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 9px; }
    .doc-stage { padding: 4px 8px; border-radius: 999px; background: #f0eee9; color: #777168; font-size: .76rem; }
    .doc-stage.done { background: #e5eee7; color: #43694c; }
    .doc-stage.current { background: #f5eadc; color: #76533a; font-weight: 650; }
    .doc-stage.failed { background: #fae7e4; color: #a32323; }
    .doc-actions { display: flex; gap: 8px; margin-left: auto; }
    .doc button { width: auto; flex: 0 0 auto; margin: 0; }
    .documents-pagination { display: flex; align-items: center; justify-content: center; gap: 14px; padding-top: 12px; }
    .documents-pagination[hidden] { display: none; }
    .documents-pagination button { min-width: 42px; margin: 0; }
    .documents-pagination span { color: #777168; font-size: .88rem; }
    @media (max-width: 600px) { .grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <h1>Itihasa AI API tester</h1>
  <p class="intro">Try the backend upload, query, status, and delete endpoints. Document progress refreshes automatically while processing.</p>

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
    <nav id="documents-pagination" class="documents-pagination" aria-label="Document pages" hidden>
      <button id="previous-documents" class="secondary" type="button" aria-label="Previous documents">&larr;</button>
      <span id="documents-page"></span>
      <button id="next-documents" class="secondary" type="button" aria-label="Next documents">&rarr;</button>
    </nav>
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
        currentDocumentPage = 0;
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

    const documentsPerPage = 3;
    let currentDocumentPage = 0;
    let refreshingDocuments = false;
    async function refreshDocuments() {
      const output = document.getElementById("documents-result");
      if (refreshingDocuments) return;
      refreshingDocuments = true;
      output.replaceChildren();
      try {
        const { data } = await request("/api/documents");
        output.dataset.hasActiveDocuments = "false";
        if (!data.length) {
          output.textContent = "No documents uploaded yet.";
          document.getElementById("documents-pagination").hidden = true;
          return;
        }
        const totalPages = Math.ceil(data.length / documentsPerPage);
        currentDocumentPage = Math.min(currentDocumentPage, totalPages - 1);
        const start = currentDocumentPage * documentsPerPage;
        const pageDocuments = data.slice(start, start + documentsPerPage);
        const pagination = document.getElementById("documents-pagination");
        pagination.hidden = data.length <= documentsPerPage;
        document.getElementById("documents-page").textContent =
          `${start + 1}-${Math.min(start + documentsPerPage, data.length)} of ${data.length}`;
        document.getElementById("previous-documents").disabled = currentDocumentPage === 0;
        document.getElementById("next-documents").disabled = currentDocumentPage >= totalPages - 1;
        const hasActiveDocuments = data.some(
          (doc) => !["indexed", "failed"].includes(doc.status),
        );
        const stages = [
          ["extracting", "Extracting"],
          ["chunking", "Chunking"],
          ["embedding", "Embedding"],
          ["indexing", "Indexing"],
        ];
        for (const doc of pageDocuments) {
          const isIndexed = doc.status === "indexed";
          const row = document.createElement("div");
          row.className = "doc";
          const main = document.createElement("div");
          main.className = "doc-main";
          const title = document.createElement("div");
          title.className = "doc-title";
          title.textContent = `${doc.title} — ${doc.status}`;
          const metadata = document.createElement("small");
          metadata.className = "doc-meta";
          metadata.textContent = `${doc.filename} · ${doc.num_pages} pages · ${doc.num_chunks} chunks · ID ${doc.id}`;
          if (!isIndexed) {
            const progressRow = document.createElement("div");
            progressRow.className = "doc-progress-row";
            const progress = document.createElement("progress");
            progress.className = "doc-progress";
            progress.max = 100;
            progress.value = doc.progress_percent || 0;
            progress.setAttribute("aria-label", `${progress.value}% complete`);
            const percentage = document.createElement("strong");
            percentage.textContent = `${progress.value}%`;
            progressRow.append(progress, percentage);

            const stageList = document.createElement("div");
            stageList.className = "doc-stages";
            const activeIndex = stages.findIndex(([status]) => status === doc.status);
            for (const [index, [, label]] of stages.entries()) {
              const stage = document.createElement("span");
              stage.className = "doc-stage";
              if (activeIndex >= 0 && index < activeIndex) {
                stage.classList.add("done");
              } else if (doc.status === "failed" && index === activeIndex) {
                stage.classList.add("failed");
              } else if (!["failed", "pending"].includes(doc.status) && index === activeIndex) {
                stage.classList.add("current");
              }
              stage.textContent = label;
              stageList.append(stage);
            }
            main.append(progressRow, stageList);
          }
          const detail = document.createElement("small");
          detail.className = "doc-detail";
          detail.textContent = isIndexed
            ? doc.progress_detail || "Ingestion complete"
            : doc.error
              ? `Error: ${doc.error}`
              : doc.progress_detail || "Waiting to start";
          main.append(title, metadata, detail);
          row.append(main);

          const actions = document.createElement("div");
          actions.className = "doc-actions";
          const statusButton = document.createElement("button");
          statusButton.type = "button";
          statusButton.className = "secondary";
          statusButton.textContent = "Refresh";
          statusButton.addEventListener("click", async () => {
            try {
              await request(`/api/documents/${encodeURIComponent(doc.id)}`);
              refreshDocuments();
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
          actions.append(statusButton, deleteButton);
          row.append(actions);
          output.append(row);
        }
        output.dataset.hasActiveDocuments = String(hasActiveDocuments);
      } catch (error) {
        output.dataset.hasActiveDocuments = "false";
        showResult(output, null, error.message);
      } finally {
        refreshingDocuments = false;
      }
    }

    document.getElementById("refresh-documents").addEventListener("click", refreshDocuments);
    document.getElementById("previous-documents").addEventListener("click", () => {
      if (currentDocumentPage > 0) {
        currentDocumentPage -= 1;
        refreshDocuments();
      }
    });
    document.getElementById("next-documents").addEventListener("click", () => {
      currentDocumentPage += 1;
      refreshDocuments();
    });
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

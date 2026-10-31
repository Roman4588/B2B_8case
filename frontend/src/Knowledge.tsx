import { useRef, useState } from "react";
import {
  FileText,
  Plus,
  RefreshCw,
  Search,
  UploadCloud,
  X,
  Trash2,
} from "lucide-react";
import { api, useResource } from "./api";
import type { Job, Runbook } from "./types";
import { categoryNames, Empty, jobNames } from "./ui";
import { ShowMore } from "./ShowMore";

export function Knowledge({ canDelete = false }: { canDelete?: boolean }) {
  const [deleting, setDeleting] = useState<{
    kind: "book" | "job";
    id: string;
    name: string;
  } | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [visibleBooks, setVisibleBooks] = useState(10);
  const [visibleJobs, setVisibleJobs] = useState(10);
  const [editing, setEditing] = useState<Runbook | null | undefined>(undefined);
  const [notice, setNotice] = useState("");
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const dragDepth = useRef(0);
  const uploadBusy = useRef(false);
  const books = useResource<{ items: Runbook[]; semantic: boolean }>(
    "/runbooks?q=" + encodeURIComponent(query),
  );
  const jobs = useResource<Job[]>("/jobs");
  function askDelete(kind: "book" | "job", id: string, name: string) {
    setDeleteError("");
    setDeleting({ kind, id, name });
  }
  async function remove() {
    if (!deleting || deleteBusy) return;
    setDeleteBusy(true);
    setDeleteError("");
    try {
      const result = await api<{
        deleted_instructions: number;
        file_cleanup_pending?: boolean;
      }>((deleting.kind === "book" ? "/runbooks/" : "/jobs/") + deleting.id, {
        method: "DELETE",
      });
      books.refresh();
      jobs.refresh();
      setEditing(undefined);
      setDeleting(null);
      setNotice(
        result.file_cleanup_pending
          ? "Инструкции удалены. Очистка исходного файла не завершена — сообщите администратору."
          : `Удалено инструкций: ${result.deleted_instructions}. Изменение записано в журнал.`,
      );
    } catch (e) {
      setDeleteError((e as Error).message);
    } finally {
      setDeleteBusy(false);
    }
  }
  async function upload(file: File) {
    if (uploadBusy.current) return;
    if (!/\.(json|md|txt|pdf|docx)$/i.test(file.name)) {
      setNotice("Поддерживаются JSON, MD, TXT, PDF и DOCX.");
      return;
    }
    if (file.size > 25 * 1024 * 1024) {
      setNotice("Размер документа не должен превышать 25 МБ.");
      return;
    }
    uploadBusy.current = true;
    setUploading(true);
    setNotice("");
    const body = new FormData();
    body.append("file", file);
    try {
      await api("/runbooks/import", { method: "POST", body });
      jobs.refresh();
      setNotice(
        "Документ принят. Обработка продолжится, даже если вы закроете страницу.",
      );
    } catch (e) {
      setNotice((e as Error).message);
    } finally {
      uploadBusy.current = false;
      setUploading(false);
    }
  }
  async function retryJob(id: string) {
    try {
      await api("/jobs/" + id + "/retry", { method: "POST" });
      jobs.refresh();
    } catch (e) {
      setNotice((e as Error).message);
    }
  }
  return (
    <div className="knowledge-screen">
      <div className="section-heading">
        <div>
          <h2>
            Инструкции{" "}
            <span className="count">{books.data?.items.length ?? "—"}</span>
          </h2>
          <p>Проверенные инструкции вашей команды</p>
        </div>
        <button className="primary" onClick={() => setEditing(null)}>
          <Plus size={17} />
          Добавить инструкцию
        </button>
      </div>
      <div
        className={"knowledge-intro" + (dragging ? " drag-over" : "")}
        onDragEnter={(e) => {
          if (!e.dataTransfer.types.includes("Files")) return;
          e.preventDefault();
          dragDepth.current += 1;
          setDragging(true);
        }}
        onDragOver={(e) => {
          if (!e.dataTransfer.types.includes("Files")) return;
          e.preventDefault();
          e.dataTransfer.dropEffect = uploadBusy.current ? "none" : "copy";
        }}
        onDragLeave={() => {
          dragDepth.current = Math.max(0, dragDepth.current - 1);
          if (!dragDepth.current) setDragging(false);
        }}
        onDrop={(e) => {
          if (!e.dataTransfer.types.includes("Files")) return;
          e.preventDefault();
          dragDepth.current = 0;
          setDragging(false);
          if (e.dataTransfer.files.length !== 1) {
            setNotice("Перетащите один документ за раз.");
            return;
          }
          void upload(e.dataTransfer.files[0]);
        }}
      >
        <div>
          <h3>Импорт инструкций</h3>
          <p>
            Перетащите документ в эту область или выберите файл. Ассистент
            найдёт подходящий по смыслу события на русском и английском.
          </p>
        </div>
        <label className={"upload-button " + (uploading ? "disabled" : "")}>
          <UploadCloud size={23} />
          <strong>{uploading ? "Загрузка…" : "Загрузить документ"}</strong>
          <span>
            <abbr title="Поддерживаемые форматы документов">
              JSON, MD, TXT, PDF, DOCX
            </abbr>
            , до 25 МБ
          </span>
          <input
            type="file"
            accept=".json,.md,.txt,.pdf,.docx"
            disabled={uploading}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void upload(file);
              e.target.value = "";
            }}
          />
        </label>
      </div>
      {notice && (
        <div className="hint" role="status">
          {notice}
        </div>
      )}
      {!!jobs.data?.length && (
        <section className="jobs" id="knowledge-import-list">
          <h3>Обработка документов</h3>
          {jobs.data.slice(0, visibleJobs).map((job) => (
            <div className="job" key={job.id}>
              <FileText size={18} />
              <span>
                <strong>{job.filename}</strong>
                <small>
                  {job.error ||
                    `${job.progress} / ${job.total || "…"} инструкций`}
                </small>
              </span>
              <span className={"job-status " + job.status}>
                {jobNames[job.status]}
              </span>
              {job.status === "failed" && (
                <button
                  className="icon-button"
                  aria-label="Повторить импорт"
                  onClick={() => void retryJob(job.id)}
                >
                  <RefreshCw size={16} />
                </button>
              )}
              {canDelete && (
                <button
                  className="icon-button"
                  aria-label={"Удалить документ " + job.filename}
                  disabled={job.status === "running"}
                  title={
                    job.status === "running"
                      ? "Дождитесь завершения обработки"
                      : "Удалить файл и все его инструкции"
                  }
                  onClick={() => askDelete("job", job.id, job.filename)}
                >
                  <Trash2 size={16} />
                </button>
              )}
            </div>
          ))}
          <ShowMore
            shown={visibleJobs}
            total={jobs.data.length}
            onMore={() => setVisibleJobs((n) => n + 10)}
            label="Показать ещё документы"
            controls="knowledge-import-list"
          />
        </section>
      )}
      <form
        className="knowledge-search"
        onSubmit={(e) => {
          e.preventDefault();
          setVisibleBooks(10);
          setQuery(q);
        }}
      >
        <label className="search">
          <Search size={18} />
          <input
            placeholder="Опишите проблему — поиск по смыслу"
            aria-label="Поиск регламентов"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </label>
        <button className="secondary">Найти</button>
        {query && (
          <button
            type="button"
            className="text-button"
            onClick={() => {
              setQuery("");
              setQ("");
              setVisibleBooks(10);
            }}
          >
            Сбросить
          </button>
        )}
      </form>
      {books.error && (
        <div className="error" role="alert">
          {books.error}
        </div>
      )}
      {!books.data && !books.error && (
        <div className="loading" role="status">
          {query
            ? "Ищем инструкции по смыслу. При первом поиске запускается локальная модель…"
            : "Загружаем базу знаний…"}
        </div>
      )}
      {books.data?.items.length === 0 && (
        <Empty
          title="Инструкции не найдены"
          description="Добавьте новый регламент или попробуйте другое описание проблемы."
        />
      )}
      <div className="book-grid" id="knowledge-book-list">
        {books.data?.items.slice(0, visibleBooks).map((book) => (
          <article className="book" key={book.id}>
            <h3>{book.title}</h3>
            <header>
              <span className="category-label">
                {categoryNames[book.category]}
              </span>
              <span className={"job-status " + (book.status || "ready")}>
                {book.status
                  ? jobNames[book.status]
                  : `${Math.round((book.similarity || 0) * 100)}% сходства`}
              </span>
            </header>
            <p>{book.condition}</p>
            <div className="book-steps">
              <span>{book.steps.length} шага</span>
              <span>Редакция {book.revision || 1}</span>
            </div>
            {book.error && (
              <div className="error">
                {book.error}
                <button
                  onClick={() => {
                    void api("/runbooks/" + book.id + "/retry", {
                      method: "POST",
                    })
                      .then(books.refresh)
                      .catch((e) => setNotice(e.message));
                  }}
                >
                  Повторить
                </button>
              </div>
            )}
            <footer>
              <span>{book.source}</span>
              <button className="text-button" onClick={() => setEditing(book)}>
                Открыть
              </button>
              {canDelete && (
                <button
                  className="text-button"
                  aria-label={"Удалить инструкцию " + book.title}
                  onClick={() => askDelete("book", book.id, book.title)}
                >
                  Удалить
                </button>
              )}
            </footer>
          </article>
        ))}
      </div>
      <ShowMore
        shown={visibleBooks}
        total={books.data?.items.length ?? 0}
        onMore={() => setVisibleBooks((n) => n + 10)}
        label="Показать ещё инструкции"
        controls="knowledge-book-list"
      />
      {editing !== undefined && (
        <BookEditor
          book={editing}
          onClose={() => setEditing(undefined)}
          onSaved={() => {
            setEditing(undefined);
            books.refresh();
          }}
        />
      )}
      {deleting && (
        <div
          className="confirm-access"
          role="dialog"
          aria-modal="true"
          aria-labelledby="delete-instruction-title"
          onKeyDown={(e) => {
            if (e.key === "Escape" && !deleteBusy) setDeleting(null);
          }}
        >
          <section className="account-panel">
            <h2 id="delete-instruction-title">
              {deleting.kind === "job"
                ? "Удалить документ?"
                : "Удалить инструкцию?"}
            </h2>
            <p>{deleting.name}</p>
            <p>
              {deleting.kind === "job"
                ? "Будут удалены исходный файл и все инструкции из этого импорта."
                : "Инструкция исчезнет из базы знаний и поиска."}{" "}
              Восстановить удаление нельзя. Запись в журнале сохранится.
            </p>
            {deleteError && (
              <div className="error" role="alert">
                {deleteError}
              </div>
            )}
            <div className="dialog-actions">
              <button
                className="secondary"
                autoFocus
                disabled={deleteBusy}
                onClick={() => setDeleting(null)}
              >
                Отмена
              </button>
              <button
                className="primary"
                disabled={deleteBusy}
                onClick={() => void remove()}
              >
                {deleteBusy ? "Удаление…" : "Удалить"}
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

function BookEditor({
  book,
  onClose,
  onSaved,
}: {
  book: Runbook | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [title, setTitle] = useState(book?.title || "");
  const [condition, setCondition] = useState(book?.condition || "");
  const [steps, setSteps] = useState(book?.steps.join("\n") || "");
  const [cautions, setCautions] = useState(book?.cautions || "");
  const [category, setCategory] = useState(book?.category || "server");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function save() {
    setBusy(true);
    try {
      await api("/runbooks" + (book ? "/" + book.id : ""), {
        method: book ? "PATCH" : "POST",
        body: JSON.stringify({
          title,
          condition,
          steps: steps
            .split("\n")
            .map((s) => s.trim())
            .filter(Boolean),
          cautions,
          category,
        }),
      });
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="modal-overlay knowledge-editor-overlay" onClick={onClose}>
      <section
        className="modal knowledge-editor"
        role="dialog"
        aria-modal="true"
        aria-label="Инструкция"
        onClick={(e) => e.stopPropagation()}
      >
        <header>
          <h2>{book ? "Редактировать инструкцию" : "Новая инструкция"}</h2>
          <button
            className="icon-button"
            aria-label="Закрыть форму"
            onClick={onClose}
          >
            <X size={20} />
          </button>
        </header>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void save();
          }}
        >
          <label>
            Название
            <input
              required
              maxLength={200}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </label>
          <label>
            Если: описание события
            <textarea
              required
              minLength={3}
              value={condition}
              onChange={(e) => setCondition(e.target.value)}
            />
          </label>
          <label>
            Действия: каждый шаг с новой строки
            <textarea
              required
              rows={6}
              value={steps}
              onChange={(e) => setSteps(e.target.value)}
            />
          </label>
          <label>
            Предостережения
            <textarea
              value={cautions}
              onChange={(e) => setCautions(e.target.value)}
            />
          </label>
          <label>
            Категория
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value as typeof category)}
            >
              {Object.entries(categoryNames).map(([key, name]) => (
                <option key={key} value={key}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          {error && (
            <div className="error" role="alert">
              {error}
            </div>
          )}
          <footer>
            <button type="button" className="secondary" onClick={onClose}>
              Отмена
            </button>
            <button className="primary" disabled={busy}>
              {busy ? "Сохраняем…" : "Сохранить и индексировать"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  );
}

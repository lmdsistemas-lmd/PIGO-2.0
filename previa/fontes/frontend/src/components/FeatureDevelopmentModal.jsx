import { useEffect } from "react";
import "../styles/feature-development-modal.css";

function FeatureDevelopmentModal({
  open,
  title = "Funcionalidade em Desenvolvimento",
  message = "",
  icon = "🚧",
  onClose,
}) {
  useEffect(() => {
    if (!open) {
      return undefined;
    }

    function handleKeyDown(event) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  const paragraphs = Array.isArray(message)
    ? message
    : String(message || "")
        .split("\n")
        .map((item) => item.trim())
        .filter(Boolean);

  return (
    <div
      className="feature-dev-modal-overlay"
      onClick={onClose}
      role="presentation"
    >
      <section
        className="feature-dev-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="feature-dev-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="feature-dev-modal-icon" aria-hidden="true">
          {icon}
        </div>

        <div className="feature-dev-modal-content">
          <h2 id="feature-dev-modal-title">{title}</h2>
          {paragraphs.map((paragraph) => (
            <p key={paragraph}>{paragraph}</p>
          ))}
        </div>

        <div className="feature-dev-modal-actions">
          <button
            type="button"
            className="feature-dev-modal-primary"
            onClick={onClose}
          >
            Fechar
          </button>
        </div>
      </section>
    </div>
  );
}

export default FeatureDevelopmentModal;

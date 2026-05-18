import { useEffect, useRef, useState } from "react";

function IconSearch() {
  return (
    <svg viewBox="0 0 24 24" style={styles.iconSvg} aria-hidden="true">
      <path
        d="M15.5 14h-.79l-.28-.27A6.47 6.47 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16a6.47 6.47 0 0 0 4.23-1.57l.27.28v.79L20 21.5 21.5 20 15.5 14zM9.5 14A4.5 4.5 0 1 1 14 9.5 4.5 4.5 0 0 1 9.5 14z"
        fill="currentColor"
      />
    </svg>
  );
}

function IconFilter() {
  return (
    <svg viewBox="0 0 24 24" style={styles.iconSvg} aria-hidden="true">
      <path
        d="M3 5h18v2l-7 7v5l-4-2v-3L3 7V5z"
        fill="currentColor"
      />
    </svg>
  );
}

function IconSort() {
  return (
    <svg viewBox="0 0 24 24" style={styles.iconSvg} aria-hidden="true">
      <path
        d="M7 6h10v2H7V6zm3 5h7v2h-7v-2zm4 5h3v2h-3v-2zM5 18V6H3v12H1l3 4 3-4H5z"
        fill="currentColor"
      />
    </svg>
  );
}

function IconPlus() {
  return (
    <svg viewBox="0 0 24 24" style={styles.iconSvg} aria-hidden="true">
      <path d="M19 11h-6V5h-2v6H5v2h6v6h2v-6h6v-2z" fill="currentColor" />
    </svg>
  );
}

function Popover({
  aberto,
  titulo,
  opcoes,
  valor,
  onSelecionar,
  onFechar,
  placeholder = "Todos",
}) {
  if (!aberto) return null;

  return (
    <div style={styles.popover}>
      <div style={styles.popoverTitle}>{titulo}</div>

      <button
        type="button"
        style={{
          ...styles.optionButton,
          ...(valor === "" ? styles.optionButtonActive : {}),
        }}
        onClick={() => {
          onSelecionar("");
          onFechar();
        }}
      >
        {placeholder}
      </button>

      {opcoes.map((opcao) => (
        <button
          key={opcao.value}
          type="button"
          style={{
            ...styles.optionButton,
            ...(valor === opcao.value ? styles.optionButtonActive : {}),
          }}
          onClick={() => {
            onSelecionar(opcao.value);
            onFechar();
          }}
        >
          {opcao.label}
        </button>
      ))}
    </div>
  );
}

function PopoverOrdenacao({
  aberto,
  valor,
  onSelecionar,
  onFechar,
  opcoesOrdenacao,
}) {
  if (!aberto) return null;

  return (
    <div style={styles.popover}>
      <div style={styles.popoverTitle}>Ordenar por</div>

      {opcoesOrdenacao.map((opcao) => (
        <button
          key={opcao.value}
          type="button"
          style={{
            ...styles.optionButton,
            ...(valor === opcao.value ? styles.optionButtonActive : {}),
          }}
          onClick={() => {
            onSelecionar(opcao.value);
            onFechar();
          }}
        >
          {opcao.label}
        </button>
      ))}
    </div>
  );
}

export default function Toolbar({
  search,
  setSearch,
  onNovo,
  filtroDepartamento,
  setFiltroDepartamento,
  opcoesDepartamentos = [],
  filtroSetor,
  setFiltroSetor,
  opcoesSetores = [],
  ordenacao,
  setOrdenacao,
}) {
  const [menuAberto, setMenuAberto] = useState("");
  const containerRef = useRef(null);

  const opcoesOrdenacao = [
    { value: "nome_asc", label: "Nome (A → Z)" },
    { value: "nome_desc", label: "Nome (Z → A)" },
    { value: "status_asc", label: "Status (A → Z)" },
    { value: "departamento_asc", label: "Departamento (A → Z)" },
    { value: "setor_asc", label: "Setor (A → Z)" },
  ];

  useEffect(() => {
    function handleClickFora(evento) {
      if (containerRef.current && !containerRef.current.contains(evento.target)) {
        setMenuAberto("");
      }
    }

    document.addEventListener("mousedown", handleClickFora);
    return () => document.removeEventListener("mousedown", handleClickFora);
  }, []);

  function obterLabelOrdenacao() {
    const encontrada = opcoesOrdenacao.find((item) => item.value === ordenacao);
    return encontrada ? encontrada.label : "Nome";
  }

  return (
    <div style={styles.wrapper} ref={containerRef}>
      <div style={styles.leftGroup}>
        <div style={styles.searchBox}>
          <span style={styles.searchIcon}>
            <IconSearch />
          </span>

          <input
            type="text"
            placeholder="Pesquisar colaborador"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={styles.input}
          />
        </div>

        <div style={styles.filterArea}>
          <button
            type="button"
            style={styles.filterButton}
            onClick={() =>
              setMenuAberto((atual) =>
                atual === "departamento" ? "" : "departamento"
              )
            }
          >
            <span style={styles.buttonIcon}>
              <IconFilter />
            </span>
            <span>Departamentos</span>
          </button>

          <Popover
            aberto={menuAberto === "departamento"}
            titulo="Filtrar por departamento"
            opcoes={opcoesDepartamentos}
            valor={filtroDepartamento}
            onSelecionar={setFiltroDepartamento}
            onFechar={() => setMenuAberto("")}
            placeholder="Todos os departamentos"
          />
        </div>

        <div style={styles.filterArea}>
          <button
            type="button"
            style={styles.filterButton}
            onClick={() =>
              setMenuAberto((atual) => (atual === "setor" ? "" : "setor"))
            }
          >
            <span style={styles.buttonIcon}>
              <IconFilter />
            </span>
            <span>Setores</span>
          </button>

          <Popover
            aberto={menuAberto === "setor"}
            titulo="Filtrar por setor"
            opcoes={opcoesSetores}
            valor={filtroSetor}
            onSelecionar={setFiltroSetor}
            onFechar={() => setMenuAberto("")}
            placeholder="Todos os setores"
          />
        </div>
      </div>

      <div style={styles.rightGroup}>
        <div style={styles.filterArea}>
          <button
            type="button"
            style={styles.orderButton}
            onClick={() =>
              setMenuAberto((atual) => (atual === "ordenacao" ? "" : "ordenacao"))
            }
          >
            <span style={styles.orderLabel}>Ordem:</span>
            <span style={styles.orderValue}>{obterLabelOrdenacao()}</span>
            <span style={styles.buttonIcon}>
              <IconSort />
            </span>
          </button>

          <PopoverOrdenacao
            aberto={menuAberto === "ordenacao"}
            valor={ordenacao}
            onSelecionar={setOrdenacao}
            onFechar={() => setMenuAberto("")}
            opcoesOrdenacao={opcoesOrdenacao}
          />
        </div>

        <button type="button" onClick={onNovo} style={styles.primaryButton}>
          <span style={styles.buttonIcon}>
            <IconPlus />
          </span>
          <span>Novo vínculo</span>
        </button>
      </div>
    </div>
  );
}

const styles = {
  wrapper: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: "16px",
    flexWrap: "wrap",
    position: "relative",
    zIndex: 2,
  },

  leftGroup: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    flexWrap: "wrap",
    flex: 1,
    minWidth: "280px",
  },

  rightGroup: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    flexWrap: "wrap",
  },

  searchBox: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    backgroundColor: "#ffffff",
    border: "1px solid #e5e7eb",
    borderRadius: "12px",
    padding: "0 12px",
    minWidth: "260px",
    flex: 1,
    maxWidth: "380px",
    height: "44px",
    boxSizing: "border-box",
    boxShadow: "0 4px 14px rgba(15, 23, 42, 0.04)",
  },

  searchIcon: {
    width: "16px",
    height: "16px",
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    color: "#9ca3af",
    flexShrink: 0,
  },

  input: {
    border: "none",
    outline: "none",
    backgroundColor: "transparent",
    width: "100%",
    fontSize: "14px",
    color: "#374151",
  },

  filterArea: {
    position: "relative",
  },

  filterButton: {
    height: "44px",
    padding: "0 14px",
    border: "1px solid #dbeafe",
    borderRadius: "12px",
    backgroundColor: "#ffffff",
    color: "#374151",
    fontSize: "13px",
    fontWeight: "600",
    display: "flex",
    alignItems: "center",
    gap: "8px",
    cursor: "pointer",
    boxShadow: "0 4px 14px rgba(15, 23, 42, 0.04)",
  },

  orderButton: {
    height: "44px",
    padding: "0 14px",
    border: "1px solid #dbeafe",
    borderRadius: "12px",
    backgroundColor: "#ffffff",
    color: "#374151",
    fontSize: "13px",
    fontWeight: "600",
    display: "flex",
    alignItems: "center",
    gap: "8px",
    cursor: "pointer",
    boxShadow: "0 4px 14px rgba(15, 23, 42, 0.04)",
  },

  primaryButton: {
    height: "44px",
    padding: "0 18px",
    border: "none",
    borderRadius: "12px",
    backgroundColor: "#60a5fa",
    color: "#ffffff",
    fontWeight: "700",
    fontSize: "14px",
    display: "flex",
    alignItems: "center",
    gap: "8px",
    cursor: "pointer",
    boxShadow: "0 8px 18px rgba(96, 165, 250, 0.28)",
  },

  orderLabel: {
    color: "#6b7280",
    fontWeight: "600",
  },

  orderValue: {
    color: "#1f2937",
    fontWeight: "700",
  },

  popover: {
    position: "absolute",
    top: "52px",
    left: 0,
    minWidth: "240px",
    maxWidth: "280px",
    backgroundColor: "#ffffff",
    border: "1px solid #e5e7eb",
    borderRadius: "14px",
    boxShadow: "0 16px 32px rgba(15, 23, 42, 0.12)",
    padding: "10px",
    display: "flex",
    flexDirection: "column",
    gap: "6px",
  },

  popoverTitle: {
    fontSize: "12px",
    fontWeight: "700",
    color: "#6b7280",
    padding: "6px 8px 8px 8px",
    borderBottom: "1px solid #f1f5f9",
    marginBottom: "4px",
  },

  optionButton: {
    border: "none",
    backgroundColor: "#ffffff",
    color: "#374151",
    textAlign: "left",
    padding: "10px 12px",
    borderRadius: "10px",
    cursor: "pointer",
    fontSize: "13px",
    fontWeight: "600",
  },

  optionButtonActive: {
    backgroundColor: "#eff6ff",
    color: "#2563eb",
  },

  buttonIcon: {
    width: "16px",
    height: "16px",
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
  },

  iconSvg: {
    width: "16px",
    height: "16px",
    display: "block",
    color: "currentColor",
  },
};
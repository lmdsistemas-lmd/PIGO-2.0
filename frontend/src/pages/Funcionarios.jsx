import { useEffect, useMemo, useState } from "react";
import Topbar from "../components/Topbar";
import FuncionarioCard from "../components/FuncionarioCard";
import api from "../services/api";
import "../styles/dashboard.css";
import "../styles/topbar.css";
import "../styles/funcionarios.css";

function Funcionarios({ onToggleSidebar, isMobileOrTablet, theme, toggleTheme }) {
  const [funcionarios, setFuncionarios] = useState([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState("");
  const [pesquisa, setPesquisa] = useState("");
  const [ordemSelecionada, setOrdemSelecionada] = useState("nome");

  useEffect(() => {
    async function carregarFuncionarios() {
      try {
        setLoading(true);
        setErro("");

        const response = await api.get("/funcionarios/");
        const dados = Array.isArray(response.data) ? response.data : [];

        const funcionariosFormatados = dados.map((item) => ({
          pes_id: item.pes_id,
          col_pessoa: item.col_pessoa,
          nome: item.nome || "FUNCIONÁRIO SEM NOME",
          cargo_oficial: item.cargo_oficial || "Não informado",
          departamento_nome: item.departamento_nome || "Não informado",
          status:
            item.status && item.status.trim() !== ""
              ? item.status
              : "Sem status",
        }));

        setFuncionarios(funcionariosFormatados);
      } catch (error) {
        console.error("Erro ao carregar funcionários:", error);
        setErro("Não foi possível carregar os funcionários da API.");
      } finally {
        setLoading(false);
      }
    }

    carregarFuncionarios();
  }, []);

  const funcionariosFiltradosEOrdenados = useMemo(() => {
    let resultado = [...funcionarios];

    if (pesquisa.trim() !== "") {
      const texto = pesquisa.toLowerCase();

      resultado = resultado.filter((funcionario) => {
        const nome = String(funcionario.nome || "").toLowerCase();
        const idErp = String(funcionario.col_pessoa || "").toLowerCase();
        const cargo = String(funcionario.cargo_oficial || "").toLowerCase();
        const status = String(funcionario.status || "").toLowerCase();

        return (
          nome.includes(texto) ||
          idErp.includes(texto) ||
          cargo.includes(texto) ||
          status.includes(texto)
        );
      });
    }

    if (ordemSelecionada === "nome") {
      resultado.sort((a, b) =>
        String(a.nome || "").localeCompare(String(b.nome || ""), "pt-BR")
      );
    }

    if (ordemSelecionada === "idErp") {
      resultado.sort(
        (a, b) => Number(a.col_pessoa || 0) - Number(b.col_pessoa || 0)
      );
    }

    return resultado;
  }, [funcionarios, pesquisa, ordemSelecionada]);

  return (
    <div className="funcionarios-page">
      <Topbar 
        titulo="Funcionários" 
        subtitulo="Gestão de pessoas e colaboradores"
        onToggleSidebar={onToggleSidebar}
        isMobileOrTablet={isMobileOrTablet}
        theme={theme}
        toggleTheme={toggleTheme}
      />

      <div className="funcionarios-toolbar">
        <div className="funcionarios-toolbar-left">
          <input
            type="text"
            placeholder="🔎 Buscar por nome, cargo ou status..."
            className="funcionarios-search"
            value={pesquisa}
            onChange={(e) => setPesquisa(e.target.value)}
          />
        </div>

        <div className="funcionarios-toolbar-right">
          <div className="funcionarios-ordem-box">
            <span>Ordenar por:</span>
            <select
              className="funcionarios-select"
              value={ordemSelecionada}
              onChange={(e) => setOrdemSelecionada(e.target.value)}
            >
              <option value="nome">🔤 Nome</option>
              <option value="idErp">🔢 ID ERP</option>
            </select>
          </div>
        </div>
      </div>

      {loading && (
        <div className="funcionarios-mensagem">
          Carregando funcionários...
        </div>
      )}

      {!loading && erro && (
        <div className="funcionarios-mensagem erro">
          {erro}
        </div>
      )}

      {!loading && !erro && funcionariosFiltradosEOrdenados.length === 0 && (
        <div className="funcionarios-mensagem">
          Nenhum funcionário encontrado.
        </div>
      )}

      {!loading && !erro && funcionariosFiltradosEOrdenados.length > 0 && (
        <>
          <div className="funcionarios-grid">
            {funcionariosFiltradosEOrdenados.map((funcionario) => (
              <FuncionarioCard
                key={funcionario.col_pessoa}
                funcionario={funcionario}
              />
            ))}
          </div>

          <div className="funcionarios-footer">
            <div className="funcionarios-resultados">
              Mostrando {funcionariosFiltradosEOrdenados.length} resultado(s)
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default Funcionarios;

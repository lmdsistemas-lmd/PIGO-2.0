import { useNavigate } from "react-router-dom";

function FuncionarioCard({ funcionario }) {
  const navigate = useNavigate();

  const nome = funcionario?.nome || "Funcionário sem nome";
  const funcionarioId = funcionario?.pes_id || funcionario?.col_pessoa;
  const idErp = funcionario?.col_pessoa || "-";
  const cargoOficial = funcionario?.cargo_oficial || "Não informado";
  const status = funcionario?.status || "Sem status";

  function abrirAnalise() {
    if (!funcionarioId) {
      alert("Funcionário inválido para análise.");
      return;
    }

    const origin = funcionario?.origem || (funcionario?.usuario_id ? 'usuario_erp' : 'colaborador');
    navigate(`/funcionarios/${encodeURIComponent(funcionarioId)}/analise?origem=${origin}`);
  }


  const primeiraLetra = nome.charAt(0).toUpperCase();
  const isActive = status.toLowerCase().includes("ativo") || status.toLowerCase().includes("trabalhando");

  return (
    <div className="funcionario-card">
      <div className="funcionario-header">
        <div className="funcionario-avatar-wrapper">
          <div className="funcionario-avatar">{primeiraLetra}</div>
          <div className={`funcionario-status-badge ${isActive ? '' : 'inativo'}`} />
        </div>
        <div className="funcionario-nome">{nome}</div>
        <div className="funcionario-id">ERP #{idErp}</div>
      </div>

      <div className="funcionario-info-box">
        <div className="funcionario-info-row">
          <span className="funcionario-label">Cargo</span>
          <span className="funcionario-value">{cargoOficial}</span>
        </div>

        <div className="funcionario-info-row">
          <span className="funcionario-label">Status</span>
          <span className="funcionario-value">{status}</span>
        </div>
      </div>

      <div className="funcionario-tags">
        <button
          type="button"
          className="tag-button tag-button-blue"
          onClick={abrirAnalise}
        >
          🔍 Ver Análise
        </button>
      </div>
    </div>
  );
}

export default FuncionarioCard;

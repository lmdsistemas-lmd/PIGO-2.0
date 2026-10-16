import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import Topbar from "../components/Topbar";
import {
  criarCargo,
  criarDepartamento,
  criarFuncionario,
  excluirCargo,
  excluirDepartamento,
  listarCargos,
  listarColaboradoresERPDisponiveis,
  listarDepartamentos,
  atualizarCargo,
  atualizarDepartamento,
} from "../services/funcionariosService";
import "../styles/dashboard.css";
import "../styles/topbar.css";
import "../styles/funcionarios.css";

function FuncionarioNovoVinculo({ onToggleSidebar, isMobileOrTablet, theme, toggleTheme }) {
  const navigate = useNavigate();

  const [abaAtiva, setAbaAtiva] = useState("vinculo");

  const [pesquisa, setPesquisa] = useState("");
  const [colaboradores, setColaboradores] = useState([]);
  const [colaboradorSelecionado, setColaboradorSelecionado] = useState(null);

  const [departamentos, setDepartamentos] = useState([]);
  const [cargos, setCargos] = useState([]);

  const [departamentoId, setDepartamentoId] = useState("");
  const [cargoId, setCargoId] = useState("");

  const [novoCargo, setNovoCargo] = useState("");
  const [cargoEdicaoId, setCargoEdicaoId] = useState(null);
  const [cargoEdicaoNome, setCargoEdicaoNome] = useState("");

  const [novoDepartamento, setNovoDepartamento] = useState("");
  const [departamentoEdicaoId, setDepartamentoEdicaoId] = useState(null);
  const [departamentoEdicaoNome, setDepartamentoEdicaoNome] = useState("");

  const [loadingInicial, setLoadingInicial] = useState(true);
  const [loadingColaboradores, setLoadingColaboradores] = useState(false);
  const [salvandoVinculo, setSalvandoVinculo] = useState(false);
  const [salvandoCargo, setSalvandoCargo] = useState(false);
  const [salvandoDepartamento, setSalvandoDepartamento] = useState(false);

  const [erro, setErro] = useState("");
  const [sucesso, setSucesso] = useState("");

  async function carregarListasBase() {
    const [departamentosData, cargosData] = await Promise.all([
      listarDepartamentos(),
      listarCargos(),
    ]);

    setDepartamentos(Array.isArray(departamentosData) ? departamentosData : []);
    setCargos(Array.isArray(cargosData) ? cargosData : []);
  }

  async function carregarColaboradores(search = "") {
    setLoadingColaboradores(true);
    try {
      const data = await listarColaboradoresERPDisponiveis(search);
      setColaboradores(Array.isArray(data) ? data : []);
    } finally {
      setLoadingColaboradores(false);
    }
  }

  useEffect(() => {
    async function carregarDadosIniciais() {
      try {
        setLoadingInicial(true);
        setErro("");
        setSucesso("");

        await Promise.all([carregarListasBase(), carregarColaboradores("")]);
      } catch (error) {
        console.error("Erro ao carregar dados iniciais:", error);
        setErro("Não foi possível carregar os dados da tela.");
      } finally {
        setLoadingInicial(false);
      }
    }

    carregarDadosIniciais();
  }, []);

  useEffect(() => {
    const timeout = setTimeout(() => {
      carregarColaboradores(pesquisa).catch((error) => {
        console.error("Erro ao pesquisar colaboradores:", error);
      });
    }, 350);

    return () => clearTimeout(timeout);
  }, [pesquisa]);

  const colaboradorLabel = useMemo(() => {
    if (!colaboradorSelecionado) {
      return "Nenhum colaborador selecionado";
    }

    return `${colaboradorSelecionado.nome} • ID ERP ${colaboradorSelecionado.col_pessoa}`;
  }, [colaboradorSelecionado]);

  async function salvarVinculo() {
    if (!colaboradorSelecionado) {
      setErro("Selecione um colaborador do ERP.");
      return;
    }

    if (!departamentoId) {
      setErro("Selecione um departamento.");
      return;
    }

    try {
      setSalvandoVinculo(true);
      setErro("");
      setSucesso("");

      await criarFuncionario({
        col_pessoa: Number(colaboradorSelecionado.col_pessoa),
        departamento_id: Number(departamentoId),
        cargo_id: cargoId === "" ? null : Number(cargoId),
      });

      setSucesso("Vínculo criado com sucesso.");
      setColaboradorSelecionado(null);
      setDepartamentoId("");
      setCargoId("");

      await carregarColaboradores(pesquisa);

      setTimeout(() => {
        navigate("/funcionarios");
      }, 800);
    } catch (error) {
      console.error("Erro ao criar vínculo:", error);
      const mensagem =
        error?.response?.data?.detail ||
        "Não foi possível criar o vínculo do funcionário.";
      setErro(String(mensagem));
    } finally {
      setSalvandoVinculo(false);
    }
  }

  async function salvarCargo() {
    if (!novoCargo.trim()) {
      setErro("Informe o nome do cargo.");
      return;
    }

    try {
      setSalvandoCargo(true);
      setErro("");
      setSucesso("");

      await criarCargo({ nome: novoCargo.trim() });
      setNovoCargo("");
      await carregarListasBase();
      setSucesso("Cargo cadastrado com sucesso.");
    } catch (error) {
      console.error("Erro ao cadastrar cargo:", error);
      const mensagem =
        error?.response?.data?.detail || "Não foi possível cadastrar o cargo.";
      setErro(String(mensagem));
    } finally {
      setSalvandoCargo(false);
    }
  }

  async function salvarEdicaoCargo() {
    if (!cargoEdicaoId || !cargoEdicaoNome.trim()) {
      setErro("Selecione um cargo e informe um nome válido.");
      return;
    }

    try {
      setSalvandoCargo(true);
      setErro("");
      setSucesso("");

      await atualizarCargo(cargoEdicaoId, { nome: cargoEdicaoNome.trim() });
      setCargoEdicaoId(null);
      setCargoEdicaoNome("");
      await carregarListasBase();
      setSucesso("Cargo atualizado com sucesso.");
    } catch (error) {
      console.error("Erro ao atualizar cargo:", error);
      const mensagem =
        error?.response?.data?.detail || "Não foi possível atualizar o cargo.";
      setErro(String(mensagem));
    } finally {
      setSalvandoCargo(false);
    }
  }

  async function removerCargo(id) {
    const confirmado = window.confirm("Deseja realmente excluir este cargo?");
    if (!confirmado) {
      return;
    }

    try {
      setErro("");
      setSucesso("");
      await excluirCargo(id);
      await carregarListasBase();
      setSucesso("Cargo excluído com sucesso.");
    } catch (error) {
      console.error("Erro ao excluir cargo:", error);
      const mensagem =
        error?.response?.data?.detail || "Não foi possível excluir o cargo.";
      setErro(String(mensagem));
    }
  }

  async function salvarDepartamento() {
    if (!novoDepartamento.trim()) {
      setErro("Informe o nome do departamento.");
      return;
    }

    try {
      setSalvandoDepartamento(true);
      setErro("");
      setSucesso("");

      await criarDepartamento({ nome: novoDepartamento.trim() });
      setNovoDepartamento("");
      await carregarListasBase();
      setSucesso("Departamento cadastrado com sucesso.");
    } catch (error) {
      console.error("Erro ao cadastrar departamento:", error);
      const mensagem =
        error?.response?.data?.detail ||
        "Não foi possível cadastrar o departamento.";
      setErro(String(mensagem));
    } finally {
      setSalvandoDepartamento(false);
    }
  }

  async function salvarEdicaoDepartamento() {
    if (!departamentoEdicaoId || !departamentoEdicaoNome.trim()) {
      setErro("Selecione um departamento e informe um nome válido.");
      return;
    }

    try {
      setSalvandoDepartamento(true);
      setErro("");
      setSucesso("");

      await atualizarDepartamento(departamentoEdicaoId, {
        nome: departamentoEdicaoNome.trim(),
      });

      setDepartamentoEdicaoId(null);
      setDepartamentoEdicaoNome("");
      await carregarListasBase();
      setSucesso("Departamento atualizado com sucesso.");
    } catch (error) {
      console.error("Erro ao atualizar departamento:", error);
      const mensagem =
        error?.response?.data?.detail ||
        "Não foi possível atualizar o departamento.";
      setErro(String(mensagem));
    } finally {
      setSalvandoDepartamento(false);
    }
  }

  async function removerDepartamento(id) {
    const confirmado = window.confirm(
      "Deseja realmente excluir este departamento?"
    );
    if (!confirmado) {
      return;
    }

    try {
      setErro("");
      setSucesso("");
      await excluirDepartamento(id);
      await carregarListasBase();
      setSucesso("Departamento excluído com sucesso.");
    } catch (error) {
      console.error("Erro ao excluir departamento:", error);
      const mensagem =
        error?.response?.data?.detail ||
        "Não foi possível excluir o departamento.";
      setErro(String(mensagem));
    }
  }

  return (
    <div className="dashboard-page">
      <Topbar
        titulo="Novo Vínculo"
        caminho="Funcionários / Novo Vínculo"
        onToggleSidebar={onToggleSidebar}
        isMobileOrTablet={isMobileOrTablet}
        theme={theme}
        toggleTheme={toggleTheme}
      />

      <div className="funcionario-tabs">
        <button
          type="button"
          className={`funcionario-tab ${abaAtiva === "vinculo" ? "active" : ""}`}
          onClick={() => setAbaAtiva("vinculo")}
        >
          Vincular colaborador
        </button>

        <button
          type="button"
          className={`funcionario-tab ${abaAtiva === "cargos" ? "active" : ""}`}
          onClick={() => setAbaAtiva("cargos")}
        >
          Cargos
        </button>

        <button
          type="button"
          className={`funcionario-tab ${
            abaAtiva === "departamentos" ? "active" : ""
          }`}
          onClick={() => setAbaAtiva("departamentos")}
        >
          Departamentos
        </button>
      </div>

      {erro && <div className="funcionarios-mensagem erro">{erro}</div>}
      {sucesso && <div className="funcionario-vinculo-sucesso">{sucesso}</div>}

      {abaAtiva === "vinculo" && (
        <div className="funcionario-vinculo-layout">
          <div className="funcionario-vinculo-box">
            <h3 className="funcionario-vinculo-titulo">Colaborador do ERP</h3>

            <div className="funcionario-vinculo-campo">
              <label>Pesquisar colaborador</label>
              <input
                type="text"
                className="funcionarios-search funcionario-vinculo-search"
                placeholder="Digite nome, CPF, cargo ou status"
                value={pesquisa}
                onChange={(e) => setPesquisa(e.target.value)}
              />
            </div>

            <div className="funcionario-vinculo-selecionado">
              <strong>Selecionado:</strong> {colaboradorLabel}
            </div>

            <div className="funcionario-vinculo-lista">
              {loadingInicial || loadingColaboradores ? (
                <div className="funcionarios-mensagem">
                  Carregando colaboradores...
                </div>
              ) : colaboradores.length === 0 ? (
                <div className="funcionarios-mensagem">
                  Nenhum colaborador disponível encontrado.
                </div>
              ) : (
                colaboradores.map((colaborador) => {
                  const ativo =
                    Number(colaboradorSelecionado?.col_pessoa || 0) ===
                    Number(colaborador.col_pessoa || 0);

                  return (
                    <button
                      key={colaborador.col_pessoa}
                      type="button"
                      className={`funcionario-vinculo-item ${
                        ativo ? "active" : ""
                      }`}
                      onClick={() => setColaboradorSelecionado(colaborador)}
                    >
                      <div className="funcionario-vinculo-item-top">
                        <strong>{colaborador.nome}</strong>
                        <span>ID ERP {colaborador.col_pessoa}</span>
                      </div>

                      <div className="funcionario-vinculo-item-info">
                        <span>CPF: {colaborador.cpf || "Não informado"}</span>
                        <span>
                          Cargo ERP: {colaborador.cargo_oficial || "Não informado"}
                        </span>
                        <span>Status: {colaborador.status || "Não informado"}</span>
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </div>

          <div className="funcionario-vinculo-box">
            <h3 className="funcionario-vinculo-titulo">Dados do RH</h3>

            <div className="funcionario-vinculo-campo">
              <label>Departamento</label>
              <select
                className="funcionarios-select funcionario-vinculo-select"
                value={departamentoId}
                onChange={(e) => setDepartamentoId(e.target.value)}
              >
                <option value="">Selecione um departamento</option>
                {departamentos.map((departamento) => (
                  <option key={departamento.id} value={departamento.id}>
                    {departamento.nome}
                  </option>
                ))}
              </select>
            </div>

            <div className="funcionario-vinculo-campo">
              <label>Cargo</label>
              <select
                className="funcionarios-select funcionario-vinculo-select"
                value={cargoId}
                onChange={(e) => setCargoId(e.target.value)}
              >
                <option value="">Selecione um cargo</option>
                {cargos.map((cargo) => (
                  <option key={cargo.id} value={cargo.id}>
                    {cargo.nome}
                  </option>
                ))}
              </select>
            </div>

            <div className="funcionario-vinculo-acoes">
              <button
                type="button"
                className="funcionario-vinculo-btn secundario"
                onClick={() => navigate("/funcionarios")}
              >
                Cancelar
              </button>

              <button
                type="button"
                className="funcionario-vinculo-btn primario"
                onClick={salvarVinculo}
                disabled={salvandoVinculo}
              >
                {salvandoVinculo ? "Salvando..." : "Salvar vínculo"}
              </button>
            </div>
          </div>
        </div>
      )}

      {abaAtiva === "cargos" && (
        <div className="cadastro-auxiliar-layout">
          <div className="funcionario-vinculo-box">
            <h3 className="funcionario-vinculo-titulo">Cadastrar cargo</h3>

            <div className="funcionario-vinculo-campo">
              <label>Nome do cargo</label>
              <input
                type="text"
                className="funcionarios-search funcionario-vinculo-search"
                value={novoCargo}
                onChange={(e) => setNovoCargo(e.target.value)}
                placeholder="Ex.: Supervisor Comercial"
              />
            </div>

            <div className="funcionario-vinculo-acoes">
              <button
                type="button"
                className="funcionario-vinculo-btn primario"
                onClick={salvarCargo}
                disabled={salvandoCargo}
              >
                {salvandoCargo ? "Salvando..." : "Cadastrar cargo"}
              </button>
            </div>
          </div>

          <div className="funcionario-vinculo-box">
            <h3 className="funcionario-vinculo-titulo">Editar cargos</h3>

            <div className="cadastro-auxiliar-lista">
              {cargos.map((cargo) => {
                const emEdicao = cargoEdicaoId === cargo.id;

                return (
                  <div className="cadastro-auxiliar-item" key={cargo.id}>
                    {emEdicao ? (
                      <>
                        <input
                          type="text"
                          className="funcionarios-search funcionario-vinculo-search"
                          value={cargoEdicaoNome}
                          onChange={(e) => setCargoEdicaoNome(e.target.value)}
                        />

                        <div className="cadastro-auxiliar-acoes">
                          <button
                            type="button"
                            className="funcionario-vinculo-btn primario"
                            onClick={salvarEdicaoCargo}
                          >
                            Salvar
                          </button>

                          <button
                            type="button"
                            className="funcionario-vinculo-btn secundario"
                            onClick={() => {
                              setCargoEdicaoId(null);
                              setCargoEdicaoNome("");
                            }}
                          >
                            Cancelar
                          </button>
                        </div>
                      </>
                    ) : (
                      <>
                        <div className="cadastro-auxiliar-nome">{cargo.nome}</div>

                        <div className="cadastro-auxiliar-acoes">
                          <button
                            type="button"
                            className="funcionario-vinculo-btn secundario"
                            onClick={() => {
                              setCargoEdicaoId(cargo.id);
                              setCargoEdicaoNome(cargo.nome || "");
                            }}
                          >
                            Editar
                          </button>

                          <button
                            type="button"
                            className="funcionario-vinculo-btn danger"
                            onClick={() => removerCargo(cargo.id)}
                          >
                            Excluir
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {abaAtiva === "departamentos" && (
        <div className="cadastro-auxiliar-layout">
          <div className="funcionario-vinculo-box">
            <h3 className="funcionario-vinculo-titulo">Cadastrar departamento</h3>

            <div className="funcionario-vinculo-campo">
              <label>Nome do departamento</label>
              <input
                type="text"
                className="funcionarios-search funcionario-vinculo-search"
                value={novoDepartamento}
                onChange={(e) => setNovoDepartamento(e.target.value)}
                placeholder="Ex.: Comercial"
              />
            </div>

            <div className="funcionario-vinculo-acoes">
              <button
                type="button"
                className="funcionario-vinculo-btn primario"
                onClick={salvarDepartamento}
                disabled={salvandoDepartamento}
              >
                {salvandoDepartamento ? "Salvando..." : "Cadastrar departamento"}
              </button>
            </div>
          </div>

          <div className="funcionario-vinculo-box">
            <h3 className="funcionario-vinculo-titulo">Editar departamentos</h3>

            <div className="cadastro-auxiliar-lista">
              {departamentos.map((departamento) => {
                const emEdicao = departamentoEdicaoId === departamento.id;

                return (
                  <div className="cadastro-auxiliar-item" key={departamento.id}>
                    {emEdicao ? (
                      <>
                        <input
                          type="text"
                          className="funcionarios-search funcionario-vinculo-search"
                          value={departamentoEdicaoNome}
                          onChange={(e) =>
                            setDepartamentoEdicaoNome(e.target.value)
                          }
                        />

                        <div className="cadastro-auxiliar-acoes">
                          <button
                            type="button"
                            className="funcionario-vinculo-btn primario"
                            onClick={salvarEdicaoDepartamento}
                          >
                            Salvar
                          </button>

                          <button
                            type="button"
                            className="funcionario-vinculo-btn secundario"
                            onClick={() => {
                              setDepartamentoEdicaoId(null);
                              setDepartamentoEdicaoNome("");
                            }}
                          >
                            Cancelar
                          </button>
                        </div>
                      </>
                    ) : (
                      <>
                        <div className="cadastro-auxiliar-nome">
                          {departamento.nome}
                        </div>

                        <div className="cadastro-auxiliar-acoes">
                          <button
                            type="button"
                            className="funcionario-vinculo-btn secundario"
                            onClick={() => {
                              setDepartamentoEdicaoId(departamento.id);
                              setDepartamentoEdicaoNome(departamento.nome || "");
                            }}
                          >
                            Editar
                          </button>

                          <button
                            type="button"
                            className="funcionario-vinculo-btn danger"
                            onClick={() => removerDepartamento(departamento.id)}
                          >
                            Excluir
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default FuncionarioNovoVinculo;
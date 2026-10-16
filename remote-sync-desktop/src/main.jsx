import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const defaults = {
  firebird: {
    host: "127.0.0.1",
    port: 3050,
    database: "",
    user: "SYSDBA",
    version: "3",
    architecture: "",
    clientPath: "",
    charset: "WIN1252",
    driver: "fdb",
  },
  pigo: {
    apiBaseUrl: "https://pigo.lmdsistemasdev.qzz.io/api",
    companyCnpj: "",
    syncIntervalMinutes: 1,
  },
  advanced: { timeoutSeconds: 30, batchSize: 1000, logLevel: "INFO" },
  options: { startWithWindows: true },
};
const stages = [
  "Boas-vindas",
  "Firebird",
  "Banco de dados",
  "PIGO",
  "Teste",
  "Ativação",
  "Conclusão",
];
const normalizeStatus = (value = {}) => ({
  ...value,
  lastSync: value.lastSync || value.last_sync_at,
  nextSync: value.nextSync || value.next_sync_at,
  running: ["STARTING", "IDLE", "SYNCING", "WRITING", "PAUSED", "DIAGNOSING", "RELOADING_CONFIG"].includes(value.state),
  paused: value.state === "PAUSED",
});
const Field = ({ label, value, onChange, type = "text", placeholder }) => (
  <label>
    <span>{label}</span>
    <input
      type={type}
      value={value ?? ""}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
    />
  </label>
);
function App() {
  const api = window.pigo;
  const [config, setConfig] = useState(defaults);
  const [step, setStep] = useState(0);
  const [ready, setReady] = useState(false);
  const [status, setStatus] = useState({ state: "Não configurado" });
  const [result, setResult] = useState(null);
  const [logs, setLogs] = useState([]);
  const [advanced, setAdvanced] = useState(false);
  const [activated, setActivated] = useState(false);
  const [build, setBuild] = useState(null);
  useEffect(() => {
    if (!api) return;
    api.initialize().then((x) => {
      setConfig({
        ...defaults,
        ...x.config,
        firebird: { ...defaults.firebird, ...x.config?.firebird },
        pigo: { ...defaults.pigo, ...x.config?.pigo },
      });
      setReady(x.configured);
      setStatus(normalizeStatus(x.status));
      setBuild(x.build);
      const activationConfirmed = Boolean(
        x.activated &&
        x.installationState === "OWNER_READY" &&
        x.status?.last_result === "success" &&
        x.status?.last_diagnostic?.authenticated === true &&
        x.status?.last_diagnostic?.tenant_resolved === true
      );
      setActivated(activationConfirmed);
      if (activationConfirmed) setStep(6);
      else if (x.configured) setStep(5);
    });
    return api.onStatus((value) => setStatus(normalizeStatus(value)));
  }, []);
  const fb = (key, val) =>
    setConfig((c) => ({ ...c, firebird: { ...c.firebird, [key]: val } }));
  const pg = (key, val) =>
    setConfig((c) => ({ ...c, pigo: { ...c.pigo, [key]: val } }));
  const save = async () => {
    await api.saveConfig(config);
    setReady(true);
    setStep(6);
  };
  const diagnose = async () => {
    setResult({ busy: true });
    setResult(await api.diagnose(config));
  };
  const activate = async (options = {}) => {
    setActivated(false);
    setResult({ busy: true });
    await api.saveConfig(config);
    const outcome = await api.activate(options);
    setResult(outcome);
    setActivated(Boolean(
      outcome.success &&
      outcome.tokenPersisted &&
      outcome.ownerStarted &&
      outcome.pipeReady &&
      outcome.authenticated
    ));
    if (outcome.status) setStatus(normalizeStatus(outcome.status));
  };
  const browse = async () => {
    const path = await api.selectDatabase();
    if (path) fb("database", path);
  };
  const action = async (name) => {
    setStatus(normalizeStatus(await api.agentCommand(name)));
    if (name === "logs") setLogs(await api.readLogs());
  };
  if (!api)
    return (
      <main>
        <h1>PIGO Remote Sync</h1>
        <p>Esta interface deve ser aberta pelo aplicativo Windows.</p>
      </main>
    );
  return (
    <div className="shell">
      <aside>
        <div className="brand">
          <b>PIGO</b>
          <small>REMOTE SYNC</small>
        </div>
        {stages.map((s, i) => (
          <button
            className={i === step ? "active" : ""}
            onClick={() => setStep(i)}
            key={s}
          >
            <i>{i + 1}</i>
            {s}
          </button>
        ))}
      </aside>
      <main>
        {step === 0 && (
          <section>
            <p className="eyebrow">CONFIGURAÇÃO SEGURA</p>
            <h1>Seu ERP conectado ao PIGO, sem complicação.</h1>
            <p className="lead">
              Configure, diagnostique e mantenha o sincronismo em funcionamento
              sem usar o Prompt de Comando.
            </p>
            <div className="actions">
              <button className="primary" onClick={() => setStep(1)}>
                Iniciar configuração
              </button>
              <button
                onClick={async () => {
                  const x = await api.importLegacy();
                  if (x) {
                    setConfig(x);
                    setStep(1);
                  }
                }}
              >
                Importar configuração existente
              </button>
            </div>
          </section>
        )}
        {step === 1 && (
          <section>
            <h2>Configuração do Firebird</h2>
            <div className="grid">
              <Field
                label="Host"
                value={config.firebird.host}
                onChange={(v) => fb("host", v)}
              />
              <Field
                label="Porta"
                type="number"
                value={config.firebird.port}
                onChange={(v) => fb("port", Number(v))}
              />
              <Field
                label="Usuário"
                value={config.firebird.user}
                onChange={(v) => fb("user", v)}
              />
              <Field
                label="Senha"
                type="password"
                value={config.secrets?.firebirdPassword}
                onChange={(v) =>
                  setConfig((c) => ({
                    ...c,
                    secrets: { ...c.secrets, firebirdPassword: v },
                  }))
                }
              />
              <label>
                <span>Versão</span>
                <select
                  value={config.firebird.version}
                  onChange={(e) => fb("version", e.target.value)}
                >
                  <option value="3">Firebird 3</option>
                  <option value="5">Firebird 5</option>
                </select>
              </label>
              <label>
                <span>Arquitetura</span>
                <select
                  value={config.firebird.architecture}
                  onChange={(e) => fb("architecture", e.target.value)}
                >
                  <option value="">Detectar</option>
                  <option value="x86">32 bits</option>
                  <option value="x64">64 bits</option>
                </select>
              </label>
              <Field
                label="Client Library"
                value={config.firebird.clientPath}
                onChange={(v) => fb("clientPath", v)}
              />
              <Field
                label="Charset"
                value={config.firebird.charset}
                onChange={(v) => fb("charset", v)}
              />
              <label>
                <span>Driver</span>
                <select
                  value={config.firebird.driver || "fdb"}
                  onChange={(event) => fb("driver", event.target.value)}
                >
                  <option value="fdb">FDB (legado)</option>
                  <option value="firebird-driver">Firebird Driver</option>
                </select>
              </label>
            </div>
            <button onClick={async () => setResult(await api.detectFirebird())}>
              Detectar instalações
            </button>
            {result?.installations && (
              <div className="results">
                {result.installations.map((x, i) => (
                  <button
                    key={i}
                    onClick={() =>
                      setConfig((c) => ({
                        ...c,
                        firebird: { ...c.firebird, ...x },
                      }))
                    }
                  >
                    {x.version} · {x.architecture} · {x.clientPath}
                  </button>
                ))}
              </div>
            )}
          </section>
        )}
        {step === 2 && (
          <section>
            <h2>Selecione o banco de dados</h2>
            <div className="browse">
              <Field
                label="Arquivo .FDB ou .GDB"
                value={config.firebird.database}
                onChange={(v) => fb("database", v)}
              />
              <button onClick={browse}>Selecionar arquivo</button>
            </div>
            <p className="hint">
              Caminhos locais, UNC e bancos hospedados em outro servidor são
              aceitos.
            </p>
          </section>
        )}
        {step === 3 && (
          <section>
            <h2>Conexão com o PIGO</h2>
            <div className="grid">
              <Field
                label="URL da API"
                value={config.pigo.apiBaseUrl}
                onChange={(v) => pg("apiBaseUrl", v)}
              />
              <Field
                label="CNPJ"
                value={config.pigo.companyCnpj}
                onChange={(v) => pg("companyCnpj", v)}
              />
              <Field
                label="Chave de licença"
                type="password"
                value={config.secrets?.licenseApiKey}
                onChange={(v) =>
                  setConfig((c) => ({
                    ...c,
                    secrets: { ...c.secrets, licenseApiKey: v },
                  }))
                }
              />
              <Field
                label="Intervalo (minutos)"
                type="number"
                value={config.pigo.syncIntervalMinutes}
                onChange={(v) => pg("syncIntervalMinutes", Number(v))}
              />
            </div>
            <button className="link" onClick={() => setAdvanced(!advanced)}>
              Configurações avançadas
            </button>
            {advanced && (
              <div className="grid card">
                <Field
                  label="Timeout (segundos)"
                  value={config.advanced.timeoutSeconds}
                  onChange={() => {}}
                />
                <Field
                  label="Tamanho dos lotes"
                  value={config.advanced.batchSize}
                  onChange={() => {}}
                />
              </div>
            )}
          </section>
        )}
        {step === 4 && (
          <section>
            <h2>Teste e diagnóstico</h2>
            <p>
              Validaremos arquivo, DLL, arquitetura, porta, autenticação e
              schema sem iniciar uma sincronização completa.
            </p>
            <button className="primary" onClick={diagnose}>
              Executar diagnóstico completo
            </button>
            <button onClick={async () => { setResult({ busy: true }); setResult(await api.exportSchema(config)); }}>
              Exportar estrutura do ERP
            </button>
            <Results data={result} />
          </section>
        )}
        {step === 5 && (
          <section>
            <h2>Ativação segura</h2>
            <p>
              A chave de licença será validada e a credencial recebida ficará
              protegida pelo DPAPI desta máquina.
            </p>
            <button className="primary" onClick={() => activate()}>
              Ativar conexão
            </button>
            <button onClick={() => activate({ reactivate: true })}>
              Reativar conexão
            </button>
            <Results data={result} onRetry={() => activate()} />
          </section>
        )}
        {step === 6 && (
          <section>
            <div className="statusline">
              <div>
                <p className="eyebrow">STATUS DO AGENTE</p>
                <h2>
                  <span
                    className={"dot " + (status.running ? "ok" : "")}
                  ></span>
                  {status.state || "Não configurado"}
                </h2>
              </div>
              <small>
                {status.pid ? `Processo ${status.pid}` : "Agente parado"}
              </small>
            </div>
            <div className="metrics">
              <article>
                <span>Firebird</span>
                <b>
                  {config.firebird.version}.0 —{" "}
                  {config.firebird.architecture || "a detectar"}
                </b>
              </article>
              <article>
                <span>Banco</span>
                <b>{config.firebird.database || "Não selecionado"}</b>
              </article>
              <article>
                <span>Última sincronização</span>
                <b>{status.lastSync || "Ainda não executada"}</b>
              </article>
              <article>
                <span>Próxima sincronização</span>
                <b>{status.nextSync || "—"}</b>
              </article>
            </div>
            {build && (
              <p className="build-version">
                Desktop {build.desktopVersion} · Agente {build.agentVersion} · IPC {build.ipcProtocolVersion} · Cofre {build.vaultVersion}
              </p>
            )}
            <CashRegisterCompatibility
              diagnostic={status.last_diagnostic?.cash_register}
              events={status.events}
              currentTable={status.current_table}
            />
            <div className="card"><b>Cadastros no ERP</b><p>{status.state === "WRITING" ? "Verificando solicitações de cadastro e edição…" : status.last_diagnostic?.writeback?.enabled ? "Gravação pelo agente habilitada nas configurações." : "Aguardando configuração e homologação da gravação no ERP."}</p><small>{status.last_writeback_at ? `Última consulta: ${new Date(status.last_writeback_at).toLocaleString("pt-BR")}` : "Nenhuma consulta à fila registrada."}</small></div>
            <div className="actions">
              <button className="primary" onClick={() => action("sync-now")}>
                Sincronizar agora
              </button>
              <button
                onClick={() => action(status.paused ? "resume" : "pause")}
              >
                {status.paused ? "Retomar" : "Pausar"}
              </button>
              <button onClick={diagnose}>Ver diagnóstico</button>
              <button onClick={() => action("logs")}>Abrir logs</button>
            </div>
            {logs.length > 0 && <pre>{logs.join("\n")}</pre>}
          </section>
        )}
        <footer>
          <button
            disabled={step === 0}
            onClick={() => setStep((s) => Math.max(0, s - 1))}
          >
            Voltar
          </button>
          <span>
            Etapa {step + 1} de {stages.length}
          </span>
          {step > 0 && step < 6 && (
            <button
              className="primary"
              disabled={step === 5 && !activated}
              onClick={() => (step === 5 ? save() : setStep((s) => s + 1))}
            >
              {step === 5 ? "Concluir" : "Continuar"}
            </button>
          )}
        </footer>
      </main>
    </div>
  );
}
function Results({ data, onRetry }) {
  const [details, setDetails] = useState(false);
  if (!data) return null;
  if (data.busy) return <p>Executando…</p>;
  const rows = data.steps || [];
  return (
    <div className="checklist">
      {rows.map((x, i) => (
        <div key={i} className={x.ok ? "pass" : "fail"}>
          <b>{x.ok ? "✓" : "!"}</b>
          <span>
            {x.label}
            <small>{x.message}</small>
          </span>
        </div>
      ))}
      {data.message && (
        <div className={data.success || data.ok ? "activation-success" : "activation-error"}>
          <strong>{data.message}</strong>
          {data.path && <p>Arquivo gerado: {data.path}</p>}
          {data.stage && <span>Etapa: {data.stage}</span>}
          {data.code && <code>{data.code}</code>}
          {!data.success && !data.ok && (
            <div className="activation-actions">
              {data.detailsAvailable && (
                <button onClick={() => setDetails((visible) => !visible)}>
                  {details ? "Ocultar detalhes" : "Ver detalhes"}
                </button>
              )}
              {onRetry && <button className="primary" onClick={onRetry}>Tentar novamente</button>}
            </div>
          )}
          {details && (
            <pre>{JSON.stringify({
              stage: data.stage,
              code: data.code,
              agentCode: data.agentCode,
              exitCode: data.exitCode,
              versions: data.versions,
              stdout: data.stdout,
              stderr: data.stderr,
              status: data.status,
            }, null, 2)}</pre>
          )}
        </div>
      )}
    </div>
  );
}
function CashRegisterCompatibility({ diagnostic, events = [], currentTable }) {
  const names = {
    TB_FECHAMENTO_CAIXA: "Fechamentos",
    TB_FECHAMENTO_CAIXA_ITEM: "Itens",
    TB_FECHAMENTO_CAIXA_VENDA: "Vendas",
    TB_MOVIMENTO_CAIXA: "Movimentos",
  };
  const completed = Object.fromEntries(
    (events || [])
      .filter((item) => item.event === "sync.table.completed" && names[item.table])
      .map((item) => [item.table, item.records]),
  );
  if (!diagnostic && !currentTable && Object.keys(completed).length === 0) return null;
  return (
    <div className="cash-module card">
      <div>
        <span>Módulo Caixa</span>
        <b>{diagnostic?.status || (currentTable && names[currentTable] ? "Sincronizando" : "Aguardando diagnóstico")}</b>
      </div>
      {(diagnostic?.tables || Object.keys(names).map((table) => ({ table }))).map((item) => (
        <div key={item.table}>
          <span>{names[item.table] || item.table}</span>
          <b>
            {currentTable === item.table
              ? "Sincronizando…"
              : completed[item.table] != null
                ? `${completed[item.table]} registros`
                : item.compatible === true
                  ? `Compatível · ${item.records ?? 0} registros`
                  : item.found === false
                    ? "Não disponível"
                    : "Aguardando"}
          </b>
        </div>
      ))}
    </div>
  );
}
createRoot(document.getElementById("root")).render(<App />);

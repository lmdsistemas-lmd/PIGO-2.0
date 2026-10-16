const { contextBridge, ipcRenderer } = require("electron");
ipcRenderer.send("renderer:preload-ready");
contextBridge.exposeInMainWorld("pigo", {
  initialize: () => ipcRenderer.invoke("initialize"),
  saveConfig: (c) => ipcRenderer.invoke("config:save", c),
  importLegacy: () => ipcRenderer.invoke("config:import"),
  selectDatabase: () => ipcRenderer.invoke("database:select"),
  detectFirebird: () => ipcRenderer.invoke("firebird:detect"),
  diagnose: (c) => ipcRenderer.invoke("diagnose", c),
  exportSchema: (config) => ipcRenderer.invoke("schema:export", config),
  activate: (options = {}) => ipcRenderer.invoke("agent:activate", options),
  reactivate: () => ipcRenderer.invoke("agent:activate", { reactivate: true }),
  agentCommand: (c) => ipcRenderer.invoke("agent:command", c),
  readLogs: () => ipcRenderer.invoke("logs:read"),
  onStatus: (fn) => {
    const h = (_, x) => fn(x);
    ipcRenderer.on("agent:status", h);
    return () => ipcRenderer.removeListener("agent:status", h);
  },
});

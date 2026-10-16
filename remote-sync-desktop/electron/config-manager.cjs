const fs = require("node:fs");
const path = require("node:path");
const { execFileSync } = require("node:child_process");

const DATA_DIR = process.env.PIGO_REMOTE_SYNC_DATA_DIR || path.join(process.env.PROGRAMDATA || "C:\\ProgramData", "PIGO Remote Sync");
const CONFIG_PATH = path.join(DATA_DIR, "config.json");
const SECRET_PATH = path.join(DATA_DIR, "credentials.dat");
const LEGACY_SECRET_PATH = path.join(DATA_DIR, "credentials.json");
const INSTALLATION_PATH = path.join(DATA_DIR, "installation.json");
const LOG_DIR = path.join(DATA_DIR, "logs");
const DIAGNOSTIC_DIR = path.join(DATA_DIR, "diagnostics");
const defaults = {firebird:{host:"127.0.0.1",port:3050,database:"",user:"SYSDBA",version:"3",architecture:"",clientPath:"",charset:"WIN1252",driver:"fdb"},pigo:{apiBaseUrl:"https://pigo.lmdsistemasdev.qzz.io/api",companyCnpj:"",syncIntervalMinutes:1},advanced:{timeoutSeconds:30,batchSize:1000,logLevel:"INFO"},options:{startWithWindows:true}};

function ensure(){for(const directory of [DATA_DIR,LOG_DIR,DIAGNOSTIC_DIR])fs.mkdirSync(directory,{recursive:true})}
function readJson(file,fallback={}){try{return JSON.parse(fs.readFileSync(file,"utf8"))}catch{return fallback}}
function fileAccessible(file){try{if(!fs.existsSync(file))return false;fs.accessSync(file,fs.constants.R_OK);return true}catch{return false}}
function atomicWrite(file,data){const temporary=`${file}.tmp`;fs.writeFileSync(temporary,JSON.stringify(data,null,2));fs.renameSync(temporary,file)}
function protect(value){if(!value)return null;if(process.platform!=="win32"){if(process.env.PIGO_ALLOW_INSECURE_CREDENTIAL_STORE==="true")return Buffer.from(value).toString("base64");throw new Error("DPAPI só está disponível no Windows.")}const script="Add-Type -AssemblyName System.Security;$v=[Console]::In.ReadToEnd();$b=[Text.Encoding]::UTF8.GetBytes($v);$p=[Security.Cryptography.ProtectedData]::Protect($b,$null,[Security.Cryptography.DataProtectionScope]::LocalMachine);[Convert]::ToBase64String($p)";return execFileSync("powershell.exe",["-NoProfile","-NonInteractive","-Command",script],{input:value,encoding:"utf8",windowsHide:true}).trim()}
function unprotect(value){if(!value)return null;if(process.platform!=="win32"){if(process.env.PIGO_ALLOW_INSECURE_CREDENTIAL_STORE==="true")return Buffer.from(value,"base64").toString();throw new Error("DPAPI só está disponível no Windows.")}const script="Add-Type -AssemblyName System.Security;$v=[Console]::In.ReadToEnd();$b=[Convert]::FromBase64String($v);$p=[Security.Cryptography.ProtectedData]::Unprotect($b,$null,[Security.Cryptography.DataProtectionScope]::LocalMachine);[Text.Encoding]::UTF8.GetString($p)";return execFileSync("powershell.exe",["-NoProfile","-NonInteractive","-Command",script],{input:value,encoding:"utf8",windowsHide:true}).trim()}
function normalizeStore(raw){if(raw.version===1&&raw.entries)return raw;const entries={};const mapping={firebirdPassword:"firebird_password",licenseApiKey:"license_api_key",remote_sync_token:"remote_sync_token"};for(const [oldKey,newKey] of Object.entries(mapping)){const item=raw[oldKey];if(item?.value)entries[newKey]=item.value}if(raw.token)entries.remote_sync_token=raw.token;return{version:1,scope:"LocalMachine",entries}}
function readStore(){const source=fs.existsSync(SECRET_PATH)?SECRET_PATH:LEGACY_SECRET_PATH;const store=normalizeStore(readJson(source,{}));if(source===LEGACY_SECRET_PATH&&fs.existsSync(LEGACY_SECRET_PATH)){ensure();atomicWrite(SECRET_PATH,store)}return store}
function save(input){ensure();const clean=structuredClone(input);const secrets=clean.secrets||{};delete clean.secrets;atomicWrite(CONFIG_PATH,clean);const store=readStore();const mapping={firebirdPassword:"firebird_password",licenseApiKey:"license_api_key"};for(const [uiKey,entryKey] of Object.entries(mapping))if(secrets[uiKey])store.entries[entryKey]=protect(secrets[uiKey]);atomicWrite(SECRET_PATH,store);return clean}
function load(){const saved=readJson(CONFIG_PATH);return{...defaults,...saved,firebird:{...defaults.firebird,...saved.firebird},pigo:{...defaults.pigo,...saved.pigo},secrets:{}}}
function configured(){const c=load();return Boolean(c.firebird?.database&&c.pigo?.apiBaseUrl&&c.pigo?.companyCnpj)}
function credentialStatus(){const store=readStore();let remoteSyncTokenReadable=false;try{remoteSyncTokenReadable=Boolean(store.entries.remote_sync_token&&unprotect(store.entries.remote_sync_token))}catch{}return{storeFound:fs.existsSync(SECRET_PATH)||fs.existsSync(LEGACY_SECRET_PATH),configFound:fileAccessible(CONFIG_PATH),installationAccessible:!fs.existsSync(INSTALLATION_PATH)||fileAccessible(INSTALLATION_PATH),licenseKeyPresent:Boolean(store.entries.license_api_key),firebirdPasswordPresent:Boolean(store.entries.firebird_password),remoteSyncTokenPresent:Boolean(store.entries.remote_sync_token),remoteSyncTokenReadable,version:store.version,scope:store.scope}}
function activated(){return credentialStatus().remoteSyncTokenPresent}
function ipcSecret(){const value=readStore().entries.ipc_secret;return value?unprotect(value):null}
function parseEnv(text){const out={};for(const line of text.split(/\r?\n/)){const m=line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);if(m)out[m[1]]=m[2].replace(/^['"]|['"]$/g,"")}return out}
function importEnv(file){const e=parseEnv(fs.readFileSync(file,"utf8"));return{...defaults,firebird:{...defaults.firebird,host:e.FB_HOST||"127.0.0.1",port:Number(e.FB_PORT||3050),database:e.FB_DATABASE||"",user:e.FB_USER||"SYSDBA",clientPath:e.FB_CLIENT_PATH||"",charset:e.FB_CHARSET||"WIN1252"},pigo:{...defaults.pigo,apiBaseUrl:e.API_BASE_URL||defaults.pigo.apiBaseUrl,companyCnpj:e.COMPANY_CNPJ||"",syncIntervalMinutes:Number(e.SYNC_INTERVAL_MINUTES||1)},secrets:{firebirdPassword:e.FB_PASS||"",licenseApiKey:e.LICENSE_API_KEY||""}}}
module.exports={DATA_DIR,APP_DIR:DATA_DIR,CONFIG_PATH,SECRET_PATH,INSTALLATION_PATH,LOG_DIR,DIAGNOSTIC_DIR,load,save,configured,activated,credentialStatus,ipcSecret,importEnv,parseEnv,normalizeStore};

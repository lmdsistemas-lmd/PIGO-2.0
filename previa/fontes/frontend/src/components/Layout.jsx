import { useState } from "react";

function IconDashboard() {
  return (
    <svg viewBox="0 0 24 24" style={styles.iconSvg} aria-hidden="true">
      <path
        d="M4 13h7V4H4v9zm9 7h7v-9h-7v9zM4 20h7v-5H4v5zm9-9h7V4h-7v7z"
        fill="currentColor"
      />
    </svg>
  );
}

function IconInbox() {
  return (
    <svg viewBox="0 0 24 24" style={styles.iconSvg} aria-hidden="true">
      <path
        d="M19 3H5a2 2 0 0 0-2 2v11a3 3 0 0 0 3 3h12a3 3 0 0 0 3-3V5a2 2 0 0 0-2-2zm0 13h-4a3 3 0 0 1-6 0H5V5h14v11z"
        fill="currentColor"
      />
    </svg>
  );
}

function IconCalendar() {
  return (
    <svg viewBox="0 0 24 24" style={styles.iconSvg} aria-hidden="true">
      <path
        d="M7 2h2v2h6V2h2v2h3a2 2 0 0 1 2 2v13a3 3 0 0 1-3 3H5a3 3 0 0 1-3-3V6a2 2 0 0 1 2-2h3V2zm13 8H4v9a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-9z"
        fill="currentColor"
      />
    </svg>
  );
}

function IconUsers() {
  return (
    <svg viewBox="0 0 24 24" style={styles.iconSvg} aria-hidden="true">
      <path
        d="M16 11a4 4 0 1 0-2.83-6.83A4 4 0 0 0 16 11zM8 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm8 1c-2.67 0-8 1.34-8 4v3h16v-3c0-2.66-5.33-4-8-4zM8 13c-2.67 0-8 1.34-8 4v3h6v-3c0-1.16.43-2.06 1.16-2.77A9.6 9.6 0 0 1 8 13z"
        fill="currentColor"
      />
    </svg>
  );
}

function IconPerformance() {
  return (
    <svg viewBox="0 0 24 24" style={styles.iconSvg} aria-hidden="true">
      <path
        d="M3 19h18v2H3v-2zm2-2 4-5 3 3 5-7 2 1-6 8-3-3-3 4H5z"
        fill="currentColor"
      />
    </svg>
  );
}

function IconPayments() {
  return (
    <svg viewBox="0 0 24 24" style={styles.iconSvg} aria-hidden="true">
      <path
        d="M3 5a2 2 0 0 1 2-2h14a3 3 0 0 1 3 3v8a3 3 0 0 1-3 3H5a2 2 0 0 1-2-2V5zm2 2v8h14a1 1 0 0 0 1-1V8H5zm9 6h4v-2h-4v2z"
        fill="currentColor"
      />
    </svg>
  );
}

function IconOffice() {
  return (
    <svg viewBox="0 0 24 24" style={styles.iconSvg} aria-hidden="true">
      <path
        d="M3 21V7l9-4 9 4v14h-7v-6h-4v6H3zm6-10h2V9H9v2zm0 4h2v-2H9v2zm4-4h2V9h-2v2zm0 4h2v-2h-2v2z"
        fill="currentColor"
      />
    </svg>
  );
}

function IconRecruitment() {
  return (
    <svg viewBox="0 0 24 24" style={styles.iconSvg} aria-hidden="true">
      <path
        d="M10 2a8 8 0 1 0 5.29 14.01l4.35 4.34 1.41-1.41-4.34-4.35A8 8 0 0 0 10 2zm0 2a6 6 0 1 1 0 12 6 6 0 0 1 0-12zm1 3H9v2H7v2h2v2h2v-2h2V9h-2V7z"
        fill="currentColor"
      />
    </svg>
  );
}

function IconSettings() {
  return (
    <svg viewBox="0 0 24 24" style={styles.smallIconSvg} aria-hidden="true">
      <path
        d="M19.14 12.94a7.97 7.97 0 0 0 .06-.94c0-.32-.02-.63-.06-.94l2.03-1.58a.5.5 0 0 0 .12-.64l-1.92-3.32a.5.5 0 0 0-.6-.22l-2.39.96a7.57 7.57 0 0 0-1.63-.94l-.36-2.54a.5.5 0 0 0-.5-.42h-3.84a.5.5 0 0 0-.5.42l-.36 2.54c-.58.22-1.12.53-1.63.94l-2.39-.96a.5.5 0 0 0-.6.22L2.71 8.84a.5.5 0 0 0 .12.64l2.03 1.58c-.04.31-.06.62-.06.94s.02.63.06.94l-2.03 1.58a.5.5 0 0 0-.12.64l1.92 3.32a.5.5 0 0 0 .6.22l2.39-.96c.5.41 1.05.72 1.63.94l.36 2.54a.5.5 0 0 0 .5.42h3.84a.5.5 0 0 0 .5-.42l.36-2.54c.58-.22 1.12-.53 1.63-.94l2.39.96a.5.5 0 0 0 .6-.22l1.92-3.32a.5.5 0 0 0-.12-.64l-2.03-1.58zM12 15.5A3.5 3.5 0 1 1 12 8a3.5 3.5 0 0 1 0 7.5z"
        fill="currentColor"
      />
    </svg>
  );
}

function IconBell() {
  return (
    <svg viewBox="0 0 24 24" style={styles.smallIconSvg} aria-hidden="true">
      <path
        d="M12 22a2.5 2.5 0 0 0 2.45-2h-4.9A2.5 2.5 0 0 0 12 22zm6-6V11a6 6 0 1 0-12 0v5L4 18v1h16v-1l-2-2z"
        fill="currentColor"
      />
    </svg>
  );
}

function MenuItem({ icon, label, active = false }) {
  return (
    <div
      style={{
        ...styles.navItem,
        ...(active ? styles.navItemActive : {}),
      }}
    >
      <span style={styles.navIcon}>{icon}</span>
      <span>{label}</span>
    </div>
  );
}

export default function Layout({ title, children }) {
  const [logoErro, setLogoErro] = useState(false);

  return (
    <div style={styles.page}>
      <aside style={styles.sidebar}>
        <div style={styles.logoArea}>
          {!logoErro ? (
            <img
              src="C:\Projetos LMD\rh_app\frontend\src\imagens\LOGO COMPRIDA AZUL A5.svg"
              alt="Logo da empresa"
              style={styles.logoImage}
              onError={() => setLogoErro(true)}
            />
          ) : (
            <div style={styles.logoFallback}>
              <div style={styles.logoBadge}></div>
              <div>
                <div style={styles.logoText}>SISTEMAS</div>
                <div style={styles.logoSubtext}>RH / Gestão de Pessoas</div>
              </div>
            </div>
          )}
        </div>

        <nav style={styles.nav}>
          <MenuItem icon={<IconDashboard />} label="Dashboard" />
          <MenuItem icon={<IconInbox />} label="Inbox" />
          <MenuItem icon={<IconCalendar />} label="Calendário" />
          <MenuItem icon={<IconUsers />} label="Funcionários" active />
          <MenuItem icon={<IconPerformance />} label="Performance" />
          <MenuItem icon={<IconPayments />} label="Pagamentos" />
          <MenuItem icon={<IconOffice />} label="Cargos e Departamentos" />
          <MenuItem icon={<IconRecruitment />} label="Recrutamento" />
        </nav>
      </aside>

      <main style={styles.main}>
        <header style={styles.header}>
          <div>
            <h1 style={styles.title}>{title}</h1>
            <p style={styles.breadcrumb}>Dashboard / Funcionários</p>
          </div>

          <div style={styles.userArea}>
            <div style={styles.iconButton}>
              <IconSettings />
            </div>

            <div style={styles.iconButton}>
              <IconBell />
            </div>

            <div style={styles.userInfo}>
              <div style={styles.userAvatar}>U</div>
              <div>
                <div style={styles.userName}>USUARIO</div>
                <div style={styles.userSubtext}>User</div>
              </div>
            </div>
          </div>
        </header>

        <section style={styles.content}>{children}</section>
      </main>
    </div>
  );
}

const styles = {
  page: {
    display: "flex",
    minHeight: "100vh",
    backgroundColor: "#f3f4f6",
    fontFamily: "Arial, sans-serif",
  },

  sidebar: {
    width: "250px",
    backgroundColor: "#ffffff",
    borderRight: "1px solid #e5e7eb",
    padding: "24px 18px",
    display: "flex",
    flexDirection: "column",
    boxSizing: "border-box",
  },

  logoArea: {
    marginBottom: "28px",
    minHeight: "64px",
    display: "flex",
    alignItems: "center",
  },

  logoImage: {
    maxWidth: "100%",
    maxHeight: "64px",
    objectFit: "contain",
  },

  logoFallback: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
  },

  logoBadge: {
    width: "40px",
    height: "40px",
    borderRadius: "12px",
    backgroundColor: "#1d4ed8",
    color: "#ffffff",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontWeight: "bold",
    fontSize: "14px",
  },

  logoText: {
    fontSize: "20px",
    fontWeight: "700",
    color: "#374151",
    letterSpacing: "0.4px",
  },

  logoSubtext: {
    fontSize: "12px",
    color: "#9ca3af",
    marginTop: "2px",
  },

  nav: {
    display: "flex",
    flexDirection: "column",
    gap: "10px",
    marginTop: "18px",
  },

  navItem: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    padding: "14px 16px",
    borderRadius: "12px",
    color: "#6b7280",
    backgroundColor: "transparent",
    fontSize: "14px",
    fontWeight: "500",
    cursor: "default",
  },

  navItemActive: {
    color: "#ffffff",
    backgroundColor: "#4da3ff",
    fontWeight: "700",
    boxShadow: "0 8px 18px rgba(77, 163, 255, 0.25)",
  },

  navIcon: {
    width: "18px",
    height: "18px",
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },

  iconSvg: {
    width: "18px",
    height: "18px",
    display: "block",
    color: "currentColor",
  },

  smallIconSvg: {
    width: "16px",
    height: "16px",
    display: "block",
    color: "currentColor",
  },

  main: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    minWidth: 0,
  },

  header: {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    padding: "24px 32px 0 32px",
    gap: "20px",
  },

  title: {
    margin: 0,
    fontSize: "32px",
    fontWeight: "700",
    color: "#1f2937",
    lineHeight: 1.2,
  },

  breadcrumb: {
    margin: "6px 0 0 0",
    fontSize: "13px",
    color: "#6b7280",
  },

  userArea: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    flexWrap: "wrap",
    justifyContent: "flex-end",
  },

  iconButton: {
    width: "36px",
    height: "36px",
    borderRadius: "10px",
    backgroundColor: "#dbeafe",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: "#2563eb",
  },

  userInfo: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    marginLeft: "8px",
  },

  userAvatar: {
    width: "36px",
    height: "36px",
    borderRadius: "999px",
    backgroundColor: "#bfdbfe",
    color: "#1d4ed8",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontWeight: "700",
    fontSize: "14px",
  },

  userName: {
    fontSize: "12px",
    fontWeight: "700",
    color: "#374151",
    textTransform: "uppercase",
    lineHeight: 1.2,
  },

  userSubtext: {
    fontSize: "12px",
    color: "#9ca3af",
    lineHeight: 1.2,
  },

  content: {
    padding: "24px 32px 32px 32px",
    boxSizing: "border-box",
  },
};
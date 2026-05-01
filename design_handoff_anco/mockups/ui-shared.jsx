// AnCo — shared UI primitives & icons
// Exposes everything to window so screen files can use them.

const Icon = {
  search: (p = {}) => (
    <svg className={`icon ${p.size ? '' : 'icon-16'}`} style={p.style} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="7" cy="7" r="4.5" />
      <line x1="10.3" y1="10.3" x2="13.5" y2="13.5" strokeLinecap="round" />
    </svg>
  ),
  arrowRight: (p = {}) => (
    <svg className="icon icon-14" style={p.style} viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
      <line x1="2" y1="7" x2="12" y2="7" strokeLinecap="round" />
      <polyline points="8.5,3.5 12,7 8.5,10.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  arrowLeft: (p = {}) => (
    <svg className="icon icon-14" style={p.style} viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
      <line x1="12" y1="7" x2="2" y2="7" strokeLinecap="round" />
      <polyline points="5.5,3.5 2,7 5.5,10.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  external: (p = {}) => (
    <svg className="icon icon-12" style={p.style} viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.3">
      <path d="M2.5 2.5h3M9.5 2.5v3M9.5 2.5L5 7" strokeLinecap="round" />
      <path d="M9.5 6.5v3h-7v-7h3" strokeLinecap="round" />
    </svg>
  ),
  filter: (p = {}) => (
    <svg className="icon icon-14" style={p.style} viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
      <line x1="2" y1="3.5" x2="12" y2="3.5" strokeLinecap="round" />
      <line x1="2" y1="7" x2="12" y2="7" strokeLinecap="round" />
      <line x1="2" y1="10.5" x2="12" y2="10.5" strokeLinecap="round" />
      <circle cx="5" cy="3.5" r="1.4" fill="var(--paper)" />
      <circle cx="9" cy="7" r="1.4" fill="var(--paper)" />
      <circle cx="4" cy="10.5" r="1.4" fill="var(--paper)" />
    </svg>
  ),
  menu: (p = {}) => (
    <svg className="icon icon-18" style={p.style} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5">
      <line x1="2" y1="5" x2="16" y2="5" strokeLinecap="round" />
      <line x1="2" y1="9" x2="16" y2="9" strokeLinecap="round" />
      <line x1="2" y1="13" x2="16" y2="13" strokeLinecap="round" />
    </svg>
  ),
  x: (p = {}) => (
    <svg className="icon icon-12" style={p.style} viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.3">
      <line x1="3" y1="3" x2="9" y2="9" strokeLinecap="round" />
      <line x1="9" y1="3" x2="3" y2="9" strokeLinecap="round" />
    </svg>
  ),
  copy: (p = {}) => (
    <svg className="icon icon-14" style={p.style} viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.3">
      <rect x="4.5" y="4.5" width="7.5" height="7.5" rx="1" />
      <path d="M9.5 4.5V2.5h-7v7h2" />
    </svg>
  ),
  download: (p = {}) => (
    <svg className="icon icon-14" style={p.style} viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.3">
      <path d="M7 2v7M4 6.5L7 9.5l3-3" strokeLinecap="round" strokeLinejoin="round" />
      <line x1="2.5" y1="11.5" x2="11.5" y2="11.5" strokeLinecap="round" />
    </svg>
  ),
  chevronDown: (p = {}) => (
    <svg className="icon icon-12" style={p.style} viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.4">
      <polyline points="3,4.5 6,7.5 9,4.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  link: (p = {}) => (
    <svg className="icon icon-12" style={p.style} viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.3">
      <path d="M5 7c-.5-.5-.5-1.3 0-1.8l1.6-1.6c.5-.5 1.3-.5 1.8 0l.5.5c.5.5.5 1.3 0 1.8L7.3 7.5" strokeLinecap="round" />
      <path d="M7 5c.5.5.5 1.3 0 1.8L5.4 8.4c-.5.5-1.3.5-1.8 0l-.5-.5c-.5-.5-.5-1.3 0-1.8L4.7 4.5" strokeLinecap="round" />
    </svg>
  ),
  brokenLink: (p = {}) => (
    <svg className="icon icon-12" style={p.style} viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.3">
      <path d="M3.5 4.5L2 6l1.5 1.5M8.5 4.5L10 6l-1.5 1.5" strokeLinecap="round" />
      <line x1="4.5" y1="6" x2="7.5" y2="6" strokeLinecap="round" strokeDasharray="1.2 1.2" />
    </svg>
  ),
  check: (p = {}) => (
    <svg className="icon icon-12" style={p.style} viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.6">
      <polyline points="2.5,6.5 5,9 9.5,3.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  bookmark: (p = {}) => (
    <svg className="icon icon-14" style={p.style} viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.3">
      <path d="M3.5 2h7v10L7 9.5 3.5 12V2z" strokeLinejoin="round" />
    </svg>
  ),
};

// Logo wordmark
function Wordmark({ size = 18, color }) {
  const c = color || 'var(--ink)';
  return (
    <span style={{
      fontFamily: 'var(--serif)',
      fontWeight: 500,
      fontSize: size,
      letterSpacing: '-0.01em',
      color: c,
      lineHeight: 1,
      display: 'inline-flex',
      alignItems: 'baseline',
      gap: 0,
    }}>
      <span>An</span>
      <span style={{ fontStyle: 'italic', fontWeight: 400 }}>Co</span>
      <span style={{ color: 'var(--gold)', fontWeight: 400 }}>.</span>
    </span>
  );
}

// Nav bar — desktop
function NavDesktop({ active = 'acervo' }) {
  const items = [
    { id: 'acervo', label: 'Acervo' },
    { id: 'sobre', label: 'Sobre' },
    { id: 'metodologia', label: 'Metodologia' },
    { id: 'equipe', label: 'Equipe' },
  ];
  return (
    <nav style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '20px 56px',
      borderBottom: '1px solid var(--rule)',
      background: 'var(--paper)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 48 }}>
        <Wordmark size={22} />
        <ul style={{ display: 'flex', gap: 28, listStyle: 'none', padding: 0, margin: 0 }}>
          {items.map(i => (
            <li key={i.id} style={{
              fontFamily: 'var(--sans)',
              fontSize: 14,
              fontWeight: active === i.id ? 600 : 400,
              color: active === i.id ? 'var(--ink)' : 'var(--ink-3)',
              borderBottom: active === i.id ? '1px solid var(--ink)' : '1px solid transparent',
              paddingBottom: 4,
            }}>{i.label}</li>
          ))}
        </ul>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <button className="btn btn-sm btn-ghost">Buscar</button>
        <button className="btn btn-sm btn-secondary">Entrar</button>
      </div>
    </nav>
  );
}

// Nav bar — mobile
function NavMobile({ showSearch }) {
  return (
    <nav style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '14px 20px',
      borderBottom: '1px solid var(--rule)',
      background: 'var(--paper)',
    }}>
      <Wordmark size={19} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {showSearch && (
          <button style={{
            width: 36, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'transparent', border: 0, color: 'var(--ink-2)', cursor: 'pointer',
          }}>
            <Icon.search />
          </button>
        )}
        <button style={{
          width: 36, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'transparent', border: 0, color: 'var(--ink-2)', cursor: 'pointer',
        }}>
          <Icon.menu />
        </button>
      </div>
    </nav>
  );
}

// Footer
function Footer({ compact }) {
  return (
    <footer style={{
      borderTop: '1px solid var(--rule)',
      padding: compact ? '24px 20px' : '40px 56px',
      background: 'var(--paper-2)',
      color: 'var(--ink-3)',
      fontFamily: 'var(--sans)',
      fontSize: 12,
      lineHeight: 1.55,
    }}>
      <div style={{
        display: 'grid',
        gridTemplateColumns: compact ? '1fr' : '2fr 1fr 1fr 1fr',
        gap: compact ? 20 : 48,
      }}>
        <div>
          <Wordmark size={16} />
          <p style={{ margin: '12px 0 0', maxWidth: 360, color: 'var(--ink-3)' }}>
            Acervo digital colaborativo de análises de literatura científica
            sobre Análise Cognitiva. Mantido pelo Programa de Pós-Graduação
            em Difusão do Conhecimento, UFBA · UNEB · IFBA · SENAI CIMATEC.
          </p>
        </div>
        {!compact && (
          <>
            <div>
              <div className="t-eyebrow" style={{ color: 'var(--ink-2)', marginBottom: 10 }}>Acervo</div>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: 6 }}>
                <li>Buscar</li><li>Análises recentes</li><li>Por base bibliográfica</li><li>Resenhas críticas</li>
              </ul>
            </div>
            <div>
              <div className="t-eyebrow" style={{ color: 'var(--ink-2)', marginBottom: 10 }}>Plataforma</div>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: 6 }}>
                <li>Sobre</li><li>Metodologia AnCo</li><li>Equipe editorial</li><li>Como contribuir</li>
              </ul>
            </div>
            <div>
              <div className="t-eyebrow" style={{ color: 'var(--ink-2)', marginBottom: 10 }}>Institucional</div>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: 6 }}>
                <li>PPGDC</li><li>UFBA</li><li>Termos de uso</li><li>Contato</li>
              </ul>
            </div>
          </>
        )}
      </div>
      <div style={{
        marginTop: compact ? 20 : 40,
        paddingTop: 16,
        borderTop: '1px solid var(--rule)',
        display: 'flex',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: 8,
      }}>
        <span>© 2024–2026 PPGDC. Análises licenciadas em CC BY-NC 4.0.</span>
        <span>v.2026.04 · acervo em construção</span>
      </div>
    </footer>
  );
}

// Section heading (with eyebrow + serif title)
function SectionHead({ eyebrow, title, count, action }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'baseline', justifyContent: 'space-between',
      marginBottom: 20, gap: 16,
    }}>
      <div>
        {eyebrow && <div className="t-eyebrow" style={{ marginBottom: 8 }}>{eyebrow}</div>}
        <h2 className="t-h1" style={{ margin: 0 }}>
          {title}
          {count != null && <span style={{ color: 'var(--ink-4)', fontSize: 22, marginLeft: 10, fontStyle: 'italic' }}>{count}</span>}
        </h2>
      </div>
      {action}
    </div>
  );
}

Object.assign(window, {
  Icon, Wordmark, NavDesktop, NavMobile, Footer, SectionHead,
});

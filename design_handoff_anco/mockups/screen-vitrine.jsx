// Vitrine — homepage screen (mobile + desktop)

const RECENT_ANALYSES = [
  {
    title: 'Análise cognitiva de práticas pedagógicas em comunidades quilombolas: uma leitura multirreferencial',
    authors: 'Santos, M. C.; Almeida, R. L.',
    journal: 'Revista Brasileira de Educação',
    year: 2025,
    analyst: 'Helena Vasconcelos Lima',
    date: '12 abr. 2026',
    badges: ['resenha'],
  },
  {
    title: 'Autopoiese e construção de sentido em ambientes virtuais de aprendizagem',
    authors: 'Pereira, J. A.; Costa, B.',
    journal: 'Educação & Sociedade',
    year: 2024,
    analyst: 'Rodrigo Tavares de Sá',
    date: '08 abr. 2026',
    badges: [],
  },
  {
    title: 'Difusão do conhecimento em saúde coletiva: um estudo polilógico das representações sociais do cuidado',
    authors: 'Mendonça, T. F.',
    journal: 'Ciência & Saúde Coletiva',
    year: 2023,
    analyst: 'Isabela Cunha Rocha',
    date: '02 abr. 2026',
    badges: ['resenha', 'aberto'],
  },
  {
    title: 'Análise do discurso e formação docente: contribuições de Pêcheux para a investigação cognitiva em sala de aula',
    authors: 'Lopes, A. M.; Ferraz, V.',
    journal: 'Cadernos CEDES',
    year: 2022,
    analyst: 'Daniel Couto Aragão',
    date: '28 mar. 2026',
    badges: [],
  },
  {
    title: 'Cognição situada e tecnologia social: o caso da Rede de Educação Cidadã na Bahia',
    authors: 'Ribeiro, P.; Nascimento, C.',
    journal: 'Educação em Revista',
    year: 2021,
    analyst: 'Marina Quadros Pinto',
    date: '21 mar. 2026',
    badges: ['historico'],
  },
];

const METRICS = [
  { value: '83', label: 'análises catalogadas' },
  { value: '24', label: 'pesquisadores contribuintes' },
  { value: '6', label: 'bases bibliográficas cobertas' },
  { value: '2008–25', label: 'amplitude de anos das obras' },
];

function HeroProse({ size }) {
  return (
    <div>
      <div className="t-eyebrow" style={{ marginBottom: 14 }}>
        Acervo digital · Difusão do conhecimento
      </div>
      <h1 style={{
        fontFamily: 'var(--serif)',
        fontWeight: 400,
        fontSize: size === 'mobile' ? 36 : 64,
        lineHeight: size === 'mobile' ? 1.05 : 1.0,
        letterSpacing: '-0.022em',
        margin: 0,
        color: 'var(--ink)',
        textWrap: 'pretty',
      }}>
        O que a literatura científica
        <br />
        diz sobre <span style={{ fontStyle: 'italic' }}>Análise Cognitiva</span>,
        <br />
        organizado por quem a pratica.
      </h1>
      <p className="t-prose" style={{
        marginTop: size === 'mobile' ? 20 : 28,
        maxWidth: size === 'mobile' ? '100%' : 620,
        fontSize: size === 'mobile' ? 16 : 19,
        lineHeight: 1.55,
      }}>
        AnCo é uma abordagem epistemológica multirreferencial para investigar
        os processos cognitivos de sujeitos engajados na construção e difusão
        do conhecimento. Este acervo cataloga, segundo uma grade conceitual
        comum, a literatura científica que mobiliza ou dialoga com este conceito
        — produzido colaborativamente por pesquisadores do PPGDC.
      </p>
    </div>
  );
}

function MetricsBlock({ size }) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: size === 'mobile' ? '1fr 1fr' : 'repeat(4, 1fr)',
      gap: size === 'mobile' ? 0 : 0,
      borderTop: '1px solid var(--rule-strong)',
      borderBottom: '1px solid var(--rule-strong)',
    }}>
      {METRICS.map((m, i) => (
        <div key={i} style={{
          padding: size === 'mobile' ? '20px 16px' : '28px 24px',
          borderRight: (size === 'mobile' ? (i % 2 === 0) : (i < 3)) ? '1px solid var(--rule)' : 'none',
          borderBottom: size === 'mobile' && i < 2 ? '1px solid var(--rule)' : 'none',
        }}>
          <div style={{
            fontFamily: 'var(--serif)',
            fontWeight: 400,
            fontSize: size === 'mobile' ? 32 : 44,
            lineHeight: 1,
            letterSpacing: '-0.02em',
            color: 'var(--ink)',
            marginBottom: size === 'mobile' ? 6 : 10,
          }}>{m.value}</div>
          <div style={{
            fontFamily: 'var(--sans)',
            fontSize: size === 'mobile' ? 12 : 13,
            color: 'var(--ink-3)',
            lineHeight: 1.35,
            textWrap: 'balance',
          }}>{m.label}</div>
        </div>
      ))}
    </div>
  );
}

function RecentItem({ a, size, dense }) {
  return (
    <article style={{
      padding: size === 'mobile' ? '20px 0' : (dense ? '18px 0' : '24px 0'),
      borderBottom: '1px solid var(--rule)',
      display: 'grid',
      gridTemplateColumns: size === 'mobile' ? '1fr' : '120px 1fr 220px',
      gap: size === 'mobile' ? 12 : 32,
      alignItems: 'baseline',
    }}>
      {size !== 'mobile' && (
        <div className="t-meta" style={{ fontVariantNumeric: 'tabular-nums', color: 'var(--ink-4)' }}>
          {a.date}
        </div>
      )}
      <div>
        <h3 style={{
          fontFamily: 'var(--serif)',
          fontWeight: 500,
          fontSize: size === 'mobile' ? 17 : 20,
          lineHeight: 1.25,
          letterSpacing: '-0.005em',
          margin: 0,
          color: 'var(--ink)',
          textWrap: 'pretty',
        }}>{a.title}</h3>
        <div style={{ marginTop: 8, fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--ink-3)', lineHeight: 1.45 }}>
          {a.authors} · <span style={{ fontStyle: 'italic' }}>{a.journal}</span>, {a.year}
        </div>
        {a.badges.length > 0 && (
          <div style={{ marginTop: 10, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {a.badges.includes('resenha') && <span className="selo selo-resenha">resenha crítica</span>}
            {a.badges.includes('aberto') && <span className="selo selo-aberto">acesso aberto</span>}
            {a.badges.includes('historico') && <span className="selo selo-historico">acervo histórico</span>}
          </div>
        )}
      </div>
      <div style={{
        fontFamily: 'var(--sans)',
        fontSize: 12,
        color: 'var(--ink-3)',
        textAlign: size === 'mobile' ? 'left' : 'right',
        marginTop: size === 'mobile' ? 8 : 0,
      }}>
        {size === 'mobile' && (
          <span style={{ display: 'inline-block', marginRight: 6, color: 'var(--ink-4)' }}>{a.date} ·</span>
        )}
        analisado por <span style={{ color: 'var(--ink-2)' }}>{a.analyst}</span>
      </div>
    </article>
  );
}

// ─── Mobile Vitrine ───────────────────────────────────────────────
function VitrineMobile() {
  return (
    <div className="frame-mobile" data-screen-label="01 Vitrine · Mobile">
      <NavMobile />

      {/* Hero */}
      <section style={{ padding: '32px 20px 28px' }}>
        <HeroProse size="mobile" />
        <div style={{ display: 'grid', gap: 10, marginTop: 28 }}>
          <button className="btn btn-primary">
            Explorar o acervo <Icon.arrowRight style={{ color: 'var(--paper)' }} />
          </button>
          <button className="btn btn-secondary">Entrar para contribuir</button>
        </div>
      </section>

      {/* Metrics */}
      <section style={{ padding: '0 20px 32px' }}>
        <div className="t-eyebrow" style={{ marginBottom: 12, color: 'var(--ink-3)' }}>
          O acervo em números
        </div>
        <MetricsBlock size="mobile" />
        <div className="t-meta" style={{ marginTop: 10, color: 'var(--ink-4)' }}>
          atualizado em 28 abr. 2026
        </div>
      </section>

      <hr className="hr" />

      {/* Recent */}
      <section style={{ padding: '32px 20px' }}>
        <div className="t-eyebrow" style={{ marginBottom: 4 }}>Publicado recentemente</div>
        <h2 className="t-h2" style={{ margin: '0 0 4px', fontSize: 22 }}>
          Cinco análises mais recentes
        </h2>
        <p className="t-small" style={{ margin: '4px 0 18px' }}>
          Aprovadas por revisão de pares e integradas ao acervo público.
        </p>
        <div>
          {RECENT_ANALYSES.map((a, i) => (
            <RecentItem key={i} a={a} size="mobile" />
          ))}
        </div>
        <button className="btn btn-ghost" style={{ width: '100%', marginTop: 20 }}>
          Ver todas as 83 análises <Icon.arrowRight />
        </button>
      </section>

      {/* Methodology teaser */}
      <section style={{
        padding: '32px 20px',
        background: 'var(--paper-2)',
        borderTop: '1px solid var(--rule)',
        borderBottom: '1px solid var(--rule)',
      }}>
        <div className="t-eyebrow" style={{ marginBottom: 10 }}>Metodologia</div>
        <h3 className="t-h2" style={{ margin: '0 0 12px' }}>
          Cada obra atravessa <span style={{ fontStyle: 'italic' }}>treze campos</span> da grade AnCo.
        </h3>
        <p className="t-prose" style={{ margin: 0, fontSize: 16 }}>
          Pertinência. Definição. Objeto. Objetivo. Foco. Metodologia.
          Epistemologia. Teoria de referência. Referenciais. Resultados.
          Aspectos. Contexto. Observações. A grade dá comparabilidade ao
          acervo sem reduzir a singularidade de cada análise.
        </p>
        <a className="link" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginTop: 14, fontSize: 14 }}>
          Sobre a metodologia <Icon.arrowRight />
        </a>
      </section>

      <Footer compact />
    </div>
  );
}

// ─── Desktop Vitrine ──────────────────────────────────────────────
function VitrineDesktop() {
  return (
    <div className="frame-desktop" data-screen-label="01 Vitrine · Desktop">
      <NavDesktop active="" />

      {/* Hero */}
      <section style={{
        padding: '88px 56px 72px',
        display: 'grid',
        gridTemplateColumns: '1.4fr 1fr',
        gap: 80,
        alignItems: 'end',
      }}>
        <HeroProse size="desktop" />
        <div>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <button className="btn btn-primary">
              Explorar o acervo <Icon.arrowRight style={{ color: 'var(--paper)' }} />
            </button>
            <button className="btn btn-secondary">Entrar para contribuir</button>
          </div>
          <p className="t-small" style={{ marginTop: 18, maxWidth: 320 }}>
            O acervo é público e citável. A contribuição requer cadastro como
            pesquisador vinculado a um programa de pós-graduação.
          </p>
        </div>
      </section>

      {/* Metrics — full bleed */}
      <section style={{ padding: '0 56px 80px' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 18 }}>
          <div className="t-eyebrow">O acervo em números</div>
          <div className="t-meta" style={{ color: 'var(--ink-4)' }}>atualizado em 28 abr. 2026</div>
        </div>
        <MetricsBlock size="desktop" />
      </section>

      {/* Recent */}
      <section style={{ padding: '40px 56px 80px', borderTop: '1px solid var(--rule)' }}>
        <SectionHead
          eyebrow="Publicado recentemente"
          title="Cinco análises mais recentes"
          action={
            <a className="link" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 14 }}>
              Ver as 83 do acervo <Icon.arrowRight />
            </a>
          }
        />
        <div>
          {RECENT_ANALYSES.map((a, i) => (
            <RecentItem key={i} a={a} size="desktop" />
          ))}
        </div>
      </section>

      {/* Two-up: methodology + how to contribute */}
      <section style={{
        background: 'var(--paper-2)',
        borderTop: '1px solid var(--rule)',
        borderBottom: '1px solid var(--rule)',
        padding: '64px 56px',
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 64,
      }}>
        <div>
          <div className="t-eyebrow" style={{ marginBottom: 14 }}>Metodologia</div>
          <h3 style={{
            fontFamily: 'var(--serif)', fontWeight: 400, fontSize: 30,
            lineHeight: 1.15, letterSpacing: '-0.015em', margin: '0 0 16px',
          }}>
            Cada obra atravessa <span style={{ fontStyle: 'italic' }}>treze campos</span> da grade AnCo, da pertinência ao contexto de produção.
          </h3>
          <p className="t-prose" style={{ margin: 0 }}>
            A grade dá comparabilidade ao acervo sem reduzir a singularidade de
            cada obra. Resenhas críticas autorais são opcionais e atravessam
            revisão cega adicional por dois pares.
          </p>
          <a className="link" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginTop: 20, fontSize: 14 }}>
            Documentação completa da grade <Icon.arrowRight />
          </a>
        </div>
        <div>
          <div className="t-eyebrow" style={{ marginBottom: 14 }}>Como contribuir</div>
          <h3 style={{
            fontFamily: 'var(--serif)', fontWeight: 400, fontSize: 30,
            lineHeight: 1.15, letterSpacing: '-0.015em', margin: '0 0 16px',
          }}>
            Você lê o artigo. <span style={{ fontStyle: 'italic' }}>Dois pares</span> revisam sua análise. O acervo cresce.
          </h3>
          <ol style={{
            margin: 0, padding: 0, listStyle: 'none',
            display: 'grid', gap: 10, fontFamily: 'var(--sans)', fontSize: 14, color: 'var(--ink-2)',
          }}>
            {[
              'Identifique o artigo e seus metadados via DOI ou CrossRef.',
              'Preencha a grade estrutural — pertinência, objeto, foco, epistemologia.',
              'Opcionalmente, redija uma resenha crítica autoral.',
              'Submeta. Dois pares revisam estrutura; mais dois revisam a resenha às cegas.',
            ].map((s, i) => (
              <li key={i} style={{ display: 'grid', gridTemplateColumns: '24px 1fr', gap: 10 }}>
                <span style={{ fontFamily: 'var(--serif)', fontStyle: 'italic', color: 'var(--ink-4)' }}>{i + 1}.</span>
                <span>{s}</span>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <Footer />
    </div>
  );
}

Object.assign(window, { VitrineMobile, VitrineDesktop });

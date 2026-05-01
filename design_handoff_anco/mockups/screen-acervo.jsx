// Acervo de busca — listagem pública (mobile + desktop)

const SEARCH_RESULTS = [
  {
    title: 'Análise cognitiva de práticas pedagógicas em comunidades quilombolas: uma leitura multirreferencial',
    authors: 'Santos, M. C.; Almeida, R. L.',
    journal: 'Revista Brasileira de Educação',
    year: 2025,
    base: 'Scopus',
    similarity: 94,
    analyst: 'Helena Vasconcelos Lima',
    date: '12 abr. 2026',
    badges: ['resenha', 'aberto'],
    snippet: 'Investiga, sob a perspectiva multirreferencial e polilógica de Macedo, os processos cognitivos engajados na produção de conhecimento em terreiros e escolas quilombolas do recôncavo baiano.',
  },
  {
    title: 'Autopoiese e construção de sentido em ambientes virtuais de aprendizagem',
    authors: 'Pereira, J. A.; Costa, B.',
    journal: 'Educação & Sociedade',
    year: 2024,
    base: 'Web of Science',
    similarity: 89,
    analyst: 'Rodrigo Tavares de Sá',
    date: '08 abr. 2026',
    badges: [],
    snippet: 'Articula a teoria da autopoiese (Maturana e Varela) com práticas de mediação docente em fóruns assíncronos, propondo categoria operatória para análise cognitiva da interação.',
  },
  {
    title: 'Difusão do conhecimento em saúde coletiva: um estudo polilógico das representações sociais do cuidado',
    authors: 'Mendonça, T. F.',
    journal: 'Ciência & Saúde Coletiva',
    year: 2023,
    base: 'Redalyc',
    similarity: 87,
    analyst: 'Isabela Cunha Rocha',
    date: '02 abr. 2026',
    badges: ['resenha', 'aberto', 'multi'],
    snippet: 'Mobiliza a análise cognitiva como dispositivo metodológico para investigar representações de cuidado entre agentes comunitários de saúde do interior baiano.',
  },
  {
    title: 'Análise do discurso e formação docente: contribuições de Pêcheux para a investigação cognitiva em sala de aula',
    authors: 'Lopes, A. M.; Ferraz, V.',
    journal: 'Cadernos CEDES',
    year: 2022,
    base: 'Scopus',
    similarity: 82,
    analyst: 'Daniel Couto Aragão',
    date: '28 mar. 2026',
    badges: ['aberto'],
    snippet: 'Discute como a análise do discurso de matriz francesa pode operar em conjunto com a noção de cognição situada para iluminar a formação inicial de professores.',
  },
  {
    title: 'Cognição situada e tecnologia social: o caso da Rede de Educação Cidadã na Bahia',
    authors: 'Ribeiro, P.; Nascimento, C.',
    journal: 'Educação em Revista',
    year: 2021,
    base: 'Repositório UFBA',
    similarity: 78,
    analyst: 'Marina Quadros Pinto',
    date: '21 mar. 2026',
    badges: ['historico'],
    snippet: 'Estudo de caso que articula cognição situada e tecnologia social a partir da experiência da Rede de Educação Cidadã, com ênfase nos processos formativos de mediadores.',
  },
  {
    title: 'Pedagogia da libertação e construção colaborativa do conhecimento: relendo Freire em chave cognitiva',
    authors: 'Barbosa, E.; Silveira, K.',
    journal: 'Educação & Pesquisa',
    year: 2020,
    base: 'Scopus',
    similarity: 76,
    analyst: 'Helena Vasconcelos Lima',
    date: '14 mar. 2026',
    badges: ['resenha'],
    snippet: 'Releitura da obra freireana sob a perspectiva da análise cognitiva, propondo a categoria de "consciência cognoscente situada" como operador analítico.',
  },
  {
    title: 'Mediação semiótica e processos cognitivos em comunidades de prática profissional',
    authors: 'Andrade, L.',
    journal: 'Trabalho, Educação e Saúde',
    year: 2019,
    base: 'Sage',
    similarity: 71,
    analyst: 'Rodrigo Tavares de Sá',
    date: '02 mar. 2026',
    badges: ['quebrado'],
    snippet: 'Examina os processos de mediação semiótica em comunidades de prática de enfermagem, articulando vigotskianos com a noção de cognição distribuída.',
  },
  {
    title: 'Currículo, complexidade e análise cognitiva: contribuições para a formação de professores na Bahia',
    authors: 'Souza, R. P.; Brito, J.',
    journal: 'Currículo sem Fronteiras',
    year: 2018,
    base: 'Repositório UFBA',
    similarity: 68,
    analyst: 'Daniel Couto Aragão',
    date: '20 fev. 2026',
    badges: ['historico', 'aberto'],
    snippet: 'Discute o lugar da análise cognitiva como matriz formativa em programas de licenciatura, articulando o pensamento complexo de Morin à abordagem multirreferencial.',
  },
];

const ACTIVE_FILTERS = [
  { label: 'Educação', group: 'Área' },
  { label: 'Multirreferencialidade', group: 'Teoria' },
  { label: 'desde 2018', group: 'Ano' },
  { label: 'Acesso aberto', group: 'Acesso' },
];

function ResultRow({ r, semantic }) {
  return (
    <article style={{
      padding: '16px 0 18px',
      borderBottom: '1px solid var(--rule)',
      display: 'grid',
      gridTemplateColumns: 'minmax(0, 1fr) 200px',
      gap: 24,
      alignItems: 'start',
    }}>
      <div style={{ minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
          {r.badges.includes('resenha') && <span className="selo selo-resenha">resenha crítica</span>}
          {r.badges.includes('aberto') && <span className="selo selo-aberto">acesso aberto</span>}
          {r.badges.includes('quebrado') && <span className="selo selo-quebrado">link quebrado</span>}
          {r.badges.includes('historico') && <span className="selo selo-historico">acervo histórico</span>}
          {r.badges.includes('multi') && <span className="selo selo-multi">múltiplas análises</span>}
        </div>
        <h3 style={{
          fontFamily: 'var(--serif)',
          fontWeight: 500,
          fontSize: 19,
          lineHeight: 1.25,
          letterSpacing: '-0.005em',
          margin: 0,
          color: 'var(--ink)',
          textWrap: 'pretty',
        }}>{r.title}</h3>
        <div style={{ marginTop: 6, fontSize: 13, color: 'var(--ink-3)' }}>
          {r.authors} · <span style={{ fontStyle: 'italic' }}>{r.journal}</span>, {r.year} · {r.base}
        </div>
        <p className="t-prose" style={{ margin: '8px 0 0', fontSize: 14, color: 'var(--ink-2)' }}>{r.snippet}</p>
      </div>
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-end',
        gap: 6,
        fontFamily: 'var(--sans)',
      }}>
        {semantic && (
          <div style={{
            fontFamily: 'var(--serif)',
            fontSize: 22,
            fontWeight: 400,
            color: 'var(--ink)',
            fontVariantNumeric: 'tabular-nums',
            letterSpacing: '-0.01em',
          }}>{r.similarity}<span style={{ fontSize: 14, color: 'var(--ink-3)' }}>%</span></div>
        )}
        {semantic && (
          <div className="t-meta" style={{ color: 'var(--ink-4)' }}>similaridade</div>
        )}
        <div style={{ height: 8 }} />
        <div className="t-meta" style={{ textAlign: 'right' }}>
          analisado por<br />
          <span style={{ color: 'var(--ink-2)' }}>{r.analyst}</span>
        </div>
        <div className="t-meta" style={{ color: 'var(--ink-4)' }}>{r.date}</div>
      </div>
    </article>
  );
}

function ResultRowMobile({ r, semantic }) {
  return (
    <article style={{
      padding: '16px 0 18px',
      borderBottom: '1px solid var(--rule)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6, flexWrap: 'wrap' }}>
        {semantic && (
          <span style={{
            fontFamily: 'var(--serif)',
            fontSize: 14,
            fontStyle: 'italic',
            color: 'var(--ink-3)',
            marginRight: 4,
          }}>{r.similarity}%</span>
        )}
        {r.badges.includes('resenha') && <span className="selo selo-resenha" style={{ fontSize: 10, padding: '3px 6px' }}>resenha</span>}
        {r.badges.includes('aberto') && <span className="selo selo-aberto" style={{ fontSize: 10, padding: '3px 6px' }}>aberto</span>}
        {r.badges.includes('quebrado') && <span className="selo selo-quebrado" style={{ fontSize: 10, padding: '3px 6px' }}>link quebrado</span>}
        {r.badges.includes('historico') && <span className="selo selo-historico" style={{ fontSize: 10, padding: '3px 6px' }}>histórico</span>}
        {r.badges.includes('multi') && <span className="selo selo-multi" style={{ fontSize: 10, padding: '3px 6px' }}>múltiplas</span>}
      </div>
      <h3 style={{
        fontFamily: 'var(--serif)',
        fontWeight: 500,
        fontSize: 17,
        lineHeight: 1.25,
        margin: 0,
        color: 'var(--ink)',
      }}>{r.title}</h3>
      <div style={{ marginTop: 6, fontSize: 12, color: 'var(--ink-3)', lineHeight: 1.45 }}>
        {r.authors} · <span style={{ fontStyle: 'italic' }}>{r.journal}</span>, {r.year}
      </div>
      <div style={{ marginTop: 8, fontSize: 11, color: 'var(--ink-4)', display: 'flex', justifyContent: 'space-between' }}>
        <span>{r.base}</span>
        <span>{r.analyst} · {r.date}</span>
      </div>
    </article>
  );
}

function FilterGroup({ label, children, defaultOpen = true }) {
  return (
    <div style={{ borderBottom: '1px solid var(--rule)', padding: '14px 0' }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 600,
        textTransform: 'uppercase', letterSpacing: '0.08em',
        color: 'var(--ink-2)', marginBottom: defaultOpen ? 12 : 0, cursor: 'pointer',
      }}>
        <span>{label}</span>
        <Icon.chevronDown style={{ transform: defaultOpen ? 'rotate(0)' : 'rotate(-90deg)', color: 'var(--ink-3)' }} />
      </div>
      {defaultOpen && children}
    </div>
  );
}

function FilterCheck({ label, count, checked }) {
  return (
    <label style={{
      display: 'flex', alignItems: 'center', gap: 10,
      fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--ink-2)',
      padding: '5px 0', cursor: 'pointer',
    }}>
      <span style={{
        width: 14, height: 14, border: '1px solid var(--rule-strong)',
        borderRadius: 2, display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        background: checked ? 'var(--ink)' : 'var(--paper)',
        color: 'var(--paper)',
        flex: '0 0 auto',
      }}>
        {checked && <Icon.check style={{ width: 10, height: 10 }} />}
      </span>
      <span style={{ flex: 1 }}>{label}</span>
      <span style={{ color: 'var(--ink-4)', fontVariantNumeric: 'tabular-nums', fontSize: 12 }}>{count}</span>
    </label>
  );
}

function FiltersSidebar() {
  return (
    <aside style={{ fontFamily: 'var(--sans)' }}>
      <div style={{
        fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 600,
        textTransform: 'uppercase', letterSpacing: '0.1em',
        color: 'var(--ink)', paddingBottom: 8, borderBottom: '1px solid var(--rule-strong)',
      }}>Filtros</div>

      <FilterGroup label="Ano de publicação">
        <div style={{ padding: '4px 2px' }}>
          <div style={{ position: 'relative', height: 32, marginBottom: 8 }}>
            <div style={{ position: 'absolute', top: 14, left: 0, right: 0, height: 4, background: 'var(--paper-2)', border: '1px solid var(--rule)' }} />
            <div style={{ position: 'absolute', top: 14, left: '20%', right: '8%', height: 4, background: 'var(--ink)' }} />
            <div style={{ position: 'absolute', top: 8, left: '18%', width: 16, height: 16, background: 'var(--paper)', border: '1.5px solid var(--ink)', borderRadius: '50%' }} />
            <div style={{ position: 'absolute', top: 8, right: '6%', width: 16, height: 16, background: 'var(--paper)', border: '1.5px solid var(--ink)', borderRadius: '50%' }} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--ink-3)', fontVariantNumeric: 'tabular-nums' }}>
            <span>2018</span><span>2025</span>
          </div>
        </div>
      </FilterGroup>

      <FilterGroup label="Base bibliográfica">
        <FilterCheck label="Web of Science" count={18} />
        <FilterCheck label="Scopus" count={24} checked />
        <FilterCheck label="Science Direct" count={9} />
        <FilterCheck label="Redalyc" count={11} />
        <FilterCheck label="Sage" count={7} />
        <FilterCheck label="Repositório UFBA" count={14} />
      </FilterGroup>

      <FilterGroup label="Área do conhecimento">
        <FilterCheck label="Educação" count={37} checked />
        <FilterCheck label="Saúde coletiva" count={14} />
        <FilterCheck label="Comunicação" count={9} />
        <FilterCheck label="Ciência da informação" count={8} />
        <FilterCheck label="Linguística" count={6} />
        <FilterCheck label="Gestão" count={5} />
      </FilterGroup>

      <FilterGroup label="Epistemologia">
        <FilterCheck label="Construtivismo" count={22} />
        <FilterCheck label="Fenomenologia" count={11} />
        <FilterCheck label="Pragmatismo" count={9} />
        <FilterCheck label="Empirismo" count={4} />
      </FilterGroup>

      <FilterGroup label="Teoria de referência">
        <FilterCheck label="Multirreferencialidade" count={18} checked />
        <FilterCheck label="Autopoiese" count={12} />
        <FilterCheck label="Pedagogia da libertação" count={9} />
        <FilterCheck label="Análise do discurso" count={11} />
        <FilterCheck label="Representações sociais" count={8} />
      </FilterGroup>

      <FilterGroup label="Características da análise" defaultOpen={false} />
      <FilterGroup label="Acesso & estado" defaultOpen={false} />
    </aside>
  );
}

function SearchControls({ semantic, size }) {
  return (
    <div>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        background: 'var(--paper)',
        border: '1.5px solid var(--ink)',
        borderRadius: 2,
        height: size === 'mobile' ? 48 : 56,
      }}>
        <span style={{ paddingLeft: size === 'mobile' ? 14 : 18, color: 'var(--ink-3)' }}>
          <Icon.search />
        </span>
        <input
          className="t-body"
          type="text"
          defaultValue="cognição situada e formação docente"
          style={{
            flex: 1,
            border: 0,
            outline: 0,
            background: 'transparent',
            padding: size === 'mobile' ? '0 12px' : '0 14px',
            fontFamily: 'var(--sans)',
            fontSize: size === 'mobile' ? 15 : 16,
            color: 'var(--ink)',
          }}
        />
        <button style={{
          height: '100%',
          padding: '0 16px',
          background: 'var(--ink)',
          color: 'var(--paper)',
          border: 0,
          fontFamily: 'var(--sans)',
          fontSize: 13,
          fontWeight: 500,
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
          cursor: 'pointer',
        }}>Buscar</button>
      </div>

      {/* Mode toggle */}
      <div style={{
        display: 'flex',
        marginTop: 12,
        background: 'var(--paper-2)',
        border: '1px solid var(--rule)',
        padding: 3,
        borderRadius: 2,
        width: 'fit-content',
        fontFamily: 'var(--sans)',
        fontSize: 12,
      }}>
        <button style={{
          padding: '8px 14px',
          background: !semantic ? 'var(--paper)' : 'transparent',
          border: 0,
          fontFamily: 'inherit',
          fontSize: 'inherit',
          fontWeight: !semantic ? 600 : 400,
          color: !semantic ? 'var(--ink)' : 'var(--ink-3)',
          boxShadow: !semantic ? '0 1px 0 rgba(0,0,0,0.04)' : 'none',
          cursor: 'pointer',
          letterSpacing: '0.02em',
        }}>Busca textual</button>
        <button style={{
          padding: '8px 14px',
          background: semantic ? 'var(--paper)' : 'transparent',
          border: 0,
          fontFamily: 'inherit',
          fontSize: 'inherit',
          fontWeight: semantic ? 600 : 400,
          color: semantic ? 'var(--ink)' : 'var(--ink-3)',
          boxShadow: semantic ? '0 1px 0 rgba(0,0,0,0.04)' : 'none',
          cursor: 'pointer',
          letterSpacing: '0.02em',
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
        }}>
          Busca por significado
          <span style={{
            fontSize: 9, fontStyle: 'italic',
            color: semantic ? 'var(--gold-deep)' : 'var(--ink-4)',
            textTransform: 'uppercase', letterSpacing: '0.08em',
          }}>vetorial</span>
        </button>
      </div>
    </div>
  );
}

function ActiveChips({ size }) {
  return (
    <div style={{
      display: 'flex',
      gap: 6,
      flexWrap: 'wrap',
      alignItems: 'center',
    }}>
      <span className="t-meta" style={{ marginRight: 4, color: 'var(--ink-3)' }}>filtros ativos:</span>
      {ACTIVE_FILTERS.map((f, i) => (
        <span key={i} className="chip chip-removable">
          <span style={{ color: 'var(--ink-4)', fontSize: 11, marginRight: 2 }}>{f.group}:</span>
          {f.label}
          <span className="x"><Icon.x /></span>
        </span>
      ))}
      <button style={{
        background: 'transparent',
        border: 0,
        fontFamily: 'var(--sans)',
        fontSize: 12,
        color: 'var(--ink-3)',
        textDecoration: 'underline',
        textUnderlineOffset: 2,
        cursor: 'pointer',
        marginLeft: 4,
      }}>limpar todos</button>
    </div>
  );
}

// ─── Mobile Acervo ────────────────────────────────────────────────
function AcervoMobile() {
  return (
    <div className="frame-mobile" data-screen-label="02 Acervo · Mobile">
      <NavMobile />

      <section style={{ padding: '24px 20px 16px' }}>
        <div className="t-eyebrow" style={{ marginBottom: 8 }}>Acervo público</div>
        <h1 className="t-h1" style={{ margin: '0 0 16px', fontSize: 26 }}>Buscar análises</h1>
        <SearchControls semantic={true} size="mobile" />
      </section>

      {/* Active filters + filter button */}
      <section style={{
        padding: '12px 20px',
        borderTop: '1px solid var(--rule)',
        borderBottom: '1px solid var(--rule)',
        background: 'var(--paper-2)',
        display: 'flex', alignItems: 'center', gap: 10, justifyContent: 'space-between',
      }}>
        <button style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          background: 'var(--paper)', border: '1px solid var(--rule-strong)',
          padding: '8px 12px', borderRadius: 2,
          fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--ink)',
          cursor: 'pointer',
        }}>
          <Icon.filter /> Filtros <span style={{
            background: 'var(--ink)', color: 'var(--paper)',
            fontSize: 10, fontWeight: 600,
            padding: '1px 6px', borderRadius: 999, marginLeft: 2,
          }}>4</span>
        </button>
        <span className="t-small" style={{ color: 'var(--ink-3)' }}>
          <span style={{ color: 'var(--ink), fontWeight: 600' }}>27</span> resultados
        </span>
      </section>

      {/* Sort */}
      <div style={{
        padding: '10px 20px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--ink-3)',
        borderBottom: '1px solid var(--rule)',
      }}>
        <span>ordenar por <span style={{ color: 'var(--ink)', fontWeight: 500 }}>relevância</span> <Icon.chevronDown style={{ marginLeft: 2 }} /></span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <Icon.download /> CSV
        </span>
      </div>

      {/* Results */}
      <section style={{ padding: '4px 20px 24px' }}>
        {SEARCH_RESULTS.slice(0, 6).map((r, i) => (
          <ResultRowMobile key={i} r={r} semantic={true} />
        ))}
        <button className="btn btn-ghost" style={{ width: '100%', marginTop: 18 }}>
          Carregar mais (21 restantes)
        </button>
      </section>

      <Footer compact />
    </div>
  );
}

// ─── Desktop Acervo ───────────────────────────────────────────────
function AcervoDesktop() {
  return (
    <div className="frame-desktop" data-screen-label="02 Acervo · Desktop">
      <NavDesktop active="acervo" />

      {/* Search header */}
      <section style={{ padding: '48px 56px 32px', borderBottom: '1px solid var(--rule)' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 64, alignItems: 'end' }}>
          <div>
            <div className="t-eyebrow" style={{ marginBottom: 12 }}>Acervo público · 83 análises</div>
            <h1 className="t-display" style={{ margin: 0, fontSize: 48 }}>
              Buscar no acervo
            </h1>
          </div>
          <SearchControls semantic={true} size="desktop" />
        </div>
      </section>

      {/* Two-column: filters + results */}
      <section style={{
        display: 'grid',
        gridTemplateColumns: '260px 1fr',
        gap: 56,
        padding: '32px 56px 80px',
      }}>
        <FiltersSidebar />

        <div>
          {/* Active filters + count + sort */}
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            paddingBottom: 16, marginBottom: 8,
            borderBottom: '1px solid var(--rule-strong)',
            gap: 16, flexWrap: 'wrap',
          }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <ActiveChips />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 20, fontFamily: 'var(--sans)', fontSize: 13 }}>
              <span style={{ color: 'var(--ink-3)' }}>
                <span style={{ color: 'var(--ink)', fontWeight: 600 }}>27</span> resultados
              </span>
              <span style={{ color: 'var(--ink-3)', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                ordenar por <span style={{ color: 'var(--ink)', fontWeight: 500 }}>relevância</span> <Icon.chevronDown />
              </span>
              <span style={{ color: 'var(--ink-3)', display: 'inline-flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                <Icon.download /> exportar CSV
              </span>
            </div>
          </div>

          {/* Results */}
          <div>
            {SEARCH_RESULTS.map((r, i) => (
              <ResultRow key={i} r={r} semantic={true} />
            ))}
          </div>

          {/* Pagination */}
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            marginTop: 28, paddingTop: 16,
            fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--ink-3)',
          }}>
            <span>mostrando 1–8 de 27</span>
            <div style={{ display: 'flex', gap: 4 }}>
              {['1', '2', '3', '4'].map((p, i) => (
                <button key={p} style={{
                  width: 32, height: 32,
                  background: i === 0 ? 'var(--ink)' : 'transparent',
                  color: i === 0 ? 'var(--paper)' : 'var(--ink-2)',
                  border: i === 0 ? 0 : '1px solid var(--rule-strong)',
                  fontFamily: 'inherit', fontSize: 13, cursor: 'pointer',
                  fontVariantNumeric: 'tabular-nums',
                }}>{p}</button>
              ))}
              <button style={{
                width: 32, height: 32,
                background: 'transparent',
                color: 'var(--ink-2)',
                border: '1px solid var(--rule-strong)',
                cursor: 'pointer',
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              }}><Icon.arrowRight /></button>
            </div>
          </div>
        </div>
      </section>

      <Footer />
    </div>
  );
}

Object.assign(window, { AcervoMobile, AcervoDesktop });

// Página de análise — exibição completa, citável (mobile + desktop)

const ANALYSIS = {
  title: 'Análise cognitiva de práticas pedagógicas em comunidades quilombolas: uma leitura multirreferencial',
  authors: 'Santos, Maria Clara; Almeida, Ricardo Luís',
  journal: 'Revista Brasileira de Educação',
  volume: 30, number: 82, pages: '1–24', year: 2025,
  doi: '10.1590/S1413-24782025308201',
  base: 'Scopus',
  hasReview: true,
  openAccess: true,
  reviewText:
    'O artigo de Santos e Almeida ocupa um lugar incomum na literatura sobre Análise Cognitiva: dialoga com a tradição multirreferencial sem reduzi-la a um inventário de autores. Ao tomar como objeto as práticas pedagógicas em comunidades quilombolas do recôncavo baiano, os autores recusam tanto o gesto extrativista de aplicar uma grade externa quanto o gesto romântico de transferir ao território a tarefa de explicar-se. O que emerge é uma análise polilógica em sentido forte — vozes em coexistência, não em síntese.\n\nA contribuição mais original está na proposição da categoria "consciência cognoscente situada", que tensiona produtivamente o legado freireano com a noção de cognição distribuída. Pesa, porém, uma certa economia metodológica: o leitor fica curioso sobre como exatamente os pesquisadores operacionalizaram a coleta sem repetir o vício extrativista que o texto critica. É uma omissão, não um erro — mas merece nota.\n\nObra fundamental para quem investiga AnCo em interface com epistemologias do Sul. Recomenda-se em conjunto com a leitura crítica de Macedo (2010) e Sousa Santos (2007).',
  reviewer1: 'Helena Vasconcelos Lima',
  reviewer2: 'Daniel Couto Aragão',
  fields: {
    'Pertinência': { value: 'Sim — alta pertinência para o campo da Análise Cognitiva.', kind: 'text' },
    'Define o conceito': {
      value: 'Sim. Os autores propõem que a Análise Cognitiva opera como "agenciamento situado de saberes, práticas e percepções de sujeitos engajados em construção coletiva de conhecimento" (p. 7), tomando explicitamente a definição de Macedo (2010) como ponto de partida e a estendendo com a noção freireana de consciência cognoscente.',
      kind: 'text',
    },
    'Objeto do estudo': { value: 'Práticas pedagógicas situadas em três comunidades quilombolas do recôncavo baiano (Cachoeira, Maragogipe e São Francisco do Conde), no período 2020–2023.', kind: 'text' },
    'Objetivo declarado': { value: 'Investigar como saberes ancestrais e currículos escolares se articulam — ou colidem — em situações concretas de mediação docente, e propor categorias operatórias para a análise cognitiva desse encontro.', kind: 'text' },
    'Foco específico': { value: 'O movimento de tradução cognitiva entre matrizes epistemológicas distintas (escolar e tradicional) na figura do(a) professor(a)-mediador(a) quilombola.', kind: 'text' },
    'Metodologia': { value: 'Etnografia colaborativa em três sítios, com observação participante (208h registradas), entrevistas em profundidade (n=27) e análise multirreferencial dos materiais didáticos produzidos coletivamente.', kind: 'text' },
    'Epistemologia': { value: ['Construtivismo crítico', 'Fenomenologia', 'Multirreferencialidade'], kind: 'chips' },
    'Teoria de referência': { value: ['Pedagogia da libertação (Freire)', 'Análise multirreferencial (Ardoino, Macedo)', 'Cognição situada (Lave & Wenger)'], kind: 'chips' },
    'Referenciais teóricos citados': { value: 'Freire (1968, 1996); Ardoino (1998); Macedo (2010, 2018); Maturana & Varela (1984); Lave & Wenger (1991); Sousa Santos (2007); Mignolo (2011); Munanga (2009).', kind: 'text' },
    'Resultados': { value: 'Os autores identificam três modos recorrentes de tradução cognitiva: integração assimétrica (predominância da matriz escolar), justaposição não dialógica (matrizes em paralelo), e o que denominam "agenciamento polilógico" (matrizes em tensão produtiva). Apenas o terceiro modo, observado em 4 dos 27 casos, sustenta o que classificam como "consciência cognoscente situada".', kind: 'text' },
    'Aspectos relevantes': { value: 'A categoria operatória "consciência cognoscente situada" estende a noção freireana incorporando a dimensão da localização cognitiva. Útil para análises subsequentes em outros territórios tradicionais.', kind: 'text' },
    'Contexto de produção': { value: 'Pesquisa vinculada ao GT Cognição & Território do PPGDC (UFBA), com financiamento CNPq edital universal 2021. Os autores integram, respectivamente, o Departamento de Educação da UFRB e a Faculdade de Educação da UFBA.', kind: 'text' },
    'Observações do analista': { value: 'A análise estrutural é robusta. A operacionalização metodológica da coleta — especialmente a negociação ética com as comunidades — está descrita com menos densidade do que mereceria, ponto retomado na resenha.', kind: 'text' },
  },
  analyst: 'Helena Vasconcelos Lima',
  reviewersOpen: ['Rodrigo Tavares de Sá', 'Isabela Cunha Rocha'],
  publishedDate: '12 abril 2026',
  version: 'v.3',
  versionDate: '12 abr. 2026',
};

function Eyebrow({ children, style }) {
  return <div className="t-eyebrow" style={{ marginBottom: 10, ...style }}>{children}</div>;
}

function FieldBlock({ label, value, kind, size }) {
  if (!value || (Array.isArray(value) && value.length === 0)) return null;
  return (
    <div style={{
      padding: size === 'mobile' ? '20px 0' : '24px 0',
      borderBottom: '1px solid var(--rule)',
      display: 'grid',
      gridTemplateColumns: '1fr',
      gap: 8,
    }}>
      <div style={{
        fontFamily: 'var(--sans)',
        fontSize: 11,
        fontWeight: 600,
        letterSpacing: '0.12em',
        textTransform: 'uppercase',
        color: 'var(--ink-3)',
      }}>{label}</div>
      {kind === 'chips' ? (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
          {value.map((v, i) => <span key={i} className="chip">{v}</span>)}
        </div>
      ) : (
        <p style={{
          fontFamily: 'var(--serif)',
          fontSize: size === 'mobile' ? 16 : 17,
          lineHeight: 1.55,
          color: 'var(--ink-2)',
          margin: 0,
          textWrap: 'pretty',
        }}>{value}</p>
      )}
    </div>
  );
}

function ReviewCallout({ text, size }) {
  return (
    <section style={{
      background: 'var(--review-bg)',
      borderTop: '1px solid var(--review-rule)',
      borderBottom: '1px solid var(--review-rule)',
      padding: size === 'mobile' ? '32px 20px' : '56px 0',
      marginInline: size === 'mobile' ? -20 : 0,
    }}>
      <div style={{ maxWidth: size === 'mobile' ? '100%' : 700, margin: '0 auto' }}>
        <div className="t-eyebrow" style={{ color: 'var(--gold-deep)', marginBottom: 8 }}>Resenha crítica</div>
        <div className="t-meta" style={{ fontStyle: 'italic', color: 'var(--ink-3)', marginBottom: 24 }}>
          revisão cega por dois pares
        </div>
        {text.split('\n\n').map((para, i) => (
          <p key={i} style={{
            fontFamily: 'var(--serif)',
            fontSize: size === 'mobile' ? 17 : 19,
            lineHeight: 1.6,
            color: 'var(--ink-2)',
            margin: i === 0 ? 0 : '20px 0 0',
            textWrap: 'pretty',
          }}>
            {i === 0 ? (
              <><span style={{ fontFamily: 'var(--serif)', fontSize: '1.5em', float: 'left', lineHeight: 0.9, marginRight: 6, marginTop: 6, color: 'var(--ink)' }}>{para[0]}</span>{para.slice(1)}</>
            ) : para}
          </p>
        ))}
      </div>
    </section>
  );
}

function CitationBlock({ size }) {
  const abnt = 'SANTOS, M. C.; ALMEIDA, R. L. Análise cognitiva de práticas pedagógicas em comunidades quilombolas: uma leitura multirreferencial. Revista Brasileira de Educação, v. 30, n. 82, p. 1–24, 2025. Análise por Helena Vasconcelos Lima, Acervo AnCo, v.3, 2026. Disponível em: anco.ppgdc.org.br/a/2025-santos-quilombola.';
  const apa = 'Santos, M. C., & Almeida, R. L. (2025). Análise cognitiva de práticas pedagógicas em comunidades quilombolas: uma leitura multirreferencial. Revista Brasileira de Educação, 30(82), 1–24. [Análise por H. V. Lima, AnCo Archive, v.3, 2026]. https://anco.ppgdc.org.br/a/2025-santos-quilombola';

  return (
    <section style={{
      background: 'var(--paper-2)',
      border: '1px solid var(--rule)',
      padding: size === 'mobile' ? 20 : 32,
    }}>
      <div className="t-eyebrow" style={{ marginBottom: 16 }}>Como citar esta análise</div>
      <div style={{ display: 'grid', gap: 18 }}>
        {[['ABNT', abnt], ['APA', apa]].map(([fmt, txt]) => (
          <div key={fmt}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
              <span style={{ fontFamily: 'var(--sans)', fontSize: 11, fontWeight: 600, letterSpacing: '0.1em', color: 'var(--ink-2)' }}>{fmt}</span>
              <button style={{
                background: 'transparent',
                border: 0,
                fontFamily: 'var(--sans)',
                fontSize: 12,
                color: 'var(--ink-3)',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
              }}>
                <Icon.copy /> copiar
              </button>
            </div>
            <p style={{
              fontFamily: 'var(--serif)',
              fontSize: size === 'mobile' ? 13 : 14,
              lineHeight: 1.55,
              color: 'var(--ink-2)',
              margin: 0,
            }}>{txt}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function AnalysisHeader({ size }) {
  const a = ANALYSIS;
  return (
    <div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: size === 'mobile' ? 16 : 24 }}>
        <span className="selo selo-resenha">resenha crítica</span>
        <span className="selo selo-aberto">acesso aberto</span>
      </div>

      <Eyebrow style={{ color: 'var(--gold-deep)' }}>Análise de</Eyebrow>

      <h1 style={{
        fontFamily: 'var(--serif)',
        fontWeight: 400,
        fontSize: size === 'mobile' ? 28 : 48,
        lineHeight: size === 'mobile' ? 1.15 : 1.08,
        letterSpacing: '-0.018em',
        margin: '0 0 24px',
        color: 'var(--ink)',
        textWrap: 'pretty',
      }}>{a.title}</h1>

      <div style={{
        fontFamily: 'var(--sans)',
        fontSize: size === 'mobile' ? 14 : 15,
        color: 'var(--ink-2)',
        lineHeight: 1.55,
        marginBottom: 8,
      }}>
        {a.authors}
      </div>
      <div style={{
        fontFamily: 'var(--sans)',
        fontSize: size === 'mobile' ? 13 : 14,
        color: 'var(--ink-3)',
        lineHeight: 1.5,
      }}>
        <span style={{ fontStyle: 'italic' }}>{a.journal}</span>, v. {a.volume}, n. {a.number}, p. {a.pages}, {a.year}.
      </div>
      <div style={{
        marginTop: 6,
        fontFamily: 'var(--mono)',
        fontSize: 12,
        color: 'var(--ink-4)',
      }}>
        DOI: <a className="link">{a.doi}</a>
      </div>

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: size === 'mobile' ? 20 : 28 }}>
        <button className="btn btn-secondary btn-sm">
          Acessar obra original <Icon.external />
        </button>
        <button className="btn btn-ghost btn-sm">
          <Icon.bookmark /> Snapshot Internet Archive
        </button>
      </div>
    </div>
  );
}

function MetadataFooter({ size }) {
  const a = ANALYSIS;
  return (
    <section style={{
      borderTop: '1px solid var(--rule-strong)',
      paddingTop: size === 'mobile' ? 32 : 48,
      marginTop: size === 'mobile' ? 32 : 48,
      display: 'grid',
      gridTemplateColumns: size === 'mobile' ? '1fr' : '1fr 1fr',
      gap: size === 'mobile' ? 24 : 64,
    }}>
      <div>
        <div className="t-eyebrow" style={{ marginBottom: 14 }}>Autoria & revisão</div>
        <dl style={{ margin: 0, display: 'grid', gap: 14, fontFamily: 'var(--sans)', fontSize: 13 }}>
          <div>
            <dt style={{ color: 'var(--ink-3)', marginBottom: 2 }}>Análise estrutural</dt>
            <dd style={{ margin: 0, color: 'var(--ink)' }}>{a.analyst}</dd>
          </div>
          <div>
            <dt style={{ color: 'var(--ink-3)', marginBottom: 2 }}>Revisão estrutural (assinada)</dt>
            <dd style={{ margin: 0, color: 'var(--ink)' }}>{a.reviewersOpen.join(' · ')}</dd>
          </div>
          <div>
            <dt style={{ color: 'var(--ink-3)', marginBottom: 2 }}>Revisão da resenha (cega)</dt>
            <dd style={{ margin: 0, color: 'var(--ink-2)', fontStyle: 'italic' }}>revisor A · revisor B</dd>
          </div>
        </dl>
      </div>
      <div>
        <div className="t-eyebrow" style={{ marginBottom: 14 }}>Versionamento & licença</div>
        <dl style={{ margin: 0, display: 'grid', gap: 14, fontFamily: 'var(--sans)', fontSize: 13 }}>
          <div>
            <dt style={{ color: 'var(--ink-3)', marginBottom: 2 }}>Versão atual</dt>
            <dd style={{ margin: 0, color: 'var(--ink)' }}>
              {a.version} · {a.versionDate}
              <a className="link" style={{ marginLeft: 8, fontSize: 12 }}>histórico (3)</a>
            </dd>
          </div>
          <div>
            <dt style={{ color: 'var(--ink-3)', marginBottom: 2 }}>Publicado no acervo</dt>
            <dd style={{ margin: 0, color: 'var(--ink)' }}>{a.publishedDate}</dd>
          </div>
          <div>
            <dt style={{ color: 'var(--ink-3)', marginBottom: 2 }}>Licença</dt>
            <dd style={{ margin: 0, color: 'var(--ink)' }}>
              CC BY-NC 4.0 — atribuição obrigatória, uso não-comercial.
            </dd>
          </div>
        </dl>
      </div>
    </section>
  );
}

// ─── Mobile Análise ───────────────────────────────────────────────
function AnaliseMobile() {
  const a = ANALYSIS;
  return (
    <div className="frame-mobile" data-screen-label="03 Análise · Mobile">
      <NavMobile showSearch />

      {/* Breadcrumb */}
      <div style={{
        padding: '12px 20px',
        fontFamily: 'var(--sans)',
        fontSize: 12,
        color: 'var(--ink-3)',
        borderBottom: '1px solid var(--rule)',
      }}>
        <a className="link" style={{ color: 'var(--ink-3)' }}>Acervo</a> / <span>análise</span>
      </div>

      <section style={{ padding: '28px 20px 32px' }}>
        <AnalysisHeader size="mobile" />
      </section>

      <ReviewCallout text={a.reviewText} size="mobile" />

      <section style={{ padding: '32px 20px 16px' }}>
        <div className="t-eyebrow" style={{ marginBottom: 4 }}>Grade de análise</div>
        <h2 className="t-h2" style={{ margin: '0 0 8px', fontSize: 22 }}>
          A obra atravessada pela grade AnCo
        </h2>
        <p className="t-small" style={{ margin: 0 }}>
          Treze campos, ocultos quando vazios.
        </p>
        <div style={{ marginTop: 12 }}>
          {Object.entries(a.fields).map(([label, f]) => (
            <FieldBlock key={label} label={label} value={f.value} kind={f.kind} size="mobile" />
          ))}
        </div>
      </section>

      <section style={{ padding: '24px 20px 32px' }}>
        <CitationBlock size="mobile" />
      </section>

      <section style={{ padding: '0 20px 40px' }}>
        <MetadataFooter size="mobile" />
      </section>

      <Footer compact />
    </div>
  );
}

// ─── Desktop Análise ──────────────────────────────────────────────
function AnaliseDesktop() {
  const a = ANALYSIS;
  return (
    <div className="frame-desktop" data-screen-label="03 Análise · Desktop">
      <NavDesktop active="acervo" />

      {/* Breadcrumb */}
      <div style={{
        padding: '14px 56px',
        fontFamily: 'var(--sans)',
        fontSize: 12,
        color: 'var(--ink-3)',
        borderBottom: '1px solid var(--rule)',
      }}>
        <a className="link" style={{ color: 'var(--ink-3)' }}>Acervo</a> / <a className="link" style={{ color: 'var(--ink-3)' }}>Educação</a> / análise
      </div>

      {/* Header — full bleed editorial */}
      <section style={{
        padding: '64px 56px 56px',
        maxWidth: 900,
        margin: '0 auto',
      }}>
        <AnalysisHeader size="desktop" />
      </section>

      {/* Review callout — wider */}
      <ReviewCallout text={a.reviewText} size="desktop" />

      {/* Two-column body: structural grid + sticky sidebar */}
      <section style={{
        padding: '64px 56px 32px',
        display: 'grid',
        gridTemplateColumns: 'minmax(0, 720px) 280px',
        gap: 80,
        maxWidth: 1180,
        margin: '0 auto',
        alignItems: 'start',
      }}>
        <div>
          <div className="t-eyebrow" style={{ marginBottom: 8 }}>Grade de análise</div>
          <h2 style={{
            fontFamily: 'var(--serif)', fontWeight: 400, fontSize: 32,
            lineHeight: 1.15, letterSpacing: '-0.012em', margin: '0 0 8px',
          }}>
            A obra atravessada pela grade AnCo
          </h2>
          <p className="t-small" style={{ margin: '0 0 8px' }}>
            Treze campos derivados da metodologia do grupo. Campos vazios são ocultos.
          </p>
          <div style={{ marginTop: 16 }}>
            {Object.entries(a.fields).map(([label, f]) => (
              <FieldBlock key={label} label={label} value={f.value} kind={f.kind} size="desktop" />
            ))}
          </div>
        </div>

        <aside style={{ position: 'sticky', top: 24 }}>
          <div style={{
            border: '1px solid var(--rule)',
            background: 'var(--paper)',
            padding: 20,
          }}>
            <div className="t-eyebrow" style={{ marginBottom: 12 }}>Nesta página</div>
            <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: 8, fontFamily: 'var(--sans)', fontSize: 13 }}>
              <li><a className="link" style={{ color: 'var(--ink-2)' }}>Cabeçalho</a></li>
              <li><a className="link" style={{ color: 'var(--gold-deep)' }}>Resenha crítica</a></li>
              <li><a className="link" style={{ color: 'var(--ink-2)' }}>Grade de análise</a></li>
              <li><a className="link" style={{ color: 'var(--ink-2)' }}>Como citar</a></li>
              <li><a className="link" style={{ color: 'var(--ink-2)' }}>Autoria & revisão</a></li>
            </ul>
          </div>

          <div style={{
            marginTop: 16,
            padding: 20,
            background: 'var(--paper-2)',
            border: '1px solid var(--rule)',
          }}>
            <div className="t-eyebrow" style={{ marginBottom: 10 }}>Análise rápida</div>
            <dl style={{ margin: 0, display: 'grid', gap: 10, fontFamily: 'var(--sans)', fontSize: 12 }}>
              <div><dt style={{ color: 'var(--ink-3)' }}>Pertinência</dt><dd style={{ margin: 0, color: 'var(--ink)', fontWeight: 500 }}>sim</dd></div>
              <div><dt style={{ color: 'var(--ink-3)' }}>Define o conceito</dt><dd style={{ margin: 0, color: 'var(--ink)', fontWeight: 500 }}>sim</dd></div>
              <div><dt style={{ color: 'var(--ink-3)' }}>Base bibliográfica</dt><dd style={{ margin: 0, color: 'var(--ink)' }}>{a.base}</dd></div>
              <div><dt style={{ color: 'var(--ink-3)' }}>Tem resenha</dt><dd style={{ margin: 0, color: 'var(--ink)', fontWeight: 500 }}>sim · revisão cega</dd></div>
            </dl>
          </div>

          <div style={{ marginTop: 16, fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--ink-3)', lineHeight: 1.5 }}>
            <Icon.link style={{ marginRight: 4 }} /> URL estável<br />
            <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink-2)', wordBreak: 'break-all' }}>
              anco.ppgdc.org.br/a/2025-santos-quilombola
            </span>
          </div>
        </aside>
      </section>

      {/* Citation */}
      <section style={{ padding: '24px 56px 32px', maxWidth: 1180, margin: '0 auto' }}>
        <div style={{ maxWidth: 720 }}>
          <CitationBlock size="desktop" />
        </div>
      </section>

      {/* Metadata */}
      <section style={{ padding: '0 56px 64px', maxWidth: 1180, margin: '0 auto' }}>
        <div style={{ maxWidth: 720 }}>
          <MetadataFooter size="desktop" />
        </div>
      </section>

      <Footer />
    </div>
  );
}

Object.assign(window, { AnaliseMobile, AnaliseDesktop });

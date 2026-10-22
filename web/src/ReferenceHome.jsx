import React from 'react';
import './reference-home.css';

const NAVIGATION = [
  ['home', 'Home'], ['explore', 'Explore demand'], ['compare', 'Compare histories'],
  ['categories', 'Categories'], ['about', 'About'],
];

// Fit the complete landscape artworks to each frame; labels remain live HTML.
const QUESTIONS = [
  { question: 'What keeps selling?', description: 'Products that build demand over time.', href: '#/explore?question=lasting', x: 44, width: 464 },
  { question: 'What sells in a burst?', description: 'Products with short, concentrated sales spikes.', href: '#/explore?question=spikes', x: 532, width: 449 },
  { question: 'Does the bigger peak win?', description: 'Peak intensity versus total observed sales.', href: '#/compare', x: 1003, width: 454 },
  { question: 'Which categories behave differently?', description: 'Demand patterns across garment groups.', href: '#/categories', x: 1480, width: 458 },
];

export default function ReferenceHome() {
  return <div className="reference-page">
    <a className="skip-link" href="#reference-content" onClick={event => {
      event.preventDefault(); document.getElementById('reference-content').focus();
    }}>Skip to content</a>
    <main id="reference-content" className="reference-page-main" tabIndex={-1}>
    <div className="reference-home">
    <header className="reference-header">
      <nav aria-label="Main navigation">{NAVIGATION.map(([page, label]) =>
        <a key={page} href={`#/${page}`} aria-current={page === 'home' ? 'page' : undefined}>{label}</a>
      )}</nav>
    </header>
    <div className="reference-content">
      <div className="reference-art" aria-hidden="true">
        <img src="/art/home-reference.png" width="1672" height="941" alt="" fetchPriority="high"/>
      </div>
      <section className="reference-copy" aria-labelledby="reference-title">
        <h1 id="reference-title"><span>Demand,</span><span>beyond the peak.</span></h1>
        <p>Explore which fashion products keep selling,<br className="reference-break"/>
          which sell in a burst, and how their histories<br className="reference-break"/>
          compare.</p>
        <a className="reference-explore" href="#/explore?question=lasting"><span>Explore demand</span><span aria-hidden="true">⟶</span></a>
      </section>
    </div>
    <footer className="reference-footer">H&amp;M Fashion Demand Momentum · An independent case study</footer>
    </div>
    <section className="demand-questions" aria-labelledby="demand-questions-title">
      <h2 id="demand-questions-title">Follow the shape of demand.</h2>
      <div className="demand-questions-grid">
        {QUESTIONS.map(({ question, description, href, x, width }) =>
          <a className="demand-question" href={href} key={href}>
            <div className="demand-question-frame">
              <img src="/art/demand-card-artwork-wide.png" alt="" width="1983" height="793" loading="lazy"
                style={{ width: `${1983 / width * 100}%`, height: `${793 / 335 * 100}%`, left: `${-x / width * 100}%`, top: 0, transform: `translateY(${-254 / 793 * 100}%)` }}/>
              <h3>{question}</h3>
            </div>
            <p>{description}</p>
          </a>
        )}
      </div>
    </section>
    <section className="discovery-section" aria-labelledby="discovery-title">
      <div className="discovery-panel">
        <span className="discovery-pill">Demand study</span>
        <h2 id="discovery-title">The peak isn’t the<br/><em>end of the story.</em></h2>
        <p className="discovery-introduction">Sales often keep accumulating long after<br className="discovery-break"/> demand reaches its highest point.</p>
        <div className="discovery-statistic">
          {/* Validated export: median post_peak_share_pct = 62.65 across 31,833 boundary-complete histories. */}
          <strong>≈63%</strong>
          <p>Median share of observed units sold<br className="discovery-break"/> after the smoothed demand peak.</p>
        </div>
        <div className="discovery-panel-footer">
          <p>Across 31,833 eligible histories passing dataset-boundary checks.</p>
          <a href="#/explore?question=lasting">Explore the histories →</a>
        </div>
      </div>
    </section>
    </main>
  </div>;
}

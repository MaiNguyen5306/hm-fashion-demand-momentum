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
    <section className="lily-discovery" aria-labelledby="lily-discovery-title">
      <div className="lily-discovery-photo">
        <img src="/art/discovery-lily.png" alt="" width="1672" height="941" loading="lazy"/>
        <h2 id="lily-discovery-title">The peak isn’t the<br/><em>end of the story.</em></h2>
      </div>
      <div className="lily-discovery-details">
        <div className="lily-discovery-story">
          <span className="lily-discovery-eyebrow">Demand study</span>
          {/* Rounded from the validated product-level median of 62.65%. */}
          <strong>63%</strong>
          <p>Median share of observed units sold after the smoothed demand peak.</p>
          <p className="lily-discovery-description">Sales often keep accumulating after demand reaches its highest point.</p>
        </div>
        <figure className="lily-discovery-chart">
          <svg viewBox="0 0 700 390" role="img" aria-labelledby="lily-chart-title lily-chart-description">
            <title id="lily-chart-title">Sales continue after the peak</title>
            <desc id="lily-chart-description">Illustrative curve, not an individual product history. A smoothed demand peak is followed by a long declining tail. The shaded region indicates sales after the peak, without encoding the population median.</desc>
            <path d="M205 75 C260 75 275 195 365 244 S535 310 670 320 L670 340 L205 340 Z" fill="#f5e0e6" fillOpacity=".65"/>
            <path d="M20 330 C95 310 140 75 205 75 S275 195 365 244 S535 310 670 320" fill="none" stroke="#111" strokeWidth="2.5"/>
            <path d="M20 340 H675" fill="none" stroke="#111" strokeWidth="1"/>
            <path d="M205 75 V340" fill="none" stroke="#555" strokeWidth="1" strokeDasharray="4 4"/>
            <circle cx="205" cy="75" r="5" fill="#111"/>
            <text x="335" y="195" fill="#111" fontSize="19">After the peak</text>
            <text x="350" y="380" textAnchor="middle" fill="#111" fontSize="16">Time since first observed sale →</text>
          </svg>
          <figcaption>Illustrative curve · not an individual product history</figcaption>
        </figure>
      </div>
    </section>
    <section className="catalog-invitation" aria-label="Dataset scale and exploration">
      <dl className="catalog-scale">
        <div className="catalog-scale-card catalog-scale-purchases">
          <span className="catalog-scale-star" aria-hidden="true">★</span>
          <dt>purchases studied</dt><dd>31.8 million</dd>
        </div>
        <div className="catalog-scale-card catalog-scale-histories">
          <span className="catalog-scale-star" aria-hidden="true">★</span>
          <dt>eligible product histories</dt><dd>44,014</dd>
        </div>
        <div className="catalog-scale-card catalog-scale-period">
          <span className="catalog-scale-star" aria-hidden="true">★</span>
          <dt>dataset period</dt>
          <dd><time dateTime="2018-09">September 2018</time> -<br/><time dateTime="2020-09">September 2020</time></dd>
        </div>
      </dl>
      <a className="catalog-explore" href="#/explore">Explore now <span aria-hidden="true">→</span></a>
    </section>
    </main>
  </div>;
}

// Plain ES module, inlined into the built page so the site works as one file.
//
// Navigation is a cascade: your seat, then who is in the hand (nobody, one
// rival, or two earlier players), then the situations that pair unlocks. All of
// that structure is precomputed in web/src/data/charts.json (see
// scripts/build_web_data.py); this file only indexes and renders it.
//
// @typedef {{ color: string, from: number, to: number }} Segment
// @typedef {{ id: string, label: string, sub: string }} Situation
// @typedef {{ rival: string, label: string, side: "before"|"after",
//   situations: Situation[] }} Pair
// @typedef {{ opener: string, openerLabel: string, third: string,
//   thirdLabel: string, situations: Situation[] }} Triple
// @typedef {{ solo: Situation|null, pairs: Pair[], triples: Triple[] }} Nav
// @typedef {{ id: string, family: string, familyLabel: string, hero: string,
//   headline: string, chip: string, decision: string,
//   steps: { seat: string, action: string }[], history: string[],
//   rivals: string[], stat: string, action: string,
//   legend: { color: string, label: string }[], g: string }} Spot
// @typedef {{ meta: object, patterns: Segment[][], hands: string[],
//   combos: number[], spots: Spot[], nav: Record<string, Nav>,
//   heroes: { id: string, label: string }[] }} Payload

const OUT_OF_RANGE = '#1F1E1E';
const COMBOS_TOTAL = 1326;
const HINT = 'Keys: 1-6 seat · [ ] situation · t two players before you';

/** @type {Payload} */
const payload = JSON.parse(document.getElementById('payload').textContent);

const CW = payload.meta.codeWidth;
const PATTERNS = payload.patterns;
const HANDS = payload.hands;
const COMBOS = payload.combos;
const BY_ID = new Map(payload.spots.map((spot) => [spot.id, spot]));

const el = {
  positions: document.querySelectorAll('.pos'),
  nav: document.getElementById('nav'),
  grid: document.getElementById('grid'),
  history: document.getElementById('history'),
  cellinfo: document.getElementById('cellinfo'),
  legend: document.getElementById('legend'),
  stat: document.getElementById('stat'),
  copy: document.getElementById('copy'),
  hint: document.getElementById('hint'),
};

const state = {
  hero: 'utg',
  /** rival seat id, or null for "everyone folded"; the opener in two-rival mode */
  rival: null,
  /** the third player when two rivals are in the hand */
  third: null,
  twoWay: false,
  spot: null,
};

function tree() {
  return payload.nav[state.hero];
}

/** @param {string} id @returns {Spot} */
function spot(id) {
  return BY_ID.get(id);
}

/** Situations unlocked by the current selection. */
function situations() {
  const nav = tree();
  if (state.twoWay) {
    const triple = nav.triples.find(
      (candidate) => candidate.opener === state.rival && candidate.third === state.third,
    );
    return triple ? triple.situations : [];
  }
  if (state.rival === null) return nav.solo ? [nav.solo] : [];
  const pair = nav.pairs.find((candidate) => candidate.rival === state.rival);
  return pair ? pair.situations : [];
}

function current() {
  return spot(state.spot) ?? spot(situations()[0].id);
}

/** Repair the selection after a change so it always points at a real spot. */
function normalise() {
  const nav = tree();
  if (state.twoWay && !nav.triples.length) state.twoWay = false;

  if (state.twoWay) {
    const openers = [...new Set(nav.triples.map((triple) => triple.opener))];
    if (!openers.includes(state.rival)) state.rival = openers[0];
    const thirds = nav.triples
      .filter((triple) => triple.opener === state.rival)
      .map((triple) => triple.third);
    if (!thirds.includes(state.third)) state.third = thirds[0];
  } else if (state.rival === null && !nav.solo) {
    state.rival = nav.pairs[0].rival; // the big blind never opens
  } else if (state.rival !== null && !nav.pairs.some((pair) => pair.rival === state.rival)) {
    state.rival = null;
  }

  const list = situations();
  if (!list.some((situation) => situation.id === state.spot)) {
    state.spot = list[0].id;
  }
}

function codes(chart) {
  const out = [];
  for (let i = 0; i < chart.g.length; i += CW) out.push(parseInt(chart.g.slice(i, i + CW), 36));
  return out;
}

function background(segments) {
  if (segments.length === 1) return segments[0].color;
  const stops = segments
    .map((segment) => `${segment.color} ${segment.from}% ${segment.to}%`)
    .join(', ');
  return `linear-gradient(to right, ${stops})`;
}

function actionLabel(chart, color) {
  if (color === OUT_OF_RANGE) return 'Not in range';
  const entry = chart.legend.find((candidate) => candidate.color === color);
  return entry ? entry.label : 'Unknown';
}

function fractions(chart, index) {
  return PATTERNS[codes(chart)[index]].map((segment) => ({
    label: actionLabel(chart, segment.color),
    pct: Math.round(segment.to - segment.from),
    color: segment.color,
  }));
}

function playedShare(chart, color) {
  let combos = 0;
  codes(chart).forEach((pattern, index) => {
    for (const segment of PATTERNS[pattern]) {
      if (segment.color !== color) continue;
      combos += (COMBOS[index] * (segment.to - segment.from)) / 100;
    }
  });
  return (combos / COMBOS_TOTAL) * 100;
}

function rangeText(chart) {
  const rival = chart.rivals.length ? chart.rivals.join(' + ') : 'everyone folded';
  const lines = [`${chart.hero} · ${chart.chip} (${rival}) — ${chart.stat}`];
  const groups = chart.legend
    .filter((entry) => entry.label !== 'Fold')
    .map((entry) => ({ label: entry.label, color: entry.color, hands: [] }));

  codes(chart).forEach((pattern, index) => {
    for (const segment of PATTERNS[pattern]) {
      const pct = Math.round(segment.to - segment.from);
      if (pct === 0) continue;
      const group = groups.find((candidate) => candidate.color === segment.color);
      if (!group) continue;
      const hand = HANDS[index];
      group.hands.push(pct >= 100 ? hand : `${hand} ${pct}%`);
    }
  });

  for (const group of groups) {
    if (!group.hands.length) continue;
    lines.push(`${group.label} (${playedShare(chart, group.color).toFixed(1)}%): ${group.hands.join(' ')}`);
  }
  return lines.join('\n');
}

function legendRank(chart, color) {
  const order = ['Fold', 'Call', 'All-in', 'Not in range', 'Raise'];
  const label = actionLabel(chart, color);
  const found = order.findIndex((prefix) => label.startsWith(prefix));
  return found === -1 ? order.length : found;
}

// ---------------------------------------------------------------- rendering

function chip(options) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'chip';
  button.classList.toggle('is-active', Boolean(options.active));
  button.classList.toggle('is-muted', Boolean(options.disabled));
  button.disabled = Boolean(options.disabled);
  if (options.title) button.title = options.title;
  button.setAttribute('aria-pressed', String(Boolean(options.active)));

  const main = document.createElement('span');
  main.className = 'chip-main';
  main.textContent = options.text;
  button.append(main);

  if (options.sub) {
    const sub = document.createElement('span');
    sub.className = 'chip-sub';
    sub.textContent = options.sub;
    button.append(sub);
  }
  if (options.onClick) button.addEventListener('click', options.onClick);
  return button;
}

function row(label, nodes) {
  const wrapper = document.createElement('div');
  wrapper.className = 'step';
  const tag = document.createElement('span');
  tag.className = 'step-label';
  tag.textContent = label;
  const chips = document.createElement('div');
  chips.className = 'chips';
  chips.append(...nodes);
  wrapper.append(tag, chips);
  return wrapper;
}

function renderPositions() {
  el.positions.forEach((button) => {
    const active = button.dataset.hero === state.hero;
    button.classList.toggle('is-active', active);
    button.setAttribute('aria-pressed', String(active));
  });
}

function renderNav() {
  const nav = tree();
  const rows = [];

  // step 2: who is in the hand
  const rivalChips = [
    chip({
      text: 'Nobody',
      sub: nav.solo ? nav.solo.label : 'the big blind never opens',
      active: !state.twoWay && state.rival === null,
      disabled: !nav.solo,
      title: nav.solo ? 'Everyone folded to you' : 'The big blind never gets to open',
      onClick: () => {
        state.twoWay = false;
        state.rival = null;
        normalise();
        render();
      },
    }),
  ];

  for (const side of ['before', 'after']) {
    const group = nav.pairs.filter((pair) => pair.side === side);
    if (!group.length) continue;
    const tag = document.createElement('span');
    tag.className = 'side-tag';
    tag.textContent = side === 'before' ? '↑ before you' : '↓ after you';
    rivalChips.push(tag);
    for (const pair of group) {
      rivalChips.push(
        chip({
          text: pair.label,
          sub: `${pair.situations.length} spots`,
          active: !state.twoWay && state.rival === pair.rival,
          onClick: () => {
            state.twoWay = false;
            state.rival = pair.rival;
            state.third = null;
            normalise();
            render();
          },
        }),
      );
    }
  }

  if (nav.triples.length) {
    rivalChips.push(
      chip({
        text: 'Two players',
        sub: `before you · ${nav.triples.length}`,
        active: state.twoWay,
        onClick: () => {
          state.twoWay = !state.twoWay;
          state.third = null;
          if (state.twoWay) state.rival = nav.triples[0].opener;
          normalise();
          render();
        },
      }),
    );
  }
  rows.push(row('Rival', rivalChips));

  if (state.twoWay) {
    const openers = [...new Set(nav.triples.map((triple) => triple.opener))];
    rows.push(
      row(
        'Opened',
        openers.map((opener) =>
          chip({
            text: opener.toUpperCase(),
            active: state.rival === opener,
            onClick: () => {
              state.rival = opener;
              state.third = null;
              normalise();
              render();
            },
          }),
        ),
      ),
    );
    const thirds = nav.triples
      .filter((triple) => triple.opener === state.rival)
      .map((triple) => triple.third);
    rows.push(
      row(
        'Then',
        thirds.map((third) =>
          chip({
            text: third.toUpperCase(),
            sub: '3-bet or call',
            active: state.third === third,
            onClick: () => {
              state.third = third;
              normalise();
              render();
            },
          }),
        ),
      ),
    );
  }

  // step 3: the situation those seats unlock
  rows.push(
    row(
      'Situation',
      situations().map((situation) =>
        chip({
          text: situation.label,
          sub: situation.sub,
          active: state.spot === situation.id,
          onClick: () => {
            state.spot = situation.id;
            render();
          },
        }),
      ),
    ),
  );

  el.nav.replaceChildren(...rows);
}

function renderGrid() {
  const chart = current();
  const patterns = codes(chart);
  const cells = el.grid.children;
  for (let index = 0; index < HANDS.length; index += 1) {
    const cell = cells[index];
    const segments = PATTERNS[patterns[index]];
    cell.style.background = background(segments);
    cell.classList.toggle(
      'is-dark',
      segments.every((segment) => segment.color === OUT_OF_RANGE),
    );
    cell.classList.remove('is-picked');
    cell.setAttribute(
      'aria-label',
      `${HANDS[index]}: ${fractions(chart, index)
        .map((fraction) => `${fraction.label} ${fraction.pct}%`)
        .join(', ')}`,
    );
  }
}

function describe(index) {
  const chart = current();
  const hand = HANDS[index];
  const parts = fractions(chart, index);
  if (parts.length === 1 && parts[0].label === 'Not in range') {
    el.cellinfo.innerHTML = `<b>${hand}</b><span class="muted">not in range: the previous player never holds this hand</span>`;
    return;
  }
  const chips = parts
    .map(
      (part) =>
        `<span class="frac"><i style="background:${part.color}"></i>${part.label} <b>${part.pct}%</b></span>`,
    )
    .join('');
  el.cellinfo.innerHTML = `<b>${hand}</b><span class="muted">${COMBOS[index]} combos</span><span class="fracs">${chips}</span>`;
}

function renderPanel() {
  const chart = current();
  el.history.replaceChildren(
    ...chart.history.map((line, index) => {
      const item = document.createElement('li');
      item.textContent = line;
      if (index === chart.history.length - 1) item.className = 'is-last';
      return item;
    }),
  );

  const used = new Set();
  codes(chart).forEach((pattern) =>
    PATTERNS[pattern].forEach((segment) => used.add(segment.color)),
  );
  el.legend.replaceChildren(
    ...Array.from(used)
      .sort((a, b) => legendRank(chart, a) - legendRank(chart, b))
      .map((color) => {
        const item = document.createElement('li');
        const swatch = document.createElement('i');
        swatch.style.background = color;
        item.append(swatch, document.createTextNode(actionLabel(chart, color)));
        return item;
      }),
  );

  el.stat.textContent = `${chart.decision} · ${chart.stat}`;
  el.cellinfo.innerHTML = '<span class="muted">Hover or tap a hand for its exact mix</span>';
}

function syncHash() {
  const target = `#${state.hero}/${state.spot}`;
  if (window.location.hash !== target) window.history.replaceState(null, '', target);
}

function render() {
  renderPositions();
  renderNav();
  renderGrid();
  renderPanel();
  syncHash();
}

// ------------------------------------------------------------------ actions

function pickHero(hero) {
  if (hero === state.hero) return;
  state.hero = hero;
  state.twoWay = false;
  state.rival = null;
  state.third = null;
  normalise();
  render();
}

function cycleSituation(step) {
  const list = situations();
  const index = list.findIndex((situation) => situation.id === state.spot);
  state.spot = list[(index + step + list.length) % list.length].id;
  render();
}

/** Restore a selection from a spot id, used for deep links. */
function selectSpot(id) {
  const chart = spot(id);
  if (!chart) return false;
  state.hero = chart.hero.toLowerCase();
  state.rival = chart.rivals.length ? chart.rivals[0].toLowerCase() : null;
  state.twoWay = chart.rivals.length > 1;
  state.third = chart.rivals.length > 1 ? chart.rivals[1].toLowerCase() : null;
  state.spot = id;
  normalise();
  return true;
}

function boot() {
  el.grid.replaceChildren(
    ...HANDS.map((hand, index) => {
      const cell = document.createElement('div');
      cell.className = 'cell';
      cell.textContent = hand;
      cell.dataset.index = String(index);
      return cell;
    }),
  );

  el.positions.forEach((button) => {
    button.addEventListener('click', () => pickHero(button.dataset.hero));
  });

  el.grid.addEventListener('pointerover', (event) => {
    const cell = event.target.closest('.cell');
    if (cell) describe(Number(cell.dataset.index));
  });

  el.grid.addEventListener('click', (event) => {
    const cell = event.target.closest('.cell');
    if (!cell) return;
    for (const sibling of el.grid.children) sibling.classList.remove('is-picked');
    cell.classList.add('is-picked');
    describe(Number(cell.dataset.index));
  });

  el.copy.addEventListener('click', async () => {
    const text = rangeText(current());
    try {
      await navigator.clipboard.writeText(text);
      el.hint.textContent = 'Range copied to the clipboard.';
    } catch {
      el.hint.textContent = text;
    }
    window.setTimeout(() => {
      el.hint.textContent = HINT;
    }, 2400);
  });

  document.addEventListener('keydown', (event) => {
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    const seats = payload.heroes;
    const digit = Number(event.key);
    if (Number.isInteger(digit) && digit >= 1 && digit <= seats.length) {
      pickHero(seats[digit - 1].id);
      return;
    }
    if (event.key === '[' || event.key === ']') {
      cycleSituation(event.key === ']' ? 1 : -1);
      return;
    }
    if (event.key === 't' && tree().triples.length) {
      state.twoWay = !state.twoWay;
      state.third = null;
      if (state.twoWay) state.rival = tree().triples[0].opener;
      normalise();
      render();
    }
  });

  const [hashHero, hashSpot] = window.location.hash.replace(/^#/, '').split('/');
  const restored =
    hashSpot &&
    spot(hashSpot) &&
    spot(hashSpot).hero.toLowerCase() === hashHero &&
    selectSpot(hashSpot);
  if (!restored) {
    const known = payload.heroes.some((hero) => hero.id === hashHero);
    if (known) state.hero = hashHero;
    normalise();
  }
  render();

  el.hint.textContent = HINT;
  document.body.dataset.ready = 'true';
}

boot();

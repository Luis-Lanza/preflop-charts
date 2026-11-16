// Plain ES module, inlined into the built page so the site works as one file.
// Types live in JSDoc so an editor can still check it.
//
// @typedef {{ color: string, from: number, to: number }} Segment
// @typedef {{ color: string, label: string }} LegendEntry
// @typedef {{ id: string, family: string, familyLabel: string, hero: string,
//   heroLabel: string, headline: string, decision: string, history: string[],
//   stat: string, action: string, legend: LegendEntry[], g: string }} Spot
// @typedef {{ id: string, label: string, spots: Spot[] }} Hero
// @typedef {{ meta: object, patterns: Segment[][], hands: string[],
//   combos: number[], heroes: Hero[] }} Payload

const OUT_OF_RANGE = '#1F1E1E';
const COMBOS_TOTAL = 1326;
const HINT = 'Keys: 1-6 pick a seat · [ and ] cycle spots';

/** @type {Payload} */
const payload = JSON.parse(document.getElementById('payload').textContent);

const CW = payload.meta.codeWidth;
const PATTERNS = payload.patterns;
const HANDS = payload.hands;
const COMBOS = payload.combos;

const el = {
  positions: document.querySelectorAll('.pos'),
  spots: document.getElementById('spots'),
  grid: document.getElementById('grid'),
  history: document.getElementById('history'),
  cellinfo: document.getElementById('cellinfo'),
  legend: document.getElementById('legend'),
  stat: document.getElementById('stat'),
  copy: document.getElementById('copy'),
  hint: document.getElementById('hint'),
};

const state = {
  hero: payload.heroes[0].id,
  spot: payload.heroes[0].spots[0].id,
};

/** @param {string} id @returns {Hero} */
function heroOf(id) {
  return payload.heroes.find((hero) => hero.id === id) ?? payload.heroes[0];
}

/** @param {string} id @returns {Spot | undefined} */
function spotOf(id) {
  for (const hero of payload.heroes) {
    const found = hero.spots.find((spot) => spot.id === id);
    if (found) return found;
  }
  return undefined;
}

/** @returns {Spot} */
function current() {
  return spotOf(state.spot) ?? heroOf(state.hero).spots[0];
}

/** Pattern codes pack one base-36 index per cell. @param {Spot} spot @returns {number[]} */
function codes(spot) {
  const out = [];
  for (let i = 0; i < spot.g.length; i += CW) {
    out.push(parseInt(spot.g.slice(i, i + CW), 36));
  }
  return out;
}

/** @param {Segment[]} segments */
function background(segments) {
  if (segments.length === 1) return segments[0].color;
  const stops = segments
    .map((segment) => `${segment.color} ${segment.from}% ${segment.to}%`)
    .join(', ');
  return `linear-gradient(to right, ${stops})`;
}

/** @param {Spot} spot @param {string} color */
function actionLabel(spot, color) {
  if (color === OUT_OF_RANGE) return 'Not in range';
  const entry = spot.legend.find((candidate) => candidate.color === color);
  return entry ? entry.label : 'Unknown';
}

/** Per-hand fractions, straight from the frozen colour split.
 * @param {Spot} spot @param {number} index */
function fractions(spot, index) {
  return PATTERNS[codes(spot)[index]].map((segment) => ({
    label: actionLabel(spot, segment.color),
    pct: Math.round(segment.to - segment.from),
    color: segment.color,
  }));
}

/** Combo-weighted share of the range taking one action.
 * @param {Spot} spot @param {string} color */
function playedShare(spot, color) {
  let combos = 0;
  codes(spot).forEach((pattern, index) => {
    for (const segment of PATTERNS[pattern]) {
      if (segment.color !== color) continue;
      combos += (COMBOS[index] * (segment.to - segment.from)) / 100;
    }
  });
  return (combos / COMBOS_TOTAL) * 100;
}

/** Copyable text: one line per action, mixed hands keep their share.
 * @param {Spot} spot */
function rangeText(spot) {
  const lines = [`${spot.heroLabel} · ${spot.headline} — ${spot.stat}`];
  const groups = spot.legend
    .filter((entry) => entry.label !== 'Fold')
    .map((entry) => ({ label: entry.label, color: entry.color, hands: [] }));

  codes(spot).forEach((pattern, index) => {
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
    const share = playedShare(spot, group.color).toFixed(1);
    lines.push(`${group.label} (${share}%): ${group.hands.join(' ')}`);
  }
  return lines.join('\n');
}

/** @param {Spot} spot @param {string} color */
function legendRank(spot, color) {
  const order = ['Fold', 'Call', 'All-in', 'Not in range', 'Raise'];
  const label = actionLabel(spot, color);
  const found = order.findIndex((prefix) => label.startsWith(prefix));
  return found === -1 ? order.length : found;
}

function renderPositions() {
  el.positions.forEach((button) => {
    const active = button.dataset.hero === state.hero;
    button.classList.toggle('is-active', active);
    button.setAttribute('aria-pressed', String(active));
  });
}

function renderSpots() {
  const hero = heroOf(state.hero);
  el.spots.replaceChildren(
    ...hero.spots.map((spot) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'chip';
      button.dataset.spot = spot.id;
      button.classList.toggle('is-active', spot.id === state.spot);
      button.setAttribute('aria-pressed', String(spot.id === state.spot));
      const main = document.createElement('span');
      main.className = 'chip-main';
      main.textContent = spot.headline;
      const sub = document.createElement('span');
      sub.className = 'chip-sub';
      sub.textContent = spot.familyLabel;
      button.append(main, sub);
      return button;
    }),
  );
}

function renderGrid() {
  const spot = current();
  const patterns = codes(spot);
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
      `${HANDS[index]}: ${fractions(spot, index)
        .map((fraction) => `${fraction.label} ${fraction.pct}%`)
        .join(', ')}`,
    );
  }
}

/** @param {number} index */
function describe(index) {
  const spot = current();
  const hand = HANDS[index];
  const parts = fractions(spot, index);
  if (parts.length === 1 && parts[0].label === 'Not in range') {
    el.cellinfo.innerHTML =
      `<b>${hand}</b><span class="muted">not in range: the previous player never holds this hand</span>`;
    return;
  }
  const chips = parts
    .map(
      (part) =>
        `<span class="frac"><i style="background:${part.color}"></i>${part.label} <b>${part.pct}%</b></span>`,
    )
    .join('');
  el.cellinfo.innerHTML =
    `<b>${hand}</b><span class="muted">${COMBOS[index]} combos</span><span class="fracs">${chips}</span>`;
}

function renderPanel() {
  const spot = current();
  el.history.replaceChildren(
    ...spot.history.map((line, index) => {
      const item = document.createElement('li');
      item.textContent = line;
      if (index === spot.history.length - 1) item.className = 'is-last';
      return item;
    }),
  );

  const used = new Set();
  codes(spot).forEach((pattern) =>
    PATTERNS[pattern].forEach((segment) => used.add(segment.color)),
  );
  el.legend.replaceChildren(
    ...Array.from(used)
      .sort((a, b) => legendRank(spot, a) - legendRank(spot, b))
      .map((color) => {
        const item = document.createElement('li');
        const swatch = document.createElement('i');
        swatch.style.background = color;
        item.append(swatch, document.createTextNode(actionLabel(spot, color)));
        return item;
      }),
  );

  el.stat.textContent = `${spot.decision} · ${spot.stat}`;
  el.cellinfo.innerHTML = '<span class="muted">Hover or tap a hand for its exact mix</span>';
}

function syncHash() {
  const target = `#${state.hero}/${state.spot}`;
  if (window.location.hash !== target) window.history.replaceState(null, '', target);
}

/** @param {string} hero @param {string} [spot] */
function select(hero, spot) {
  state.hero = hero;
  const spots = heroOf(hero).spots;
  const wanted = spot ?? state.spot;
  state.spot = spots.some((candidate) => candidate.id === wanted) ? wanted : spots[0].id;
  renderPositions();
  renderSpots();
  renderGrid();
  renderPanel();
  syncHash();
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
    button.addEventListener('click', () => select(button.dataset.hero));
  });

  el.spots.addEventListener('click', (event) => {
    const chip = event.target.closest('.chip');
    if (chip) select(state.hero, chip.dataset.spot);
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
      select(seats[digit - 1].id);
      return;
    }
    if (event.key === '[' || event.key === ']') {
      const spots = heroOf(state.hero).spots;
      const index = spots.findIndex((spot) => spot.id === state.spot);
      const step = event.key === ']' ? 1 : spots.length - 1;
      select(state.hero, spots[(index + step) % spots.length].id);
    }
  });

  const [hashHero, hashSpot] = window.location.hash.replace(/^#/, '').split('/');
  const startHero = payload.heroes.some((hero) => hero.id === hashHero)
    ? hashHero
    : state.hero;
  select(startHero, hashSpot);

  el.hint.textContent = HINT;
  document.body.dataset.ready = 'true';
}

boot();

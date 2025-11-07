// Rysuje wektorowe GUI 80s jako overlay SVG.
// Nic nie importujemy – czysty DOM/SVG.

const hud = document.getElementById('hud');
const svgNS = 'http://www.w3.org/2000/svg';

const svg = document.createElementNS(svgNS, 'svg');
svg.setAttribute('class', 'hud-svg');
svg.setAttribute('viewBox', '0 0 1600 900'); // stały układ – skaluje się do okna
svg.setAttribute('preserveAspectRatio', 'none');
hud.appendChild(svg);

// defs: drobny pattern kropek (dithering)
const defs = document.createElementNS(svgNS, 'defs');
const pattern = document.createElementNS(svgNS, 'pattern');
pattern.setAttribute('id', 'dots');
pattern.setAttribute('x', '0');
pattern.setAttribute('y', '0');
pattern.setAttribute('width', '6');
pattern.setAttribute('height', '6');
pattern.setAttribute('patternUnits', 'userSpaceOnUse');
const dot = document.createElementNS(svgNS, 'circle');
dot.setAttribute('cx', '1.5');
dot.setAttribute('cy', '1.5');
dot.setAttribute('r', '0.7');
dot.setAttribute('fill', '#00ff66');
pattern.appendChild(dot);
defs.appendChild(pattern);
svg.appendChild(defs);

// helpery
function rect(x,y,w,h, cls='hud-stroke', rx=0){
  const r = document.createElementNS(svgNS, 'rect');
  r.setAttribute('x', x); r.setAttribute('y', y);
  r.setAttribute('width', w); r.setAttribute('height', h);
  r.setAttribute('rx', rx);
  r.setAttribute('class', cls);
  svg.appendChild(r);
  return r;
}
function line(x1,y1,x2,y2, cls='hud-stroke'){
  const l = document.createElementNS(svgNS, 'line');
  l.setAttribute('x1', x1); l.setAttribute('y1', y1);
  l.setAttribute('x2', x2); l.setAttribute('y2', y2);
  l.setAttribute('class', cls);
  svg.appendChild(l);
  return l;
}
function textLabel(x,y,txt, cls='hud-text title'){
  const t = document.createElementNS(svgNS, 'text');
  t.setAttribute('x', x); t.setAttribute('y', y);
  t.setAttribute('class', cls);
  t.textContent = txt;
  svg.appendChild(t);
  return t;
}

// GÓRNY PANEL: EDITING CURRENT PARAMETER
rect(60, 40, 620, 140, 'hud-stroke');
textLabel(80, 70, 'EDITING CURRENT PARAMETER:');
textLabel(490, 70, 'TURBULENCE', 'hud-text title pulse');

// Małe okno z „mini-terenem” – tylko kontener (wypełnienie kropkami)
const mini = rect(80, 90, 580, 70, 'hud-stroke', 2);
mini.classList.add('pulse');
const miniDots = rect(80, 90, 580, 70, 'dotfill', 2);

// Skala u dołu panelu
for (let i = 0; i <= 6; i++){
  const x = 80 + i * (580/6);
  line(x, 165, x, 175);
  textLabel(x-16, 195, String(1000 + i*500), 'hud-text tiny');
}
line(80, 175, 660, 175);

// PRAWY PANEL: GEOGRAPHIC REFERENCE + lista
rect(1120, 60, 380, 260, 'hud-stroke');
textLabel(1140, 90, 'GEOGRAPHIC REFERENCE');
rect(1140, 110, 110, 24, 'hud-stroke'); // ikonki (placeholdery)
rect(1260, 110, 110, 24, 'hud-stroke');
rect(1380, 110, 100, 24, 'hud-stroke');

rect(1140, 150, 340, 34, 'btn'); textLabel(1160, 172, 'MOUNTAIN TERRAIN', 'btn-label');
rect(1140, 190, 340, 34, 'btn'); textLabel(1160, 212, 'CITYSCAPE TERRAIN', 'btn-label');
rect(1140, 230, 340, 34, 'btn'); textLabel(1160, 252, 'FOREST TERRAIN', 'btn-label');
rect(1140, 270, 340, 34, 'btn'); textLabel(1160, 292, 'OCEAN TERRAIN', 'btn-label');

// ŚRODKOWA SIATKA „3D” – ramka + podpisy
rect(180, 300, 560, 320, 'hud-stroke', 2);
textLabel(220, 320, '04_LANDFORM/OCEAN', 'hud-text small');
textLabel(220, 340, 'CREATING_NEW_FILE', 'hud-text small');
textLabel(220, 360, 'KEYCODE_69LY746R6', 'hud-text tiny');

// Pasek separatora pod siatką
line(60, 650, 1540, 650);

// Dół: foldery + literki
const folderY = 690, cellW = 200;
for (let i = 0; i < 4; i++){
  const x = 120 + i*cellW;
  // folder – prosta „teczka”
  line(x, folderY, x+120, folderY);
  line(x, folderY, x, folderY-70);
  line(x, folderY-70, x+120, folderY-70);
  line(x+120, folderY-70, x+120, folderY);
  // zakładka
  line(x+15, folderY-70, x+45, folderY-90);
  line(x+45, folderY-90, x+85, folderY-90);
  line(x+85, folderY-90, x+105, folderY-70);
  // podpis
  textLabel(x+30, folderY+30, String.fromCharCode(65+i), 'hud-text title');
  rect(x+24, folderY+40, 22, 22, 'hud-stroke'); // mała ikonka a/b/c/d
  textLabel(x+32, folderY+56, String.fromCharCode(97+i), 'hud-text tiny');
}

// Prawy-dół: okno kodu + przyciski ABORT/EXPORT
rect(1120, 670, 380, 150, 'hud-stroke');
textLabel(1140, 700, 'forest.saveToFolder(folderName);', 'hud-text small');
textLabel(1140, 720, '{', 'hud-text small');
textLabel(1160, 740, '  var ocean = 1;', 'hud-text small');
textLabel(1160, 760, '  landscape.chooseTerrain();', 'hud-text small');
textLabel(1140, 780, '}', 'hud-text small');

rect(1520, 670, 60, 60, 'hud-stroke'); textLabel(1530, 706, 'X', 'hud-text title'); // ABORT
rect(1520, 740, 60, 80, 'hud-stroke'); textLabel(1526, 788, 'EXPORT', 'hud-text tiny');

// Logo
textLabel(1120, 620, 'SUPER', 'hud-text title');
textLabel(1250, 620, 'TERRAIN', 'hud-text xxl pulse');
textLabel(1490, 628, '86', 'hud-text xxl');

// Drobne metadane
textLabel(1160, 640, 'PRODUCT INTERFACE', 'hud-text tiny');
textLabel(1440, 640, 'LAB TECH ©1986', 'hud-text tiny');

// Responsywność: nic nie robimy w JS – SVG skaluje się sam (viewBox)

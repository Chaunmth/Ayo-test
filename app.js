/* ————————————————————————————————————————————————
   Ayo — danse avec ta main

   Principe :
   · Ayo reste fixe au centre
   · la position horizontale de ta main choisit l'image de la danse parmi 32
     (main à gauche = début du mouvement, main à droite = fin)
   · tout le traitement d'image se fait ici, dans le navigateur
   ———————————————————————————————————————————————— */

const $ = (id) => document.getElementById(id);

const stage      = $('stage');
const ayo        = $('ayo');
const trackDot   = $('trackDot');
const statusEl   = $('status');
const cam        = $('cam');
const camFeed    = $('camFeed');
const handDot    = $('handDot');
const song       = $('song');
const loader     = $('loader');
const loaderBar  = $('loaderBar');
const loaderText = $('loaderText');
const intro      = $('intro');
const infoSheet  = $('infoSheet');
const btnSound   = $('btnSound');
const btnCam     = $('btnCam');

// ————— Réglages —————

const SHEET   = { cols: 8, rows: 4, frames: 32 };
const MARGIN  = 0.15;   // bords du champ caméra ignorés (pas besoin de tendre le bras)
const SMOOTH  = 0.18;   // lissage : 0 = figé, 1 = brut
const LOST_MS = 1200;   // délai avant de considérer la main perdue
const VOLUME  = 0.8;

const isSmallScreen = Math.min(window.innerWidth, window.innerHeight) < 560;

// ————— État —————

let pos = 0.5;          // cible 0..1
let smooth = 0.5;       // valeur lissée appliquée
let mode = 'idle';      // 'hand' | 'pointer' | 'idle'
let handSeenAt = 0;
let shownFrame = -1;    // dernière image affichée

let landmarker = null;
let stream = null;
let camOn = false;
let camWasOn = false;
let lastStamp = -1;
let started = false;

const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);

function setStatus(text, cls = '') {
  statusEl.textContent = text;
  statusEl.className = 'status' + (cls ? ' ' + cls : '');
}

// ————— Sprite légère sur petit écran (moins de mémoire à décoder) —————

if (isSmallScreen) {
  ayo.style.backgroundImage = 'url("assets/ayo_sheet_sm.jpg")';
}

// ————— Boucle de rendu —————

function render(ts) {
  // personne aux commandes : Ayo danse tout seul, doucement
  if (mode === 'idle') {
    pos = 0.5 + Math.sin(ts / 2400) * 0.45;
  } else if (mode === 'hand' && ts - handSeenAt > LOST_MS) {
    mode = 'idle';
    handDot.hidden = true;
    setStatus('montre ta main à la caméra');
  }

  smooth += (pos - smooth) * SMOOTH;

  // la position de la main choisit l'image : c'est toi qui déroules la danse
  const i = clamp(Math.round(smooth * (SHEET.frames - 1)), 0, SHEET.frames - 1);
  if (i !== shownFrame) {
    shownFrame = i;
    const col = i % SHEET.cols;
    const row = (i / SHEET.cols) | 0;
    ayo.style.backgroundPosition =
      `${(col / (SHEET.cols - 1)) * 100}% ${(row / (SHEET.rows - 1)) * 100}%`;
  }

  trackDot.style.left = `${smooth * 100}%`;

  requestAnimationFrame(render);
}

// ————— Repli souris / doigt —————

function fromPointer(e) {
  if (mode === 'hand') return;  // la main a la priorité
  const r = stage.getBoundingClientRect();
  pos = clamp((e.clientX - r.left) / r.width, 0, 1);
  if (mode !== 'pointer') {
    mode = 'pointer';
    setStatus(isSmallScreen ? 'glisse ton doigt' : 'souris aux commandes');
  }
}
stage.addEventListener('pointerdown', fromPointer);
stage.addEventListener('pointermove', fromPointer);

// ————— Son —————

function startSound() {
  song.volume = 0;
  song.play().then(() => {
    // fondu d'entrée sur minuteur (et non requestAnimationFrame, qui se met
    // en pause quand l'onglet passe en arrière-plan et laisserait le son à 0)
    const t0 = Date.now();
    const timer = setInterval(() => {
      const k = Math.min(1, (Date.now() - t0) / 900);
      song.volume = k * VOLUME;
      if (k >= 1) clearInterval(timer);
    }, 40);
  }).catch(() => {
    btnSound.textContent = '🔇';
  });
}

btnSound.addEventListener('click', () => {
  if (song.paused) {
    startSound();
    btnSound.textContent = '🔊';
    btnSound.setAttribute('aria-label', 'Couper le son');
  } else {
    song.pause();
    btnSound.textContent = '🔇';
    btnSound.setAttribute('aria-label', 'Remettre le son');
  }
});

// ————— Chargement du modèle (avec progression) —————

async function fetchWithProgress(url, onProgress) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const total = Number(res.headers.get('content-length')) || 0;
  if (!res.body || !total) return new Uint8Array(await res.arrayBuffer());

  const reader = res.body.getReader();
  const chunks = [];
  let got = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    got += value.length;
    onProgress(got / total);
  }
  const out = new Uint8Array(got);
  let off = 0;
  for (const c of chunks) { out.set(c, off); off += c.length; }
  return out;
}

async function loadModel() {
  if (landmarker) return;

  loader.hidden = false;
  loaderText.textContent = 'Chargement du modèle… 0 %';

  const bytes = await fetchWithProgress('vendor/hand_landmarker.task', (p) => {
    const pct = Math.round(p * 100);
    loaderBar.style.width = `${pct}%`;
    loaderText.textContent = `Chargement du modèle… ${pct} %`;
  });

  loaderText.textContent = 'Initialisation…';
  const { FilesetResolver, HandLandmarker } = await import('./vendor/vision_bundle.mjs');
  const fileset = await FilesetResolver.forVisionTasks('vendor/wasm');

  const options = (delegate) => ({
    baseOptions: { modelAssetBuffer: bytes, delegate },
    runningMode: 'VIDEO',
    numHands: 1,
    minHandDetectionConfidence: 0.5,
    minHandPresenceConfidence: 0.5,
    minTrackingConfidence: 0.5,
  });

  try {
    landmarker = await HandLandmarker.createFromOptions(fileset, options('GPU'));
  } catch {
    landmarker = await HandLandmarker.createFromOptions(fileset, options('CPU'));
  }

  // La toute première inférence compile les shaders et bloque plusieurs
  // secondes. On la fait ici, pendant que l'écran de chargement est encore
  // affiché, plutôt qu'au premier mouvement de main (où ça ressemblerait
  // à un plantage).
  loaderText.textContent = 'Préparation…';
  loaderBar.style.width = '100%';
  await new Promise((r) => setTimeout(r, 60));   // laisse le temps d'afficher le texte
  try {
    const warm = document.createElement('canvas');
    warm.width = 320;
    warm.height = 240;
    warm.getContext('2d').fillRect(0, 0, 1, 1);
    lastStamp = performance.now();
    landmarker.detectForVideo(warm, lastStamp);
  } catch { /* le préchauffage est facultatif */ }

  loader.hidden = true;
}

// ————— Caméra —————

function camErrorMessage(err) {
  switch (err && err.name) {
    case 'NotAllowedError':
    case 'SecurityError':
      return 'caméra refusée — autorise-la dans les réglages du navigateur';
    case 'NotFoundError':
    case 'OverconstrainedError':
      return 'aucune caméra détectée';
    case 'NotReadableError':
      return 'caméra déjà utilisée par une autre application';
    default:
      return 'caméra indisponible';
  }
}

async function startCamera() {
  if (!window.isSecureContext) {
    setStatus('la caméra exige une connexion sécurisée (https)', 'warn');
    return;
  }
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    setStatus('navigateur sans accès caméra', 'warn');
    return;
  }

  setStatus('autorise la caméra…');

  try {
    // vidéo uniquement : le micro n'est jamais demandé
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
      audio: false,
    });
  } catch (err) {
    setStatus(camErrorMessage(err), 'warn');
    return;
  }

  camFeed.srcObject = stream;
  try { await camFeed.play(); } catch { /* ignoré : la vidéo est muette */ }

  cam.hidden = false;
  camOn = true;
  btnCam.textContent = 'Couper la caméra';

  try {
    await loadModel();
  } catch (err) {
    loader.hidden = true;
    setStatus('échec du chargement du modèle', 'warn');
    stopCamera();
    return;
  }

  setStatus('montre ta main à la caméra');
  detectLoop();
}

function stopCamera() {
  camOn = false;
  if (stream) {
    stream.getTracks().forEach((t) => t.stop());
    stream = null;
  }
  camFeed.srcObject = null;
  cam.hidden = true;
  handDot.hidden = true;
  btnCam.textContent = 'Activer la caméra';
  if (mode === 'hand') {
    mode = 'idle';
    setStatus('caméra coupée');
  }
}

btnCam.addEventListener('click', () => {
  if (camOn) stopCamera();
  else startCamera();
});

// ————— Détection —————

function detectLoop() {
  if (!camOn || !landmarker) return;

  const now = performance.now();

  if (camFeed.readyState >= 2 && camFeed.videoWidth > 0) {
    // l'horodatage doit être strictement croissant
    const stamp = Math.max(now, lastStamp + 1);
    lastStamp = stamp;

    let result = null;
    try {
      result = landmarker.detectForVideo(camFeed, stamp);
    } catch { /* image ignorée */ }

    const hands = result && result.landmarks;
    if (hands && hands.length) {
      const lm = hands[0];
      // centre de la paume : poignet + base des quatre doigts (plus stable
      // que le bout d'un doigt, qui tremble)
      const ids = [0, 5, 9, 13, 17];
      let sx = 0, sy = 0;
      for (const i of ids) { sx += lm[i].x; sy += lm[i].y; }
      sx /= ids.length;
      sy /= ids.length;

      const mirrored = 1 - sx;   // ta droite = la droite de l'écran
      pos = clamp((mirrored - MARGIN) / (1 - 2 * MARGIN), 0, 1);
      handSeenAt = now;

      if (mode !== 'hand') {
        mode = 'hand';
        setStatus('main détectée', 'ok');
      }

      handDot.hidden = false;
      handDot.style.left = `${(1 - sx) * 100}%`;   // l'aperçu est en miroir
      handDot.style.top = `${sy * 100}%`;
    } else {
      handDot.hidden = true;
    }
  }

  // l'inférence coûte ~8 ms : 30 détections/s sur ordinateur (latence basse),
  // 20 sur mobile (on ménage la batterie)
  setTimeout(detectLoop, isSmallScreen ? 50 : 33);
}

// ————— Hygiène : on relâche la caméra dès que la page passe en arrière-plan —————

document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    camWasOn = camOn;
    if (camOn) stopCamera();
  } else if (camWasOn) {
    camWasOn = false;
    startCamera();
  }
});
window.addEventListener('pagehide', stopCamera);

// ————— Panneau confidentialité —————

$('btnInfo').addEventListener('click', () => { infoSheet.hidden = false; });
$('btnInfoClose').addEventListener('click', () => { infoSheet.hidden = true; });

// ————— Démarrage —————

function begin() {
  if (started) return;
  started = true;
  intro.hidden = true;
  startSound();
  requestAnimationFrame(render);
}

$('btnStartCam').addEventListener('click', () => {
  begin();
  startCamera();
});

$('btnStartNoCam').addEventListener('click', () => {
  begin();
  setStatus(isSmallScreen ? 'glisse ton doigt sur l’écran' : 'bouge la souris');
});

// on précharge la sprite pour éviter un clignotement au démarrage
const pre = new Image();
pre.src = isSmallScreen ? 'assets/ayo_sheet_sm.jpg' : 'assets/ayo_sheet.jpg';

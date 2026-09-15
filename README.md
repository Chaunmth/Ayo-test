# Ayo — danse avec ta main

Expérience web interactive : Ayo, la mascotte de Dakar 2026, reste fixe au centre
et c'est le mouvement de ta main, capté par la webcam, qui déroule sa danse.
Main à gauche, main à droite, et tu le pilotes image par image. Fonctionne aussi
à la souris et au doigt, sur ordinateur comme sur téléphone.

## Comment ça marche

- **Danse** — 32 images extraites de la vidéo d'origine, assemblées en une seule
  sprite sheet. La position de la main choisit l'image : Ayo ne se déplace pas,
  il prend la pose correspondante.
- **Suivi de la main** — [MediaPipe Hand Landmarker](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker)
  en WebAssembly, exécuté dans le navigateur. On utilise le centre de la paume
  (poignet + base des quatre doigts), plus stable que le bout d'un doigt.
- **Lissage** — la position est interpolée à chaque image, sinon le tremblement
  naturel de la main fait vibrer la pose.
- **Repli** — si la caméra est refusée ou indisponible, la souris ou le doigt
  prend le relais. Sans interaction, Ayo danse tout seul, doucement.

## Décisions d'implémentation

| Choix | Raison |
| --- | --- |
| Images normalisées au moment du build | le long du clip, Ayo recule en dansant : 18 % de hauteur en moins et des pieds qui remontent. Piloté à la main, ce glissement se verrait comme un défaut |
| Sprite sheet plutôt que `<video>` scrubbé | le seek vidéo est lent et saccadé, surtout sur iOS |
| Fond de page identique au fond de la sprite (`#d6d4d2`) | le bord de l'image reste invisible |
| Préchauffage du modèle pendant le chargement | la première inférence compile les shaders GPU et bloque plusieurs secondes |
| MediaPipe hébergé dans le dépôt | pas de dépendance à un CDN tiers, et une CSP restreinte à l'origine du site |
| Deux tailles de sprite sheet | la grande fait 2952×2880 : trop de mémoire à décoder sur un téléphone |
| Fondu du son sur minuteur, pas sur `requestAnimationFrame` | rAF se met en pause en arrière-plan et laisserait le volume bloqué à zéro |

Le traitement de l'image est local : la détection tourne dans le navigateur et
la page est limitée par CSP à sa propre origine.

## Poids

| | |
| --- | --- |
| code (html + css + js) | 27 Ko |
| sprite sheet | 454 Ko sur ordinateur, 203 Ko sur mobile |
| musique | 1,40 Mo, chargée en flux |
| **au premier affichage** | **~230 Ko sur mobile**, le reste suit |

Le suivi de la main n'est téléchargé que si l'utilisateur active la caméra :
5,54 Mo pour le modèle (stocké pré-compressé, décompressé par la page : 2 Mo
économisés quelle que soit la configuration du serveur), 8,98 Mo pour le
runtime WebAssembly — 2,72 Mo si le serveur le sert compressé, ce que fait
GitHub Pages pour ce type de fichier. Le navigateur le met ensuite en cache.

## Développement

```bash
node dev-server.js   # http://localhost:8770
```

Un serveur local est nécessaire : l'accès caméra exige un contexte sécurisé
(`localhost` ou `https`), ce qu'un fichier ouvert en `file://` n'est pas.

### Régénérer les assets

```bash
python3 tools/build-sprites.py          # sprite sheets, depuis ayo.mp4

# bande-son, à partir de 1:00 du morceau
ffmpeg -ss 60 -i "source.mp3" -c:a libmp3lame -b:a 128k assets/song.mp3
```

Le script mesure chaque image, impose une hauteur constante et une ligne de sol
fixe, puis assemble la grille 8×4. Il est déterministe : relancé, il produit des
fichiers identiques.

## Structure

```
index.html              page
style.css               styles
app.js                  logique (module ES)
assets/                 sprite sheets + bande-son
vendor/                 MediaPipe (bibliothèque, wasm, modèle)
tools/build-sprites.py  génération des sprite sheets
dev-server.js           serveur local de développement
```

## Crédits

Ayo est la mascotte des Jeux Olympiques de la Jeunesse Dakar 2026.
La bande-son et la vidéo source appartiennent à leurs auteurs respectifs.

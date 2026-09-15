# Ayo — danse avec ta main

Expérience web interactive : Ayo, la mascotte de Dakar 2026, suit le mouvement de
ta main de gauche à droite, capté par la webcam. Fonctionne aussi à la souris et
au doigt, sur ordinateur comme sur téléphone.

## Comment ça marche

- **Danse** — 32 images extraites de la vidéo d'origine, assemblées en une seule
  sprite sheet jouée en aller-retour (pas de saut à la boucle).
- **Suivi de la main** — [MediaPipe Hand Landmarker](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker)
  en WebAssembly, exécuté dans le navigateur. On utilise le centre de la paume
  (poignet + base des quatre doigts), plus stable que le bout d'un doigt.
- **Déplacement** — la position horizontale de la paume est lissée, puis appliquée
  en `translate3d` + une légère inclinaison proportionnelle à la vitesse.
- **Repli** — si la caméra est refusée ou indisponible, la souris ou le doigt
  prend le relais. Sans interaction, Ayo se balance tout seul.

## Détails d'implémentation

| Choix | Raison |
| --- | --- |
| Sprite sheet plutôt que `<video>` scrubbé | le seek vidéo est lent et saccadé, surtout sur iOS |
| Fond de page identique au fond de la sprite (`#d6d4d2`) | le bord de l'image devient invisible quand Ayo se déplace |
| Aller-retour sur les 32 images | le personnage rétrécit légèrement le long du clip : une boucle simple provoquerait un saut de taille |
| Préchauffage du modèle pendant le chargement | la première inférence compile les shaders GPU et bloque plusieurs secondes |
| MediaPipe hébergé dans le dépôt | pas de dépendance à un CDN tiers, et une CSP restreinte à l'origine du site |
| Deux tailles de sprite sheet | la grande fait 2952×2880 : trop de mémoire à décoder sur un téléphone |

Le traitement de l'image est local : la détection tourne dans le navigateur et
la page est limitée par CSP à sa propre origine.

## Développement

```bash
node dev-server.js   # http://localhost:8770
```

Un serveur local est nécessaire : l'accès caméra exige un contexte sécurisé
(`localhost` ou `https`), ce qu'un fichier ouvert en `file://` n'est pas.

### Régénérer les assets

```bash
# sprite sheet (32 images, grille 8×4), recadrée sur le personnage
ffmpeg -i ayo.mp4 -vf "crop=432:844:700:236,scale=369:720:flags=lanczos,tile=8x4" \
  -frames:v 1 -q:v 3 assets/ayo_sheet.jpg

# version mobile
ffmpeg -i ayo.mp4 -vf "crop=432:844:700:236,scale=185:360:flags=lanczos,tile=8x4" \
  -frames:v 1 -q:v 4 assets/ayo_sheet_sm.jpg

# bande-son, à partir de 1:00
ffmpeg -ss 60 -i "source.mp3" -c:a libmp3lame -b:a 128k assets/song.mp3
```

## Structure

```
index.html          page
style.css           styles
app.js              logique (module ES)
assets/             sprite sheets + bande-son
vendor/             MediaPipe (bibliothèque, wasm, modèle)
dev-server.js       serveur local de développement
```

## Crédits

Ayo est la mascotte des Jeux Olympiques de la Jeunesse Dakar 2026.
La bande-son et la vidéo source appartiennent à leurs auteurs respectifs.

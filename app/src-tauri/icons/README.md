# The app's icon

`src/querysolo-mac.svg` and `src/querysolo-linux.svg` are the masters: the prompt mark (`>_` with
a lime cursor, `brand/querysolo-logos.html` direction C; `build-sessions/logo-querysolo-plan.md` L2),
off-white and lime on the deep green. The macOS one sits on the Big Sur canvas — the tile is 824 of 1024
with Apple's corner radius, so it lines up with other Dock icons; the Linux one fills the canvas, because the
desktop neither rounds nor insets. The site's favicon is the Linux master. `tauri.conf.json` points at
this folder and `tauri.linux.conf.json` at `linux/`.

To regenerate every size after editing a master, from `app/`:

```bash
node scripts/icon-masters.mjs          # the two masters to 1024 px PNGs, in Playwright's Chromium
npx tauri icon src-tauri/icons/src/querysolo-mac.png -o src-tauri/icons
npx tauri icon src-tauri/icons/src/querysolo-linux.png -o src-tauri/icons/linux
```

then delete what the bundler does not use (`android/`, `ios/`, `Square*.png`, `StoreLogo.png`,
`64x64.png`) so the set stays the six files the config names.

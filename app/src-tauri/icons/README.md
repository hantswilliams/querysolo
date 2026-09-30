# The app's icon

`src/querysolo-mac.svg` and `src/querysolo-linux.svg` are the masters: the site's wave-and-fish mark
(`web/src/components/exploration/Wordmark.astro`), lime on the deep green (decisions U4,
2026-09-20). The macOS one sits on the Big Sur canvas — the tile is 824 of 1024 with Apple's
corner radius, so it lines up with other Dock icons; the Linux one fills the canvas, because the
desktop neither rounds nor insets. `tauri.conf.json` points at this folder and
`tauri.linux.conf.json` at `linux/`.

To regenerate every size after editing a master, from `app/`:

```bash
python3 -c "import cairosvg; [cairosvg.svg2png(url=f'src-tauri/icons/src/querysolo-{n}.svg', write_to=f'src-tauri/icons/src/querysolo-{n}.png', output_width=1024, output_height=1024) for n in ('mac', 'linux')]"
npx tauri icon src-tauri/icons/src/querysolo-mac.png -o src-tauri/icons
npx tauri icon src-tauri/icons/src/querysolo-linux.png -o src-tauri/icons/linux
```

then delete what the bundler does not use (`android/`, `ios/`, `Square*.png`, `StoreLogo.png`,
`64x64.png`) so the set stays the six files the config names.

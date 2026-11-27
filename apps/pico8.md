# PICO-8 (io.wip.pico8)

Adapter: `apps/pico8.json` (27 keys). Checked 2026-11-27 against versionName `1.6.6` on an AYN Thor and the wrapper's source at tag 1.6.6.

`io.wip.pico8` is Macs75/pico8-android: a Godot app that runs a user-supplied PICO-8 Raspberry Pi build (`pico8_64`, checked with 0.2.7) inside proot and streams its picture and sound. Two config files matter: PICO-8's own `config.txt` and the wrapper's `settings.cfg`. There are no per-cart settings.

## Files

| Path | Role |
|---|---|
| `/sdcard/Documents/pico8/data/config.txt` | PICO-8's config (inside proot: `/home/public/data/config.txt`, via `-home /home/public/data`). |
| `/data/data/io.wip.pico8/files/settings.cfg` | Wrapper settings (Godot `user://settings.cfg`). Root only. |
| `/sdcard/Documents/pico8/data/carts`, `cdata/`, `bbs/`, `favourites.txt` | Carts, cart save data, downloaded carts, favourites. |
| `/sdcard/Documents/pico8/shaders/*.gdshader`, `bezel.png`, `themes/` | Wrapper screen shaders (a `<name>.custom.gdshader` copy overrides), bezel, themes. |
| `/data/data/io.wip.pico8/files/package/` | proot, rootfs, launch scripts (`start_pico_proot.sh`, `rootfs/home/pico/start_pico.sh`). |
| `/data/data/io.wip.pico8/files/activity_stats.json`, `cart_metadata.json` | Play stats. |

## config.txt Format and Timing

- One setting per line: `key value`, space-separated; values are numbers or words; multi-value keys keep spaces (`window_size 128 128`). `//` starts a comment. Keep the comment lines and change only the value token. Format is `other` in the JSON.
- PICO-8 reads it at start and saves it on a clean exit. The wrapper stops pico8 with `pkill -9`, so in practice it is never rewritten.
- The wrapper's command line overrides some keys: `-width 128 -height 128 -windowed 1` (window_size, screen_size, windowed), `-root_path` (root_path), `-splore` (boot_to_splore, controlled by the wrapper's `start_with_splore`), `-accept_future 1`. Editing those keys has no effect.
- `stop_before_write: true`: stop the app so no running pico8 can save over the edit.

## settings.cfg Format and Timing

- Godot ConfigFile: `[settings]` and `[updates]` sections, `key=value` lines with Godot literals (`3`, `1.0`, `true`, `"sles"`, `Color(r, g, b, a)`). Format is `other` in the JSON; adapter key = `settings/<key>`.
- Only changed keys are present; a missing key is at its default.
- The app loads the file once into a cache and saves the whole file on every option change (`PicoBootManager.set_setting`). Stop the app before editing; it reads the file at next start.

## Gotchas

- `audio_backend` is forced to `stream` when the app is installed to adoptable storage, and changes need an app restart.
- `shader_type` indexes the built-in shader list; custom copies in the shaders folder replace the built-in file of the same name.
- `show_fps` in config.txt draws PICO-8's own counter inside the game picture.

## Verified On Device vs From Source

- On the test device: both files, the launch scripts and command line, the rootfs layout, every config.txt value (`verified_on_device: true`), `bg_color` in settings.cfg.
- From source: wrapper keys, defaults and enums (`frontend/options_menu.gd`, `boot.gd`, `video_streamer.gd`, `theme_manager.gd` at tag 1.6.6, commit 562662e35727ae7706fe97fed3390db249a35263); config.txt meanings from its own comments. The wrapper's compiled scripts in the installed APK contain the same key strings.

## Sources

- https://github.com/Macs75/pico8-android (tag 1.6.6)
- PICO-8 0.2.7 config.txt comments and `pico-8_manual.txt` (shipped in the PICO-8 Raspberry Pi zip).

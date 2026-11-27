# Vita3K (org.vita3k.emulator)

Adapter: `apps/vita3k.json`. Checked 2026-11-27 against Vita3K-Android release 12 on an AYN Thor and the Vita3K-Android source at tag `v12`.

## Checked Build

- `dumpsys package`: versionName `0.2.0-12`, versionCode 12.
- The checked `base.apk` is byte-identical to the `vita3k-android-release-12.apk` asset of GitHub release v12 (SHA-256 `59709b92…c8914fe`, 14,823,479 bytes).
- `libVita3K.so` reports `Vita3K v0.2.0 3621-781e7064-Macdu/android`. Commit `781e7064` is not on GitHub (the branch was rebased), so all source facts come from the published tag **v12** (`a62e232`, 2024-06-06) of `github.com/Vita3K/Vita3K-Android`.
- Every key in a `config.yml` written by this build (`custom-driver-name`, `turbo-mode`, `memory-mapping`, `psn-signed-in`, `fps-hack`, `http-*`, `tracy-*` and the rest) is in v12's `CONFIG_LIST`, in the same order. The UI strings "Enable Turbo Mode", "Add custom driver" and "Show front/back touchscreen switch button." are in the installed library.
- Vita3K was not running at check time (`pidof` empty).

## Files

| Path | What it holds |
|---|---|
| `/sdcard/Android/data/org.vita3k.emulator/files/config.yml` | Every setting (global). Flat YAML. Owner `u0_a<N>:ext_data_rw`, mode 660, label `media_rw_data_file:s0`. |
| `/sdcard/Android/data/org.vita3k.emulator/files/config/config_<TITLEID>.xml` | Per-game settings. The `config/` folder exists only once a game has a custom config. |
| `/data/data/org.vita3k.emulator/files/driver/<name>/` | Imported custom GPU drivers: `driver_name.txt` (the .so name), the .so, `meta.json`, `file_redirect/`. Root only. |
| `/data/data/org.vita3k.emulator/shared_prefs/org.vita3k.emulator_preferences.xml` | Touch-overlay button positions only (`<id>-X`, `<id>-Y` floats, `OverlayInit`). No emulator settings. |
| `/sdcard/Android/data/org.vita3k.emulator/files/cache/shaders/` | Vulkan pipeline and shader cache. `files/shaderlog/<TITLEID>/` holds shader logs. |
| `<pref-path>` (default `files/vita/`; Release 12 can point it at any folder, e.g. `/sdcard/Vita3k/`) | The emulated Vita file system: `ux0/app/<TITLEID>` holds installed games. |

`config_path` on Android is `SDL_AndroidGetExternalStoragePath()` = `/storage/emulated/0/Android/data/org.vita3k.emulator/files/` (`app_init.cpp` `init_paths`). Per-game files go there, **not** under `pref-path`.

## Write Rules (Global, `yaml`)

Sources: `config/include/config/config.h` (`CONFIG_INDIVIDUAL`), `config/include/config/state.h`, `config/src/config.cpp`.

- One `key: value` line per setting at the top level, between `---` and `...`. Five keys are YAML sequences (`controller-binds`, `controller-led-color`, `lle-modules`, `ime-langs`, `tracy-advanced-profiling-modules`). The flat `yaml_write` in `cocoonlib` cannot edit those.
- Bools are lowercase `true`/`false`. Floats are plain (`2`, `1.25`, `0.300000012`). An empty string must be written as `""` (`custom-driver-name: ""`).
- A missing key takes the source default. Keys are re-emitted in `CONFIG_LIST` order on every save. Unknown keys are dropped on the next save.
- `update_members()` converts keys in order with `yaml-cpp as<T>()`. A YAML syntax error, or a value that cannot convert (for example `audio-volume: loud`), throws. That key and every later key keep their defaults, and the start-up save writes those defaults back to disk. **A bad edit can reset half the file**, so validate before writing.
- Key spellings to copy exactly: `stretch_the_display_area` uses underscores, and `perfomance-overlay-detail` / `perfomance-overlay-position` are misspelled in the source.
- `psn-signed-in` is an int (`0`/`1`) in YAML but a bool in the per-game XML.

## When Vita3K Reads and Writes `config.yml`

- **Read**: once, at process start (`config::init_config`). Then `init_config` writes the file straight back (`overwrite_config` defaults to true).
- **Written**:
  - On every Settings **Save**.
  - On every change in Controls (overlay show, scale, opacity, touch switch) and controller binding.
  - By the emulated Vita Settings app (language, date, enter button).
  - On user switch, IME change, initial setup and the welcome dialog.
  - At app exit (`app::destroy` always saves "changes made in the GUI").
- So an edit made while the process is alive is never read and is overwritten at exit. **Force-stop Vita3K, edit, then start it** (`stop_before_write: true`).
- Restarts: switching backend or driver relaunches the process through `run_execv` → JNI `restartApp` → ProcessPhoenix with `-r <TITLEID>`. The new process re-reads `config.yml` from disk.

## Per-Game Settings (`config_<TITLEID>.xml`, format `other`)

Sources: `gui/src/settings_dialog.cpp` (`get_custom_config`, `save_config`, `set_config`), `gui/src/app_context_menu.cpp:487`, `gui/src/main_menubar.cpp:127`, `main.cpp:292,424`.

### Format

This is pugixml output, with a tab indent and an `utf-8` declaration:

```xml
<?xml version="1.0" encoding="utf-8"?>
<config>
	<core modules-mode="0">
		<lle-modules />            <!-- or <lle-modules><module>libngs</module>...</lle-modules> -->
	</core>
	<cpu cpu-backend="Dynarmic" cpu-opt="true" />
	<gpu backend-renderer="Vulkan" custom-driver-name="turnip_mrpurple_T30-toasted.adpkg" high-accuracy="false" resolution-multiplier="2" disable-surface-sync="true" screen-filter="Bilinear" memory-mapping="double-buffer" v-sync="true" anisotropic-filtering="1" async-pipeline-compilation="true" import-textures="false" export-textures="false" export-as-png="true" fps-hack="false" />
	<audio audio-volume="100" enable-ngs="true" />
	<system pstv-mode="false" />
	<emulator show-touchpad-cursor="true" />
	<network psn-signed-in="false" />
</config>
```

- The glossary field `per_game_key` (element/attribute, for example `gpu/resolution-multiplier`) is an extension beyond SCHEMA.md, added so a reader for this format can map each key. The attribute name matches the YAML key except `ngs-enable` → `audio/enable-ngs`.
- Per-game keys: `modules-mode`, `lle-modules`, `cpu-backend`, `cpu-opt`, every `gpu` attribute above, `audio-volume`, NGS, `pstv-mode`, `show-touchpad-cursor` and `psn-signed-in`. Everything else is global only. `stretch_the_display_area` is in the per-game dialog, but its Save writes it to `config.yml`.

### Semantics

- **All or nothing.** If the file exists and parses, *every* per-game setting comes from it (`emuenv.cfg.current_config = config`). Nothing falls back to `config.yml`, and there is no `use_global` flag.
- **A missing element or attribute is not "inherit".** `config = {}` and pugixml defaults give `false`, `0` or `""`:
  - `resolution-multiplier` 0.
  - `anisotropic-filtering` 0.
  - `cpu-backend ""`, which is treated as Unicorn.
  - `custom-driver-name ""`, which is the stock driver.
- So a hand-made file must hold every attribute. Seed it from the current `config.yml` values (the `per_game.template` has `{yaml-key}` placeholders), then change what you want.
- Bools: pugixml `as_bool` treats a first character of `1`/`t`/`T`/`y`/`Y` as true. Write `true`/`false`.
- If the XML fails to parse or has no `<config>` root, **Vita3K deletes the file** and uses global settings.
- A hand-made file is read: `get_custom_config` only checks that the file exists and parses. The in-app menu entry switches from Custom Config > Create to Edit/Remove when the file exists.

### When It Is Read and Written

- **Read** from disk at every game boot (`set_config(emuenv, app_path)`), both from the home screen and from `-r` launches (pinned shortcuts with action `LAUNCH_<TITLEID>` and extra `AppStartParameters = ["-r", "<TITLEID>"]`). It is also read when the per-game dialog opens. An edit is therefore picked up at the next boot of that game even if the process is alive, as long as the per-game settings dialog is not open. Stopping the app first is still safest.
- **Written** only by the per-game dialog's Save (Custom Config > Create/Edit, or Configuration > Settings while that game runs and its file exists). Removed by Custom Config > Remove and when the app is uninstalled from Vita3K.
- Backend, driver or resolution changes that differ from the running renderer restart the process at boot (`main.cpp:424-431`).

### Creating One by Hand

1. Create `/sdcard/Android/data/org.vita3k.emulator/files/config/`, matching its parent: owner `u0_a<N>`, group `ext_data_rw`, mode `2770`, label `u:object_r:media_rw_data_file:s0:c<N>,c256,c512,c768`.
2. Write `config_<TITLEID>.xml` as owner `u0_a<N>:ext_data_rw`, mode 660, label `media_rw_data_file`, with all attributes.

### Game IDs

The file name uses the app folder name under `<pref-path>/ux0/app/`. That is the 9-character title ID. The title name and version are in `ux0/app/<TITLEID>/sce_sys/param.sfo`.

## GPU Driver Selection

Sources: `app/src/app_init.cpp` (`load_custom_driver`, `init`), `app/src/app.cpp` (`add_custom_driver`), `renderer/src/vulkan/renderer.cpp` (`get_gpu_list`, `set_turbo_mode`), `settings_dialog.cpp:620-650`.

- `custom-driver-name` is the folder name under `/data/data/org.vita3k.emulator/files/driver/`.
  - Empty means the stock driver.
  - It is per-game switchable (`gpu/custom-driver-name`).
  - At process start, libadrenotools loads `<folder>/<driver_name.txt contents>`.
  - If the folder or `driver_name.txt` is missing, `app::init` fails and the emulator does not start.
- Installing a driver ("Add custom driver") unzips the picked zip into `driver/<zip name without .zip>/` and writes `driver_name.txt` with the first entry whose name contains `vulkan`. To add one by hand, copy that layout as root with owner `u0_a<N>:u0_a<N>`, mode 700/600 and label `app_data_file:s0:c<N>,c256,c512,c768`.
- `gpu-idx` is the GPU combo's position in `[Default] + folders of driver/ in readdir order`, which is not sorted.
  - While the GPU tab is open, the dialog sets `custom-driver-name` to the folder at that position. Index 0 forces it empty.
  - Save writes the result. **Always write `gpu-idx` together with `custom-driver-name`.**
- **Mismatch.** If `gpu-idx` points at a different folder than `custom-driver-name` (for example after drivers were added in another order):
  - The renderer loads the driver `custom-driver-name` names.
  - Opening Settings > GPU and pressing Save would probably switch to the driver at position `gpu-idx`.
  - Not checked in the UI.
- `turbo-mode` (Enable Turbo Mode) calls `adrenotools_set_turbo`, and is global only.

## Gotchas

- **V-Sync** is OpenGL only. Vulkan always picks Mailbox > FIFO Relaxed > FIFO > Immediate.
- **Screen filter strings** are matched exactly (`Nearest`, `Bilinear`, `Bicubic`, `FXAA`, `FSR`), and anything else means Bilinear. The dialog saves the *translated* label, so with a non-English `user-lang` it stores a string the renderer treats as Bilinear. `user-lang` `""` means English. FSR needs shaderInt16 and FP16, and otherwise no filter is used.
- **Disable Surface Sync is inverted**: `true` means surface sync is off (faster). On Android the checkbox only appears on Vulkan with memory mapping, and when it is hidden, Save forces `true`.
- **Memory mapping** has no effect on OpenGL. An unsupported method falls back to `double-buffer` (or `disabled`). It is greyed out in game.
- **Applied when.** These apply at game boot (renderer `late_init`, kernel CPU setup) or by restart: `high-accuracy`, `memory-mapping`, `cpu-*`, `audio-backend`, `backend-renderer`, `custom-driver-name`, `resolution-multiplier`. These apply live on Save in game: `screen-filter`, `anisotropic-filtering`, `audio-volume`, `fps-hack`, `async-pipeline-compilation`, texture import/export, `disable-surface-sync`.
- **OpenGL-only keys**: `shader-cache` and `texture-cache`.
- **Unicorn** is compiled into the Android build ("Unicorn (deprecated)" is in the library), so `cpu-backend: Unicorn` works, but slowly.
- **`enable-gamepad-overlay`** defaults to true in source.
- **`pref-path`**: changing it in Settings resets the user login and the app list.

## Verified on Device vs Taken From Source

Verified on the test device (read-only adb and root reads):
- Package version and that the APK is identical to the release 12 asset.
- The git revision in `libVita3K.so`.
- File paths, owners, modes and labels.
- Every glossary key exists in `config.yml` (all 39 `verified_on_device: true`).
- That the prefs hold only overlay positions.
- The driver folders and `driver_name.txt`.
- Reading title IDs and names from `param.sfo`.
- That Vita3K was not running.

Taken from source (v12), not tested on device:
- Value meanings, defaults and labels.
- The read and write timing.
- The all-or-nothing per-game semantics and the delete-on-parse-failure.
- The `gpu-idx`/driver coupling.
- That V-Sync is ignored on Vulkan.
- The exact XML attribute names: no per-game file was available to compare against.

No writes were made and nothing was launched.

## Sources

- Vita3K-Android, tag v12 (`a62e232024d21ca4a74d16a5d5cacedf66bd39ea`): https://github.com/Vita3K/Vita3K-Android/tree/v12
  - `vita3k/config/include/config/{config.h,state.h,yaml.h}`, `vita3k/config/src/config.cpp`: keys, defaults, load and save.
  - `vita3k/gui/src/settings_dialog.cpp`: per-game XML read/write, labels, value lists, `set_config`.
  - `vita3k/gui/src/{controls_dialog.cpp,app_context_menu.cpp,main_menubar.cpp}`: overlay keys, Custom Config menu.
  - `vita3k/lang/include/lang/state.h`, `vita3k/gui/include/gui/state.h`: English labels, modules-mode names.
  - `vita3k/app/src/{app_init.cpp,app.cpp}`, `vita3k/main.cpp`: Android paths, driver load and install, start-up and exit saves.
  - `vita3k/renderer/src/vulkan/{renderer.cpp,screen_renderer.cpp}`: mapping methods, filters, present mode, GPU list, turbo.
  - `vita3k/util/include/util/system.h`: sys-lang, enter button enums.
  - `android/src/main/java/org/vita3k/emulator/{Emulator.java,overlay/InputOverlay.java}`: launch intents, shared prefs.
- Release 12 notes and APK: https://github.com/Vita3K/Vita3K-Android/releases/tag/v12

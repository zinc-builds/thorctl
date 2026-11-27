---
name: thor-home-and-navbar
description: Diagnose and fix home-screen, Recents/app-switcher and gesture-bar problems on the AYN Thor with Cocoon as the dual-screen home app - Cocoon landing on the wrong screen, the bottom screen losing Cocoon, competing launchers, Home-button interceptors, and the navigation handle staying visible after opening Recents. Use when the user reports anything odd about Home, Recents, multitasking or the gesture bar.
---

# Thor Home Screens, Recents and Gesture Bar

Device basics: `thor-device` skill. If `local/skills/thor-home-and-navbar.md` exists in the repo root (two levels above this skill, after resolving symlinks), read it too: it holds this device's own state.

## Expected State

- HOME apps: only `rip.moth.cocoonshell/.MainActivity`, AYN's `com.odin.odinlauncher`, `com.android.launcher3` (Quickstep, provides Recents) and `com.android.settings/.FallbackHome`.
- SECONDARY_HOME: Cocoon `ExternalDisplayActivity` and Launcher3's `SecondaryDisplayLauncher`.
- Accessibility services: no Home-key interceptors (AYN's game assistant is expected).

Check:

```bash
adb shell "cmd package query-activities --brief -a android.intent.action.MAIN -c android.intent.category.HOME"
adb shell "cmd package query-activities --brief -a android.intent.action.MAIN -c android.intent.category.SECONDARY_HOME"
adb shell "cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME | tail -1"
adb shell "settings get secure enabled_accessibility_services"
adb shell "dumpsys activity activities | grep topResumedActivity"
```

Any extra launcher (Mjolnir `xyz.blacksheep.mjolnir`, Nova, Smart Launcher, Radikal, RetroHrai, jr.brian.home, NeoStation) competes for HOME/SECONDARY_HOME. Mjolnir also runs a `HomeKeyInterceptorService` accessibility service + keep-alive service + focus-stealer overlay, and its users often leave AYN focus mode on "Top screen only" — tell the user to set the AYN quick-menu screen focus back to **Auto-lock**. Uninstalling removes its accessibility service; ask before uninstalling anything.

## Gesture Bar Stuck Visible

Root cause (decompiled AYN SystemUI + Launcher3, firmware 377):
- `settings global hide_nav_bar=1` hides the handle, but SystemUI's `NavigationBarController` only applies it when a NavigationBar is created (and its ContentObserver only targets display 0).
- AYN's re-hide after Overview lives in Launcher3 `LauncherRecentsView.onStateTransitionComplete`, which only runs when Launcher3 is the home app. With Cocoon as home, Recents uses the fallback `RecentsActivity`, so nothing re-hides the bar if something shows it.
- Toggling `hide_nav_bar` 0→1 does **not** fix it. Restarting SystemUI does, in ~3 s.

Tools: `scripts/navbar.sh` reports the handle on both screens; `scripts/navbar.sh --fix` restarts SystemUI only if it's visible. `scripts/hometest.sh [cycles] [rom]` runs a DS game (default `$THOR_HOMETEST_ROM`, else the first `.nds` in `Roms/NDS` on the SD card) plus Recents/Back/Home cycles and prints resumed activities and bar state per step (adb can't simulate physical swipes; note that in reports).

## Known Cocoon Issues (GitHub inssekt/CocoonFE)

- #302 task switcher instead of Cocoon after closing a game; #291 crash swiping back from Recents (fixed 3.04); #525 old app on bottom screen after wake (open on 3.07); #370 Mjolnir vs Cocoon home fights.
- Back from Recents returns to Cocoon, not the previous app (fallback Recents behaviour); tapping the card resumes the game.
- If Cocoon's bottom activity ends up on the top screen (e.g. after `am start --display 0`): `am force-stop rip.moth.cocoonshell`.

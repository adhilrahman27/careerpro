#!/usr/bin/env bash
# Requires Node 22+, JDK 17 and a compatible Android SDK on PATH.
# Uses a debug keystore for LOCAL TESTING ONLY. Do not publish to stores.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root/apps/mobile"
npm install --no-audit --no-fund
npx expo install --fix --npm
npx tsc --noEmit
npx expo prebuild --platform android --non-interactive
python3 - <<'PY'
from pathlib import Path
p=Path('android/app/build.gradle')
s=p.read_text()
old='signingConfig signingConfigs.release'
if old not in s and 'signingConfig signingConfigs.debug' not in s:
 raise SystemExit('Expected signing configuration not found')
p.write_text(s.replace(old,'signingConfig signingConfigs.debug'))
PY
(cd android && chmod +x gradlew && ./gradlew :app:assembleRelease --no-daemon)
echo "Your TEST APK: $PWD/android/app/build/outputs/apk/release/app-release.apk"

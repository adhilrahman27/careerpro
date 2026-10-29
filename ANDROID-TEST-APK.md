# CareerRadar Pro Android TEST APK — Build package

**Important:** This archive is Android source code with a one-click cloud build workflow, **not a compiled APK**. No native build was possible in the authoring environment (Android SDK unavailable, package registry inaccessible). Do not rename the ZIP to `.apk`. The build instructions and workflow have not been verified on a runner.

## What you will see after installing a test APK

If no `CAREERRADAR_API_URL` is set, the Android client opens in **OFFLINE DEMO MODE** with a clearly visible warning and three *fictional, labelled* vacancies. You can test filters, job details, saved jobs, alerts, application tracking and profile editing. Changes persist on the phone via Expo SecureStore. This does **not** connect to live jobs, send notifications, create real accounts or process payments. Job applications are disabled in demo mode.

For live functionality, separately deploy and secure the Python backend first; set `CAREERRADAR_API_URL` to its public HTTPS URL in GitHub repository Variables, and rebuild. A URL using `localhost` cannot reach a server running on another computer from a phone.

## Build without installing Android Studio (GitHub Actions)

1. Sign in at github.com and create a **new private repository** (for example `careerradar-pro-test`). Do not upload to a public repository until you review the code and credentials.
2. Extract this ZIP; open the `careerradar-pro` folder. Upload its **contents** to the repository root (including the `.github` hidden folder). An easier option is to use git commands from inside the folder: `git init`, `git add .`, `git commit -m "CareerRadar source"`, then create and push to a new GitHub repository. Do not commit `.env`, secrets, CVs or your local database.
3. Open the GitHub **Actions** tab, choose **Build installable Android test APK**, then click **Run workflow**. The workflow runs on a cloud Linux runner with Node/Java/Android toolchain.
4. When it completes successfully, click the workflow run, locate **Artifacts**, and download **CareerRadar-Pro-Android-Test-APK**. Unzip the downloaded artifact to obtain `app-release.apk`.
5. On the Android phone, open the APK and allow installation from that trusted source when prompted. Uninstall the demo build before installing a Play Store-signed build if keys differ.

If the runner fails, inspect the job log; do not treat a red build as a working APK. Expo SDK 58 requires Node 22+ and React Native 0.88. Android dependencies may be downloaded by Gradle during the workflow.

### Backend URL configuration

For live server connections (after independently deploying the server on HTTPS): GitHub repository **Settings → Secrets and variables → Actions → Variables**, create `CAREERRADAR_API_URL` with value `https://your-api-domain.example`. This value is public configuration embedded into the app, not a secret. **Do not enter API keys, passwords or service role credentials here.** Without this value the build deliberately operates in offline demo mode.

## Local Android build

On a Linux/macOS machine with JDK 17, Node 22+, Android SDK and network access:

```bash
bash scripts/build-test-apk.sh
```

To configure the real server, first export `EXPO_PUBLIC_API_BASE_URL=https://your-api-domain.example`.

The test APK is assembled using the Android debug keystore. **It is not signed for production release and must not be submitted to Google Play.** The production app needs a controlled upload key, release QA, and store policy review.

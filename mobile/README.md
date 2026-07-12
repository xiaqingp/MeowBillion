# MeowBillion Android

## Development

Start the local backend from `C:\Users\surreal\MyProjects\MeowBillion` with:

```powershell
.\start-meowbillion-server.ps1
```

This is the required local startup command. It binds the backend to `0.0.0.0` so both the Android emulator and Tailscale devices can reach it. Use `-Restart` after backend code changes.

Install Java 17+ and the Android SDK, then run:

```powershell
npm install
npx expo run:android
```

The login screen defaults to `http://10.0.2.2:8090`, which is the Android emulator mapping to this computer's current MeowBillion server. Enter a different private backend URL in the **后端地址** field when needed; the app saves it locally. Signed-in users can change it from **更多** > **连接设置**. Changing the address signs out the current session before any request is made to the new server.

For a physical device, enter the reachable private HTTPS URL for the MeowBillion Flask server. Do not expose the local Flask server directly to the public internet.

When the phone is on the same Wi-Fi network as the current Windows host, use `http://192.168.86.57:8090`. Do not use `127.0.0.1` or `10.0.2.2` on a physical phone. Use **测试后端连接** before entering credentials; the login request times out after 10 seconds with a visible error message.

The M2 private-development APK permits HTTP so an Android emulator can reach `10.0.2.2`. Use HTTPS for any physical-device or remote deployment.

## Verification

```powershell
npm test
npm run typecheck
```

The first usable build verifies this sequence:

1. Open the app and sign in with an existing MeowBillion user.
2. Close and reopen the app; the session should restore.
3. Confirm the home page shows accounts, monthly income/expense, unreviewed transactions, and sync status.
4. Pull down to refresh.
5. Sign out and confirm the home page can no longer be opened.

## Security

Open **More** from Home to enable **App Lock**. The app then requires the device's enrolled biometric authentication whenever it returns from the background. If the device has no enrolled biometric method, App Lock remains off.

Open **More** > **Security** to see mobile sessions. **Sign out other devices** revokes every other mobile token. Use **Revoke** for one device. A revoked device is returned to sign-in on its next API request.

## Troubleshooting

- A request that cannot reach the server or does not complete within 10 seconds shows a retryable error. Confirm the private server address and Wi-Fi connection, then retry or pull to refresh.
- APK upgrades preserve the signed-in session unless the server address changes or the session is revoked.

## Build

```powershell
npx expo prebuild --platform android
cd android
.\gradlew.bat assembleRelease
```

The APK is written below `android/app/build/outputs/apk/release/` after a successful local build.

The private signing key and its local build properties live in the current Windows user's `.meowbillion` directory. Keep that directory in an encrypted backup: losing it prevents future APK upgrades over an existing installation.

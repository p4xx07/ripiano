# Ripiano for Android

This native shell opens the same Ripiano UI served by your NAS. Enter its **HTTPS** origin on first launch (a Tailscale HTTPS hostname is supported). The shell accepts navigation and scanner messages only from that exact origin. The account session stays in the Android WebView; no third-party account is involved.

The Appearance selector in Ripiano offers device setting, Light, Dark, and AMOLED black. The Android toolbar and system bars follow the selected palette, and the last resolved palette is kept for the next launch.

The **Scan pages** action uses Google ML Kit's on-device document scanner to crop, reorder, and combine pages into a PDF. Google Play services supplies the scanner UI/model, so first use needs it installed and may download the module. Android 8+ and a device with at least 1.7 GB RAM are required by the scanner. The app itself does not request a camera permission. Photos and files use the Android file picker.

Scanned PDFs are copied into a server-specific private `pending-scans` folder before upload. The shell retries them after sign-in or from its **Retry scans** menu. It deletes a pending file only after Ripiano confirms upload. The scan UUID is sent as an idempotency key, so a lost response can be retried without creating a second document. The server's current upload limit is 25 MB; oversized scans remain on the device and show an error.

Open this directory in Android Studio or run `./gradlew :app:assembleDebug` with Android SDK API 36 installed. Install `app/build/outputs/apk/debug/app-debug.apk` on an Android device for real scanner testing. Release signing and device validation remain release gates.

## Sign-in gateway (Authelia)

If a sign-in page protects Ripiano (for example the [Raspberry Pi gateway](../../deploy/gateway/README.md) with Authelia), enter its address under **Sign-in address** on the server screen, for example `https://auth.example.com`. Use the menu's **Change server** to add it later.

- Only the Ripiano address and that sign-in address load inside the app. Every other address opens in the browser, as before.
- The sign-in page's cookie is stored in the app, so you stay signed in (30 days with **Remember me**). Without this setting, the gateway redirect would open in the browser, whose cookies the app cannot use, and the app would keep returning to the sign-in page.
- The scanner, uploads, and downloads stay bound to the Ripiano address; the sign-in page cannot use them.
- Scan uploads carry the gateway cookie automatically. If the gateway session has expired, the upload is refused, the scan stays on the phone, and it is retried after you sign in again.

The configured NAS must serve a certificate trusted by Android. Changing the server address does not transfer pending scans; retry them against the original archive first.

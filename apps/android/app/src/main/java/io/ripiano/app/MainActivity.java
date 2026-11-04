package io.ripiano.app;

import android.app.AlertDialog;
import android.app.DownloadManager;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.view.Gravity;
import android.view.MenuItem;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.webkit.DownloadListener;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.PopupMenu;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.ComponentActivity;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.IntentSenderRequest;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.webkit.WebViewCompat;
import androidx.webkit.WebViewFeature;

import com.google.mlkit.vision.documentscanner.GmsDocumentScanner;
import com.google.mlkit.vision.documentscanner.GmsDocumentScannerOptions;
import com.google.mlkit.vision.documentscanner.GmsDocumentScanning;
import com.google.mlkit.vision.documentscanner.GmsDocumentScanningResult;

import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Collections;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

import javax.net.ssl.HttpsURLConnection;

public final class MainActivity extends ComponentActivity {
    private static final long MAX_SCAN_BYTES = 25L * 1024 * 1024;
    private final ExecutorService uploads = Executors.newSingleThreadExecutor();
    private final AtomicBoolean retryQueued = new AtomicBoolean(false);
    private WebView webView;
    private String origin;
    private String scanOrigin;
    private ValueCallback<Uri[]> fileChoice;

    private final ActivityResultLauncher<Intent> filePicker = registerForActivityResult(
            new ActivityResultContracts.StartActivityForResult(), result -> {
                if (fileChoice != null) {
                    fileChoice.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(
                            result.getResultCode(), result.getData()));
                    fileChoice = null;
                }
            });

    private final ActivityResultLauncher<IntentSenderRequest> scannerResult = registerForActivityResult(
            new ActivityResultContracts.StartIntentSenderForResult(), result -> {
                if (result.getResultCode() != RESULT_OK || result.getData() == null) {
                    notifyWeb("cancelled", "");
                    return;
                }
                GmsDocumentScanningResult scan = GmsDocumentScanningResult.fromActivityResultIntent(result.getData());
                if (scan == null || scan.getPdf() == null) {
                    notifyWeb("failed", "Scanner did not return a PDF");
                    return;
                }
                Uri pdfUri = scan.getPdf().getUri();
                String destination = scanOrigin != null ? scanOrigin : origin;
                notifyWeb("uploading", "");
                uploads.execute(() -> {
                    try {
                        persistScan(pdfUri, destination);
                        runOnUiThread(() -> retryPending());
                    } catch (Exception error) {
                        notifyWeb("failed", "Could not save the scan on this device");
                    }
                });
            });

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (savedInstanceState != null) scanOrigin = savedInstanceState.getString("scan_origin");
        String saved = Origin.serverOrigin(getPreferences(MODE_PRIVATE).getString("server_origin", ""));
        if (saved == null) askForServer(); else {
            getPreferences(MODE_PRIVATE).edit().putString("server_origin", saved).apply();
            openServer(saved);
        }
    }

    @Override protected void onSaveInstanceState(Bundle state) {
        state.putString("scan_origin", scanOrigin);
        super.onSaveInstanceState(state);
    }

    private void askForServer() {
        if (retryQueued.get()) {
            Toast.makeText(this, "Wait for the current upload to finish", Toast.LENGTH_SHORT).show();
            return;
        }
        EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setInputType(android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_VARIATION_URI);
        input.setHint("https://ripiano.example.com");
        if (origin != null) input.setText(origin);
        int pad = (int) (24 * getResources().getDisplayMetrics().density);
        LinearLayout holder = new LinearLayout(this);
        holder.setPadding(pad, 0, pad, 0);
        holder.addView(input, new LinearLayout.LayoutParams(-1, -2));
        new AlertDialog.Builder(this)
                .setTitle("Connect to Ripiano")
                .setMessage("Enter the HTTPS address of your Ripiano archive on the NAS.")
                .setView(holder)
                .setCancelable(false)
                .setPositiveButton("Connect", (dialog, which) -> {
                    String address = Origin.serverOrigin(input.getText().toString());
                    if (address == null) {
                        Toast.makeText(this, "Enter an HTTPS origin without a path", Toast.LENGTH_LONG).show();
                        askForServer();
                    } else {
                        getPreferences(MODE_PRIVATE).edit().putString("server_origin", address).apply();
                        openServer(address);
                    }
                }).show();
    }

    private void openServer(String address) {
        origin = address;
        if (webView != null) webView.destroy();
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(245, 248, 243));
        LinearLayout toolbar = new LinearLayout(this);
        toolbar.setPadding(18, 0, 10, 0);
        toolbar.setGravity(Gravity.CENTER_VERTICAL);
        toolbar.setBackgroundColor(Color.rgb(34, 79, 55));
        TextView title = new TextView(this);
        title.setText("ripiano");
        title.setTextSize(20);
        title.setTextColor(Color.WHITE);
        toolbar.addView(title, new LinearLayout.LayoutParams(0, 48 * density(), 1));
        Button menu = new Button(this);
        menu.setText("⋮");
        menu.setContentDescription("More options");
        toolbar.addView(menu, new LinearLayout.LayoutParams(48 * density(), 48 * density()));
        menu.setOnClickListener(view -> {
            PopupMenu popup = new PopupMenu(this, menu);
            popup.getMenu().add("Retry pending scans");
            popup.getMenu().add("Change server");
            popup.setOnMenuItemClickListener((MenuItem item) -> {
                if (item.getTitle().toString().startsWith("Retry")) retryPending();
                else askForServer();
                return true;
            });
            popup.show();
        });
        root.addView(toolbar);

        webView = new WebView(this);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(true);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setSupportMultipleWindows(false);
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, false);
        webView.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri target = request.getUrl();
                if (origin.equals(Origin.originOfUrl(target.toString()))) return false;
                if ("https".equals(target.getScheme())) startActivity(new Intent(Intent.ACTION_VIEW, target));
                return true;
            }
        });
        webView.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (fileChoice != null) fileChoice.onReceiveValue(null);
                fileChoice = callback;
                try { filePicker.launch(params.createIntent()); }
                catch (Exception error) { fileChoice.onReceiveValue(null); fileChoice = null; return false; }
                return true;
            }
        });
        webView.setDownloadListener((url, userAgent, disposition, mime, size) -> {
            Uri target = Uri.parse(url);
            if (!origin.equals(Origin.originOfUrl(target.toString()))) return;
            DownloadManager.Request request = new DownloadManager.Request(target);
            String cookie = CookieManager.getInstance().getCookie(origin);
            if (cookie != null) request.addRequestHeader("Cookie", cookie);
            request.setMimeType(mime);
            request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS,
                    android.webkit.URLUtil.guessFileName(url, disposition, mime));
            ((DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE)).enqueue(request);
            Toast.makeText(this, "Saving to Downloads", Toast.LENGTH_SHORT).show();
        });
        if (WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) {
            WebViewCompat.addWebMessageListener(webView, "RipianoAndroid", Collections.singleton(origin),
                    (view, message, sourceOrigin, isMainFrame, replyProxy) -> {
                        if (isMainFrame && origin.equals(Origin.originOfUrl(sourceOrigin.toString()))) {
                            if ("scan".equals(message.getData())) startScan();
                            if ("retry".equals(message.getData())) retryPending();
                        }
                    });
        }
        root.addView(webView, new LinearLayout.LayoutParams(-1, 0, 1));
        setContentView(root);
        webView.loadUrl(origin + "/");
    }

    private int density() { return (int) getResources().getDisplayMetrics().density; }

    private void startScan() {
        scanOrigin = origin;
        GmsDocumentScannerOptions options = new GmsDocumentScannerOptions.Builder()
                .setGalleryImportAllowed(true)
                .setPageLimit(20)
                .setResultFormats(GmsDocumentScannerOptions.RESULT_FORMAT_PDF)
                .setScannerMode(GmsDocumentScannerOptions.SCANNER_MODE_FULL)
                .build();
        GmsDocumentScanner scanner = GmsDocumentScanning.getClient(options);
        scanner.getStartScanIntent(this)
                .addOnSuccessListener(sender -> scannerResult.launch(new IntentSenderRequest.Builder(sender).build()))
                .addOnFailureListener(error -> notifyWeb("failed", "Native scanner unavailable. Use Photos or Files instead."));
    }

    private File persistScan(Uri uri, String destination) throws Exception {
        File directory = pendingDirectory(destination);
        if (!directory.exists() && !directory.mkdirs()) throw new IllegalStateException("Cannot create pending scans folder");
        File file = new File(directory, UUID.randomUUID() + ".pdf");
        try (InputStream input = getContentResolver().openInputStream(uri); OutputStream output = new FileOutputStream(file)) {
            if (input == null) throw new IllegalStateException("Scanner PDF missing");
            byte[] buffer = new byte[64 * 1024];
            int count;
            while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
        } catch (Exception error) { file.delete(); throw error; }
        return file;
    }

    private void retryPending() {
        if (webView == null || !origin.equals(Origin.originOfUrl(webView.getUrl()))) return;
        if (!retryQueued.compareAndSet(false, true)) return;
        String destination = origin;
        File directory = pendingDirectory(destination);
        File[] pending = directory.listFiles((dir, name) -> name.endsWith(".pdf"));
        if (pending == null || pending.length == 0) { retryQueued.set(false); return; }
        String cookie = CookieManager.getInstance().getCookie(origin);
        String csrf = cookieValue(cookie, "csrftoken");
        if (cookie == null || csrf.isEmpty()) { retryQueued.set(false); return; }
        uploads.execute(() -> {
            try {
                for (File file : pending) {
                    if (file.length() > MAX_SCAN_BYTES) {
                        notifyWeb("failed", "A scan exceeds the 25 MB limit. It remains on this device.");
                        continue;
                    }
                    try {
                        notifyWeb("uploading", "");
                        upload(destination, file, cookie, csrf);
                        if (!file.delete()) throw new IllegalStateException("Could not clear saved scan");
                        notifyWeb("saved", "");
                    } catch (Exception error) {
                        notifyWeb("failed", "Scan saved on this device. Sign in or retry when the NAS is reachable.");
                        break;
                    }
                }
            } finally { retryQueued.set(false); }
        });
    }

    private File pendingDirectory(String destination) {
        try {
            byte[] hash = MessageDigest.getInstance("SHA-256").digest(destination.getBytes(StandardCharsets.UTF_8));
            StringBuilder name = new StringBuilder();
            for (int i = 0; i < 12; i++) name.append(String.format("%02x", hash[i] & 0xff));
            return new File(new File(getFilesDir(), "pending-scans"), name.toString());
        } catch (Exception error) { throw new IllegalStateException(error); }
    }

    private void upload(String destination, File file, String cookie, String csrf) throws Exception {
        String boundary = "Ripiano" + UUID.randomUUID().toString().replace("-", "");
        URL url = new URL(destination + "/api/documents");
        HttpsURLConnection connection = (HttpsURLConnection) url.openConnection();
        connection.setInstanceFollowRedirects(false);
        connection.setConnectTimeout(15000);
        connection.setReadTimeout(90000);
        connection.setRequestMethod("POST");
        connection.setDoOutput(true);
        connection.setRequestProperty("Origin", destination);
        connection.setRequestProperty("Cookie", cookie);
        connection.setRequestProperty("X-CSRFToken", csrf);
        connection.setRequestProperty("X-Ripiano-Scan-ID", file.getName().replace(".pdf", ""));
        connection.setRequestProperty("Content-Type", "multipart/form-data; boundary=" + boundary);
        connection.setChunkedStreamingMode(64 * 1024);
        try {
            try (OutputStream output = connection.getOutputStream(); InputStream input = new FileInputStream(file)) {
                output.write(("--" + boundary + "\r\nContent-Disposition: form-data; name=\"document\"; filename=\"scan-" + file.getName() + "\"\r\nContent-Type: application/pdf\r\n\r\n").getBytes(StandardCharsets.UTF_8));
                byte[] buffer = new byte[64 * 1024];
                int count;
                while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
                output.write(("\r\n--" + boundary + "--\r\n").getBytes(StandardCharsets.UTF_8));
            }
            int status = connection.getResponseCode();
            if (status != HttpURLConnection.HTTP_OK && status != HttpURLConnection.HTTP_ACCEPTED)
                throw new IllegalStateException("Upload failed: " + status);
        } finally { connection.disconnect(); }
    }

    private static String cookieValue(String cookie, String key) {
        if (cookie == null) return "";
        for (String part : cookie.split(";")) {
            String value = part.trim();
            if (value.startsWith(key + "=")) return value.substring(key.length() + 1);
        }
        return "";
    }

    private void notifyWeb(String status, String message) {
        runOnUiThread(() -> {
            if (webView == null || !origin.equals(Origin.originOfUrl(webView.getUrl()))) return;
            String payload = "{\"status\":" + JSONObject.quote(status) + ",\"message\":" + JSONObject.quote(message) + "}";
            webView.evaluateJavascript("window.dispatchEvent(new CustomEvent('ripiano-native-upload',{detail:" + payload + "}))", null);
        });
    }

    @Override public void onBackPressed() {
        if (webView != null && webView.canGoBack()) webView.goBack(); else super.onBackPressed();
    }

    @Override protected void onDestroy() {
        if (fileChoice != null) fileChoice.onReceiveValue(null);
        if (webView != null) webView.destroy();
        uploads.shutdown();
        super.onDestroy();
    }
}

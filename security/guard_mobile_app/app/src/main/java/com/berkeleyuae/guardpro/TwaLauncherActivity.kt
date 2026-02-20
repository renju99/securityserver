package com.berkeleyuae.guardpro

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.util.Log
import android.webkit.GeolocationPermissions
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKeys

class TwaLauncherActivity : AppCompatActivity() {

    private val PERMISSION_REQUEST_CODE = 1001
    private lateinit var webView: WebView
    
    // Configure URL here - Use Security domain
    private val START_URL = "https://security.berkeleyuae.com/guardpro/mobile"
    private val ALLOWED_HOST = "security.berkeleyuae.com"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        // Setup WebView UI
        setupWebView()

        // Check and request permissions
        if (checkPermissions()) {
            startLocationService()
        } else {
            requestPermissions()
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun setupWebView() {
        webView = WebView(this)
        setContentView(webView)

        val settings = webView.settings
        settings.javaScriptEnabled = true
        settings.domStorageEnabled = true
        settings.databaseEnabled = true
        settings.allowFileAccess = true
        settings.allowContentAccess = true
        settings.loadWithOverviewMode = true
        settings.useWideViewPort = true
        settings.javaScriptCanOpenWindowsAutomatically = true
        settings.setSupportMultipleWindows(false) // Changed to false for better stability
        settings.mixedContentMode = WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE
        
        settings.cacheMode = WebSettings.LOAD_DEFAULT
        settings.userAgentString = settings.userAgentString + " Berkeley-GuardPro-App-v1.0"
        
        // Add the Native-to-JS Bridge
        webView.addJavascriptInterface(WebAppInterface(this), "AndroidBridge")

        webView.webChromeClient = object : WebChromeClient() {
            override fun onGeolocationPermissionsShowPrompt(origin: String, callback: GeolocationPermissions.Callback) {
                callback.invoke(origin, true, false)
            }
            
            override fun onConsoleMessage(consoleMessage: android.webkit.ConsoleMessage?): Boolean {
                consoleMessage?.let {
                    Log.d("WebViewConsole", "[${it.messageLevel()}] ${it.message()} -- From line ${it.lineNumber()} of ${it.sourceId()}")
                }
                return true
            }
        }

        webView.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                Log.d("WebView", "Page finished loading: $url")
                // Inform the web layer about the native environment
                webView.evaluateJavascript("window.isNativeApp = true; if(window.setPermissionUI) window.setPermissionUI('granted');", null)
            }
            
            override fun onReceivedSslError(view: WebView?, handler: android.webkit.SslErrorHandler?, error: android.net.http.SslError?) {
                Log.w("WebViewSSL", "SSL Error: $error")
                handler?.proceed() // Proceed for now (optional, safe if we trust our domain)
            }

            override fun onReceivedError(view: WebView?, request: android.webkit.WebResourceRequest?, error: android.webkit.WebResourceError?) {
                super.onReceivedError(view, request, error)
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                    val url = request?.url?.toString() ?: "unknown"
                    Log.e("WebViewError", "Error loading $url: ${error?.description} (Code: ${error?.errorCode})")
                }
            }

            override fun shouldOverrideUrlLoading(view: WebView?, request: android.webkit.WebResourceRequest?): Boolean {
                val url = request?.url?.toString()
                if (url != null) {
                    val isInternal = url.contains(ALLOWED_HOST) || 
                                   url.contains("/web/login") || 
                                   url.contains("/web/session") ||
                                   url.contains("/guardpro/mobile")
                    
                    if (isInternal) {
                        return false // Load in WebView
                    }
                }
                // Open external links in browser
                try {
                    val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
                    startActivity(intent)
                } catch (e: Exception) {
                    Log.e("WebView", "Error opening external URL: ${e.message}")
                }
                return true
            }
        }

        webView.loadUrl(START_URL)
    }

    /**
     * JS Bridge class exposed as window.AndroidBridge
     */
    inner class WebAppInterface(private val context: Context) {
        
        @JavascriptInterface
        fun postToken(token: String) {
            if (token.isEmpty()) return
            // Save token securely
            saveTokenSecurely(token)
            // Start/Restart Location Service with the new token
            startLocationService()
        }

        private fun saveTokenSecurely(token: String) {
            try {
                val masterKeyAlias = MasterKeys.getOrCreate(MasterKeys.AES256_GCM_SPEC)
                val sharedPreferences = EncryptedSharedPreferences.create(
                    "secure_prefs",
                    masterKeyAlias,
                    context,
                    EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                    EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
                )
                sharedPreferences.edit().putString("auth_token", token).apply()
            } catch (e: Exception) {
                // Fallback to standard SharedPreferences if encryption fails
                val prefs = context.getSharedPreferences("auth_prefs", Context.MODE_PRIVATE)
                prefs.edit().putString("auth_token", token).apply()
            }
        }
    }

    private fun checkPermissions(): Boolean {
        val fineLocation = ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
        val coarseLocation = ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED
        var backgroundLocation = true
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            backgroundLocation = ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_BACKGROUND_LOCATION) == PackageManager.PERMISSION_GRANTED
        }
        return fineLocation && coarseLocation && backgroundLocation
    }

    private fun requestPermissions() {
        val permissions = mutableListOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION)
        if (Build.VERSION.SDK_INT == Build.VERSION_CODES.Q) permissions.add(Manifest.permission.ACCESS_BACKGROUND_LOCATION)
        ActivityCompat.requestPermissions(this, permissions.toTypedArray(), PERMISSION_REQUEST_CODE)
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == PERMISSION_REQUEST_CODE) {
            val allGranted = grantResults.all { it == PackageManager.PERMISSION_GRANTED }
            if (allGranted) {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                    if (ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_BACKGROUND_LOCATION) != PackageManager.PERMISSION_GRANTED) {
                        showBackgroundPermissionRationale()
                    } else {
                        startLocationService()
                    }
                } else {
                    startLocationService()
                }
            } else {
                showPermissionRequiredDialog()
            }
        }
    }

    private fun showBackgroundPermissionRationale() {
        AlertDialog.Builder(this)
            .setTitle("Guard Location Access")
            .setMessage("Guard Pro requires 'Allow all the time' location permissions to ensure your safety and verify patrols. Please select 'Allow all the time' in the next screen.")
            .setPositiveButton("Settings") { _, _ ->
                val intent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                    data = Uri.fromParts("package", packageName, null)
                }
                startActivity(intent)
            }
            .setNegativeButton("Cancel") { dialog, _ -> dialog.dismiss() }
            .setCancelable(false)
            .show()
    }

    private fun showPermissionRequiredDialog() {
        AlertDialog.Builder(this)
            .setTitle("Permissions Needed")
            .setMessage("Location access is required for this app to function.")
            .setPositiveButton("Try Again") { _, _ -> requestPermissions() }
            .setNegativeButton("Exit") { _, _ -> finish() }
            .setCancelable(false)
            .show()
    }

    private fun startLocationService() {
        val serviceIntent = Intent(this, LocationService::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(serviceIntent)
        } else {
            startService(serviceIntent)
        }
    }

    override fun onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack()
        } else {
            super.onBackPressed()
        }
    }
}

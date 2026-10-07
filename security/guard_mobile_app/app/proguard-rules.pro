# GuardLink ProGuard / R8 rules
# Keep only what reflection / WebView / runtime entry points need.
# Broad -keep of entire packages was why Play showed ~1% obfuscation.

# ── Attributes (needed for annotations, Kotlin, WebView bridge) ───────────────
-keepattributes Signature
-keepattributes *Annotation*
-keepattributes EnclosingMethod
-keepattributes InnerClasses
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile

# ── WebView JavaScript bridge (method names are called from JS) ───────────────
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}

# ── Kotlin metadata (coroutines / reflection helpers) ─────────────────────────
-keep class kotlin.Metadata { *; }
-dontwarn kotlin.**
-dontwarn kotlinx.coroutines.**

# ── OkHttp (publicsuffix resource is loaded reflectively) ─────────────────────
-dontwarn okhttp3.**
-dontwarn okio.**
-keepnames class okhttp3.internal.publicsuffix.PublicSuffixDatabase

# ── Media3 / ExoPlayer ────────────────────────────────────────────────────────
-dontwarn androidx.media3.**

# ── Google Play Services Location ─────────────────────────────────────────────
-dontwarn com.google.android.gms.**

# ── EncryptedSharedPreferences / Tink ─────────────────────────────────────────
-dontwarn com.google.crypto.tink.**

# ── Common library noise ──────────────────────────────────────────────────────
-dontwarn javax.annotation.**
-dontwarn org.codehaus.mojo.**
-dontwarn retrofit2.**
-dontwarn com.google.gson.**

# Berkeley Attendance App - Proguard/R8 Rules

# Retrofit 2 rules
-dontwarn retrofit2.**
-keep class retrofit2.** { *; }
-keepattributes Signature, InnerClasses

# Gson rules
-keepattributes Signature
-keepattributes *Annotation*
-dontwarn sun.misc.**
-keep class com.google.gson.** { *; }
-keep class * extends com.google.gson.TypeAdapter

# Keep our API Data Models from being obfuscated
-keep class com.berkeleyuae.attendance.LocationPayload { *; }
-keep class com.berkeleyuae.attendance.AttendanceApi { *; }

# OkHttp rules
-dontwarn okhttp3.**
-dontwarn okio.**
-keep class okhttp3.** { *; }

# AndroidX Security rules
-keep class androidx.security.crypto.** { *; }

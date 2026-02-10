package com.berkeleyuae.attendance

import com.google.gson.annotations.SerializedName
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.Header
import retrofit2.http.POST

// Data Model for Location Update mapping to specific Berkeley API requirements
data class LocationPayload(
    @SerializedName("lat") val lat: Double,
    @SerializedName("lng") val lng: Double,
    @SerializedName("hw_id") val hwId: String,
    @SerializedName("ts") val ts: Long
)

data class DebugLog(
    @SerializedName("tag") val tag: String,
    @SerializedName("msg") val msg: String
)

// Retrofit API Interface
interface AttendanceApi {
    @POST("api/location/update")
    suspend fun updateLocation(
        @Body payload: LocationPayload
    ): Response<Unit>

    @POST("api/debug/log")
    suspend fun logDebug(
        @Body payload: DebugLog
    ): Response<Unit>
}

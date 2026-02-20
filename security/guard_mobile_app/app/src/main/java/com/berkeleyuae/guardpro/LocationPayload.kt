package com.berkeleyuae.guardpro

data class LocationPayload(
    val lat: Double,
    val lng: Double,
    val ts: Long,
    val hwId: String,
    val accuracy: Float = 0f,
    val speed: Float = 0f,
    val heading: Float = 0f,
    val battery: Int = 0
)

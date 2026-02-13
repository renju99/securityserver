/**
 * Geocoding utility to handle reverse geocoding for reports
 * Uses a local cache to minimize API calls
 */

const addressCache = new Map();

/**
 * Reverse geocode coordinates to an address
 * @param {number} lat 
 * @param {number} lng 
 * @param {string} apiKey 
 * @returns {Promise<string>}
 */
export const reverseGeocode = async (lat, lng, apiKey) => {
    const cacheKey = `${parseFloat(lat).toFixed(5)},${parseFloat(lng).toFixed(5)}`;

    if (addressCache.has(cacheKey)) {
        return addressCache.get(cacheKey);
    }

    if (!apiKey) {
        return 'No API Key provided';
    }

    try {
        const response = await fetch(
            `https://maps.googleapis.com/maps/api/geocode/json?latlng=${lat},${lng}&key=${apiKey}`
        );
        const data = await response.json();

        if (data.status === 'OK' && data.results.length > 0) {
            // Find the most appropriate address component
            // We'll prefer formatted_address but clean it up slightly if needed
            const address = data.results[0].formatted_address;
            addressCache.set(cacheKey, address);
            return address;
        } else {
            console.warn('Geocoding failed:', data.status, data.error_message);
            return 'Address not found';
        }
    } catch (error) {
        console.error('Geocoding error:', error);
        return 'Address unavailable';
    }
};

/**
 * Batch geocode a list of points (with concurrency control)
 * @param {Array} points [{latitude, longitude}]
 * @param {string} apiKey 
 * @returns {Promise<Object>} Map of coords to address
 */
export const batchReverseGeocode = async (points, apiKey) => {
    const results = {};
    const uniquePoints = [];
    const seen = new Set();

    // Deduplicate points (same as cache keys)
    points.forEach(p => {
        const key = `${parseFloat(p.latitude).toFixed(5)},${parseFloat(p.longitude).toFixed(5)}`;
        if (!seen.has(key)) {
            seen.add(key);
            uniquePoints.push(p);
        }
    });

    // Process in batches to avoid overwhelming browser/API
    const batchSize = 5;
    for (let i = 0; i < uniquePoints.length; i += batchSize) {
        const batch = uniquePoints.slice(i, i + batchSize);
        await Promise.all(batch.map(async (p) => {
            const key = `${parseFloat(p.latitude).toFixed(5)},${parseFloat(p.longitude).toFixed(5)}`;
            results[key] = await reverseGeocode(p.latitude, p.longitude, apiKey);
        }));
    }

    return results;
};

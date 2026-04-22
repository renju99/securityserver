var exec = require('cordova/exec');

var SERVICE = 'BW360Location';

function call(action, args, success, error) {
    exec(success || function () {}, error || function () {}, SERVICE, action, args || []);
}

module.exports = {
    /**
     * Start the foreground location tracking service.
     * opts: { intervalMs?: number, fastestIntervalMs?: number, notificationTitle?: string, notificationText?: string }
     * success is called once with { started: true }, then repeatedly with location objects:
     *   { latitude, longitude, accuracy, speed, bearing, altitude, time, provider }
     */
    start: function (opts, success, error) {
        call('start', [opts || {}], success, error);
    },

    stop: function (success, error) {
        call('stop', [], success, error);
    },

    isRunning: function (success, error) {
        call('isRunning', [], success, error);
    },

    /** Ask the system to disable battery optimization for this app. */
    requestIgnoreBatteryOptimizations: function (success, error) {
        call('requestIgnoreBatteryOptimizations', [], success, error);
    },

    /** Open this app's location settings page so the user can grant "Allow all the time". */
    openAppSettings: function (success, error) {
        call('openAppSettings', [], success, error);
    },

    /** Get current battery optimization state: returns { ignoring: boolean }. */
    isIgnoringBatteryOptimizations: function (success, error) {
        call('isIgnoringBatteryOptimizations', [], success, error);
    }
};

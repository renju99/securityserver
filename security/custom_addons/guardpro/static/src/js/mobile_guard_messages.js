/** @odoo-module **/

/**
 * Guard Messages (chat inbox) - shim.
 * -----------------------------------
 * Historical placeholder kept because ``__manifest__.py`` and several
 * templates in ``mobile_simple_templates.xml`` reference this file.
 * The inbox chat UI itself lives in those templates; the new-message
 * notification path is now handled by ``mobile_outbox.js`` via the
 * unified outbox (``guardpro.mobile.outbox``) that ``guard.message``
 * writes to on create.
 *
 * This stub exists so the browser does not 404 on every page load,
 * which (a) breaks the console and (b) caused the service worker
 * to never cache the page.
 */
(function () {
    "use strict";
    // Intentionally empty - see mobile_outbox.js for the poller.
})();

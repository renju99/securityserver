/**
 * GuardLink Mobile Navigation - Simple and efficient
 * Handles bottom navigation and view switching
 * 
 * Note: This is a standard frontend JavaScript file, not an Odoo module.
 * It uses IIFE pattern for encapsulation.
 */

(function () {
    'use strict';

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initMobileNavigation);
    } else {
        initMobileNavigation();
    }

    function initMobileNavigation() {
        console.log('[GuardLink Mobile] Initializing navigation...');

        try {
            // Note: Navigation links use standard href navigation (separate pages)
            // We don't need to intercept them - let them work normally
            // Only add visual feedback for active navigation items

            // Mark active navigation item based on current URL
            const currentPath = window.location.pathname;
            const navLinks = document.querySelectorAll('.guardpro-mobile-nav .nav-link');
            navLinks.forEach(link => {
                try {
                    const href = link.getAttribute('href');
                    if (href && (currentPath === href || currentPath.startsWith(href + '/'))) {
                        link.classList.add('active');
                    }

                    // Ensure links are touchable and work properly
                    link.style.touchAction = 'manipulation';
                    link.style.webkitTapHighlightColor = 'rgba(26, 35, 126, 0.2)';
                    link.style.cursor = 'pointer';

                    // Add click handler that doesn't prevent default navigation
                    link.addEventListener('click', function (e) {
                        console.log('[GuardLink Mobile] Navigation link clicked:', href);
                        // Allow normal navigation - don't prevent default
                    }, { passive: true });
                } catch (err) {
                    console.warn('[GuardLink Mobile] Error setting up nav link:', err);
                }
            });

            // Handle quick widget clicks (only if they have data-view attribute)
            const widgets = document.querySelectorAll('.quick-widget[data-view]');
            widgets.forEach(widget => {
                try {
                    // Skip if already has onclick handler
                    if (widget.onclick || widget.hasAttribute('onclick')) {
                        return;
                    }
                    widget.addEventListener('click', function (e) {
                        const viewName = this.getAttribute('data-view');
                        if (viewName) {
                            e.preventDefault();
                            switchView(viewName);
                        }
                    }, { passive: false });
                } catch (err) {
                    console.warn('[GuardLink Mobile] Error setting up widget:', err);
                }
            });

            // Handle more menu items (only if they have data-action attribute)
            const moreItems = document.querySelectorAll('.more-menu-item[data-action]');
            moreItems.forEach(item => {
                try {
                    // Skip if already has onclick handler
                    if (item.onclick || item.hasAttribute('onclick')) {
                        return;
                    }
                    item.addEventListener('click', function (e) {
                        const action = this.getAttribute('data-action');
                        if (action) {
                            e.preventDefault();
                            handleMoreAction(action);
                        }
                    }, { passive: false });
                } catch (err) {
                    console.warn('[GuardLink Mobile] Error setting up more menu item:', err);
                }
            });

            // Setup geolocation for forms
            setupGeolocation();

            console.log('[GuardLink Mobile] Navigation initialized');
        } catch (err) {
            console.error('[GuardLink Mobile] Error initializing navigation:', err);
        }
    }

    function switchView(viewName) {
        console.log('[GuardLink Mobile] Switching to view:', viewName);

        // This function is only used for single-page app style navigation
        // If views exist in the DOM, switch them
        const views = document.querySelectorAll('.view-content');
        if (views.length > 0) {
            // Hide all views
            views.forEach(view => {
                view.classList.remove('active');
            });

            // Show selected view
            const selectedView = document.getElementById('view-' + viewName);
            if (selectedView) {
                selectedView.classList.add('active');
            } else {
                console.warn('[GuardLink Mobile] View not found:', viewName);
                // If view doesn't exist, redirect to the page instead
                redirectToView(viewName);
            }
        } else {
            // No views in DOM, redirect to page instead
            redirectToView(viewName);
        }

        // Load view data if needed
        loadViewData(viewName);
    }

    function redirectToView(viewName) {
        // Redirect to the appropriate page
        const routes = {
            'dashboard': '/guardpro/mobile',
            'shifts': '/guardpro/mobile/shifts',
            'tours': '/guardpro/mobile/tours',
            'tasks': '/guardpro/mobile/tasks',
            'incidents': '/guardpro/mobile/incidents',
            'more': '/guardpro/mobile/more',
            'settings': '/guardpro/mobile/settings',
            'profile': '/guardpro/mobile/profile',
            'site-info': '/guardpro/mobile/site_info',
            'emergency': '/guardpro/mobile/emergency',
            'training': '/mobile/training'
        };

        const route = routes[viewName];
        if (route) {
            console.log('[GuardLink Mobile] Redirecting to:', route);
            window.location.href = route;
        } else {
            console.warn('[GuardLink Mobile] Unknown view name:', viewName);
        }
    }

    function loadViewData(viewName) {
        // Placeholder for dynamic data loading
        console.log('[GuardLink Mobile] Loading data for view:', viewName);

        switch (viewName) {
            case 'dashboard':
                loadDashboard();
                break;
            case 'shifts':
                loadShifts();
                break;
            case 'tours':
                loadTours();
                break;
            case 'tasks':
                loadTasks();
                break;
            case 'equipment':
                loadEquipment();
                break;
            case 'attendance':
                loadAttendance();
                break;
            case 'training':
                loadTraining();
                break;
            case 'more':
                // More view doesn't need dynamic loading
                break;
        }
    }

    function loadDashboard() {
        // Dashboard data already loaded on page load
    }

    function loadShifts() {
        // Stay on mobile page - shifts view should already be in the DOM
        console.log('[GuardLink Mobile] Shifts view - data already loaded');
    }

    function loadTours() {
        // Could load tours via AJAX or redirect
        console.log('[GuardLink Mobile] Tours view');
    }

    function loadTasks() {
        // Stay on mobile page - tasks view should already be in the DOM
        console.log('[GuardLink Mobile] Tasks view - data already loaded');
    }

    function loadEquipment() {
        console.log('[GuardLink Mobile] Equipment view');
    }

    function loadAttendance() {
        console.log('[GuardLink Mobile] Attendance view');
    }

    function loadTraining() {
        console.log('[GuardLink Mobile] Training view');
    }

    function handleMoreAction(action) {
        console.log('[GuardLink Mobile] More action:', action);

        switch (action) {
            case 'profile':
                showProfile();
                break;
            case 'site-info':
                showSiteInfo();
                break;
            case 'emergency':
                showEmergencyProcedures();
                break;
            case 'training':
                redirectToView('training');
                break;
            case 'settings':
                showSettings();
                break;
            default:
                console.warn('[GuardLink Mobile] Unknown action:', action);
        }
    }

    function showProfile() {
        console.log('[GuardLink Mobile] Show profile');
        switchView('profile');
    }

    function showSiteInfo() {
        console.log('[GuardLink Mobile] Show site info');
        switchView('site-info');
    }

    function showEmergencyProcedures() {
        console.log('[GuardLink Mobile] Show emergency procedures');
        switchView('emergency');
    }

    function showSettings() {
        console.log('[GuardLink Mobile] Show settings');
        switchView('settings');
    }

    function setupGeolocation() {
        // Setup geolocation helper for forms
        window.getLocationAndSubmit = function (form, event) {
            console.log('[GuardLink Mobile] getLocationAndSubmit called for form:', form.action);

            // Always prevent default form submission
            if (event) {
                event.preventDefault();
            }

            const latField = form.querySelector('[name="latitude"]');
            const lngField = form.querySelector('[name="longitude"]');

            // Show loading state
            const submitBtn = form.querySelector('button[type="submit"]');
            const originalText = submitBtn ? submitBtn.innerHTML : '';
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Saving...';
            }

            // Create a function to submit the form properly
            const submitForm = function () {
                try {
                    // Remove the onsubmit handler temporarily to avoid infinite loop
                    const originalOnSubmit = form.onsubmit;
                    form.onsubmit = null;

                    // Use requestSubmit if available (properly triggers validation and submission)
                    if (typeof form.requestSubmit === 'function') {
                        form.requestSubmit();
                    } else {
                        // Fallback: create a temporary submit button and click it
                        // This ensures all form data including files are included
                        const tempSubmit = document.createElement('button');
                        tempSubmit.type = 'submit';
                        tempSubmit.style.display = 'none';
                        form.appendChild(tempSubmit);
                        tempSubmit.click();
                        setTimeout(function () {
                            if (form.contains(tempSubmit)) {
                                form.removeChild(tempSubmit);
                            }
                        }, 100);
                    }

                    // Restore onsubmit handler after a delay
                    setTimeout(function () {
                        form.onsubmit = originalOnSubmit;
                    }, 1000);
                } catch (error) {
                    console.error('[GuardLink Mobile] Error submitting form:', error);
                    // Last resort: direct submit
                    form.submit();
                }
            };

            // Check if geolocation is available
            if (!navigator.geolocation) {
                console.warn('[GuardLink Mobile] Geolocation not available, submitting without location');
                submitForm();
                return false;
            }

            // Get location with timeout
            const locationTimeout = setTimeout(function () {
                console.warn('[GuardLink Mobile] Location timeout, submitting without location');
                submitForm();
            }, 6000); // 6 second timeout

            navigator.geolocation.getCurrentPosition(
                function (position) {
                    clearTimeout(locationTimeout);
                    if (latField) latField.value = position.coords.latitude;
                    if (lngField) lngField.value = position.coords.longitude;
                    console.log('[GuardLink Mobile] Location captured:', position.coords.latitude, position.coords.longitude);
                    submitForm();
                },
                function (error) {
                    clearTimeout(locationTimeout);
                    // Submit without location on error
                    console.warn('[GuardLink Mobile] Location error:', error.message || error);
                    console.warn('[GuardLink Mobile] Submitting form without location');
                    submitForm();
                },
                {
                    timeout: 5000,
                    enableHighAccuracy: true,
                    maximumAge: 30000 // Accept cached position up to 30 seconds old
                }
            );

            return false;
        };

        console.log('[GuardLink Mobile] getLocationAndSubmit function registered');
    }

    // Scroll to section helper for bottom navigation
    window.scrollToSection = function (sectionId) {
        const section = document.getElementById(sectionId);
        if (section) {
            console.log('[GuardLink Mobile] Scrolling to section:', sectionId);
            section.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } else {
            console.warn('[GuardLink Mobile] Section not found:', sectionId);
        }
    };

    // Expose global API for template compatibility
    window.guardProApp = {
        switchView: switchView,
        showProfile: showProfile,
        showSiteInfo: showSiteInfo,
        showEmergencyProcedures: showEmergencyProcedures,
        showSettings: showSettings,
        getLocationAndSubmit: window.getLocationAndSubmit
    };

    console.log('[GuardLink Mobile] guardProApp API exposed');

})();


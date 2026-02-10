/**
 * Guard eLearning Navigation Enhancement
 * 
 * Adds a floating "Back to Mobile Dashboard" button for guards
 * when they are viewing eLearning courses.
 * 
 * This is a plain JavaScript file (not Odoo module) for maximum compatibility.
 */

(function() {
    'use strict';
    
    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
    
    function init() {
        // Check if we're on an eLearning page (slides)
        const currentPath = window.location.pathname;
        const isElearningPage = currentPath.includes('/slides') || currentPath.includes('/my/training');
        
        if (!isElearningPage) {
            console.log('GuardPro: Not on eLearning page, skipping mobile button');
            return;
        }
        
        console.log('GuardPro: On eLearning page, adding mobile dashboard button');
        
        // Add CSS styles first
        addStyles();
        
        // Create and add the floating button
        createMobileButton();
        
        // Also add a link in the top navigation area
        addTopNavigationLink();
    }
    
    function addStyles() {
        const style = document.createElement('style');
        style.id = 'guardpro-navigation-styles';
        style.textContent = `
            /* Floating mobile button */
            .guardpro-mobile-floating-btn {
                position: fixed !important;
                bottom: 20px !important;
                right: 20px !important;
                z-index: 99999 !important;
                border-radius: 50px !important;
                padding: 14px 28px !important;
                background-color: #007bff !important;
                color: white !important;
                font-weight: bold !important;
                box-shadow: 0 4px 12px rgba(0, 123, 255, 0.4) !important;
                text-decoration: none !important;
                display: flex !important;
                align-items: center !important;
                animation: guardpro-pulse 2s infinite;
            }
            
            @keyframes guardpro-pulse {
                0%, 100% {
                    box-shadow: 0 4px 12px rgba(0, 123, 255, 0.4);
                }
                50% {
                    box-shadow: 0 6px 20px rgba(0, 123, 255, 0.7);
                }
            }
            
            .guardpro-mobile-floating-btn:hover {
                transform: scale(1.05) !important;
                transition: all 0.2s ease-in-out !important;
                background-color: #0056b3 !important;
                color: white !important;
                text-decoration: none !important;
            }
            
            .guardpro-mobile-floating-btn i {
                font-size: 20px !important;
                margin-right: 8px !important;
            }
            
            /* Top navigation breadcrumb link */
            .guardpro-top-mobile-link {
                background-color: #28a745 !important;
                color: white !important;
                padding: 8px 16px !important;
                border-radius: 20px !important;
                margin-right: 15px !important;
                text-decoration: none !important;
                display: inline-flex !important;
                align-items: center !important;
                font-weight: 500 !important;
            }
            
            .guardpro-top-mobile-link:hover {
                background-color: #218838 !important;
                color: white !important;
                text-decoration: none !important;
            }
            
            .guardpro-top-mobile-link i {
                margin-right: 6px !important;
            }
            
            /* Responsive */
            @media (max-width: 768px) {
                .guardpro-mobile-floating-btn {
                    bottom: 15px !important;
                    right: 15px !important;
                    padding: 10px 20px !important;
                }
                
                .guardpro-mobile-floating-btn i {
                    font-size: 16px !important;
                }
            }
        `;
        
        document.head.appendChild(style);
        console.log('GuardPro: Styles added');
    }
    
    function createMobileButton() {
        // Create floating "Back to Mobile Dashboard" button
        const mobileButton = document.createElement('a');
        mobileButton.href = '/guardpro/mobile';
        mobileButton.className = 'guardpro-mobile-floating-btn';
        mobileButton.title = 'Return to Sentry Mobile Dashboard';
        mobileButton.innerHTML = '<i class="fa fa-mobile"></i> <span>Mobile</span>';
        
        // Append button to body
        document.body.appendChild(mobileButton);
        
        console.log('GuardPro: Floating mobile button added');
    }
    
    function addTopNavigationLink() {
        // Try to add a link in the breadcrumb or search area
        setTimeout(function() {
            const searchArea = document.querySelector('nav.o_wslides_home_nav form[role="search"]');
            const breadcrumb = document.querySelector('nav.breadcrumb');
            
            if (searchArea) {
                const mobileLink = document.createElement('a');
                mobileLink.href = '/guardpro/mobile';
                mobileLink.className = 'guardpro-top-mobile-link';
                mobileLink.innerHTML = '<i class="fa fa-arrow-left"></i> Mobile Dashboard';
                
                searchArea.parentElement.insertBefore(mobileLink, searchArea);
                console.log('GuardPro: Top navigation link added (search area)');
            } else if (breadcrumb) {
                const mobileLink = document.createElement('a');
                mobileLink.href = '/guardpro/mobile';
                mobileLink.className = 'guardpro-top-mobile-link';
                mobileLink.style.marginLeft = '15px';
                mobileLink.innerHTML = '<i class="fa fa-arrow-left"></i> Mobile Dashboard';
                
                breadcrumb.appendChild(mobileLink);
                console.log('GuardPro: Top navigation link added (breadcrumb)');
            }
        }, 500);  // Small delay to ensure DOM is fully loaded
    }
    
})();


/**
 * GuardPro Documentation JavaScript
 * Plain JavaScript (no Odoo module format)
 */

(function() {
    'use strict';
    
    // Wait for DOM to be ready
    document.addEventListener('DOMContentLoaded', function() {
        try {
            initDocumentationSearch();
            initCodeHighlighting();
            initSmoothScroll();
            /* In-app docs already have a full sidebar; auto-TOC duplicated nav and looked broken in some themes. */
            /* initTableOfContents(); */
            initScrollToTop();
            initKeyboardShortcuts();
            initLoadingStates();
            initAnimations();
        } catch (error) {
            console.error('Documentation viewer initialization error:', error);
        }
    });
    
    /**
     * Initialize documentation search functionality
     */
    function initDocumentationSearch() {
        var searchInput = document.getElementById('docSearchInput');
        var searchBtn = document.getElementById('docSearchBtn');
        var searchResults = document.getElementById('searchResults');
        
        if (!searchInput || !searchBtn || !searchResults) {
            return;
        }
        
        // Search on button click
        searchBtn.addEventListener('click', function() {
            performSearch();
        });
        
        // Search on Enter key
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                performSearch();
            }
        });
        
        // Clear results when input is empty
        searchInput.addEventListener('input', function() {
            if (this.value.length === 0) {
                searchResults.innerHTML = '';
                searchResults.classList.remove('show');
            }
        });
        
        /**
         * Perform documentation search
         */
        function performSearch() {
            var query = searchInput.value.trim();
            
            if (query.length < 3) {
                searchResults.innerHTML = '<div class="p-3 text-muted">Please enter at least 3 characters</div>';
                searchResults.classList.add('show');
                return;
            }
            
            // Show loading
            searchResults.innerHTML = '<div class="p-3"><i class="fa fa-spinner fa-spin"></i> Searching...</div>';
            searchResults.classList.add('show');
            
            // Call search endpoint
            fetch('/guardpro/documentation/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: {
                        query: query
                    }
                })
            })
            .then(response => {
                console.log('Search response status:', response.status);
                return response.json();
            })
            .then(data => {
                console.log('Search response data:', data);
                // Handle both direct response and JSON-RPC response
                var result = data.result || data;
                displaySearchResults(result);
            })
            .catch(error => {
                console.error('Search error:', error);
                searchResults.innerHTML = '<div class="p-3 alert alert-danger">Search failed. Please try again.</div>';
            });
        }
        
        /**
         * Display search results
         */
        function displaySearchResults(data) {
            if (data.error) {
                searchResults.innerHTML = '<div class="p-3 alert alert-danger">Search error: ' + escapeHtml(data.error) + '</div>';
                return;
            }
            
            if (!data.results || data.results.length === 0) {
                searchResults.innerHTML = '<div class="p-3 text-muted">No results found</div>';
                return;
            }
            
            var html = '';
            data.results.forEach(function(result) {
                html += '<div class="search-result-item" onclick="window.location.href=\'/guardpro/documentation/' + result.file + '\'">';
                html += '<div class="search-result-section">' + formatSectionName(result.section) + '</div>';
                html += '<div class="search-result-title">' + escapeHtml(result.title) + '</div>';
                html += '<div class="search-result-context">' + escapeHtml(result.context) + '</div>';
                html += '</div>';
            });
            
            searchResults.innerHTML = html;
        }
        
        /**
         * Format section name for display
         */
        function formatSectionName(section) {
            return section.replace(/_/g, ' ').replace(/\b\w/g, function(l) {
                return l.toUpperCase();
            });
        }
        
        /**
         * Escape HTML to prevent XSS
         */
        function escapeHtml(text) {
            var map = {
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#039;'
            };
            return text.replace(/[&<>"']/g, function(m) {
                return map[m];
            });
        }
    }
    
    /**
     * Initialize code syntax highlighting
     */
    function initCodeHighlighting() {
        // Add copy button to code blocks
        var codeBlocks = document.querySelectorAll('.documentation-body pre');
        
        codeBlocks.forEach(function(block) {
            // Create copy button
            var copyBtn = document.createElement('button');
            copyBtn.className = 'btn btn-sm btn-outline-light code-copy-btn';
            copyBtn.innerHTML = '<i class="fa fa-copy"></i> Copy';
            copyBtn.style.cssText = 'position: absolute; top: 5px; right: 5px; z-index: 10;';
            
            // Wrap block in relative container
            var wrapper = document.createElement('div');
            wrapper.style.position = 'relative';
            block.parentNode.insertBefore(wrapper, block);
            wrapper.appendChild(block);
            wrapper.appendChild(copyBtn);
            
            // Add copy functionality
            copyBtn.addEventListener('click', function() {
                var code = block.querySelector('code') || block;
                var text = code.textContent;
                
                navigator.clipboard.writeText(text).then(function() {
                    copyBtn.innerHTML = '<i class="fa fa-check"></i> Copied!';
                    copyBtn.classList.add('btn-success');
                    copyBtn.classList.remove('btn-outline-light');
                    
                    setTimeout(function() {
                        copyBtn.innerHTML = '<i class="fa fa-copy"></i> Copy';
                        copyBtn.classList.remove('btn-success');
                        copyBtn.classList.add('btn-outline-light');
                    }, 2000);
                }).catch(function(err) {
                    console.error('Copy failed:', err);
                });
            });
        });
    }
    
    /**
     * Initialize smooth scrolling for anchor links
     */
    function initSmoothScroll() {
        var links = document.querySelectorAll('.documentation-body a[href^="#"]');
        
        links.forEach(function(link) {
            link.addEventListener('click', function(e) {
                var targetId = this.getAttribute('href').substring(1);
                var targetElement = document.getElementById(targetId);
                
                if (targetElement) {
                    e.preventDefault();
                    targetElement.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            });
        });
    }
    
    /**
     * Initialize table of contents generation
     */
    function initTableOfContents() {
        var headings = document.querySelectorAll('.documentation-body h2, .documentation-body h3');
        
        if (headings.length === 0) {
            return;
        }
        
        // Create TOC container (custom markup — avoid Bootstrap .card dark-theme clashes in Odoo)
        var tocContainer = document.createElement('div');
        tocContainer.className = 'documentation-toc docs-toc-panel';
        tocContainer.setAttribute('role', 'navigation');
        tocContainer.setAttribute('aria-label', 'On this page');
        tocContainer.innerHTML = '<div class="docs-toc-header">' +
            '<span class="docs-toc-title"><i class="fa fa-list mr-1"></i> On this page</span>' +
            '</div>' +
            '<div class="docs-toc-body">' +
            '<ul class="toc-list list-unstyled mb-0"></ul>' +
            '</div>';
        
        var tocList = tocContainer.querySelector('.toc-list');
        
        // Build TOC
        headings.forEach(function(heading, index) {
            // Add ID to heading if it doesn't have one
            if (!heading.id) {
                heading.id = 'heading-' + index;
            }
            
            var li = document.createElement('li');
            li.className = heading.tagName === 'H2' ? 'toc-h2' : 'toc-h3';
            
            var link = document.createElement('a');
            link.href = '#' + heading.id;
            link.textContent = heading.textContent;
            
            li.appendChild(link);
            tocList.appendChild(li);
        });
        
        // Insert TOC at the beginning of content
        var contentBody = document.querySelector('.documentation-body');
        var firstHeading = contentBody.querySelector('h1, h2');
        
        if (firstHeading && headings.length >= 3) {
            firstHeading.parentNode.insertBefore(tocContainer, firstHeading.nextSibling);
        }
    }
    
    /**
     * Initialize scroll to top functionality
     */
    function initScrollToTop() {
        var scrollBtn = document.getElementById('scrollToTop');
        if (!scrollBtn) return;

        // Show/hide button based on scroll position
        window.addEventListener('scroll', function() {
            if (window.pageYOffset > 300) {
                scrollBtn.style.display = 'flex';
                scrollBtn.style.alignItems = 'center';
                scrollBtn.style.justifyContent = 'center';
            } else {
                scrollBtn.style.display = 'none';
            }
        });
    }

    /**
     * Initialize keyboard shortcuts
     */
    function initKeyboardShortcuts() {
        document.addEventListener('keydown', function(e) {
            // Ctrl/Cmd + K: Focus search
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                var searchInput = document.getElementById('docSearchInput');
                if (searchInput) {
                    searchInput.focus();
                    searchInput.select();
                }
            }

            // Ctrl/Cmd + /: Show keyboard shortcuts help
            if ((e.ctrlKey || e.metaKey) && e.key === '/') {
                e.preventDefault();
                showKeyboardShortcuts();
            }
        });
    }

    /**
     * Show keyboard shortcuts help
     */
    function showKeyboardShortcuts() {
        var shortcuts = [
            { keys: 'Ctrl+K', description: 'Focus search box' },
            { keys: 'Ctrl+/', description: 'Show this help' },
            { keys: 'Ctrl+Enter', description: 'Submit forms' },
            { keys: 'Ctrl+S', description: 'Save draft' },
            { keys: 'Esc', description: 'Cancel/Close modals' },
            { keys: 'Ctrl+P', description: 'Print page' }
        ];

        var html = '<div class="keyboard-shortcuts-modal">';
        html += '<div class="modal-backdrop fade show"></div>';
        html += '<div class="modal fade show d-block" tabindex="-1">';
        html += '<div class="modal-dialog modal-dialog-centered">';
        html += '<div class="modal-content">';
        html += '<div class="modal-header">';
        html += '<h5 class="modal-title"><i class="fa fa-keyboard-o mr-2"></i>Keyboard Shortcuts</h5>';
        html += '<button type="button" class="close" onclick="this.closest(\'.keyboard-shortcuts-modal\').remove()">';
        html += '<span>&times;</span></button></div>';
        html += '<div class="modal-body">';
        html += '<div class="list-group">';

        shortcuts.forEach(function(shortcut) {
            html += '<div class="list-group-item d-flex justify-content-between align-items-center">';
            html += '<span>' + shortcut.description + '</span>';
            html += '<kbd class="bg-light text-dark px-2 py-1 rounded">' + shortcut.keys + '</kbd>';
            html += '</div>';
        });

        html += '</div></div></div></div></div></div>';

        document.body.insertAdjacentHTML('beforeend', html);
    }

    /**
     * Initialize loading states
     */
    function initLoadingStates() {
        // Add loading state to search button
        var searchBtn = document.getElementById('docSearchBtn');
        if (searchBtn) {
            var originalHtml = searchBtn.innerHTML;
            searchBtn.addEventListener('click', function() {
                if (this.classList.contains('loading')) return;

                this.classList.add('loading');
                this.innerHTML = '<i class="fa fa-spinner fa-spin mr-1"></i>Searching...';

                // Remove loading state after 2 seconds (fallback)
                setTimeout(function() {
                    searchBtn.classList.remove('loading');
                    searchBtn.innerHTML = originalHtml;
                }, 2000);
            });
        }
    }

    /**
     * Initialize animations
     */
    function initAnimations() {
        // Add fade-in animation to content
        var contentBody = document.querySelector('.odoo-docs-body');
        if (contentBody) {
            contentBody.classList.add('fade-in');
        }

        // Add slide-in animation to sidebar items
        var sidebarLinks = document.querySelectorAll('.documentation-sidebar .nav-link');
        sidebarLinks.forEach(function(link, index) {
            link.style.animationDelay = (index * 0.05) + 's';
            link.classList.add('slide-in-left');
        });

        // Animate search results
        var searchResults = document.getElementById('searchResults');
        if (searchResults) {
            var observer = new MutationObserver(function(mutations) {
                mutations.forEach(function(mutation) {
                    if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                        var resultItems = searchResults.querySelectorAll('.search-result-item');
                        resultItems.forEach(function(item, index) {
                            item.style.animationDelay = (index * 0.1) + 's';
                            item.classList.add('fade-in');
                        });
                    }
                });
            });
            observer.observe(searchResults, { childList: true });
        }
    }

    /**
     * Enhanced search with debouncing and better UX
     */
    function performSearch() {
        var query = searchInput.value.trim();

        if (query.length < 3) {
            searchResults.innerHTML = '<div class="p-4 text-center text-muted">' +
                '<i class="fa fa-search fa-2x mb-2"></i>' +
                '<p>Please enter at least 3 characters to search</p>' +
                '</div>';
            searchResults.classList.add('show');
            return;
        }

        // Show loading
        searchResults.innerHTML = '<div class="p-4 text-center">' +
            '<i class="fa fa-spinner fa-spin fa-2x text-primary mb-2"></i>' +
            '<p class="text-muted">Searching documentation...</p>' +
            '</div>';
        searchResults.classList.add('show');

        // Call search endpoint with error handling
        fetch('/guardpro/documentation/search', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                jsonrpc: '2.0',
                method: 'call',
                params: {
                    query: query
                }
            })
        })
        .then(function(response) {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(function(data) {
            var result = data.result || data;
            displaySearchResults(result);
        })
        .catch(function(error) {
            console.error('Search error:', error);
            searchResults.innerHTML = '<div class="p-4 alert alert-danger">' +
                '<i class="fa fa-exclamation-triangle mr-2"></i>' +
                'Search failed. Please check your connection and try again.' +
                '</div>';
        })
        .finally(function() {
            // Remove loading state from button
            searchBtn.classList.remove('loading');
            searchBtn.innerHTML = '<i class="fa fa-search mr-1"></i>Search';
        });
    }

    /**
     * Add print functionality with better formatting
     */
    window.printDocumentation = function() {
        // Add print-specific styles
        var printStyle = document.createElement('style');
        printStyle.innerHTML = '@media print { .no-print { display: none !important; } }';
        document.head.appendChild(printStyle);

        window.print();

        // Clean up
        setTimeout(function() {
            document.head.removeChild(printStyle);
        }, 1000);
    };

    /**
     * Enhanced copy functionality with better feedback
     */
    function initEnhancedCopy() {
        document.addEventListener('click', function(e) {
            if (e.target.closest('.code-copy-btn')) {
                var btn = e.target.closest('.code-copy-btn');
                var codeBlock = btn.closest('pre');
                var code = codeBlock.querySelector('code') || codeBlock;

                navigator.clipboard.writeText(code.textContent).then(function() {
                    var originalHtml = btn.innerHTML;
                    btn.innerHTML = '<i class="fa fa-check"></i> Copied!';
                    btn.classList.remove('btn-outline-light');
                    btn.classList.add('btn-success');

                    setTimeout(function() {
                        btn.innerHTML = originalHtml;
                        btn.classList.remove('btn-success');
                        btn.classList.add('btn-outline-light');
                    }, 2000);
                }).catch(function(err) {
                    console.error('Copy failed:', err);
                    btn.innerHTML = '<i class="fa fa-times"></i> Failed';
                    btn.classList.remove('btn-outline-light');
                    btn.classList.add('btn-danger');

                    setTimeout(function() {
                        btn.innerHTML = '<i class="fa fa-copy"></i> Copy';
                        btn.classList.remove('btn-danger');
                        btn.classList.add('btn-outline-light');
                    }, 2000);
                });
            }
        });
    }

    // Initialize enhanced copy functionality
    initEnhancedCopy();

})();


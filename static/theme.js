// Theme management
(function() {
    'use strict';
    
    const THEME_KEY = 'attendance_theme';
    const THEME_ATTRIBUTE = 'data-theme';
    
    // Get saved theme or default to dark
    function getSavedTheme() {
        const saved = localStorage.getItem(THEME_KEY);
        // Default to dark if nothing saved or invalid value
        return (saved === 'light' || saved === 'dark') ? saved : 'dark';
    }
    
    // Save theme preference
    function saveTheme(theme) {
        localStorage.setItem(THEME_KEY, theme);
    }
    
    // Apply theme to document
    function applyTheme(theme) {
        // Ensure theme is valid
        if (theme !== 'light' && theme !== 'dark') {
            theme = 'dark';
        }
        
        // Remove any existing theme attribute first
        document.documentElement.removeAttribute(THEME_ATTRIBUTE);
        
        // Only set attribute for light theme (dark is default via :root)
        if (theme === 'light') {
            document.documentElement.setAttribute(THEME_ATTRIBUTE, 'light');
        }
        // For dark theme, we can either set it explicitly or rely on :root
        // Setting it explicitly ensures consistency
        else {
            document.documentElement.setAttribute(THEME_ATTRIBUTE, 'dark');
        }
        
        saveTheme(theme);
        updateThemeToggleIcon(theme);
    }
    
    // Toggle between light and dark
    function toggleTheme() {
        const currentAttr = document.documentElement.getAttribute(THEME_ATTRIBUTE);
        // If no attribute, check saved theme or default to dark
        const currentTheme = currentAttr || getSavedTheme() || 'dark';
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        applyTheme(newTheme);
    }
    
    // Update theme toggle icon
    function updateThemeToggleIcon(theme) {
        const toggle = document.getElementById('theme-toggle');
        if (!toggle) return;
        
        let icon = toggle.querySelector('svg');
        if (!icon) {
            // Create SVG if it doesn't exist
            icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            icon.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
            icon.setAttribute('viewBox', '0 0 24 24');
            icon.setAttribute('fill', 'none');
            icon.setAttribute('stroke', 'currentColor');
            icon.setAttribute('stroke-width', '2');
            icon.setAttribute('stroke-linecap', 'round');
            icon.setAttribute('stroke-linejoin', 'round');
            toggle.appendChild(icon);
        }
        
        // Clear existing content
        icon.innerHTML = '';
        
        // Update icon based on theme
        if (theme === 'light') {
            // Moon icon for light theme (click to go dark)
            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.setAttribute('d', 'M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z');
            icon.appendChild(path);
        } else {
            // Sun icon for dark theme (click to go light)
            const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            circle.setAttribute('cx', '12');
            circle.setAttribute('cy', '12');
            circle.setAttribute('r', '5');
            icon.appendChild(circle);
            
            const lines = [
                {x1: '12', y1: '1', x2: '12', y2: '3'},
                {x1: '12', y1: '21', x2: '12', y2: '23'},
                {x1: '4.22', y1: '4.22', x2: '5.64', y2: '5.64'},
                {x1: '18.36', y1: '18.36', x2: '19.78', y2: '19.78'},
                {x1: '1', y1: '12', x2: '3', y2: '12'},
                {x1: '21', y1: '12', x2: '23', y2: '12'},
                {x1: '4.22', y1: '19.78', x2: '5.64', y2: '18.36'},
                {x1: '18.36', y1: '5.64', x2: '19.78', y2: '4.22'}
            ];
            
            lines.forEach(line => {
                const lineEl = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                lineEl.setAttribute('x1', line.x1);
                lineEl.setAttribute('y1', line.y1);
                lineEl.setAttribute('x2', line.x2);
                lineEl.setAttribute('y2', line.y2);
                icon.appendChild(lineEl);
            });
        }
    }
    
    // Initialize theme on page load
    function initTheme() {
        // Force dark theme on first load if no preference saved
        const savedTheme = getSavedTheme();
        
        // If saved theme is invalid or missing, default to dark
        if (!savedTheme || (savedTheme !== 'light' && savedTheme !== 'dark')) {
            applyTheme('dark');
        } else {
            applyTheme(savedTheme);
        }
        
        // Add event listener to toggle button
        const toggle = document.getElementById('theme-toggle');
        if (toggle) {
            // Remove any existing listeners to prevent duplicates
            const newToggle = toggle.cloneNode(true);
            toggle.parentNode.replaceChild(newToggle, toggle);
            newToggle.addEventListener('click', toggleTheme);
        }
    }
    
    // Run when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTheme);
    } else {
        initTheme();
    }
})();


/**
 * Dashboard functionality for the Insider Threat Detection System
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize feather icons
    feather.replace();
    
    // Make entire user row clickable in the threats table
    const userRows = document.querySelectorAll('.user-row');
    userRows.forEach(row => {
        row.addEventListener('click', function(e) {
            // Don't trigger if clicking on a button or link
            if (!e.target.closest('a, button')) {
                const userId = this.getAttribute('data-user-id');
                window.location.href = `/user/${userId}`;
            }
        });
    });
    
    // Add hover class to user rows
    userRows.forEach(row => {
        row.classList.add('user-card');
    });
    
    // Update last analysis time
    document.getElementById('last-analysis-time').textContent = new Date().toLocaleTimeString();
    
    // Initialize periodic update (every 60 seconds)
    setInterval(updateDashboard, 60000);
});

/**
 * Updates dashboard data without full page refresh
 */
function updateDashboard() {
    // Fetch latest threats data
    fetch('/api/threats')
        .then(response => response.json())
        .then(threats => {
            // Update counts
            document.getElementById('total-users').textContent = threats.length;
            
            const highRiskCount = threats.filter(t => t.risk_score >= 0.75).length;
            document.getElementById('high-risk-count').textContent = highRiskCount;
            
            const mediumRiskCount = threats.filter(t => t.risk_score >= 0.5 && t.risk_score < 0.75).length;
            document.getElementById('medium-risk-count').textContent = mediumRiskCount;
            
            // Update risk chart if it exists
            const riskChart = Chart.getChart('riskChart');
            if (riskChart) {
                const lowRiskCount = threats.filter(t => t.risk_score >= 0.25 && t.risk_score < 0.5).length;
                const noRiskCount = threats.filter(t => t.risk_score < 0.25).length;
                
                riskChart.data.datasets[0].data = [
                    highRiskCount,
                    mediumRiskCount,
                    lowRiskCount,
                    noRiskCount
                ];
                riskChart.update();
            }
            
            // Update last analysis time
            document.getElementById('last-analysis-time').textContent = new Date().toLocaleTimeString();
        })
        .catch(error => {
            console.error('Error updating dashboard:', error);
        });
}

/**
 * Format a risk score with appropriate color class
 * @param {number} score - Risk score between 0 and 1
 * @returns {Object} Object with score text and color class
 */
function formatRiskScore(score) {
    const percentage = score * 100;
    
    let color = 'success';
    if (percentage >= 75) {
        color = 'danger';
    } else if (percentage >= 50) {
        color = 'warning';
    } else if (percentage >= 25) {
        color = 'info';
    }
    
    return {
        score: `${percentage.toFixed(1)}%`,
        color: color
    };
}

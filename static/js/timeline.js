/**
 * Timeline visualization for user activities
 */

/**
 * Initialize timeline visualization with activity data and optional attention weights
 * @param {Array} activities - List of user activities
 * @param {Object} attentionData - Optional attention weights data
 */
function initTimeline(activities, attentionData) {
    // Group activities by day
    const groupedActivities = groupActivitiesByDay(activities);
    
    // Map attention weights to activities if available
    const weightedActivities = mapAttentionWeights(groupedActivities, attentionData);
    
    // Render timeline
    renderTimeline(weightedActivities);
}

/**
 * Group activities by day
 * @param {Array} activities - List of user activities
 * @returns {Object} Activities grouped by day
 */
function groupActivitiesByDay(activities) {
    const days = {};
    
    activities.forEach(activity => {
        const date = new Date(activity.timestamp);
        const dateKey = date.toISOString().split('T')[0]; // YYYY-MM-DD
        
        if (!days[dateKey]) {
            days[dateKey] = {
                date: dateKey,
                displayDate: formatDate(date),
                activities: []
            };
        }
        
        days[dateKey].activities.push({
            id: activity.id,
            time: formatTime(date),
            timestamp: date,
            type: activity.activity_type,
            details: activity.details,
            importance: 0 // Default importance, will be updated with attention weights
        });
    });
    
    // Sort activities within each day by time
    Object.values(days).forEach(day => {
        day.activities.sort((a, b) => a.timestamp - b.timestamp);
    });
    
    // Convert to array and sort by date
    return Object.values(days).sort((a, b) => 
        new Date(a.date) - new Date(b.date)
    );
}

/**
 * Map attention weights to activities
 * @param {Array} groupedActivities - Activities grouped by day
 * @param {Object} attentionData - Attention weights data
 * @returns {Array} Activities with mapped attention weights
 */
function mapAttentionWeights(groupedActivities, attentionData) {
    // If no attention data, return original activities
    if (!attentionData || !attentionData.timestamps || !attentionData.weights) {
        return groupedActivities;
    }
    
    // Create timestamp -> weight mapping
    const weightMap = {};
    attentionData.timestamps.forEach((timestamp, i) => {
        weightMap[timestamp] = attentionData.weights[i];
    });
    
    // Map weights to activities
    groupedActivities.forEach(day => {
        day.activities.forEach(activity => {
            // Find closest timestamp in attention data
            const activityTime = activity.timestamp.toISOString();
            let closestTime = null;
            let minDiff = Infinity;
            
            for (const timestamp of attentionData.timestamps) {
                const diff = Math.abs(new Date(timestamp) - activity.timestamp);
                if (diff < minDiff) {
                    minDiff = diff;
                    closestTime = timestamp;
                }
            }
            
            // Only use weight if within 24 hours (86400000 ms)
            if (closestTime && minDiff < 86400000) {
                activity.importance = weightMap[closestTime];
            }
        });
    });
    
    return groupedActivities;
}

/**
 * Render timeline visualization
 * @param {Array} groupedActivities - Activities grouped by day with attention weights
 */
function renderTimeline(groupedActivities) {
    const timelineContainer = document.getElementById('activity-timeline');
    
    // Clear any existing content
    timelineContainer.innerHTML = '';
    
    // If no activities, show message
    if (groupedActivities.length === 0) {
        timelineContainer.innerHTML = `
            <div class="text-center py-5">
                <span data-feather="calendar" style="width: 48px; height: 48px;" class="text-muted mb-3"></span>
                <p class="mb-0">No activity data available for this user.</p>
            </div>
        `;
        return;
    }
    
    // Add each day to the timeline
    groupedActivities.forEach(day => {
        const dayElement = document.createElement('div');
        dayElement.className = 'timeline-date mb-3';
        dayElement.textContent = day.displayDate;
        timelineContainer.appendChild(dayElement);
        
        // Add activities for this day
        day.activities.forEach(activity => {
            const activityElement = document.createElement('div');
            
            // Determine if activity is suspicious based on importance
            const isSuspicious = activity.importance > 0.2; // Threshold for suspicious
            
            activityElement.className = `activity-item mb-3 ${isSuspicious ? 'suspicious' : ''}`;
            
            // Calculate background color based on importance (red with varying opacity)
            const opacity = Math.min(0.1 + (activity.importance * 0.9), 1);
            if (activity.importance > 0) {
                activityElement.style.backgroundColor = `rgba(220, 53, 69, ${opacity * 0.2})`;
            }
            
            // Create activity content
            activityElement.innerHTML = `
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <div class="d-flex align-items-center">
                            <span data-feather="${getActivityIcon(activity.type)}" class="me-2"></span>
                            <strong>${activity.type.toUpperCase()}</strong>
                            <span class="activity-time ms-2">${activity.time}</span>
                        </div>
                        <p class="mb-1">${formatActivityDescription(activity)}</p>
                    </div>
                    ${activity.importance > 0 ? 
                        `<span class="badge ${getImportanceBadgeClass(activity.importance)}">
                            Attention: ${Math.round(activity.importance * 100)}%
                        </span>` : ''}
                </div>
            `;
            
            timelineContainer.appendChild(activityElement);
        });
    });
    
    // Initialize feather icons for the newly added elements
    feather.replace();
}

/**
 * Get icon name for activity type
 * @param {string} activityType - Type of activity
 * @returns {string} Feather icon name
 */
function getActivityIcon(activityType) {
    switch (activityType) {
        case 'logon': return 'log-in';
        case 'device': return 'hard-drive';
        case 'email': return 'mail';
        case 'file': return 'file-text';
        case 'web': return 'globe';
        default: return 'activity';
    }
}

/**
 * Format activity description based on details
 * @param {Object} activity - Activity object
 * @returns {string} Formatted description
 */
function formatActivityDescription(activity) {
    const details = activity.details;
    
    if (!details) {
        return `${activity.type} activity`;
    }
    
    switch (activity.type) {
        case 'logon':
            const logonType = details.logon_type || 'Unknown';
            const device = details.device_id || 'Unknown device';
            const success = details.success ? 'successful' : 'failed';
            return `${logonType} logon (${success}) on ${device}`;
            
        case 'device':
            const deviceType = details.device_type || 'Unknown device';
            const action = details.action || 'accessed';
            return `${action} ${deviceType} device`;
            
        case 'email':
            const recipient = details.recipient || 'unknown recipient';
            const subject = details.subject || 'No subject';
            const hasAttachment = details.attachment_size > 0 ? 'with attachment' : 'without attachments';
            return `Email to ${recipient} (${subject}) ${hasAttachment}`;
            
        case 'file':
            const path = details.path || 'unknown location';
            const operation = details.operation || 'accessed';
            const count = details.file_count || 1;
            const fileText = count > 1 ? 'files' : 'file';
            return `${operation} ${count} ${fileText} in ${path}`;
            
        case 'web':
            const url = details.url || 'unknown website';
            const duration = details.duration || 0;
            return `Visited ${url} for ${duration} minutes`;
            
        default:
            return `${activity.type} activity`;
    }
}

/**
 * Get badge class based on importance value
 * @param {number} importance - Importance value between 0 and 1
 * @returns {string} Bootstrap badge class
 */
function getImportanceBadgeClass(importance) {
    if (importance >= 0.75) {
        return 'bg-danger';
    } else if (importance >= 0.5) {
        return 'bg-warning';
    } else if (importance >= 0.25) {
        return 'bg-info';
    } else {
        return 'bg-secondary';
    }
}

/**
 * Format date for display
 * @param {Date} date - Date object
 * @returns {string} Formatted date string
 */
function formatDate(date) {
    const options = { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' };
    return date.toLocaleDateString('en-US', options);
}

/**
 * Format time for display
 * @param {Date} date - Date object
 * @returns {string} Formatted time string
 */
function formatTime(date) {
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
}

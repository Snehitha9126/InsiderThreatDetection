/**
 * Attention weight visualization for model explainability
 */

/**
 * Initialize attention visualization
 * @param {Object} attentionData - Attention data with weights and feature names
 */
function initAttentionVisualization(attentionData) {
    // Check if we have valid attention data
    if (!attentionData || !attentionData.weights || !attentionData.timestamps || !attentionData.feature_names) {
        document.getElementById('attention-heatmap').innerHTML = 
            '<div class="alert alert-info">No attention data available</div>';
        return;
    }
    
    // Create heatmap visualization using D3.js
    createAttentionHeatmap(attentionData);
}

/**
 * Create a heatmap visualization of attention weights
 * @param {Object} attentionData - Attention data
 */
function createAttentionHeatmap(attentionData) {
    // Clear any existing content
    const container = document.getElementById('attention-heatmap');
    container.innerHTML = '';
    
    // Set up dimensions
    const margin = { top: 30, right: 30, bottom: 100, left: 100 };
    const width = container.clientWidth - margin.left - margin.right;
    const height = 300 - margin.top - margin.bottom;
    
    // Create SVG
    const svg = d3.select('#attention-heatmap')
        .append('svg')
            .attr('width', width + margin.left + margin.right)
            .attr('height', height + margin.top + margin.bottom)
        .append('g')
            .attr('transform', `translate(${margin.left},${margin.top})`);
    
    // Process data
    const timestamps = attentionData.timestamps.map(ts => {
        const date = new Date(ts);
        return `${date.toLocaleDateString()} ${date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}`;
    });
    
    // Display only a subset of feature names if there are too many
    let featureNames = attentionData.feature_names;
    if (featureNames.length > 8) {
        // Take most important features based on average attention
        const featureImportance = {};
        featureNames.forEach(feature => {
            featureImportance[feature] = 0;
        });
        
        attentionData.weights.forEach(weight => {
            featureNames.forEach(feature => {
                featureImportance[feature] += weight;
            });
        });
        
        // Sort by importance and take top 8
        featureNames = Object.keys(featureImportance)
            .sort((a, b) => featureImportance[b] - featureImportance[a])
            .slice(0, 8);
    }
    
    // Format feature names for display
    const displayFeatureNames = featureNames.map(name => {
        return name
            .replace(/_/g, ' ')
            .replace(/count/g, '')
            .trim()
            .split(' ')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ');
    });
    
    // Create scales
    const x = d3.scaleBand()
        .range([0, width])
        .domain(timestamps)
        .padding(0.05);
    
    const y = d3.scaleBand()
        .range([height, 0])
        .domain(displayFeatureNames)
        .padding(0.05);
    
    // Add X axis
    svg.append('g')
        .attr('transform', `translate(0,${height})`)
        .call(d3.axisBottom(x)
            .tickFormat((d, i) => {
                // Show abbreviated timestamps for readability
                const date = new Date(attentionData.timestamps[i]);
                return `${date.getMonth()+1}/${date.getDate()} ${date.getHours()}:${String(date.getMinutes()).padStart(2, '0')}`;
            })
        )
        .selectAll('text')
            .attr('transform', 'rotate(-45)')
            .style('text-anchor', 'end')
            .attr('dx', '-.8em')
            .attr('dy', '.15em')
            .style('font-size', '10px');
    
    // Add Y axis
    svg.append('g')
        .call(d3.axisLeft(y))
        .selectAll('text')
            .style('font-size', '10px');
    
    // Build color scale
    const colorScale = d3.scaleSequential()
        .interpolator(d3.interpolateReds)
        .domain([0, 1]);
    
    // Create tooltip
    const tooltip = d3.select('body')
        .append('div')
        .attr('class', 'attention-tooltip')
        .style('opacity', 0);
    
    // Add squares for each cell in the heatmap
    for (let i = 0; i < attentionData.weights.length; i++) {
        const weight = attentionData.weights[i];
        const timestamp = timestamps[i];
        
        for (let j = 0; j < displayFeatureNames.length; j++) {
            const featureName = displayFeatureNames[j];
            
            // Calculate cell color - all features at the same time point get same weight
            svg.append('rect')
                .attr('x', x(timestamp))
                .attr('y', y(featureName))
                .attr('width', x.bandwidth())
                .attr('height', y.bandwidth())
                .attr('class', 'cell')
                .style('fill', colorScale(weight))
                .on('mouseover', function(event) {
                    tooltip.transition()
                        .duration(200)
                        .style('opacity', .9);
                    
                    tooltip.html(`
                        <strong>${featureName}</strong><br/>
                        Time: ${timestamp}<br/>
                        Attention: ${(weight * 100).toFixed(1)}%
                    `)
                    .style('left', (event.pageX + 10) + 'px')
                    .style('top', (event.pageY - 28) + 'px');
                    
                    d3.select(this)
                        .style('stroke', '#white')
                        .style('stroke-width', 2);
                })
                .on('mouseout', function() {
                    tooltip.transition()
                        .duration(500)
                        .style('opacity', 0);
                    
                    d3.select(this)
                        .style('stroke', 'var(--bs-dark)')
                        .style('stroke-width', 1);
                });
        }
    }
    
    // Add title
    svg.append('text')
        .attr('x', width / 2)
        .attr('y', -10)
        .attr('text-anchor', 'middle')
        .style('font-size', '14px')
        .text('Attention Weights Heatmap');
    
    // Add X axis label
    svg.append('text')
        .attr('x', width / 2)
        .attr('y', height + margin.bottom - 40)
        .attr('text-anchor', 'middle')
        .style('font-size', '12px')
        .text('Timestamp');
    
    // Add Y axis label
    svg.append('text')
        .attr('transform', 'rotate(-90)')
        .attr('x', -height / 2)
        .attr('y', -margin.left + 20)
        .attr('text-anchor', 'middle')
        .style('font-size', '12px')
        .text('Feature');
}

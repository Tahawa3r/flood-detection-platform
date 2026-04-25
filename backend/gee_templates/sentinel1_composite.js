// =============================================================================
// Sentinel-1 Flood Detection Template
// =============================================================================
// This script helps detect flooding by comparing satellite radar images before 
// and after a flood event. Sentinel-1 radar can see through clouds and darkness,
// making it perfect for flood monitoring during disasters.
//
// HOW TO USE:
// 1. Copy this entire script
// 2. Go to https://code.earthengine.google.com/
// 3. Paste and click Run
// 4. Check the map for flood areas (red = increased water)
// 5. Export results if needed from the Tasks tab
// =============================================================================

// =============================================================================
// STEP 1: DEFINE YOUR STUDY AREA
// =============================================================================
// Replace these coordinates with your area of interest.
// Format: [[longitude, latitude], [longitude, latitude], ...]
// Current example: Morocco region around Tangier
var geometry = ee.Geometry.Polygon([
    [[-6.5, 34.0], [-5.5, 34.0], [-5.5, 35.0], [-6.5, 35.0], [-6.5, 34.0]]
]);

// =============================================================================
// STEP 2: SET TIME PERIODS
// =============================================================================
// Define the dates for comparison:
// - PRE_START/PRE_END: Normal conditions before the flood
// - POST_START/POST_END: During/after the flood event
var PRE_START = '2023-09-01';  // Start of dry season (before flood)
var PRE_END = '2023-10-31';    // End of dry season (before flood)
var POST_START = '2023-11-01';  // Start of flood period
var POST_END = '2023-12-15';    // End of flood period

// =============================================================================
// STEP 3: SENTINEL-1 DATA PROCESSING
// =============================================================================
// This function fetches and processes Sentinel-1 radar data
// Sentinel-1 uses radar waves that can detect water on the surface
function getS1(startDate, endDate) {
    return ee.ImageCollection('COPERNICUS/S1_GRD')
        // Limit to our study area
        .filterBounds(geometry)
        // Limit to our time period
        .filterDate(startDate, endDate)
        // Use VV polarization (best for water detection)
        .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
        // Use Interferometric Wide swath mode (standard for flood monitoring)
        .filter(ee.Filter.eq('instrumentMode', 'IW'))
        // Select only the VV band
        .select('VV')
        // Create median composite (reduces noise from multiple images)
        .median()
        // Clip to our study area
        .clip(geometry);
}

// =============================================================================
// STEP 4: COMPARE BEFORE AND AFTER IMAGES
// =============================================================================
// Get radar images for both time periods
var preFlood = getS1(PRE_START, PRE_END);   // Normal conditions
var postFlood = getS1(POST_START, POST_END); // During/after flood

// Calculate the difference to see what changed
// Negative values = more water (water appears dark in radar)
var floodDifference = postFlood.subtract(preFlood).rename('floodChange');

// Create a composite image with all bands for analysis
var compositeImage = preFlood.rename('before_flood')
    .addBands(postFlood.rename('after_flood'))
    .addBands(floodDifference);

// =============================================================================
// STEP 5: VISUALIZE RESULTS
// =============================================================================
// Center the map on our study area
Map.centerObject(geometry, 9);

// Display the after-flood radar image
// Dark areas = water, bright areas = land
Map.addLayer(compositeImage, { 
    bands: ['after_flood'], 
    min: -25, 
    max: 0 
}, 'Radar Image (After Flood)');

// Display the flood change detection
// Blue = less water (normal), White = no change, Red = more water (flooded)
Map.addLayer(floodDifference, { 
    min: -10, 
    max: 2, 
    palette: ['#0066CC', '#FFFFFF', '#FF0000'] 
}, 'Flood Detection (Red = Flooded Areas)');

// =============================================================================
// OPTIONAL: EXPORT RESULTS
// =============================================================================
// Uncomment these lines to export data to your Google Drive
// Go to the "Tasks" tab in Earth Engine to start the exports

/*
// Export the flood detection map
Export.image.toDrive({
  image: floodDifference,
  description: 'flood_detection_map',
  scale: 10,  // 10-meter resolution (Sentinel-1 native)
  region: geometry,
  fileFormat: 'GeoTIFF'
});

// Export the composite image (before + after + difference)
Export.image.toDrive({
  image: compositeImage,
  description: 'sentinel1_composite',
  scale: 10,
  region: geometry,
  fileFormat: 'GeoTIFF'
});
*/

print('✅ Flood detection analysis complete!');
print('📍 Red areas in the map indicate potential flooding');
print('💾 Check the Tasks tab to export results if needed');

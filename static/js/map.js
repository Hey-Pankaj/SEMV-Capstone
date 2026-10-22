/**
 * वज्रSense (VajraSense) — Geospatial GIS Radar & Lightning Map Engine
 * Powered by Leaflet.js with custom radar reflectivity rendering,
 * storm trajectory vector arrows, uncertainty hazard cones, and lightning pulses.
 */

class VajraMapEngine {
    constructor(elementId) {
        this.elementId = elementId;
        this.map = null;
        this.baseTileLayer = null;
        this.currentTheme = document.documentElement.getAttribute('data-theme') || 'night';
        this.lastStation = null;
        this.lastCells = null;
        this.lastTimeMinutes = 0;
        this.radarLayerGroup = L.layerGroup();
        this.lightningLayerGroup = L.layerGroup();
        this.cellTrackerLayerGroup = L.layerGroup();
        this.stationLayerGroup = L.layerGroup();

        this.layerVisibility = {
            radar: true,
            lightning: true,
            tracking: true
        };

        this.initMap();
    }

    getTileUrl(theme) {
        const cartoKey = (window.VAJRA_CONFIG && window.VAJRA_CONFIG.cartoApiKey) || 'cb1_4qhk_1_857570c78f1776c27331ce8c';
        const variant = theme === 'day' ? 'light_all' : 'dark_all';
        return cartoKey
            ? `https://{s}.basemaps.cartocdn.com/rastertiles/${variant}/{z}/{x}/{y}{r}.png?key=${encodeURIComponent(cartoKey)}`
            : `https://{s}.basemaps.cartocdn.com/rastertiles/${variant}/{z}/{x}/{y}{r}.png`;
    }

    initMap() {
        this.map = L.map(this.elementId, {
            center: [19.0760, 72.8777],
            zoom: 8,
            minZoom: 5,
            maxZoom: 13,
            zoomControl: true,
            attributionControl: false
        });

        const tileUrl = this.getTileUrl(this.currentTheme);

        this.baseTileLayer = L.tileLayer(tileUrl, {
            subdomains: 'abcd',
            maxZoom: 19,
            attribution: '&copy; <a href="https://carto.com/">CARTO</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        }).addTo(this.map);

        this.radarLayerGroup.addTo(this.map);
        this.lightningLayerGroup.addTo(this.map);
        this.cellTrackerLayerGroup.addTo(this.map);
        this.stationLayerGroup.addTo(this.map);
    }

    setTheme(theme) {
        this.currentTheme = theme;
        if (this.baseTileLayer) {
            const tileUrl = this.getTileUrl(theme);
            this.baseTileLayer.setUrl(tileUrl);
        }
        if (this.lastStation) {
            this.renderStation(this.lastStation);
        }
        if (this.lastCells) {
            this.renderStormTracking(this.lastCells, this.lastTimeMinutes);
        }
    }

    setCenter(lat, lon, zoom = 8) {
        if (this.map) {
            this.map.flyTo([lat, lon], zoom, { duration: 1.2 });
        }
    }

    toggleLayer(layerName, isVisible) {
        this.layerVisibility[layerName] = isVisible;
        const groupMap = {
            radar: this.radarLayerGroup,
            lightning: this.lightningLayerGroup,
            tracking: this.cellTrackerLayerGroup
        };
        const grp = groupMap[layerName];
        if (grp) {
            if (isVisible) {
                if (!this.map.hasLayer(grp)) grp.addTo(this.map);
            } else {
                if (this.map.hasLayer(grp)) this.map.removeLayer(grp);
            }
        }
    }

    getDbzColor(dbz) {
        if (dbz >= 65) return '#ffffff';
        if (dbz >= 60) return '#ec4899';
        if (dbz >= 55) return '#ef4444';
        if (dbz >= 50) return '#f97316';
        if (dbz >= 45) return '#f59e0b';
        if (dbz >= 40) return '#eab308';
        if (dbz >= 35) return '#84cc16';
        if (dbz >= 30) return '#22c55e';
        if (dbz >= 25) return '#10b981';
        if (dbz >= 20) return '#06b6d4';
        if (dbz >= 15) return '#0284c7';
        return 'transparent';
    }

    renderRadarGrid(gridData) {
        this.radarLayerGroup.clearLayers();
        if (!gridData || !gridData.points) return;

        gridData.points.forEach(pt => {
            if (pt.dbz < 18) return;
            const color = this.getDbzColor(pt.dbz);
            const opacity = pt.dbz >= 45 ? 0.75 : 0.55;

            const circle = L.circle([pt.lat, pt.lon], {
                radius: 4200,
                color: 'transparent',
                fillColor: color,
                fillOpacity: opacity,
                interactive: false
            });
            this.radarLayerGroup.addLayer(circle);
        });
    }

    renderLightning(strikes) {
        this.lightningLayerGroup.clearLayers();
        if (!strikes || !strikes.length) return;

        strikes.forEach(s => {
            const isCG = s.type.startsWith('CG');
            const color = isCG ? '#facc15' : '#38bdf8';
            const iconHtml = `
                <div style="
                    width: 14px; height: 14px;
                    border-radius: 50%;
                    background: ${color};
                    box-shadow: 0 0 10px ${color}, 0 0 20px ${color};
                    border: 2px solid #ffffff;
                    animation: pulse-ring 1.4s infinite;
                "></div>
            `;
            const customIcon = L.divIcon({
                html: iconHtml,
                className: 'lightning-marker',
                iconSize: [14, 14],
                iconAnchor: [7, 7]
            });

            const marker = L.marker([s.lat, s.lon], { icon: customIcon });
            marker.bindPopup(`
                <div style="font-family: sans-serif; font-size: 12px; color: #0f172a;">
                    <strong style="color: #0284c7;">⚡ Lightning Stroke</strong><br>
                    <strong>ID:</strong> ${s.id}<br>
                    <strong>Type:</strong> ${s.type}<br>
                    <strong>Peak Current:</strong> ${s.peak_current_ka} kA<br>
                    <strong>Recorded:</strong> ${Math.round(s.age_secs / 60)} min ago
                </div>
            `);
            this.lightningLayerGroup.addLayer(marker);
        });
    }

    renderStormTracking(cells, timeMinutes) {
        this.lastCells = cells;
        this.lastTimeMinutes = timeMinutes;
        this.cellTrackerLayerGroup.clearLayers();
        if (!cells || !cells.length) return;

        const trajColor = this.currentTheme === 'day' ? '#0284c7' : '#38bdf8';
        const trajDotFill = this.currentTheme === 'day' ? '#0369a1' : '#0284c7';

        cells.forEach(cell => {
            const marker = L.circleMarker([cell.center_lat, cell.center_lon], {
                radius: 9,
                color: '#ef4444',
                weight: 3,
                fillColor: '#ffffff',
                fillOpacity: 0.95
            });
            marker.bindPopup(`
                <div style="font-family: sans-serif; font-size: 12px; color: #0f172a;">
                    <strong>🌀 Convective Cell: ${cell.id}</strong><br>
                    <strong>Reflectivity:</strong> ${cell.max_dbz} dBZ<br>
                    <strong>Motion:</strong> ${cell.speed_kmh} km/h @ ${cell.heading_deg}°<br>
                    <strong>VIL:</strong> ${cell.vil} kg/m²<br>
                    <strong>Lead Time:</strong> +${timeMinutes} min
                </div>
            `);
            this.cellTrackerLayerGroup.addLayer(marker);

            if (cell.uncertainty_radius_km) {
                const uncertaintyCircle = L.circle([cell.center_lat, cell.center_lon], {
                    radius: cell.uncertainty_radius_km * 1000,
                    color: '#f97316',
                    dashArray: '6, 6',
                    weight: 2,
                    fillColor: '#f97316',
                    fillOpacity: 0.12
                });
                this.cellTrackerLayerGroup.addLayer(uncertaintyCircle);
            }

            if (cell.trajectory && cell.trajectory.length > 1) {
                const latlngs = cell.trajectory.map(p => [p.lat, p.lon]);
                const polyline = L.polyline(latlngs, {
                    color: trajColor,
                    weight: 3,
                    dashArray: '4, 4',
                    opacity: 0.85
                });
                this.cellTrackerLayerGroup.addLayer(polyline);

                [2, 4, 6].forEach(idx => {
                    if (cell.trajectory[idx]) {
                        const pt = cell.trajectory[idx];
                        const dot = L.circleMarker([pt.lat, pt.lon], {
                            radius: 4,
                            color: trajColor,
                            fillColor: trajDotFill,
                            fillOpacity: 1.0
                        });
                        this.cellTrackerLayerGroup.addLayer(dot);
                    }
                });
            }
        });
    }

    renderStation(station) {
        this.lastStation = station;
        this.stationLayerGroup.clearLayers();
        if (!station) return;

        const stationIcon = L.divIcon({
            html: `
                <div style="
                    width: 22px; height: 22px;
                    border-radius: 50%;
                    background: #0284c7;
                    border: 2px solid #ffffff;
                    display: flex; align-items: center; justify-content: center;
                    color: white; font-size: 11px; font-weight: bold;
                    box-shadow: 0 0 10px rgba(2, 132, 199, 0.8);
                ">📡</div>
            `,
            className: 'station-marker',
            iconSize: [22, 22],
            iconAnchor: [11, 11]
        });

        const stMarker = L.marker([station.lat, station.lon], { icon: stationIcon });
        stMarker.bindPopup(`
            <div style="font-family: sans-serif; font-size: 12px; color: #0f172a;">
                <strong>Doppler Radar Station</strong><br>
                <strong>Name:</strong> ${station.name}<br>
                <strong>Surveillance Range:</strong> ${station.radar_range_km} km<br>
                <strong>Elevation:</strong> ${station.elevation_m} m
            </div>
        `);
        this.stationLayerGroup.addLayer(stMarker);

        const ringColor = this.currentTheme === 'day' ? 'rgba(2, 132, 199, 0.45)' : 'rgba(56, 189, 248, 0.35)';
        const rangeRing = L.circle([station.lat, station.lon], {
            radius: station.radar_range_km * 1000,
            color: ringColor,
            weight: 1.5,
            dashArray: '3, 6',
            fillColor: 'transparent',
            interactive: false
        });
        this.stationLayerGroup.addLayer(rangeRing);
    }
}

window.VajraMapEngine = VajraMapEngine;

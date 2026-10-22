/**
 * वज्रSense (VajraSense) — Frontend Application Controller
 * Coordinates API requests, UI updates, time horizon scrubbing,
 * audio warning alerts, and analytical modals.
 */

document.addEventListener('DOMContentLoaded', () => {
    const state = {
        scenarioId: 'mumbai_severe',
        stationKey: 'VABB_MUMBAI',
        currentMinutes: 0,
        isPlaying: false,
        playInterval: null,
        audioAlertsEnabled: false,
        cachedEvaluation: null,
        mapEngine: null
    };

    state.mapEngine = new VajraMapEngine('map-view');

    const scenarioSelect = document.getElementById('scenario-select');
    const stationSelect = document.getElementById('station-select');
    const timelineSlider = document.getElementById('timeline-slider');
    const playBtn = document.getElementById('play-btn');
    const audioToggleBtn = document.getElementById('audio-toggle-btn');
    const evalModalBtn = document.getElementById('eval-modal-btn');
    const fuzzyModalBtn = document.getElementById('fuzzy-modal-btn');
    const themeBtnDay = document.getElementById('theme-btn-day');
    const themeBtnNight = document.getElementById('theme-btn-night');
    const notifBtn = document.getElementById('notif-btn');
    const notifModal = document.getElementById('notif-modal');
    const notifBadge = document.getElementById('notif-badge');
    const clearNotifsBtn = document.getElementById('clear-notifs-btn');
    const settingsBtn = document.getElementById('settings-btn');
    const settingsModal = document.getElementById('settings-modal');
    const landingScreen = document.getElementById('landing-screen');
    const dashboardView = document.getElementById('dashboard-view');
    const exploreDashboardBtn = document.getElementById('explore-dashboard-btn');
    const brandHomeBtn = document.getElementById('brand-home-btn') || document.querySelector('.brand-section');

    // ==========================================
    // Theme Management (Night & Day Modes)
    // ==========================================
    function applyTheme(theme, persist = true) {
        document.documentElement.setAttribute('data-theme', theme);
        document.body.classList.remove('theme-day', 'theme-night');
        document.body.classList.add(`theme-${theme}`);

        const isDay = theme === 'day';
        if (themeBtnDay) {
            themeBtnDay.classList.toggle('active', isDay);
            themeBtnDay.setAttribute('aria-checked', isDay ? 'true' : 'false');
        }
        if (themeBtnNight) {
            themeBtnNight.classList.toggle('active', !isDay);
            themeBtnNight.setAttribute('aria-checked', !isDay ? 'true' : 'false');
        }

        if (state.mapEngine) {
            state.mapEngine.setTheme(theme);
        }

        const metaThemeColor = document.getElementById('meta-theme-color');
        if (metaThemeColor) {
            metaThemeColor.setAttribute('content', isDay ? '#f0f4f9' : '#0a0e17');
        }

        if (persist) {
            try {
                localStorage.setItem('vajrasense_theme', theme);
            } catch (err) {
                console.warn('Could not save theme to localStorage:', err);
            }
        }
    }

    if (themeBtnDay) {
        themeBtnDay.addEventListener('click', () => applyTheme('day'));
    }
    if (themeBtnNight) {
        themeBtnNight.addEventListener('click', () => applyTheme('night'));
    }

    // Initialize with stored or default theme
    const initialTheme = localStorage.getItem('vajrasense_theme') || 'night';
    applyTheme(initialTheme, false);

    const evalModal = document.getElementById('eval-modal');
    const fuzzyModal = document.getElementById('fuzzy-modal');
    const closeButtons = document.querySelectorAll('.modal-close');

    const layerButtons = document.querySelectorAll('.layer-btn');
    layerButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const layer = btn.getAttribute('data-layer');
            const isActive = btn.classList.toggle('active');
            state.mapEngine.toggleLayer(layer, isActive);
        });
    });

    const stepButtons = document.querySelectorAll('.timeline-step-btn');
    stepButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const mins = parseInt(btn.getAttribute('data-min'));
            setTimelineStep(mins);
        });
    });

    function setTimelineStep(mins) {
        state.currentMinutes = mins;
        timelineSlider.value = mins;
        
        stepButtons.forEach(b => {
            if (parseInt(b.getAttribute('data-min')) === mins) {
                b.classList.add('active');
            } else {
                b.classList.remove('active');
            }
        });

        loadNowcastData();
    }

    timelineSlider.addEventListener('input', (e) => {
        const val = parseInt(e.target.value);
        const horizons = [0, 30, 60, 120];
        const closest = horizons.reduce((prev, curr) => Math.abs(curr - val) < Math.abs(prev - val) ? curr : prev);
        setTimelineStep(closest);
    });

    playBtn.addEventListener('click', () => {
        if (state.isPlaying) {
            pauseAnimation();
        } else {
            startAnimation();
        }
    });

    function startAnimation() {
        state.isPlaying = true;
        playBtn.innerHTML = '⏸';
        playBtn.title = 'Pause Playback';

        const steps = [0, 30, 60, 120];
        let idx = steps.indexOf(state.currentMinutes);

        state.playInterval = setInterval(() => {
            idx = (idx + 1) % steps.length;
            setTimelineStep(steps[idx]);
        }, 2400);
    }

    function pauseAnimation() {
        state.isPlaying = false;
        playBtn.innerHTML = '▶';
        playBtn.title = 'Play 0–2h Projection Animation';
        if (state.playInterval) {
            clearInterval(state.playInterval);
            state.playInterval = null;
        }
    }

    function playWarningChime(severity) {
        if (!state.audioAlertsEnabled) return;
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();

            osc.type = severity === 'Severe' ? 'sawtooth' : 'sine';
            osc.frequency.setValueAtTime(severity === 'Severe' ? 880 : 587, ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(severity === 'Severe' ? 440 : 293, ctx.currentTime + 0.4);

            gain.gain.setValueAtTime(0.2, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.5);

            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.5);
        } catch (e) {
            console.error('Audio chime error:', e);
        }
    }

    if (audioToggleBtn) {
        audioToggleBtn.addEventListener('click', () => {
            state.audioAlertsEnabled = !state.audioAlertsEnabled;
            const icon = document.getElementById('audio-btn-icon');
            const label = document.getElementById('audio-btn-label');
            if (icon) icon.textContent = state.audioAlertsEnabled ? '🔊' : '🔇';
            if (label) label.textContent = state.audioAlertsEnabled ? 'Audio Alerts: ON' : 'Audio Alerts: OFF';
            audioToggleBtn.classList.toggle('active', state.audioAlertsEnabled);
            if (state.audioAlertsEnabled) {
                playWarningChime('Moderate');
            }
        });
    }

    if (notifBtn && notifModal) {
        notifBtn.addEventListener('click', () => {
            notifModal.classList.add('active');
        });
    }

    if (settingsBtn && settingsModal) {
        settingsBtn.addEventListener('click', () => {
            settingsModal.classList.add('active');
        });
    }

    if (clearNotifsBtn) {
        clearNotifsBtn.addEventListener('click', () => {
            if (notifBadge) notifBadge.style.display = 'none';
            document.querySelectorAll('.notif-card').forEach(c => c.style.opacity = '0.5');
            clearNotifsBtn.textContent = 'All Read';
            clearNotifsBtn.disabled = true;
        });
    }

    const layerChips = document.querySelectorAll('.layer-toggle-chip');
    layerChips.forEach(chip => {
        chip.addEventListener('click', () => {
            const layer = chip.getAttribute('data-layer');
            const isActive = chip.classList.toggle('active');
            if (state.mapEngine) {
                state.mapEngine.toggleLayer(layer, isActive);
            }
        });
    });

    if (scenarioSelect) {
        scenarioSelect.addEventListener('change', (e) => {
            state.scenarioId = e.target.value;
            state.stationKey = ''; // Allow server to load scenario's primary station
            loadNowcastData(true);
        });
    }

    if (stationSelect) {
        stationSelect.addEventListener('change', (e) => {
            state.stationKey = e.target.value;
            loadNowcastData(true);
        });
    }

    async function loadNowcastData(recenterMap = false) {
        try {
            const stationParam = state.stationKey ? `&station=${state.stationKey}` : '';
            const url = `/api/nowcast?scenario=${state.scenarioId}${stationParam}&minutes=${state.currentMinutes}`;
            const res = await fetch(url);
            const data = await res.json();

            if (data.status !== 'success') return;

            if (data.station_key) {
                state.stationKey = data.station_key;
                if (stationSelect) stationSelect.value = data.station_key;
            }

            if (data.station) {
                state.mapEngine.renderStation(data.station);
                if (recenterMap) {
                    state.mapEngine.setCenter(data.station.lat, data.station.lon, 8);
                }
            }

            state.mapEngine.renderRadarGrid(data.radar_grid);
            state.mapEngine.renderLightning(data.lightning_strikes);
            state.mapEngine.renderStormTracking(data.cells, data.time_minutes);

            updateTelemetryCards(data);

            if (data.fuzzy_risk && data.fuzzy_risk.category === 'Severe' && state.currentMinutes === 0) {
                playWarningChime('Severe');
            }
        } catch (err) {
            console.error('Error fetching nowcast data:', err);
        }
    }

    function updateTelemetryCards(data) {
        const fuzzy = data.fuzzy_risk;
        const ml = data.ml_risk;
        const env = data.environmental_params;

        const riskBadge = document.getElementById('primary-risk-badge');
        const alertCodeLabel = document.getElementById('alert-code-label');
        if (riskBadge && fuzzy) {
            riskBadge.textContent = fuzzy.category;
            riskBadge.className = `risk-badge ${fuzzy.category.toLowerCase()}`;
            if (alertCodeLabel) alertCodeLabel.textContent = fuzzy.alert_code.replace('_', ' ');
        }

        const lightningScoreVal = document.getElementById('lightning-score-val');
        const lightningFill = document.getElementById('lightning-progress-fill');
        if (lightningScoreVal && fuzzy) {
            lightningScoreVal.textContent = fuzzy.score;
            if (lightningFill) {
                lightningFill.style.width = `${fuzzy.score}%`;
                lightningFill.style.backgroundColor = fuzzy.color;
            }
        }

        const mlClassVal = document.getElementById('ml-class-val');
        const mlConfidenceFill = document.getElementById('ml-confidence-fill');
        if (mlClassVal && ml) {
            mlClassVal.textContent = ml.predicted_class;
            const topProb = Math.round(ml.probabilities[ml.predicted_class] * 100);
            if (mlConfidenceFill) {
                mlConfidenceFill.style.width = `${topProb}%`;
                mlConfidenceFill.style.backgroundColor = topProb > 70 ? '#38bdf8' : '#eab308';
            }
        }

        const setVal = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.textContent = val;
        };

        if (env) {
            setVal('tel-cape', `${Math.round(env.cape_j_kg)} J/kg`);
            setVal('tel-dbz', `${env.max_dbz} dBZ`);
            setVal('tel-vil', `${env.vil} kg/m²`);
            setVal('tel-shear', `${env.shear_0_6km_ms} m/s`);
            setVal('tel-flashes', `${env.flash_rate} /min`);
            setVal('tel-pw', `${env.precipitable_water_mm} mm`);
        }

        const horizonList = document.getElementById('horizon-list-container');
        if (horizonList && data.horizons) {
            horizonList.innerHTML = '';
            data.horizons.forEach(h => {
                const card = document.createElement('div');
                card.className = 'horizon-card';
                card.innerHTML = `
                    <div>
                        <div class="h-name">${h.label}</div>
                        <div class="h-desc">${h.description} • Confidence: ${h.confidence_pct}%</div>
                    </div>
                    <div class="h-stat">
                        <span class="h-badge" style="background: ${h.risk_color}22; color: ${h.risk_color}; border: 1px solid ${h.risk_color};">
                            ${h.risk_category} (${h.risk_score})
                        </span>
                        <div style="font-size: 0.68rem; color: #94a3b8; margin-top: 3px;">Max ${h.projected_max_dbz} dBZ</div>
                    </div>
                `;
                horizonList.appendChild(card);
            });
        }

        const ruleExplainer = document.getElementById('fuzzy-active-rule');
        if (ruleExplainer && fuzzy.active_rules && fuzzy.active_rules.length > 0) {
            const topRule = fuzzy.active_rules[0];
            ruleExplainer.innerHTML = `<strong>Rule ${topRule.id} fired:</strong> IF ${topRule.rule} &rarr; <em>${topRule.consequent}</em> (Weight: ${(topRule.weight * 100).toFixed(0)}%)`;
        }
    }

    if (evalModalBtn && evalModal) {
        evalModalBtn.addEventListener('click', async () => {
            evalModal.classList.add('active');
            if (!state.cachedEvaluation) {
                const res = await fetch('/api/evaluation');
                const resData = await res.json();
                if (resData.status === 'success') {
                    state.cachedEvaluation = resData.data;
                    renderEvaluationTable(state.cachedEvaluation);
                }
            }
        });
    }

    if (fuzzyModalBtn && fuzzyModal) {
        fuzzyModalBtn.addEventListener('click', () => {
            fuzzyModal.classList.add('active');
            runFuzzySimulator();
        });
    }

    function resetNavToDashboardIfActive() {
        if (dashboardView && dashboardView.style.display !== 'none') {
            setActiveNav('dashboard');
        }
    }

    closeButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            if (evalModal) evalModal.classList.remove('active');
            if (fuzzyModal) fuzzyModal.classList.remove('active');
            if (notifModal) notifModal.classList.remove('active');
            if (settingsModal) settingsModal.classList.remove('active');
            resetNavToDashboardIfActive();
        });
    });

    window.addEventListener('click', (e) => {
        if (e.target === evalModal) { evalModal.classList.remove('active'); resetNavToDashboardIfActive(); }
        if (e.target === fuzzyModal) { fuzzyModal.classList.remove('active'); resetNavToDashboardIfActive(); }
        if (notifModal && e.target === notifModal) { notifModal.classList.remove('active'); }
        if (settingsModal && e.target === settingsModal) { settingsModal.classList.remove('active'); }
    });

    window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (evalModal) evalModal.classList.remove('active');
            if (fuzzyModal) fuzzyModal.classList.remove('active');
            if (notifModal) notifModal.classList.remove('active');
            if (settingsModal) settingsModal.classList.remove('active');
            resetNavToDashboardIfActive();
        }
    });

    // ==========================================
    // Landing Page & Dashboard Screen Transitions
    // ==========================================
    function showDashboard(targetNav = 'dashboard') {
        if (landingScreen) landingScreen.style.display = 'none';
        if (dashboardView) dashboardView.style.display = 'grid';
        if (targetNav) setActiveNav(targetNav);

        // Invalidate map size so Leaflet recalculates dimensions now that container is visible
        if (state.mapEngine && state.mapEngine.map) {
            state.mapEngine.map.invalidateSize();
            setTimeout(() => {
                if (state.mapEngine && state.mapEngine.map) {
                    state.mapEngine.map.invalidateSize();
                }
            }, 80);
        }
    }

    function showLanding() {
        if (dashboardView) dashboardView.style.display = 'none';
        if (landingScreen) landingScreen.style.display = 'flex';
        // Clear active class from navbar items when on landing overview
        navItems.forEach(item => {
            item.classList.remove('active');
            item.removeAttribute('aria-current');
        });
        // Close any open modals
        if (evalModal) evalModal.classList.remove('active');
        if (fuzzyModal) fuzzyModal.classList.remove('active');
        if (notifModal) notifModal.classList.remove('active');
        if (settingsModal) settingsModal.classList.remove('active');
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    if (exploreDashboardBtn) {
        exploreDashboardBtn.addEventListener('click', () => {
            showDashboard('dashboard');
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }

    if (brandHomeBtn) {
        brandHomeBtn.addEventListener('click', () => {
            showLanding();
        });
        brandHomeBtn.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                showLanding();
            }
        });
    }

    // ==========================================
    // Minimal Professional Navbar Navigation
    // ==========================================
    const navItems = document.querySelectorAll('.nav-item');
    function setActiveNav(navKey) {
        navItems.forEach(item => {
            const isMatch = item.getAttribute('data-nav') === navKey;
            item.classList.toggle('active', isMatch);
            if (isMatch) {
                item.setAttribute('aria-current', 'page');
            } else {
                item.removeAttribute('aria-current');
            }
        });
    }

    navItems.forEach(item => {
        item.addEventListener('click', async () => {
            const navKey = item.getAttribute('data-nav');

            // If landing page is currently visible, reveal the operational dashboard
            if (dashboardView && dashboardView.style.display === 'none') {
                showDashboard(navKey);
            }

            if (navKey !== 'evaluation' && evalModal) evalModal.classList.remove('active');
            if (navKey !== 'model' && fuzzyModal) fuzzyModal.classList.remove('active');

            if (navKey === 'dashboard') {
                setActiveNav('dashboard');
                window.scrollTo({ top: 0, behavior: 'smooth' });
                const mapView = document.getElementById('map-view');
                if (mapView && state.mapEngine && state.mapEngine.map) {
                    state.mapEngine.map.invalidateSize();
                }
            } else if (navKey === 'weather') {
                setActiveNav('weather');
                const sidebar = document.querySelector('.sidebar-panel');
                if (sidebar) {
                    sidebar.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    const riskCard = document.querySelector('.primary-risk-card');
                    if (riskCard) {
                        riskCard.style.boxShadow = '0 0 20px var(--primary-accent)';
                        setTimeout(() => { riskCard.style.boxShadow = ''; }, 1200);
                    }
                }
            } else if (navKey === 'model') {
                setActiveNav('model');
                if (fuzzyModal) {
                    fuzzyModal.classList.add('active');
                    runFuzzySimulator();
                }
            } else if (navKey === 'evaluation') {
                setActiveNav('evaluation');
                if (evalModal) {
                    evalModal.classList.add('active');
                    if (!state.cachedEvaluation) {
                        const res = await fetch('/api/evaluation');
                        const resData = await res.json();
                        if (resData.status === 'success') {
                            state.cachedEvaluation = resData.data;
                            renderEvaluationTable(state.cachedEvaluation);
                        }
                    }
                }
            }
        });
    });

    function renderEvaluationTable(data) {
        const tableBody = document.getElementById('eval-table-body');
        if (!tableBody || !data.horizons) return;

        tableBody.innerHTML = '';
        Object.keys(data.horizons).forEach(k => {
            const h = data.horizons[k];
            const v = h.vajra;
            const b = h.persistence_baseline;

            const row = document.createElement('tr');
            row.innerHTML = `
                <td><strong>${h.label}</strong></td>
                <td><span style="color:#22c55e; font-weight:700;">${v.pod}</span> <small style="color:#94a3b8;">(vs ${b.pod})</small></td>
                <td><span style="color:#38bdf8; font-weight:700;">${v.far}</span> <small style="color:#94a3b8;">(vs ${b.far})</small></td>
                <td><span style="color:#facc15; font-weight:700;">${v.csi}</span> <small style="color:#94a3b8;">(vs ${b.csi})</small></td>
                <td><span style="color:#a855f7; font-weight:700;">${v.hss}</span></td>
                <td><span style="color:#4ade80; font-weight:700;">+${h.csi_improvement_pct}%</span></td>
            `;
            tableBody.appendChild(row);
        });
    }

    const simCape = document.getElementById('sim-cape');
    const simDbz = document.getElementById('sim-dbz');
    const simFlash = document.getElementById('sim-flash');
    const simShear = document.getElementById('sim-shear');

    [simCape, simDbz, simFlash, simShear].forEach(slider => {
        if (slider) {
            slider.addEventListener('input', runFuzzySimulator);
        }
    });

    async function runFuzzySimulator() {
        if (!simCape) return;
        const cape = simCape.value;
        const dbz = simDbz.value;
        const flash = simFlash.value;
        const shear = simShear.value;

        document.getElementById('sim-cape-val').textContent = `${cape} J/kg`;
        document.getElementById('sim-dbz-val').textContent = `${dbz} dBZ`;
        document.getElementById('sim-flash-val').textContent = `${flash} /min`;
        document.getElementById('sim-shear-val').textContent = `${shear} m/s`;

        try {
            const res = await fetch(`/api/fuzzy-explain?cape=${cape}&dbz=${dbz}&flash=${flash}&shear=${shear}`);
            const data = await res.json();
            if (data.status === 'success') {
                const r = data.result;
                const scoreBadge = document.getElementById('sim-result-score');
                if (scoreBadge) {
                    scoreBadge.textContent = `${r.score} — ${r.category}`;
                    scoreBadge.style.color = r.color;
                    scoreBadge.style.borderColor = r.color;
                }

                const rulesContainer = document.getElementById('sim-rules-container');
                if (rulesContainer && r.active_rules) {
                    rulesContainer.innerHTML = r.active_rules.map(rl => `
                        <div style="background: var(--bg-inset); padding: 8px 12px; border-radius: 6px; margin-bottom: 6px; border: 1px solid var(--border-subtle); color: var(--text-secondary);">
                            <strong style="color: var(--text-primary);">Rule ${rl.id}:</strong> IF ${rl.rule} &rarr; <span style="color: var(--lightning-gold); font-weight: 600;">${rl.consequent}</span> (Firing Degree: ${(rl.weight * 100).toFixed(0)}%)
                        </div>
                    `).join('');
                }
            }
        } catch (e) {
            console.error('Simulator error:', e);
        }
    }

    loadNowcastData(true);
});

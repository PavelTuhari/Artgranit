/**
 * ScaleKiosk — Universal full-screen scale modal for AGRO modules.
 * Instantiated by agro_field.html (purchase) and agro_sales.html (sale).
 *
 * Usage:
 *   var kiosk = new ScaleKiosk({ mode: 'purchase', ... });
 *   kiosk.open(lineId);
 */
(function() {
'use strict';

var EMOJI_MAP = {
    APPLE:'🍎', PEAR:'🍐', PEACH:'🍑', PLUM:'🟣', CHERRY:'🍒',
    GRAPE:'🍇', APRICOT:'🟠', WALNUT:'🌰', TOMATO:'🍅', PEPPER:'🌶️'
};

function ScaleKiosk(config) {
    this.mode = config.mode || 'purchase';
    this.title = config.title || '⚖️ Весы / Cântar';
    this.products = config.products || [];
    this.weightRange = config.weightRange || {min: 50, max: 500};
    this.showPassport = config.showPassport !== undefined ? config.showPassport : false;
    this.showEmulator = config.showEmulator !== undefined ? config.showEmulator : false;
    this.onCapture = config.onCapture || function() {};
    this.toastFn = config.toastFn || function() {};
    this.scaleId = config.scaleId || 'default';
    this.emulationInterval = config.emulationInterval || 20000;
    this.loadDriverConfig = config.loadDriverConfig !== undefined ? config.loadDriverConfig : true;

    // Internal state
    this._targetLineId = null;
    this._pollTimer = null;
    this._emuTimer = null;
    this._paused = false;
    this._selectedProduct = null;
    this._selectedVariety = null;
    this._manualWeight = false;
    this._container = null;
    this._id = 'sk_' + this.mode;

    // Build product maps
    this._productNames = {};
    this._productImages = {};
    this._productKeys = [];
    for (var i = 0; i < this.products.length; i++) {
        var p = this.products[i];
        this._productKeys.push(p.key);
        this._productNames[p.key] = p.name;
        this._productImages[p.key] = p.svgPath || '';
    }

    this._renderModal();
    this._bindEvents();
}

// ---- DOM helpers ----
ScaleKiosk.prototype.$ = function(suffix) {
    return this._container ? this._container.querySelector('[data-sk="' + suffix + '"]') : null;
};

ScaleKiosk.prototype.$$ = function(suffix) {
    return this._container ? this._container.querySelectorAll('[data-sk="' + suffix + '"]') : [];
};

// ---- Render ----
ScaleKiosk.prototype._renderModal = function() {
    var div = document.createElement('div');
    div.className = 'scale-kiosk-overlay';
    div.style.display = 'none';
    div.id = this._id + '_overlay';

    var passportHtml = '';
    if (this.showPassport) {
        passportHtml =
            '<div class="sk-passport" data-sk="passport" style="display:none;">' +
            '  <div class="sk-passport-header">' +
            '    <span class="sk-passport-product-name" data-sk="passportName">—</span>' +
            '    <span class="sk-passport-badge">Паспорт / Pasaport</span>' +
            '  </div>' +
            '  <div class="sk-passport-section">' +
            '    <div class="sk-passport-label">Сорт / Soi</div>' +
            '    <div class="sk-variety-grid" data-sk="varietyGrid"></div>' +
            '  </div>' +
            '  <div class="sk-passport-all">' +
            '    <div class="sk-field-row">' +
            '      <div class="sk-field"><label>Калибр, мм / Calibru</label>' +
            '        <div class="sk-stepper">' +
            '          <button class="sk-step-btn" data-step="ppCalibr" data-delta="-1">−</button>' +
            '          <input type="number" data-sk="ppCalibr" class="sk-step-input" placeholder="—" step="1" min="0">' +
            '          <button class="sk-step-btn" data-step="ppCalibr" data-delta="1">+</button>' +
            '        </div><div class="sk-field-ref" data-sk="ppCalibrRef"></div></div>' +
            '      <div class="sk-field"><label>Brix, °</label>' +
            '        <div class="sk-stepper">' +
            '          <button class="sk-step-btn" data-step="ppBrix" data-delta="-0.5">−</button>' +
            '          <input type="number" data-sk="ppBrix" class="sk-step-input" placeholder="—" step="0.5" min="0">' +
            '          <button class="sk-step-btn" data-step="ppBrix" data-delta="0.5">+</button>' +
            '        </div><div class="sk-field-ref" data-sk="ppBrixRef"></div></div>' +
            '    </div>' +
            '    <div class="sk-field-row" data-sk="ppColorRow">' +
            '      <div class="sk-field" style="flex:1;"><label>Окраска, % / Colorare</label>' +
            '        <input type="range" data-sk="ppColorSlider" min="0" max="100" value="50" class="sk-slider">' +
            '        <div style="display:flex;justify-content:space-between;font-size:11px;color:#6c6c8a;">' +
            '          <span>0%</span><span data-sk="ppColorVal" style="color:#53d769;font-weight:700;">50%</span><span>100%</span>' +
            '        </div><div class="sk-field-ref" data-sk="ppColorRef"></div></div>' +
            '    </div>' +
            '    <div class="sk-field-row">' +
            '      <div class="sk-field"><label>t °C / Temperatura</label>' +
            '        <div class="sk-stepper">' +
            '          <button class="sk-step-btn" data-step="ppTemp" data-delta="-0.5">−</button>' +
            '          <input type="number" data-sk="ppTemp" class="sk-step-input" placeholder="—" step="0.5">' +
            '          <button class="sk-step-btn" data-step="ppTemp" data-delta="0.5">+</button>' +
            '        </div><div class="sk-field-ref" data-sk="ppTempRef"></div></div>' +
            '      <div class="sk-field"><label>Свежесть / Prospetime</label>' +
            '        <div class="sk-rating" data-sk="ppFreshness">' +
            '          <button class="sk-rate-btn" data-rate="1">1</button>' +
            '          <button class="sk-rate-btn" data-rate="2">2</button>' +
            '          <button class="sk-rate-btn" data-rate="3">3</button>' +
            '          <button class="sk-rate-btn active" data-rate="4">4</button>' +
            '          <button class="sk-rate-btn" data-rate="5">5</button>' +
            '        </div></div>' +
            '    </div>' +
            '    <div class="sk-field-row">' +
            '      <div class="sk-field"><label>Срок хран. / Termen</label>' +
            '        <div class="sk-step-input-ro" data-sk="ppShelfLife">—</div></div>' +
            '      <div class="sk-field"><label>Дефекты / Defecte</label>' +
            '        <div class="sk-btn-group" data-sk="ppDefects" data-value="none">' +
            '          <button class="sk-opt-btn active" data-opt="none">Нет</button>' +
            '          <button class="sk-opt-btn" data-opt="minor">Мин.</button>' +
            '          <button class="sk-opt-btn" data-opt="serious">Серьёз.</button>' +
            '        </div></div>' +
            '    </div>' +
            '    <div class="sk-field-row" data-sk="ppDefectPctRow" style="display:none;">' +
            '      <div class="sk-field" style="flex:1;"><label>% дефектных / % defecte</label>' +
            '        <div class="sk-stepper">' +
            '          <button class="sk-step-btn" data-step="ppDefectPct" data-delta="-1">−</button>' +
            '          <input type="number" data-sk="ppDefectPct" class="sk-step-input" value="0" step="1" min="0" max="100">' +
            '          <button class="sk-step-btn" data-step="ppDefectPct" data-delta="1">+</button>' +
            '        </div></div>' +
            '    </div>' +
            '    <div class="sk-field-row">' +
            '      <div class="sk-field"><label>Упаковка / Ambalaj</label>' +
            '        <div class="sk-btn-group" data-sk="ppPackaging" data-value="ok">' +
            '          <button class="sk-opt-btn active" data-opt="ok">✓ OK</button>' +
            '          <button class="sk-opt-btn" data-opt="damaged">Поврежд.</button>' +
            '          <button class="sk-opt-btn" data-opt="missing">Нет</button>' +
            '        </div></div>' +
            '      <div class="sk-field"><label>Маркировка / Etichetare</label>' +
            '        <div class="sk-btn-group" data-sk="ppLabel" data-value="ok">' +
            '          <button class="sk-opt-btn active" data-opt="ok">✓ OK</button>' +
            '          <button class="sk-opt-btn" data-opt="partial">Частичн.</button>' +
            '          <button class="sk-opt-btn" data-opt="missing">Нет</button>' +
            '        </div></div>' +
            '    </div>' +
            '    <div class="sk-field-row">' +
            '      <div class="sk-field" style="flex:1;"><label>Заметки / Note</label>' +
            '        <textarea data-sk="ppNotes" rows="2" class="sk-textarea" placeholder="Комментарий..."></textarea></div>' +
            '    </div>' +
            '  </div>' +
            '</div>';
    }

    var emulatorHtml = '';
    if (this.showEmulator) {
        emulatorHtml =
            '<div class="sk-emulator">' +
            '  <div class="sk-emulator-title">Эмулятор / Emulator</div>' +
            '  <div class="sk-emu-btns">' +
            '    <input type="number" data-sk="emuWeight" placeholder="кг" step="0.1" min="0" class="sk-emu-input">' +
            '    <button data-sk="emuSet" class="sk-btn">Set</button>' +
            '    <button data-sk="emuRandom" class="sk-btn">Random</button>' +
            '    <button data-sk="emuRemove" class="sk-btn">Remove</button>' +
            '  </div>' +
            '</div>';
    }

    div.innerHTML =
        '<div class="scale-kiosk">' +
        '  <div class="sk-header">' +
        '    <div class="sk-title" data-sk="title">' + this.title + '</div>' +
        '    <div class="sk-status">' +
        '      <span class="sk-indicator" data-sk="indicator"></span>' +
        '      <span data-sk="statusText">Idle</span>' +
        '    </div>' +
        '    <div class="sk-driver-info" data-sk="driverInfo">' +
        '      <span>Driver: <b>Emulator</b></span>' +
        '      <span>Max: <b>600 kg</b></span>' +
        '    </div>' +
        '    <button class="sk-pause-btn" data-sk="pauseBtn">⏸ Пауза / Pauză</button>' +
        '    <button class="sk-close" data-sk="closeBtn">&times;</button>' +
        '  </div>' +
        '  <div class="sk-body">' +
        '    <div class="sk-products">' +
        '      <div class="sk-products-title">Продукция / Produse</div>' +
        '      <div class="sk-product-grid" data-sk="productGrid"></div>' +
        passportHtml +
        '    </div>' +
        '    <div class="sk-scale">' +
        '      <div class="sk-weight-display">' +
        '        <div class="sk-weight-gross" data-sk="gross">0.000</div>' +
        '        <div class="sk-weight-unit">kg</div>' +
        '      </div>' +
        '      <div class="sk-weight-sub">' +
        '        <div class="sk-sub-item"><span class="sk-sub-label">Tare / Тара</span>' +
        '          <span class="sk-sub-val" data-sk="tare">0.000</span></div>' +
        '        <div class="sk-sub-item"><span class="sk-sub-label">Net / Нетто</span>' +
        '          <span class="sk-sub-val sk-net" data-sk="net">0.000</span></div>' +
        '      </div>' +
        '      <div class="sk-scale-btns">' +
        '        <button class="sk-btn sk-btn-zero" data-sk="zeroBtn">Zero</button>' +
        '        <button class="sk-btn sk-btn-tare" data-sk="tareBtn">Tare</button>' +
        '      </div>' +
        '      <div class="sk-numpad">' +
        '        <div class="sk-numpad-title">Ручной ввод / Introducere manuală</div>' +
        '        <input type="text" class="sk-numpad-input" data-sk="numpadInput" placeholder="0.00" readonly>' +
        '        <div class="sk-numpad-grid">' +
        '          <button class="sk-numpad-btn" data-num="7">7</button>' +
        '          <button class="sk-numpad-btn" data-num="8">8</button>' +
        '          <button class="sk-numpad-btn" data-num="9">9</button>' +
        '          <button class="sk-numpad-btn" data-num="4">4</button>' +
        '          <button class="sk-numpad-btn" data-num="5">5</button>' +
        '          <button class="sk-numpad-btn" data-num="6">6</button>' +
        '          <button class="sk-numpad-btn" data-num="1">1</button>' +
        '          <button class="sk-numpad-btn" data-num="2">2</button>' +
        '          <button class="sk-numpad-btn" data-num="3">3</button>' +
        '          <button class="sk-numpad-btn" data-num="0">0</button>' +
        '          <button class="sk-numpad-btn" data-num=".">.</button>' +
        '          <button class="sk-numpad-btn sk-numpad-del" data-num="del">⌫</button>' +
        '        </div>' +
        '        <button class="sk-numpad-apply" data-sk="numpadApply">Применить вес / Aplică</button>' +
        '      </div>' +
        '      <button class="sk-capture-btn" data-sk="captureBtn" disabled>' +
        '        ⚖️ Снять вес / Cântărește' +
        '      </button>' +
        '    </div>' +
        '    <div class="sk-camera">' +
        '      <div class="sk-camera-header">' +
        '        <span>📷 AI Camera</span>' +
        '        <span class="ai-badge">AI</span>' +
        '      </div>' +
        '      <div class="sk-camera-viewport" data-sk="viewport">' +
        '        <div class="camera-idle"><div style="font-size:40px;">📷</div><div>Запуск...</div></div>' +
        '      </div>' +
        '      <div class="sk-ai-result" data-sk="aiResult" style="display:none;">' +
        '        <div class="sk-ai-label">Распознано / Recunoscut:</div>' +
        '        <div class="sk-ai-product" data-sk="aiProduct">—</div>' +
        '        <div class="sk-ai-confidence" data-sk="aiConfidence"></div>' +
        '      </div>' +
        emulatorHtml +
        '    </div>' +
        '  </div>' +
        '</div>';

    document.body.appendChild(div);
    this._container = div;
};

// ---- Event binding (delegation) ----
ScaleKiosk.prototype._bindEvents = function() {
    var self = this;

    this._container.addEventListener('click', function(e) {
        var t = e.target;

        // Close button
        if (t.matches('[data-sk="closeBtn"]') || t.closest('[data-sk="closeBtn"]')) {
            self.close(); return;
        }

        // Pause
        if (t.matches('[data-sk="pauseBtn"]') || t.closest('[data-sk="pauseBtn"]')) {
            self._togglePause(); return;
        }

        // Zero / Tare
        if (t.matches('[data-sk="zeroBtn"]')) { self._scaleZero(); return; }
        if (t.matches('[data-sk="tareBtn"]')) { self._scaleTare(); return; }

        // Capture
        if (t.matches('[data-sk="captureBtn"]')) { self._capture(); return; }

        // Numpad digits
        var numBtn = t.closest('[data-num]');
        if (numBtn) { self._numpadPress(numBtn.getAttribute('data-num')); return; }

        // Numpad apply
        if (t.matches('[data-sk="numpadApply"]')) { self._numpadApply(); return; }

        // Product grid
        var prodBtn = t.closest('.sk-product-btn');
        if (prodBtn && self._container.contains(prodBtn)) {
            var key = prodBtn.getAttribute('data-product');
            if (key) self._selectProduct(key);
            return;
        }

        // Passport: stepper
        var stepBtn = t.closest('[data-step]');
        if (stepBtn) {
            self._stepField(stepBtn.getAttribute('data-step'), parseFloat(stepBtn.getAttribute('data-delta')));
            return;
        }

        // Passport: rating
        var rateBtn = t.closest('.sk-rate-btn');
        if (rateBtn) {
            var ratingGroup = rateBtn.closest('.sk-rating');
            if (ratingGroup) self._setRating(ratingGroup, parseInt(rateBtn.getAttribute('data-rate')));
            return;
        }

        // Passport: opt-btn
        var optBtn = t.closest('.sk-opt-btn');
        if (optBtn) {
            var optGroup = optBtn.closest('.sk-btn-group');
            if (optGroup) self._selectOpt(optGroup, optBtn);
            return;
        }

        // Passport: variety
        var varBtn = t.closest('.sk-variety-btn');
        if (varBtn) {
            var vIndex = varBtn.getAttribute('data-vidx');
            if (vIndex !== null) self._selectVarietyByIndex(parseInt(vIndex));
            return;
        }

        // Emulator buttons
        if (t.matches('[data-sk="emuSet"]')) { self._emuSet(); return; }
        if (t.matches('[data-sk="emuRandom"]')) { self._emuRandom(); return; }
        if (t.matches('[data-sk="emuRemove"]')) { self._emuRemove(); return; }
    });

    // Color slider input event
    if (this.showPassport) {
        this._container.addEventListener('input', function(e) {
            if (e.target.matches('[data-sk="ppColorSlider"]')) {
                var valEl = self.$('ppColorVal');
                if (valEl) valEl.textContent = e.target.value + '%';
            }
        });
    }
};

// ---- Public API ----
ScaleKiosk.prototype.open = function(lineId) {
    this._targetLineId = lineId;
    this._selectedProduct = null;
    this._selectedVariety = null;
    this._manualWeight = false;
    this._paused = false;

    // Reset UI
    this.$('gross').textContent = '0.000';
    this.$('tare').textContent = '0.000';
    this.$('net').textContent = '0.000';
    this.$('statusText').textContent = 'Запуск... / Pornire...';
    this.$('indicator').style.background = '#ffc107';
    this.$('captureBtn').disabled = true;
    this.$('captureBtn').textContent = '⚖️ Снять вес / Cântărește';
    this.$('aiResult').style.display = 'none';
    this.$('numpadInput').value = '';
    this.$('viewport').innerHTML =
        '<div class="camera-idle"><div style="font-size:40px;">📷</div><div>Запуск... / Pornire...</div></div>';

    var pauseBtn = this.$('pauseBtn');
    if (pauseBtn) { pauseBtn.classList.remove('active'); pauseBtn.textContent = '⏸ Пауза / Pauză'; }

    if (this.showPassport) this._hidePassport();

    // Load driver config
    if (this.loadDriverConfig) this._loadDriverConfig();

    // Build product grid
    this._buildProductGrid();

    // Show
    this._container.style.display = 'flex';

    // Start polling + emulation
    this._startPolling();
    this._startAutoEmulation();
};

ScaleKiosk.prototype.close = function() {
    this._container.style.display = 'none';
    this._stopPolling();
    this._stopAutoEmulation();
    this._targetLineId = null;
    this._selectedProduct = null;
    this._selectedVariety = null;
    this._paused = false;
    if (this.showPassport) this._hidePassport();
};

ScaleKiosk.prototype.destroy = function() {
    this.close();
    if (this._container && this._container.parentNode) {
        this._container.parentNode.removeChild(this._container);
    }
    this._container = null;
};

// ---- Product grid ----
ScaleKiosk.prototype._buildProductGrid = function() {
    var grid = this.$('productGrid');
    if (!grid) return;
    grid.innerHTML = '';
    var self = this;
    this._productKeys.forEach(function(key) {
        var btn = document.createElement('button');
        btn.className = 'sk-product-btn';
        btn.setAttribute('data-product', key);
        var imgSrc = self._productImages[key];
        var emoji = EMOJI_MAP[key] || '📦';
        var label = self._productNames[key] || key;
        if (imgSrc) {
            btn.innerHTML =
                '<img src="' + imgSrc + '" alt="' + key + '" class="sk-product-img" onerror="this.style.display=\'none\'">' +
                '<div class="sk-product-emoji" style="display:none;">' + emoji + '</div>' +
                '<span class="sk-product-label">' + label + '</span>';
            // If img fails, show emoji
            var img = btn.querySelector('img');
            img.addEventListener('error', function() { btn.querySelector('.sk-product-emoji').style.display = ''; });
        } else {
            btn.innerHTML =
                '<div class="sk-product-emoji">' + emoji + '</div>' +
                '<span class="sk-product-label">' + label + '</span>';
        }
        grid.appendChild(btn);
    });
};

ScaleKiosk.prototype._selectProduct = function(key) {
    this._selectedProduct = key;
    this._highlightProduct(key);

    // Update AI panel
    this.$('aiResult').style.display = 'block';
    this.$('aiProduct').textContent = this._productNames[key] || key;
    this.$('aiConfidence').textContent = 'Выбрано вручную / Selectat manual';

    // Camera viewport
    var imgSrc = this._productImages[key];
    var emoji = EMOJI_MAP[key] || '📦';
    var label = this._productNames[key] || key;
    var imgHtml = imgSrc
        ? '<img src="' + imgSrc + '" class="camera-product-img" alt="' + key + '" onerror="this.outerHTML=\'<div style=font-size:64px>' + emoji + '</div>\'">'
        : '<div style="font-size:64px;">' + emoji + '</div>';
    this.$('viewport').innerHTML =
        '<div class="camera-product-preview">' + imgHtml +
        '<div class="camera-product-name">' + label + '</div></div>';

    // Passport
    if (this.showPassport) this._showPassport(key);
};

ScaleKiosk.prototype._highlightProduct = function(key) {
    var btns = this.$$('productGrid')[0];
    if (!btns) return;
    var all = btns.querySelectorAll('.sk-product-btn');
    for (var i = 0; i < all.length; i++) {
        all[i].classList.toggle('active', all[i].getAttribute('data-product') === key);
    }
};

// ---- Scale polling ----
ScaleKiosk.prototype._startPolling = function() {
    this._stopPolling();
    var self = this;
    this._pollScale();
    this._pollTimer = setInterval(function() { self._pollScale(); }, 1000);
};

ScaleKiosk.prototype._stopPolling = function() {
    if (this._pollTimer) { clearInterval(this._pollTimer); this._pollTimer = null; }
};

ScaleKiosk.prototype._pollScale = function() {
    var self = this;
    fetch('/api/agro-scale/read?scale_id=' + this.scaleId)
        .then(function(r) { return r.json(); })
        .then(function(res) {
            if (!res.success) return;
            var d = res.data;
            self.$('gross').textContent = d.gross_kg.toFixed(3);
            self.$('tare').textContent = d.tare_kg.toFixed(3);
            self.$('net').textContent = d.net_kg.toFixed(3);

            var indicator = self.$('indicator');
            var statusText = self.$('statusText');
            var captureBtn = self.$('captureBtn');

            if (d.status === 'stable' && d.gross_kg > 0) {
                indicator.style.background = '#53d769';
                statusText.textContent = '● Stable / Стабильно';
                captureBtn.disabled = false;
            } else if (d.status === 'settling') {
                indicator.style.background = '#ffc107';
                statusText.textContent = '◌ Settling... / Стабилизация...';
                captureBtn.disabled = true;
            } else {
                indicator.style.background = '#666';
                statusText.textContent = 'Idle / Ожидание';
                captureBtn.disabled = true;
            }
        }).catch(function() {
            var ind = self.$('indicator');
            if (ind) ind.style.background = '#e94560';
            var st = self.$('statusText');
            if (st) st.textContent = 'Ошибка связи';
        });
};

// ---- Scale commands ----
ScaleKiosk.prototype._scaleZero = function() {
    fetch('/api/agro-scale/zero', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({scale_id: this.scaleId})
    });
};

ScaleKiosk.prototype._scaleTare = function() {
    fetch('/api/agro-scale/tare', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({scale_id: this.scaleId})
    });
};

// ---- Numpad ----
ScaleKiosk.prototype._numpadPress = function(val) {
    var inp = this.$('numpadInput');
    if (!inp) return;
    if (val === 'del') {
        inp.value = inp.value.slice(0, -1);
    } else if (val === '.') {
        if (inp.value.indexOf('.') === -1) inp.value += '.';
    } else {
        if (inp.value.replace('.', '').length < 6) inp.value += val;
    }
};

ScaleKiosk.prototype._numpadApply = function() {
    var inp = this.$('numpadInput');
    var weight = parseFloat(inp.value);
    if (!weight || weight <= 0) return;
    this._manualWeight = true;
    this._stopAutoEmulation();

    var self = this;
    fetch('/api/agro-scale/simulate', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({scale_id: this.scaleId, weight_kg: weight})
    }).then(function(r) { return r.json(); })
    .then(function() {
        self.$('gross').textContent = weight.toFixed(3);
        self.$('net').textContent = weight.toFixed(3);
        self.$('indicator').style.background = '#ffc107';
        self.$('statusText').textContent = 'Ручной ввод / Manual';
        self.$('captureBtn').disabled = false;
        inp.value = '';
    });
};

// ---- Auto-emulation ----
ScaleKiosk.prototype._startAutoEmulation = function() {
    this._stopAutoEmulation();
    var self = this;
    this._runEmulationCycle();
    this._emuTimer = setInterval(function() { self._runEmulationCycle(); }, this.emulationInterval);
};

ScaleKiosk.prototype._stopAutoEmulation = function() {
    if (this._emuTimer) { clearInterval(this._emuTimer); this._emuTimer = null; }
};

ScaleKiosk.prototype._togglePause = function() {
    this._paused = !this._paused;
    var btn = this.$('pauseBtn');
    if (btn) {
        btn.classList.toggle('active', this._paused);
        btn.textContent = this._paused ? '▶ Продолжить / Continuă' : '⏸ Пауза / Pauză';
    }
};

ScaleKiosk.prototype._runEmulationCycle = function() {
    if (this._paused) return;
    var viewport = this.$('viewport');
    var captureBtn = this.$('captureBtn');
    if (!viewport) return;

    viewport.innerHTML =
        '<div class="camera-scanning">' +
        '<div style="font-size:13px;color:#ffc107;margin-bottom:12px;">🔍 Сканирование... / Scanare...</div>' +
        '<div class="camera-scanline"></div>' +
        '<div style="font-size:11px;color:var(--text-muted,#8888aa);margin-top:12px;">Анализ изображения / Analiza imaginii</div>' +
        '</div>';

    var self = this;
    var range = this.weightRange;

    fetch('/api/agro-scale/simulate', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({scale_id: this.scaleId, random: true, min_kg: range.min, max_kg: range.max})
    }).then(function(r) { return r.json(); })
    .then(function() {
        var attempts = 0;
        var stableTimer = setInterval(function() {
            attempts++;
            fetch('/api/agro-scale/read?scale_id=' + self.scaleId)
                .then(function(r) { return r.json(); })
                .then(function(res) {
                    if (!res.success) return;
                    if (res.data.stable || attempts >= 20) {
                        clearInterval(stableTimer);
                        var randomKey = self._productKeys[Math.floor(Math.random() * self._productKeys.length)];
                        self._selectedProduct = randomKey;
                        var imgSrc = self._productImages[randomKey];
                        var emoji = EMOJI_MAP[randomKey] || '📦';
                        var productLabel = self._productNames[randomKey] || randomKey;
                        var confidence = (85 + Math.random() * 14).toFixed(1);
                        var d = res.data;

                        self._highlightProduct(randomKey);
                        if (self.showPassport) self._showPassport(randomKey);

                        var imgHtml = imgSrc
                            ? '<img src="' + imgSrc + '" class="camera-product-img" alt="' + productLabel + '" onerror="this.outerHTML=\'<div style=font-size:64px>' + emoji + '</div>\'">'
                            : '<div style="font-size:64px;">' + emoji + '</div>';
                        viewport.innerHTML =
                            '<div class="camera-product-preview">' + imgHtml +
                            '<div class="camera-product-name">' + productLabel + '</div>' +
                            '<div class="camera-ai-confidence">' +
                            '<div class="camera-ai-bar"><div class="camera-ai-bar-fill" style="width:' + confidence + '%"></div></div>' +
                            '<span>AI: ' + confidence + '%</span>' +
                            '</div></div>';

                        self.$('aiResult').style.display = 'block';
                        self.$('aiProduct').textContent = productLabel;
                        self.$('aiConfidence').textContent =
                            'Точность: ' + confidence + '% | Вес: ' + d.net_kg.toFixed(2) + ' кг';

                        if (captureBtn) captureBtn.disabled = false;
                    }
                });
        }, 300);
    }).catch(function() {});
};

// ---- Capture ----
ScaleKiosk.prototype._capture = function() {
    var captureBtn = this.$('captureBtn');
    captureBtn.disabled = true;
    captureBtn.textContent = '⏳ Фиксация...';
    this._stopAutoEmulation();

    var self = this;
    fetch('/api/agro-scale/capture', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({scale_id: this.scaleId})
    }).then(function(r) { return r.json(); })
    .then(function(cap) {
        var reading = cap.reading || cap.data || {};
        var data = {
            lineId: self._targetLineId,
            gross: reading.gross_kg || 0,
            tare: reading.tare_kg || 0,
            net: reading.net_kg || 0,
            productKey: self._selectedProduct,
            productName: self._selectedProduct ? (self._productNames[self._selectedProduct] || self._selectedProduct) : '',
            passport: self.showPassport ? self._collectPassport() : null
        };

        self.onCapture(data);

        var weightStr = data.net.toFixed(2);
        self.close();
        captureBtn.textContent = '⚖️ Снять вес / Cântărește';
        self.toastFn('Вес снят: ' + weightStr + ' кг' + (data.productName ? ' — ' + data.productName : ''), 'success');
    }).catch(function(err) {
        captureBtn.textContent = '⚖️ Снять вес / Cântărește';
        captureBtn.disabled = false;
        self._startAutoEmulation();
        self.toastFn('Ошибка: ' + (err.message || 'связь с весами'), 'error');
    });
};

// ---- Driver config ----
ScaleKiosk.prototype._loadDriverConfig = function() {
    var self = this;
    fetch('/api/agro-admin/module-config')
        .then(function(r) { return r.json(); })
        .then(function(j) {
            if (!j.success) return;
            var drivers = (j.data || []).filter(function(r) { return r.config_group === 'scale_driver'; });
            var active = null;
            for (var i = 0; i < drivers.length; i++) {
                try {
                    var cfg = JSON.parse(drivers[i].config_value || '{}');
                    if (cfg.active !== false) { active = cfg; break; }
                } catch(e) {}
            }
            if (active) {
                var titleEl = self.$('title');
                if (titleEl) titleEl.textContent = '⚖️ Весы / Cântar — ' + (active.brand || 'Emulator');
                var infoEl = self.$('driverInfo');
                if (infoEl) infoEl.innerHTML =
                    '<span>Driver: <b>' + (active.brand || '—') + '</b></span>' +
                    '<span>Max: <b>' + (active.max_capacity || 600) + ' kg</b></span>';
            }
        }).catch(function() {});
};

// ---- Passport (purchase mode) ----
ScaleKiosk.prototype._showPassport = function(productKey) {
    if (!this.showPassport) return;
    var panel = this.$('passport');
    if (!panel) return;
    panel.style.display = 'flex';
    this.$('passportName').textContent = this._productNames[productKey] || productKey;

    var agroRefs = window._agroRefs || {};
    var allVarieties = agroRefs.varieties || [];
    this._currentVarieties = allVarieties.filter(function(v) { return v.item_code === productKey; });

    var colorRow = this.$('ppColorRow');
    var hasColor = (productKey === 'APPLE' || productKey === 'PEACH' || productKey === 'CHERRY');
    if (colorRow) colorRow.style.display = hasColor ? 'flex' : 'none';

    this._resetPassport();

    var vGrid = this.$('varietyGrid');
    this._selectedVariety = null;
    if (this._currentVarieties.length === 0) {
        vGrid.innerHTML = '<span style="font-size:12px;color:#6c6c8a;">Нет сортов / Fara soiuri</span>';
    } else {
        vGrid.innerHTML = '';
        for (var i = 0; i < this._currentVarieties.length; i++) {
            var v = this._currentVarieties[i];
            var btn = document.createElement('button');
            btn.className = 'sk-variety-btn';
            btn.textContent = v.name_ru || v.code;
            btn.setAttribute('data-vidx', i);
            vGrid.appendChild(btn);
        }
        this._selectVarietyByIndex(0);
    }
};

ScaleKiosk.prototype._selectVarietyByIndex = function(idx) {
    if (!this._currentVarieties || idx >= this._currentVarieties.length) return;
    var v = this._currentVarieties[idx];
    this._selectedVariety = v;

    var btns = this.$('varietyGrid').querySelectorAll('.sk-variety-btn');
    for (var i = 0; i < btns.length; i++) {
        btns[i].classList.toggle('active', parseInt(btns[i].getAttribute('data-vidx')) === idx);
    }

    var cr = this.$('ppCalibrRef');
    var br = this.$('ppBrixRef');
    var clr = this.$('ppColorRef');
    var tr = this.$('ppTempRef');
    var sl = this.$('ppShelfLife');
    if (cr) cr.textContent = v.min_calibre_mm ? 'мин. ' + v.min_calibre_mm + ' мм' : '';
    if (br) br.textContent = v.min_brix ? 'мин. ' + v.min_brix + '°' : '';
    if (clr) clr.textContent = v.color_coverage_pct ? 'мин. ' + v.color_coverage_pct + '%' : '';
    if (tr) tr.textContent = (v.optimal_temp_min != null ? v.optimal_temp_min + '…' + v.optimal_temp_max + ' °C' : '');
    if (sl) sl.textContent = v.shelf_life_days ? v.shelf_life_days + ' дн.' : '—';

    if (v.min_calibre_mm) { var c = this.$('ppCalibr'); if (c) { c.value = v.min_calibre_mm; c.placeholder = v.min_calibre_mm; } }
    if (v.min_brix) { var b = this.$('ppBrix'); if (b) { b.value = v.min_brix; b.placeholder = v.min_brix; } }
    if (v.color_coverage_pct) {
        var cs = this.$('ppColorSlider'); if (cs) cs.value = v.color_coverage_pct;
        var cv = this.$('ppColorVal'); if (cv) cv.textContent = v.color_coverage_pct + '%';
    }
    if (v.optimal_temp_min != null) {
        var tp = this.$('ppTemp');
        if (tp) { tp.value = v.optimal_temp_min; tp.placeholder = v.optimal_temp_min + '…' + v.optimal_temp_max; }
    }
};

ScaleKiosk.prototype._resetPassport = function() {
    var fields = ['ppCalibr','ppBrix','ppTemp'];
    for (var i = 0; i < fields.length; i++) {
        var f = this.$(fields[i]); if (f) f.value = '';
    }
    var cs = this.$('ppColorSlider'); if (cs) cs.value = 50;
    var cv = this.$('ppColorVal'); if (cv) cv.textContent = '50%';
    var dp = this.$('ppDefectPct'); if (dp) dp.value = '0';
    var notes = this.$('ppNotes'); if (notes) notes.value = '';

    var freshness = this.$('ppFreshness');
    if (freshness) this._setRating(freshness, 4);

    var defaults = {ppPackaging: 'ok', ppLabel: 'ok', ppDefects: 'none'};
    var self = this;
    ['ppPackaging','ppLabel','ppDefects'].forEach(function(gid) {
        var grp = self.$(gid);
        if (grp) {
            grp.setAttribute('data-value', defaults[gid]);
            var btns = grp.querySelectorAll('.sk-opt-btn');
            for (var j = 0; j < btns.length; j++) {
                btns[j].classList.toggle('active', j === 0);
            }
        }
    });
    var defRow = this.$('ppDefectPctRow');
    if (defRow) defRow.style.display = 'none';
};

ScaleKiosk.prototype._hidePassport = function() {
    var panel = this.$('passport');
    if (panel) panel.style.display = 'none';
    this._selectedVariety = null;
};

ScaleKiosk.prototype._stepField = function(fieldName, delta) {
    var inp = this.$(fieldName);
    if (!inp) return;
    var val = parseFloat(inp.value) || 0;
    val = Math.round((val + delta) * 10) / 10;
    if (inp.min !== '' && val < parseFloat(inp.min)) val = parseFloat(inp.min);
    if (inp.max !== '' && val > parseFloat(inp.max)) val = parseFloat(inp.max);
    inp.value = val;
};

ScaleKiosk.prototype._setRating = function(group, val) {
    var btns = group.querySelectorAll('.sk-rate-btn');
    for (var i = 0; i < btns.length; i++) {
        btns[i].classList.toggle('active', parseInt(btns[i].getAttribute('data-rate')) <= val);
    }
    group.setAttribute('data-value', val);
};

ScaleKiosk.prototype._selectOpt = function(group, btn) {
    var all = group.querySelectorAll('.sk-opt-btn');
    for (var i = 0; i < all.length; i++) all[i].classList.remove('active');
    btn.classList.add('active');
    var val = btn.getAttribute('data-opt');
    group.setAttribute('data-value', val);

    // Show defect % when defects != none
    var skName = group.getAttribute('data-sk');
    if (skName === 'ppDefects') {
        var row = this.$('ppDefectPctRow');
        if (row) row.style.display = (val !== 'none') ? 'flex' : 'none';
    }
};

ScaleKiosk.prototype._collectPassport = function() {
    if (!this.showPassport) return null;
    return {
        product_key: this._selectedProduct,
        variety_id: this._selectedVariety ? this._selectedVariety.id : null,
        variety_code: this._selectedVariety ? this._selectedVariety.code : null,
        calibre_mm: parseFloat((this.$('ppCalibr') || {}).value) || null,
        brix: parseFloat((this.$('ppBrix') || {}).value) || null,
        color_coverage_pct: parseInt((this.$('ppColorSlider') || {}).value) || null,
        freshness_score: parseInt(((this.$('ppFreshness') || {}).getAttribute('data-value')) || '4'),
        temp_c: parseFloat((this.$('ppTemp') || {}).value) || null,
        packaging: ((this.$('ppPackaging') || {}).getAttribute('data-value')) || 'ok',
        labeling: ((this.$('ppLabel') || {}).getAttribute('data-value')) || 'ok',
        defects: ((this.$('ppDefects') || {}).getAttribute('data-value')) || 'none',
        defect_pct: parseFloat((this.$('ppDefectPct') || {}).value) || 0,
        notes: (this.$('ppNotes') || {}).value || ''
    };
};

// ---- Emulator (sale mode) ----
ScaleKiosk.prototype._emuSet = function() {
    var inp = this.$('emuWeight');
    var kg = parseFloat(inp.value);
    if (isNaN(kg) || kg < 0) { this.toastFn('Введите вес для эмулятора', 'warning'); return; }
    var self = this;
    fetch('/api/agro-scale/simulate', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({scale_id: this.scaleId, weight_kg: kg})
    }).then(function(r) { return r.json(); })
    .then(function(d) { if (d.success) self.toastFn('Эмулятор: ' + kg + ' кг'); });
};

ScaleKiosk.prototype._emuRandom = function() {
    var self = this;
    var range = this.weightRange;
    fetch('/api/agro-scale/simulate', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({scale_id: this.scaleId, random: true, min_kg: range.min, max_kg: range.max})
    }).then(function(r) { return r.json(); })
    .then(function(d) { if (d.success) self.toastFn('Эмулятор: случайный вес'); });
};

ScaleKiosk.prototype._emuRemove = function() {
    var self = this;
    fetch('/api/agro-scale/simulate', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({scale_id: this.scaleId, weight_kg: 0})
    }).then(function(r) { return r.json(); })
    .then(function(d) { if (d.success) self.toastFn('Эмулятор: вес убран'); });
};

window.ScaleKiosk = ScaleKiosk;
})();
